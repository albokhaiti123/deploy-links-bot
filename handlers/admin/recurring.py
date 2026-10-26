"""
Recurring broadcasts admin handlers — list, start/stop, delete, create.
"""

from aiogram import Router, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from models.admins import is_admin
from models.broadcasts import (
    list_recurring_broadcasts, set_recurring_broadcast_active,
    delete_recurring_broadcast, create_recurring_broadcast,
)
from states.states import AdminEdit

router = Router(name="admin_recurring")


@router.callback_query(F.data == "admin_recurring_bw")
async def cb_admin_recurring_bw(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    rows = await list_recurring_broadcasts()
    if not rows:
        text = "🔄 <b>الإذاعات الدورية:</b>\n\nلا توجد إذاعات دورية حالياً."
    else:
        text = "🔄 <b>الإذاعات الدورية:</b>\n\n"
        target_map = {"users": "مستخدمين", "groups": "مجموعات", "all": "الجميع"}
        for row in rows:
            rb_id, target, repeat_hours, is_active, rb_text = row
            status_icon = "▶️" if is_active else "⏸"
            preview = (rb_text[:30] + "...") if rb_text and len(rb_text) > 30 else (rb_text or "")
            text += f"{status_icon} #{rb_id} | {target_map.get(target, target)} | كل {repeat_hours}h | {preview}\n"
    buttons = []
    for row in rows:
        rb_id, _, _, is_active, _ = row
        if is_active:
            buttons.append([
                InlineKeyboardButton(text=f"⏸ إيقاف #{rb_id}", callback_data=f"rbw_stop_{rb_id}"),
                InlineKeyboardButton(text=f"🗑 حذف #{rb_id}", callback_data=f"rbw_del_{rb_id}"),
            ])
        else:
            buttons.append([
                InlineKeyboardButton(text=f"▶️ تشغيل #{rb_id}", callback_data=f"rbw_start_{rb_id}"),
                InlineKeyboardButton(text=f"🗑 حذف #{rb_id}", callback_data=f"rbw_del_{rb_id}"),
            ])
    buttons.append([InlineKeyboardButton(text="➕ إنشاء إذاعة دورية", callback_data="rbw_create")])
    buttons.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_broadcast_menu")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()


@router.callback_query(F.data.startswith("rbw_stop_"))
async def cb_rbw_stop(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    rb_id = int(callback.data.split("_")[-1])
    await set_recurring_broadcast_active(rb_id, False)
    await callback.answer("⏸ تم الإيقاف.", show_alert=True)
    await cb_admin_recurring_bw(callback)


@router.callback_query(F.data.startswith("rbw_start_"))
async def cb_rbw_start(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    rb_id = int(callback.data.split("_")[-1])
    await set_recurring_broadcast_active(rb_id, True)
    await callback.answer("▶️ تم التشغيل.", show_alert=True)
    await cb_admin_recurring_bw(callback)


@router.callback_query(F.data.startswith("rbw_del_"))
async def cb_rbw_del(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    rb_id = int(callback.data.split("_")[-1])
    await delete_recurring_broadcast(rb_id)
    await callback.answer("🗑 تم الحذف.", show_alert=True)
    await cb_admin_recurring_bw(callback)


@router.callback_query(F.data == "rbw_create")
async def cb_rbw_create(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 مستخدمين", callback_data="rbw_target_users")],
        [InlineKeyboardButton(text="🌐 مجموعات", callback_data="rbw_target_groups")],
        [InlineKeyboardButton(text="📢 الجميع", callback_data="rbw_target_all")],
    ])
    await callback.message.answer("🔄 <b>إنشاء إذاعة دورية:</b>\n\nاختر الهدف:", reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()


@router.callback_query(F.data.startswith("rbw_target_"))
async def cb_rbw_target(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    target = callback.data.replace("rbw_target_", "")
    await state.update_data(rbw_target=target, rbw_mode=True)
    await callback.message.answer("📝 أرسل نص الإذاعة الدورية:\n(لإلغاء أرسل /cancel)", parse_mode=ParseMode.HTML)
    await state.set_state(AdminEdit.waiting_for_rbw_text)
    await callback.answer()


@router.message(AdminEdit.waiting_for_rbw_text, F.text)
async def process_rbw_text(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
    await state.update_data(rbw_text=message.html_text or message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="كل 6 ساعات", callback_data="rbw_hours_6"),
         InlineKeyboardButton(text="كل 12 ساعة", callback_data="rbw_hours_12")],
        [InlineKeyboardButton(text="كل 24 ساعة", callback_data="rbw_hours_24"),
         InlineKeyboardButton(text="كل 48 ساعة", callback_data="rbw_hours_48")],
    ])
    await message.answer("🔄 كل كم ساعة تريد تكرار هذه الإذاعة؟", reply_markup=kb, parse_mode=ParseMode.HTML)
    await state.set_state(AdminEdit.waiting_for_rbw_hours)


@router.callback_query(AdminEdit.waiting_for_rbw_hours, F.data.startswith("rbw_hours_"))
async def cb_rbw_hours(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    hours = int(callback.data.replace("rbw_hours_", ""))
    await create_recurring_broadcast(
        target=data.get("rbw_target", "all"),
        text=data.get("rbw_text", ""),
        repeat_hours=hours,
    )
    await state.clear()
    await callback.message.answer(f"✅ تم إنشاء إذاعة دورية (كل {hours} ساعة)!")
    await callback.answer()
