"""
Phase 8 — User Dashboard Pro Handler
Implements:
  - 📊 My Statistics
  - 📊 Last Run Report
  - 👁 Private Test Send (Test DM)
  - ✏️ Live Edit active campaign (zero quota, 2-step button builder)
  - 🗂 Campaign History + ♻️ 1-Click Relaunch
  - 🔄 Groups Health Check
"""

import html
import json
import logging
from typing import Any

from aiogram import Router, F, types, Bot
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext

from core.i18n import t, get_lang
from models.user_campaigns import (
    get_current_campaign,
    get_user_overall_stats,
    get_campaign_last_run_deliveries,
    get_user_campaign_history,
    update_user_campaign_fields,
    get_quota,
    extract_campaign_target_ids,
)
from models.groups import get_user_active_groups, upsert_group
from states.user_states import UserCampaignWizard, UserCampaignEdit


async def _check_group_health(bot: "Bot", chat_id: int) -> str:
    """Check if the bot has posting permissions in a group. Returns 'ok' or 'no_permission'."""
    try:
        member = await bot.get_chat_member(chat_id, (await bot.me()).id)
        if hasattr(member, "can_post_messages") and member.can_post_messages is False:
            return "no_permission"
        if member.status in ("kicked", "left", "restricted"):
            return "no_permission"
        return "ok"
    except Exception:
        return "no_permission"

logger = logging.getLogger(__name__)

router = Router(name="user_dashboard_pro")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _status_label(status: str, lang: str) -> str:
    key = f"u8_status_{status}"
    return t(key, lang) if f"u8_status_{status}" else status


def _mode_label(campaign: dict, lang: str) -> str:
    if campaign.get("mode") == "recurring":
        return t("uc_mode_label_recurring", lang).format(hours=campaign.get("repeat_hours", "?"))
    return t("uc_mode_label_immediate", lang)


def _fmt_dt(dt_str: str | None, lang: str) -> str:
    if not dt_str:
        return t("u8_not_scheduled", lang)
    return str(dt_str)[:16]


