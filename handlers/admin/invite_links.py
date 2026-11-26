"""
Handlers for:
  1. Bot Owner Invite Links Management (permanent/temporary, pause/resume, delete) — Bilingual AR/EN
  2. Regular User Permanent Referral Link — Bilingual AR/EN
Phase 6: Full i18n using t(key, lang) for all UI strings.
"""

import html
from urllib.parse import quote

from aiogram import Router, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.bot import bot
from core.config import ADMIN_ID, BOT_USERNAME
from core.i18n import get_lang, t
from states.states import AdminEdit
from models.invite_links import (
    create_owner_invite_link,
    get_owner_invite_link,
    list_owner_invite_links,
    set_owner_invite_status,
    delete_owner_invite_link,
    get_or_create_user_referral,
)

router = Router(name="invite_links")


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _safe_edit_or_answer(
    message: types.Message, text: str, kb: InlineKeyboardMarkup | None = None
) -> None:
    """Safely edit a text or media-caption message, falling back to answer()."""
    is_media = bool(
        getattr(message, "photo", None)
        or getattr(message, "video", None)
        or getattr(message, "caption", None) is not None
    )
    try:
        if is_media:
            await message.edit_caption(caption=text, reply_markup=kb, parse_mode=ParseMode.HTML)
        else:
            await message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception:
        await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


async def _get_bot_username() -> str:
    try:
        me = await bot.get_me()
        if getattr(me, "username", None):
            return me.username
    except Exception:
        pass
    return BOT_USERNAME or "bot"


async def _resolve_lang(user_obj) -> str:
    uid = getattr(user_obj, "id", None)
    tg_code = getattr(user_obj, "language_code", None)
    return await get_lang(uid if isinstance(uid, int) else None, tg_code)


def _status_label(effective_status: str, lang: str) -> str:
    key_map = {
        "active": "inv_status_active",
        "paused": "inv_status_paused",
        "expired": "inv_status_expired",
    }
    return t(key_map.get(effective_status, "inv_status_active"), lang)


def _is_owner(user_id: int) -> bool:
    return int(user_id) == int(ADMIN_ID)


# ── Referral button label (used by handlers/start.py) ────────────────────────

# Legacy 15-language map (kept for backward compat with start.py import)
_REFERRAL_BTN_LABELS = {
    "ar": "🔗 رابط الاحالة الخاص بي",
    "en": "🔗 My Referral Link",
    "fa": "🔗 لینک معرفی من",
    "tr": "🔗 Referans Linklerim",
    "es": "🔗 Mi enlace de referencia",
    "ru": "🔗 Моя реферальная ссылка",
    "id": "🔗 Link Referral Saya",
    "hi": "🔗 मेरा रेफरल लिंक",
    "pt": "🔗 Meu link de indicação",
    "it": "🔗 Il mio link referral",
    "nl": "🔗 Mijn verwijzingslink",
    "uk": "🔗 Моє реферальне посилання",
}


def get_referral_btn_label(language_code: str | None) -> str:
    """Return the referral button label in the user's language (falls back to English)."""
    lang = (language_code or "en").split("-")[0].lower()
    return _REFERRAL_BTN_LABELS.get(lang, _REFERRAL_BTN_LABELS["en"])


# ── A. User Permanent Referral Link ──────────────────────────────────────────

@router.callback_query(F.data == "user_my_referral")
async def cb_user_my_referral(callback: types.CallbackQuery):
    """
    Shows the user's permanent referral link in their chosen language.
    """
    user_id = callback.from_user.id
    lang = await _resolve_lang(callback.from_user)
    ref = await get_or_create_user_referral(user_id)
    bot_username = await _get_bot_username()
    ref_url = f"https://t.me/{bot_username}?start=ref_{ref['ref_code']}"
    share_url = (
        f"https://t.me/share/url?url={quote(ref_url)}"
        f"&text={quote(t('referral_share_text', lang))}"
    )

    text = t("referral_body", lang, url=html.escape(ref_url), count=ref["referrals_count"])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_share_link", lang), url=share_url)],
        [InlineKeyboardButton(text=t("btn_back", lang), callback_data="start_back")],
    ])
    await _safe_edit_or_answer(callback.message, text, kb)
    try:
        await callback.answer()
    except Exception:
        pass


