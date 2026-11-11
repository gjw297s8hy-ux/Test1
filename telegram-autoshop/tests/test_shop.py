"""Runs without Telegram or network: a fake Bot session records what the bot would send.

    pip install pytest && pytest
"""
import asyncio
import datetime
import time
from decimal import Decimal

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import GetFile, SendDocument, SendMessage, EditMessageText
from aiogram.types import Chat, Message, Update, User

from bot import chains, payments
from bot.chains import COINS, Incoming, format_amount, match_payment, to_atomic
from bot.config import Config
from bot.db import Database
from bot.handlers import admin, user

ADMIN, BUYER = 1, 42
BTC_ADDR = "bc1qshopaddress"


class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls = []

    async def close(self):
        pass

    async def stream_content(self, *a, **k):
        yield b""

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if isinstance(method, (SendMessage, SendDocument, EditMessageText)):
            chat_id = getattr(method, "chat_id", None) or 0
            return Message(message_id=len(self.calls), date=datetime.datetime.now(), chat=Chat(id=chat_id, type="private"))
        return True

    def texts(self, chat_id=None):
        return [m.text for m in self.calls if isinstance(m, (SendMessage, EditMessageText))
                and (chat_id is None or m.chat_id == chat_id)]

    def last_markup(self):
        for m in reversed(self.calls):
            if getattr(m, "reply_markup", None):
                return [b for row in m.reply_markup.inline_keyboard for b in row]
        return []


class Shop:
    """A dispatcher wired like bot/__main__.py, driven by synthetic updates."""

    def __init__(self, tmp_path, **cfg):
        self.cfg = Config(token="1:x", admin_ids=frozenset({ADMIN}), wallets={"BTC": BTC_ADDR},
                          extra_wallets={"XMR": "4xmr"}, **cfg)
        self.db = Database(str(tmp_path / "shop.db"))
        self.session = FakeSession()
        self.bot = Bot("1:x", session=self.session, default=DefaultBotProperties(parse_mode="HTML"))
        self.dp = Dispatcher(storage=MemoryStorage())
        # Routers are module-level singletons; detach them from any previous test's dispatcher.
        for r in (admin.router, user.router):
            r._parent_router = None
        self.dp.include_router(admin.router)
        self.dp.include_router(user.router)
        self.dp["db"], self.dp["cfg"], self.dp["http"] = self.db, self.cfg, None
        self.n = 0

    live = []

    async def start(self):
        await self.db.connect()
        Shop.live.append(self)
        return self

    def _user(self, uid):
        return {"id": uid, "is_bot": False, "first_name": "u", "username": f"user{uid}"}

    async def say(self, uid, text):
        self.n += 1
        upd = {"update_id": self.n, "message": {"message_id": self.n, "date": int(time.time()),
               "chat": {"id": uid, "type": "private"}, "from": self._user(uid), "text": text}}
        if text.startswith("/"):
            upd["message"]["entities"] = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]
        await self.dp.feed_update(self.bot, Update.model_validate(upd))

    async def tap(self, uid, data):
        self.n += 1
        upd = {"update_id": self.n, "callback_query": {"id": str(self.n), "from": self._user(uid),
               "chat_instance": "c", "data": data, "message": {"message_id": 1, "date": int(time.time()),
               "chat": {"id": uid, "type": "private"}, "text": "menu"}}}
        await self.dp.feed_update(self.bot, Update.model_validate(upd))

    async def add_keys(self, name="Cle", price="10", keys=("K1", "K2", "K3")):
        await self.say(ADMIN, "/admin")
        await self.tap(ADMIN, "a:add")
        await self.say(ADMIN, name)
        await self.say(ADMIN, "-")
        await self.say(ADMIN, price)
        await self.tap(ADMIN, "a:kind:stock")
        await self.say(ADMIN, "\n".join(keys))
        return (await self.db.list_products())[-1]["id"]