def _build_edit_menu_kb(cid: int, lang: str) -> types.InlineKeyboardMarkup:
    rows = [
        [
            types.InlineKeyboardButton(text=t("uc_btn_edit_text", lang),    callback_data=f"u8_edit_text_{cid}"),
            types.InlineKeyboardButton(text=t("uc_btn_edit_photo", lang),   callback_data=f"u8_edit_photo_{cid}"),
        ],
        [
            types.InlineKeyboardButton(text=t("uc_btn_edit_buttons", lang), callback_data=f"u8_edit_buttons_{cid}"),
            types.InlineKeyboardButton(text=t("uc_btn_edit_groups", lang),  callback_data=f"u8_edit_groups_{cid}"),
        ],
        [
            types.InlineKeyboardButton(text=t("uc_btn_edit_mode", lang),    callback_data=f"u8_edit_mode_{cid}"),
            types.InlineKeyboardButton(text=t("uc_btn_edit_autodel", lang), callback_data=f"u8_edit_autodel_{cid}"),
        ],
        [
            types.InlineKeyboardButton(text=t("u8_edit_btn_back_camp", lang), callback_data=f"user_camp_back_{cid}"),
        ],
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


# ── 📊 My Statistics ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "user_my_stats")
async def cb_my_stats(call: types.CallbackQuery):
    lang = await get_lang(call.from_user.id)
    stats = await get_user_overall_stats(call.from_user.id)
    text = t("u8_stats_body", lang).format(**stats)

    camp = await get_current_campaign(call.from_user.id)
    if camp:
        text += t("u8_stats_current_section", lang).format(
            cid=camp["id"],
            status_label=_status_label(camp["status"], lang),
            mode_label=_mode_label(camp, lang),
            last_run=_fmt_dt(camp.get("last_run_at"), lang) if camp.get("last_run_at") else t("u8_not_run_yet", lang),
            next_run=_fmt_dt(camp.get("next_run_at"), lang),
        )
    else:
        text += "\n\n" + t("u8_stats_no_current", lang)

    await call.message.edit_text(text, parse_mode=ParseMode.HTML)
    await call.answer()


# ── 📊 Last Run Report ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("user_camp_report_"))
async def cb_last_report(call: types.CallbackQuery):
    lang = await get_lang(call.from_user.id)
    cid = int(call.data.split("_")[-1])

    rows = await get_campaign_last_run_deliveries(cid, call.from_user.id)
    if not rows:
        await call.answer(t("u8_report_empty", lang), show_alert=True)
        return

    text = t("u8_report_title", lang).format(cid=cid)
    ok = fail = 0
    for row in rows:
        safe_title = html.escape(row["title"])
        if row["status"] == "sent":
            text += t("u8_report_row_ok", lang).format(title=safe_title)
            ok += 1
        else:
            err = html.escape(row.get("error_code") or "unknown")
            text += t("u8_report_row_fail", lang).format(title=safe_title, error=err)
            fail += 1
    text += t("u8_report_summary", lang).format(ok=ok, fail=fail)

    kb = types.InlineKeyboardMarkup(inline_keyboard=[[
        types.InlineKeyboardButton(text=t("btn_back", lang), callback_data=f"user_camp_back_{cid}")
    ]])
    await call.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await call.answer()


# ── 👁 Private Test Send ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("user_test_campaign_"))
async def cb_test_dm(call: types.CallbackQuery, bot: Bot):
    lang = await get_lang(call.from_user.id)
    cid = int(call.data.split("_")[-1])

    camp = await get_current_campaign(call.from_user.id)
    if not camp or camp["id"] != cid:
        await call.answer(t("u8_camp_not_found", lang), show_alert=True)
        return

    # Build inline keyboard from stored buttons JSON
    reply_markup = None
    if camp.get("buttons_json"):
        try:
            buttons = json.loads(camp["buttons_json"])
            # Support both flat [{"text":..,"url":..}] and nested [[{"label":..,"url":..}]]
            if buttons and isinstance(buttons[0], dict) and "text" in buttons[0]:
                rows_kb = [[types.InlineKeyboardButton(text=b["text"], url=b["url"]) for b in buttons]]
            elif buttons and isinstance(buttons[0], list):
                rows_kb = [
                    [types.InlineKeyboardButton(text=b.get("label", b.get("text", "")), url=b["url"]) for b in row]
                    for row in buttons
                ]
            else:
                rows_kb = []
            if rows_kb:
                reply_markup = types.InlineKeyboardMarkup(inline_keyboard=rows_kb)
        except Exception:
            pass

    try:
        if camp.get("photo_file_id"):
            await bot.send_photo(
                chat_id=call.from_user.id,
                photo=camp["photo_file_id"],
                caption=camp.get("text") or "",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
        else:
            await bot.send_message(
                chat_id=call.from_user.id,
                text=camp.get("text") or "(no text)",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
        await call.answer(t("u8_test_dm_sent_toast", lang), show_alert=True)
    except Exception as e:
        await call.answer(f"❌ {e}", show_alert=True)


# ── ✏️ Live Edit — open menu ──────────────────────────────────────────────────

@router.callback_query(F.data.startswith("user_edit_live_camp_"))
async def cb_edit_live_open(call: types.CallbackQuery, state: FSMContext):
    lang = await get_lang(call.from_user.id)
    cid = int(call.data.split("_")[-1])

    camp = await get_current_campaign(call.from_user.id)
    if not camp or camp["id"] != cid:
        await call.answer(t("u8_camp_not_found", lang), show_alert=True)
        return
    if camp["status"] == "running":
        await call.answer(t("u8_edit_blocked_running", lang), show_alert=True)
        return

    await state.update_data(edit_cid=cid, edit_buttons=[])
    await state.set_state(UserCampaignEdit.menu)
    await call.message.edit_text(
        t("u8_edit_title", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=_build_edit_menu_kb(cid, lang),
    )
    await call.answer()


# ── Live Edit: Text ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("u8_edit_text_"))
async def cb_edit_text_prompt(call: types.CallbackQuery, state: FSMContext):
    lang = await get_lang(call.from_user.id)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[
        types.InlineKeyboardButton(text=t("u8_edit_btn_clear_text", lang), callback_data="u8_clear_text"),
        types.InlineKeyboardButton(text=t("btn_back", lang), callback_data="u8_back_edit_menu"),
    ]])
    await call.message.edit_text(t("u8_edit_text_prompt", lang), reply_markup=kb)
    await state.set_state(UserCampaignEdit.text)
    await call.answer()


@router.message(UserCampaignEdit.text)
async def handle_edit_text(message: types.Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    cid = data["edit_cid"]
    new_text = message.text or message.caption or ""
    ok, reason = await update_user_campaign_fields(cid, message.from_user.id, text=new_text)
    if ok:
        await message.answer(t("u8_edit_saved_notice", lang))
    else:
        await message.answer(t("u8_edit_failed", lang).format(reason=reason))
    await state.set_state(UserCampaignEdit.menu)
    # Re-show edit menu
    await message.answer(
        t("u8_edit_title", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=_build_edit_menu_kb(cid, lang),
    )


@router.callback_query(F.data == "u8_clear_text")
async def cb_clear_text(call: types.CallbackQuery, state: FSMContext):
    lang = await get_lang(call.from_user.id)
    data = await state.get_data()
    cid = data["edit_cid"]
    ok, reason = await update_user_campaign_fields(cid, call.from_user.id, text=None)
    if ok:
        await call.answer(t("u8_edit_saved_notice", lang), show_alert=False)
    else:
        await call.answer(t("u8_edit_failed", lang).format(reason=reason), show_alert=True)
    await state.set_state(UserCampaignEdit.menu)
    await call.message.edit_text(
        t("u8_edit_title", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=_build_edit_menu_kb(cid, lang),
    )


# ── Live Edit: Photo ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("u8_edit_photo_"))
async def cb_edit_photo_prompt(call: types.CallbackQuery, state: FSMContext):
    lang = await get_lang(call.from_user.id)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[
        types.InlineKeyboardButton(text=t("u8_edit_btn_clear_photo", lang), callback_data="u8_clear_photo"),
        types.InlineKeyboardButton(text=t("btn_back", lang), callback_data="u8_back_edit_menu"),
    ]])
    await call.message.edit_text(t("u8_edit_photo_prompt", lang), reply_markup=kb)
    await state.set_state(UserCampaignEdit.photo)
    await call.answer()


@router.message(UserCampaignEdit.photo, F.photo)
async def handle_edit_photo(message: types.Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    cid = data["edit_cid"]
    file_id = message.photo[-1].file_id
    ok, reason = await update_user_campaign_fields(cid, message.from_user.id, photo_file_id=file_id)
    if ok:
        await message.answer(t("u8_edit_saved_notice", lang))
    else:
        await message.answer(t("u8_edit_failed", lang).format(reason=reason))
    await state.set_state(UserCampaignEdit.menu)
    await message.answer(
        t("u8_edit_title", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=_build_edit_menu_kb(cid, lang),
    )


@router.callback_query(F.data == "u8_clear_photo")
async def cb_clear_photo(call: types.CallbackQuery, state: FSMContext):
    lang = await get_lang(call.from_user.id)
    data = await state.get_data()
    cid = data["edit_cid"]
    ok, reason = await update_user_campaign_fields(cid, call.from_user.id, photo_file_id=None)
    if ok:
        await call.answer(t("u8_edit_saved_notice", lang), show_alert=False)
    else:
        await call.answer(t("u8_edit_failed", lang).format(reason=reason), show_alert=True)
    await state.set_state(UserCampaignEdit.menu)
    await call.message.edit_text(
        t("u8_edit_title", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=_build_edit_menu_kb(cid, lang),
    )


# ── Live Edit: 2-step Button Builder ─────────────────────────────────────────

@router.callback_query(F.data.startswith("u8_edit_buttons_"))
async def cb_edit_buttons_start(call: types.CallbackQuery, state: FSMContext):
    lang = await get_lang(call.from_user.id)
    cid = int(call.data.split("_")[-1])
    await state.update_data(edit_cid=cid, edit_buttons=[])
    await state.set_state(UserCampaignEdit.button_label)
    await call.message.edit_text(
        t("uc_step3a_label_prompt", lang),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[
            types.InlineKeyboardButton(text=t("uc_btn_skip_buttons", lang), callback_data=f"u8_skip_buttons_{cid}"),
            types.InlineKeyboardButton(text=t("btn_back", lang), callback_data="u8_back_edit_menu"),
        ]]),
    )
    await call.answer()


@router.message(UserCampaignEdit.button_label)
async def handle_edit_button_label(message: types.Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    label = message.text.strip() if message.text else ""
    if not label:
        await message.answer("❌ Label cannot be empty.")
        return
    await state.update_data(pending_btn_label=label)
    await state.set_state(UserCampaignEdit.button_url)
    await message.answer(t("uc_step3b_url_prompt", lang).format(label=html.escape(label)), parse_mode=ParseMode.HTML)


@router.message(UserCampaignEdit.button_url)
async def handle_edit_button_url(message: types.Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    url = message.text.strip() if message.text else ""
    if not url.startswith(("http://", "https://", "tg://")):
        await message.answer(t("uc_btn_url_invalid", lang))
        return
    data = await state.get_data()
    label = data.get("pending_btn_label", "Button")
    buttons = data.get("edit_buttons", [])
    buttons.append({"text": label, "url": url})
    cid = data["edit_cid"]

    if len(buttons) >= 3:
        # Save buttons and return to menu
        ok, reason = await update_user_campaign_fields(
            cid, message.from_user.id,
            buttons_json=json.dumps(buttons),
        )
        if ok:
            await message.answer(t("u8_edit_saved_notice", lang))
        else:
            await message.answer(t("u8_edit_failed", lang).format(reason=reason))
        await state.update_data(edit_buttons=[])
        await state.set_state(UserCampaignEdit.menu)
        await message.answer(
            t("u8_edit_title", lang),
            parse_mode=ParseMode.HTML,
            reply_markup=_build_edit_menu_kb(cid, lang),
        )
        return

    await state.update_data(edit_buttons=buttons)
    # Ask for another button or finish
    btn_list = "\n".join(f"• {b['text']}" for b in buttons)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=t("uc_btn_add_another", lang), callback_data=f"u8_add_btn_{cid}")],
        [types.InlineKeyboardButton(text=t("uc_btn_done_buttons", lang), callback_data=f"u8_done_buttons_{cid}")],
    ])
    await message.answer(
        f"✅ Button added.\n\nButtons so far:\n{btn_list}",
        reply_markup=kb,
    )
    await state.set_state(UserCampaignEdit.buttons)


@router.callback_query(F.data.startswith("u8_add_btn_"))
async def cb_add_another_button(call: types.CallbackQuery, state: FSMContext):
    lang = await get_lang(call.from_user.id)
    await state.set_state(UserCampaignEdit.button_label)
    await call.message.edit_text(t("uc_step3a_label_prompt", lang))
    await call.answer()


@router.callback_query(F.data.startswith("u8_done_buttons_"))
async def cb_done_buttons(call: types.CallbackQuery, state: FSMContext):
    lang = await get_lang(call.from_user.id)
    data = await state.get_data()
    cid = data["edit_cid"]
    buttons = data.get("edit_buttons", [])
    ok, reason = await update_user_campaign_fields(
        cid, call.from_user.id,
        buttons_json=json.dumps(buttons) if buttons else None,
    )
    if ok:
        await call.answer(t("u8_edit_saved_notice", lang), show_alert=False)
    else:
        await call.answer(t("u8_edit_failed", lang).format(reason=reason), show_alert=True)
    await state.update_data(edit_buttons=[])
    await state.set_state(UserCampaignEdit.menu)
    await call.message.edit_text(
        t("u8_edit_title", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=_build_edit_menu_kb(cid, lang),
    )


@router.callback_query(F.data.startswith("u8_skip_buttons_"))
async def cb_skip_buttons(call: types.CallbackQuery, state: FSMContext):
    lang = await get_lang(call.from_user.id)
    data = await state.get_data()
    cid = data["edit_cid"]
    ok, reason = await update_user_campaign_fields(cid, call.from_user.id, buttons_json=None)
    if ok:
        await call.answer(t("u8_edit_saved_notice", lang), show_alert=False)
    else:
        await call.answer(t("u8_edit_failed", lang).format(reason=reason), show_alert=True)
    await state.set_state(UserCampaignEdit.menu)
    await call.message.edit_text(
        t("u8_edit_title", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=_build_edit_menu_kb(cid, lang),
    )


# ── Live Edit: Groups ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("u8_edit_groups_"))
async def cb_edit_groups_prompt(call: types.CallbackQuery, state: FSMContext):
    lang = await get_lang(call.from_user.id)
    cid = int(call.data.split("_")[-1])
    groups = await get_user_active_groups(call.from_user.id)
    if not groups:
        await call.answer(t("u8_relaunch_no_groups", lang), show_alert=True)
        return

    data = await state.get_data()
    # Pre-select current targets
    camp = await get_current_campaign(call.from_user.id)
    current_ids = set(extract_campaign_target_ids(camp)) if camp else set()

    rows_kb = []
    for gid, title, health in groups:
        icon = "✅" if gid in current_ids else "⬜"
        rows_kb.append([types.InlineKeyboardButton(
            text=f"{icon} {html.escape(title)}",
            callback_data=f"u8_grp_toggle_{gid}_{cid}",
        )])
    rows_kb.append([
        types.InlineKeyboardButton(text=t("uc_btn_select_all", lang), callback_data=f"u8_grp_all_{cid}"),
        types.InlineKeyboardButton(text=t("uc_btn_clear_all", lang), callback_data=f"u8_grp_none_{cid}"),
    ])
    rows_kb.append([
        types.InlineKeyboardButton(text=t("uc_btn_confirm_groups", lang), callback_data=f"u8_grp_confirm_{cid}"),
    ])
    await state.update_data(edit_cid=cid, grp_selected=list(current_ids))
    await state.set_state(UserCampaignEdit.groups)
    await call.message.edit_text(t("uc_step4_groups_prompt", lang), reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows_kb))
    await call.answer()


@router.callback_query(F.data.startswith("u8_grp_toggle_"))
async def cb_grp_toggle(call: types.CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    gid = int(parts[3])
    cid = int(parts[4])
    data = await state.get_data()
    selected = data.get("grp_selected", [])
    if gid in selected:
        selected.remove(gid)
    else:
        selected.append(gid)
    await state.update_data(grp_selected=selected)
    await call.answer()
    await _refresh_group_kb(call, state, cid)


@router.callback_query(F.data.startswith("u8_grp_all_"))
async def cb_grp_all(call: types.CallbackQuery, state: FSMContext):
    cid = int(call.data.split("_")[-1])
    groups = await get_user_active_groups(call.from_user.id)
    await state.update_data(grp_selected=[g[0] for g in groups])
    await call.answer()
    await _refresh_group_kb(call, state, cid)


@router.callback_query(F.data.startswith("u8_grp_none_"))
async def cb_grp_none(call: types.CallbackQuery, state: FSMContext):
    cid = int(call.data.split("_")[-1])
    await state.update_data(grp_selected=[])
    await call.answer()
    await _refresh_group_kb(call, state, cid)


async def _refresh_group_kb(call: types.CallbackQuery, state: FSMContext, cid: int):
    lang = await get_lang(call.from_user.id)
    data = await state.get_data()
    selected = set(data.get("grp_selected", []))
    groups = await get_user_active_groups(call.from_user.id)
    rows_kb = []
    for gid, title, health in groups:
        icon = "✅" if gid in selected else "⬜"
        rows_kb.append([types.InlineKeyboardButton(
            text=f"{icon} {html.escape(title)}",
            callback_data=f"u8_grp_toggle_{gid}_{cid}",
        )])
    rows_kb.append([
        types.InlineKeyboardButton(text=t("uc_btn_select_all", lang), callback_data=f"u8_grp_all_{cid}"),
        types.InlineKeyboardButton(text=t("uc_btn_clear_all", lang), callback_data=f"u8_grp_none_{cid}"),
    ])
    rows_kb.append([
        types.InlineKeyboardButton(text=t("uc_btn_confirm_groups", lang), callback_data=f"u8_grp_confirm_{cid}"),
    ])
    await call.message.edit_reply_markup(reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows_kb))


@router.callback_query(F.data.startswith("u8_grp_confirm_"))
async def cb_grp_confirm(call: types.CallbackQuery, state: FSMContext):
    lang = await get_lang(call.from_user.id)
    cid = int(call.data.split("_")[-1])
    data = await state.get_data()
    selected = data.get("grp_selected", [])
    if not selected:
        await call.answer(t("u8_relaunch_no_groups", lang), show_alert=True)
        return
    ok, reason = await update_user_campaign_fields(cid, call.from_user.id, target_chat_ids=selected)
    if ok:
        await call.answer(t("u8_edit_saved_notice", lang), show_alert=False)
    else:
        await call.answer(t("u8_edit_failed", lang).format(reason=reason), show_alert=True)
    await state.set_state(UserCampaignEdit.menu)
    await call.message.edit_text(
        t("u8_edit_title", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=_build_edit_menu_kb(cid, lang),
    )


# ── Live Edit: Mode / Auto-Delete ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("u8_edit_mode_"))
async def cb_edit_mode_prompt(call: types.CallbackQuery, state: FSMContext):
    lang = await get_lang(call.from_user.id)
    cid = int(call.data.split("_")[-1])
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=t("uc_btn_immediate", lang), callback_data=f"u8_mode_imm_{cid}")],
        [
            types.InlineKeyboardButton(text="🔄 6h",  callback_data=f"u8_mode_rec_6_{cid}"),
            types.InlineKeyboardButton(text="🔄 12h", callback_data=f"u8_mode_rec_12_{cid}"),
            types.InlineKeyboardButton(text="🔄 24h", callback_data=f"u8_mode_rec_24_{cid}"),
            types.InlineKeyboardButton(text="🔄 48h", callback_data=f"u8_mode_rec_48_{cid}"),
        ],
        [types.InlineKeyboardButton(text=t("btn_back", lang), callback_data="u8_back_edit_menu")],
    ])
    await call.message.edit_reply_markup(reply_markup=kb)
    await state.update_data(edit_cid=cid)
    await state.set_state(UserCampaignEdit.mode)
    await call.answer()


