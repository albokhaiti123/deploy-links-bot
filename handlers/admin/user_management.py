"""
Owner user/group management handler.
Only ADMIN_ID can access this panel.
"""

from aiogram import Router, F, types
from aiogram.enums import ParseMode

from core.config import ADMIN_ID
from models.groups import get_all_groups_paginated, get_group_counts
from models.settings import get_setting, set_setting
from models.user_campaigns import (
    get_current_campaign, suspend_all_active_campaigns,
    get_campaign_by_id,
)
from services.group_manager import leave_group
from models.users import get_all_user_ids

router = Router(name="admin_user_management")

PAGE_SIZE = 10


def _owner_only(user_id: int) -> bool:
    return user_id == ADMIN_ID


# ── Global feature switch ────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_toggle_user_campaigns")
async def cb_toggle_user_campaigns(callback: types.CallbackQuery):
    if not _owner_only(callback.from_user.id):
        await callback.answer("Owner only.", show_alert=True)
        return

    current = await get_setting("user_campaigns_enabled")
    if current == "true":
        # Disable: increment generation, suspend all campaigns
        gen_val = await get_setting("user_campaigns_generation")
        try:
            gen = int(gen_val) + 1
        except (ValueError, TypeError):
            gen = 2
        await set_setting("user_campaigns_generation", str(gen))
        await set_setting("user_campaigns_enabled", "false")
        count = await suspend_all_active_campaigns()
        await callback.answer(
            f"✅ User campaigns disabled. {count} campaigns suspended.",
            show_alert=True,
        )
    else:
        # Re-enable — campaigns stay suspended, users resume manually
        await set_setting("user_campaigns_enabled", "true")
        await callback.answer(
            "✅ User campaigns enabled. Existing campaigns remain suspended until users resume them.",
            show_alert=True,
        )

    # Refresh admin panel
    from handlers.admin.panel import get_admin_keyboard
    promo_enabled = await get_setting("promo_enabled")
    text = "━━━━━━━━━━━━━━\n⚙️ <b>لوحة التحكم</b>\n━━━━━━━━━━━━━━"
    await callback.message.edit_text(
        text, reply_markup=get_admin_keyboard(promo_enabled, callback.from_user.id),
        parse_mode=ParseMode.HTML,
    )


# ── Groups management ────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_all_groups")
@router.callback_query(F.data.startswith("admin_all_groups_p"))
async def cb_admin_all_groups(callback: types.CallbackQuery):
    if not _owner_only(callback.from_user.id):
        await callback.answer("Owner only.", show_alert=True)
        return

    page = 0
    if "admin_all_groups_p" in callback.data:
        try:
            page = int(callback.data.split("_p")[-1])
        except ValueError:
            page = 0

    offset = page * PAGE_SIZE
    rows = await get_all_groups_paginated(limit=PAGE_SIZE, offset=offset)
    active_count, total_count = await get_group_counts()

    if not rows:
        await callback.message.edit_text(
            f"🌐 <b>All Groups</b>\nActive: {active_count} / Total: {total_count}\n\nNo groups found.",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🔙 Back", callback_data="admin_main")]
            ]),
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
        return

    text = f"🌐 <b>All Groups</b> ({active_count} active / {total_count} total) — Page {page+1}\n\n"
    buttons = []
    health_icons = {"ok": "✅", "no_permission": "🚫", "banned": "❌",
                    "left": "👋", "upgraded": "🔄", "unreachable": "⚠️", "unknown": "❓"}

    for chat_id, title, status, health, owner_id, fail_count in rows:
        icon = health_icons.get(health or "unknown", "❓")
        label = (title or f"{chat_id}")[:25]
        status_str = "🟢" if status == "active" else "🔴"
        text += f"{status_str} {icon} <b>{label}</b> (owner: {owner_id or '?'})\n"
        buttons.append([
            types.InlineKeyboardButton(
                text=f"🗑 Remove: {label[:20]}",
                callback_data=f"owner_leave_group_{chat_id}"
            )
        ])

    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton(text="◀️", callback_data=f"admin_all_groups_p{page-1}"))
    if len(rows) == PAGE_SIZE:
        nav.append(types.InlineKeyboardButton(text="▶️", callback_data=f"admin_all_groups_p{page+1}"))
    if nav:
        buttons.append(nav)

    buttons.append([types.InlineKeyboardButton(text="🔙 Back", callback_data="admin_main")])
    await callback.message.edit_text(
        text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("owner_leave_group_"))
async def cb_owner_leave_group(callback: types.CallbackQuery):
    if not _owner_only(callback.from_user.id):
        await callback.answer("Owner only.", show_alert=True)
        return
    chat_id = int(callback.data.split("_")[-1])
    success, msg = await leave_group(chat_id, callback.from_user.id)
    await callback.answer(f"{'✅' if success else '❌'} {msg}", show_alert=True)
    # Refresh page
    await cb_admin_all_groups(callback)
