"""SQLite storage: products, stock, orders, payments."""
from __future__ import annotations

import asyncio
import random
import sqlite3
import time
from contextlib import asynccontextmanager

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    username TEXT,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS products(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    price_cents INTEGER NOT NULL,
    -- 'stock': each sale consumes unique items (keys, codes). 'file': same content for every buyer.
    kind TEXT NOT NULL DEFAULT 'stock',
    content TEXT,
    file_id TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    deleted INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS stock(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    order_id INTEGER,              -- reserved for / sold to this order
    sold INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS stock_free ON stock(product_id, sold, order_id);
CREATE TABLE IF NOT EXISTS orders(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    qty INTEGER NOT NULL,
    price_cents INTEGER NOT NULL,  -- total, in fiat cents
    fiat TEXT NOT NULL,
    coin TEXT NOT NULL,
    address TEXT NOT NULL,
    amount_atomic INTEGER NOT NULL, -- 0 for manually confirmed coins
    status TEXT NOT NULL,           -- pending, paid, delivered, expired, cancelled, paid_no_stock
    txid TEXT,
    seen_txid TEXT,
    note TEXT,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    paid_at INTEGER
);
CREATE INDEX IF NOT EXISTS orders_status ON orders(status);
CREATE TABLE IF NOT EXISTS payments(
    txid TEXT PRIMARY KEY,          -- a transaction can pay one order only
    order_id INTEGER NOT NULL
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        self._db: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        self._db = await aiosqlite.connect(self.path, isolation_level=None)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA)

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    @asynccontextmanager
    async def _tx(self):
        """One connection is shared, so multi-statement work must not interleave."""
        async with self._lock:
            await self._db.execute("BEGIN IMMEDIATE")
            try:
                yield self._db
            except BaseException:
                await self._db.execute("ROLLBACK")
                raise
            else:
                await self._db.execute("COMMIT")

    async def _all(self, sql: str, args: tuple = ()) -> list[dict]:
        async with self._lock:
            cur = await self._db.execute(sql, args)
            return [dict(r) for r in await cur.fetchall()]

    async def _one(self, sql: str, args: tuple = ()) -> dict | None:
        rows = await self._all(sql, args)
        return rows[0] if rows else None

    async def _run(self, sql: str, args: tuple = ()) -> int:
        async with self._lock:
            cur = await self._db.execute(sql, args)
            return cur.lastrowid if sql.lstrip().upper().startswith("INSERT") else cur.rowcount

    # ------------------------------------------------------------------ users

    async def upsert_user(self, user_id: int, username: str | None) -> None:
        await self._run(
            "INSERT INTO users(id, username, created_at) VALUES(?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET username=excluded.username",
            (user_id, username, int(time.time())),
        )

    # ------------------------------------------------------------------ products

    async def add_product(
        self, name: str, description: str, price_cents: int, kind: str,
        content: str | None = None, file_id: str | None = None,
    ) -> int:
        return await self._run(
            "INSERT INTO products(name, description, price_cents, kind, content, file_id) VALUES(?,?,?,?,?,?)",
            (name, description, price_cents, kind, content, file_id),
        )

    async def get_product(self, product_id: int) -> dict | None:
        return await self._one(
            "SELECT p.*, (SELECT COUNT(*) FROM stock s WHERE s.product_id=p.id AND s.sold=0 "
            "AND s.order_id IS NULL) AS in_stock FROM products p WHERE p.id=? AND p.deleted=0",
            (product_id,),
        )

    async def list_products(self, active_only: bool = True) -> list[dict]:
        where = "p.deleted=0" + (" AND p.active=1" if active_only else "")
        return await self._all(
            "SELECT p.*, (SELECT COUNT(*) FROM stock s WHERE s.product_id=p.id AND s.sold=0 "
            f"AND s.order_id IS NULL) AS in_stock FROM products p WHERE {where} ORDER BY p.id"
        )

    async def set_active(self, product_id: int, active: bool) -> None:
        await self._run("UPDATE products SET active=? WHERE id=?", (int(active), product_id))

    async def set_price(self, product_id: int, price_cents: int) -> None:
        await self._run("UPDATE products SET price_cents=? WHERE id=?", (price_cents, product_id))

    async def delete_product(self, product_id: int) -> None:
        # Soft delete: past orders still point at the product.
        await self._run("UPDATE products SET deleted=1, active=0 WHERE id=?", (product_id,))

    async def add_stock(self, product_id: int, items: list[str]) -> int:
        async with self._tx() as db:
            await db.executemany(
                "INSERT INTO stock(product_id, content) VALUES(?,?)", [(product_id, i) for i in items]
            )
        return len(items)

    # ------------------------------------------------------------------ orders

    @staticmethod
    async def _reserve(db, order_id: int, product_id: int, qty: int) -> bool:
        cur = await db.execute(
            "SELECT id FROM stock WHERE product_id=? AND sold=0 AND order_id IS NULL ORDER BY id LIMIT ?",
            (product_id, qty),
        )
        ids = [r[0] for r in await cur.fetchall()]
        if len(ids) < qty:
            return False
        await db.executemany("UPDATE stock SET order_id=? WHERE id=?", [(order_id, i) for i in ids])
        return True

    async def create_order(
        self, *, user_id: int, product: dict, qty: int, fiat: str, coin: str, address: str,
        base_amount: int, jitter: int, ttl: int, late_grace: int,
    ) -> dict | None:
        """Create a pending order and reserve its stock. None if stock ran out.

        For on-chain coins the amount is nudged by a few atomic units until no other open
        order on the same coin shares it - that amount is how the payment is recognised.
        """
        now = int(time.time())
        async with self._tx() as db:
            amount = base_amount
            if base_amount > 0:
                for attempt in range(200):
                    amount = base_amount + (random.randint(1, jitter) if attempt < 150 else jitter + attempt)
                    cur = await db.execute(
                        "SELECT 1 FROM orders WHERE coin=? AND amount_atomic=? AND "
                        "(status='pending' OR (status='expired' AND expires_at>?))",
                        (coin, amount, now - late_grace),
                    )
                    if not await cur.fetchone():
                        break
                else:
                    return None
            cur = await db.execute(
                "INSERT INTO orders(user_id, product_id, qty, price_cents, fiat, coin, address, "
                "amount_atomic, status, created_at, expires_at) VALUES(?,?,?,?,?,?,?,?,'pending',?,?)",
                (user_id, product["id"], qty, product["price_cents"] * qty, fiat, coin, address,
                 amount, now, now + ttl),
            )
            order_id = cur.lastrowid
            if product["kind"] == "stock" and not await self._reserve(db, order_id, product["id"], qty):
                await db.execute("DELETE FROM orders WHERE id=?", (order_id,))
                return None
        return await self.get_order(order_id)

    async def get_order(self, order_id: int) -> dict | None:
        return await self._one(
            "SELECT o.*, p.name AS product_name, p.kind AS product_kind FROM orders o "
            "JOIN products p ON p.id=o.product_id WHERE o.id=?",
            (order_id,),
        )

    async def user_orders(self, user_id: int, limit: int = 10) -> list[dict]:
        return await self._all(
            "SELECT o.*, p.name AS product_name, p.kind AS product_kind FROM orders o "
            "JOIN products p ON p.id=o.product_id WHERE o.user_id=? ORDER BY o.id DESC LIMIT ?",
            (user_id, limit),
        )

    async def count_pending(self, user_id: int) -> int:
        row = await self._one("SELECT COUNT(*) AS n FROM orders WHERE user_id=? AND status='pending'", (user_id,))
        return row["n"]

    async def watch_orders(self, late_grace: int) -> list[dict]:
        """Orders the payment watcher must look at: pending, plus recently expired ones (late payers)."""
        return await self._all(
            "SELECT o.*, p.name AS product_name, p.kind AS product_kind FROM orders o "
            "JOIN products p ON p.id=o.product_id WHERE o.amount_atomic>0 AND "
            "(o.status='pending' OR (o.status='expired' AND o.expires_at>?))",
            (int(time.time()) - late_grace,),
        )

    async def orders_by_status(self, *statuses: str) -> list[dict]:
        marks = ",".join("?" * len(statuses))
        return await self._all(
            "SELECT o.*, p.name AS product_name, p.kind AS product_kind FROM orders o "
            f"JOIN products p ON p.id=o.product_id WHERE o.status IN ({marks}) ORDER BY o.id",
            statuses,
        )

    async def used_txids(self) -> set[str]:
        return {r["txid"] for r in await self._all("SELECT txid FROM payments")}

    async def set_seen(self, order_id: int, txid: str) -> None:
        await self._run("UPDATE orders SET seen_txid=? WHERE id=?", (txid, order_id))

    async def set_note(self, order_id: int, note: str) -> None:
        await self._run("UPDATE orders SET note=? WHERE id=?", (note, order_id))

    async def _close(self, order_id: int, status: str, only_from: tuple[str, ...]) -> bool:
        async with self._tx() as db:
            marks = ",".join("?" * len(only_from))
            cur = await db.execute(
                f"UPDATE orders SET status=? WHERE id=? AND status IN ({marks})", (status, order_id, *only_from)
            )
            if cur.rowcount == 0:
                return False
            await db.execute("UPDATE stock SET order_id=NULL WHERE order_id=? AND sold=0", (order_id,))
        return True

    async def cancel_order(self, order_id: int) -> bool:
        """Cancel and release the reserved stock. Only unpaid orders can be cancelled."""
        return await self._close(order_id, "cancelled", ("pending", "expired"))

    async def expire_due(self) -> list[dict]:
        """Expire overdue pending orders, releasing their stock. Returns the orders expired."""
        due = await self._all(
            "SELECT id, user_id FROM orders WHERE status='pending' AND expires_at<=?", (int(time.time()),)
        )
        return [o for o in due if await self._close(o["id"], "expired", ("pending",))]

    async def mark_paid(self, order_id: int, txid: str | None) -> str | None:
        """Record a payment. Returns the new status, or None if nothing changed.

        'paid' means the stock is reserved and delivery can go ahead. 'paid_no_stock' means the
        customer paid an expired order after its stock had been sold to someone else.
        """
        async with self._tx() as db:
            cur = await db.execute(
                "SELECT o.status, o.qty, o.product_id, p.kind FROM orders o "
                "JOIN products p ON p.id=o.product_id WHERE o.id=?",
                (order_id,),
            )
            row = await cur.fetchone()
            if not row or row["status"] not in ("pending", "expired"):
                return None
            if txid:
                try:
                    await db.execute("INSERT INTO payments(txid, order_id) VALUES(?,?)", (txid, order_id))
                except sqlite3.IntegrityError:
                    return None  # this transaction already paid another order
            status = "paid"
            if row["status"] == "expired" and row["kind"] == "stock":
                if not await self._reserve(db, order_id, row["product_id"], row["qty"]):
                    status = "paid_no_stock"
            await db.execute(
                "UPDATE orders SET status=?, txid=COALESCE(?, txid), paid_at=? WHERE id=?",
                (status, txid, int(time.time()), order_id),
            )
        return status

    async def retry_stock(self, order_id: int) -> bool:
        """After restocking, try again to reserve items for a paid_no_stock order."""
        async with self._tx() as db:
            cur = await db.execute("SELECT status, qty, product_id FROM orders WHERE id=?", (order_id,))
            row = await cur.fetchone()
            if not row or row["status"] != "paid_no_stock":
                return False
            if not await self._reserve(db, order_id, row["product_id"], row["qty"]):
                return False
            await db.execute("UPDATE orders SET status='paid' WHERE id=?", (order_id,))
        return True

    async def order_items(self, order_id: int) -> list[str]:
        rows = await self._all("SELECT content FROM stock WHERE order_id=? ORDER BY id", (order_id,))
        return [r["content"] for r in rows]

    async def mark_delivered(self, order_id: int) -> bool:
        async with self._tx() as db:
            cur = await db.execute("UPDATE orders SET status='delivered' WHERE id=? AND status='paid'", (order_id,))
            if cur.rowcount == 0:
                return False
            await db.execute("UPDATE stock SET sold=1 WHERE order_id=?", (order_id,))
        return True

    async def stats(self) -> dict:
        row = await self._one(
            "SELECT (SELECT COUNT(*) FROM users) AS users, "
            "(SELECT COUNT(*) FROM orders WHERE status='delivered') AS sales, "
            "(SELECT COALESCE(SUM(price_cents),0) FROM orders WHERE status='delivered') AS revenue_cents, "
            "(SELECT COUNT(*) FROM orders WHERE status='pending') AS pending, "
            "(SELECT COUNT(*) FROM orders WHERE status IN ('paid','paid_no_stock')) AS stuck"
        )
        return row
