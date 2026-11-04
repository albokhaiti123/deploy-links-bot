"""
User campaign handler — campaign wizard, management, and stats.
Enforces feature switch, quota, ownership, and content-type restrictions.
"""

import json
import asyncio

from aiogram import Router, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext

from core.config import ADMIN_ID
from models.groups import get_user_active_groups
from models.user_campaigns import (
    get_current_campaign, get_quota, update_campaign_status,
    get_delivery_stats, _today,
)
from services.user_broadcast import (
    create_user_campaign, execute_user_campaign,
    _feature_enabled, validate_buttons,
)
from states.user_states import UserCampaignWizard

router = Router(name="user_my_campaign")


# ── Feature gate helper ──────────────────────────────────────────────────────

async def _check_feature(callback: types.CallbackQuery) -> bool:
    if not await _feature_enabled():
        await callback.message.edit_text(
            "⛔ The campaign feature is temporarily disabled by the administrator.\n"
            "Please try again later.",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🔙 Back", callback_data="user_menu")]
            ])
        )
        try:
            await callback.answer()
        except Exception:
            pass
        return False
    return True


# ── User menu ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "user_menu")
async def cb_user_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    if user_id == ADMIN_ID:
        await callback.answer()
        return

    groups = await get_user_active_groups(user_id)
    quota = await get_quota(user_id, _today())
    current = await get_current_campaign(user_id)

    status_icon = "🟢" if current and current["status"] == "active" else \
                  "🔴" if not current else "⏸"

    text = (
        f"👤 <b>User Dashboard</b>\n\n"
        f"📱 Groups: <b>{len(groups)}</b>\n"
        f"📋 Campaigns today: <b>{quota}/2</b>\n"
        f"📢 Current campaign: <b>{'None' if not current else current.get('status','?')}</b> {status_icon if current else ''}"
    )
    buttons = [
        [types.InlineKeyboardButton(text=f"📱 My Groups ({len(groups)})", callback_data="user_my_groups")],
    ]
    if quota < 2:
        buttons.append([types.InlineKeyboardButton(text="➕ Create Campaign", callback_data="user_create_campaign")])
    else:
        buttons.append([types.InlineKeyboardButton(text="🚫 Daily Limit Reached (2/2)", callback_data="user_quota_info")])

    if current:
        buttons.append([types.InlineKeyboardButton(text="📋 My Campaign", callback_data="user_view_campaign")])

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons),
                                     parse_mode=ParseMode.HTML)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "user_quota_info")
async def cb_user_quota_info(callback: types.CallbackQuery):
    await callback.answer("You've used both campaigns for today. Try again tomorrow.", show_alert=True)


# ── View current campaign ────────────────────────────────────────────────────

@router.callback_query(F.data == "user_view_campaign")
async def cb_user_view_campaign(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    current = await get_current_campaign(user_id)
    if not current:
        await callback.answer("No active campaign.", show_alert=True)
        return

    stats = await get_delivery_stats(current["id"])
    sent = stats.get("sent", 0)
    failed = stats.get("failed", 0)
    targets = json.loads(current["target_groups_json"] or "[]")

    text = (
        f"📋 <b>My Campaign</b>\n\n"
        f"Status: <b>{current['status']}</b>\n"
        f"Mode: <b>{current['mode']}</b>\n"
        f"Target groups: <b>{len(targets)}</b>\n"
        f"Sent: <b>{sent}</b> | Failed: <b>{failed}</b>\n"
    )
    if current["mode"] == "recurring":
        text += f"Interval: <b>{current['repeat_hours']}h</b>\n"
        if current["next_run_at"]:
            text += f"Next run: <b>{str(current['next_run_at'])[:16]}</b>\n"

    buttons = []
    if current["status"] == "active":
        buttons.append([types.InlineKeyboardButton(text="⏸ Pause", callback_data=f"user_pause_campaign_{current['id']}")])
    elif current["status"] == "paused":
        buttons.append([types.InlineKeyboardButton(text="▶️ Resume", callback_data=f"user_resume_campaign_{current['id']}")])

    if current["status"] in ("active", "paused") and current["mode"] == "immediate":
        buttons.append([types.InlineKeyboardButton(text="📢 Send Now", callback_data=f"user_send_now_{current['id']}")])

    buttons.append([types.InlineKeyboardButton(text="🗑 Delete Campaign", callback_data=f"user_delete_campaign_{current['id']}")])
    buttons.append([types.InlineKeyboardButton(text="🔙 Back", callback_data="user_menu")])

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons),
                                     parse_mode=ParseMode.HTML)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("user_pause_campaign_"))
async def cb_user_pause_campaign(callback: types.CallbackQuery):
    cid = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    current = await get_current_campaign(user_id)
    if not current or current["id"] != cid:
        await callback.answer("Campaign not found.", show_alert=True)
        return
    await update_campaign_status(cid, "paused")
    await callback.answer("⏸ Campaign paused.")
    await cb_user_view_campaign(callback)


