#!/usr/bin/env python3
"""
Phase 2 Repair Script — Deploy Links Bot
Addresses confirmed issues: ISS-05, ISS-07, ISS-08, ISS-09, ISS-10, ISS-16, ISS-17

Features:
  - Idempotent execution (safe to run multiple times)
  - Automatic backup before modification (.backups/phase2/)
  - AST syntax verification before writing any file
  - Supports --dry-run and --rollback modes
"""

import argparse
import ast
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKUP_DIR = PROJECT_ROOT / ".backups" / "phase2"

TARGET_FILES = [
    "handlers/start.py",
    "services/media.py",
    "models/campaigns.py",
    "services/campaign.py",
    "services/broadcast.py",
    "services/user_broadcast.py",
    "handlers/admin/campaigns.py",
    "handlers/admin/promo_settings.py",
    "handlers/admin/welcome_settings.py",
    "handlers/admin/stats.py",
    "handlers/admin/user_management.py",
    "handlers/admin/button_manager.py",
    "handlers/admin/recurring.py",
    "handlers/user/my_groups.py",
    "handlers/user/my_campaign.py",
]


def verify_python_syntax(code: str, filepath: str) -> None:
    """Parse Python source with AST to guarantee zero syntax errors."""
    try:
        ast.parse(code, filename=filepath)
    except SyntaxError as exc:
        raise RuntimeError(f"AST syntax check failed for {filepath}: {exc}") from exc


def create_backups(dry_run: bool = False) -> None:
    if dry_run:
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for rel_path in TARGET_FILES:
        src = PROJECT_ROOT / rel_path
        dst = BACKUP_DIR / rel_path
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def rollback() -> int:
    if not BACKUP_DIR.exists():
        print("[ROLLBACK] No backup directory found at .backups/phase2/")
        return 1
    for rel_path in TARGET_FILES:
        bkp = BACKUP_DIR / rel_path
        dst = PROJECT_ROOT / rel_path
        if bkp.exists():
            shutil.copy2(bkp, dst)
            print(f"[ROLLBACK] Restored {rel_path}")
    print("[ROLLBACK] Phase 2 rollback completed successfully.")
    return 0


def ensure_import_html(content: str) -> str:
    """Ensure `import html` is present at top-level imports."""
    if "import html\n" in content:
        return content
    if "from aiogram import" in content:
        return content.replace("from aiogram import", "import html\nfrom aiogram import", 1)
    return "import html\n" + content


# ── 1. handlers/start.py (ISS-05) ────────────────────────────────────────────

def patch_handlers_start(content: str) -> tuple[str, list[str]]:
    applied = []
    old_block = (
        '@router.callback_query(F.data == "start_btn2_click")\n'
        'async def cb_start_btn2_click(callback: types.CallbackQuery):\n'
        '    content = await get_setting("start_btn2_content")\n'
        '    if not content:\n'
        '        content = "No message available."\n'
        '    kb = InlineKeyboardMarkup(inline_keyboard=[\n'
        '        [InlineKeyboardButton(text="🔙 Back", callback_data="start_back")]\n'
        '    ])\n'
        '    await callback.message.edit_text(content, reply_markup=kb, parse_mode=ParseMode.HTML)\n'
        '\n'
        '\n'
        '@router.callback_query(F.data == "start_back")\n'
        'async def cb_start_back(callback: types.CallbackQuery):\n'
        '    bot_info = await bot.get_me()\n'
        '    text, kb = await get_start_message_data(bot_info.username or BOT_USERNAME)\n'
        '    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)'
    )
    new_block = (
        'async def _edit_start_message(message: types.Message, text: str, kb: InlineKeyboardMarkup) -> None:\n'
        '    """Safely edit welcome message whether it is text-only or photo/video media."""\n'
        '    is_media = bool(getattr(message, "photo", None) or getattr(message, "video", None) or getattr(message, "caption", None) is not None)\n'
        '    try:\n'
        '        if is_media:\n'
        '            await message.edit_caption(caption=text, reply_markup=kb, parse_mode=ParseMode.HTML)\n'
        '        else:\n'
        '            await message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)\n'
        '    except Exception:\n'
        '        if is_media:\n'
        '            await message.edit_caption(caption=text, reply_markup=kb)\n'
        '        else:\n'
        '            await message.edit_text(text, reply_markup=kb)\n'
        '\n'
        '\n'
        '@router.callback_query(F.data == "start_btn2_click")\n'
        'async def cb_start_btn2_click(callback: types.CallbackQuery):\n'
        '    content = await get_setting("start_btn2_content")\n'
        '    if not content:\n'
        '        content = "No message available."\n'
        '    kb = InlineKeyboardMarkup(inline_keyboard=[\n'
        '        [InlineKeyboardButton(text="🔙 Back", callback_data="start_back")]\n'
        '    ])\n'
        '    await _edit_start_message(callback.message, content, kb)\n'
        '    try:\n'
        '        await callback.answer()\n'
        '    except Exception:\n'
        '        pass\n'
        '\n'
        '\n'
        '@router.callback_query(F.data == "start_back")\n'
        'async def cb_start_back(callback: types.CallbackQuery):\n'
        '    from models.admins import is_admin as _is_admin\n'
        '    bot_info = await bot.get_me()\n'
        '    text, kb = await get_start_message_data(bot_info.username or BOT_USERNAME)\n'
        '    if not await _is_admin(callback.from_user.id):\n'
        '        existing_rows = kb.inline_keyboard if kb else []\n'
        '        user_btn = [[InlineKeyboardButton(text="👤 My Dashboard", callback_data="user_menu")]]\n'
        '        kb = InlineKeyboardMarkup(inline_keyboard=existing_rows + user_btn)\n'
        '    await _edit_start_message(callback.message, text, kb)\n'
        '    try:\n'
        '        await callback.answer()\n'
        '    except Exception:\n'
        '        pass'
    )
    if "async def _edit_start_message" not in content:
        if old_block not in content:
            raise RuntimeError("Could not locate cb_start_btn2_click / cb_start_back in handlers/start.py")
        content = content.replace(old_block, new_block, 1)
        applied.append("ISS-05: Fixed media caption editing in cb_start_btn2_click/cb_start_back and preserved user_menu button")
    return content, applied


# ── 2. services/media.py (ISS-17) ────────────────────────────────────────────

