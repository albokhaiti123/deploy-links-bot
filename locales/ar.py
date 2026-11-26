"""
Arabic (ar) locale strings for Deploy Links Bot.
All keys MUST match exactly with en.py for parity checks.
"""

STRINGS: dict[str, str] = {
    # ── Language switcher ──────────────────────────────────────────────────
    "lang_title": "🌐 اختيار اللغة",
    "lang_changed": "✅ تم تغيير اللغة إلى العربية",
    "btn_lang_ar": "🇸🇦 العربية",
    "btn_lang_en": "🇬🇧 English",
    "btn_lang_switch": "🌐 اللغة / Language",

    # ── Referral screen ────────────────────────────────────────────────────
    "btn_my_referral": "🔗 رابط الإحالة الخاص بي",
    "referral_title": "🔗 <b>رابط الإحالة الخاص بك (دائم):</b>",
    "referral_count": "👥 <b>عدد المنضمين عبر رابطك:</b>",
    "referral_hint": "💡 <i>اضغط على الرابط لنسخه. يمكنك الوصول إليه دائماً عبر هذا الزر.</i>",
    "btn_share_link": "📤 مشاركة الرابط",
    "btn_back": "🔙 رجوع",
    "referral_share_text": "انضم عبر رابط الإحالة الخاص بي!",

    # ── My Groups screen ───────────────────────────────────────────────────
    "my_groups_title": "📱 <b>مجموعاتي</b>",
    "my_groups_empty": (
        "📱 <b>مجموعاتي</b>\n\n"
        "لا توجد مجموعات مسجلة بعد.\n\n"
        "لتسجيل مجموعة، أضف هذا البوت إلى مجموعة تيليجرام الخاصة بك."
    ),
    "my_groups_header": "📱 <b>مجموعاتي</b> ({count} مسجلة)\n\n",

    # ── Campaign progress screen ───────────────────────────────────────────
    "camp_locked_msg": (
        "🔒 <b>{title}</b>\n\n"
        "✅ المجموعات المضافة: <b>{verified}/{required}</b>\n\n"
        "📋 لفتح هذا المحتوى، أضف البوت إلى <b>{remaining}</b> مجموعة إضافية وتحقق منها.\n\n"
        "🤖 رابط البوت: <code>https://t.me/{bot_username}</code>"
    ),
    "camp_unlocked_msg": "🎉 <b>تهانينا!</b> لقد فتحت المحتوى.",
    "btn_verify": "✅ تحقق الآن",
    "btn_camp_back": "🔙 رجوع",
    "verify_cooldown_alert": "⏳ يرجى الانتظار {seconds} ثانية قبل التحقق مرة أخرى.",
    "verify_already_verified": "✅ تم التحقق بالفعل من هذه المجموعة.",
    "verify_bot_not_in_group": "❌ البوت ليس موجوداً في هذه المجموعة بعد.",

    # ── Start / welcome buttons ────────────────────────────────────────────
    "btn_back_to_start": "🔙 رجوع للبداية",
    "btn_my_dashboard": "👤 لوحتي",

    # ── Admin-panel (non-translated — just the Back button label) ──────────
    "btn_admin_back": "🔙 لوحة التحكم",

    # ── Owner invite errors ────────────────────────────────────────────────
    "invite_paused": "⛔️ عذراً، رابط الدعوة هذا متوقف حالياً من قِبل إدارة البوت.",
    "invite_expired": "⌛️ عذراً، انتهت صلاحية رابط الدعوة المؤقت هذا.",
    "invite_invalid": "❌ عذراً، رابط الدعوة هذا غير صالح أو تم حذفه.",
}