def run(coro):
    async def wrapper():
        try:
            await coro
        finally:  # an open aiosqlite connection keeps its worker thread, and the process, alive
            while Shop.live:
                await Shop.live.pop().db.close()
    asyncio.run(wrapper())


def fake_rate(monkeypatch, value="50000"):
    async def rate(session, coin, fiat):
        return Decimal(value)
    monkeypatch.setattr(user, "get_rate", rate)


def fake_chain(monkeypatch, txs):
    async def incoming(session, coin, address, key=""):
        return list(txs)
    monkeypatch.setattr(payments, "fetch_incoming", incoming)


# ------------------------------------------------------------------ pure logic


def test_amount_conversion_rounds_up_and_formats_exactly():
    btc = COINS["BTC"]
    assert to_atomic(1000, Decimal("50000"), btc) == 20000          # 10.00 at 50k = 0.0002 BTC
    assert to_atomic(1000, Decimal("65908"), btc) == 15173          # 15172.6 rounded up
    assert format_amount(20137, btc) == "0.00020137"
    assert format_amount(100000000, btc) == "1"
    assert format_amount(1500000, COINS["USDT_TRC20"]) == "1.5"


def test_match_payment_rules():
    order = {"amount_atomic": 20137, "created_at": 1000}
    exact = Incoming("tx1", 20137, 2, 1500)
    assert match_payment(order, [exact], set(), 1) == ("paid", exact)
    assert match_payment(order, [exact], {"tx1"}, 1) == ("none", None)                      # already used
    assert match_payment(order, [Incoming("t", 20136, 2, 1500)], set(), 1)[0] == "none"     # wrong amount
    assert match_payment(order, [Incoming("t", 20137, 2, 500)], set(), 1)[0] == "none"      # older than order
    assert match_payment(order, [Incoming("t", 20137, 0, None)], set(), 1)[0] == "seen"     # unconfirmed
    assert match_payment(order, [Incoming("t", 20137, 0, None)], set(), 0)[0] == "paid"     # 0-conf allowed


# ------------------------------------------------------------------ flows


def test_admin_menu_is_hidden_from_customers(tmp_path):
    async def go():
        shop = await Shop(tmp_path).start()
        await shop.say(BUYER, "/admin")
        await shop.tap(BUYER, "a:stats")
        assert shop.session.texts(BUYER) == []
        await shop.say(ADMIN, "/admin")
        assert "Administration" in shop.session.texts(ADMIN)[-1]
    run(go())


