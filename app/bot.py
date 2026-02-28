from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from .config import get_settings
from .db import fetch_scalar
from .nlp import parse_query
from .query_builder import build_query

logging.basicConfig(level=logging.INFO)

router = Router()


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "Отправьте запрос на русском. Например: 'Сколько всего видео есть в системе?'"
    )


@router.message()
async def handle_query(message: Message) -> None:
    text = (message.text or "").strip()
    if not text:
        return

    try:
        plan = await parse_query(text)
        stmt = build_query(plan)
        value = await fetch_scalar(stmt)
        await message.answer(str(value))
    except Exception as exc:
        logging.exception("Failed to handle query: %s", exc)
        await message.answer("Не смог разобрать запрос. Попробуйте переформулировать.")


async def main() -> None:
    settings = get_settings()
    bot = Bot(settings.bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