@router.callback_query(F.data.startswith("u8_mode_imm_"))
async def cb_mode_immediate(call: types.CallbackQuery, state: FSMContext):
    lang = await get_lang(call.from_user.id)
    cid = int(call.data.split("_")[-1])
    ok, reason = await update_user_campaign_fields(cid, call.from_user.id, mode="immediate", repeat_hours=None)
    if ok:
        await call.answer(t("u8_edit_saved_notice", lang))
    else:
        await call.answer(t("u8_edit_failed", lang).format(reason=reason), show_alert=True)
    await state.set_state(UserCampaignEdit.menu)
    await call.message.edit_text(t("u8_edit_title", lang), parse_mode=ParseMode.HTML, reply_markup=_build_edit_menu_kb(cid, lang))


@router.callback_query(F.data.startswith("u8_mode_rec_"))
async def cb_mode_recurring(call: types.CallbackQuery, state: FSMContext):
    lang = await get_lang(call.from_user.id)
    parts = call.data.split("_")
    hours = int(parts[3])
    cid = int(parts[4])
    ok, reason = await update_user_campaign_fields(cid, call.from_user.id, mode="recurring", repeat_hours=hours)
    if ok:
        await call.answer(t("u8_edit_saved_notice", lang))
    else:
        await call.answer(t("u8_edit_failed", lang).format(reason=reason), show_alert=True)
    await state.set_state(UserCampaignEdit.menu)
    await call.message.edit_text(t("u8_edit_title", lang), parse_mode=ParseMode.HTML, reply_markup=_build_edit_menu_kb(cid, lang))


