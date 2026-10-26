"""
Broadcast wizard handlers — target, text, media, VIP, stars, duration, confirm.
"""

import asyncio
from aiogram import Router, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from models.admins import is_admin
from services.broadcast import execute_broadcast
from states.states import BroadcastWizard

router = Router(name="admin_broadcast")


@router.callback_query(F.data == "admin_broadcast_menu")
async def cb_admin_broadcast_menu(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.clear()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 للإدارة والمستخدمين (في الخاص)", callback_data="start_bw_users")],
        [InlineKeyboardButton(text="🌐 للمجموعات فقط", callback_data="start_bw_groups")],
        [InlineKeyboardButton(text="🔄 الإذاعات الدورية", callback_data="admin_recurring_bw")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_main")],
    ])
    await callback.message.edit_text(
        "📣 <b>ساحر الإذاعة الجديد:</b>\n\nاختر الوجهة التي تريد بدء الإذاعة إليها:",
        reply_markup=keyboard, parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("start_bw_"))
async def cb_start_bw(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    target = callback.data.split("_")[2]
    await state.update_data(target=target)
    await callback.message.answer(
        "📝 <b>الخطوة 1:</b> أرسل النص الخاص بالإذاعة.\n"
        "(يمكنك إضافة روابط أو تنسيقات HTML)\nلإلغاء الأمر أرسل /cancel",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(BroadcastWizard.text)
    await callback.answer()


@router.message(BroadcastWizard.text)
async def process_bw_text(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
    await state.update_data(text=message.html_text or message.text)
    await message.answer(
        "🖼 <b>الخطوة 2:</b> أرسل صورة أو فيديو لإرفاقه مع الإذاعة.\n"
        "إذا أردت إرسال الإذاعة كنص فقط دون وسائط، أرسل /skip\nلإلغاء الأمر أرسل /cancel",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(BroadcastWizard.media)


@router.message(BroadcastWizard.media, F.photo | F.video | F.text)
async def process_bw_media(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
    if message.text == "/skip":
        await state.update_data(media_id=None, media_type=None)
        await _ask_duration(message, state)
        return
    if message.photo:
        await state.update_data(media_id=message.photo[-1].file_id, media_type="photo")
    elif message.video:
        await state.update_data(media_id=message.video.file_id, media_type="video")
    else:
        await message.answer("❌ يجب إرسال صورة أو فيديو، أو /skip، أو /cancel.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 مجانية (مفتوحة)", callback_data="media_free")],
        [InlineKeyboardButton(text="⭐️ مدفوعة (VIP - بنجوم تيليجرام)", callback_data="media_vip")],
    ])
    await message.answer(
        "💎 <b>الخطوة 3:</b> هل تريد أن يكون هذا المحتوى مجانياً أم مدفوعاً (مظلل يفتح بالنجوم)؟",
        reply_markup=kb, parse_mode=ParseMode.HTML,
    )
    await state.set_state(BroadcastWizard.media_type_vip)


@router.callback_query(BroadcastWizard.media_type_vip)
async def cb_bw_media_type(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    if callback.data == "media_free":
        await state.update_data(is_vip=False, stars=0)
        await _ask_duration(callback.message, state)
    elif callback.data == "media_vip":
        await state.update_data(is_vip=True)
        await callback.message.answer("⭐️ كم عدد النجوم المطلوبة لفتح المحتوى؟ (أرسل رقماً بين 1 و 2500):")
        await state.set_state(BroadcastWizard.stars)
    await callback.answer()


@router.message(BroadcastWizard.stars)
async def process_bw_stars(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
    if not message.text.isdigit():
        return await message.answer("❌ يرجى إرسال أرقام فقط (مثلاً 50).")
    stars = int(message.text)
    if stars < 1 or stars > 2500:
        return await message.answer("❌ يجب أن يكون العدد بين 1 و 2500.")
    await state.update_data(stars=stars)
    await _ask_duration(message, state)


async def _ask_duration(message: types.Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="لا تحذف أبداً", callback_data="duration_0")],
        [InlineKeyboardButton(text="بعد 10 دقائق", callback_data="duration_10"),
         InlineKeyboardButton(text="بعد 30 دقيقة", callback_data="duration_30")],
        [InlineKeyboardButton(text="بعد 1 ساعة", callback_data="duration_60"),
         InlineKeyboardButton(text="بعد 6 ساعات", callback_data="duration_360")],
        [InlineKeyboardButton(text="بعد 24 ساعة", callback_data="duration_1440")],
    ])
    await message.answer(
        "⏳ <b>الخطوة ما قبل الأخيرة:</b> متى تريد حذف الإذاعة تلقائياً؟",
        reply_markup=kb, parse_mode=ParseMode.HTML,
    )
    await state.set_state(BroadcastWizard.duration)


@router.callback_query(BroadcastWizard.duration)
async def cb_bw_duration(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    mins = int(callback.data.split("_")[1])
    await state.update_data(duration_mins=mins)
    data = await state.get_data()
    target_ar = "المستخدمين في الخاص" if data["target"] == "users" else "المجموعات"
    dur_ar = "لا تُحذف" if mins == 0 else f"تُحذف بعد {mins} دقيقة"
    vip_ar = f"مدفوعة بـ {data.get('stars', 0)} نجمة ⭐️" if data.get("is_vip") else "مجانية"
    summary = (
        f"📋 <b>ملخص الإذاعة النهائي:</b>\n\n"
        f"👥 <b>الوجهة:</b> {target_ar}\n"
        f"🖼 <b>الوسائط:</b> {'نعم' if data.get('media_id') else 'لا'} ({vip_ar})\n"
        f"⏳ <b>التدمير الذاتي:</b> {dur_ar}\n\n"
        f"هل أنت متأكد من الإرسال الآن؟"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ إرسال الآن", callback_data="confirm_send")],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="cancel_wizard")],
    ])
    await callback.message.answer(summary, reply_markup=kb, parse_mode=ParseMode.HTML)
    await state.set_state(BroadcastWizard.confirm)
    await callback.answer()


@router.callback_query(BroadcastWizard.confirm)
async def cb_bw_confirm(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    if callback.data == "cancel_wizard":
        await callback.message.answer("❌ تم إلغاء الإذاعة.")
        await state.clear()
        return
    data = await state.get_data()
    await state.clear()
    status_msg = await callback.message.answer("🚀 جاري الإرسال، يرجى الانتظار (قد يستغرق بعض الوقت لتجنب الحظر)...")
    asyncio.create_task(execute_broadcast(data, status_msg))
    await callback.answer()
