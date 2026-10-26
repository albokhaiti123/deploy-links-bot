"""
Welcome message settings handlers — start message text, btn2, preview.
"""

from aiogram import Router, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.bot import bot
from core.config import BOT_USERNAME
from models.admins import is_admin
from models.settings import get_setting, set_setting
from services.promo import get_start_message_data
from states.states import AdminEdit

router = Router(name="admin_welcome_settings")


@router.callback_query(F.data == "admin_start_settings")
async def cb_admin_start_settings(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 تعديل نص رسالة الترحيب", callback_data="admin_edit_start_msg")],
        [InlineKeyboardButton(text="🖼️ تعديل وسائط الترحيب", callback_data="admin_edit_start_media")],
        [InlineKeyboardButton(text="🔘 تعديل اسم الزر الإضافي", callback_data="admin_edit_btn2_name")],
        [InlineKeyboardButton(text="🔗 جعله رابط (URL)", callback_data="admin_edit_btn2_url"),
         InlineKeyboardButton(text="💬 جعله رسالة نصية", callback_data="admin_edit_btn2_text")],
        [InlineKeyboardButton(text="🔘 أزرار مخصصة", callback_data="btn_list_welcome")],
        [InlineKeyboardButton(text="👁 معاينة رسالة الترحيب", callback_data="admin_preview_start")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_settings")],
    ])
    await callback.message.edit_text(
        "⚙️ <b>إعدادات رسالة الترحيب (الخاص):</b>\n\n"
        "تتحكم هذه القائمة بالرسالة والأزرار التي تظهر للأعضاء عند بدء المحادثة مع البوت في الخاص.\n"
        "اختر ما تريد تعديله:",
        reply_markup=kb, parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data == "admin_preview_start")
async def cb_admin_preview_start(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    bot_info = await bot.get_me()
    text, kb = await get_start_message_data(bot_info.username or BOT_USERNAME)
    media_id = await get_setting("start_media_id")
    media_type = await get_setting("start_media_type")
    preview_text = f"👁 <b>معاينة الترحيب:</b>\n\n{text}"
    if media_id and media_type == "photo":
        await callback.message.answer_photo(photo=media_id, caption=preview_text, reply_markup=kb, parse_mode=ParseMode.HTML)
    elif media_id and media_type == "video":
        await callback.message.answer_video(video=media_id, caption=preview_text, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        await callback.message.answer(preview_text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()


@router.callback_query(F.data == "admin_edit_start_media")
async def cb_admin_edit_start_media(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.answer(
        "🖼️ أرسل صورة أو فيديو لإرفاقه مع رسالة الترحيب.\n"
        "لحذف الوسائط الحالية أرسل /clear\n"
        "لإلغاء أرسل /cancel"
    )
    await state.set_state(AdminEdit.waiting_for_start_media)
    await callback.answer()


@router.message(AdminEdit.waiting_for_start_media, F.photo | F.video | F.text)
async def process_start_media(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
    if message.text == "/clear":
        await set_setting("start_media_id", "")
        await set_setting("start_media_type", "")
        await message.answer("✅ تم حذف الوسائط. رسالة الترحيب ستكون نصية فقط.")
        await state.clear()
        return
    if message.photo:
        await set_setting("start_media_id", message.photo[-1].file_id)
        await set_setting("start_media_type", "photo")
        await message.answer("✅ تم حفظ صورة الترحيب بنجاح.")
    elif message.video:
        await set_setting("start_media_id", message.video.file_id)
        await set_setting("start_media_type", "video")
        await message.answer("✅ تم حفظ فيديو الترحيب بنجاح.")
    else:
        await message.answer("❌ أرسل صورة أو فيديو، أو /clear، أو /cancel.")
        return
    await state.clear()


@router.callback_query(F.data == "admin_edit_start_msg")
async def cb_admin_edit_start_msg(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.answer(
        "أرسل الآن رسالة الترحيب الجديدة التي ستظهر للأعضاء في الخاص عند إرسال /start:\n"
        "(يمكنك استخدام HTML)\nلإلغاء الأمر أرسل /cancel"
    )
    await state.set_state(AdminEdit.waiting_for_start_msg)
    await callback.answer()


@router.message(AdminEdit.waiting_for_start_msg)
async def process_start_msg(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("تم الإلغاء.")
        await state.clear()
        return
    await set_setting("start_message", message.text)
    await message.answer("✅ تم تحديث رسالة الترحيب بنجاح.")
    await state.clear()


@router.callback_query(F.data == "admin_edit_btn2_name")
async def cb_admin_edit_btn2_name(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.answer(
        "أرسل الآن الاسم الجديد للزر الإضافي (مثال: اشترك في الباقة).\n"
        "لإخفاء الزر تماماً أرسل /hide\nلإلغاء الأمر أرسل /cancel"
    )
    await state.set_state(AdminEdit.waiting_for_start_btn2_name)
    await callback.answer()


@router.message(AdminEdit.waiting_for_start_btn2_name)
async def process_start_btn2_name(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("تم الإلغاء.")
        await state.clear()
        return
    if message.text == "/hide":
        await set_setting("start_btn2_name", "")
        await message.answer("✅ تم إخفاء الزر الإضافي.")
    else:
        await set_setting("start_btn2_name", message.text)
        await message.answer("✅ تم تحديث اسم الزر الإضافي.")
    await state.clear()


@router.callback_query(F.data == "admin_edit_btn2_url")
async def cb_admin_edit_btn2_url(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.answer("أرسل الآن الرابط (يجب أن يبدأ بـ http أو https أو tg://):\nلإلغاء الأمر أرسل /cancel")
    await state.set_state(AdminEdit.waiting_for_start_btn2_url)
    await callback.answer()


@router.message(AdminEdit.waiting_for_start_btn2_url)
async def process_start_btn2_url(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("تم الإلغاء.")
        await state.clear()
        return
    if not message.text.startswith(("http://", "https://", "tg://")):
        await message.answer("❌ عذراً، الرابط غير صحيح. يجب أن يبدأ بـ http أو https أو tg://")
        return
    await set_setting("start_btn2_type", "url")
    await set_setting("start_btn2_content", message.text)
    await message.answer("✅ تم تحويل الزر الإضافي إلى رابط بنجاح.")
    await state.clear()


@router.callback_query(F.data == "admin_edit_btn2_text")
async def cb_admin_edit_btn2_text(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.answer("أرسل الآن الرسالة النصية التي تريد ظهورها عند ضغط المستخدم على الزر:\nلإلغاء الأمر أرسل /cancel")
    await state.set_state(AdminEdit.waiting_for_start_btn2_text)
    await callback.answer()


@router.message(AdminEdit.waiting_for_start_btn2_text)
async def process_start_btn2_text(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("تم الإلغاء.")
        await state.clear()
        return
    await set_setting("start_btn2_type", "text")
    await set_setting("start_btn2_content", message.text)
    await message.answer("✅ تم تحويل الزر الإضافي إلى رسالة نصية بنجاح.")
    await state.clear()
