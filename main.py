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
    exc = event.exception
    exc_msg = str(exc).lower()

    # ── HTML parse error fallback ──
    if "can't parse entities" in exc_msg:
        logger.warning(f"HTML parse error intercepted: {exc}")
        try:
            update = event.update
            # Try to answer the callback to prevent "query too old"
            if update.callback_query:
                try:
                    await update.callback_query.answer(
                        "⚠️ خطأ في تنسيق النص، يرجى مراجعة الإعدادات.", show_alert=True
                    )
                except Exception:
                    pass
            # Try to notify the user/admin in chat
            chat_id = None
            if update.message:
                chat_id = update.message.chat.id
            elif update.callback_query and update.callback_query.message:
                chat_id = update.callback_query.message.chat.id
            if chat_id:
                await bot.send_message(
                    chat_id,
                    "⚠️ حدث خطأ في تنسيق HTML بالنص. يرجى مراجعة النصوص في الإعدادات والتأكد من إغلاق جميع الوسوم مثل <b>...</b>",
                )
        except Exception as inner:
            logger.warning(f"Failed to send HTML error fallback: {inner}")
        return True

    # ── Query too old — suppress silently ──
    if "query is too old" in exc_msg or "query id is invalid" in exc_msg:
        return True

    logger.warning(f"Caught unhandled error: {exc.__class__.__name__}: {exc}")
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
