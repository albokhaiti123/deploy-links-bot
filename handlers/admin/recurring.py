"""
Recurring broadcasts admin handlers — list, start/stop, delete, create,
edit text, preview, send now.
"""

import asyncio

from aiogram import Router, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.bot import bot
from core.config import ADMIN_ID
from models.admins import is_admin
from models.broadcasts import (
    list_recurring_broadcasts, set_recurring_broadcast_active,
    delete_recurring_broadcast, create_recurring_broadcast,
    get_recurring_broadcast, update_recurring_broadcast_text,
)
from services.broadcast import execute_recurring_broadcast_cycle
from services.media import send_media_message
from states.states import AdminEdit

router = Router(name="admin_recurring")


@router.callback_query(F.data == "admin_recurring_bw")
async def cb_admin_recurring_bw(callback: types.CallbackQuery, state: FSMContext = None):
    if not await is_admin(callback.from_user.id):
        return
    if state:
        await state.clear()
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
    if rows:
        for row in rows:
            rb_id, _, _, is_active, _ = row
            row1 = []
            if is_active:
                row1.append(InlineKeyboardButton(text=f"⏸ إيقاف #{rb_id}", callback_data=f"rbw_stop_{rb_id}"))
            else:
                row1.append(InlineKeyboardButton(text=f"▶️ تشغيل #{rb_id}", callback_data=f"rbw_start_{rb_id}"))
            row1.append(InlineKeyboardButton(text=f"🗑 حذف #{rb_id}", callback_data=f"rbw_del_{rb_id}"))
            buttons.append(row1)
            buttons.append([
                InlineKeyboardButton(text=f"📝 تعديل #{rb_id}", callback_data=f"rbw_edit_{rb_id}"),
                InlineKeyboardButton(text=f"👁 معاينة #{rb_id}", callback_data=f"rbw_preview_{rb_id}"),
                InlineKeyboardButton(text=f"📢 نشر #{rb_id}", callback_data=f"rbw_send_{rb_id}"),
            ])
    buttons.append([InlineKeyboardButton(text="➕ إنشاء إذاعة دورية", callback_data="rbw_create")])
    buttons.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_broadcast_menu")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    try:
        await callback.answer()
    except Exception:
        pass


# ── Start / Stop / Delete ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rbw_stop_"))
async def cb_rbw_stop(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    rb_id = int(callback.data.split("_")[-1])
    await set_recurring_broadcast_active(rb_id, False)
    try:
        await callback.answer("⏸ تم الإيقاف.", show_alert=True)
    except Exception:
        pass
    await cb_admin_recurring_bw(callback)


@router.callback_query(F.data.startswith("rbw_start_"))
async def cb_rbw_start(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    rb_id = int(callback.data.split("_")[-1])
    await set_recurring_broadcast_active(rb_id, True)
    try:
        await callback.answer("▶️ تم التشغيل.", show_alert=True)
    except Exception:
        pass
    await cb_admin_recurring_bw(callback)


@router.callback_query(F.data.startswith("rbw_del_"))
async def cb_rbw_del(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    rb_id = int(callback.data.split("_")[-1])
    await delete_recurring_broadcast(rb_id)
    try:
        await callback.answer("🗑 تم الحذف.", show_alert=True)
    except Exception:
        pass
    await cb_admin_recurring_bw(callback)


# ── Edit Text ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rbw_edit_"))
async def cb_rbw_edit(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    rb_id = int(callback.data.split("_")[-1])
    rb = await get_recurring_broadcast(rb_id)
    if not rb:
        await callback.answer("❌ الإذاعة غير موجودة.", show_alert=True)
        return
    await state.update_data(rbw_edit_id=rb_id)
    await callback.message.answer(
        f"📝 <b>تعديل الإذاعة الدورية #{rb_id}</b>\n\n"
        f"النص الحالي:\n<blockquote>{(rb['text'] or '')[:200]}</blockquote>\n\n"
        f"أرسل النص الجديد:\n(لإلغاء أرسل /cancel)",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(AdminEdit.waiting_for_rbw_edit_text)
    await callback.answer()


@router.message(AdminEdit.waiting_for_rbw_edit_text)
async def process_rbw_edit_text(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
    data = await state.get_data()
    rb_id = data.get("rbw_edit_id")
    new_text = message.html_text or message.text
    await update_recurring_broadcast_text(rb_id, new_text)
    await message.answer(f"✅ تم تحديث نص الإذاعة الدورية #{rb_id} بنجاح!")
    await state.clear()


# ── Preview ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rbw_preview_"))
async def cb_rbw_preview(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    rb_id = int(callback.data.split("_")[-1])
    rb = await get_recurring_broadcast(rb_id)
    if not rb:
        await callback.answer("❌ الإذاعة غير موجودة.", show_alert=True)
        return
    try:
        await send_media_message(
            bot, callback.from_user.id,
            f"👁 <b>معاينة الإذاعة الدورية #{rb_id}:</b>\n\n{rb['text'] or ''}",
            media_id=rb.get("media_id"),
            media_type=rb.get("media_type"),
        )
        await callback.answer("✅ تم إرسال المعاينة.", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ خطأ: {str(e)[:100]}", show_alert=True)


# ── Send Now (manual trigger) ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rbw_send_"))
async def cb_rbw_send(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    rb_id = int(callback.data.split("_")[-1])
    rb = await get_recurring_broadcast(rb_id)
    if not rb:
        await callback.answer("❌ الإذاعة غير موجودة.", show_alert=True)
        return
    await callback.answer("🚀 جاري النشر...", show_alert=True)
    asyncio.create_task(execute_recurring_broadcast_cycle(
        rb_id, rb["target"], rb["text"],
        rb.get("media_id"), rb.get("media_type"),
        bool(rb.get("is_vip")), rb.get("stars", 0),
    ))


# ── Create Wizard ────────────────────────────────────────────────────────────

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