# ── B. Owner Invite Links Management ─────────────────────────────────────────

async def _render_link_detail(
    target_msg: types.Message, link_id: int, lang: str, prefix_notice: str = ""
) -> None:
    lnk = await get_owner_invite_link(link_id)
    if not lnk:
        await _safe_edit_or_answer(
            target_msg,
            t("inv_not_found", lang),
            InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t("btn_back", lang), callback_data="admin_invite_links")]
            ]),
        )
        return

    bot_username = await _get_bot_username()
    full_url = f"https://t.me/{bot_username}?start=inv_{lnk['code']}"
    raw_title = lnk.get("label") or t("inv_default_title", lang, id=lnk["id"])
    title = html.escape(str(raw_title))
    type_text = t(
        "inv_type_permanent" if lnk["link_type"] == "permanent" else "inv_type_temporary", lang
    )
    status_text = _status_label(lnk["effective_status"], lang)
    exp_line = (
        t("inv_exp_line", lang, expires_at=lnk["expires_at"])
        if lnk["link_type"] == "temporary" and lnk.get("expires_at")
        else ""
    )
    text = t(
        "inv_detail_body", lang,
        prefix=prefix_notice, title=title, url=html.escape(full_url),
        type_text=type_text, status_text=status_text, exp_line=exp_line,
        clicks=lnk["clicks_count"], joins=lnk["joins_count"], created_at=lnk["created_at"],
    )

    kb_rows = []
    if lnk["status"] == "active":
        kb_rows.append([InlineKeyboardButton(
            text=t("inv_btn_pause", lang), callback_data=f"owner_inv_pause_{lnk['id']}"
        )])
    else:
        kb_rows.append([InlineKeyboardButton(
            text=t("inv_btn_resume", lang), callback_data=f"owner_inv_resume_{lnk['id']}"
        )])
    kb_rows.append([InlineKeyboardButton(
        text=t("inv_btn_delete", lang), callback_data=f"owner_inv_del_ask_{lnk['id']}"
    )])
    kb_rows.append([InlineKeyboardButton(
        text=t("inv_btn_back_list", lang), callback_data="admin_invite_links"
    )])
    await _safe_edit_or_answer(target_msg, text, InlineKeyboardMarkup(inline_keyboard=kb_rows))


@router.callback_query(F.data == "admin_invite_links")
async def cb_admin_invite_links(callback: types.CallbackQuery, state: FSMContext | None = None):
    lang = await _resolve_lang(callback.from_user)
    if not _is_owner(callback.from_user.id):
        return await callback.answer(t("inv_owner_only", lang), show_alert=True)
    if state:
        await state.clear()

    links = await list_owner_invite_links()
    text = t("inv_list_title", lang)
    kb_rows = [[InlineKeyboardButton(text=t("inv_btn_create", lang), callback_data="owner_inv_create")]]

    if not links:
        text += t("inv_list_empty", lang)
    else:
        text += t("inv_list_choose", lang)
        for lnk in links[:15]:
            st_text = _status_label(lnk["effective_status"], lang)
            st_icon = st_text.split()[0]
            type_label = t(
                "inv_type_permanent" if lnk["link_type"] == "permanent" else "inv_type_temporary", lang
            )
            raw_title = lnk.get("label") or t("inv_default_title", lang, id=lnk["id"])
            title = html.escape(str(raw_title)[:25])
            text += t(
                "inv_list_item", lang,
                icon=st_icon, title=title, type_label=type_label,
                joins=lnk["joins_count"], clicks=lnk["clicks_count"],
            )
            kb_rows.append([InlineKeyboardButton(
                text=t("inv_list_btn_item", lang, icon=st_icon, title=str(raw_title)[:20], joins=lnk["joins_count"]),
                callback_data=f"owner_inv_view_{lnk['id']}",
            )])

    kb_rows.append([InlineKeyboardButton(text=t("admin_btn_back", lang), callback_data="admin_main")])
    await _safe_edit_or_answer(callback.message, text, InlineKeyboardMarkup(inline_keyboard=kb_rows))
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "owner_inv_create")
async def cb_owner_inv_create(callback: types.CallbackQuery, state: FSMContext):
    lang = await _resolve_lang(callback.from_user)
    if not _is_owner(callback.from_user.id):
        return await callback.answer(t("inv_owner_only_short", lang), show_alert=True)
    await state.clear()
    await state.set_state(AdminEdit.waiting_for_inv_label)
    await callback.message.answer(t("inv_create_prompt", lang), parse_mode=ParseMode.HTML)
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(AdminEdit.waiting_for_inv_label)
async def process_owner_inv_label(message: types.Message, state: FSMContext):
    lang = await _resolve_lang(message.from_user)
    if not _is_owner(message.from_user.id):
        return
    if not message.text:
        return await message.answer(t("inv_label_invalid", lang))
    if message.text.strip() == "/cancel":
        await state.clear()
        return await message.answer(t("inv_create_cancelled", lang))

    label = None if message.text.strip() == "/skip" else message.text.strip()[:60]
    await state.update_data(inv_label=label)
    await state.set_state(AdminEdit.waiting_for_inv_type)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("inv_btn_type_perm", lang), callback_data="owner_inv_type_perm")],
        [InlineKeyboardButton(text=t("inv_btn_type_temp", lang), callback_data="owner_inv_type_temp")],
        [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="admin_invite_links")],
    ])
    await message.answer(t("inv_choose_type_prompt", lang), reply_markup=kb, parse_mode=ParseMode.HTML)


