"""
Admin panel — main menu, /admin command, toggle promo.
"""

from aiogram import Router, F, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.config import ADMIN_ID
from models.admins import is_admin
from models.settings import get_setting, set_setting

router = Router(name="admin_panel")


def get_admin_keyboard(promo_enabled: str, user_id: int) -> InlineKeyboardMarkup:
    toggle_text = "⏸️ إيقاف الترويج" if promo_enabled == "true" else "▶️ تشغيل الترويج"
    keyboard = [
        [InlineKeyboardButton(text="📢 إعداد الترويج", callback_data="admin_promo_settings")],
        [InlineKeyboardButton(text="👥 المجموعات", callback_data="admin_groups"),
         InlineKeyboardButton(text="📊 الإحصائيات", callback_data="admin_stats")],
        [InlineKeyboardButton(text="⚙️ الإعدادات", callback_data="admin_settings")],
        [InlineKeyboardButton(text="📣 ساحر الإذاعة (جديد ⭐️)", callback_data="admin_broadcast_menu")],
        [InlineKeyboardButton(text="🎯 الحملات الترويجية", callback_data="cmp_menu")],
        [InlineKeyboardButton(text=toggle_text, callback_data="admin_toggle_promo")],
    ]
    if user_id == ADMIN_ID:
        keyboard.insert(4, [InlineKeyboardButton(text="👑 إدارة المشرفين", callback_data="admin_manage_admins")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.clear()
    promo_enabled = await get_setting("promo_enabled")
    text = "━━━━━━━━━━━━━━\n⚙️ <b>لوحة التحكم</b>\n━━━━━━━━━━━━━━"
    await message.answer(text, reply_markup=get_admin_keyboard(promo_enabled, message.from_user.id), parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "admin_main")
async def cb_admin_main(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.clear()
    promo_enabled = await get_setting("promo_enabled")
    text = "━━━━━━━━━━━━━━\n⚙️ <b>لوحة التحكم</b>\n━━━━━━━━━━━━━━"
    await callback.message.edit_text(text, reply_markup=get_admin_keyboard(promo_enabled, callback.from_user.id), parse_mode=ParseMode.HTML)
    await callback.answer()


@router.callback_query(F.data == "admin_toggle_promo")
async def cb_admin_toggle_promo(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("promo_enabled")
    new_val = "false" if current == "true" else "true"
    await set_setting("promo_enabled", new_val)
    await callback.message.edit_reply_markup(reply_markup=get_admin_keyboard(new_val, callback.from_user.id))
    status_text = "تم تشغيل الترويج" if new_val == "true" else "تم إيقاف الترويج"
    await callback.answer(status_text)


# ── Global Cancel Handlers ───────────────────────────────────────────────────

@router.callback_query(F.data == "cancel_wizard")
async def cb_cancel_wizard(callback: types.CallbackQuery, state: FSMContext):
    """Universal cancel button for all wizards — clears state and confirms."""
    await state.clear()
    await callback.message.answer("❌ تم الإلغاء.")
    await callback.answer()


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    """Universal /cancel command — clears any active FSM state."""
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer("❌ تم إلغاء العملية الحالية.")
    else:
        await message.answer("لا توجد عملية جارية للإلغاء.")
