"""
User campaign handler — Phase 7 Interactive Campaign Wizard + management.
Enforces feature switch, quota, ownership, and content-type restrictions.
"""

import asyncio
import html
import json

from aiogram import Router, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext

from core.config import ADMIN_ID
from core.i18n import get_lang, t as i18n_t
from models.groups import get_user_active_groups
from models.user_campaigns import (
    get_current_campaign, get_quota, update_campaign_status,
    resume_user_campaign, get_delivery_stats, _today,
)
from services.user_broadcast import (
    create_user_campaign, execute_user_campaign,
    _feature_enabled, _get_generation, validate_buttons,
)
from states.user_states import UserCampaignWizard

router = Router(name="user_my_campaign")

_P7_MAX_BUTTONS = 3


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


# ── Language helper ──────────────────────────────────────────────────────────

async def _p7_resolve_lang(event) -> str:
    """Resolve user language; falls back to 'en'."""
    from core.i18n import get_lang, get_context_lang
    user = getattr(event, "from_user", None)
    uid = getattr(user, "id", None)
    if isinstance(uid, int):
        return await get_lang(uid, getattr(user, "language_code", None))
    ctx = get_context_lang()
    return ctx if ctx in ("ar", "en") else "en"


# ── Safe edit/answer helper ──────────────────────────────────────────────────

async def _p7_safe_edit_or_answer(
    message: types.Message,
    text: str,
    kb: types.InlineKeyboardMarkup | None = None,
    prefer_edit: bool = True,
) -> None:
    if prefer_edit:
        try:
            await message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


# ── Button validation ────────────────────────────────────────────────────────

def _p7_validate_single_button(label: str, url: str) -> tuple[bool, str | None]:
    label = (label or "").strip()
    url = (url or "").strip()
    if not label or len(label) > 64:
        return False, "label"
    if (
        not url
        or " " in url
        or len(url) > 256
        or not url.startswith(("https://", "http://", "tg://"))
    ):
        return False, "url"
    # Match validate_buttons() schema: list of rows containing {"label": ..., "url": ...}
    service_payload = [[{"label": label, "url": url}]]
    try:
        res = validate_buttons(json.dumps(service_payload))
        if res is False or (isinstance(res, tuple) and len(res) >= 2 and res[0] is False):
            return False, "url"
    except Exception:
        pass
    return True, None


def _p7_build_preview_keyboard(buttons_list: list[dict]) -> types.InlineKeyboardMarkup | None:
    if not buttons_list:
        return None
    rows = [
        [types.InlineKeyboardButton(text=b["text"], url=b["url"])]
        for b in buttons_list
        if b.get("text") and b.get("url")
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


# ── User menu ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "user_menu")
async def cb_user_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    if user_id == ADMIN_ID:
        await callback.answer()
        return

    if not await _feature_enabled():
        await callback.answer(
            "الخدمة متوقفة مؤقتاً لأعمال الصيانة، يرجى المحاولة لاحقاً.",
            show_alert=True,
        )
        return

    lang = await get_lang(user_id)
    groups = await get_user_active_groups(user_id)
    quota = await get_quota(user_id, _today())
    current = await get_current_campaign(user_id)

    status_icon = ("🟢" if current and current["status"] == "active" else
                   "🔴" if not current else "⏸")

    if lang == "ar":
        text = (
            f"👤 <b>لوحة تحكم المستخدم</b>\n\n"
            f"📱 المجموعات: <b>{len(groups)}</b>\n"
            f"📋 حملات اليوم: <b>{quota}/5</b>\n"
            f"📢 الحملة الحالية: <b>{'لا يوجد' if not current else current.get('status', '?')}</b> "
            f"{status_icon if current else ''}"
        )
        btn_groups = f"📱 مجموعاتي ({len(groups)})"
        btn_referral = "🔗 رابط الإحالة الخاص بي"
        btn_create = "➕ إنشاء حملة"
        btn_quota = "🚫 تم الوصول للحد اليومي (5/5)"
        btn_campaign = "📋 حملتي الحالية"
        btn_stats = "📊 إحصائياتي"
        btn_history = "🗂 سجل حملاتي"
        btn_lang = "🌐 اللغة / Language"
    else:
        text = (
            f"👤 <b>User Dashboard</b>\n\n"
            f"📱 Groups: <b>{len(groups)}</b>\n"
            f"📋 Campaigns today: <b>{quota}/5</b>\n"
            f"📢 Current campaign: <b>{'None' if not current else current.get('status', '?')}</b> "
            f"{status_icon if current else ''}"
        )
        btn_groups = f"📱 My Groups ({len(groups)})"
        btn_referral = "🔗 My Referral Link"
        btn_create = "➕ Create Campaign"
        btn_quota = "🚫 Daily Limit Reached (5/5)"
        btn_campaign = "📋 My Campaign"
        btn_stats = "📊 My Stats"
        btn_history = "🗂 Campaign History"
        btn_lang = "🌐 اللغة / Language"

    buttons = [
        [types.InlineKeyboardButton(text=btn_groups, callback_data="user_my_groups")],
        [types.InlineKeyboardButton(text=btn_referral, callback_data="user_my_referral")],
    ]
    if quota < 5:
        buttons.append([types.InlineKeyboardButton(text=btn_create, callback_data="user_create_campaign")])
    else:
        buttons.append([types.InlineKeyboardButton(text=btn_quota, callback_data="user_quota_info")])

    if current:
        buttons.append([types.InlineKeyboardButton(text=btn_campaign, callback_data="user_view_campaign")])

    buttons.append([types.InlineKeyboardButton(text=btn_stats, callback_data="user_my_stats")])
    buttons.append([types.InlineKeyboardButton(text=btn_history, callback_data="user_campaign_history")])
    buttons.append([types.InlineKeyboardButton(text=btn_lang, callback_data="lang_menu_user")])

    kb = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "user_quota_info")
