"""
Handlers for:
  1. Bot Owner Invite Links Management (permanent/temporary, manual pause/resume, delete)
  2. Regular User "🔗 رابط الاحالة الخاص بي" button (background generation on first click, permanent access)
"""

import html
from urllib.parse import quote
from aiogram import Router, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.bot import bot
from core.config import ADMIN_ID, BOT_USERNAME
from states.states import AdminEdit
from models.invite_links import (
    create_owner_invite_link,
    get_owner_invite_link,
    list_owner_invite_links,
    set_owner_invite_status,
    delete_owner_invite_link,
    get_or_create_user_referral,
)

router = Router()

STATUS_LABELS = {
    "active": "🟢 نشط",
    "paused": "⏸ متوقف يدوياً",
    "expired": "⌛️ منتهي الصلاحية",
}

# ── Referral button label translations ───────────────────────────────────────
_REFERRAL_BTN_LABELS = {
    "ar": "🔗 رابط الاحالة الخاص بي",
    "en": "🔗 My Referral Link",
    "fa": "🔗 لینک معرفی من",
    "tr": "🔗 Referans Linklerim",
    "fr": "🔗 Mon lien de parrainage",
    "de": "🔗 Mein Empfehlungslink",
    "es": "🔗 Mi enlace de referencia",
    "ru": "🔗 Моя реферальная ссылка",
    "id": "🔗 Link Referral Saya",
    "hi": "🔗 मेरा रेफरल लिंक",
    "pt": "🔗 Meu link de indicação",
    "it": "🔗 Il mio link referral",
    "nl": "🔗 Mijn verwijzingslink",
    "uk": "🔗 Моє реферальне посилання",
    "pl": "🔗 Mój link polecający",
}

def get_referral_btn_label(language_code: str | None) -> str:
    """Return the referral button label in the user's language (falls back to English)."""
    lang = (language_code or "en").split("-")[0].lower()
    return _REFERRAL_BTN_LABELS.get(lang, _REFERRAL_BTN_LABELS["en"])


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


# ── A. User Permanent Referral Link ("🔗 رابط الاحالة الخاص بي") ──────────────

@router.callback_query(F.data == "user_my_referral")
async def cb_user_my_referral(callback: types.CallbackQuery):
    """
    On first click: generates a permanent referral link for the user in the background.
    On every click: retrieves and displays the permanent referral link immediately.
    """
    user_id = callback.from_user.id
    lang = getattr(callback.from_user, "language_code", None)
    ref = await get_or_create_user_referral(user_id)
    bot_username = await _get_bot_username()
    ref_url = f"https://t.me/{bot_username}?start=ref_{ref['ref_code']}"

    # Localised share text
    _share_texts = {
        "ar": "انضم عبر رابط الإحالة الخاص بي!",
        "en": "Join using my referral link!",
        "fa": "از لینک معرفی من استفاده کن!",
        "tr": "Referans linkimle katıl!",
        "fr": "Rejoins via mon lien de parrainage!",
        "de": "Tritt über meinen Empfehlungslink bei!",
        "es": "¡Únete con mi enlace de referencia!",
        "ru": "Присоединяйся по моей реферальной ссылке!",
    }
    lang_key = (lang or "en").split("-")[0].lower()
    share_text = _share_texts.get(lang_key, _share_texts["en"])
    share_url = f"https://t.me/share/url?url={quote(ref_url)}&text={quote(share_text)}"

    # Localised page labels
    _page_labels = {
        "ar": ("🔗 <b>رابط الإحالة الخاص بك (دائم):</b>", "👥 <b>عدد المنضمين عبر رابطك:</b>", "💡 <i>اضغط على الرابط لنسخه. يمكنك الوصول إليه دائماً عبر هذا الزر.</i>", "📤 مشاركة الرابط", "🔙 رجوع"),
        "en": ("🔗 <b>Your permanent referral link:</b>", "👥 <b>Users joined via your link:</b>", "💡 <i>Tap the link to copy it. You can always access it from this button.</i>", "📤 Share Link", "🔙 Back"),
    }
    lbl = _page_labels.get(lang_key, _page_labels["en"])

    text = (
        f"{lbl[0]}\n\n"
        f"<code>{html.escape(ref_url)}</code>\n\n"
        f"{lbl[1]} {ref['referrals_count']}\n\n"
        f"{lbl[2]}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lbl[3], url=share_url)],
        [InlineKeyboardButton(text=lbl[4], callback_data="start_back")],
    ])
    await _safe_edit_or_answer(callback.message, text, kb)
    try:
        await callback.answer()
    except Exception:
        pass


