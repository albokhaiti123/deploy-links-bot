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



@router.callback_query(F.data == "start_btn2_click")
async def cb_start_btn2_click(callback: types.CallbackQuery):
    content = await get_setting("start_btn2_content")
    if not content:
        content = "No message available."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back", callback_data="start_back")]
    ])
    await callback.message.edit_text(content, reply_markup=kb, parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "start_back")
async def cb_start_back(callback: types.CallbackQuery):
    bot_info = await bot.get_me()
    text, kb = await get_start_message_data(bot_info.username or BOT_USERNAME)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
