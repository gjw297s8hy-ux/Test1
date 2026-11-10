"""Customer side: catalogue, checkout, orders."""
from __future__ import annotations

import logging
import time
from html import escape

import aiohttp
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from ..chains import COINS, format_amount, get_rate, to_atomic
from ..config import Config
from ..db import Database
from ..payments import check_orders, notify_admins

log = logging.getLogger("shop.user")
router = Router()

MAX_QTY = 50
STATUS_LABEL = {
    "pending": "⏳ en attente de paiement",
    "paid": "✅ payée, livraison en cours",
    "delivered": "📦 livrée",
    "expired": "⌛ expirée",
    "cancelled": "❌ annulée",
    "paid_no_stock": "⚠️ payée, en attente de stock",
}


class TxidForm(StatesGroup):
    waiting = State()


def kb(*rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d) for t, d in row] for row in rows]
    )


def price(cents: int, fiat: str) -> str:
    return f"{cents / 100:.2f} {fiat}"


async def show(cb: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    """Replace the current menu message, falling back to a new one."""
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as exc:
        if "not modified" not in str(exc):
            await cb.message.answer(text, reply_markup=markup)
    await cb.answer()


def home_view(cfg: Config) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"👋 Bienvenue sur <b>{escape(cfg.shop_name)}</b>.\n\n"
        "Choisissez un produit, payez en crypto, et recevez-le ici automatiquement."
    )
    return text, kb([("🛍 Catalogue", "cat")], [("📦 Mes commandes", "orders"), ("ℹ️ Aide", "help")])


def order_view(order: dict, cfg: Config) -> tuple[str, InlineKeyboardMarkup]:
    head = (
        f"🧾 <b>Commande #{order['id']}</b>\n{escape(order['product_name'])} × {order['qty']} — "
        f"{price(order['price_cents'], order['fiat'])}\nStatut : {STATUS_LABEL.get(order['status'], order['status'])}\n"
    )
    back = [("⬅️ Menu", "home")]
    if order["status"] != "pending":
        return head, kb(back)
    minutes = max(0, (order["expires_at"] - int(time.time())) // 60)
    if order["amount_atomic"] > 0:
        coin = COINS[order["coin"]]
        text = head + (
            f"\nEnvoyez <b>exactement</b> ce montant en {coin.label} :\n"
            f"<code>{format_amount(order['amount_atomic'], coin)}</code> {coin.unit}\n\n"
            f"À cette adresse :\n<code>{escape(order['address'])}</code>\n\n"
            "⚠️ Le montant doit être exact (frais de réseau en plus) : c'est lui qui identifie votre commande.\n"
            f"⏱ Valable encore {minutes} min. Livraison automatique après confirmation."
        )
        return text, kb([("🔄 Vérifier le paiement", f"chk:{order['id']}")], [("❌ Annuler", f"cxl:{order['id']}")], back)
    text = head + (
        f"\nEnvoyez l'équivalent de <b>{price(order['price_cents'], order['fiat'])}</b> en {escape(order['coin'])} "
        f"à cette adresse :\n<code>{escape(order['address'])}</code>\n\n"
        "Puis appuyez sur « J'ai payé » et envoyez l'identifiant de la transaction. "
        f"Un administrateur validera votre commande.\n⏱ Valable encore {minutes} min."
    )
    return text, kb([("✅ J'ai payé", f"paid:{order['id']}")], [("❌ Annuler", f"cxl:{order['id']}")], back)


# ------------------------------------------------------------------ menu


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, db: Database, cfg: Config) -> None:
    await state.clear()
    await db.upsert_user(message.from_user.id, message.from_user.username)
    text, markup = home_view(cfg)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "home")
async def home(cb: CallbackQuery, state: FSMContext, cfg: Config) -> None:
    await state.clear()
    await show(cb, *home_view(cfg))


@router.message(Command("help"))
async def help_cmd(message: Message, cfg: Config) -> None:
    await message.answer(help_text(cfg))


def help_text(cfg: Config) -> str:
    text = (
        "ℹ️ <b>Comment ça marche</b>\n\n"
        "1. Choisissez un produit dans le catalogue.\n"
        "2. Choisissez la crypto-monnaie : le bot affiche une adresse et un montant exact.\n"
        "3. Envoyez ce montant. Dès la confirmation, le produit arrive dans cette conversation."
    )
    if cfg.support:
        text += f"\n\nUn problème ? Contactez {escape(cfg.support)}."
    return text


@router.callback_query(F.data == "help")
async def help_cb(cb: CallbackQuery, cfg: Config) -> None:
    await show(cb, help_text(cfg), kb([("⬅️ Menu", "home")]))


# ------------------------------------------------------------------ catalogue