@router.callback_query(F.data.startswith("user_resume_campaign_"))
async def cb_user_resume_campaign(callback: types.CallbackQuery):
    cid = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    if not await _check_feature(callback):
        return
    current = await get_current_campaign(user_id)
    if not current or current["id"] != cid:
        await callback.answer("Campaign not found.", show_alert=True)
        return
    await update_campaign_status(cid, "active")
    await callback.answer("▶️ Campaign resumed.")
    await cb_user_view_campaign(callback)


@router.callback_query(F.data.startswith("user_delete_campaign_"))
async def cb_user_delete_campaign(callback: types.CallbackQuery):
    cid = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    current = await get_current_campaign(user_id)
    if not current or current["id"] != cid:
        await callback.answer("Campaign not found.", show_alert=True)
        return
    await update_campaign_status(cid, "deleted")
    await callback.message.edit_text(
        "🗑 Campaign deleted. Note: messages already sent are not recalled.\n"
        "Your daily quota is NOT restored.",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔙 Back", callback_data="user_menu")]
        ])
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("user_send_now_"))
async def cb_user_send_now(callback: types.CallbackQuery):
    cid = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    if not await _check_feature(callback):
        return
    current = await get_current_campaign(user_id)
    if not current or current["id"] != cid:
        await callback.answer("Campaign not found.", show_alert=True)
        return
    await callback.message.edit_text("🚀 Sending campaign... please wait.")
    try:
        await callback.answer()
    except Exception:
        pass
    asyncio.create_task(execute_user_campaign(cid))


# ── Campaign creation wizard ─────────────────────────────────────────────────

