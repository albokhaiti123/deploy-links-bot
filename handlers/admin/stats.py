"""
Stats and Groups list handlers.
"""

from aiogram import Router, F, types
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from models.admins import is_admin
from models.users import get_total_users, get_users_since
from models.groups import get_group_counts, get_recent_groups
from models.events import count_events, count_events_since

router = Router(name="admin_stats")


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    total_users = await get_total_users()
    users_today = await get_users_since("datetime('now', '-1 day')")
    active_groups, total_groups = await get_group_counts()
    total_promos = await count_events("promo_sent")
    promos_today = await count_events_since("promo_sent", "datetime('now', '-1 day')")

    text = (
        "📊 <b>الإحصائيات</b>\n\n"
        f"👥 إجمالي المستخدمين: <b>{total_users}</b> (اليوم: {users_today})\n"
        f"🌐 المجموعات النشطة: <b>{active_groups}</b> / الإجمالي: {total_groups}\n"
        f"📢 إجمالي الترويجات: <b>{total_promos}</b> (اليوم: {promos_today})"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_main")],
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()


@router.callback_query(F.data == "admin_groups")
async def cb_admin_groups(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    groups = await get_recent_groups(20)
    if not groups:
        text = "🌐 <b>المجموعات:</b>\n\nلا توجد مجموعات مسجلة حتى الآن."
    else:
        text = "🌐 <b>آخر 20 مجموعة:</b>\n\n"
        for chat_id, title, status, added_at in groups:
            status_icon = "✅" if status == "active" else "❌"
            text += f"{status_icon} <b>{title or 'بدون اسم'}</b>\n  └ <code>{chat_id}</code>\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_main")],
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()