async def cb_user_quota_info(callback: types.CallbackQuery):
    await callback.answer("You've used all 5 campaigns for today. Try again tomorrow.", show_alert=True)


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
    elif current["status"] in ("paused", "suspended_admin"):
        buttons.append([types.InlineKeyboardButton(text="▶️ Resume", callback_data=f"user_resume_campaign_{current['id']}")])

    if current["status"] == "active" and current["mode"] == "immediate":
        buttons.append([types.InlineKeyboardButton(text="📢 Send Now", callback_data=f"user_send_now_{current['id']}")])

    # Phase 8 Pro buttons
    cid_p8 = current["id"]
    buttons.append([
        types.InlineKeyboardButton(text="👁 Test DM",         callback_data=f"user_test_campaign_{cid_p8}"),
        types.InlineKeyboardButton(text="📊 Last Report",     callback_data=f"user_camp_report_{cid_p8}"),
    ])
    if current["status"] in ("active", "paused", "suspended_admin"):
        buttons.append([types.InlineKeyboardButton(text="✏️ Live Edit", callback_data=f"user_edit_live_camp_{cid_p8}")])
    buttons.append([types.InlineKeyboardButton(text="🗑 Delete Campaign", callback_data=f"user_delete_campaign_{current['id']}")])
    buttons.append([types.InlineKeyboardButton(text="🔙 Back", callback_data="user_menu")])

    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode=ParseMode.HTML,
    )
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
    gen = await _get_generation()
    await resume_user_campaign(cid, gen)
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
    if current["status"] != "active":
        await callback.answer("⏸ Campaign is not active. Resume it first.", show_alert=True)
        return
    await callback.message.edit_text("🚀 Sending campaign... please wait.")
    try:
        await callback.answer()
    except Exception:
        pass
    asyncio.create_task(execute_user_campaign(cid))


# ── Campaign creation wizard — entry point ────────────────────────────────────

@router.callback_query(F.data == "user_create_campaign")
async def cb_user_create_campaign(callback: types.CallbackQuery, state: FSMContext):
    if not await _check_feature(callback):
        return
    user_id = callback.from_user.id
    if user_id == ADMIN_ID:
        await callback.answer()
        return

    quota = await get_quota(user_id, _today())
    if quota >= 5:
        await callback.answer("Daily limit reached (5/5). Try again tomorrow.", show_alert=True)
        return

    groups = await get_user_active_groups(user_id)
    if not groups:
        await callback.answer("You have no registered groups. Add this bot to a group first.", show_alert=True)
        return

    try:
        await callback.answer()
    except Exception:
        pass

    await _enter_ucw_step1(callback, state, editing=False)


# ── Phase 7 Interactive User Campaign Wizard ─────────────────────────────────

async def _enter_ucw_step1(event, state: FSMContext, editing: bool = False) -> None:
    """Enter Step 1 (Text) with bilingual prompt and inline Skip/Cancel buttons."""
    from core.i18n import t

    lang = await _p7_resolve_lang(event)
    if not editing:
        await state.update_data(
            text=None,
            photo_file_id=None,
            buttons_list=[],
            pending_btn_label=None,
            selected_groups=[],
            available_groups=[],
            target_chat_ids=[],
            mode="immediate",
            repeat_hours=0,
            auto_delete_seconds=0,
            editing_field=None,
            _groups_touched=False,
        )
    else:
        await state.update_data(editing_field="text")

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=t("uc_btn_skip_text", lang), callback_data="ucw_skip_text")],
        [types.InlineKeyboardButton(text=t("uc_btn_cancel", lang), callback_data="ucw_cancel_wizard")],
    ])
    target_msg = getattr(event, "message", event)
    await state.set_state(UserCampaignWizard.text)
    await _p7_safe_edit_or_answer(
        target_msg,
        t("uc_step1_text_prompt", lang),
        kb,
        prefer_edit=isinstance(event, types.CallbackQuery),
    )


async def _ask_ucw_photo(event, state: FSMContext, prefer_edit: bool = False) -> None:
    from core.i18n import t

    lang = await _p7_resolve_lang(event)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=t("uc_btn_skip_photo", lang), callback_data="ucw_skip_photo")],
        [types.InlineKeyboardButton(text=t("uc_btn_cancel", lang), callback_data="ucw_cancel_wizard")],
    ])
    target_msg = getattr(event, "message", event)
    await state.set_state(UserCampaignWizard.photo)
    await _p7_safe_edit_or_answer(
        target_msg,
        t("uc_step2_photo_prompt", lang),
        kb,
        prefer_edit=prefer_edit,
    )


# ── Step 1: Text Handlers ────────────────────────────────────────────────────

