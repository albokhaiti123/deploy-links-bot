"""
Bot & Dispatcher singletons.

Every module that needs `bot` or `dp` imports from here:
    from core.bot import bot, dp
"""

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from core.config import BOT_TOKEN

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
