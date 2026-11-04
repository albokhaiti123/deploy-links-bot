"""
Broadcast service — execute one-time and recurring broadcasts.
"""

import asyncio
from datetime import datetime, timedelta

from aiogram import types
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from core.bot import bot
from core.logging_config import logger
from models.users import get_all_user_ids
from models.groups import get_active_group_ids, deactivate_group
from models.broadcasts import schedule_delete
from services.media import send_media_message


async def execute_broadcast(data: dict, status_msg: types.Message) -> None:
    """
    Execute a broadcast from BroadcastWizard data.
    Sends to users and/or groups, handles VIP, schedules auto-delete.
    """
    target = data["target"]
    targets: list[int] = []

    if target == "users":
        targets = await get_all_user_ids()
    else:
        targets = await get_active_group_ids()

    success = 0
    dur = data.get("duration_mins", 0)
    delete_at = datetime.now() + timedelta(minutes=dur) if dur > 0 else None

    for chat_id in targets:
        try:
            sent_msg = await send_media_message(
                bot, chat_id, data["text"],
                media_id=data.get("media_id"),
                media_type=data.get("media_type"),
                is_vip=bool(data.get("is_vip")),
                stars=data.get("stars", 0),
            )

            if sent_msg and delete_at:
                await schedule_delete(chat_id, sent_msg.message_id, delete_at)

            success += 1
        except TelegramForbiddenError:
            if target != "users":
                await deactivate_group(chat_id)
        except TelegramBadRequest as e:
            err = str(e).lower()
            if "upgraded to a supergroup" in err:
                logger.info(f"Broadcast: group {chat_id} upgraded to supergroup, deactivating.")
                await deactivate_group(chat_id)
            elif "not enough rights" in err:
                logger.info(f"Broadcast: no send rights in {chat_id}, skipping.")
            else:
                logger.warning(f"Broadcast BadRequest for {chat_id}: {e}")
        except Exception as e:
            logger.warning(f"Broadcast failed for {chat_id}: {e}")

        await asyncio.sleep(0.05)  # Flood protection

    await status_msg.edit_text(f"✅ اكتملت المهمة! تمت الإذاعة بنجاح إلى {success} جهة.")


async def execute_recurring_broadcast_cycle(
    rb_id: int,
    target: str,
    text: str,
    media_id: str | None,
    media_type: str | None,
    is_vip: bool,
    stars: int,
) -> None:
    """Execute a single cycle of a recurring broadcast (called by background task)."""
    from models.broadcasts import update_recurring_broadcast_time

    targets: list[int] = []
    if target in ("users", "all"):
        targets += await get_all_user_ids()
    if target in ("groups", "all"):
        targets += await get_active_group_ids()

    for chat_id in targets:
        try:
            await send_media_message(
                bot, chat_id, text,
                media_id=media_id,
                media_type=media_type,
                is_vip=is_vip,
                stars=stars,
            )
        except TelegramForbiddenError:
            await deactivate_group(chat_id)
        except TelegramBadRequest as e:
            err = str(e).lower()
            if "upgraded to a supergroup" in err:
                await deactivate_group(chat_id)
            elif "not enough rights" not in err:
                logger.warning(f"Recurring broadcast {rb_id} BadRequest for {chat_id}: {e}")
        except Exception as e:
            logger.warning(f"Recurring broadcast {rb_id} failed for {chat_id}: {e}")
        await asyncio.sleep(0.05)

    await update_recurring_broadcast_time(rb_id)
    logger.info(f"Recurring broadcast {rb_id}: done.")