@router.callback_query(F.data == "cat")
async def catalogue(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    products = await db.list_products()
    if not products:
        await show(cb, "Le catalogue est vide pour le moment.", kb([("⬅️ Menu", "home")]))
        return
    rows = []
    for p in products:
        if p["kind"] == "stock":
            stock = f"{p['in_stock']} en stock" if p["in_stock"] else "rupture"
        else:
            stock = "disponible"
        rows.append([(f"{p['name']} — {price(p['price_cents'], cfg.fiat)} ({stock})", f"p:{p['id']}:1")])
    rows.append([("⬅️ Menu", "home")])
    await show(cb, "🛍 <b>Catalogue</b>", kb(*rows))


@router.callback_query(F.data.regexp(r"^p:(\d+):(\d+)$").as_("m"))
async def product_page(cb: CallbackQuery, m, db: Database, cfg: Config) -> None:
    product = await db.get_product(int(m.group(1)))
    if not product or not product["active"]:
        await cb.answer("Ce produit n'est plus disponible.", show_alert=True)
        return
    unique = product["kind"] == "stock"
    limit = min(MAX_QTY, product["in_stock"]) if unique else 1
    qty = max(1, min(int(m.group(2)), max(1, limit)))
    text = f"<b>{escape(product['name'])}</b>\n\n{escape(product['description'])}\n\n"
    text += f"Prix : <b>{price(product['price_cents'], cfg.fiat)}</b>"
    rows = []
    if unique:
        text += f"\nStock : {product['in_stock']}"
        if product["in_stock"] == 0:
            await show(cb, text + "\n\n❌ Rupture de stock.", kb([("⬅️ Catalogue", "cat")]))
            return
        if limit > 1:
            text += f"\nQuantité : <b>{qty}</b> — total {price(product['price_cents'] * qty, cfg.fiat)}"
            rows.append([
                ("➖", f"p:{product['id']}:{max(1, qty - 1)}"),
                (str(qty), f"p:{product['id']}:{qty}"),
                ("➕", f"p:{product['id']}:{min(limit, qty + 1)}"),
            ])
    rows += [[("🛒 Acheter", f"buy:{product['id']}:{qty}")], [("⬅️ Catalogue", "cat")]]
    await show(cb, text, kb(*rows))


@router.callback_query(F.data.regexp(r"^buy:(\d+):(\d+)$").as_("m"))
async def choose_coin(cb: CallbackQuery, m, cfg: Config) -> None:
    pid, qty = m.group(1), m.group(2)
    rows = [[(COINS[code].label, f"pay:{pid}:{qty}:{code}")] for code in cfg.wallets if code in COINS]
    rows += [[(f"{code} (validation manuelle)", f"pay:{pid}:{qty}:{code}")] for code in cfg.extra_wallets]
    rows.append([("⬅️ Retour", f"p:{pid}:{qty}")])
    await show(cb, "💳 Choisissez votre moyen de paiement :", kb(*rows))


@router.callback_query(F.data.regexp(r"^pay:(\d+):(\d+):([A-Z0-9_]+)$").as_("m"))
async def create_order(cb: CallbackQuery, m, db: Database, cfg: Config, http: aiohttp.ClientSession) -> None:
    code = m.group(3)
    product = await db.get_product(int(m.group(1)))
    if not product or not product["active"]:
        await cb.answer("Ce produit n'est plus disponible.", show_alert=True)
        return
    qty = max(1, min(int(m.group(2)), MAX_QTY)) if product["kind"] == "stock" else 1
    if await db.count_pending(cb.from_user.id) >= cfg.max_pending:
        await cb.answer("Vous avez trop de commandes en attente. Payez-les ou annulez-les d'abord.", show_alert=True)
        return

    if code in cfg.wallets and code in COINS:
        coin = COINS[code]
        try:
            rate = await get_rate(http, coin, cfg.fiat)
        except Exception as exc:
            log.warning("rate lookup failed: %s", exc)
            await cb.answer("Taux de change indisponible, réessayez dans un instant.", show_alert=True)
            return
        address, base, jitter = cfg.wallets[code], to_atomic(product["price_cents"] * qty, rate, coin), coin.jitter
    elif code in cfg.extra_wallets:
        address, base, jitter = cfg.extra_wallets[code], 0, 0
    else:
        await cb.answer("Moyen de paiement indisponible.", show_alert=True)
        return

    await db.upsert_user(cb.from_user.id, cb.from_user.username)
    order = await db.create_order(
        user_id=cb.from_user.id, product=product, qty=qty, fiat=cfg.fiat, coin=code, address=address,
        base_amount=base, jitter=jitter, ttl=cfg.order_ttl, late_grace=cfg.late_grace,
    )
    if not order:
        await cb.answer("Stock insuffisant pour cette quantité.", show_alert=True)
        return
    await show(cb, *order_view(order, cfg))


# ------------------------------------------------------------------ orders


async def _own_order(cb: CallbackQuery, db: Database, order_id: int) -> dict | None:
    order = await db.get_order(order_id)
    if not order or order["user_id"] != cb.from_user.id:
        await cb.answer("Commande introuvable.", show_alert=True)
        return None
    return order


@router.callback_query(F.data == "orders")
async def my_orders(cb: CallbackQuery, db: Database) -> None:
    orders = await db.user_orders(cb.from_user.id)
    if not orders:
        await show(cb, "Vous n'avez pas encore de commande.", kb([("🛍 Catalogue", "cat")], [("⬅️ Menu", "home")]))
        return
    rows = [[(f"#{o['id']} {o['product_name']} — {STATUS_LABEL.get(o['status'], o['status'])}", f"o:{o['id']}")]
            for o in orders]
    rows.append([("⬅️ Menu", "home")])
    await show(cb, "📦 <b>Vos dernières commandes</b>", kb(*rows))


@router.callback_query(F.data.regexp(r"^o:(\d+)$").as_("m"))
async def order_page(cb: CallbackQuery, m, db: Database, cfg: Config) -> None:
    order = await _own_order(cb, db, int(m.group(1)))
    if order:
        await show(cb, *order_view(order, cfg))


@router.callback_query(F.data.regexp(r"^chk:(\d+)$").as_("m"))
async def check(cb: CallbackQuery, m, bot: Bot, db: Database, cfg: Config, http: aiohttp.ClientSession) -> None:
    order = await _own_order(cb, db, int(m.group(1)))
    if not order:
        return
    if order["status"] != "pending":
        await show(cb, *order_view(order, cfg))
        return
    state = (await check_orders(bot, db, cfg, http, [order])).get(order["id"])
    if state == "seen":
        await cb.answer("Paiement détecté, en attente de confirmation sur la blockchain.", show_alert=True)
    elif state:
        await show(cb, *order_view(await db.get_order(order["id"]), cfg))
    else:
        await cb.answer("Aucun paiement détecté pour l'instant. La vérification est aussi automatique.", show_alert=True)


@router.callback_query(F.data.regexp(r"^cxl:(\d+)$").as_("m"))
async def cancel(cb: CallbackQuery, m, db: Database, cfg: Config) -> None:
    order = await _own_order(cb, db, int(m.group(1)))
    if not order:
        return
    if order["status"] == "pending" and order["seen_txid"]:
        await cb.answer("Un paiement est en cours de confirmation : annulation impossible.", show_alert=True)
        return
    if order["status"] == "pending":
        await db.cancel_order(order["id"])
    await show(cb, *order_view(await db.get_order(order["id"]), cfg))


@router.callback_query(F.data.regexp(r"^paid:(\d+)$").as_("m"))
async def paid_manual(cb: CallbackQuery, m, state: FSMContext, db: Database) -> None:
    order = await _own_order(cb, db, int(m.group(1)))
    if not order or order["status"] != "pending" or order["amount_atomic"] > 0:
        if order:
            await cb.answer("Cette commande n'attend pas de validation.", show_alert=True)
        return
    await state.set_state(TxidForm.waiting)
    await state.update_data(order_id=order["id"])
    await cb.message.answer("Envoyez l'identifiant (hash) de votre transaction :")
    await cb.answer()


@router.message(TxidForm.waiting, F.text & ~F.text.startswith("/"))
async def receive_txid(message: Message, state: FSMContext, bot: Bot, db: Database, cfg: Config) -> None:
    data = await state.get_data()
    await state.clear()
    order = await db.get_order(data.get("order_id", 0))
    if not order or order["user_id"] != message.from_user.id or order["status"] != "pending":
        await message.answer("Cette commande n'est plus en attente.")
        return
    txid = message.text.strip()[:200]
    await db.set_note(order["id"], txid)
    who = f"@{message.from_user.username}" if message.from_user.username else str(message.from_user.id)
    await notify_admins(
        bot, cfg,
        f"🔔 <b>Paiement à valider</b>\nCommande #{order['id']} — {escape(order['product_name'])} × {order['qty']}\n"
        f"{price(order['price_cents'], order['fiat'])} en {escape(order['coin'])}\nClient : {escape(who)}\n"
        f"TX : <code>{escape(txid)}</code>",
        kb([("✅ Valider et livrer", f"a:ok:{order['id']}"), ("❌ Refuser", f"a:no:{order['id']}")]),
    )
    await message.answer("Merci. Un administrateur vérifie votre paiement ; vous serez livré ici dès validation.")