# ── B. Owner Invite Links Management (Strictly ADMIN_ID) ─────────────────────

def _is_owner(user_id: int) -> bool:
    return int(user_id) == int(ADMIN_ID)


@router.callback_query(F.data == "admin_invite_links")
async def cb_admin_invite_links(callback: types.CallbackQuery, state: FSMContext | None = None):
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔️ هذا القسم مخصص لمالك البوت فقط.", show_alert=True)
    if state:
        await state.clear()

    links = await list_owner_invite_links()
    text = "🔗 <b>إدارة روابط دعوة البوت (للمالك):</b>\n\n"
    kb_rows = [
        [InlineKeyboardButton(text="➕ توليد رابط دعوة جديد", callback_data="owner_inv_create")]
    ]

    if not links:
        text += "لا توجد روابط دعوة مولدة حتى الآن."
    else:
        text += "اختر رابطاً من القائمة لعرض تفاصيله أو إيقافه أو حذفه:\n\n"
        for lnk in links[:15]:
            st_icon = STATUS_LABELS.get(lnk["effective_status"], "🟢").split()[0]
            type_label = "♾ دائم" if lnk["link_type"] == "permanent" else "⏳ مؤقت"
            title = html.escape((lnk.get("label") or f"رابط #{lnk['id']}")[:25])
            text += (
                f"{st_icon} <b>{title}</b> ({type_label}) — "
                f"المنضمون: <b>{lnk['joins_count']}</b> | النقرات: {lnk['clicks_count']}\n"
            )
            lnk_id = lnk["id"]
            lnk_label = lnk.get("label") or f"رابط #{lnk_id}"
            lnk_joins = lnk["joins_count"]
            kb_rows.append([
                InlineKeyboardButton(
                    text=f"{st_icon} {lnk_label[:20]} ({lnk_joins} منضم)",
                    callback_data=f"owner_inv_view_{lnk_id}",
                )
            ])

    kb_rows.append([InlineKeyboardButton(text="🔙 رجوع للوحة التحكم", callback_data="admin_main")])
    await _safe_edit_or_answer(callback.message, text, InlineKeyboardMarkup(inline_keyboard=kb_rows))
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "owner_inv_create")
async def cb_owner_inv_create(callback: types.CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔️ للمالك فقط.", show_alert=True)
    await state.clear()
    await state.set_state(AdminEdit.waiting_for_inv_label)
    await callback.message.answer(
        "🏷 <b>توليد رابط دعوة جديد</b>\n\n"
        "أرسل اسماً توضيحياً للرابط (مثلاً: <i>إعلان قناة التوصيات</i>)، أو أرسل /skip للتخطي.\n"
        "لإلغاء العملية أرسل /cancel",
        parse_mode=ParseMode.HTML,
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(AdminEdit.waiting_for_inv_label)
async def process_owner_inv_label(message: types.Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    if not message.text:
        return await message.answer("❌ يرجى إرسال اسم الرابط كنص أو /skip أو /cancel.")
    if message.text.strip() == "/cancel":
        await state.clear()
        return await message.answer("❌ تم إلغاء توليد الرابط.")

    label = None if message.text.strip() == "/skip" else message.text.strip()[:60]
    await state.update_data(inv_label=label)
    await state.set_state(AdminEdit.waiting_for_inv_type)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="♾ رابط دائم", callback_data="owner_inv_type_perm")],
        [InlineKeyboardButton(text="⏳ رابط مؤقت (بمدة محددة)", callback_data="owner_inv_type_temp")],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_invite_links")],
    ])
    await message.answer(
        "⚙️ <b>اختر نوع رابط الدعوة:</b>\n\n"
        "• <b>♾ دائم:</b> يعمل باستمرار حتى تقوم بإيقافه يدوياً أو حذفه.\n"
        "• <b>⏳ مؤقت:</b> ينتهي تلقائياً بعد عدد الساعات الذي تحدده (مع إمكانية إيقافه أو حذفه يدوياً أيضاً).",
        reply_markup=kb,
        parse_mode=ParseMode.HTML,
    )


