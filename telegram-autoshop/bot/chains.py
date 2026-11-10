"""Coins, exchange rates and reading incoming payments from public block explorers.

Payments go straight to the shop owner's own addresses. Because every customer pays to the
same address, an order is recognised by its amount: each order gets a slightly different,
unique amount (see Database.create_order), and we look for a transaction of exactly that value.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import ROUND_UP, Decimal

import aiohttp

USDT_TRC20_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"


@dataclass(frozen=True)
class Coin:
    code: str
    label: str
    decimals: int
    rate_id: str  # CoinGecko id
    jitter: int  # max atomic units added to make an order's amount unique
    unit: str


COINS: dict[str, Coin] = {
    # 300 sats is a few cents; USDT/LTC jitters are well under one cent.
    "BTC": Coin("BTC", "Bitcoin (BTC)", 8, "bitcoin", 300, "BTC"),
    "LTC": Coin("LTC", "Litecoin (LTC)", 8, "litecoin", 9_999, "LTC"),
    "USDT_TRC20": Coin("USDT_TRC20", "USDT (TRC20)", 6, "tether", 9_999, "USDT"),
}

_MEMPOOL_API = {"BTC": "https://mempool.space/api", "LTC": "https://litecoinspace.org/api"}


@dataclass(frozen=True)
class Incoming:
    txid: str
    amount: int  # atomic units received by our address
    confirmations: int
    timestamp: int | None  # block time, None while unconfirmed


def format_amount(atomic: int, coin: Coin) -> str:
    """Exact decimal string for an atomic amount - never rounded, the amount identifies the order."""
    text = f"{Decimal(atomic) / (Decimal(10) ** coin.decimals):.{coin.decimals}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def to_atomic(price_cents: int, rate: Decimal, coin: Coin) -> int:
    """Convert a fiat price to atomic coin units, rounded up so the shop is never short."""
    value = (Decimal(price_cents) / 100) / rate * (Decimal(10) ** coin.decimals)
    return int(value.to_integral_value(rounding=ROUND_UP))


# ----------------------------------------------------------------------------- rates

_rate_cache: dict[tuple[str, str], tuple[float, Decimal]] = {}


async def get_rate(session: aiohttp.ClientSession, coin: Coin, fiat: str) -> Decimal:
    """Price of one coin in `fiat`, cached for a minute."""
    key = (coin.rate_id, fiat.lower())
    cached = _rate_cache.get(key)
    if cached and time.time() - cached[0] < 60:
        return cached[1]
    url = "https://api.coingecko.com/api/v3/simple/price"
    async with session.get(url, params={"ids": coin.rate_id, "vs_currencies": key[1]}) as resp:
        resp.raise_for_status()
        data = await resp.json()
    rate = Decimal(str(data[coin.rate_id][key[1]]))
    if rate <= 0:
        raise ValueError(f"invalid rate for {coin.code}")
    _rate_cache[key] = (time.time(), rate)
    return rate


# ----------------------------------------------------------------------------- explorers


async def _mempool_incoming(session: aiohttp.ClientSession, base: str, address: str) -> list[Incoming]:
    async with session.get(f"{base}/blocks/tip/height") as resp:
        resp.raise_for_status()
        tip = int((await resp.text()).strip())
    async with session.get(f"{base}/address/{address}/txs") as resp:
        resp.raise_for_status()
        txs = await resp.json()
    out = []
    for tx in txs:
        value = sum(v.get("value", 0) for v in tx.get("vout", []) if v.get("scriptpubkey_address") == address)
        if value <= 0:
            continue
        status = tx.get("status") or {}
        confirmed = bool(status.get("confirmed"))
        confirmations = max(1, tip - int(status["block_height"]) + 1) if confirmed else 0
        out.append(Incoming(tx["txid"], int(value), confirmations, status.get("block_time") if confirmed else None))
    return out


async def _tron_incoming(session: aiohttp.ClientSession, address: str, api_key: str) -> list[Incoming]:
    url = f"https://api.trongrid.io/v1/accounts/{address}/transactions/trc20"
    params = {
        "only_to": "true",
        "only_confirmed": "true",
        "limit": "100",
        "contract_address": USDT_TRC20_CONTRACT,
    }
    headers = {"TRON-PRO-API-KEY": api_key} if api_key else {}
    async with session.get(url, params=params, headers=headers) as resp:
        resp.raise_for_status()
        data = await resp.json()
    out = []
    for t in data.get("data", []):
        # Re-check the contract: anyone can deploy a token that calls itself "USDT".
        if (t.get("token_info") or {}).get("address") != USDT_TRC20_CONTRACT:
            continue
        if t.get("to") != address or t.get("type") != "Transfer":
            continue
        # only_confirmed=true means the transfer is already final on Tron.
        out.append(Incoming(t["transaction_id"], int(t["value"]), 20, int(t["block_timestamp"]) // 1000))
    return out


async def fetch_incoming(
    session: aiohttp.ClientSession, coin: Coin, address: str, trongrid_key: str = ""
) -> list[Incoming]:
    """Recent transfers received by `address`."""
    if coin.code in _MEMPOOL_API:
        return await _mempool_incoming(session, _MEMPOOL_API[coin.code], address)
    if coin.code == "USDT_TRC20":
        return await _tron_incoming(session, address, trongrid_key)
    raise ValueError(f"no explorer for {coin.code}")


def match_payment(
    order: dict, incoming: list[Incoming], used_txids: set[str], min_conf: int
) -> tuple[str, Incoming | None]:
    """Find the transfer that pays `order`.

    Returns ("paid", tx) once it has enough confirmations, ("seen", tx) while it is still
    confirming, and ("none", None) otherwise.
    """
    seen = None
    for tx in incoming:
        if tx.amount != order["amount_atomic"] or tx.txid in used_txids:
            continue
        # A transfer mined before the order existed cannot be its payment.
        if tx.timestamp is not None and tx.timestamp < order["created_at"] - 120:
            continue
        if tx.confirmations >= min_conf:
            return "paid", tx
        seen = seen or tx
    return ("seen", seen) if seen else ("none", None)
