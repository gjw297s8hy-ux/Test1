"""Link to the Mini App storefront.

The Mini App is one static HTML page with no server behind it. The bot hands it the catalogue
inside the link itself, and the page hands the customer's choice back with Telegram's
`sendData`, which only works for a page opened from a reply-keyboard button.
"""
from __future__ import annotations

import base64
import json

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from .chains import COINS
from .config import Config

BUTTON_TEXT = "🌴 Ouvrir la boutique"
MAX_URL = 2000  # stay well inside what Telegram clients accept for a button link


def _encode(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def miniapp_url(cfg: Config, products: list[dict]) -> str:
    coins = [[c, COINS[c].label] for c in cfg.wallets if c in COINS]
    coins += [[c, c] for c in cfg.extra_wallets]
    rows = [
        [p["id"], p["name"], p["description"][:140], p["price_cents"], p["in_stock"] if p["kind"] == "stock" else -1]
        for p in products
    ]
    sep = "&" if "?" in cfg.miniapp_url else "?"

    def build() -> str:
        return f"{cfg.miniapp_url}{sep}d=" + _encode({"n": cfg.shop_name, "f": cfg.fiat, "c": coins, "p": rows})

    url = build()
    if len(url) > MAX_URL:  # big catalogue: drop descriptions first, then the last products
        for row in rows:
            row[2] = ""
        url = build()
    while len(url) > MAX_URL and rows:
        rows.pop()
        url = build()
    return url


def miniapp_keyboard(cfg: Config, products: list[dict]) -> ReplyKeyboardMarkup:
    button = KeyboardButton(text=BUTTON_TEXT, web_app=WebAppInfo(url=miniapp_url(cfg, products)))
    return ReplyKeyboardMarkup(keyboard=[[button]], resize_keyboard=True, is_persistent=True)