@router.callback_query(
    AdminEdit.waiting_for_inv_type,
    F.data.in_({"owner_inv_type_perm", "owner_inv_type_temp"}),
)
async def cb_owner_inv_type(callback: types.CallbackQuery, state: FSMContext):
    lang = await _resolve_lang(callback.from_user)
    if not _is_owner(callback.from_user.id):
        return await callback.answer(t("inv_owner_only_short", lang), show_alert=True)

    data = await state.get_data()
    label = data.get("inv_label")

    if callback.data == "owner_inv_type_perm":
        await state.clear()
        created = await create_owner_invite_link(
            label=label, link_type="permanent", duration_hours=None, created_by=callback.from_user.id
        )
        await _render_link_detail(
            callback.message, created["id"], lang=lang,
            prefix_notice=t("inv_created_perm_notice", lang),
        )
        try:
            await callback.answer(t("inv_created_perm_toast", lang))
        except Exception:
            pass
        return

    # Temporary — ask duration
    await state.set_state(AdminEdit.waiting_for_inv_hours)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t("inv_dur_1h", lang), callback_data="owner_inv_dur_1"),
            InlineKeyboardButton(text=t("inv_dur_6h", lang), callback_data="owner_inv_dur_6"),
        ],
        [
            InlineKeyboardButton(text=t("inv_dur_24h", lang), callback_data="owner_inv_dur_24"),
            InlineKeyboardButton(text=t("inv_dur_168h", lang), callback_data="owner_inv_dur_168"),
        ],
        [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="admin_invite_links")],
    ])
    await _safe_edit_or_answer(callback.message, t("inv_choose_hours_prompt", lang), kb)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(AdminEdit.waiting_for_inv_hours, F.data.startswith("owner_inv_dur_"))
async def cb_owner_inv_dur_preset(callback: types.CallbackQuery, state: FSMContext):
    lang = await _resolve_lang(callback.from_user)
    if not _is_owner(callback.from_user.id):
        return await callback.answer(t("inv_owner_only_short", lang), show_alert=True)
    hours = int(callback.data.replace("owner_inv_dur_", ""))
    data = await state.get_data()
    label = data.get("inv_label")
    await state.clear()
    created = await create_owner_invite_link(
        label=label, link_type="temporary", duration_hours=hours, created_by=callback.from_user.id
    )
    await _render_link_detail(
        callback.message, created["id"], lang=lang,
        prefix_notice=t("inv_created_temp_notice", lang, hours=hours),
    )
    try:
        await callback.answer(t("inv_created_temp_toast", lang))
    except Exception:
        pass