@router.callback_query(F.data.startswith("u8_edit_autodel_"))
async def cb_edit_autodel_prompt(call: types.CallbackQuery, state: FSMContext):
    lang = await get_lang(call.from_user.id)
    cid = int(call.data.split("_")[-1])
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text=t("uc_btn_autodel_none", lang), callback_data=f"u8_autodel_0_{cid}"),
            types.InlineKeyboardButton(text="1h",  callback_data=f"u8_autodel_3600_{cid}"),
            types.InlineKeyboardButton(text="6h",  callback_data=f"u8_autodel_21600_{cid}"),
            types.InlineKeyboardButton(text="24h", callback_data=f"u8_autodel_86400_{cid}"),
        ],
        [types.InlineKeyboardButton(text=t("btn_back", lang), callback_data="u8_back_edit_menu")],
    ])
    await call.message.edit_reply_markup(reply_markup=kb)
    await state.update_data(edit_cid=cid)
    await state.set_state(UserCampaignEdit.auto_delete)
    await call.answer()


@router.callback_query(F.data.startswith("u8_autodel_"))
async def cb_autodel_pick(call: types.CallbackQuery, state: FSMContext):
    lang = await get_lang(call.from_user.id)
    parts = call.data.split("_")
    secs = int(parts[2])
    cid = int(parts[3])
    ok, reason = await update_user_campaign_fields(cid, call.from_user.id, auto_delete_seconds=secs or None)
    if ok:
        await call.answer(t("u8_edit_saved_notice", lang))
    else:
        await call.answer(t("u8_edit_failed", lang).format(reason=reason), show_alert=True)
    await state.set_state(UserCampaignEdit.menu)
    await call.message.edit_text(t("u8_edit_title", lang), parse_mode=ParseMode.HTML, reply_markup=_build_edit_menu_kb(cid, lang))


