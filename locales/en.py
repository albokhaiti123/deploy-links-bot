"""
English (en) locale strings for Deploy Links Bot.
All keys MUST match exactly with ar.py for parity checks.
This is the fallback language.
"""

STRINGS: dict[str, str] = {
    # ── Language switcher ──────────────────────────────────────────────────
    "lang_title": "🌐 Choose Language",
    "lang_changed": "✅ Language changed to English",
    "btn_lang_ar": "🇸🇦 العربية",
    "btn_lang_en": "🇬🇧 English",
    "btn_lang_switch": "🌐 اللغة / Language",

    # ── Referral screen ────────────────────────────────────────────────────
    "btn_my_referral": "🔗 My Referral Link",
    "referral_title": "🔗 <b>Your permanent referral link:</b>",
    "referral_count": "👥 <b>Users joined via your link:</b>",
    "referral_hint": "💡 <i>Tap the link to copy it. You can always access it from this button.</i>",
    "btn_share_link": "📤 Share Link",
    "btn_back": "🔙 Back",
    "referral_share_text": "Join using my referral link!",

    # Phase 6: Full referral body
    "referral_body": (
        "🔗 <b>Your permanent referral link:</b>\n\n"
        "<code>{url}</code>\n\n"
        "👥 <b>Users joined via your link:</b> {count}\n\n"
        "💡 <i>Tap the link to copy it. You can always access it from this button.</i>"
    ),

    # ── My Groups screen ───────────────────────────────────────────────────
    "my_groups_title": "📱 <b>My Groups</b>",
    "my_groups_empty": (
        "📱 <b>My Groups</b>\n\n"
        "You have no registered groups yet.\n\n"
        "To register a group, add this bot to your Telegram group."
    ),
    "my_groups_header": "📱 <b>My Groups</b> ({count} registered)\n\n",

    # ── Campaign progress screen ───────────────────────────────────────────
    "camp_locked_msg": (
        "🔒 <b>{title}</b>\n\n"
        "✅ Groups added: <b>{verified}/{required}</b>\n\n"
        "📋 To unlock this content, add the bot to <b>{remaining}</b> more group(s) and verify.\n\n"
        "🤖 Bot link: <code>https://t.me/{bot_username}</code>"
    ),
    "camp_unlocked_msg": "🎉 <b>Congratulations!</b> You have unlocked the content.",
    "btn_verify": "✅ Verify Now",
    "btn_camp_back": "🔙 Back",
    "verify_cooldown_alert": "⏳ Please wait {seconds} seconds before verifying again.",
    "verify_already_verified": "✅ This group has already been verified.",
    "verify_bot_not_in_group": "❌ The bot is not in that group yet.",

    # ── Start / welcome buttons ────────────────────────────────────────────
    "btn_back_to_start": "🔙 Back",
    "btn_my_dashboard": "👤 My Dashboard",

    # ── Admin-panel back button ────────────────────────────────────────────
    "btn_admin_back": "🔙 Admin Panel",

    # ── Owner invite errors ────────────────────────────────────────────────
    "invite_paused": "⛔️ Sorry, this invite link is currently paused by the bot administration.",
    "invite_expired": "⌛️ Sorry, this temporary invite link has expired.",
    "invite_invalid": "❌ Sorry, this invite link is invalid or has been deleted.",

    # ── Phase 6: General admin ─────────────────────────────────────────────
    "btn_cancel": "❌ Cancel",
    "admin_cancelled": "❌ Operation cancelled.",

    # ── Phase 6: Invite link admin keys ────────────────────────────────────
    "inv_owner_only": "⛔️ This section is restricted to the bot owner only.",
    "inv_owner_only_short": "⛔️ Bot owner only.",
    "inv_status_active": "🟢 Active",
    "inv_status_paused": "⏸ Manually Paused",
    "inv_status_expired": "⌛️ Expired",
    "inv_type_permanent": "♾ Permanent",
    "inv_type_temporary": "⏳ Temporary",
    "inv_list_title": "🔗 <b>Bot Invite Links Management (Owner):</b>\n\n",
    "inv_list_empty": "No invite links have been generated yet.",
    "inv_list_choose": "Select a link below to view details, pause, or delete it:\n\n",
    "inv_list_item": "{icon} <b>{title}</b> ({type_label}) — Joins: <b>{joins}</b> | Clicks: {clicks}\n",
    "inv_list_btn_item": "{icon} {title} ({joins} joins)",
    "inv_default_title": "Link #{id}",
    "inv_btn_create": "➕ Generate New Invite Link",
    "inv_create_prompt": (
        "🏷 <b>Generate New Invite Link</b>\n\n"
        "Send a descriptive label for the link (e.g. <i>Channel Ad</i>), or send /skip.\n"
        "Send /cancel to abort."
    ),
    "inv_label_invalid": "❌ Please send the link label as text, /skip, or /cancel.",
    "inv_create_cancelled": "❌ Invite link creation cancelled.",
    "inv_choose_type_prompt": (
        "⚙️ <b>Choose Invite Link Type:</b>\n\n"
        "• <b>♾ Permanent:</b> Stays active until you manually pause or delete it.\n"
        "• <b>⏳ Temporary:</b> Expires automatically after your chosen duration."
    ),
    "inv_btn_type_perm": "♾ Permanent Link",
    "inv_btn_type_temp": "⏳ Temporary Link (Timed)",
    "inv_not_found": "❌ This invite link does not exist or has been deleted.",
    "inv_exp_line": "⏰ <b>Expires at:</b> <code>{expires_at}</code>\n",
    "inv_detail_body": (
        "{prefix}"
        "🔗 <b>Invite Link Details: {title}</b>\n\n"
        "📎 <b>Link:</b>\n<code>{url}</code>\n\n"
        "📌 <b>Type:</b> {type_text}\n"
        "📊 <b>Status:</b> {status_text}\n"
        "{exp_line}"
        "👆 <b>Total Clicks:</b> {clicks}\n"
        "👥 <b>Unique Joins:</b> {joins}\n"
        "📅 <b>Created At:</b> <code>{created_at}</code>"
    ),
    "inv_btn_pause": "⏸ Pause Link Manually",
    "inv_btn_resume": "▶️ Resume Link",
    "inv_btn_delete": "🗑 Delete Link Permanently",
    "inv_btn_back_list": "🔙 Back to Invite Links",
    "inv_created_perm_notice": "✅ <b>Permanent invite link generated successfully!</b>\n\n",
    "inv_created_perm_toast": "✅ Permanent link generated",
    "inv_created_temp_notice": "✅ <b>Temporary invite link ({hours}h) generated successfully!</b>\n\n",
    "inv_created_temp_toast": "✅ Temporary link generated",
    "inv_choose_hours_prompt": (
        "⏳ <b>Set Temporary Link Duration:</b>\n\n"
        "Choose a preset below, or send the number of hours (between 1 and 8760):"
    ),
    "inv_dur_1h": "1 Hour (1h)",
    "inv_dur_6h": "6 Hours (6h)",
    "inv_dur_24h": "24 Hours (1d)",
    "inv_dur_168h": "7 Days (168h)",
    "inv_hours_invalid_type": "❌ Please send the number of hours as digits only (e.g. 12) or /cancel.",
    "inv_hours_invalid_range": "❌ Please send a valid integer between 1 and 8760 hours.",
    "inv_paused_notice": "⏸ <b>Invite link has been manually paused.</b>\n\n",
    "inv_paused_toast": "⏸ Link manually paused",
    "inv_resumed_notice": "▶️ <b>Invite link has been resumed successfully.</b>\n\n",
    "inv_resumed_toast": "▶️ Link resumed",
    "inv_del_confirm_prompt": (
        "⚠️ <b>Confirm Deletion:</b>\n\n"
        "Are you sure you want to permanently delete invite link #{id}? This cannot be undone."
    ),
    "inv_btn_del_confirm": "✅ Yes, Delete Permanently",
    "inv_btn_del_cancel": "🔙 Cancel",
    "inv_deleted_toast": "🗑 Invite link permanently deleted",

    # ── Phase 6: Admin management ──────────────────────────────────────────
    "admin_owner_protected": "⛔️ You cannot modify the main owner's permissions.",
    "admin_id_invalid": "❌ Please send a valid numeric Telegram ID.\nTry again or send /cancel",
    "admin_added_success": "✅ Admin <code>{tid}</code> added successfully!",
    "admin_removed_success": "✅ Admin <code>{tid}</code> removed successfully!",

    # ── Phase 6: Broadcast & campaign completion ───────────────────────────
    "admin_bcast_done": "✅ Broadcast complete! Sent successfully to <b>{success}</b> target(s).",
    "admin_camp_not_found": "❌ Campaign not found.",
    "admin_camp_bcast_done": "✅ Campaign broadcast complete! Sent to <b>{success}</b> target(s).",
}