@router.message(AdminEdit.waiting_for_inv_hours)
async def process_owner_inv_hours(message: types.Message, state: FSMContext):
    lang = await _resolve_lang(message.from_user)
    if not _is_owner(message.from_user.id):
        return
    if not message.text:
        return await message.answer(t("inv_hours_invalid_type", lang))
    if message.text.strip() == "/cancel":
        await state.clear()
        return await message.answer(t("admin_cancelled", lang))
    raw = message.text.strip()
    if not raw.isdigit() or not (1 <= int(raw) <= 8760):
        return await message.answer(t("inv_hours_invalid_range", lang))
    hours = int(raw)
    data = await state.get_data()
    label = data.get("inv_label")
    await state.clear()
    created = await create_owner_invite_link(
        label=label, link_type="temporary", duration_hours=hours, created_by=message.from_user.id
    )
    await _render_link_detail(
        message, created["id"], lang=lang,
        prefix_notice=t("inv_created_temp_notice", lang, hours=hours),
    )


@router.callback_query(F.data.startswith("owner_inv_view_"))
async def cb_owner_inv_view(callback: types.CallbackQuery):
    lang = await _resolve_lang(callback.from_user)
    if not _is_owner(callback.from_user.id):
        return await callback.answer(t("inv_owner_only_short", lang), show_alert=True)
    link_id = int(callback.data.replace("owner_inv_view_", ""))
    await _render_link_detail(callback.message, link_id, lang=lang)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("owner_inv_pause_"))
async def cb_owner_inv_pause(callback: types.CallbackQuery):
    lang = await _resolve_lang(callback.from_user)
    if not _is_owner(callback.from_user.id):
        return await callback.answer(t("inv_owner_only_short", lang), show_alert=True)
    link_id = int(callback.data.replace("owner_inv_pause_", ""))
    await set_owner_invite_status(link_id, "paused")
    await _render_link_detail(
        callback.message, link_id, lang=lang, prefix_notice=t("inv_paused_notice", lang)
    )
    try:
        await callback.answer(t("inv_paused_toast", lang))
    except Exception:
        pass


@router.callback_query(F.data.startswith("owner_inv_resume_"))
async def cb_owner_inv_resume(callback: types.CallbackQuery):
    lang = await _resolve_lang(callback.from_user)
    if not _is_owner(callback.from_user.id):
        return await callback.answer(t("inv_owner_only_short", lang), show_alert=True)
    link_id = int(callback.data.replace("owner_inv_resume_", ""))
    await set_owner_invite_status(link_id, "active")
    await _render_link_detail(
        callback.message, link_id, lang=lang, prefix_notice=t("inv_resumed_notice", lang)
    )
    try:
        await callback.answer(t("inv_resumed_toast", lang))
    except Exception:
        pass


@router.callback_query(F.data.startswith("owner_inv_del_ask_"))
async def cb_owner_inv_del_ask(callback: types.CallbackQuery):
    lang = await _resolve_lang(callback.from_user)
    if not _is_owner(callback.from_user.id):
        return await callback.answer(t("inv_owner_only_short", lang), show_alert=True)
    link_id = int(callback.data.replace("owner_inv_del_ask_", ""))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=t("inv_btn_del_confirm", lang),
            callback_data=f"owner_inv_del_confirm_{link_id}",
        )],
        [InlineKeyboardButton(
            text=t("inv_btn_del_cancel", lang),
            callback_data=f"owner_inv_view_{link_id}",
        )],
    ])
    await _safe_edit_or_answer(
        callback.message, t("inv_del_confirm_prompt", lang, id=link_id), kb
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("owner_inv_del_confirm_"))
async def cb_owner_inv_del_confirm(callback: types.CallbackQuery, state: FSMContext):
    lang = await _resolve_lang(callback.from_user)
    if not _is_owner(callback.from_user.id):
        return await callback.answer(t("inv_owner_only_short", lang), show_alert=True)
    link_id = int(callback.data.replace("owner_inv_del_confirm_", ""))
    await delete_owner_invite_link(link_id)
    try:
        await callback.answer(t("inv_deleted_toast", lang))
    except Exception:
        pass
    await cb_admin_invite_links(callback, state)
