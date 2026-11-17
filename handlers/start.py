"""
Start handler — /start command, welcome message, btn2 click, back button.
"""

from aiogram import Router, types, F
from aiogram.enums import ParseMode, ChatType
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.bot import bot
from core.config import BOT_USERNAME
from models.settings import get_setting
from models.users import upsert_user
from services.promo import get_start_message_data, trigger_group_promo
from services.campaign import show_campaign_progress

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    if message.chat.type != ChatType.PRIVATE:
        await trigger_group_promo(message, message.from_user)
        return

    await upsert_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )

    # Campaign deep link: /start camp_123
    parts = message.text.split()
    if len(parts) > 1 and parts[1].startswith("camp_"):
        try:
            campaign_id = int(parts[1].replace("camp_", ""))
            await show_campaign_progress(message, campaign_id, message.from_user.id)
            return
        except (ValueError, TypeError):
            pass

    # Check if private welcome is enabled
    pw_enabled = await get_setting("private_welcome_enabled")
    if pw_enabled == "false":
        return

    bot_info = await bot.get_me()
    text, kb = await get_start_message_data(bot_info.username or BOT_USERNAME)
    media_id = await get_setting("start_media_id")
    media_type = await get_setting("start_media_type")

    # For non-admin users, add a user dashboard button to the keyboard
    from models.admins import is_admin as _is_admin
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    if not await _is_admin(message.from_user.id):
        # Append user dashboard button to existing keyboard
        existing_rows = kb.inline_keyboard if kb else []
        user_btn = [[InlineKeyboardButton(text="👤 My Dashboard", callback_data="user_menu")]]
        kb = InlineKeyboardMarkup(inline_keyboard=existing_rows + user_btn)

    try:
        if media_id and media_type == "photo":
            await message.answer_photo(photo=media_id, caption=text, reply_markup=kb, parse_mode=ParseMode.HTML)
        elif media_id and media_type == "video":
            await message.answer_video(video=media_id, caption=text, reply_markup=kb, parse_mode=ParseMode.HTML)
        else:
            await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception:
        # Fallback: send without HTML parsing if admin text has broken tags
        if media_id and media_type == "photo":
            await message.answer_photo(photo=media_id, caption=text, reply_markup=kb)
        elif media_id and media_type == "video":
            await message.answer_video(video=media_id, caption=text, reply_markup=kb)
        else:
            await message.answer(text, reply_markup=kb)



async def _edit_start_message(message: types.Message, text: str, kb: InlineKeyboardMarkup) -> None:
    """Safely edit welcome message whether it is text-only or photo/video media."""
    is_media = bool(getattr(message, "photo", None) or getattr(message, "video", None) or getattr(message, "caption", None) is not None)
    try:
        if is_media:
            await message.edit_caption(caption=text, reply_markup=kb, parse_mode=ParseMode.HTML)
        else:
            await message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception:
        if is_media:
            await message.edit_caption(caption=text, reply_markup=kb)
        else:
            await message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data == "start_btn2_click")
async def cb_start_btn2_click(callback: types.CallbackQuery):
    content = await get_setting("start_btn2_content")
    if not content:
        content = "No message available."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back", callback_data="start_back")]
    ])
    await _edit_start_message(callback.message, content, kb)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "start_back")
async def cb_start_back(callback: types.CallbackQuery):
    from models.admins import is_admin as _is_admin
    bot_info = await bot.get_me()
    text, kb = await get_start_message_data(bot_info.username or BOT_USERNAME)
    if not await _is_admin(callback.from_user.id):
        existing_rows = kb.inline_keyboard if kb else []
        user_btn = [[InlineKeyboardButton(text="👤 My Dashboard", callback_data="user_menu")]]
        kb = InlineKeyboardMarkup(inline_keyboard=existing_rows + user_btn)
    await _edit_start_message(callback.message, text, kb)
    try:
        await callback.answer()
    except Exception:
        pass


# ── Phase 4 Invite & Referral Integration ──
_orig_get_start_message_data = get_start_message_data


async def get_start_message_data(bot_username: str):
    """Wrap get_start_message_data to always include '🔗 رابط الاحالة الخاص بي' button."""
    text, kb = await _orig_get_start_message_data(bot_username)
    rows = list(kb.inline_keyboard) if kb and getattr(kb, "inline_keyboard", None) else []
    has_ref_btn = any(
        getattr(btn, "callback_data", None) == "user_my_referral"
        for row in rows
        for btn in row
    )
    if not has_ref_btn:
        rows.append([InlineKeyboardButton(text="🔗 رابط الاحالة الخاص بي", callback_data="user_my_referral")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


_orig_cmd_start = cmd_start


async def _phase4_wrapped_start(message: types.Message, *args, **kwargs):
    """Intercept /start inv_<code> and /start ref_<code> deep links before standard /start flow."""
    raw_text = (getattr(message, "text", None) or "").strip()
    parts = raw_text.split(maxsplit=1)
    if len(parts) > 1:
        payload = parts[1].strip()
        if payload.startswith("inv_"):
            from models.invite_links import process_owner_invite_join
            from models.users import upsert_user
            code = payload[4:]
            user = message.from_user
            if user:
                await upsert_user(user.id, getattr(user, "username", None), getattr(user, "first_name", None))
                ok, reason, _ = await process_owner_invite_join(code, user.id)
                if not ok:
                    if reason == "paused":
                        await message.answer("⛔️ عذراً، رابط الدعوة هذا متوقف حالياً من قِبل إدارة البوت.")
                    elif reason == "expired":
                        await message.answer("⌛️ عذراً، انتهت صلاحية رابط الدعوة المؤقت هذا.")
                    else:
                        await message.answer("❌ عذراً، رابط الدعوة هذا غير صالح أو تم حذفه.")
                    return
        elif payload.startswith("ref_"):
            from models.invite_links import process_user_referral_join
            from models.users import upsert_user
            ref_code = payload[4:]
            user = message.from_user
            if user:
                await upsert_user(user.id, getattr(user, "username", None), getattr(user, "first_name", None))
                await process_user_referral_join(ref_code, user.id)

    return await _orig_cmd_start(message, *args, **kwargs)


cmd_start = _phase4_wrapped_start
for _obs_handler in router.message.handlers:
    if getattr(_obs_handler, "callback", None) is _orig_cmd_start:
        _obs_handler.callback = _phase4_wrapped_start