@router.message(UserCampaignWizard.text)
async def process_ucw_text(message: types.Message, state: FSMContext):
    from core.i18n import t

    lang = await _p7_resolve_lang(message)
    if not message.text:
        await message.answer(t("uc_err_text_required", lang))
        return

    raw_text = message.text.strip()
    if raw_text == "/cancel":
        await state.clear()
        await message.answer(t("uc_cancelled", lang))
        return

    data = await state.get_data()
    editing_field = data.get("editing_field")
    skip = raw_text == "/skip"

    if skip and editing_field == "text" and not data.get("photo_file_id"):
        await message.answer(t("uc_err_cannot_skip_both", lang))
        return

    saved_text = None if skip else (message.html_text or message.text)
    await state.update_data(text=saved_text)

    if editing_field == "text":
        await state.update_data(editing_field=None)
        await _show_live_preview(message, message.from_user.id, state, lang)
        return

    await _ask_ucw_photo(message, state, prefer_edit=False)


@router.callback_query(UserCampaignWizard.text, F.data == "ucw_skip_text")
async def cb_ucw_skip_text(callback: types.CallbackQuery, state: FSMContext):
    from core.i18n import t

    lang = await _p7_resolve_lang(callback)
    data = await state.get_data()
    if data.get("editing_field") == "text" and not data.get("photo_file_id"):
        await callback.answer(t("uc_err_cannot_skip_both", lang), show_alert=True)
        return

    await state.update_data(text=None)
    if data.get("editing_field") == "text":
        await state.update_data(editing_field=None)
        await _show_live_preview(callback.message, callback.from_user.id, state, lang)
    else:
        await _ask_ucw_photo(callback, state, prefer_edit=True)
    try:
        await callback.answer()
    except Exception:
        pass


# ── Step 2: Photo Handlers ───────────────────────────────────────────────────

@router.message(UserCampaignWizard.photo, F.photo)
async def process_ucw_photo(message: types.Message, state: FSMContext):
    lang = await _p7_resolve_lang(message)
    file_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=file_id)
    data = await state.get_data()
    if data.get("editing_field") == "photo":
        await state.update_data(editing_field=None)
        await _show_live_preview(message, message.from_user.id, state, lang)
        return
    await _ask_buttons(message, state)


@router.message(UserCampaignWizard.photo, F.text)
async def process_ucw_photo_text(message: types.Message, state: FSMContext):
    from core.i18n import t

    lang = await _p7_resolve_lang(message)
    if message.text == "/cancel":
        await state.clear()
        await message.answer(t("uc_cancelled", lang))
        return
    if message.text != "/skip":
        await message.answer(t("uc_err_photo_input", lang))
        return
    data = await state.get_data()
    if not data.get("text"):
        await message.answer(t("uc_err_cannot_skip_both", lang))
        return
    await state.update_data(photo_file_id=None)
    if data.get("editing_field") == "photo":
        await state.update_data(editing_field=None)
        await _show_live_preview(message, message.from_user.id, state, lang)
        return
    await _ask_buttons(message, state)


@router.callback_query(UserCampaignWizard.photo, F.data == "ucw_skip_photo")
async def cb_ucw_skip_photo(callback: types.CallbackQuery, state: FSMContext):
    from core.i18n import t

    lang = await _p7_resolve_lang(callback)
    data = await state.get_data()
    if not data.get("text"):
        await callback.answer(t("uc_err_cannot_skip_both", lang), show_alert=True)
        return
    await state.update_data(photo_file_id=None)
    if data.get("editing_field") == "photo":
        await state.update_data(editing_field=None)
        await _show_live_preview(callback.message, callback.from_user.id, state, lang)
    else:
        await _ask_buttons(callback, state, prefer_edit=True)
    try:
        await callback.answer()
    except Exception:
        pass


# ── Step 3: Two-Step Interactive Button Builder ──────────────────────────────

async def _ask_buttons(event, state: FSMContext, prefer_edit: bool = False) -> None:
    from core.i18n import t

    lang = await _p7_resolve_lang(event)
    data = await state.get_data()
    buttons_list: list[dict] = list(data.get("buttons_list") or [])

    if not buttons_list:
        list_text = t("uc_buttons_empty_list", lang)
    else:
        lines = []
        for idx, b in enumerate(buttons_list, 1):
            lines.append(
                f"{idx}. <b>{html.escape(b['text'])}</b> → <code>{html.escape(b['url'])}</code>"
            )
        list_text = "\n".join(lines)

    kb_rows = []
    if len(buttons_list) < _P7_MAX_BUTTONS:
        add_key = "uc_btn_add_button" if not buttons_list else "uc_btn_add_another_button"
        kb_rows.append([types.InlineKeyboardButton(text=t(add_key, lang), callback_data="ucw_btn_add")])

    for idx, b in enumerate(buttons_list):
        kb_rows.append([
            types.InlineKeyboardButton(
                text=t("uc_btn_remove_button", lang, idx=idx + 1, label=b["text"][:22]),
                callback_data=f"ucw_btn_del_{idx}",
            )
        ])

    kb_rows.append([types.InlineKeyboardButton(text=t("uc_btn_continue", lang), callback_data="ucw_btn_done")])
    kb_rows.append([types.InlineKeyboardButton(text=t("uc_btn_cancel", lang), callback_data="ucw_cancel_wizard")])

    target_msg = getattr(event, "message", event)
    await state.set_state(UserCampaignWizard.buttons)
    await _p7_safe_edit_or_answer(
        target_msg,
        t(
            "uc_step3_buttons_prompt",
            lang,
            count=len(buttons_list),
            max_buttons=_P7_MAX_BUTTONS,
            list_text=list_text,
        ),
        types.InlineKeyboardMarkup(inline_keyboard=kb_rows),
        prefer_edit=prefer_edit,
    )


