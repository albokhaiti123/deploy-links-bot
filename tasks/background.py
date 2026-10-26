"""
Background tasks — auto-delete broadcasts, recurring campaigns, recurring broadcasts.
"""

import asyncio
from datetime import datetime

from core.bot import bot
from core.logging_config import logger
from models.broadcasts import (
    get_expired_messages, remove_delete_record, get_active_recurring_broadcasts,
)
from models.campaigns import get_active_recurring_campaigns
from services.broadcast import execute_recurring_broadcast_cycle
from services.campaign import execute_recurring_campaign_cycle


async def auto_delete_broadcasts() -> None:
    """Background task: delete messages that have reached their scheduled delete time."""
    while True:
        try:
            await asyncio.sleep(60)
            expired = await get_expired_messages()
            for record_id, chat_id, message_id in expired:
                try:
                    await bot.delete_message(chat_id, message_id)
                except Exception:
                    pass
                await remove_delete_record(record_id)
        except Exception as e:
            logger.error(f"Error in auto_delete_broadcasts: {e}")


async def auto_recurring_campaigns() -> None:
    """Background task: execute recurring campaign broadcasts on schedule."""
    while True:
        try:
            await asyncio.sleep(300)
            campaigns = await get_active_recurring_campaigns()
            for cid, repeat_hours, last_at in campaigns:
                if not repeat_hours or repeat_hours <= 0:
                    continue
                if last_at:
                    try:
                        last_time = datetime.fromisoformat(str(last_at))
                    except (ValueError, TypeError):
                        last_time = datetime.min
                else:
                    last_time = datetime.min
                if (datetime.now() - last_time).total_seconds() >= repeat_hours * 3600:
                    logger.info(f"Recurring campaign {cid}: broadcasting...")
                    try:
                        await execute_recurring_campaign_cycle(cid)
                    except Exception as e:
                        logger.error(f"Recurring campaign {cid} error: {e}")
        except Exception as e:
            logger.error(f"Error in auto_recurring_campaigns: {e}")


async def auto_recurring_broadcasts() -> None:
    """Background task: execute recurring broadcasts on schedule."""
    while True:
        try:
            await asyncio.sleep(300)
            rows = await get_active_recurring_broadcasts()
            for row in rows:
                rb_id, target, text, media_id, media_type, is_vip, stars, repeat_hours, last_at = row
                if not repeat_hours or repeat_hours <= 0:
                    continue
                if last_at:
                    try:
                        last_time = datetime.fromisoformat(str(last_at))
                    except (ValueError, TypeError):
                        last_time = datetime.min
                else:
                    last_time = datetime.min
                if (datetime.now() - last_time).total_seconds() >= repeat_hours * 3600:
                    logger.info(f"Recurring broadcast {rb_id}: sending...")
                    try:
                        await execute_recurring_broadcast_cycle(
                            rb_id, target, text, media_id, media_type,
                            bool(is_vip), stars,
                        )
                    except Exception as e:
                        logger.error(f"Recurring broadcast {rb_id} error: {e}")
        except Exception as e:
            logger.error(f"Error in auto_recurring_broadcasts: {e}")