def test_buy_keys_with_btc_end_to_end(tmp_path, monkeypatch):
    async def go():
        shop = await Shop(tmp_path).start()
        fake_rate(monkeypatch)
        pid = await shop.add_keys()
        assert (await shop.db.get_product(pid))["in_stock"] == 3

        await shop.say(BUYER, "/start")
        await shop.tap(BUYER, "cat")
        assert "Cle — 10.00 EUR (3 en stock)" in [b.text for b in shop.session.last_markup()]
        await shop.tap(BUYER, f"p:{pid}:2")
        await shop.tap(BUYER, f"buy:{pid}:2")
        assert [b.text for b in shop.session.last_markup()][:2] == ["Bitcoin (BTC)", "XMR (validation manuelle)"]
        await shop.tap(BUYER, f"pay:{pid}:2:BTC")

        order = (await shop.db.user_orders(BUYER))[0]
        assert order["status"] == "pending" and order["qty"] == 2 and order["price_cents"] == 2000
        assert 40000 < order["amount_atomic"] <= 40000 + COINS["BTC"].jitter       # 20 EUR + unique jitter
        page = shop.session.texts(BUYER)[-1]
        assert format_amount(order["amount_atomic"], COINS["BTC"]) in page and BTC_ADDR in page
        assert (await shop.db.get_product(pid))["in_stock"] == 1                  # 2 reserved

        # Nothing on chain yet, then an unconfirmed tx, then a confirmed one.
        fake_chain(monkeypatch, [])
        assert await payments.check_orders(shop.bot, shop.db, shop.cfg, None, [order]) == {}
        fake_chain(monkeypatch, [Incoming("txA", order["amount_atomic"], 0, None)])
        assert await payments.check_orders(shop.bot, shop.db, shop.cfg, None, [order]) == {order["id"]: "seen"}
        assert "Paiement détecté" in shop.session.texts(BUYER)[-1]
        await shop.tap(BUYER, f"cxl:{order['id']}")                                # cannot cancel mid-confirmation
        assert (await shop.db.get_order(order["id"]))["status"] == "pending"

        fake_chain(monkeypatch, [Incoming("txA", order["amount_atomic"], 1, int(time.time()))])
        watched = await shop.db.watch_orders(shop.cfg.late_grace)
        assert await payments.check_orders(shop.bot, shop.db, shop.cfg, None, watched) == {order["id"]: "delivered"}
        delivered = shop.session.texts(BUYER)[-1]
        assert "<code>K1</code>" in delivered and "<code>K2</code>" in delivered and "K3" not in delivered
        assert "Vente" in shop.session.texts(ADMIN)[-1]
        final = await shop.db.get_order(order["id"])
        assert final["status"] == "delivered" and final["txid"] == "txA"

        # The same transaction can never pay a second order, even one with the same amount.
        await shop.tap(BUYER, f"pay:{pid}:1:BTC")
        second = (await shop.db.user_orders(BUYER))[0]
        await shop.db._run("UPDATE orders SET amount_atomic=? WHERE id=?", (order["amount_atomic"], second["id"]))
        watched = await shop.db.watch_orders(shop.cfg.late_grace)
        assert await payments.check_orders(shop.bot, shop.db, shop.cfg, None, watched) == {}
        assert (await shop.db.get_order(second["id"]))["status"] == "pending"
    run(go())


def test_amounts_are_unique_and_stock_cannot_be_oversold(tmp_path, monkeypatch):
    async def go():
        shop = await Shop(tmp_path, max_pending=50).start()
        fake_rate(monkeypatch)
        pid = await shop.add_keys(keys=[f"K{i}" for i in range(30)])
        for _ in range(30):
            await shop.tap(BUYER, f"pay:{pid}:1:BTC")
        orders = await shop.db.user_orders(BUYER, limit=100)
        assert len(orders) == 30 and len({o["amount_atomic"] for o in orders}) == 30
        await shop.tap(BUYER, f"pay:{pid}:1:BTC")                                  # stock exhausted
        assert len(await shop.db.user_orders(BUYER, limit=100)) == 30
    run(go())


def test_pending_limit_cancel_and_expiry_release_stock(tmp_path, monkeypatch):
    async def go():
        shop = await Shop(tmp_path, max_pending=2).start()
        fake_rate(monkeypatch)
        pid = await shop.add_keys()
        for _ in range(3):
            await shop.tap(BUYER, f"pay:{pid}:1:BTC")
        orders = await shop.db.user_orders(BUYER)
        assert len(orders) == 2                                                    # third refused
        await shop.tap(BUYER, f"cxl:{orders[0]['id']}")
        assert (await shop.db.get_order(orders[0]["id"]))["status"] == "cancelled"
        assert (await shop.db.get_product(pid))["in_stock"] == 2

        await shop.db._run("UPDATE orders SET expires_at=? WHERE id=?", (int(time.time()) - 1, orders[1]["id"]))
        assert [o["id"] for o in await shop.db.expire_due()] == [orders[1]["id"]]
        assert (await shop.db.get_product(pid))["in_stock"] == 3
        # Somebody else's order is not reachable.
        await shop.tap(999, f"cxl:{orders[1]['id']}")
        await shop.tap(999, f"o:{orders[1]['id']}")
        assert shop.session.texts(999) == []
    run(go())