@router.callback_query(UserCampaignWizard.buttons, F.data == "ucw_btn_add")
async def cb_ucw_btn_add(callback: types.CallbackQuery, state: FSMContext):
    from core.i18n import t

    lang = await _p7_resolve_lang(callback)
    data = await state.get_data()
    buttons_list = list(data.get("buttons_list") or [])
    if len(buttons_list) >= _P7_MAX_BUTTONS:
        await callback.answer(t("uc_btn_max_reached", lang, max_buttons=_P7_MAX_BUTTONS), show_alert=True)
        return

    await state.set_state(UserCampaignWizard.button_label)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔙 Back", callback_data="ucw_btn_back")],
        [types.InlineKeyboardButton(text=t("uc_btn_cancel", lang), callback_data="ucw_cancel_wizard")],
    ])
    await _p7_safe_edit_or_answer(
        callback.message,
        t("uc_btn_label_prompt", lang, num=len(buttons_list) + 1, max_buttons=_P7_MAX_BUTTONS),
        kb,
        prefer_edit=True,
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "ucw_btn_back")
async def cb_ucw_btn_back(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(pending_btn_label=None)
    await _ask_buttons(callback, state, prefer_edit=True)
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(UserCampaignWizard.button_label)
async def process_ucw_btn_label(message: types.Message, state: FSMContext):
    """Two-Step Button Builder — Step 1/2: receive Button Label."""
    from core.i18n import t

    lang = await _p7_resolve_lang(message)
    if not message.text:
        await message.answer(t("uc_err_btn_label_invalid", lang))
        return
    label = message.text.strip()
    if label == "/cancel":
        await state.clear()
        await message.answer(t("uc_cancelled", lang))
        return
    if not (1 <= len(label) <= 64):
        await message.answer(t("uc_err_btn_label_invalid", lang))
        return

    await state.update_data(pending_btn_label=label)
    await state.set_state(UserCampaignWizard.button_url)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔙 Back", callback_data="ucw_btn_back")],
        [types.InlineKeyboardButton(text=t("uc_btn_cancel", lang), callback_data="ucw_cancel_wizard")],
    ])
    await message.answer(
        t("uc_btn_url_prompt", lang, label=html.escape(label)),
        reply_markup=kb,
        parse_mode=ParseMode.HTML,
    )


@router.message(UserCampaignWizard.button_url)
async def process_ucw_btn_url(message: types.Message, state: FSMContext):
    """Two-Step Button Builder — Step 2/2: receive and validate Button URL."""
    from core.i18n import t

    lang = await _p7_resolve_lang(message)
    if not message.text:
        await message.answer(t("uc_err_btn_url_invalid", lang), parse_mode=ParseMode.HTML)
        return
    url = message.text.strip()
    if url == "/cancel":
        await state.clear()
        await message.answer(t("uc_cancelled", lang))
        return

    data = await state.get_data()
    label = (data.get("pending_btn_label") or "").strip()
    ok, _ = _p7_validate_single_button(label, url)
    if not ok:
        await message.answer(t("uc_err_btn_url_invalid", lang), parse_mode=ParseMode.HTML)
        return

    buttons_list = list(data.get("buttons_list") or [])
    if len(buttons_list) < _P7_MAX_BUTTONS:
        buttons_list.append({"text": label, "url": url})
    await state.update_data(buttons_list=buttons_list, pending_btn_label=None)
    await _ask_buttons(message, state, prefer_edit=False)


@router.callback_query(UserCampaignWizard.buttons, F.data.startswith("ucw_btn_del_"))
async def cb_ucw_btn_del(callback: types.CallbackQuery, state: FSMContext):
    from core.i18n import t

    lang = await _p7_resolve_lang(callback)
    idx = int(callback.data.replace("ucw_btn_del_", ""))
    data = await state.get_data()
    buttons_list = list(data.get("buttons_list") or [])
    if 0 <= idx < len(buttons_list):
        buttons_list.pop(idx)
        await state.update_data(buttons_list=buttons_list)
    await _ask_buttons(callback, state, prefer_edit=True)
    try:
        await callback.answer(t("uc_btn_removed_toast", lang))
    except Exception:
        pass


@router.callback_query(UserCampaignWizard.buttons, F.data == "ucw_btn_done")
async def cb_ucw_btn_done(callback: types.CallbackQuery, state: FSMContext):
    lang = await _p7_resolve_lang(callback)
    data = await state.get_data()
    if data.get("editing_field") == "buttons":
        await state.update_data(editing_field=None)
        await _show_live_preview(callback.message, callback.from_user.id, state, lang)
    else:
        await _ask_groups(callback, state, prefer_edit=True)
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(UserCampaignWizard.buttons)
async def process_ucw_buttons(message: types.Message, state: FSMContext):
    """Backward-compatible text handler (supports /skip, /cancel, or Label | URL)."""
    from core.i18n import t

    lang = await _p7_resolve_lang(message)
    if not message.text:
        await message.answer(t("uc_err_btn_label_invalid", lang))
        return
    raw = message.text.strip()
    if raw == "/cancel":
        await state.clear()
        await message.answer(t("uc_cancelled", lang))
        return
    if raw == "/skip":
        data = await state.get_data()
        if data.get("editing_field") == "buttons":
            await state.update_data(editing_field=None)
            await _show_live_preview(message, message.from_user.id, state, lang)
        else:
            await _ask_groups(message, state, prefer_edit=False)
        return

    # Optional legacy format "Label | https://..."
    if "|" in raw:
        parts = [p.strip() for p in raw.split("|", 1)]
        if len(parts) == 2:
            ok, _ = _p7_validate_single_button(parts[0], parts[1])
            if ok:
                data = await state.get_data()
                buttons_list = list(data.get("buttons_list") or [])
                if len(buttons_list) < _P7_MAX_BUTTONS:
                    buttons_list.append({"text": parts[0], "url": parts[1]})
                    await state.update_data(buttons_list=buttons_list)
                await _ask_buttons(message, state, prefer_edit=False)
                return
    await _ask_buttons(message, state, prefer_edit=False)


