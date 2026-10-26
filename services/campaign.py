"""
Campaign service — business logic for the Campaign Unlock System.

Handles:
  - Showing user progress
  - Verifying group additions
  - Delivering unlock content
  - Campaign broadcasting
"""

import asyncio
import time

from aiogram import types
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.bot import bot
from core.config import BOT_USERNAME
from core.logging_config import logger
from models.campaigns import (
    get_campaign, get_verified_group_ids, add_verified_group,
    update_user_progress, ensure_user_progress, update_campaign_last_broadcast,
)
from models.groups import get_user_active_groups, deactivate_group
from models.events import log_event
from models.users import get_all_user_ids
from models.groups import get_active_group_ids
from models.broadcasts import schedule_delete_after
from services.media import send_media_message


# Verify cooldown: {(user_id, campaign_id): timestamp}
_campaign_verify_cooldown: dict[tuple[int, int], float] = {}
VERIFY_COOLDOWN_SECONDS = 10


async def show_campaign_progress(target, campaign_id: int, user_id: int) -> None:
    """
    Show campaign progress to a user.
    'target' can be a Message or CallbackQuery.
    """
    is_callback = isinstance(target, types.CallbackQuery)
    msg = target.message if is_callback else target

    campaign = await get_campaign(campaign_id)
    if not campaign or campaign["status"] == "deleted":
        text = "❌ This campaign is unavailable."
        if is_callback:
            try:
                await msg.edit_text(text)
            except TelegramAPIError:
                await msg.answer(text)
            await target.answer()
        else:
            await msg.answer(text)
        return

    # Get or create progress
    verified_count, status = await ensure_user_progress(campaign_id, user_id)
    required = campaign["required_groups"]
    await log_event(0, user_id, f"campaign_{campaign_id}_viewed")

    if status == "unlocked":
        text = (
            f"🎉 <b>Offer Unlocked!</b>\n\n"
            f"📣 <b>{campaign['name']}</b>\n\n"
            f"✅ You completed the requirement ({required}/{required} groups).\n\n"
            f"Tap the button below to claim your offer."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Claim Offer", callback_data=f"camp_unlock_{campaign_id}")]
        ])
    elif campaign["status"] == "paused" and verified_count == 0:
        text = "⏸ This campaign is currently paused."
        kb = None
    else:
        bar_filled = min(verified_count, required)
        bar = "▓" * bar_filled + "░" * (required - bar_filled)
        bot_info = await bot.get_me()
        text = (
            f"🔒 <b>Offer Locked</b>\n\n"
            f"📣 <b>{campaign['name']}</b>\n\n"
            f"To unlock this offer, add the bot to <b>{required}</b> groups.\n\n"
            f"📊 Progress: <b>{verified_count}</b> / <b>{required}</b>\n"
            f"<code>{bar}</code>\n"
        )
        if 0 < verified_count < required:
            text += f"\n⏳ Add <b>{required - verified_count}</b> more groups to unlock."

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="➕ Add Bot to Groups",
                url=f"https://t.me/{bot_info.username}?startgroup=camp_{campaign_id}",
            )],
            [InlineKeyboardButton(
                text="🔄 Verify Additions",
                callback_data=f"camp_verify_{campaign_id}",
            )],
        ])

    try:
        if is_callback:
            await msg.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
            await target.answer()
        else:
            await msg.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except TelegramAPIError:
        await msg.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        if is_callback:
            await target.answer()


async def verify_campaign_groups(callback: types.CallbackQuery, campaign_id: int) -> None:
    """Verify that the user has added the bot to enough groups for a campaign."""
    user_id = callback.from_user.id

    # Rate limit
    key = (user_id, campaign_id)
    now = time.time()
    if key in _campaign_verify_cooldown:
        elapsed = now - _campaign_verify_cooldown[key]
        if elapsed < VERIFY_COOLDOWN_SECONDS:
            remaining = int(VERIFY_COOLDOWN_SECONDS - elapsed)
            await callback.answer(
                f"⏳ Please wait {remaining} seconds before verifying again.",
                show_alert=True,
            )
            return
    _campaign_verify_cooldown[key] = now

    campaign = await get_campaign(campaign_id)
    if not campaign or campaign["status"] == "deleted":
        await callback.answer("❌ This campaign is unavailable.", show_alert=True)
        return

    # Check if already unlocked
    progress = await ensure_user_progress(campaign_id, user_id)
    if progress[1] == "unlocked":
        await show_campaign_progress(callback, campaign_id, user_id)
        return

    await callback.answer("🔄 Verifying group additions...")

    required = campaign["required_groups"]
    bot_info = await bot.get_me()
    bot_id = bot_info.id

    # Get user's groups and already-verified groups
    user_groups = await get_user_active_groups(user_id)
    already_verified = await get_verified_group_ids(campaign_id, user_id)

    new_verified = 0
    for chat_id, title in user_groups:
        if chat_id in already_verified:
            continue
        if len(already_verified) + new_verified >= required:
            break
        try:
            member = await bot.get_chat_member(chat_id, bot_id)
            if member.status in ("member", "administrator", "creator"):
                await add_verified_group(campaign_id, user_id, chat_id, title)
                new_verified += 1
                await log_event(chat_id, user_id, f"campaign_{campaign_id}_group_verified")
        except (TelegramForbiddenError, TelegramAPIError):
            pass
        await asyncio.sleep(0.1)

    total_verified = len(already_verified) + new_verified
    is_complete = total_verified >= required
    new_status = "unlocked" if is_complete else "in_progress"

    await update_user_progress(campaign_id, user_id, total_verified, new_status)

    if is_complete:
        await log_event(0, user_id, f"campaign_{campaign_id}_unlocked")

    await show_campaign_progress(callback, campaign_id, user_id)