def patch_services_media(content: str) -> tuple[str, list[str]]:
    applied = []
    old_paid_media = (
        '            try:\n'
        '                sent = await bot.send_paid_media(\n'
        '                    chat_id=chat_id,\n'
        '                    star_count=stars,\n'
        '                    media=media_payload,\n'
        '                    caption=text,\n'
        '                    parse_mode=parse_mode,\n'
        '                )\n'
        '            except TelegramBadRequest as e:\n'
        '                if "can\'t parse entities" in str(e).lower():\n'
        '                    logger.warning(f"HTML parse error in VIP media for {chat_id}, retrying without formatting")\n'
        '                    sent = await bot.send_paid_media(\n'
        '                        chat_id=chat_id,\n'
        '                        star_count=stars,\n'
        '                        media=media_payload,\n'
        '                        caption=text,\n'
        '                    )'
    )
    new_paid_media = (
        '            try:\n'
        '                sent = await bot.send_paid_media(\n'
        '                    chat_id=chat_id,\n'
        '                    star_count=stars,\n'
        '                    media=media_payload,\n'
        '                    caption=text,\n'
        '                    parse_mode=parse_mode,\n'
        '                    reply_markup=keyboard,\n'
        '                )\n'
        '            except TelegramBadRequest as e:\n'
        '                if "can\'t parse entities" in str(e).lower():\n'
        '                    logger.warning(f"HTML parse error in VIP media for {chat_id}, retrying without formatting")\n'
        '                    sent = await bot.send_paid_media(\n'
        '                        chat_id=chat_id,\n'
        '                        star_count=stars,\n'
        '                        media=media_payload,\n'
        '                        caption=text,\n'
        '                        reply_markup=keyboard,\n'
        '                    )'
    )
    if "reply_markup=keyboard,\n                )\n            except TelegramBadRequest" not in content:
        if old_paid_media not in content:
            raise RuntimeError("Could not locate send_paid_media block in services/media.py")
        content = content.replace(old_paid_media, new_paid_media, 1)
        applied.append("ISS-17: Passed reply_markup=keyboard to bot.send_paid_media in services/media.py")
    return content, applied


# ── 3. models/campaigns.py (ISS-08) ──────────────────────────────────────────

def patch_models_campaigns(content: str) -> tuple[str, list[str]]:
    applied = []
    old_fn = (
        'async def get_verified_group_ids(campaign_id: int, user_id: int) -> set[int]:\n'
        '    """Return set of chat_ids already verified for a user in a campaign."""\n'
        '    async with get_db() as db:\n'
        '        async with db.execute(\n'
        '            "SELECT chat_id FROM campaign_groups WHERE campaign_id = ? AND user_id = ? AND verified = 1",\n'
        '            (campaign_id, user_id),\n'
        '        ) as cursor:\n'
        '            return {row[0] for row in await cursor.fetchall()}'
    )
    new_fn = (
        'async def get_verified_group_ids(campaign_id: int, user_id: int) -> set[int]:\n'
        '    """Return set of chat_ids already verified for a user in a campaign."""\n'
        '    async with get_db() as db:\n'
        '        async with db.execute(\n'
        '            "SELECT chat_id FROM campaign_groups WHERE campaign_id = ? AND user_id = ? AND verified = 1",\n'
        '            (campaign_id, user_id),\n'
        '        ) as cursor:\n'
        '            return {row[0] for row in await cursor.fetchall()}\n'
        '\n'
        '\n'
        'async def get_globally_verified_group_ids(exclude_campaign_id: int | None = None) -> set[int]:\n'
        '    """Return set of chat_ids already verified in any other campaign to prevent group reuse across campaigns."""\n'
        '    async with get_db() as db:\n'
        '        if exclude_campaign_id is not None:\n'
        '            async with db.execute(\n'
        '                "SELECT chat_id FROM campaign_groups WHERE campaign_id != ? AND verified = 1",\n'
        '                (exclude_campaign_id,),\n'
        '            ) as cursor:\n'
        '                return {row[0] for row in await cursor.fetchall()}\n'
        '        async with db.execute(\n'
        '            "SELECT chat_id FROM campaign_groups WHERE verified = 1"\n'
        '        ) as cursor:\n'
        '            return {row[0] for row in await cursor.fetchall()}'
    )
    if "async def get_globally_verified_group_ids" not in content:
        if old_fn not in content:
            raise RuntimeError("Could not locate get_verified_group_ids in models/campaigns.py")
        content = content.replace(old_fn, new_fn, 1)
        applied.append("ISS-08: Added get_globally_verified_group_ids() to models/campaigns.py")
    return content, applied


# ── 4. services/campaign.py (ISS-07, ISS-08, ISS-09, ISS-16) ─────────────────