# ── Step 4: Interactive Groups Checkbox Selector ─────────────────────────────

async def _ask_groups(event, state: FSMContext, prefer_edit: bool = False) -> None:
    from core.i18n import t

    lang = await _p7_resolve_lang(event)
    user_id = event.from_user.id
    groups = await get_user_active_groups(user_id)
    target_msg = getattr(event, "message", event)

    if not groups:
        await state.clear()
        await _p7_safe_edit_or_answer(target_msg, t("uc_no_groups", lang), prefer_edit=prefer_edit)
        return

    avail = [[int(chat_id), str(title or chat_id)] for chat_id, title, _ in groups]
    data = await state.get_data()
    valid_ids = {g[0] for g in avail}
    selected = [int(cid) for cid in (data.get("selected_groups") or []) if int(cid) in valid_ids]
    if not selected and not data.get("_groups_touched"):
        selected = [g[0] for g in avail]  # Pre-select all on first visit

    await state.update_data(available_groups=avail, selected_groups=selected, _groups_touched=True)
    await state.set_state(UserCampaignWizard.groups)
    await _render_groups_picker(target_msg, avail, selected, lang, prefer_edit=prefer_edit)


async def _render_groups_picker(
    target_msg: types.Message,
    avail: list[list],
    selected: list[int],
    lang: str,
    prefer_edit: bool = True,
) -> None:
    from core.i18n import t

    selected_set = set(selected)
    kb_rows = []
    for chat_id, title in avail[:25]:
        mark = "✅" if chat_id in selected_set else "⬜"
        kb_rows.append([
            types.InlineKeyboardButton(
                text=f"{mark} {title[:32]}",
                callback_data=f"ucw_grp_toggle_{chat_id}",
            )
        ])

    kb_rows.append([
        types.InlineKeyboardButton(text=t("uc_btn_select_all", lang), callback_data="ucw_grp_all"),
        types.InlineKeyboardButton(text=t("uc_btn_clear_all", lang), callback_data="ucw_grp_none"),
    ])
    kb_rows.append([
        types.InlineKeyboardButton(
            text=t("uc_btn_confirm_groups", lang, count=len(selected_set)),
            callback_data="ucw_grp_done",
        )
    ])
    kb_rows.append([
        types.InlineKeyboardButton(text=t("uc_btn_cancel", lang), callback_data="ucw_cancel_wizard")
    ])

    await _p7_safe_edit_or_answer(
        target_msg,
        t("uc_step4_groups_prompt", lang, selected_count=len(selected_set), total_count=len(avail)),
        types.InlineKeyboardMarkup(inline_keyboard=kb_rows),
        prefer_edit=prefer_edit,
    )


@router.callback_query(UserCampaignWizard.groups, F.data.startswith("ucw_grp_toggle_"))
async def cb_ucw_grp_toggle(callback: types.CallbackQuery, state: FSMContext):
    lang = await _p7_resolve_lang(callback)
    chat_id = int(callback.data.replace("ucw_grp_toggle_", ""))
    data = await state.get_data()
    avail = data.get("available_groups") or []
    selected = list(data.get("selected_groups") or [])
    if chat_id in selected:
        selected.remove(chat_id)
    else:
        selected.append(chat_id)
    await state.update_data(selected_groups=selected, _groups_touched=True)
    await _render_groups_picker(callback.message, avail, selected, lang, prefer_edit=True)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(UserCampaignWizard.groups, F.data == "ucw_grp_all")
async def cb_ucw_grp_all(callback: types.CallbackQuery, state: FSMContext):
    lang = await _p7_resolve_lang(callback)
    data = await state.get_data()
    avail = data.get("available_groups") or []
    selected = [int(g[0]) for g in avail]
    await state.update_data(selected_groups=selected, _groups_touched=True)
    await _render_groups_picker(callback.message, avail, selected, lang, prefer_edit=True)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(UserCampaignWizard.groups, F.data == "ucw_grp_none")
async def cb_ucw_grp_none(callback: types.CallbackQuery, state: FSMContext):
    lang = await _p7_resolve_lang(callback)
    data = await state.get_data()
    avail = data.get("available_groups") or []
    await state.update_data(selected_groups=[], _groups_touched=True)
    await _render_groups_picker(callback.message, avail, [], lang, prefer_edit=True)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(UserCampaignWizard.groups, F.data == "ucw_grp_done")