async def _render_owner_link_details(
    target_msg: types.Message, link_id: int, prefix_notice: str = ""
) -> None:
    lnk = await get_owner_invite_link(link_id)
    if not lnk:
        await _safe_edit_or_answer(
            target_msg,
            "❌ هذا الرابط غير موجود أو تم حذفه.",
            InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_invite_links")]
            ]),
        )
        return

    bot_username = await _get_bot_username()
    full_url = f"https://t.me/{bot_username}?start=inv_{lnk['code']}"
    title = html.escape(lnk.get("label") or f"رابط #{lnk['id']}")
    type_text = "♾ دائم" if lnk["link_type"] == "permanent" else "⏳ مؤقت"
    status_text = STATUS_LABELS.get(lnk["effective_status"], lnk["effective_status"])
    exp_line = (
        f"⏰ <b>ينتهي في:</b> <code>{lnk['expires_at']}</code>\n"
        if lnk["link_type"] == "temporary" and lnk.get("expires_at")
        else ""
    )

    text = (
        f"{prefix_notice}"
        f"🔗 <b>تفاصيل رابط الدعوة: {title}</b>\n\n"
        f"📎 <b>الرابط:</b>\n<code>{html.escape(full_url)}</code>\n\n"
        f"📌 <b>النوع:</b> {type_text}\n"
        f"📊 <b>الحالة:</b> {status_text}\n"
        f"{exp_line}"
        f"👆 <b>إجمالي النقرات:</b> {lnk['clicks_count']}\n"
        f"👥 <b>المستخدمون المنضمون:</b> {lnk['joins_count']}\n"
        f"📅 <b>تاريخ الإنشاء:</b> <code>{lnk['created_at']}</code>"
    )

    kb_rows = []
    if lnk["status"] == "active":
        kb_rows.append([
            InlineKeyboardButton(
                text="⏸ إيقاف الرابط يدوياً",
                callback_data=f"owner_inv_pause_{lnk['id']}",
            )
        ])
    else:
        kb_rows.append([
            InlineKeyboardButton(
                text="▶️ إعادة تفعيل الرابط",
                callback_data=f"owner_inv_resume_{lnk['id']}",
            )
        ])

    kb_rows.append([
        InlineKeyboardButton(
            text="🗑 حذف الرابط نهائياً",
            callback_data=f"owner_inv_del_ask_{lnk['id']}",
        )
    ])
    kb_rows.append([
        InlineKeyboardButton(text="🔙 رجوع لقائمة الروابط", callback_data="admin_invite_links")
    ])
    await _safe_edit_or_answer(target_msg, text, InlineKeyboardMarkup(inline_keyboard=kb_rows))


