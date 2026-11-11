"""Configuration, read from the environment (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    token: str
    admin_ids: frozenset[int]
    shop_name: str = "Auto Shop"
    fiat: str = "EUR"
    support: str = ""
    # code -> address, for coins checked automatically on-chain
    wallets: dict[str, str] = field(default_factory=dict)
    # code -> address, for coins an admin confirms by hand
    extra_wallets: dict[str, str] = field(default_factory=dict)
    order_ttl: int = 3600
    min_conf: int = 1
    max_pending: int = 3
    trongrid_key: str = ""
    db_path: str = "shop.db"
    # https address of the Mini App page; empty = no Mini App button
    miniapp_url: str = ""
    # how long after expiry a late payment is still recognised
    late_grace: int = 6 * 3600


def _pairs(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in raw.split(","):
        code, sep, address = part.strip().partition(":")
        if sep and code.strip() and address.strip():
            out[code.strip().upper()] = address.strip()
    return out


def load_config() -> Config:
    load_dotenv()
    env = os.environ.get

    token = (env("BOT_TOKEN") or "").strip()
    if not token:
        raise SystemExit("BOT_TOKEN manquant : copiez .env.example en .env et remplissez-le.")

    admins = frozenset(int(x) for x in (env("ADMIN_IDS") or "").replace(" ", "").split(",") if x)
    if not admins:
        raise SystemExit("ADMIN_IDS manquant : indiquez au moins un identifiant Telegram admin.")

    wallets = {}
    for code in ("BTC", "LTC", "USDT_TRC20"):
        address = (env(f"WALLET_{code}") or "").strip()
        if address:
            wallets[code] = address
    extra = {k: v for k, v in _pairs(env("EXTRA_WALLETS") or "").items() if k not in wallets}
    if not wallets and not extra:
        raise SystemExit("Aucune adresse crypto configuree (WALLET_BTC, WALLET_LTC, ...).")

    miniapp = (env("MINIAPP_URL") or "").strip()
    if miniapp and not miniapp.startswith("https://"):
        raise SystemExit("MINIAPP_URL doit commencer par https:// (Telegram refuse les autres adresses).")

    return Config(
        token=token,
        miniapp_url=miniapp,
        admin_ids=admins,
        shop_name=(env("SHOP_NAME") or "Auto Shop").strip(),
        fiat=(env("FIAT") or "EUR").strip().upper(),
        support=(env("SUPPORT") or "").strip(),
        wallets=wallets,
        extra_wallets=extra,
        order_ttl=max(5, int(env("ORDER_TTL_MIN") or 60)) * 60,
        min_conf=max(0, int(env("MIN_CONFIRMATIONS") or 1)),
        max_pending=max(1, int(env("MAX_PENDING") or 3)),
        trongrid_key=(env("TRONGRID_API_KEY") or "").strip(),
        db_path=(env("DB_PATH") or "shop.db").strip(),
    )
