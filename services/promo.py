"""
Promo service — handles promotional message logic.

Responsibilities:
  - Build promo keyboards
  - Build welcome (start) message data
  - Trigger group promo on new member join
"""

import time
from datetime import timedelta, datetime

from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.bot import bot
from core.config import BOT_USERNAME
from core.logging_config import logger
from models.settings import get_setting, get_many_settings
from models.groups import get_last_promo_msg, update_last_promo_msg, deactivate_group
from models.events import log_event
from models.broadcasts import schedule_delete_after
from services.media import send_media_message

# In-memory cooldown cache: {chat_id: last_promo_timestamp}
_last_promo_times: dict[int, float] = {}


def get_bot_add_url(bot_username: str) -> str:
    """Generate the URL to add the bot to a group."""
    return f"https://t.me/{bot_username}?startgroup=add"


def build_promo_keyboard(
    promo_url: str,
    promo_button_text: str,
    bot_username: str,
    show_bot_btn: str = "true",
) -> InlineKeyboardMarkup:
    """Build the inline keyboard for promo messages."""
    keyboard = []
    if promo_button_text and promo_url:
        keyboard.append([InlineKeyboardButton(text=promo_button_text, url=promo_url)])
    if show_bot_btn == "true":
        keyboard.append([InlineKeyboardButton(
            text="🤖 Add bot to your group",
            url=get_bot_add_url(bot_username),
        )])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def get_start_message_data(bot_username: str) -> tuple[str, InlineKeyboardMarkup]:
    """
    Build welcome message text and keyboard for /start in private chat.
    Returns (text, InlineKeyboardMarkup).
    """
    s = await get_many_settings(
        "start_message", "start_btn2_name", "start_btn2_type", "start_btn2_content"
    )
    start_text = s["start_message"] or "🤖 Welcome to the bot!"

    kb = [[InlineKeyboardButton(
        text="➕ Add bot to my group",
        url=get_bot_add_url(bot_username),
    )]]

    btn2_name = s["start_btn2_name"]
    if btn2_name:
        if s["start_btn2_type"] == "url":
            kb.append([InlineKeyboardButton(text=btn2_name, url=s["start_btn2_content"])])
        else:
            kb.append([InlineKeyboardButton(text=btn2_name, callback_data="start_btn2_click")])

    return start_text, InlineKeyboardMarkup(inline_keyboard=kb)


async def trigger_group_promo(message, target_user) -> None:
    """
    Send a promotional message in a group when a new member joins.
    Handles cooldown, media, VIP, auto-delete old, and timed self-destruct.
    """
    from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter, TelegramForbiddenError

    bot_info = await bot.get_me()
    chat_id = message.chat.id

    # ── Check enabled ──
    s = await get_many_settings(
        "promo_enabled", "cooldown", "promo_text", "promo_url",
        "promo_button_text", "promo_media_id", "promo_media_type",
        "show_add_bot_button", "auto_delete", "promo_is_vip",
        "promo_stars", "promo_delete_seconds",
    )

    if s["promo_enabled"] != "true":
        return

    # ── Cooldown ──
    cooldown_val = s["cooldown"]
    cooldown = int(cooldown_val) if cooldown_val and cooldown_val.isdigit() else 60
    current_time = time.time()

    if cooldown > 0 and chat_id in _last_promo_times:
        if current_time - _last_promo_times[chat_id] < cooldown:
            logger.info(f"Promo skipped in {chat_id} due to cooldown active.")
            return

    _last_promo_times[chat_id] = current_time

    # ── Format text with mention ──
    user_name = target_user.first_name.replace("<", "&lt;").replace(">", "&gt;")
    mention = f"<a href='tg://user?id={target_user.id}'>{user_name}</a>"
    promo_text_formatted = s["promo_text"].replace("{user}", mention)

    # ── Build keyboard ──
    keyboard = build_promo_keyboard(
        s["promo_url"], s["promo_button_text"],
        bot_info.username or BOT_USERNAME, s["show_add_bot_button"],
    )

    # ── Auto-delete old message ──
    if s["auto_delete"] == "true":
        old_msg_id = await get_last_promo_msg(chat_id)
        if old_msg_id:
            try:
                await bot.delete_message(chat_id, old_msg_id)
            except TelegramAPIError:
                pass

    # ── Send ──
    is_vip = s["promo_is_vip"] == "true"
    stars = int(s["promo_stars"]) if s["promo_stars"] and s["promo_stars"].isdigit() else 50

    try:
        sent_msg = await send_media_message(
            bot, chat_id, promo_text_formatted,
            media_id=s["promo_media_id"] or None,
            media_type=s["promo_media_type"] or None,
            keyboard=keyboard,
            is_vip=is_vip,
            stars=stars,
        )

        if sent_msg:
            await update_last_promo_msg(chat_id, sent_msg.message_id)

        await log_event(chat_id, target_user.id, "promo_sent")

        # ── Timed self-destruct ──
        promo_del_sec = s["promo_delete_seconds"]
        if sent_msg and promo_del_sec and promo_del_sec.isdigit() and int(promo_del_sec) > 0:
            await schedule_delete_after(chat_id, sent_msg.message_id, int(promo_del_sec))

        logger.info(f"Promo sent in {chat_id}")

    except TelegramRetryAfter as e:
        logger.warning(f"Rate limited in {chat_id}. Retry after {e.retry_after}")
    except TelegramForbiddenError:
        logger.warning(f"Forbidden to send message in {chat_id}. Marking inactive.")
        await deactivate_group(chat_id)
    except TelegramAPIError as e:
        logger.error(f"Failed to send promo in {chat_id}: {e}")
