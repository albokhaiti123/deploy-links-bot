"""
Button manager admin handler — generic add/list/toggle/delete buttons for any context.

Used by promo settings, welcome settings, and campaign admin views.
Callback data pattern: btn_{action}_{context}[_{id}]
FSM: Uses a new ButtonWizard state for the add flow.
"""

from aiogram import Router, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from models.admins import is_admin
from models.custom_buttons import get_buttons, add_button, remove_button, toggle_button, count_buttons

router = Router(name="admin_button_manager")

MAX_BUTTONS_PER_CONTEXT = 10


class ButtonWizard(StatesGroup):
    waiting_for_label = State()
    waiting_for_url = State()


def _back_callback(context: str) -> str:
    """Return the callback_data to go back to the parent settings page."""
    if context == "promo":
        return "admin_promo_settings"
    elif context == "welcome":
        return "admin_start_settings"
    elif context.startswith("campaign_"):
        cid = context.split("_")[1]
        return f"cmp_view_{cid}"
    return "admin_main"


def _context_label(context: str) -> str:
    """Human-readable context name in Arabic."""
    if context == "promo":
        return "الترويج"
    elif context == "welcome":
        return "رسالة الترحيب"
    elif context.startswith("campaign_"):
        return f"الحملة #{context.split('_')[1]}"
    return context


async def show_button_list(target, context: str):
    """Show the button management panel for a context."""
    msg = target.message if isinstance(target, types.CallbackQuery) else target
    buttons_data = await get_buttons(context, active_only=False)
    label = _context_label(context)

    text = f"🔘 <b>أزرار {label}:</b>\n\n"
    if not buttons_data:
        text += "لا توجد أزرار مخصصة حالياً.\n"
    else:
        for btn in buttons_data:
            icon = "✅" if btn["is_active"] else "❌"
            text += f"{icon} <b>{btn['label']}</b>\n  └ {btn['url']}\n"

    kb_rows = []
    for btn in buttons_data:
        toggle_text = "❌ تعطيل" if btn["is_active"] else "✅ تفعيل"
        kb_rows.append([
            InlineKeyboardButton(text=f"{toggle_text} | {btn['label'][:15]}", callback_data=f"btn_toggle_{context}_{btn['id']}"),
            InlineKeyboardButton(text="🗑", callback_data=f"btn_del_{context}_{btn['id']}"),
        ])

    total = await count_buttons(context)
    if total < MAX_BUTTONS_PER_CONTEXT:
        kb_rows.append([InlineKeyboardButton(text="➕ إضافة زر جديد", callback_data=f"btn_add_{context}")])
    kb_rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=_back_callback(context))])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    try:
        await msg.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception:
        await msg.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)

    if isinstance(target, types.CallbackQuery):
        await target.answer()


# ── Entry point: show button list ────────────────────────────────────────────

@router.callback_query(F.data.startswith("btn_list_"))
async def cb_btn_list(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.clear()
    context = callback.data.replace("btn_list_", "")
    await show_button_list(callback, context)


# ── Add button flow ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("btn_add_"))
async def cb_btn_add(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    context = callback.data.replace("btn_add_", "")
    await state.update_data(btn_context=context)
    await callback.message.answer(
        f"🔘 <b>إضافة زر جديد ({_context_label(context)}):</b>\n\n"
        f"أرسل <b>نص الزر</b> (مثال: 📢 قناتنا):\n"
        f"لإلغاء أرسل /cancel",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(ButtonWizard.waiting_for_label)
    await callback.answer()


@router.message(ButtonWizard.waiting_for_label)
async def process_btn_label(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
    if len(message.text) > 64:
        return await message.answer("❌ نص الزر طويل جداً (الحد 64 حرف). حاول مجدداً:")
    await state.update_data(btn_label=message.text)
    await message.answer(
        "🔗 أرسل الآن <b>رابط الزر</b> (يجب أن يبدأ بـ http أو https أو tg://):\n"
        "لإلغاء أرسل /cancel",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(ButtonWizard.waiting_for_url)


@router.message(ButtonWizard.waiting_for_url)
async def process_btn_url(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
    if not message.text.startswith(("http://", "https://", "tg://")):
        return await message.answer("❌ الرابط غير صحيح. يجب أن يبدأ بـ http:// أو https:// أو tg://")
    data = await state.get_data()
    context = data["btn_context"]
    label = data["btn_label"]
    await add_button(context, label, message.text)
    await message.answer(f"✅ تم إضافة الزر <b>{label}</b> بنجاح!", parse_mode=ParseMode.HTML)
    await state.clear()


# ── Toggle button ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("btn_toggle_"))
async def cb_btn_toggle(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    parts = callback.data.split("_")
    btn_id = int(parts[-1])
    # Reconstruct context (could contain underscores like "campaign_5")
    context = "_".join(parts[2:-1])
    new_state = await toggle_button(btn_id)
    status = "مفعّل ✅" if new_state else "معطّل ❌"
    await callback.answer(f"الزر الآن: {status}", show_alert=True)
    await show_button_list(callback, context)


# ── Delete button ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("btn_del_"))
async def cb_btn_del(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    parts = callback.data.split("_")
    btn_id = int(parts[-1])
    context = "_".join(parts[2:-1])
    await remove_button(btn_id)
    await callback.answer("🗑 تم حذف الزر.", show_alert=True)
    await show_button_list(callback, context)