@router.callback_query(F.data == "u8_back_edit_menu")
async def cb_back_edit_menu(call: types.CallbackQuery, state: FSMContext):
    lang = await get_lang(call.from_user.id)
    data = await state.get_data()
    cid = data.get("edit_cid", 0)
    await state.set_state(UserCampaignEdit.menu)
    await call.message.edit_text(t("u8_edit_title", lang), parse_mode=ParseMode.HTML, reply_markup=_build_edit_menu_kb(cid, lang))
    await call.answer()


# ── 🗂 Campaign History ───────────────────────────────────────────────────────

@router.callback_query(F.data == "user_campaign_history")
async def cb_campaign_history(call: types.CallbackQuery):
    lang = await get_lang(call.from_user.id)
    history = await get_user_campaign_history(call.from_user.id, limit=10)
    if not history:
        await call.answer(t("u8_hist_empty", lang), show_alert=True)
        return

    text = t("u8_hist_title", lang)
    rows_kb = []
    for camp in history:
        status_label = _status_label(camp["status"], lang)
        btn_label = t("u8_hist_item_btn", lang).format(
            cid=camp["id"],
            status=camp["status"],
            date=str(camp["created_at"])[:10] if camp["created_at"] else "?",
        )
        rows_kb.append([types.InlineKeyboardButton(
            text=btn_label,
            callback_data=f"u8_hist_detail_{camp['id']}",
        )])

    rows_kb.append([types.InlineKeyboardButton(text=t("btn_back", lang), callback_data="user_my_stats")])
    await call.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows_kb))
    await call.answer()


