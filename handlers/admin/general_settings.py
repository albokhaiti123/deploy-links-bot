"""
General settings handlers — cooldown, auto-delete, welcome toggle, promo delete, test group.
"""

from aiogram import Router, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from models.admins import is_admin
from models.settings import get_setting, set_setting
from states.states import AdminEdit

router = Router(name="admin_general_settings")


# ── Settings Page ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_settings")
async def cb_admin_settings(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    if state:
        await state.clear()
    cooldown = await get_setting("cooldown")
    auto_del = await get_setting("auto_delete")
    auto_del_text = "🧹 إيقاف الحذف التلقائي" if auto_del == "true" else "🧹 تشغيل الحذف التلقائي"
    pw_enabled = await get_setting("private_welcome_enabled")
    pw_text = "📴 إيقاف رسالة الترحيب (الخاص)" if pw_enabled != "false" else "📱 تشغيل رسالة الترحيب (الخاص)"
    promo_del = await get_setting("promo_delete_seconds")
    promo_del_display = "بدون حذف" if not promo_del or promo_del == "0" else f"{promo_del} ثانية"
    cooldown_display = "بدون انتظار (0 ثانية)" if cooldown == "0" else f"{cooldown} ثانية"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 إعدادات رسالة الترحيب (الخاص)", callback_data="admin_start_settings")],
        [InlineKeyboardButton(text=pw_text, callback_data="admin_toggle_pw")],
        [InlineKeyboardButton(text="⏱ تعديل مدة الانتظار (Cooldown)", callback_data="admin_edit_cooldown")],
        [InlineKeyboardButton(text=auto_del_text, callback_data="admin_toggle_autodelete")],
        [InlineKeyboardButton(text=f"🗑 حذف رسالة الترويج بعد: {promo_del_display}", callback_data="admin_edit_promo_del")],
        [InlineKeyboardButton(text="🧪 مجموعة الاختبار", callback_data="admin_test_group")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_main")],
    ])
    text = (
        "⚙️ <b>الإعدادات:</b>\n\n"
        f"📱 رسالة الترحيب (الخاص): {'مفعلة ✅' if pw_enabled != 'false' else 'معطلة ❌'}\n"
        f"⏱ مدة الانتظار الحالية: {cooldown_display}\n"
        f"🧹 الحذف التلقائي للإعلان القديم: {'مفعل ✅' if auto_del == 'true' else 'معطل ❌'}\n"
        f"🗑 حذف رسالة الترويج بعد: {promo_del_display}"
    )
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    await callback.answer()


# ── Private Welcome Toggle ───────────────────────────────────────────────────