async def deliver_unlock_content(callback: types.CallbackQuery, campaign_id: int) -> None:
    """Deliver the unlock content to a user who completed the campaign requirement."""
    user_id = callback.from_user.id

    campaign = await get_campaign(campaign_id)
    if not campaign:
        await callback.answer("❌ Campaign not found.", show_alert=True)
        return

    # Verify unlocked status
    progress = await ensure_user_progress(campaign_id, user_id)
    if progress[1] != "unlocked":
        await callback.answer("❌ You haven't completed the requirement yet.", show_alert=True)
        return

    await log_event(0, user_id, f"campaign_{campaign_id}_content_delivered")

    unlock_text = campaign["unlock_content"] or "🎁 Offer Unlocked!"
    try:
        sent_msg = await send_media_message(
            bot, callback.message.chat.id,
            f"🔓 <b>Unlocked Content:</b>\n\n{unlock_text}",
            media_id=campaign.get("unlock_media_file_id"),
            media_type=campaign.get("unlock_media_type"),
        )
        # Schedule auto-delete of unlock content
        del_sec = campaign.get("unlock_delete_seconds", 0)
        if del_sec and int(del_sec) > 0 and sent_msg:
            await schedule_delete_after(
                callback.message.chat.id, sent_msg.message_id, int(del_sec)
            )
    except Exception as e:
        logger.error(f"Failed to deliver campaign {campaign_id} content: {e}")
        await callback.message.answer("❌ An error occurred. Please try again later.")

    await callback.answer()


async def execute_campaign_broadcast(
    campaign_id: int, target: str, status_msg: types.Message
) -> None:
    """Broadcast a campaign promo to users/groups/all."""
    campaign = await get_campaign(campaign_id)
    if not campaign:
        await status_msg.edit_text("❌ الحملة غير موجودة.")
        return

    bot_info = await bot.get_me()
    cta_button = InlineKeyboardButton(
        text=campaign["button_text"],
        url=f"https://t.me/{bot_info.username}?start=camp_{campaign_id}",
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[cta_button]])

    targets_list: list[int] = []
    if target in ("users", "all"):
        targets_list += await get_all_user_ids()
    if target in ("groups", "all"):
        targets_list += await get_active_group_ids()

    success = 0
    for chat_id in targets_list:
        try:
            await send_media_message(
                bot, chat_id, campaign["promo_text"],
                media_id=campaign.get("media_file_id"),
                media_type=campaign.get("media_type"),
                keyboard=kb,
            )
            success += 1
        except TelegramForbiddenError:
            if target in ("groups", "all"):
                await deactivate_group(chat_id)
        except Exception:
            pass
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ اكتمل نشر الحملة! تم الإرسال إلى <b>{success}</b> جهة.",
        parse_mode=ParseMode.HTML,
    )


async def execute_recurring_campaign_cycle(campaign_id: int) -> None:
    """Execute a single cycle of a recurring campaign broadcast (called by background task)."""
    campaign = await get_campaign(campaign_id)
    if not campaign:
        return

    bot_info = await bot.get_me()
    cta = InlineKeyboardButton(
        text=campaign["button_text"],
        url=f"https://t.me/{bot_info.username}?start=camp_{campaign_id}",
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[cta]])

    targets: list[int] = []
    targets += await get_all_user_ids()
    targets += await get_active_group_ids()

    for chat_id in targets:
        try:
            await send_media_message(
                bot, chat_id, campaign["promo_text"],
                media_id=campaign.get("media_file_id"),
                media_type=campaign.get("media_type"),
                keyboard=kb,
            )
        except Exception:
            pass
        await asyncio.sleep(0.05)

    await update_campaign_last_broadcast(campaign_id)
    logger.info(f"Recurring campaign {campaign_id}: done.")
