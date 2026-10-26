"""
Promo settings handlers — text, media, URL, button, VIP, post-payment, preview.
"""

from aiogram import Router, F, types
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputPaidMediaPhoto, InputPaidMediaVideo

from core.bot import bot
from core.config import BOT_USERNAME
from models.admins import is_admin
from models.settings import get_setting, set_setting
from services.promo import build_promo_keyboard
from states.states import AdminEdit

router = Router(name="admin_promo_settings")


# ── Promo Settings Menu ─────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_promo_settings")
async def cb_admin_promo_settings(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.clear()
    show_bot_btn = await get_setting("show_add_bot_button")
    btn_text = "🤖 إخفاء زر البوت" if show_bot_btn == "true" else "🤖 إظهار زر البوت"

    is_vip = await get_setting("promo_is_vip") == "true"
    stars = await get_setting("promo_stars") or "50"
    vip_text = f"💎 الإعلان: مدفوع ({stars}⭐️)" if is_vip else "🟢 الإعلان: مجاني"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 تعديل النص", callback_data="admin_edit_text"),
         InlineKeyboardButton(text="🖼️ تعديل الوسائط", callback_data="admin_edit_media")],
        [InlineKeyboardButton(text="🔗 تعديل الرابط", callback_data="admin_edit_url"),
         InlineKeyboardButton(text="🔘 تعديل نص الزر", callback_data="admin_edit_button")],
        [InlineKeyboardButton(text=btn_text, callback_data="admin_toggle_bot_btn")],
        [InlineKeyboardButton(text=vip_text, callback_data="admin_toggle_promo_vip")],
        [InlineKeyboardButton(text="💬 رسالة ما بعد الدفع", callback_data="admin_edit_post_payment_msg")],
        [InlineKeyboardButton(text="👁 معاينة الإعلان", callback_data="admin_preview_promo")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_main")],
    ])
    text = (
        "📢 <b>إعداد الترويج (للمجموعات)</b>\n\n"
        "يمكنك استخدام <code>{user}</code> في النص ليتم استبدالها تلقائياً بـ 'منشن' للعضو الجديد.\n\n"
        "اختر ما تريد تعديله:"
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    except TelegramAPIError:
        pass
    await callback.answer()


# ── VIP Toggle ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_toggle_promo_vip")
async def cb_admin_toggle_promo_vip(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    is_vip = await get_setting("promo_is_vip") == "true"
    if is_vip:
        await set_setting("promo_is_vip", "false")
        await cb_admin_promo_settings(callback, state)
    else:
        await callback.message.answer(
            "⭐️ أرسل عدد نجوم تيليجرام المطلوبة لهذا الإعلان (مثلاً 50):\nلإلغاء الأمر أرسل /cancel"
        )
        await state.set_state(AdminEdit.waiting_for_promo_stars)
        await callback.answer()


@router.message(AdminEdit.waiting_for_promo_stars)
async def process_promo_stars(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
    if not message.text.isdigit():
        return await message.answer("❌ يرجى إرسال أرقام فقط.")
    await set_setting("promo_stars", message.text)
    await set_setting("promo_is_vip", "true")
    await message.answer(f"✅ تم تحويل الإعلان إلى مدفوع بقيمة {message.text} ⭐️")
    await state.clear()


# ── Post-Payment Message ─────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_edit_post_payment_msg")
async def cb_admin_edit_post_payment_msg(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.answer(
        "💬 أرسل الآن رسالة تأكيد الدفع (التي سيستلمها المستخدم بعد دفع النجوم):\n"
        "(يمكنك وضع روابط أو نصوص)\n"
        "ملاحظة: تليجرام يفتح الصور المدفوعة تلقائياً ولا يرسل إشعاراً للبوت بذلك، "
        "لذلك هذه الرسالة ستعمل بشكل أساسي مع (الإعلانات النصية المدفوعة الفواتير).\n"
        "لإلغاء الأمر أرسل /cancel"
    )
    await state.set_state(AdminEdit.waiting_for_post_payment_msg)
    await callback.answer()


@router.message(AdminEdit.waiting_for_post_payment_msg)
async def process_post_payment_msg(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
    await set_setting("promo_post_payment_msg", message.html_text or message.text)
    await message.answer("✅ تم حفظ رسالة ما بعد الدفع.")
    await state.clear()


# ── Toggle Bot Button ────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_toggle_bot_btn")
async def cb_admin_toggle_bot_btn(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("show_add_bot_button")
    new_val = "false" if current == "true" else "true"
    await set_setting("show_add_bot_button", new_val)
    await callback.answer("✅ تم التحديث")
    await cb_admin_promo_settings(callback, state)


# ── Preview ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_preview_promo")
async def cb_admin_preview_promo(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    promo_text = await get_setting("promo_text")
    promo_url = await get_setting("promo_url")
    promo_button_text = await get_setting("promo_button_text")
    promo_media_id = await get_setting("promo_media_id")
    promo_media_type = await get_setting("promo_media_type")
    show_bot_btn = await get_setting("show_add_bot_button")
    is_vip = await get_setting("promo_is_vip") == "true"
    stars = int(await get_setting("promo_stars") or 50)
    bot_info = await bot.get_me()

    user_name = callback.from_user.first_name.replace("<", "&lt;").replace(">", "&gt;")
    mention = f"<a href='tg://user?id={callback.from_user.id}'>{user_name}</a>"
    promo_text_formatted = promo_text.replace("{user}", mention)
    keyboard = build_promo_keyboard(promo_url, promo_button_text, bot_info.username or BOT_USERNAME, show_bot_btn)

    try:
        if is_vip:
            if promo_media_id:
                media_payload = [InputPaidMediaPhoto(media=promo_media_id)] if promo_media_type == "photo" else [InputPaidMediaVideo(media=promo_media_id)]
                await bot.send_paid_media(chat_id=callback.from_user.id, star_count=stars, media=media_payload, caption=f"👁 معاينة:\n\n{promo_text_formatted}", parse_mode=ParseMode.HTML)
            else:
                text_msg = await callback.message.answer(f"👁 معاينة:\n\n{promo_text_formatted}", reply_markup=keyboard, parse_mode=ParseMode.HTML)
                prices = [types.LabeledPrice(label="فتح المحتوى السري", amount=stars)]
                await bot.send_invoice(chat_id=callback.from_user.id, title="محتوى مدفوع (VIP)", description="قم بدفع النجوم لاستلام رسالة ما بعد الدفع فوراً.", payload="paid_promo", provider_token="", currency="XTR", prices=prices, reply_to_message_id=text_msg.message_id)
        else:
            if promo_media_id and promo_media_type == "photo":
                await callback.message.answer_photo(photo=promo_media_id, caption=f"👁 <b>معاينة:</b>\n\n{promo_text_formatted}", reply_markup=keyboard, parse_mode=ParseMode.HTML)
            elif promo_media_id and promo_media_type == "video":
                await callback.message.answer_video(video=promo_media_id, caption=f"👁 <b>معاينة:</b>\n\n{promo_text_formatted}", reply_markup=keyboard, parse_mode=ParseMode.HTML)
            else:
                await callback.message.answer(f"👁 <b>معاينة:</b>\n\n{promo_text_formatted}", reply_markup=keyboard, parse_mode=ParseMode.HTML)
    except Exception as e:
        await callback.message.answer(f"❌ حدث خطأ في المعاينة. تأكد من صحة الإعدادات.\nالخطأ: {e}")
    await callback.answer()


# ── Edit Text ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_edit_text")
async def cb_admin_edit_text(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.answer("أرسل الآن نص الإعلان الجديد:\n(تذكر يمكنك استخدام <code>{user}</code> للمنشن)\nلإلغاء الأمر أرسل /cancel", parse_mode=ParseMode.HTML)
    await state.set_state(AdminEdit.waiting_for_promo_text)
    await callback.answer()


@router.message(AdminEdit.waiting_for_promo_text)
async def process_promo_text(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("تم الإلغاء.")
        await state.clear()
        return
    await set_setting("promo_text", message.text)
    await message.answer("✅ تم تحديث نص الإعلان بنجاح.")
    await state.clear()


# ── Edit Media ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_edit_media")
async def cb_admin_edit_media(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.answer("أرسل الآن (صورة أو فيديو) ليتم إرفاقه مع الإعلان.\nلحذف الوسائط والاكتفاء بالنص أرسل /clear\nلإلغاء الأمر أرسل /cancel")
    await state.set_state(AdminEdit.waiting_for_media)
    await callback.answer()


@router.message(AdminEdit.waiting_for_media, F.photo | F.video | F.text)
async def process_promo_media(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("تم الإلغاء.")
        await state.clear()
        return
    elif message.text == "/clear":
        await set_setting("promo_media_id", "")
        await set_setting("promo_media_type", "")
        await message.answer("✅ تم حذف الوسائط. سيتم إرسال الإعلان كنص فقط.")
        await state.clear()
        return
    if message.photo:
        await set_setting("promo_media_id", message.photo[-1].file_id)
        await set_setting("promo_media_type", "photo")
        await message.answer("✅ تم حفظ الصورة بنجاح.")
    elif message.video:
        await set_setting("promo_media_id", message.video.file_id)
        await set_setting("promo_media_type", "video")
        await message.answer("✅ تم حفظ الفيديو بنجاح.")
    else:
        await message.answer("❌ أرسل صورة أو فيديو، أو /clear، أو /cancel.")
        return
    await state.clear()


# ── Edit URL ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_edit_url")
async def cb_admin_edit_url(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.answer("أرسل الآن الرابط الترويجي الجديد (يجب أن يبدأ بـ http أو https):\nلإلغاء الأمر أرسل /cancel")
    await state.set_state(AdminEdit.waiting_for_promo_url)
    await callback.answer()


@router.message(AdminEdit.waiting_for_promo_url)
async def process_promo_url(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("تم الإلغاء.")
        await state.clear()
        return
    if not message.text.startswith(("http://", "https://")):
        await message.answer("❌ الرابط غير صحيح. يجب أن يبدأ بـ http:// أو https://\nحاول مجدداً أو أرسل /cancel")
        return
    await set_setting("promo_url", message.text)
    await message.answer("✅ تم تحديث الرابط بنجاح.")
    await state.clear()


# ── Edit Button Text ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_edit_button")
async def cb_admin_edit_button(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.answer("أرسل الآن نص الزر الجديد:\nلإلغاء الأمر أرسل /cancel")
    await state.set_state(AdminEdit.waiting_for_promo_button)
    await callback.answer()


@router.message(AdminEdit.waiting_for_promo_button)
async def process_promo_button(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("تم الإلغاء.")
        await state.clear()
        return
    await set_setting("promo_button_text", message.text)
    await message.answer("✅ تم تحديث نص الزر بنجاح.")
    await state.clear()