async def cb_ucw_grp_done(callback: types.CallbackQuery, state: FSMContext):
    from core.i18n import t

    lang = await _p7_resolve_lang(callback)
    data = await state.get_data()
    selected = list(data.get("selected_groups") or [])
    if not selected:
        await callback.answer(t("uc_err_no_groups_selected", lang), show_alert=True)
        return
    await state.update_data(target_chat_ids=selected)
    if data.get("editing_field") == "groups":
        await state.update_data(editing_field=None)
        await _show_live_preview(callback.message, callback.from_user.id, state, lang)
    else:
        await _ask_ucw_mode(callback, state, prefer_edit=True)
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(UserCampaignWizard.groups)
async def process_ucw_groups(message: types.Message, state: FSMContext):
    """Backward-compatible text input (1,2,3 or all)."""
    from core.i18n import t

    lang = await _p7_resolve_lang(message)
    if not message.text:
        await message.answer(t("uc_err_groups_input", lang))
        return
    raw = message.text.strip().lower()
    if raw == "/cancel":
        await state.clear()
        await message.answer(t("uc_cancelled", lang))
        return

    data = await state.get_data()
    avail = data.get("available_groups") or []
    if raw == "all":
        selected = [int(g[0]) for g in avail]
    else:
        try:
            indices = [int(x.strip()) for x in raw.split(",") if x.strip()]
            selected = [int(avail[i - 1][0]) for i in indices if 1 <= i <= len(avail)]
            selected = list(dict.fromkeys(selected))
        except (ValueError, IndexError):
            await message.answer(t("uc_err_groups_input", lang))
            return

    if not selected:
        await message.answer(t("uc_err_groups_input", lang))
        return

    await state.update_data(selected_groups=selected, target_chat_ids=selected)
    if data.get("editing_field") == "groups":
        await state.update_data(editing_field=None)
        await _show_live_preview(message, message.from_user.id, state, lang)
    else:
        await _ask_ucw_mode(message, state, prefer_edit=False)


# ── Step 5: Schedule Mode Picker ─────────────────────────────────────────────

async def _ask_ucw_mode(event, state: FSMContext, prefer_edit: bool = False) -> None:
    from core.i18n import t

    lang = await _p7_resolve_lang(event)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=t("uc_btn_mode_now", lang), callback_data="ucw_mode_now")],
        [
            types.InlineKeyboardButton(text=t("uc_btn_mode_rec_6", lang), callback_data="ucw_mode_rec_6"),
            types.InlineKeyboardButton(text=t("uc_btn_mode_rec_12", lang), callback_data="ucw_mode_rec_12"),
        ],
        [
            types.InlineKeyboardButton(text=t("uc_btn_mode_rec_24", lang), callback_data="ucw_mode_rec_24"),
            types.InlineKeyboardButton(text=t("uc_btn_mode_rec_48", lang), callback_data="ucw_mode_rec_48"),
        ],
        [types.InlineKeyboardButton(text=t("uc_btn_mode_rec_custom", lang), callback_data="ucw_mode_rec_custom")],
        [types.InlineKeyboardButton(text=t("uc_btn_cancel", lang), callback_data="ucw_cancel_wizard")],
    ])
    target_msg = getattr(event, "message", event)
    await state.set_state(UserCampaignWizard.mode)
    await _p7_safe_edit_or_answer(target_msg, t("uc_step5_mode_prompt", lang), kb, prefer_edit=prefer_edit)


@router.callback_query(UserCampaignWizard.mode, F.data == "ucw_mode_now")
async def cb_ucw_mode_now(callback: types.CallbackQuery, state: FSMContext):
    lang = await _p7_resolve_lang(callback)
    await state.update_data(mode="immediate", repeat_hours=0)
    data = await state.get_data()
    if data.get("editing_field") == "mode":
        await state.update_data(editing_field=None)
        await _show_live_preview(callback.message, callback.from_user.id, state, lang)
    else:
        await _ask_ucw_autodel(callback, state, prefer_edit=True)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(UserCampaignWizard.mode, F.data.startswith("ucw_mode_rec_"))
async def cb_ucw_mode_recurring(callback: types.CallbackQuery, state: FSMContext):
    from core.i18n import t

    lang = await _p7_resolve_lang(callback)
    val = callback.data.replace("ucw_mode_rec_", "")
    if val == "custom":
        await state.set_state(UserCampaignWizard.custom_hours)
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=t("uc_btn_cancel", lang), callback_data="ucw_cancel_wizard")]
        ])
        await _p7_safe_edit_or_answer(callback.message, t("uc_custom_hours_prompt", lang), kb, prefer_edit=True)
        try:
            await callback.answer()
        except Exception:
            pass
        return

    hours = int(val)
    await state.update_data(mode="recurring", repeat_hours=hours)
    data = await state.get_data()
    if data.get("editing_field") == "mode":
        await state.update_data(editing_field=None)
        await _show_live_preview(callback.message, callback.from_user.id, state, lang)
    else:
        await _ask_ucw_autodel(callback, state, prefer_edit=True)
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(UserCampaignWizard.custom_hours)
async def process_ucw_custom_hours(message: types.Message, state: FSMContext):
    from core.i18n import t

    lang = await _p7_resolve_lang(message)
    if not message.text:
        await message.answer(t("uc_err_min_hours", lang))
        return
    raw = message.text.strip()
    if raw == "/cancel":
        await state.clear()
        await message.answer(t("uc_cancelled", lang))
        return
    if not raw.isdigit() or not (6 <= int(raw) <= 720):
        await message.answer(t("uc_err_min_hours", lang))
        return

    await state.update_data(mode="recurring", repeat_hours=int(raw))
    data = await state.get_data()
    if data.get("editing_field") == "mode":
        await state.update_data(editing_field=None)
        await _show_live_preview(message, message.from_user.id, state, lang)
    else:
        await _ask_ucw_autodel(message, state, prefer_edit=False)


