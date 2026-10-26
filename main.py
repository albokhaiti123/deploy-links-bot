"""
deploy-links-bot v2 — Entry Point

Initializes the database, registers all handlers, starts background tasks,
and runs the self-healing polling loop.
"""

import asyncio

from aiogram import types

from core.config import validate_config
from core.logging_config import setup_logging, logger
from core.bot import bot, dp
from core.database import init_db
from handlers import register_all_routers
from tasks.background import (
    auto_delete_broadcasts,
    auto_recurring_campaigns,
    auto_recurring_broadcasts,
)


# ── Global Error Handler ────────────────────────────────────────────────────
@dp.errors()
async def global_error_handler(event: types.ErrorEvent) -> bool:
    logger.warning(f"Caught unhandled error: {event.exception.__class__.__name__}: {event.exception}")
    return True


async def main():
    # 1. Validate configuration
    validate_config()

    # 2. Setup logging
    setup_logging()

    # 3. Initialize database
    await init_db()
    logger.info("Database initialized.")

    # 4. Register all handlers
    register_all_routers(dp)
    logger.info("All routers registered.")

    # 5. Start background tasks
    asyncio.create_task(auto_delete_broadcasts())
    asyncio.create_task(auto_recurring_campaigns())
    asyncio.create_task(auto_recurring_broadcasts())
    logger.info("Background tasks started.")

    # 6. Self-healing polling loop
    while True:
        try:
            logger.info("Starting bot polling...")
            await dp.start_polling(bot, drop_pending_updates=True)
            break
        except Exception as e:
            logger.error(f"Critical Polling Error (Poisonous Update): {e}")
            logger.info("Restarting polling in 3 seconds to auto-clean...")
            await asyncio.sleep(3)

    await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