def test_late_payment_on_expired_order(tmp_path, monkeypatch):
    async def go():
        shop = await Shop(tmp_path).start()
        fake_rate(monkeypatch)
        pid = await shop.add_keys(keys=["ONLY"])
        await shop.tap(BUYER, f"pay:{pid}:1:BTC")
        order = (await shop.db.user_orders(BUYER))[0]
        await shop.db._run("UPDATE orders SET expires_at=? WHERE id=?", (int(time.time()) - 1, order["id"]))
        await shop.db.expire_due()
        fake_chain(monkeypatch, [Incoming("late", order["amount_atomic"], 3, int(time.time()))])

        # Stock still free: the late payer is delivered.
        watched = await shop.db.watch_orders(shop.cfg.late_grace)
        assert await payments.check_orders(shop.bot, shop.db, shop.cfg, None, watched) == {order["id"]: "delivered"}
        assert "ONLY" in shop.session.texts(BUYER)[-1]
    run(go())


def test_late_payment_after_stock_sold_alerts_admin_then_retry(tmp_path, monkeypatch):
    async def go():
        shop = await Shop(tmp_path).start()
        fake_rate(monkeypatch)
        pid = await shop.add_keys(keys=["ONLY"])
        await shop.tap(BUYER, f"pay:{pid}:1:BTC")
        order = (await shop.db.user_orders(BUYER))[0]
        await shop.db._run("UPDATE orders SET expires_at=? WHERE id=?", (int(time.time()) - 1, order["id"]))
        await shop.db.expire_due()
        await shop.db._run("UPDATE stock SET sold=1, order_id=999")               # sold to someone else meanwhile

        fake_chain(monkeypatch, [Incoming("late", order["amount_atomic"], 3, int(time.time()))])
        watched = await shop.db.watch_orders(shop.cfg.late_grace)
        assert await payments.check_orders(shop.bot, shop.db, shop.cfg, None, watched) == {order["id"]: "paid_no_stock"}
        assert "plus de stock" in shop.session.texts(ADMIN)[-1]
        assert "ONLY" not in "".join(shop.session.texts(BUYER))

        await shop.tap(ADMIN, f"a:stock:{pid}")
        await shop.say(ADMIN, "FRESH")
        await shop.tap(ADMIN, f"a:retry:{order['id']}")
        assert "<code>FRESH</code>" in shop.session.texts(BUYER)[-1]
        assert (await shop.db.get_order(order["id"]))["status"] == "delivered"
    run(go())


def test_manual_coin_needs_admin_validation(tmp_path):
    async def go():
        shop = await Shop(tmp_path).start()
        pid = await shop.add_keys()
        await shop.tap(BUYER, f"pay:{pid}:1:XMR")
        order = (await shop.db.user_orders(BUYER))[0]
        assert order["amount_atomic"] == 0 and "4xmr" in shop.session.texts(BUYER)[-1]
        await shop.tap(BUYER, f"paid:{order['id']}")
        await shop.say(BUYER, "deadbeef")
        assert "deadbeef" in shop.session.texts(ADMIN)[-1]
        await shop.tap(BUYER, f"a:ok:{order['id']}")                               # a customer cannot self-validate
        assert (await shop.db.get_order(order["id"]))["status"] == "pending"
        await shop.tap(ADMIN, f"a:ok:{order['id']}")
        assert (await shop.db.get_order(order["id"]))["status"] == "delivered"
        assert "<code>K1</code>" in shop.session.texts(BUYER)[-1]
    run(go())


