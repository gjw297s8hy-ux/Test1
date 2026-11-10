"""Entry point: python -m bot"""
from __future__ import annotations

import asyncio
import logging

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from . import payments
from .config import load_config
from .db import Database
from .handlers import admin, user


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    db = Database(cfg.db_path)
    await db.connect()

    bot = Bot(cfg.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    # Admin router first: its filter lets non-admins fall through to the customer handlers.
    dp.include_router(admin.router)
    dp.include_router(user.router)

    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(
        timeout=timeout, headers={"User-Agent": "telegram-autoshop"}, trust_env=True
    ) as http:
        dp["db"], dp["cfg"], dp["http"] = db, cfg, http
        await bot.set_my_commands([
            BotCommand(command="start", description="Ouvrir la boutique"),
            BotCommand(command="help", description="Aide"),
        ])
        watcher = asyncio.create_task(payments.watch(bot, db, cfg, http))
        try:
            await dp.start_polling(bot)
        finally:
            watcher.cancel()
            await db.close()
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
