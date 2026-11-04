"""
User group management handler.
Allows ordinary users to view and manage their own groups (reward_owner_id).
ADMIN_ID can view all groups via admin/user_management.py.
"""

from aiogram import Router, F, types
from aiogram.enums import ParseMode

from core.config import ADMIN_ID
from models.groups import get_user_active_groups
from services.group_manager import leave_group

router = Router(name="user_my_groups")

HEALTH_ICONS = {
    "ok": "✅",
    "no_permission": "🚫",
    "banned": "❌",
    "left": "👋",
    "upgraded": "🔄",
    "unreachable": "⚠️",
    "unknown": "❓",
}


@router.callback_query(F.data == "user_my_groups")
async def cb_user_my_groups(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id == ADMIN_ID:
        await callback.answer("Use /admin for owner group management.", show_alert=True)
        return

    groups = await get_user_active_groups(user_id)
    if not groups:
        text = (
            "📱 <b>My Groups</b>\n\n"
            "You have no registered groups yet.\n\n"
            "To register a group, add this bot to your Telegram group."
        )
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔙 Back", callback_data="user_menu")]
        ])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        await callback.answer()
        return

    text = f"📱 <b>My Groups</b> ({len(groups)} registered)\n\n"
    buttons = []
    for chat_id, title, health in groups:
        icon = HEALTH_ICONS.get(health or "unknown", "❓")
        label = (title or f"Group {chat_id}")[:30]
        text += f"{icon} <b>{label}</b>\n"
        buttons.append([
            types.InlineKeyboardButton(
                text=f"🗑 Remove bot from: {label[:20]}",
                callback_data=f"user_leave_group_{chat_id}"
            )
        ])

    buttons.append([types.InlineKeyboardButton(text="🔙 Back", callback_data="user_menu")])
    kb = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()


@router.callback_query(F.data.startswith("user_leave_group_"))
async def cb_user_leave_group_confirm(callback: types.CallbackQuery):
    chat_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text="✅ Yes, remove bot", callback_data=f"user_leave_confirm_{chat_id}"
            ),
            types.InlineKeyboardButton(text="❌ Cancel", callback_data="user_my_groups"),
        ]
    ])
    await callback.message.edit_text(
        f"⚠️ Are you sure you want to remove the bot from group <code>{chat_id}</code>?\n\n"
        "This will stop all broadcasts to this group.",
        reply_markup=kb, parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("user_leave_confirm_"))
async def cb_user_leave_confirm(callback: types.CallbackQuery):
    chat_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id

    success, msg = await leave_group(chat_id, user_id)
    text = f"✅ {msg}" if success else f"❌ {msg}"
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔙 My Groups", callback_data="user_my_groups")]
    ]))
    try:
        await callback.answer()
    except Exception:
        pass