def patch_services_campaign(content: str) -> tuple[str, list[str]]:
    applied = []
    content = ensure_import_html(content)

    # 1. Import TelegramRetryAfter and get_globally_verified_group_ids
    old_exc_import = "from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramBadRequest"
    new_exc_import = "from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter"
    if "TelegramRetryAfter" not in content:
        content = content.replace(old_exc_import, new_exc_import, 1)

    old_model_import = (
        "from models.campaigns import (\n"
        "    get_campaign, get_verified_group_ids, add_verified_group,\n"
        "    update_user_progress, ensure_user_progress, update_campaign_last_broadcast,\n"
        ")"
    )
    new_model_import = (
        "from models.campaigns import (\n"
        "    get_campaign, get_verified_group_ids, get_globally_verified_group_ids,\n"
        "    add_verified_group, update_user_progress, ensure_user_progress,\n"
        "    update_campaign_last_broadcast,\n"
        ")"
    )
    if "get_globally_verified_group_ids" not in content:
        if old_model_import not in content:
            raise RuntimeError("Could not locate models.campaigns import in services/campaign.py")
        content = content.replace(old_model_import, new_model_import, 1)

    # 2. ISS-09: Add build_campaign_keyboard helper
    helper_code = (
        "\n\nasync def build_campaign_keyboard(\n"
        "    campaign_id: int, button_text: str, bot_username: str\n"
        ") -> InlineKeyboardMarkup:\n"
        '    """Build inline keyboard for a campaign promo including active custom buttons."""\n'
        "    from models.custom_buttons import get_buttons\n"
        "\n"
        "    cta_button = InlineKeyboardButton(\n"
        "        text=button_text,\n"
        '        url=f"https://t.me/{bot_username}?start=camp_{campaign_id}",\n'
        "    )\n"
        "    kb_rows = [[cta_button]]\n"
        '    custom = await get_buttons(f"campaign_{campaign_id}", active_only=True)\n'
        "    for btn in custom:\n"
        '        kb_rows.append([InlineKeyboardButton(text=btn["label"], url=btn["url"])])\n'
        "    return InlineKeyboardMarkup(inline_keyboard=kb_rows)\n"
    )
    if "async def build_campaign_keyboard" not in content:
        anchor = "VERIFY_COOLDOWN_SECONDS = 10"
        if anchor not in content:
            raise RuntimeError("Could not locate VERIFY_COOLDOWN_SECONDS in services/campaign.py")
        content = content.replace(anchor, anchor + helper_code, 1)
        applied.append("ISS-09: Added build_campaign_keyboard() with custom buttons integration")

    # 3. ISS-07: Escape campaign['name'] in show_campaign_progress
    old_progress_text = (
        '    if status == "unlocked":\n'
        '        text = (\n'
        '            f"🎉 <b>Offer Unlocked!</b>\\n\\n"\n'
        '            f"📣 <b>{campaign[\'name\']}</b>\\n\\n"\n'
        '            f"✅ You completed the requirement ({required}/{required} groups).\\n\\n"\n'
        '            f"Tap the button below to claim your offer."\n'
        '        )\n'
        '        kb = InlineKeyboardMarkup(inline_keyboard=[\n'
        '            [InlineKeyboardButton(text="🎁 Claim Offer", callback_data=f"camp_unlock_{campaign_id}")]\n'
        '        ])\n'
        '    elif campaign["status"] == "paused" and verified_count == 0:\n'
        '        text = "⏸ This campaign is currently paused."\n'
        '        kb = None\n'
        '    else:\n'
        '        bar_filled = min(verified_count, required)\n'
        '        bar = "▓" * bar_filled + "░" * (required - bar_filled)\n'
        '        bot_info = await bot.get_me()\n'
        '        text = (\n'
        '            f"🔒 <b>Offer Locked</b>\\n\\n"\n'
        '            f"📣 <b>{campaign[\'name\']}</b>\\n\\n"'
    )
    new_progress_text = (
        '    safe_name = html.escape(str(campaign["name"] or ""))\n'
        '    if status == "unlocked":\n'
        '        text = (\n'
        '            f"🎉 <b>Offer Unlocked!</b>\\n\\n"\n'
        '            f"📣 <b>{safe_name}</b>\\n\\n"\n'
        '            f"✅ You completed the requirement ({required}/{required} groups).\\n\\n"\n'
        '            f"Tap the button below to claim your offer."\n'
        '        )\n'
        '        kb = InlineKeyboardMarkup(inline_keyboard=[\n'
        '            [InlineKeyboardButton(text="🎁 Claim Offer", callback_data=f"camp_unlock_{campaign_id}")]\n'
        '        ])\n'
        '    elif campaign["status"] == "paused" and verified_count == 0:\n'
        '        text = "⏸ This campaign is currently paused."\n'
        '        kb = None\n'
        '    else:\n'
        '        bar_filled = min(verified_count, required)\n'
        '        bar = "▓" * bar_filled + "░" * (required - bar_filled)\n'
        '        bot_info = await bot.get_me()\n'
        '        text = (\n'
        '            f"🔒 <b>Offer Locked</b>\\n\\n"\n'
        '            f"📣 <b>{safe_name}</b>\\n\\n"'
    )
    if "safe_name = html.escape" not in content:
        if old_progress_text not in content:
            raise RuntimeError("Could not locate campaign name interpolation in show_campaign_progress()")
        content = content.replace(old_progress_text, new_progress_text, 1)
        applied.append("ISS-07: Escaped campaign['name'] in show_campaign_progress()")

    # 4. ISS-08: Prevent reusing groups already verified in previous campaigns
    old_verify_loop = (
        "    # Get user's groups and already-verified groups\n"
        "    user_groups = await get_user_active_groups(user_id)\n"
        "    already_verified = await get_verified_group_ids(campaign_id, user_id)\n"
        "\n"
        "    new_verified = 0\n"
        "    for group_row in user_groups:\n"
        "        chat_id, title = group_row[0], group_row[1]\n"
        "        if chat_id in already_verified:\n"
        "            continue"
    )
    new_verify_loop = (
        "    # Get user's groups, already-verified groups for this campaign, and globally used groups\n"
        "    user_groups = await get_user_active_groups(user_id)\n"
        "    already_verified = await get_verified_group_ids(campaign_id, user_id)\n"
        "    used_in_other_campaigns = await get_globally_verified_group_ids(exclude_campaign_id=campaign_id)\n"
        "\n"
        "    new_verified = 0\n"
        "    for group_row in user_groups:\n"
        "        chat_id, title = group_row[0], group_row[1]\n"
        "        if chat_id in already_verified or chat_id in used_in_other_campaigns:\n"
        "            continue"
    )
    if "used_in_other_campaigns = await get_globally_verified_group_ids" not in content:
        if old_verify_loop not in content:
            raise RuntimeError("Could not locate verify loop in services/campaign.py")
        content = content.replace(old_verify_loop, new_verify_loop, 1)
        applied.append("ISS-08: Blocked reuse of groups already verified in earlier campaigns")

    # 5. ISS-09 & ISS-16: Update execute_campaign_broadcast and execute_recurring_campaign_cycle
    old_broadcast_funcs = (
        'async def execute_campaign_broadcast(\n'
        '    campaign_id: int, target: str, status_msg: types.Message\n'
        ') -> None:\n'
        '    """Broadcast a campaign promo to users/groups/all."""\n'
        '    campaign = await get_campaign(campaign_id)\n'
        '    if not campaign:\n'
        '        await status_msg.edit_text("❌ الحملة غير موجودة.")\n'
        '        return\n'
        '\n'
        '    bot_info = await bot.get_me()\n'
        '    cta_button = InlineKeyboardButton(\n'
        '        text=campaign["button_text"],\n'
        '        url=f"https://t.me/{bot_info.username}?start=camp_{campaign_id}",\n'
        '    )\n'
        '    kb = InlineKeyboardMarkup(inline_keyboard=[[cta_button]])\n'
        '\n'
        '    targets_list: list[int] = []\n'
        '    if target in ("users", "all"):\n'
        '        targets_list += await get_all_user_ids()\n'
        '    if target in ("groups", "all"):\n'
        '        targets_list += await get_active_group_ids()\n'
        '\n'
        '    success = 0\n'
        '    for chat_id in targets_list:\n'
        '        try:\n'
        '            await send_media_message(\n'
        '                bot, chat_id, campaign["promo_text"],\n'
        '                media_id=campaign.get("media_file_id"),\n'
        '                media_type=campaign.get("media_type"),\n'
        '                keyboard=kb,\n'
        '            )\n'
        '            success += 1\n'
        '        except TelegramForbiddenError:\n'
        '            if target in ("groups", "all"):\n'
        '                await deactivate_group(chat_id)\n'
        '        except TelegramBadRequest as e:\n'
        '            err = str(e).lower()\n'
        '            if "upgraded to a supergroup" in err:\n'
        '                await deactivate_group(chat_id)\n'
        '            elif "not enough rights" not in err:\n'
        '                logger.warning(f"Campaign {campaign_id} BadRequest for {chat_id}: {e}")\n'
        '        except Exception as e:\n'
        '            logger.warning(f"Campaign {campaign_id} broadcast failed for {chat_id}: {e}")\n'
        '        await asyncio.sleep(0.05)\n'
        '\n'
        '    await status_msg.edit_text(\n'
        '        f"✅ اكتمل نشر الحملة! تم الإرسال إلى <b>{success}</b> جهة.",\n'
        '        parse_mode=ParseMode.HTML,\n'
        '    )\n'
        '\n'
        '\n'
        'async def execute_recurring_campaign_cycle(campaign_id: int) -> None:\n'
        '    """Execute a single cycle of a recurring campaign broadcast (called by background task)."""\n'
        '    campaign = await get_campaign(campaign_id)\n'
        '    if not campaign:\n'
        '        return\n'
        '\n'
        '    bot_info = await bot.get_me()\n'
        '    cta = InlineKeyboardButton(\n'
        '        text=campaign["button_text"],\n'
        '        url=f"https://t.me/{bot_info.username}?start=camp_{campaign_id}",\n'
        '    )\n'
        '    kb = InlineKeyboardMarkup(inline_keyboard=[[cta]])\n'
        '\n'
        '    targets: list[int] = []\n'
        '    targets += await get_all_user_ids()\n'
        '    targets += await get_active_group_ids()\n'
        '\n'
        '    for chat_id in targets:\n'
        '        try:\n'
        '            await send_media_message(\n'
        '                bot, chat_id, campaign["promo_text"],\n'
        '                media_id=campaign.get("media_file_id"),\n'
        '                media_type=campaign.get("media_type"),\n'
        '                keyboard=kb,\n'
        '            )\n'
        '        except TelegramForbiddenError:\n'
        '            await deactivate_group(chat_id)\n'
        '        except TelegramBadRequest as e:\n'
        '            err = str(e).lower()\n'
        '            if "upgraded to a supergroup" in err:\n'
        '                await deactivate_group(chat_id)\n'
        '            elif "not enough rights" not in err:\n'
        '                logger.warning(f"Recurring campaign {campaign_id} BadRequest for {chat_id}: {e}")\n'
        '        except Exception as e:\n'
        '            logger.warning(f"Recurring campaign {campaign_id} failed for {chat_id}: {e}")\n'
        '        await asyncio.sleep(0.05)\n'
        '\n'
        '    await update_campaign_last_broadcast(campaign_id)\n'
        '    logger.info(f"Recurring campaign {campaign_id}: done.")'
    )
    new_broadcast_funcs = (
        'async def execute_campaign_broadcast(\n'
        '    campaign_id: int, target: str, status_msg: types.Message\n'
        ') -> None:\n'
        '    """Broadcast a campaign promo to users/groups/all."""\n'
        '    campaign = await get_campaign(campaign_id)\n'
        '    if not campaign:\n'
        '        await status_msg.edit_text("❌ الحملة غير موجودة.")\n'
        '        return\n'
        '\n'
        '    bot_info = await bot.get_me()\n'
        '    kb = await build_campaign_keyboard(\n'
        '        campaign_id, campaign["button_text"], bot_info.username or BOT_USERNAME\n'
        '    )\n'
        '\n'
        '    targets_list: list[int] = []\n'
        '    if target in ("users", "all"):\n'
        '        targets_list += await get_all_user_ids()\n'
        '    if target in ("groups", "all"):\n'
        '        targets_list += await get_active_group_ids()\n'
        '\n'
        '    success = 0\n'
        '    for chat_id in targets_list:\n'
        '        try:\n'
        '            await send_media_message(\n'
        '                bot, chat_id, campaign["promo_text"],\n'
        '                media_id=campaign.get("media_file_id"),\n'
        '                media_type=campaign.get("media_type"),\n'
        '                keyboard=kb,\n'
        '            )\n'
        '            success += 1\n'
        '        except TelegramRetryAfter as e:\n'
        '            logger.warning(f"Campaign {campaign_id} rate limited for {chat_id}, sleeping {e.retry_after}s")\n'
        '            await asyncio.sleep(e.retry_after + 1)\n'
        '            try:\n'
        '                await send_media_message(\n'
        '                    bot, chat_id, campaign["promo_text"],\n'
        '                    media_id=campaign.get("media_file_id"),\n'
        '                    media_type=campaign.get("media_type"),\n'
        '                    keyboard=kb,\n'
        '                )\n'
        '                success += 1\n'
        '            except Exception as retry_err:\n'
        '                logger.warning(f"Campaign {campaign_id} retry failed for {chat_id}: {retry_err}")\n'
        '        except TelegramForbiddenError:\n'
        '            if target in ("groups", "all"):\n'
        '                await deactivate_group(chat_id)\n'
        '        except TelegramBadRequest as e:\n'
        '            err = str(e).lower()\n'
        '            if "upgraded to a supergroup" in err:\n'
        '                await deactivate_group(chat_id)\n'
        '            elif "not enough rights" not in err:\n'
        '                logger.warning(f"Campaign {campaign_id} BadRequest for {chat_id}: {e}")\n'
        '        except Exception as e:\n'
        '            logger.warning(f"Campaign {campaign_id} broadcast failed for {chat_id}: {e}")\n'
        '        await asyncio.sleep(0.05)\n'
        '\n'
        '    await status_msg.edit_text(\n'
        '        f"✅ اكتمل نشر الحملة! تم الإرسال إلى <b>{success}</b> جهة.",\n'
        '        parse_mode=ParseMode.HTML,\n'
        '    )\n'
        '\n'
        '\n'
        'async def execute_recurring_campaign_cycle(campaign_id: int) -> None:\n'
        '    """Execute a single cycle of a recurring campaign broadcast (called by background task)."""\n'
        '    campaign = await get_campaign(campaign_id)\n'
        '    if not campaign:\n'
        '        return\n'
        '\n'
        '    bot_info = await bot.get_me()\n'
        '    kb = await build_campaign_keyboard(\n'
        '        campaign_id, campaign["button_text"], bot_info.username or BOT_USERNAME\n'
        '    )\n'
        '\n'
        '    targets: list[int] = []\n'
        '    targets += await get_all_user_ids()\n'
        '    targets += await get_active_group_ids()\n'
        '\n'
        '    for chat_id in targets:\n'
        '        try:\n'
        '            await send_media_message(\n'
        '                bot, chat_id, campaign["promo_text"],\n'
        '                media_id=campaign.get("media_file_id"),\n'
        '                media_type=campaign.get("media_type"),\n'
        '                keyboard=kb,\n'
        '            )\n'
        '        except TelegramRetryAfter as e:\n'
        '            logger.warning(f"Recurring campaign {campaign_id} rate limited for {chat_id}, sleeping {e.retry_after}s")\n'
        '            await asyncio.sleep(e.retry_after + 1)\n'
        '            try:\n'
        '                await send_media_message(\n'
        '                    bot, chat_id, campaign["promo_text"],\n'
        '                    media_id=campaign.get("media_file_id"),\n'
        '                    media_type=campaign.get("media_type"),\n'
        '                    keyboard=kb,\n'
        '                )\n'
        '            except Exception as retry_err:\n'
        '                logger.warning(f"Recurring campaign {campaign_id} retry failed for {chat_id}: {retry_err}")\n'
        '        except TelegramForbiddenError:\n'
        '            await deactivate_group(chat_id)\n'
        '        except TelegramBadRequest as e:\n'
        '            err = str(e).lower()\n'
        '            if "upgraded to a supergroup" in err:\n'
        '                await deactivate_group(chat_id)\n'
        '            elif "not enough rights" not in err:\n'
        '                logger.warning(f"Recurring campaign {campaign_id} BadRequest for {chat_id}: {e}")\n'
        '        except Exception as e:\n'
        '            logger.warning(f"Recurring campaign {campaign_id} failed for {chat_id}: {e}")\n'
        '        await asyncio.sleep(0.05)\n'
        '\n'
        '    await update_campaign_last_broadcast(campaign_id)\n'
        '    logger.info(f"Recurring campaign {campaign_id}: done.")'
    )
    if "kb = await build_campaign_keyboard(" not in content:
        if old_broadcast_funcs not in content:
            raise RuntimeError("Could not locate execute_campaign_broadcast block in services/campaign.py")
        content = content.replace(old_broadcast_funcs, new_broadcast_funcs, 1)
        applied.append("ISS-09 & ISS-16: Integrated custom buttons and TelegramRetryAfter handling in campaign broadcasts")

    return content, applied


