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

    # ── Phase 7: Interactive User Campaign Wizard ───────────────────────────
    # Step 1: Text
    "uc_step1_text_prompt": (
        "📝 <b>Step 1/6 — Campaign Text (optional)</b>\n\n"
        "Send your campaign message text (HTML formatting and links supported).\n"
        "Or tap Skip below if you want a photo-only campaign."
    ),
    "uc_btn_skip_text": "⏭ Skip Text",
    "uc_btn_cancel": "❌ Cancel",
    "uc_err_text_required": "❌ Please send campaign text, tap Skip, or send /cancel.",
    "uc_cancelled": "❌ Campaign creation cancelled. No daily quota was consumed.",

    # Step 2: Photo
    "uc_step2_photo_prompt": (
        "📸 <b>Step 2/6 — Campaign Photo (optional)</b>\n\n"
        "Send a photo to attach to your campaign, or tap Skip for text-only."
    ),
    "uc_btn_skip_photo": "⏭ Skip Photo",
    "uc_err_photo_input": "❌ Please send a photo, tap Skip, or send /cancel.",
    "uc_err_cannot_skip_both": (
        "❌ Cannot skip photo because you already skipped text.\n"
        "A campaign must have either text or a photo. Please send a photo or /cancel."
    ),

    # Step 3: Two-Step Interactive Button Builder
    "uc_step3_buttons_prompt": (
        "🔘 <b>Step 3/6 — Campaign Buttons ({count}/{max_buttons})</b>\n\n"
        "{list_text}\n\n"
        "You can add up to {max_buttons} URL buttons below your message, or continue directly."
    ),
    "uc_buttons_empty_list": "<i>No buttons added yet.</i>",
    "uc_btn_add_button": "➕ Add Button",
    "uc_btn_add_another_button": "➕ Add Another Button",
    "uc_btn_remove_button": "🗑 Remove: {idx}. {label}",
    "uc_btn_continue": "✅ Continue to Next Step",
    "uc_btn_label_prompt": (
        "🏷 <b>Add Button ({num}/{max_buttons}) — Step 1/2: Button Label</b>\n\n"
        "Send the <b>button label</b> that users will see (up to 64 characters):"
    ),
    "uc_err_btn_label_invalid": "❌ Please send a valid button label (1 to 64 characters) or /cancel.",
    "uc_btn_url_prompt": (
        "🔗 <b>Step 2/2: URL for «{label}»</b>\n\n"
        "Now send the <b>button URL</b> (must start with <code>https://</code>, <code>http://</code>, or <code>tg://</code>):"
    ),
    "uc_err_btn_url_invalid": (
        "❌ Invalid URL.\n"
        "Must start with <code>https://</code>, <code>http://</code>, or <code>tg://</code> with no spaces."
    ),
    "uc_btn_added_toast": "✅ Added button «{label}»",
    "uc_btn_removed_toast": "🗑 Button removed",
    "uc_btn_max_reached": "⚠️ Maximum limit reached ({max_buttons} buttons).",

    # Step 4: Interactive Groups Picker
    "uc_step4_groups_prompt": (
        "👥 <b>Step 4/6 — Select Target Groups</b>\n\n"
        "Tap groups below to toggle selection:\n"
        "📌 <b>Currently Selected:</b> {selected_count} of {total_count} group(s)"
    ),
    "uc_no_groups": "⚠️ You have no active groups yet. Add the bot as an admin to your groups first.",
    "uc_btn_select_all": "☑️ Select All",
    "uc_btn_clear_all": "⬜ Clear All",
    "uc_btn_confirm_groups": "✅ Confirm Groups ({count})",
    "uc_err_no_groups_selected": "⚠️ Please select at least one group before continuing.",
    "uc_err_groups_input": "❌ Invalid selection. Use the buttons or enter group numbers like: 1,2,3 or all",

    # Step 5: Schedule Mode Picker
    "uc_step5_mode_prompt": (
        "⏰ <b>Step 5/6 — Delivery Schedule</b>\n\n"
        "Choose immediate one-time delivery, or recurring delivery every few hours:"
    ),
    "uc_btn_mode_now": "🚀 Send Immediately (Once)",
    "uc_btn_mode_rec_6": "🔄 Every 6 Hours",
    "uc_btn_mode_rec_12": "🔄 Every 12 Hours",
    "uc_btn_mode_rec_24": "🔄 Every 24 Hours",
    "uc_btn_mode_rec_48": "🔄 Every 48 Hours",
    "uc_btn_mode_rec_custom": "⚙️ Custom Interval (Hours)",
    "uc_custom_hours_prompt": "⏱ Send the recurring interval in hours as a whole number (minimum <b>6</b>, maximum <b>720</b>):",
    "uc_err_mode_input": "❌ Please pick a schedule button, enter 'now', or send hours (min 6).",
    "uc_err_min_hours": "❌ Minimum recurring interval is 6 hours (maximum 720 hours).",

    # Step 6: Auto-Delete Timer Picker
    "uc_step6_autodel_prompt": (
        "🗑 <b>Step 6/6 — Auto-Delete Timer (optional)</b>\n\n"
        "Should the campaign message be automatically deleted from groups after a set time?"
    ),
    "uc_btn_autodel_none": "♾ No Auto-Delete",
    "uc_btn_autodel_1h": "⏱ After 1 Hour (1h)",
    "uc_btn_autodel_6h": "⏱ After 6 Hours (6h)",
    "uc_btn_autodel_24h": "⏱ After 24 Hours (24h)",

    # Step 7: Live Preview & Single-Field Edit
    "uc_preview_header": "👁 <b>Live Preview (exact appearance in groups):</b>",
    "uc_preview_summary": (
        "📋 <b>Campaign Summary Before Launch</b>\n\n"
        "👥 <b>Target Groups:</b> {groups_count}\n"
        "🔘 <b>Attached Buttons:</b> {buttons_count}\n"
        "⏰ <b>Delivery Mode:</b> {mode_label}\n"
        "🗑 <b>Auto-Delete:</b> {autodel_label}\n"
        "{replace_note}\n"
        "💡 <i>Daily quota (5 campaigns/day) is only consumed when you tap «Confirm & Launch».</i>"
    ),
    "uc_mode_label_immediate": "🚀 Immediate Delivery",
    "uc_mode_label_recurring": "🔄 Recurring every {hours}h",
    "uc_autodel_label_none": "♾ No Auto-Delete",
    "uc_autodel_label_hours": "⏱ After {hours}h",
    "uc_replace_warning_note": "\n⚠️ <b>Note:</b> Launching this campaign will replace your current active/paused campaign.\n",
    "uc_btn_confirm_launch": "🚀 Confirm & Launch Campaign",
    "uc_btn_edit_campaign": "✏️ Edit Campaign",
    "uc_edit_menu_title": "✏️ <b>Choose what to edit:</b>\n\nAfter editing, you will return directly to the live preview.",
    "uc_btn_edit_text": "📝 Edit Text",
    "uc_btn_edit_photo": "📸 Edit Photo",
    "uc_btn_edit_buttons": "🔘 Edit Buttons",
    "uc_btn_edit_groups": "👥 Edit Groups",
    "uc_btn_edit_mode": "⏰ Edit Schedule",
    "uc_btn_edit_autodel": "🗑 Edit Auto-Delete",
    "uc_btn_back_preview": "👁 Back to Preview",
    "uc_launch_success_immediate": (
        "✅ <b>Immediate campaign #{cid} launched successfully!</b>\n\n"
        "🚀 Sending now to <b>{groups_count}</b> group(s)."
    ),
    "uc_launch_success_recurring": (
        "✅ <b>Recurring campaign #{cid} activated successfully!</b>\n\n"
        "🔄 Will post automatically every <b>{hours}h</b> to <b>{groups_count}</b> group(s)."
    ),
    "uc_launch_failed": "❌ Failed to create campaign: {error}",
}