def test_file_product_and_admin_edits(tmp_path, monkeypatch):
    async def go():
        shop = await Shop(tmp_path).start()
        fake_rate(monkeypatch)
        await shop.say(ADMIN, "/admin")
        await shop.tap(ADMIN, "a:add")
        await shop.say(ADMIN, "Guide <PDF>")
        await shop.say(ADMIN, "Un guide")
        await shop.say(ADMIN, "abc")                                               # invalid price, asked again
        await shop.say(ADMIN, "4,50")
        await shop.tap(ADMIN, "a:kind:file")
        await shop.say(ADMIN, "https://exemple.fr/guide & code <42>")
        product = (await shop.db.list_products())[0]
        assert product["kind"] == "file" and product["price_cents"] == 450

        pid = product["id"]
        await shop.tap(ADMIN, f"a:price:{pid}")
        await shop.say(ADMIN, "5")
        await shop.tap(ADMIN, f"a:tog:{pid}")
        assert await shop.db.list_products() == []                                 # hidden from the catalogue
        await shop.tap(ADMIN, f"a:tog:{pid}")
        await shop.tap(ADMIN, "a:list")
        await shop.tap(ADMIN, "a:stats")

        for _ in range(2):                                                         # unlimited: sells repeatedly
            await shop.tap(BUYER, f"pay:{pid}:1:BTC")
            order = (await shop.db.user_orders(BUYER))[0]
            assert order["price_cents"] == 500
            fake_chain(monkeypatch, [Incoming(f"tx{order['id']}", order["amount_atomic"], 1, int(time.time()))])
            await payments.check_orders(shop.bot, shop.db, shop.cfg, None, [order])
            assert "guide &amp; code &lt;42&gt;" in shop.session.texts(BUYER)[-1]  # HTML-escaped
        assert (await shop.db.stats())["sales"] == 2

        await shop.tap(ADMIN, f"a:delok:{pid}")
        assert await shop.db.get_product(pid) is None
    run(go())


def test_miniapp_button_and_order(tmp_path, monkeypatch):
    import base64
    import json
    from urllib.parse import parse_qs, urlparse

    from bot.miniapp import MAX_URL, miniapp_url

    async def go():
        shop = await Shop(tmp_path, miniapp_url="https://example.org/shop/").start()
        fake_rate(monkeypatch)
        pid = await shop.add_keys(name="Clé é", keys=("K1", "K2"))

        # /start sends a reply keyboard whose button opens the page with the catalogue in the link.
        await shop.say(BUYER, "/start")
        keyboards = [m.reply_markup for m in shop.session.calls if getattr(m, "chat_id", None) == BUYER
                     and getattr(getattr(m, "reply_markup", None), "keyboard", None)]
        url = keyboards[-1].keyboard[0][0].web_app.url
        raw = parse_qs(urlparse(url).query)["d"][0]
        data = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        assert data["p"] == [[pid, "Clé é", "", 1000, 2]] and data["c"] == [["BTC", "Bitcoin (BTC)"], ["XMR", "XMR"]]

        # The page answers with sendData; the bot creates the order and shows how to pay.
        async def send(payload):
            shop.n += 1
            await shop.dp.feed_update(shop.bot, Update.model_validate({"update_id": shop.n, "message": {
                "message_id": shop.n, "date": int(time.time()), "chat": {"id": BUYER, "type": "private"},
                "from": shop._user(BUYER), "web_app_data": {"data": payload, "button_text": "x"}}}))

        await send(json.dumps({"p": pid, "q": 2, "c": "BTC"}))
        order = (await shop.db.user_orders(BUYER))[0]
        assert order["qty"] == 2 and order["status"] == "pending" and BTC_ADDR in shop.session.texts(BUYER)[-1]

        await send(json.dumps({"p": pid, "q": 1, "c": "BTC"}))                      # nothing left
        assert "Stock insuffisant" in shop.session.texts(BUYER)[-1]
        await send("not json")
        assert "illisible" in shop.session.texts(BUYER)[-1]
        await send(json.dumps({"p": pid, "q": 1, "c": "DOGE"}))                     # coin the shop does not take
        assert "indisponible" in shop.session.texts(BUYER)[-1]
        assert len(await shop.db.user_orders(BUYER)) == 1

        # A large catalogue still yields a link Telegram accepts.
        many = [{"id": i, "name": f"Produit numéro {i}", "description": "d" * 200, "price_cents": 999,
                 "in_stock": 5, "kind": "stock"} for i in range(200)]
        assert len(miniapp_url(shop.cfg, many)) <= MAX_URL
    run(go())