@router.callback_query(F.data.startswith("u8_hist_detail_"))
async def cb_hist_detail(call: types.CallbackQuery):
    lang = await get_lang(call.from_user.id)
    cid = int(call.data.split("_")[-1])
    history = await get_user_campaign_history(call.from_user.id, limit=10)
    camp = next((c for c in history if c["id"] == cid), None)
    if not camp:
        await call.answer(t("u8_camp_not_found", lang), show_alert=True)
        return

    text = t("u8_hist_detail", lang).format(
        cid=camp["id"],
        status_label=_status_label(camp["status"], lang),
        created_at=str(camp["created_at"])[:16] if camp["created_at"] else "?",
        mode_label=_mode_label(camp, lang),
        ok=camp["sent_ok"],
        fail=camp["sent_fail"],
    )
    rows_kb = [
        [types.InlineKeyboardButton(text=t("u8_btn_relaunch", lang), callback_data=f"user_relaunch_camp_{cid}")],
        [types.InlineKeyboardButton(text=t("u8_btn_back_history", lang), callback_data="user_campaign_history")],
    ]
    await call.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows_kb))
    await call.answer()


# ── ♻️ 1-Click Relaunch ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("user_relaunch_camp_"))
async def cb_relaunch(call: types.CallbackQuery, state: FSMContext):
    lang = await get_lang(call.from_user.id)
    cid = int(call.data.split("_")[-1])
    history = await get_user_campaign_history(call.from_user.id, limit=10)
    camp = next((c for c in history if c["id"] == cid), None)
    if not camp:
        await call.answer(t("u8_camp_not_found", lang), show_alert=True)
        return

    # Load groups
    groups = await get_user_active_groups(call.from_user.id)
    if not groups:
        await call.answer(t("u8_relaunch_no_groups", lang), show_alert=True)
        return

    # Pre-fill wizard state with old campaign data and jump to confirm
    buttons_raw = []
    if camp.get("buttons_json"):
        try:
            buttons_raw = json.loads(camp["buttons_json"])
        except Exception:
            buttons_raw = []

    group_ids = [g[0] for g in groups]

    await state.update_data(
        text=camp.get("text"),
        photo_file_id=camp.get("photo_file_id"),
        buttons=buttons_raw,
        group_ids=group_ids,
        mode=camp.get("mode", "immediate"),
        repeat_hours=camp.get("repeat_hours"),
        auto_delete_seconds=None,
    )
    await state.set_state(UserCampaignWizard.confirm)
    await call.answer(t("u8_relaunch_ready_toast", lang), show_alert=True)
    # Notify user to proceed to confirm
    await call.message.answer(
        t("u8_relaunch_ready_toast", lang),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[
            types.InlineKeyboardButton(text=t("uc_btn_confirm_launch", lang), callback_data="ucw_confirm_launch"),
            types.InlineKeyboardButton(text=t("uc_btn_edit_campaign", lang), callback_data="ucw_edit_menu"),
        ]]),
    )


# ── 🔄 Groups Health Check ────────────────────────────────────────────────────

@router.callback_query(F.data == "user_check_groups_health")
async def cb_check_groups_health(call: types.CallbackQuery, bot: Bot):
    lang = await get_lang(call.from_user.id)
    await call.answer()

    groups = await get_user_active_groups(call.from_user.id)
    if not groups:
        await call.message.edit_text(t("u8_relaunch_no_groups", lang))
        return

    ok_count = bad_count = 0
    for gid, title, old_health in groups:
        try:
            new_status = await _check_group_health(bot, gid)
        except Exception:
            new_status = "no_permission"
        # Update DB health_status
        await upsert_group(gid, title, "supergroup")
        from core.database import get_db
        async with get_db() as db:
            await db.execute(
                "UPDATE groups SET health_status=?, last_checked_at=datetime('now') WHERE chat_id=?",
                (new_status, gid),
            )
            await db.commit()
        if new_status == "ok":
            ok_count += 1
        else:
            bad_count += 1

    await call.message.answer(
        t("u8_health_check_done", lang).format(
            total=ok_count + bad_count,
            ok=ok_count,
            bad=bad_count,
        )
    )