@router.callback_query(F.data == "user_create_campaign")
async def cb_user_create_campaign(callback: types.CallbackQuery, state: FSMContext):
    if not await _check_feature(callback):
        return
    user_id = callback.from_user.id
    if user_id == ADMIN_ID:
        await callback.answer()
        return

    # Quota pre-check (non-binding; atomic check is in service)
    quota = await get_quota(user_id, _today())
    if quota >= 2:
        await callback.answer("Daily limit reached (2/2). Try again tomorrow.", show_alert=True)
        return

    groups = await get_user_active_groups(user_id)
    if not groups:
        await callback.answer("You have no registered groups. Add this bot to a group first.", show_alert=True)
        return

    current = await get_current_campaign(user_id)
    replace_msg = ""
    if current and current["status"] in ("active", "paused"):
        replace_msg = "\n\n⚠️ <b>Note:</b> Your existing campaign will be <b>replaced</b>."

    await callback.message.edit_text(
        f"📢 <b>Create Campaign — Step 1/5</b>\n\n"
        f"Send the message text (HTML formatting supported).\n"
        f"Or send /skip to create a photo-only campaign.{replace_msg}",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ Cancel", callback_data="user_menu")]
        ]),
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(UserCampaignWizard.text)
    await state.update_data(replace=bool(current))
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(UserCampaignWizard.text)
async def process_ucw_text(message: types.Message, state: FSMContext):
    text = message.text
    if text == "/cancel":
        await state.clear()
        await message.answer("❌ Campaign creation cancelled. No quota consumed.")
        return

    skip = text == "/skip"
    await state.update_data(text=None if skip else text)
    await message.answer(
        "📸 <b>Step 2/5 — Photo (optional)</b>\n\n"
        "Send a photo to include with the campaign, or /skip for text-only.",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(UserCampaignWizard.photo)


@router.message(UserCampaignWizard.photo, F.photo)
async def process_ucw_photo(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=file_id)
    await _ask_buttons(message, state)


@router.message(UserCampaignWizard.photo, F.text)
async def process_ucw_photo_text(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Campaign creation cancelled.")
        return
    await state.update_data(photo_file_id=None)
    await _ask_buttons(message, state)


async def _ask_buttons(message: types.Message, state: FSMContext):
    await message.answer(
        "🔘 <b>Step 3/5 — Inline Buttons (optional)</b>\n\n"
        "Send buttons in this format (one row per line):\n"
        "<code>Button Label | https://example.com</code>\n\n"
        "Or /skip for no buttons.",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(UserCampaignWizard.buttons)


@router.message(UserCampaignWizard.buttons)
async def process_ucw_buttons(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Campaign creation cancelled.")
        return

    buttons_json = None
    if message.text and message.text != "/skip":
        # Parse "Label | URL" lines into [[{"label":...,"url":...}]]
        rows = []
        for line in message.text.strip().splitlines():
            parts = line.split("|", 1)
            if len(parts) == 2:
                rows.append([{"label": parts[0].strip(), "url": parts[1].strip()}])
        if rows:
            buttons_json = json.dumps(rows)
            ok, err = validate_buttons(buttons_json)
            if not ok:
                await message.answer(f"❌ Invalid buttons: {err}\nTry again or /skip.")
                return

    await state.update_data(buttons_json=buttons_json)
    await _ask_groups(message, state)


async def _ask_groups(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    groups = await get_user_active_groups(user_id)

    if not groups:
        await state.clear()
        await message.answer("❌ No groups available. Add this bot to your groups first.")
        return

    text = "👥 <b>Step 4/5 — Select Target Groups</b>\n\nSend group numbers separated by commas (e.g. 1,2,3):\n\n"
    for i, (chat_id, title, health) in enumerate(groups, 1):
        text += f"{i}. {title or chat_id}\n"
    text += "\nOr send 'all' to target all your groups."

    await state.update_data(available_groups=[(g[0], g[1]) for g in groups])
    await message.answer(text, parse_mode=ParseMode.HTML)
    await state.set_state(UserCampaignWizard.groups)


@router.message(UserCampaignWizard.groups)
async def process_ucw_groups(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Campaign creation cancelled.")
        return

    data = await state.get_data()
    available = data.get("available_groups", [])

    if message.text.strip().lower() == "all":
        selected = [g[0] for g in available]
    else:
        try:
            indices = [int(x.strip()) - 1 for x in message.text.split(",")]
            selected = [available[i][0] for i in indices if 0 <= i < len(available)]
        except (ValueError, IndexError):
            await message.answer("❌ Invalid selection. Enter group numbers like: 1,2,3")
            return

    if not selected:
        await message.answer("❌ No valid groups selected. Try again.")
        return

    await state.update_data(target_groups=selected)
    await message.answer(
        "⏱ <b>Step 5/5 — Campaign Mode</b>\n\n"
        "Send <b>now</b> for immediate send.\n"
        "Or send a number (hours) for recurring (minimum 6): e.g. <code>6</code> or <code>24</code>",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(UserCampaignWizard.mode)


@router.message(UserCampaignWizard.mode)
async def process_ucw_mode(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Campaign creation cancelled.")
        return

    txt = message.text.strip().lower()
    if txt == "now":
        mode = "immediate"
        repeat_hours = 0
    else:
        try:
            repeat_hours = int(txt)
            if repeat_hours < 6:
                await message.answer("❌ Minimum recurring interval is 6 hours. Enter 6 or more.")
                return
            mode = "recurring"
        except ValueError:
            await message.answer("❌ Enter 'now' for immediate or a number of hours (min 6).")
            return

    await state.update_data(mode=mode, repeat_hours=repeat_hours)
    data = await state.get_data()

    # Show confirmation
    text_preview = (data.get("text") or "")[:100]
    has_photo = bool(data.get("photo_file_id"))
    has_buttons = bool(data.get("buttons_json"))
    targets = data.get("target_groups", [])
    mode_str = "Immediate" if mode == "immediate" else f"Every {repeat_hours}h"

    confirm_text = (
        f"✅ <b>Confirm Campaign</b>\n\n"
        f"Text: {text_preview or '—'}\n"
        f"Photo: {'Yes' if has_photo else 'No'}\n"
        f"Buttons: {'Yes' if has_buttons else 'No'}\n"
        f"Target groups: {len(targets)}\n"
        f"Mode: {mode_str}\n\n"
        f"<b>This will count as one of your 2 daily campaigns.</b>\n"
        f"{'Your existing campaign will be replaced.' if data.get('replace') else ''}"
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Confirm & Create", callback_data="user_wizard_confirm")],
        [types.InlineKeyboardButton(text="❌ Cancel", callback_data="user_wizard_cancel")],
    ])
    await message.answer(confirm_text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await state.set_state(UserCampaignWizard.confirm)


@router.callback_query(UserCampaignWizard.confirm, F.data == "user_wizard_confirm")
async def cb_user_wizard_confirm(callback: types.CallbackQuery, state: FSMContext):
    if not await _feature_enabled():
        await callback.message.edit_text("⛔ Feature disabled by administrator.")
        await state.clear()
        try:
            await callback.answer()
        except Exception:
            pass
        return

    data = await state.get_data()
    await state.clear()
    user_id = callback.from_user.id

    campaign_id, error = await create_user_campaign(
        user_id=user_id,
        text=data.get("text"),
        photo_file_id=data.get("photo_file_id"),
        buttons_json=data.get("buttons_json"),
        target_chat_ids=data.get("target_groups", []),
        mode=data.get("mode", "immediate"),
        repeat_hours=data.get("repeat_hours", 0),
    )

    if error:
        await callback.message.edit_text(
            f"❌ Failed to create campaign: {error}",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🔙 Back", callback_data="user_menu")]
            ])
        )
    else:
        mode = data.get("mode", "immediate")
        await callback.message.edit_text(
            f"✅ <b>Campaign created!</b> (ID: #{campaign_id})\n\n"
            f"{'Sending now...' if mode == 'immediate' else 'Scheduled for recurring delivery.'}",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="📋 View Campaign", callback_data="user_view_campaign")],
                [types.InlineKeyboardButton(text="🔙 Dashboard", callback_data="user_menu")],
            ]),
            parse_mode=ParseMode.HTML,
        )
        if mode == "immediate":
            asyncio.create_task(execute_user_campaign(campaign_id))

    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "user_wizard_cancel")
async def cb_user_wizard_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Campaign creation cancelled. No quota consumed.",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔙 Back", callback_data="user_menu")]
        ])
    )
    try:
        await callback.answer()
    except Exception:
        pass