# ── 5. services/broadcast.py (ISS-16) ────────────────────────────────────────

def patch_services_broadcast(content: str) -> tuple[str, list[str]]:
    applied = []
    old_import = "from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest"
    new_import = "from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter"
    if "TelegramRetryAfter" not in content:
        content = content.replace(old_import, new_import, 1)

    old_exec = (
        '            if sent_msg and delete_at:\n'
        '                await schedule_delete(chat_id, sent_msg.message_id, delete_at)\n'
        '\n'
        '            success += 1\n'
        '        except TelegramForbiddenError:'
    )
    new_exec = (
        '            if sent_msg and delete_at:\n'
        '                await schedule_delete(chat_id, sent_msg.message_id, delete_at)\n'
        '\n'
        '            success += 1\n'
        '        except TelegramRetryAfter as e:\n'
        '            logger.warning(f"Broadcast rate limited for {chat_id}, sleeping {e.retry_after}s")\n'
        '            await asyncio.sleep(e.retry_after + 1)\n'
        '            try:\n'
        '                sent_msg = await send_media_message(\n'
        '                    bot, chat_id, data["text"],\n'
        '                    media_id=data.get("media_id"),\n'
        '                    media_type=data.get("media_type"),\n'
        '                    is_vip=bool(data.get("is_vip")),\n'
        '                    stars=data.get("stars", 0),\n'
        '                )\n'
        '                if sent_msg and delete_at:\n'
        '                    await schedule_delete(chat_id, sent_msg.message_id, delete_at)\n'
        '                success += 1\n'
        '            except Exception as retry_err:\n'
        '                logger.warning(f"Broadcast retry failed for {chat_id}: {retry_err}")\n'
        '        except TelegramForbiddenError:'
    )
    if "Broadcast rate limited for" not in content:
        if old_exec not in content:
            raise RuntimeError("Could not locate execute_broadcast try block in services/broadcast.py")
        content = content.replace(old_exec, new_exec, 1)
        applied.append("ISS-16: Added TelegramRetryAfter handling to execute_broadcast()")

    old_rec_exec = (
        '        try:\n'
        '            await send_media_message(\n'
        '                bot, chat_id, text,\n'
        '                media_id=media_id,\n'
        '                media_type=media_type,\n'
        '                is_vip=is_vip,\n'
        '                stars=stars,\n'
        '            )\n'
        '        except TelegramForbiddenError:'
    )
    new_rec_exec = (
        '        try:\n'
        '            await send_media_message(\n'
        '                bot, chat_id, text,\n'
        '                media_id=media_id,\n'
        '                media_type=media_type,\n'
        '                is_vip=is_vip,\n'
        '                stars=stars,\n'
        '            )\n'
        '        except TelegramRetryAfter as e:\n'
        '            logger.warning(f"Recurring broadcast {rb_id} rate limited for {chat_id}, sleeping {e.retry_after}s")\n'
        '            await asyncio.sleep(e.retry_after + 1)\n'
        '            try:\n'
        '                await send_media_message(\n'
        '                    bot, chat_id, text,\n'
        '                    media_id=media_id,\n'
        '                    media_type=media_type,\n'
        '                    is_vip=is_vip,\n'
        '                    stars=stars,\n'
        '                )\n'
        '            except Exception as retry_err:\n'
        '                logger.warning(f"Recurring broadcast {rb_id} retry failed for {chat_id}: {retry_err}")\n'
        '        except TelegramForbiddenError:'
    )
    if "Recurring broadcast {rb_id} rate limited" not in content:
        if old_rec_exec not in content:
            raise RuntimeError("Could not locate execute_recurring_broadcast_cycle try block in services/broadcast.py")
        content = content.replace(old_rec_exec, new_rec_exec, 1)
        applied.append("ISS-16: Added TelegramRetryAfter handling to execute_recurring_broadcast_cycle()")

    return content, applied