@router.callback_query(
    AdminEdit.waiting_for_inv_type,
    F.data.in_({"owner_inv_type_perm", "owner_inv_type_temp"}),
)
async def cb_owner_inv_type(callback: types.CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔️ للمالك فقط.", show_alert=True)

    data = await state.get_data()
    label = data.get("inv_label")

    if callback.data == "owner_inv_type_perm":
        await state.clear()
        created = await create_owner_invite_link(
            label=label,
            link_type="permanent",
            duration_hours=None,
            created_by=callback.from_user.id,
        )
        await _render_owner_link_details(
            callback.message,
            created["id"],
            prefix_notice="✅ <b>تم توليد رابط الدعوة الدائم بنجاح!</b>\n\n",
        )
        try:
            await callback.answer("✅ تم توليد الرابط الدائم")
        except Exception:
            pass
        return

    # Temporary link -> ask for duration in hours
    await state.set_state(AdminEdit.waiting_for_inv_hours)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="ساعة واحدة (1h)", callback_data="owner_inv_dur_1"),
            InlineKeyboardButton(text="6 ساعات (6h)", callback_data="owner_inv_dur_6"),
        ],
        [
            InlineKeyboardButton(text="24 ساعة (1d)", callback_data="owner_inv_dur_24"),
            InlineKeyboardButton(text="7 أيام (168h)", callback_data="owner_inv_dur_168"),
        ],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_invite_links")],
    ])
    await _safe_edit_or_answer(
        callback.message,
        "⏳ <b>تحديد مدة الرابط المؤقت:</b>\n\n"
        "اختر مدة جاهزة من الأزرار أدناه، أو أرسل عدد الساعات رقماً (بين 1 و 8760):",
        kb,
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(
    AdminEdit.waiting_for_inv_hours,
    F.data.startswith("owner_inv_dur_"),
)
async def cb_owner_inv_duration_preset(callback: types.CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔️ للمالك فقط.", show_alert=True)
    hours = int(callback.data.replace("owner_inv_dur_", ""))
    data = await state.get_data()
    label = data.get("inv_label")
    await state.clear()

    created = await create_owner_invite_link(
        label=label,
        link_type="temporary",
        duration_hours=hours,
        created_by=callback.from_user.id,
    )
    await _render_owner_link_details(
        callback.message,
        created["id"],
        prefix_notice=f"✅ <b>تم توليد رابط الدعوة المؤقت ({hours} ساعة) بنجاح!</b>\n\n",
    )
    try:
        await callback.answer("✅ تم توليد الرابط المؤقت")
    except Exception:
        pass


@router.message(AdminEdit.waiting_for_inv_hours)
async def process_owner_inv_hours(message: types.Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    if not message.text:
        return await message.answer("❌ يرجى إرسال عدد الساعات كأرقام فقط (مثلاً 12) أو /cancel.")
    if message.text.strip() == "/cancel":
        await state.clear()
        return await message.answer("❌ تم إلغاء العملية.")
    if not message.text.strip().isdigit() or not (1 <= int(message.text.strip()) <= 8760):
        return await message.answer("❌ يرجى إرسال رقم صحيح بين 1 و 8760 ساعة.")

    hours = int(message.text.strip())
    data = await state.get_data()
    label = data.get("inv_label")
    await state.clear()

    created = await create_owner_invite_link(
        label=label,
        link_type="temporary",
        duration_hours=hours,
        created_by=message.from_user.id,
    )
    await _render_owner_link_details(
        message,
        created["id"],
        prefix_notice=f"✅ <b>تم توليد رابط الدعوة المؤقت ({hours} ساعة) بنجاح!</b>\n\n",
    )


@router.callback_query(F.data.startswith("owner_inv_view_"))
async def cb_owner_inv_view(callback: types.CallbackQuery):
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔️ للمالك فقط.", show_alert=True)
    link_id = int(callback.data.replace("owner_inv_view_", ""))
    await _render_owner_link_details(callback.message, link_id)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("owner_inv_pause_"))
async def cb_owner_inv_pause(callback: types.CallbackQuery):
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔️ للمالك فقط.", show_alert=True)
    link_id = int(callback.data.replace("owner_inv_pause_", ""))
    await set_owner_invite_status(link_id, "paused")
    await _render_owner_link_details(
        callback.message,
        link_id,
        prefix_notice="⏸ <b>تم إيقاف الرابط يدوياً.</b>\n\n",
    )
    try:
        await callback.answer("⏸ تم إيقاف الرابط يدوياً")
    except Exception:
        pass


@router.callback_query(F.data.startswith("owner_inv_resume_"))
async def cb_owner_inv_resume(callback: types.CallbackQuery):
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔️ للمالك فقط.", show_alert=True)
    link_id = int(callback.data.replace("owner_inv_resume_", ""))
    await set_owner_invite_status(link_id, "active")
    await _render_owner_link_details(
        callback.message,
        link_id,
        prefix_notice="▶️ <b>تمت إعادة تفعيل الرابط بنجاح.</b>\n\n",
    )
    try:
        await callback.answer("▶️ تم تفعيل الرابط")
    except Exception:
        pass


@router.callback_query(F.data.startswith("owner_inv_del_ask_"))
async def cb_owner_inv_del_ask(callback: types.CallbackQuery):
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔️ للمالك فقط.", show_alert=True)
    link_id = int(callback.data.replace("owner_inv_del_ask_", ""))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ نعم، احذف الرابط نهائياً",
                callback_data=f"owner_inv_del_confirm_{link_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="🔙 تراجع",
                callback_data=f"owner_inv_view_{link_id}",
            )
        ],
    ])
    await _safe_edit_or_answer(
        callback.message,
        f"⚠️ <b>تأكيد الحذف:</b>\n\nهل أنت متأكد من حذف رابط الدعوة #{link_id} نهائياً؟ لا يمكن التراجع عن هذا الإجراء.",
        kb,
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("owner_inv_del_confirm_"))
async def cb_owner_inv_del_confirm(callback: types.CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔️ للمالك فقط.", show_alert=True)
    link_id = int(callback.data.replace("owner_inv_del_confirm_", ""))
    await delete_owner_invite_link(link_id)
    try:
        await callback.answer("🗑 تم حذف الرابط نهائياً")
    except Exception:
        pass
    await cb_admin_invite_links(callback, state)
