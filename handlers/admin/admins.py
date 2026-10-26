"""
Admin management handlers — add/remove admins (owner-only).
"""

from aiogram import Router, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.config import ADMIN_ID
from models.admins import is_admin, add_admin, remove_admin, list_admins
from states.states import AdminEdit

router = Router(name="admin_admins")


@router.callback_query(F.data == "admin_manage_admins")
async def cb_admin_manage_admins(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    admins = await list_admins()
    if admins:
        text = "👑 <b>المشرفون الحاليون:</b>\n\n"
        for tid, added_at in admins:
            text += f"• <code>{tid}</code>\n"
    else:
        text = "👑 <b>المشرفون:</b>\n\nلا يوجد مشرفون إضافيون."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ إضافة مشرف", callback_data="admin_add_admin")],
        [InlineKeyboardButton(text="➖ إزالة مشرف", callback_data="admin_remove_admin")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_main")],
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()


@router.callback_query(F.data == "admin_add_admin")
async def cb_admin_add_admin(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.update_data(admin_action="add")
    await callback.message.answer("أرسل معرف تيليجرام (Telegram ID) للشخص الذي تريد إضافته كمشرف:\nلإلغاء الأمر أرسل /cancel")
    await state.set_state(AdminEdit.waiting_for_admin_id)
    await callback.answer()


@router.callback_query(F.data == "admin_remove_admin")
async def cb_admin_remove_admin(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.update_data(admin_action="remove")
    await callback.message.answer("أرسل معرف تيليجرام (Telegram ID) للمشرف الذي تريد إزالته:\nلإلغاء الأمر أرسل /cancel")
    await state.set_state(AdminEdit.waiting_for_admin_id)
    await callback.answer()


@router.message(AdminEdit.waiting_for_admin_id)
async def process_admin_id(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
    if not message.text.strip().isdigit():
        await message.answer("❌ يرجى إرسال معرف رقمي صالح.\nحاول مجدداً أو أرسل /cancel")
        return
    tid = int(message.text.strip())
    data = await state.get_data()
    action = data.get("admin_action")
    if action == "add":
        await add_admin(tid)
        await message.answer(f"✅ تم إضافة المشرف <code>{tid}</code> بنجاح.", parse_mode=ParseMode.HTML)
    elif action == "remove":
        await remove_admin(tid)
        await message.answer(f"✅ تم إزالة المشرف <code>{tid}</code>.", parse_mode=ParseMode.HTML)
    await state.clear()