# ── 6. services/user_broadcast.py (ISS-10) ───────────────────────────────────

def patch_services_user_broadcast(content: str) -> tuple[str, list[str]]:
    applied = []
    old_import = "from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError"
    new_import = "from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest"
    if "TelegramBadRequest" not in content:
        content = content.replace(old_import, new_import, 1)

    old_send_fn = (
        'async def _send_user_campaign_message(chat_id: int, text: str | None,\n'
        '                                      photo_file_id: str | None,\n'
        '                                      keyboard: InlineKeyboardMarkup | None) -> int | None:\n'
        '    """\n'
        '    Send a user campaign message (photo+caption OR text only).\n'
        '    Returns message_id on success, raises on permanent errors.\n'
        '    """\n'
        '    if photo_file_id:\n'
        '        caption = (text or "")[:MAX_CAPTION_LEN]\n'
        '        try:\n'
        '            msg = await bot.send_photo(\n'
        '                chat_id=chat_id,\n'
        '                photo=photo_file_id,\n'
        '                caption=caption or None,\n'
        '                reply_markup=keyboard,\n'
        '                parse_mode=ParseMode.HTML if caption else None,\n'
        '            )\n'
        '        except Exception:\n'
        '            msg = await bot.send_photo(\n'
        '                chat_id=chat_id,\n'
        '                photo=photo_file_id,\n'
        '                caption=caption or None,\n'
        '                reply_markup=keyboard,\n'
        '            )\n'
        '    else:\n'
        '        body = (text or "")[:MAX_TEXT_LEN]\n'
        '        try:\n'
        '            msg = await bot.send_message(\n'
        '                chat_id=chat_id,\n'
        '                text=body,\n'
        '                reply_markup=keyboard,\n'
        '                parse_mode=ParseMode.HTML,\n'
        '            )\n'
        '        except Exception:\n'
        '            msg = await bot.send_message(\n'
        '                chat_id=chat_id,\n'
        '                text=body,\n'
        '                reply_markup=keyboard,\n'
        '            )\n'
        '    return msg.message_id'
    )
    new_send_fn = (
        'async def _send_user_campaign_message(chat_id: int, text: str | None,\n'
        '                                      photo_file_id: str | None,\n'
        '                                      keyboard: InlineKeyboardMarkup | None) -> int | None:\n'
        '    """\n'
        '    Send a user campaign message (photo+caption OR text only).\n'
        '    Retries without HTML parse_mode ONLY on entity parse errors.\n'
        '    """\n'
        '    if photo_file_id:\n'
        '        caption = (text or "")[:MAX_CAPTION_LEN]\n'
        '        try:\n'
        '            msg = await bot.send_photo(\n'
        '                chat_id=chat_id,\n'
        '                photo=photo_file_id,\n'
        '                caption=caption or None,\n'
        '                reply_markup=keyboard,\n'
        '                parse_mode=ParseMode.HTML if caption else None,\n'
        '            )\n'
        '        except TelegramBadRequest as e:\n'
        '            if "can\'t parse entities" in str(e).lower():\n'
        '                msg = await bot.send_photo(\n'
        '                    chat_id=chat_id,\n'
        '                    photo=photo_file_id,\n'
        '                    caption=caption or None,\n'
        '                    reply_markup=keyboard,\n'
        '                )\n'
        '            else:\n'
        '                raise\n'
        '    else:\n'
        '        body = (text or "")[:MAX_TEXT_LEN]\n'
        '        try:\n'
        '            msg = await bot.send_message(\n'
        '                chat_id=chat_id,\n'
        '                text=body,\n'
        '                reply_markup=keyboard,\n'
        '                parse_mode=ParseMode.HTML,\n'
        '            )\n'
        '        except TelegramBadRequest as e:\n'
        '            if "can\'t parse entities" in str(e).lower():\n'
        '                msg = await bot.send_message(\n'
        '                    chat_id=chat_id,\n'
        '                    text=body,\n'
        '                    reply_markup=keyboard,\n'
        '                )\n'
        '            else:\n'
        '                raise\n'
        '    return msg.message_id'
    )
    if "Retries without HTML parse_mode ONLY on entity parse errors." not in content:
        if old_send_fn not in content:
            raise RuntimeError("Could not locate _send_user_campaign_message in services/user_broadcast.py")
        content = content.replace(old_send_fn, new_send_fn, 1)
        applied.append("ISS-10: Restricted _send_user_campaign_message fallback retry strictly to HTML parse errors")

    return content, applied