@router.callback_query(F.data == "admin_toggle_pw")
async def cb_admin_toggle_pw(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("private_welcome_enabled")
    new_val = "false" if current != "false" else "true"
    await set_setting("private_welcome_enabled", new_val)
    await callback.answer("✅ تم التحديث", show_alert=True)
    await cb_admin_settings(callback, state)


# ── Auto-Delete Toggle ───────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_toggle_autodelete")
async def cb_admin_toggle_autodelete(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("auto_delete")
    new_val = "false" if current == "true" else "true"
    await set_setting("auto_delete", new_val)
    await callback.answer("✅ تم التحديث")
    await cb_admin_settings(callback, state)


# ── Cooldown ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_edit_cooldown")
async def cb_admin_edit_cooldown(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡️ مع كل انضمام (0 ثانية)", callback_data="set_cooldown_0")],
        [InlineKeyboardButton(text="30 ثانية", callback_data="set_cooldown_30"),
         InlineKeyboardButton(text="60 ثانية", callback_data="set_cooldown_60")],
        [InlineKeyboardButton(text="120 ثانية", callback_data="set_cooldown_120"),
         InlineKeyboardButton(text="300 ثانية", callback_data="set_cooldown_300")],
        [InlineKeyboardButton(text="إدخال قيمة مخصصة", callback_data="set_cooldown_custom")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_settings")],
    ])
    await callback.message.edit_text(
        "⏱ اختر مدة الانتظار بين كل إعلان وآخر في نفس المجموعة:\n\n"
        "*ملاحظة: اختيار '0 ثانية' يعني إرسال الإعلان مع كل عضو جديد ينضم دون انتظار.",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_cooldown_"))
async def cb_set_cooldown(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    val = callback.data.split("_")[2]
    if val == "custom":
        await callback.message.answer("أرسل قيمة مدة الانتظار بالثواني (أرقام فقط):\nلإلغاء الأمر أرسل /cancel")
        await state.set_state(AdminEdit.waiting_for_cooldown)
    else:
        await set_setting("cooldown", val)
        await callback.answer(f"✅ تم ضبط مدة الانتظار إلى {val} ثانية", show_alert=True)
        await cb_admin_settings(callback, state)
    await callback.answer()


@router.message(AdminEdit.waiting_for_cooldown)
async def process_cooldown(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("تم الإلغاء.")
        await state.clear()
        return
    if not message.text.isdigit():
        await message.answer("❌ يرجى إرسال أرقام فقط.\nحاول مجدداً أو أرسل /cancel")
        return
    await set_setting("cooldown", message.text)
    await message.answer(f"✅ تم تحديث مدة الانتظار إلى {message.text} ثانية.")
    await state.clear()


# ── Promo Delete Duration ────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_edit_promo_del")
async def cb_admin_edit_promo_del(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="بدون حذف", callback_data="set_promo_del_0")],
        [InlineKeyboardButton(text="30 ثانية", callback_data="set_promo_del_30"),
         InlineKeyboardButton(text="1 دقيقة", callback_data="set_promo_del_60")],
        [InlineKeyboardButton(text="5 دقائق", callback_data="set_promo_del_300"),
         InlineKeyboardButton(text="10 دقائق", callback_data="set_promo_del_600")],
        [InlineKeyboardButton(text="30 دقيقة", callback_data="set_promo_del_1800"),
         InlineKeyboardButton(text="1 ساعة", callback_data="set_promo_del_3600")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_settings")],
    ])
    await callback.message.edit_text("🗑 <b>اختر مدة حذف رسالة الترويج بعد إرسالها:</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()


@router.callback_query(F.data.startswith("set_promo_del_"))
async def cb_set_promo_del(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    val = callback.data.replace("set_promo_del_", "")
    await set_setting("promo_delete_seconds", val)
    await callback.answer("✅ تم التحديث", show_alert=True)
    await cb_admin_settings(callback, state)


# ── Test Group ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_test_group")
async def cb_admin_test_group(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("test_group_chat_id")
    text = (
        f"🧪 <b>مجموعة الاختبار:</b>\n\n"
        f"المعرف الحالي: <code>{current or 'غير محدد'}</code>\n\n"
        f"أرسل معرف (Chat ID) المجموعة.\n"
        f"لإلغاء أرسل /cancel\n"
        f"لإزالة المجموعة أرسل /remove"
    )
    await callback.message.answer(text, parse_mode=ParseMode.HTML)
    await state.set_state(AdminEdit.waiting_for_test_group)
    await callback.answer()


@router.message(AdminEdit.waiting_for_test_group)
async def process_test_group(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
    if message.text == "/remove":
        await set_setting("test_group_chat_id", "")
        await message.answer("✅ تم إزالة مجموعة الاختبار.")
        await state.clear()
        return
    text = message.text.strip()
    if not text.lstrip("-").isdigit():
        await message.answer("❌ يرجى إرسال معرف رقمي صالح (Chat ID).")
        return
    await set_setting("test_group_chat_id", text)
    await message.answer(f"✅ تم تحديد مجموعة الاختبار: <code>{text}</code>", parse_mode=ParseMode.HTML)
    await state.clear()