@router.message(UserCampaignWizard.mode)
async def process_ucw_mode(message: types.Message, state: FSMContext):
    """Backward-compatible text input ('now' or hours >= 6)."""
    from core.i18n import t

    lang = await _p7_resolve_lang(message)
    if not message.text:
        await message.answer(t("uc_err_mode_input", lang))
        return
    raw = message.text.strip().lower()
    if raw == "/cancel":
        await state.clear()
        await message.answer(t("uc_cancelled", lang))
        return
    if raw == "now":
        await state.update_data(mode="immediate", repeat_hours=0)
    elif raw.isdigit() and 6 <= int(raw) <= 720:
        await state.update_data(mode="recurring", repeat_hours=int(raw))
    else:
        await message.answer(t("uc_err_mode_input", lang))
        return

    data = await state.get_data()
    if data.get("editing_field") == "mode":
        await state.update_data(editing_field=None)
        await _show_live_preview(message, message.from_user.id, state, lang)
    else:
        await _ask_ucw_autodel(message, state, prefer_edit=False)


# ── Step 6: Auto-Delete Timer Picker ─────────────────────────────────────────

async def _ask_ucw_autodel(event, state: FSMContext, prefer_edit: bool = False) -> None:
    from core.i18n import t

    lang = await _p7_resolve_lang(event)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=t("uc_btn_autodel_none", lang), callback_data="ucw_autodel_0")],
        [
            types.InlineKeyboardButton(text=t("uc_btn_autodel_1h", lang), callback_data="ucw_autodel_3600"),
            types.InlineKeyboardButton(text=t("uc_btn_autodel_6h", lang), callback_data="ucw_autodel_21600"),
        ],
        [types.InlineKeyboardButton(text=t("uc_btn_autodel_24h", lang), callback_data="ucw_autodel_86400")],
        [types.InlineKeyboardButton(text=t("uc_btn_cancel", lang), callback_data="ucw_cancel_wizard")],
    ])
    target_msg = getattr(event, "message", event)
    await state.set_state(UserCampaignWizard.auto_delete)
    await _p7_safe_edit_or_answer(target_msg, t("uc_step6_autodel_prompt", lang), kb, prefer_edit=prefer_edit)


@router.callback_query(UserCampaignWizard.auto_delete, F.data.startswith("ucw_autodel_"))
async def cb_ucw_autodel(callback: types.CallbackQuery, state: FSMContext):
    lang = await _p7_resolve_lang(callback)
    sec = int(callback.data.replace("ucw_autodel_", ""))
    await state.update_data(auto_delete_seconds=sec, editing_field=None)
    await _show_live_preview(callback.message, callback.from_user.id, state, lang)
    try:
        await callback.answer()
    except Exception:
        pass


# ── Step 7: Live Preview, Edit Submenu & Launch Confirmation ─────────────────

async def _show_live_preview(
    target_msg: types.Message,
    user_id: int,
    state: FSMContext,
    lang: str,
) -> None:
    """
    Send exact live preview of campaign message + summary control card.
    Does NOT consume daily quota.
    """
    from core.i18n import t

    data = await state.get_data()
    text = data.get("text")
    photo_file_id = data.get("photo_file_id")
    buttons_list: list[dict] = list(data.get("buttons_list") or [])
    target_chat_ids: list[int] = list(data.get("target_chat_ids") or data.get("selected_groups") or [])
    mode = data.get("mode", "immediate")
    repeat_hours = int(data.get("repeat_hours") or 0)
    auto_del_sec = int(data.get("auto_delete_seconds") or 0)

    preview_kb = _p7_build_preview_keyboard(buttons_list)

    # 1. Send exact live preview
    if photo_file_id:
        try:
            await target_msg.answer_photo(
                photo=photo_file_id,
                caption=text or None,
                reply_markup=preview_kb,
                parse_mode=ParseMode.HTML if text else None,
            )
        except Exception:
            await target_msg.answer_photo(
                photo=photo_file_id,
                caption=text or None,
                reply_markup=preview_kb,
            )
    else:
        body = text or ""
        try:
            await target_msg.answer(body, reply_markup=preview_kb, parse_mode=ParseMode.HTML)
        except Exception:
            await target_msg.answer(body, reply_markup=preview_kb)

    # 2. Summary & control card
    mode_label = (
        t("uc_mode_label_immediate", lang)
        if mode == "immediate"
        else t("uc_mode_label_recurring", lang, hours=repeat_hours)
    )
    autodel_label = (
        t("uc_autodel_label_none", lang)
        if auto_del_sec <= 0
        else t("uc_autodel_label_hours", lang, hours=max(1, auto_del_sec // 3600))
    )

    replace_note = ""
    current = await get_current_campaign(user_id)
    if current and current["status"] in ("active", "paused", "suspended_admin"):
        replace_note = t("uc_replace_warning_note", lang)

    summary_text = t(
        "uc_preview_summary",
        lang,
        groups_count=len(target_chat_ids),
        buttons_count=len(buttons_list),
        mode_label=mode_label,
        autodel_label=autodel_label,
        replace_note=replace_note,
    )
    control_kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=t("uc_btn_confirm_launch", lang), callback_data="ucw_confirm_launch")],
        [types.InlineKeyboardButton(text=t("uc_btn_edit_campaign", lang), callback_data="ucw_edit_menu")],
        [types.InlineKeyboardButton(text=t("uc_btn_cancel", lang), callback_data="ucw_cancel_wizard")],
    ])

    await state.set_state(UserCampaignWizard.confirm)
    await target_msg.answer(summary_text, reply_markup=control_kb, parse_mode=ParseMode.HTML)