# ── 7. handlers/admin/campaigns.py (ISS-07, ISS-09) ──────────────────────────

def patch_handlers_admin_campaigns(content: str) -> tuple[str, list[str]]:
    applied = []
    content = ensure_import_html(content)

    old_srv_import = "from services.campaign import execute_campaign_broadcast"
    new_srv_import = "from services.campaign import execute_campaign_broadcast, build_campaign_keyboard"
    if "build_campaign_keyboard" not in content:
        content = content.replace(old_srv_import, new_srv_import, 1)

    old_summary = (
        '    text = (\n'
        '        f"📋 <b>ملخص الحملة:</b>\\n\\n"\n'
        '        f"📌 الاسم: {data[\'name\']}\\n"\n'
        '        f"📝 نص الإعلان: {data[\'promo_text\'][:50]}...\\n"\n'
        '        f"🖼 وسائط: {\'نعم\' if data.get(\'media_file_id\') else \'لا\'}\\n"\n'
        '        f"🔘 زر CTA: {data[\'button_text\']}\\n"'
    )
    new_summary = (
        '    text = (\n'
        '        f"📋 <b>ملخص الحملة:</b>\\n\\n"\n'
        '        f"📌 الاسم: {html.escape(str(data[\'name\']))}\\n"\n'
        '        f"📝 نص الإعلان: {html.escape(str(data[\'promo_text\'][:50]))}...\\n"\n'
        '        f"🖼 وسائط: {\'نعم\' if data.get(\'media_file_id\') else \'لا\'}\\n"\n'
        '        f"🔘 زر CTA: {html.escape(str(data[\'button_text\']))}\\n"'
    )
    if "html.escape(str(data['name']))" not in content:
        if old_summary not in content:
            raise RuntimeError("Could not locate _show_confirm text block in handlers/admin/campaigns.py")
        content = content.replace(old_summary, new_summary, 1)
        content = content.replace(
            'f"✅ <b>تم إنشاء الحملة بنجاح!</b>\\n\\nالمعرف: #{campaign_id}\\nالاسم: {data[\'name\']}"',
            'f"✅ <b>تم إنشاء الحملة بنجاح!</b>\\n\\nالمعرف: #{campaign_id}\\nالاسم: {html.escape(str(data[\'name\']))}"',
            1,
        )
        content = content.replace(
            'f"🎯 <b>الحملة #{campaign_id}: {campaign[\'name\']}</b>\\n\\n"',
            'f"🎯 <b>الحملة #{campaign_id}: {html.escape(str(campaign[\'name\']))}</b>\\n\\n"',
            1,
        )
        applied.append("ISS-07: Escaped campaign name and summary fields in handlers/admin/campaigns.py")

    old_test_kb = (
        '    bot_info = await bot.get_me()\n'
        '    cta = InlineKeyboardButton(text=campaign["button_text"], url=f"https://t.me/{bot_info.username}?start=camp_{cid}")\n'
        '    kb = InlineKeyboardMarkup(inline_keyboard=[[cta]])'
    )
    new_test_kb = (
        '    bot_info = await bot.get_me()\n'
        '    kb = await build_campaign_keyboard(cid, campaign["button_text"], bot_info.username or BOT_USERNAME)'
    )
    if old_test_kb in content:
        content = content.replace(old_test_kb, new_test_kb)
        applied.append("ISS-09: Included custom campaign buttons in cb_cmp_test and cb_cmp_test_group")

    return content, applied


