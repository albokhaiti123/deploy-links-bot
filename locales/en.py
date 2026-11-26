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

    # ── Admin-panel (non-translated — just the Back button label) ──────────
    "btn_admin_back": "🔙 Admin Panel",

    # ── Owner invite errors ────────────────────────────────────────────────
    "invite_paused": "⛔️ Sorry, this invite link is currently paused by the bot administration.",
    "invite_expired": "⌛️ Sorry, this temporary invite link has expired.",
    "invite_invalid": "❌ Sorry, this invite link is invalid or has been deleted.",
}