@router.callback_query(UserCampaignWizard.confirm, F.data == "ucw_edit_menu")
async def cb_ucw_edit_menu(callback: types.CallbackQuery, state: FSMContext):
    from core.i18n import t

    lang = await _p7_resolve_lang(callback)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text=t("uc_btn_edit_text", lang), callback_data="ucw_edit_text"),
            types.InlineKeyboardButton(text=t("uc_btn_edit_photo", lang), callback_data="ucw_edit_photo"),
        ],
        [
            types.InlineKeyboardButton(text=t("uc_btn_edit_buttons", lang), callback_data="ucw_edit_buttons"),
            types.InlineKeyboardButton(text=t("uc_btn_edit_groups", lang), callback_data="ucw_edit_groups"),
        ],
        [
            types.InlineKeyboardButton(text=t("uc_btn_edit_mode", lang), callback_data="ucw_edit_mode"),
            types.InlineKeyboardButton(text=t("uc_btn_edit_autodel", lang), callback_data="ucw_edit_autodel"),
        ],
        [types.InlineKeyboardButton(text=t("uc_btn_back_preview", lang), callback_data="ucw_back_preview")],
    ])
    await _p7_safe_edit_or_answer(callback.message, t("uc_edit_menu_title", lang), kb, prefer_edit=True)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(UserCampaignWizard.confirm, F.data == "ucw_back_preview")
async def cb_ucw_back_preview(callback: types.CallbackQuery, state: FSMContext):
    lang = await _p7_resolve_lang(callback)
    await state.update_data(editing_field=None)
    await _show_live_preview(callback.message, callback.from_user.id, state, lang)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(UserCampaignWizard.confirm, F.data.startswith("ucw_edit_"))
async def cb_ucw_edit_field(callback: types.CallbackQuery, state: FSMContext):
    field = callback.data.replace("ucw_edit_", "")
    if field == "text":
        await _enter_ucw_step1(callback, state, editing=True)
    elif field == "photo":
        await state.update_data(editing_field="photo")
        await _ask_ucw_photo(callback, state, prefer_edit=True)
    elif field == "buttons":
        await state.update_data(editing_field="buttons")
        await _ask_buttons(callback, state, prefer_edit=True)
    elif field == "groups":
        await state.update_data(editing_field="groups")
        await _ask_groups(callback, state, prefer_edit=True)
    elif field == "mode":
        await state.update_data(editing_field="mode")
        await _ask_ucw_mode(callback, state, prefer_edit=True)
    elif field == "autodel":
        await state.update_data(editing_field="autodel")
        await _ask_ucw_autodel(callback, state, prefer_edit=True)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(UserCampaignWizard.confirm, F.data == "ucw_confirm_launch")
async def cb_ucw_confirm_launch(callback: types.CallbackQuery, state: FSMContext):
    """Persist campaign, consume 1 daily quota slot, and trigger execution."""
    from core.i18n import t

    lang = await _p7_resolve_lang(callback)
    user_id = callback.from_user.id
    data = await state.get_data()

    text = data.get("text")
    photo_file_id = data.get("photo_file_id")
    buttons_list: list[dict] = list(data.get("buttons_list") or [])
    # Convert wizard format {"text":..., "url":...} → service format [[{"label":..., "url":...}]]
    if buttons_list:
        service_rows = [[{"label": b["text"], "url": b["url"]} for b in buttons_list]]
        buttons_json = json.dumps(service_rows)
    else:
        buttons_json = None
    target_chat_ids: list[int] = list(data.get("target_chat_ids") or data.get("selected_groups") or [])
    mode = data.get("mode", "immediate")
    repeat_hours = int(data.get("repeat_hours") or 0)
    auto_delete_seconds = int(data.get("auto_delete_seconds") or 0)

    cid, err = await create_user_campaign(
        user_id=user_id,
        text=text,
        photo_file_id=photo_file_id,
        buttons_json=buttons_json,
        target_chat_ids=target_chat_ids,
        mode=mode,
        repeat_hours=repeat_hours,
        auto_delete_seconds=auto_delete_seconds,
    )
    await state.clear()

    if err or not cid:
        await _p7_safe_edit_or_answer(
            callback.message,
            t("uc_launch_failed", lang, error=html.escape(str(err or "Unknown error"))),
            prefer_edit=True,
        )
        try:
            await callback.answer()
        except Exception:
            pass
        return

    back_kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔙 Dashboard", callback_data="user_menu")]
    ])

    if mode == "immediate":
        await _p7_safe_edit_or_answer(
            callback.message,
            t("uc_launch_success_immediate", lang, cid=cid, groups_count=len(target_chat_ids)),
            back_kb,
            prefer_edit=True,
        )
        asyncio.create_task(execute_user_campaign(cid))
    else:
        await _p7_safe_edit_or_answer(
            callback.message,
            t(
                "uc_launch_success_recurring",
                lang,
                cid=cid,
                hours=repeat_hours,
                groups_count=len(target_chat_ids),
            ),
            back_kb,
            prefer_edit=True,
        )

    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "ucw_cancel_wizard")
async def cb_ucw_cancel_wizard(callback: types.CallbackQuery, state: FSMContext):
    from core.i18n import t

    lang = await _p7_resolve_lang(callback)
    await state.clear()
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔙 Dashboard", callback_data="user_menu")]
    ])
    await _p7_safe_edit_or_answer(callback.message, t("uc_cancelled", lang), kb, prefer_edit=True)
    try:
        await callback.answer()
    except Exception:
        pass