# ── 8. handlers/admin/promo_settings.py & welcome_settings.py (ISS-17) ───────

def patch_handlers_admin_promo_settings(content: str) -> tuple[str, list[str]]:
    applied = []
    old_preview_paid = (
        'await bot.send_paid_media(chat_id=callback.from_user.id, star_count=stars, media=media_payload, caption=f"👁 معاينة:\\n\\n{promo_text_formatted}", parse_mode=ParseMode.HTML)'
    )
    new_preview_paid = (
        'await bot.send_paid_media(chat_id=callback.from_user.id, star_count=stars, media=media_payload, caption=f"👁 معاينة:\\n\\n{promo_text_formatted}", parse_mode=ParseMode.HTML, reply_markup=keyboard)'
    )
    if old_preview_paid in content:
        content = content.replace(old_preview_paid, new_preview_paid, 1)
        applied.append("ISS-17: Passed reply_markup=keyboard in VIP promo preview")

    old_set_promo = '    await set_setting("promo_text", message.text)'
    new_set_promo = '    await set_setting("promo_text", message.html_text or message.text)'
    if old_set_promo in content:
        content = content.replace(old_set_promo, new_set_promo, 1)
        applied.append("ISS-17: Preserved message.html_text in process_promo_text()")

    return content, applied


def patch_handlers_admin_welcome_settings(content: str) -> tuple[str, list[str]]:
    applied = []
    old_set_start = '    await set_setting("start_message", message.text)'
    new_set_start = '    await set_setting("start_message", message.html_text or message.text)'
    if old_set_start in content:
        content = content.replace(old_set_start, new_set_start, 1)
        applied.append("ISS-17: Preserved message.html_text in process_start_msg()")
    return content, applied


# ── 9. Remaining Handlers HTML Escaping (ISS-07 & ISS-17) ────────────────────

def patch_handlers_admin_stats(content: str) -> tuple[str, list[str]]:
    applied = []
    content = ensure_import_html(content)
    old_line = '            text += f"{status_icon} <b>{title or \'بدون اسم\'}</b>\\n  └ <code>{chat_id}</code>\\n"'
    new_line = '            text += f"{status_icon} <b>{html.escape(str(title or \'بدون اسم\'))}</b>\\n  └ <code>{chat_id}</code>\\n"'
    if old_line in content:
        content = content.replace(old_line, new_line, 1)
        applied.append("ISS-07: Escaped group title in handlers/admin/stats.py")
    return content, applied


def patch_handlers_admin_user_management(content: str) -> tuple[str, list[str]]:
    applied = []
    content = ensure_import_html(content)
    old_block = (
        '        label = (title or f"{chat_id}")[:25]\n'
        '        status_str = "🟢" if status == "active" else "🔴"\n'
        '        text += f"{status_str} {icon} <b>{label}</b> (owner: {owner_id or \'?\'})\\n"'
    )
    new_block = (
        '        label = (title or f"{chat_id}")[:25]\n'
        '        safe_label = html.escape(label)\n'
        '        status_str = "🟢" if status == "active" else "🔴"\n'
        '        text += f"{status_str} {icon} <b>{safe_label}</b> (owner: {owner_id or \'?\'})\\n"'
    )
    if "safe_label = html.escape(label)" not in content:
        if old_block not in content:
            raise RuntimeError("Could not locate group label block in handlers/admin/user_management.py")
        content = content.replace(old_block, new_block, 1)
        applied.append("ISS-07: Escaped group title in handlers/admin/user_management.py")
    return content, applied


def patch_handlers_admin_button_manager(content: str) -> tuple[str, list[str]]:
    applied = []
    content = ensure_import_html(content)
    old_line = '            text += f"{icon} <b>{btn[\'label\']}</b>\\n  └ {btn[\'url\']}\\n"'
    new_line = '            text += f"{icon} <b>{html.escape(str(btn[\'label\']))}</b>\\n  └ {html.escape(str(btn[\'url\']))}\\n"'
    if old_line in content:
        content = content.replace(old_line, new_line, 1)
        content = content.replace(
            'await message.answer(f"✅ تم إضافة الزر <b>{label}</b> بنجاح!", parse_mode=ParseMode.HTML)',
            'await message.answer(f"✅ تم إضافة الزر <b>{html.escape(str(label))}</b> بنجاح!", parse_mode=ParseMode.HTML)',
            1,
        )
        applied.append("ISS-07: Escaped button label and URL in handlers/admin/button_manager.py")
    return content, applied


