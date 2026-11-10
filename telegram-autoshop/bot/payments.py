"""Payment watcher and delivery."""
from __future__ import annotations

import asyncio
import logging
from html import escape

import aiohttp
from aiogram import Bot
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

from .chains import COINS, fetch_incoming, match_payment
from .config import Config
from .db import Database

log = logging.getLogger("shop.payments")

POLL_SECONDS = 30


async def notify_admins(bot: Bot, cfg: Config, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    for admin_id in cfg.admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=markup)
        except Exception as exc:  # an admin who never started the bot must not break the flow
            log.warning("cannot notify admin %s: %s", admin_id, exc)


async def _safe_send(bot: Bot, user_id: int, text: str) -> None:
    try:
        await bot.send_message(user_id, text)
    except Exception as exc:
        log.warning("cannot message user %s: %s", user_id, exc)


async def deliver(bot: Bot, db: Database, cfg: Config, order: dict) -> bool:
    """Send a paid order's goods to the buyer. Safe to call again if it failed."""
    product = await db.get_product(order["product_id"]) or {}
    header = f"✅ <b>Paiement reçu — commande #{order['id']}</b>\n{escape(order['product_name'])} × {order['qty']}\n\n"
    try:
        if order["product_kind"] == "stock":
            items = await db.order_items(order["id"])
            body = "\n".join(items)
            if len(body) <= 3000:
                lines = "\n".join(f"<code>{escape(i)}</code>" for i in items)
                await bot.send_message(order["user_id"], header + lines)
            else:
                await bot.send_message(order["user_id"], header + "Vos articles sont dans le fichier ci-dessous.")
                await bot.send_document(
                    order["user_id"], BufferedInputFile(body.encode(), filename=f"commande-{order['id']}.txt")
                )
        else:
            text = header + (escape(product.get("content") or ""))
            await bot.send_message(order["user_id"], text)
            if product.get("file_id"):
                await bot.send_document(order["user_id"], product["file_id"])
    except Exception as exc:
        # Stays 'paid': the watcher retries, and the admin is told once.
        log.error("delivery of order %s failed: %s", order["id"], exc)
        return False
    await db.mark_delivered(order["id"])
    return True


async def settle(bot: Bot, db: Database, cfg: Config, order: dict, txid: str | None) -> str | None:
    """Mark an order paid and deliver it. Returns the resulting status (None if nothing changed)."""
    status = await db.mark_paid(order["id"], txid)
    if status is None:
        return None
    total = f"{order['price_cents'] / 100:.2f} {order['fiat']}"
    summary = (
        f"commande #{order['id']} — {escape(order['product_name'])} × {order['qty']} — {total} "
        f"en {order['coin']}" + (f"\nTX : <code>{escape(txid)}</code>" if txid else "\n(validée à la main)")
    )
    if status == "paid_no_stock":
        await _safe_send(
            bot, order["user_id"],
            f"⚠️ Paiement reçu pour la commande #{order['id']}, mais elle avait expiré et le stock est épuisé. "
            "Un administrateur a été prévenu et va vous livrer ou vous rembourser.",
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔁 Réessayer la livraison", callback_data=f"a:retry:{order['id']}")
        ]])
        await notify_admins(bot, cfg, f"⚠️ <b>Payé mais plus de stock</b>\n{summary}\nRéapprovisionnez puis réessayez.", markup)
        return status
    if await deliver(bot, db, cfg, order):
        await notify_admins(bot, cfg, f"💰 <b>Vente</b>\n{summary}")
        return "delivered"
    await notify_admins(bot, cfg, f"⚠️ <b>Payé, livraison en échec</b> (nouvel essai automatique)\n{summary}")
    return status


async def check_orders(
    bot: Bot, db: Database, cfg: Config, session: aiohttp.ClientSession, orders: list[dict]
) -> dict[int, str]:
    """Look on-chain for the payments of `orders`. Returns {order_id: 'delivered'|'paid'|'seen'|...}."""
    result: dict[int, str] = {}
    by_coin: dict[str, list[dict]] = {}
    for order in orders:
        if order["amount_atomic"] > 0 and order["coin"] in COINS and order["coin"] in cfg.wallets:
            by_coin.setdefault(order["coin"], []).append(order)
    for code, group in by_coin.items():
        try:
            incoming = await fetch_incoming(session, COINS[code], cfg.wallets[code], cfg.trongrid_key)
        except Exception as exc:
            log.warning("explorer error for %s: %s", code, exc)
            continue
        used = await db.used_txids()
        for order in group:
            # Only match payments sent to the address this order was told to pay.
            if order["address"] != cfg.wallets[code]:
                continue
            state, tx = match_payment(order, incoming, used, cfg.min_conf)
            if state == "paid":
                status = await settle(bot, db, cfg, order, tx.txid)
                used.add(tx.txid)
                if status:
                    result[order["id"]] = status
            elif state == "seen":
                result[order["id"]] = "seen"
                if order["seen_txid"] != tx.txid:
                    await db.set_seen(order["id"], tx.txid)
                    await _safe_send(
                        bot, order["user_id"],
                        f"⏳ Paiement détecté pour la commande #{order['id']}. "
                        "Livraison automatique dès la confirmation sur la blockchain.",
                    )
    return result


async def watch(bot: Bot, db: Database, cfg: Config, session: aiohttp.ClientSession) -> None:
    """Background loop: expire old orders, detect payments, retry failed deliveries."""
    while True:
        try:
            for order in await db.expire_due():
                await _safe_send(
                    bot, order["user_id"],
                    f"⌛ La commande #{order['id']} a expiré. Si vous avez déjà payé, elle sera livrée dès que "
                    "le paiement sera confirmé.",
                )
            await check_orders(bot, db, cfg, session, await db.watch_orders(cfg.late_grace))
            for order in await db.orders_by_status("paid"):
                await deliver(bot, db, cfg, order)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("watcher cycle failed")
        await asyncio.sleep(POLL_SECONDS)
