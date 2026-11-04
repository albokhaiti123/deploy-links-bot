"""
User broadcast service — executes user campaigns with full fencing, ownership enforcement,
and delivery tracking.

NEVER call send_media_message() from this file — user campaigns support only:
  - Photo (photo_file_id)
  - Text (HTML formatted)
  - Inline buttons (buttons_json)
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta

from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.bot import bot
from core.config import ADMIN_ID
from core.logging_config import logger
from models.settings import get_setting
from models.groups import get_user_active_groups, get_group_by_id
from models.user_campaigns import (
    get_current_campaign, get_campaign_by_id, get_quota,
    create_campaign_atomic, update_campaign_status, update_campaign_next_run,
    set_campaign_run_id, claim_execution, heartbeat_claim, release_claim,
    record_delivery, get_delivery_status, get_delivery_stats,
    CURRENT_STATUSES,
)
from services.group_manager import handle_send_error

MAX_TEXT_LEN = 4096
MAX_CAPTION_LEN = 1024
MAX_BUTTON_LABEL = 64
MAX_BUTTONS = 10


# ── Authorization helpers ────────────────────────────────────────────────────

async def _feature_enabled() -> bool:
    return await get_setting("user_campaigns_enabled") == "true"


async def _get_generation() -> int:
    val = await get_setting("user_campaigns_generation")
    try:
        return int(val)
    except (ValueError, TypeError):
        return 1


async def assert_user_owns_campaign(campaign_id: int, user_id: int) -> dict | None:
    """Return campaign dict if user owns it, None otherwise."""
    if user_id == ADMIN_ID:
        return await get_campaign_by_id(campaign_id)
    c = await get_campaign_by_id(campaign_id)
    if c and c["owner_user_id"] == user_id:
        return c
    return None


async def assert_user_owns_group(chat_id: int, user_id: int) -> bool:
    """Return True if user owns group (reward_owner_id) or user is ADMIN_ID."""
    if user_id == ADMIN_ID:
        return True
    group = await get_group_by_id(chat_id)
    return group is not None and group[4] == user_id  # reward_owner_id index=4


# ── Content validation ────────────────────────────────────────────────────────

def validate_buttons(buttons_json: str | None) -> tuple[bool, str]:
    """Validate buttons JSON structure. Returns (ok, error_msg)."""
    if not buttons_json:
        return True, ""
    try:
        rows = json.loads(buttons_json)
        if not isinstance(rows, list):
            return False, "Buttons must be a list of rows."
        total = 0
        for row in rows:
            if not isinstance(row, list):
                return False, "Each row must be a list of buttons."
            for btn in row:
                if not isinstance(btn, dict) or "label" not in btn or "url" not in btn:
                    return False, "Each button must have 'label' and 'url'."
                if not btn["url"].startswith(("http://", "https://", "tg://")):
                    return False, f"Invalid URL: {btn['url']}"
                if len(btn["label"]) > MAX_BUTTON_LABEL:
                    return False, f"Button label too long (max {MAX_BUTTON_LABEL} chars)."
                total += 1
        if total > MAX_BUTTONS:
            return False, f"Too many buttons (max {MAX_BUTTONS})."
        return True, ""
    except json.JSONDecodeError:
        return False, "Invalid buttons JSON."


def build_keyboard(buttons_json: str | None) -> InlineKeyboardMarkup | None:
    if not buttons_json:
        return None
    rows = json.loads(buttons_json)
    kb_rows = []
    for row in rows:
        kb_rows.append([InlineKeyboardButton(text=b["label"], url=b["url"]) for b in row])
    return InlineKeyboardMarkup(inline_keyboard=kb_rows) if kb_rows else None


# ── Single message send (user campaign only) ──────────────────────────────────

async def _send_user_campaign_message(chat_id: int, text: str | None,
                                      photo_file_id: str | None,
                                      keyboard: InlineKeyboardMarkup | None) -> int | None:
    """
    Send a user campaign message (photo+caption OR text only).
    Returns message_id on success, raises on permanent errors.
    """
    if photo_file_id:
        caption = (text or "")[:MAX_CAPTION_LEN]
        try:
            msg = await bot.send_photo(
                chat_id=chat_id,
                photo=photo_file_id,
                caption=caption or None,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML if caption else None,
            )
        except Exception:
            msg = await bot.send_photo(
                chat_id=chat_id,
                photo=photo_file_id,
                caption=caption or None,
                reply_markup=keyboard,
            )
    else:
        body = (text or "")[:MAX_TEXT_LEN]
        try:
            msg = await bot.send_message(
                chat_id=chat_id,
                text=body,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            msg = await bot.send_message(
                chat_id=chat_id,
                text=body,
                reply_markup=keyboard,
            )
    return msg.message_id


# ── Core execution ────────────────────────────────────────────────────────────

async def execute_user_campaign(campaign_id: int) -> dict:
    """
    Execute a user campaign delivery cycle with full fencing.
    Returns stats dict: {sent, failed, skipped, uncertain}.
    """
    campaign = await get_campaign_by_id(campaign_id)
    if not campaign:
        return {"sent": 0, "failed": 0, "skipped": 0, "error": "Campaign not found"}

    # Fencing: check feature enabled and generation
    if not await _feature_enabled():
        logger.info(f"UserCampaign {campaign_id}: feature disabled, aborting")
        return {"sent": 0, "failed": 0, "skipped": 0, "error": "Feature disabled"}

    system_gen = await _get_generation()
    if campaign["system_generation"] != system_gen:
        logger.info(f"UserCampaign {campaign_id}: stale generation, aborting")
        await update_campaign_status(campaign_id, "suspended_admin")
        return {"sent": 0, "failed": 0, "skipped": 0, "error": "Generation mismatch"}

    # Claim execution
    run_id = str(uuid.uuid4())
    if not await claim_execution(campaign_id, run_id):
        logger.info(f"UserCampaign {campaign_id}: already running, skipping")
        return {"sent": 0, "failed": 0, "skipped": 1, "error": "Already running"}

    await set_campaign_run_id(campaign_id, run_id)
    await update_campaign_status(campaign_id, "running")

    target_groups = json.loads(campaign["target_groups_json"] or "[]")
    keyboard = build_keyboard(campaign["buttons_json"])

    stats = {"sent": 0, "failed": 0, "skipped": 0, "uncertain": 0}
    heartbeat_counter = 0

    try:
        for chat_id in target_groups:
            # Per-group fencing checks
            if not await _feature_enabled():
                logger.info(f"UserCampaign {campaign_id}: feature disabled mid-run, stopping")
                break

            current_gen = await _get_generation()
            if campaign["system_generation"] != current_gen:
                logger.info(f"UserCampaign {campaign_id}: generation changed mid-run, stopping")
                break

            # Verify run_id still valid (not replaced or suspended)
            current = await get_campaign_by_id(campaign_id)
            if not current or current["run_id"] != run_id:
                # run_id cleared by replacement or suspend — stop immediately
                logger.info(
                    f"UserCampaign {campaign_id}: run_id invalidated "
                    f"(DB run_id={current['run_id'] if current else 'None'}, "
                    f"expected={run_id}), stopping"
                )
                break

            # Skip already-delivered
            existing = await get_delivery_status(campaign_id, run_id, chat_id)
            if existing in ("sent", "skipped"):
                stats["skipped"] += 1
                continue

            # Mark uncertain before send
            await record_delivery(campaign_id, run_id, chat_id, "uncertain")

            try:
                await _send_user_campaign_message(
                    chat_id, campaign["text"], campaign["photo_file_id"], keyboard
                )
                await record_delivery(campaign_id, run_id, chat_id, "sent")
                await update_group_health_ok(chat_id)
                stats["sent"] += 1
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
                try:
                    await _send_user_campaign_message(
                        chat_id, campaign["text"], campaign["photo_file_id"], keyboard
                    )
                    await record_delivery(campaign_id, run_id, chat_id, "sent")
                    stats["sent"] += 1
                except Exception as e2:
                    await handle_send_error(chat_id, e2)
                    await record_delivery(campaign_id, run_id, chat_id, "failed", str(e2)[:100])
                    stats["failed"] += 1
            except Exception as e:
                await handle_send_error(chat_id, e)
                await record_delivery(campaign_id, run_id, chat_id, "failed", str(e)[:100])
                stats["failed"] += 1

            # Heartbeat every 10 groups
            heartbeat_counter += 1
            if heartbeat_counter % 10 == 0:
                await heartbeat_claim(campaign_id, run_id)

            await asyncio.sleep(0.05)

    finally:
        await release_claim(campaign_id)
        await set_campaign_run_id(campaign_id, None)

        # Determine final status
        final_campaign = await get_campaign_by_id(campaign_id)
        if final_campaign and final_campaign["status"] == "running":
            if final_campaign["mode"] == "immediate":
                await update_campaign_status(campaign_id, "completed")
            else:
                # Recurring: set next run
                next_run = datetime.now() + timedelta(hours=final_campaign["repeat_hours"])
                await update_campaign_next_run(campaign_id, next_run)
                await update_campaign_status(campaign_id, "active")

    return stats


async def update_group_health_ok(chat_id: int) -> None:
    """Mark group as healthy after successful send."""
    from models.groups import update_group_health
    await update_group_health(chat_id, "ok")


# ── Campaign creation service ─────────────────────────────────────────────────

async def create_user_campaign(
    user_id: int,
    text: str | None,
    photo_file_id: str | None,
    buttons_json: str | None,
    target_chat_ids: list[int],
    mode: str,
    repeat_hours: int,
    auto_delete_seconds: int = 0,
) -> tuple[int | None, str]:
    """
    Full campaign creation with all validation and atomic DB write.
    Returns (campaign_id, error_message). campaign_id is None on failure.
    """
    # Feature check
    if not await _feature_enabled():
        return None, "User campaigns are currently disabled by the administrator."

    # Ownership: verify all target groups belong to user (or user is owner)
    if user_id != ADMIN_ID:
        owned = {g[0] for g in await get_user_active_groups(user_id)}
        invalid = [cid for cid in target_chat_ids if cid not in owned]
        if invalid:
            return None, "Some selected groups do not belong to you."

    if not target_chat_ids:
        return None, "No target groups selected."

    # Content validation
    if not text and not photo_file_id:
        return None, "Campaign must have text or a photo."

    if buttons_json:
        ok, err = validate_buttons(buttons_json)
        if not ok:
            return None, err

    # Recurring minimum
    if mode == "recurring" and repeat_hours < 6:
        return None, "Minimum recurring interval is 6 hours."

    system_gen = await _get_generation()
    target_json = json.dumps(target_chat_ids)

    campaign_id = await create_campaign_atomic(
        user_id=user_id,
        text=text,
        photo_file_id=photo_file_id,
        buttons_json=buttons_json,
        target_groups_json=target_json,
        mode=mode,
        repeat_hours=repeat_hours,
        auto_delete_seconds=auto_delete_seconds,
        system_generation=system_gen,
    )

    if campaign_id is None:
        return None, "Daily campaign limit reached (2 per day). Try again tomorrow."

    return campaign_id, ""