def patch_handlers_admin_recurring(content: str) -> tuple[str, list[str]]:
    applied = []
    content = ensure_import_html(content)
    old_preview = (
        '            preview = (rb_text[:30] + "...") if rb_text and len(rb_text) > 30 else (rb_text or "")\n'
        '            text += f"{status_icon} #{rb_id} | {target_map.get(target, target)} | كل {repeat_hours}h | {preview}\\n"'
    )
    new_preview = (
        '            raw_preview = (rb_text[:30] + "...") if rb_text and len(rb_text) > 30 else (rb_text or "")\n'
        '            preview = html.escape(raw_preview)\n'
        '            text += f"{status_icon} #{rb_id} | {target_map.get(target, target)} | كل {repeat_hours}h | {preview}\\n"'
    )
    if "preview = html.escape(raw_preview)" not in content:
        if old_preview not in content:
            raise RuntimeError("Could not locate preview line in handlers/admin/recurring.py")
        content = content.replace(old_preview, new_preview, 1)
        content = content.replace(
            'f"النص الحالي:\\n<blockquote>{(rb[\'text\'] or \'\')[:200]}</blockquote>\\n\\n"',
            'f"النص الحالي:\\n<blockquote>{html.escape((rb[\'text\'] or \'\')[:200])}</blockquote>\\n\\n"',
            1,
        )
        applied.append("ISS-07: Escaped recurring broadcast preview text in handlers/admin/recurring.py")
    return content, applied


def patch_handlers_user_my_groups(content: str) -> tuple[str, list[str]]:
    applied = []
    content = ensure_import_html(content)
    old_loop = (
        '    for chat_id, title, health in groups:\n'
        '        icon = HEALTH_ICONS.get(health or "unknown", "❓")\n'
        '        label = (title or f"Group {chat_id}")[:30]\n'
        '        text += f"{icon} <b>{label}</b>\\n"'
    )
    new_loop = (
        '    for chat_id, title, health in groups:\n'
        '        icon = HEALTH_ICONS.get(health or "unknown", "❓")\n'
        '        label = html.escape((title or f"Group {chat_id}")[:30])\n'
        '        text += f"{icon} <b>{label}</b>\\n"'
    )
    if "label = html.escape((title or" not in content:
        if old_loop not in content:
            raise RuntimeError("Could not locate group list loop in handlers/user/my_groups.py")
        content = content.replace(old_loop, new_loop, 1)
        applied.append("ISS-07: Escaped group title in handlers/user/my_groups.py")
    return content, applied


def patch_handlers_user_my_campaign(content: str) -> tuple[str, list[str]]:
    applied = []
    content = ensure_import_html(content)

    # ISS-17: Preserve message.html_text in process_ucw_text
    old_ucw_text = (
        '    skip = text == "/skip"\n'
        '    await state.update_data(text=None if skip else text)'
    )
    new_ucw_text = (
        '    skip = text == "/skip"\n'
        '    await state.update_data(text=None if skip else (message.html_text or text))'
    )
    if old_ucw_text in content:
        content = content.replace(old_ucw_text, new_ucw_text, 1)
        applied.append("ISS-17: Preserved message.html_text in process_ucw_text()")

    # ISS-07: Escape group title in _ask_groups and text_preview in process_ucw_mode
    old_ask_groups = (
        '    for i, (chat_id, title, health) in enumerate(groups, 1):\n'
        '        text += f"{i}. {title or chat_id}\\n"'
    )
    new_ask_groups = (
        '    for i, (chat_id, title, health) in enumerate(groups, 1):\n'
        '        text += f"{i}. {html.escape(str(title or chat_id))}\\n"'
    )
    if old_ask_groups in content:
        content = content.replace(old_ask_groups, new_ask_groups, 1)
        applied.append("ISS-07: Escaped group titles in _ask_groups()")

    old_preview = '    text_preview = (data.get("text") or "")[:100]'
    new_preview = '    text_preview = html.escape((data.get("text") or "")[:100])'
    if old_preview in content:
        content = content.replace(old_preview, new_preview, 1)
        applied.append("ISS-07: Escaped text_preview in process_ucw_mode()")

    return content, applied


def run_repair(dry_run: bool = False) -> int:
    print("=" * 65)
    print(f"Deploy Links Bot — Phase 2 Repair ({'DRY-RUN' if dry_run else 'APPLY'})")
    print("=" * 65)

    for rel_path in TARGET_FILES:
        if not (PROJECT_ROOT / rel_path).exists():
            print(f"[ERROR] Missing required file: {rel_path}")
            return 1

    create_backups(dry_run=dry_run)

    patchers = [
        ("handlers/start.py", patch_handlers_start),
        ("services/media.py", patch_services_media),
        ("models/campaigns.py", patch_models_campaigns),
        ("services/campaign.py", patch_services_campaign),
        ("services/broadcast.py", patch_services_broadcast),
        ("services/user_broadcast.py", patch_services_user_broadcast),
        ("handlers/admin/campaigns.py", patch_handlers_admin_campaigns),
        ("handlers/admin/promo_settings.py", patch_handlers_admin_promo_settings),
        ("handlers/admin/welcome_settings.py", patch_handlers_admin_welcome_settings),
        ("handlers/admin/stats.py", patch_handlers_admin_stats),
        ("handlers/admin/user_management.py", patch_handlers_admin_user_management),
        ("handlers/admin/button_manager.py", patch_handlers_admin_button_manager),
        ("handlers/admin/recurring.py", patch_handlers_admin_recurring),
        ("handlers/user/my_groups.py", patch_handlers_user_my_groups),
        ("handlers/user/my_campaign.py", patch_handlers_user_my_campaign),
    ]

    updated_contents: dict[str, str] = {}
    all_changes: list[str] = []

    for rel_path, patch_fn in patchers:
        raw = (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")
        new_code, changes = patch_fn(raw)
        verify_python_syntax(new_code, rel_path)
        updated_contents[rel_path] = new_code
        all_changes.extend(changes)

    if not dry_run:
        for rel_path, new_code in updated_contents.items():
            (PROJECT_ROOT / rel_path).write_text(new_code, encoding="utf-8")

    if all_changes:
        print("\nChanges applied:")
        for ch in all_changes:
            print(f"  [OK] {ch}")
    else:
        print("\n[INFO] All Phase 2 fixes are already applied (idempotent check passed).")

    print("\n[SUCCESS] Phase 2 repair completed cleanly.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 2 Repair Script")
    parser.add_argument("--dry-run", action="store_true", help="Simulate changes without modifying files")
    parser.add_argument("--rollback", action="store_true", help="Restore files from Phase 2 backup")
    args = parser.parse_args()

    if args.rollback:
        sys.exit(rollback())
    sys.exit(run_repair(dry_run=args.dry_run))
