"""Admin side: products, stock, manual order handling, stats. Reached with /admin."""
from __future__ import annotations

import io
from decimal import Decimal, InvalidOperation
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, TelegramObject

from ..config import Config
from ..db import Database
from ..payments import deliver, notify_admins, settle
from .user import STATUS_LABEL, kb, price, show

# Free-text answers in a form; a /command is never an answer, it falls through to its own handler.
TEXT = F.text & ~F.text.startswith("/")

router = Router()

MAX_STOCK_FILE = 2 * 1024 * 1024


class IsAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject, cfg: Config) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user and user.id in cfg.admin_ids)


router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


class AddProduct(StatesGroup):
    name = State()
    description = State()
    price = State()
    payload = State()


class AddStock(StatesGroup):
    items = State()


class SetPrice(StatesGroup):
    value = State()


def parse_price(text: str) -> int | None:
    try:
        value = Decimal(text.strip().replace(",", ".").replace("€", "").replace("$", ""))
    except InvalidOperation:
        return None
    cents = int((value * 100).to_integral_value())
    return cents if 0 < cents < 100_000_000 else None


def split_items(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


ADMIN_MENU = kb(
    [("➕ Ajouter un produit", "a:add")],
    [("📋 Produits et stock", "a:list")],
    [("🧾 Commandes à traiter", "a:orders")],
    [("📊 Statistiques", "a:stats")],
)
CANCEL = kb([("❌ Annuler", "a:menu")])


@router.message(Command("admin"))
async def admin_cmd(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("🛠 <b>Administration</b>", reply_markup=ADMIN_MENU)


@router.callback_query(F.data == "a:menu")
async def admin_menu(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show(cb, "🛠 <b>Administration</b>", ADMIN_MENU)


@router.callback_query(F.data == "a:stats")
async def stats(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    s = await db.stats()
    text = (
        "📊 <b>Statistiques</b>\n\n"
        f"Clients : {s['users']}\nVentes livrées : {s['sales']}\n"
        f"Chiffre d'affaires : {price(s['revenue_cents'], cfg.fiat)}\n"
        f"Commandes en attente de paiement : {s['pending']}\nPayées non livrées : {s['stuck']}"
    )
    await show(cb, text, kb([("⬅️ Admin", "a:menu")]))


# ------------------------------------------------------------------ add product


@router.callback_query(F.data == "a:add")
async def add_start(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddProduct.name)
    await show(cb, "Nom du produit ?", CANCEL)


@router.message(AddProduct.name, TEXT)
async def add_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip()[:60])
    await state.set_state(AddProduct.description)
    await message.answer("Description ? (envoyez - pour aucune)", reply_markup=CANCEL)


@router.message(AddProduct.description, TEXT)
async def add_description(message: Message, state: FSMContext, cfg: Config) -> None:
    text = message.text.strip()
    await state.update_data(description="" if text == "-" else text[:1500])
    await state.set_state(AddProduct.price)
    await message.answer(f"Prix en {cfg.fiat} ? (exemple : 9.99)", reply_markup=CANCEL)


@router.message(AddProduct.price, TEXT)
async def add_price(message: Message, state: FSMContext) -> None:
    cents = parse_price(message.text)
    if cents is None:
        await message.answer("Prix invalide. Exemple : 9.99", reply_markup=CANCEL)
        return
    await state.update_data(price_cents=cents)
    await message.answer(
        "Type de produit ?\n\n"
        "🔑 <b>Articles uniques</b> : clés, codes, licences. Chaque vente consomme un article du stock.\n"
        "📁 <b>Fichier ou texte</b> : le même contenu pour chaque acheteur, sans limite de stock.",
        reply_markup=kb([("🔑 Articles uniques", "a:kind:stock")], [("📁 Fichier ou texte", "a:kind:file")],
                        [("❌ Annuler", "a:menu")]),
    )


@router.callback_query(AddProduct.price, F.data.in_({"a:kind:stock", "a:kind:file"}))
async def add_kind(cb: CallbackQuery, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    if "price_cents" not in data:
        await cb.answer("Envoyez d'abord le prix.", show_alert=True)
        return
    if cb.data.endswith("stock"):
        pid = await db.add_product(data["name"], data["description"], data["price_cents"], "stock")
        await state.set_state(AddStock.items)
        await state.update_data(product_id=pid)
        await show(
            cb,
            f"✅ Produit « {escape(data['name'])} » créé.\n\nEnvoyez maintenant le stock : un article par ligne, "
            "dans un message ou un fichier .txt.",
            kb([("Plus tard", f"a:p:{pid}")]),
        )
        return
    await state.set_state(AddProduct.payload)
    await show(cb, "Envoyez le fichier (en tant que document) ou le texte à livrer aux acheteurs.", CANCEL)


@router.message(AddProduct.payload, F.document | TEXT)
async def add_payload(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    await state.clear()
    if message.document:
        content, file_id = (message.caption or "").strip() or None, message.document.file_id
    else:
        content, file_id = message.text.strip(), None
    pid = await db.add_product(data["name"], data["description"], data["price_cents"], "file", content, file_id)
    await message.answer(f"✅ Produit « {escape(data['name'])} » créé et en vente.", reply_markup=kb([("Voir", f"a:p:{pid}")]))


# ------------------------------------------------------------------ products


@router.callback_query(F.data == "a:list")
async def product_list(cb: CallbackQuery, state: FSMContext, db: Database, cfg: Config) -> None:
    await state.clear()
    products = await db.list_products(active_only=False)
    rows = []
    for p in products:
        stock = f"stock {p['in_stock']}" if p["kind"] == "stock" else "illimité"
        rows.append([(f"{'🟢' if p['active'] else '⚪️'} {p['name']} — {price(p['price_cents'], cfg.fiat)} ({stock})",
                      f"a:p:{p['id']}")])
    rows.append([("⬅️ Admin", "a:menu")])
    await show(cb, "📋 <b>Produits</b>" if products else "Aucun produit.", kb(*rows))


async def _product_view(db: Database, cfg: Config, pid: int):
    p = await db.get_product(pid)
    if not p:
        return "Produit introuvable.", kb([("⬅️ Produits", "a:list")])
    text = (
        f"<b>{escape(p['name'])}</b>\n{escape(p['description'])}\n\n"
        f"Prix : {price(p['price_cents'], cfg.fiat)}\n"
        f"Type : {'articles uniques' if p['kind'] == 'stock' else 'fichier / texte illimité'}\n"
        + (f"Stock disponible : {p['in_stock']}\n" if p["kind"] == "stock" else "")
        + f"État : {'en vente' if p['active'] else 'masqué'}"
    )
    rows = []
    if p["kind"] == "stock":
        rows.append([("📥 Ajouter du stock", f"a:stock:{pid}")])
    rows += [
        [("💶 Changer le prix", f"a:price:{pid}"), ("👁 Masquer" if p["active"] else "👁 Afficher", f"a:tog:{pid}")],
        [("🗑 Supprimer", f"a:del:{pid}")],
        [("⬅️ Produits", "a:list")],
    ]
    return text, kb(*rows)


@router.callback_query(F.data.regexp(r"^a:p:(\d+)$").as_("m"))
async def product_page(cb: CallbackQuery, m, state: FSMContext, db: Database, cfg: Config) -> None:
    await state.clear()
    await show(cb, *await _product_view(db, cfg, int(m.group(1))))


@router.callback_query(F.data.regexp(r"^a:tog:(\d+)$").as_("m"))
async def toggle(cb: CallbackQuery, m, db: Database, cfg: Config) -> None:
    pid = int(m.group(1))
    p = await db.get_product(pid)
    if p:
        await db.set_active(pid, not p["active"])
    await show(cb, *await _product_view(db, cfg, pid))


@router.callback_query(F.data.regexp(r"^a:del:(\d+)$").as_("m"))
async def delete_ask(cb: CallbackQuery, m) -> None:
    pid = m.group(1)
    await show(cb, "Supprimer ce produit ? Les commandes passées sont conservées.",
               kb([("🗑 Oui, supprimer", f"a:delok:{pid}"), ("Non", f"a:p:{pid}")]))


@router.callback_query(F.data.regexp(r"^a:delok:(\d+)$").as_("m"))
async def delete_do(cb: CallbackQuery, m, db: Database) -> None:
    await db.delete_product(int(m.group(1)))
    await show(cb, "Produit supprimé.", kb([("⬅️ Produits", "a:list")]))


@router.callback_query(F.data.regexp(r"^a:price:(\d+)$").as_("m"))
async def price_ask(cb: CallbackQuery, m, state: FSMContext, cfg: Config) -> None:
    await state.set_state(SetPrice.value)
    await state.update_data(product_id=int(m.group(1)))
    await show(cb, f"Nouveau prix en {cfg.fiat} ?", CANCEL)


@router.message(SetPrice.value, TEXT)
async def price_set(message: Message, state: FSMContext, db: Database, cfg: Config) -> None:
    cents = parse_price(message.text)
    if cents is None:
        await message.answer("Prix invalide. Exemple : 9.99", reply_markup=CANCEL)
        return
    pid = (await state.get_data())["product_id"]
    await state.clear()
    await db.set_price(pid, cents)
    text, markup = await _product_view(db, cfg, pid)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.regexp(r"^a:stock:(\d+)$").as_("m"))
async def stock_ask(cb: CallbackQuery, m, state: FSMContext) -> None:
    await state.set_state(AddStock.items)
    await state.update_data(product_id=int(m.group(1)))
    await show(cb, "Envoyez le stock : un article par ligne, dans un message ou un fichier .txt.", CANCEL)


@router.message(AddStock.items, F.document | TEXT)
async def stock_add(message: Message, state: FSMContext, bot: Bot, db: Database, cfg: Config) -> None:
    if message.document:
        if (message.document.file_size or 0) > MAX_STOCK_FILE:
            await message.answer("Fichier trop volumineux (2 Mo maximum).", reply_markup=CANCEL)
            return
        buffer = io.BytesIO()
        await bot.download(message.document, destination=buffer)
        text = buffer.getvalue().decode("utf-8", errors="replace")
    else:
        text = message.text
    items = split_items(text)
    if not items:
        await message.answer("Aucun article trouvé. Un article par ligne.", reply_markup=CANCEL)
        return
    pid = (await state.get_data())["product_id"]
    await state.clear()
    await db.add_stock(pid, items)
    view, markup = await _product_view(db, cfg, pid)
    await message.answer(f"✅ {len(items)} article(s) ajouté(s).\n\n{view}", reply_markup=markup)


# ------------------------------------------------------------------ orders


@router.callback_query(F.data == "a:orders")
async def orders(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    todo = await db.orders_by_status("pending", "paid", "paid_no_stock")
    if not todo:
        await show(cb, "Aucune commande à traiter.", kb([("⬅️ Admin", "a:menu")]))
        return
    rows = [[(f"#{o['id']} {o['product_name']} ×{o['qty']} — {o['coin']} — {STATUS_LABEL[o['status']]}",
              f"a:o:{o['id']}")] for o in todo[-40:]]
    rows.append([("⬅️ Admin", "a:menu")])
    await show(cb, "🧾 <b>Commandes à traiter</b>", kb(*rows))


@router.callback_query(F.data.regexp(r"^a:o:(\d+)$").as_("m"))
async def order_page(cb: CallbackQuery, m, db: Database) -> None:
    o = await db.get_order(int(m.group(1)))
    if not o:
        await cb.answer("Commande introuvable.", show_alert=True)
        return
    text = (
        f"🧾 <b>Commande #{o['id']}</b>\n{escape(o['product_name'])} × {o['qty']} — {price(o['price_cents'], o['fiat'])}\n"
        f"Paiement : {escape(o['coin'])}\nClient : <code>{o['user_id']}</code>\n"
        f"Statut : {STATUS_LABEL.get(o['status'], o['status'])}"
        + (f"\nTX déclarée : <code>{escape(o['note'])}</code>" if o["note"] else "")
        + (f"\nTX : <code>{escape(o['txid'])}</code>" if o["txid"] else "")
    )
    rows = []
    if o["status"] in ("pending", "expired"):
        rows.append([("✅ Valider et livrer", f"a:ok:{o['id']}"), ("❌ Annuler", f"a:no:{o['id']}")])
    elif o["status"] in ("paid", "paid_no_stock"):
        rows.append([("🔁 Réessayer la livraison", f"a:retry:{o['id']}")])
    rows.append([("⬅️ Commandes", "a:orders")])
    await show(cb, text, kb(*rows))


@router.callback_query(F.data.regexp(r"^a:ok:(\d+)$").as_("m"))
async def confirm(cb: CallbackQuery, m, bot: Bot, db: Database, cfg: Config) -> None:
    order = await db.get_order(int(m.group(1)))
    status = await settle(bot, db, cfg, order, None) if order else None
    if status is None:
        await cb.answer("Cette commande n'est plus en attente.", show_alert=True)
        return
    await cb.answer({"delivered": "Validée et livrée.", "paid_no_stock": "Validée, mais plus de stock."}.get(
        status, "Validée, livraison en échec (nouvel essai automatique)."), show_alert=True)


@router.callback_query(F.data.regexp(r"^a:no:(\d+)$").as_("m"))
async def refuse(cb: CallbackQuery, m, bot: Bot, db: Database) -> None:
    order = await db.get_order(int(m.group(1)))
    if not order or not await db.cancel_order(order["id"]):
        await cb.answer("Cette commande n'est plus en attente.", show_alert=True)
        return
    try:
        await bot.send_message(order["user_id"], f"❌ La commande #{order['id']} a été annulée par un administrateur.")
    except Exception:
        pass
    await cb.answer("Commande annulée, stock libéré.", show_alert=True)


@router.callback_query(F.data.regexp(r"^a:retry:(\d+)$").as_("m"))
async def retry(cb: CallbackQuery, m, bot: Bot, db: Database, cfg: Config) -> None:
    order = await db.get_order(int(m.group(1)))
    if not order or order["status"] not in ("paid", "paid_no_stock"):
        await cb.answer("Rien à livrer pour cette commande.", show_alert=True)
        return
    if order["status"] == "paid_no_stock" and not await db.retry_stock(order["id"]):
        await cb.answer("Toujours pas assez de stock : réapprovisionnez d'abord.", show_alert=True)
        return
    ok = await deliver(bot, db, cfg, await db.get_order(order["id"]))
    if ok:
        await notify_admins(bot, cfg, f"📦 Commande #{order['id']} livrée.")
    await cb.answer("Livrée." if ok else "Livraison en échec (le client a peut-être bloqué le bot).", show_alert=True)
