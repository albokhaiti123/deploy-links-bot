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

    # Phase 6: Full referral body
    "referral_body": (
        "🔗 <b>رابط الإحالة الخاص بك (دائم):</b>\n\n"
        "<code>{url}</code>\n\n"
        "👥 <b>عدد المنضمين عبر رابطك:</b> {count}\n\n"
        "💡 <i>اضغط على الرابط لنسخه. يمكنك الوصول إليه دائماً عبر هذا الزر.</i>"
    ),

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

    # ── Admin-panel back button ────────────────────────────────────────────
    "btn_admin_back": "🔙 لوحة التحكم",

    # ── Owner invite errors ────────────────────────────────────────────────
    "invite_paused": "⛔️ عذراً، رابط الدعوة هذا متوقف حالياً من قِبل إدارة البوت.",
    "invite_expired": "⌛️ عذراً، انتهت صلاحية رابط الدعوة المؤقت هذا.",
    "invite_invalid": "❌ عذراً، رابط الدعوة هذا غير صالح أو تم حذفه.",

    # ── Phase 6: General admin ─────────────────────────────────────────────
    "btn_cancel": "❌ إلغاء",
    "admin_cancelled": "❌ تم الإلغاء.",

    # ── Phase 6: Invite link admin keys ────────────────────────────────────
    "inv_owner_only": "⛔️ هذا القسم مخصص لمالك البوت فقط.",
    "inv_owner_only_short": "⛔️ للمالك فقط.",
    "inv_status_active": "🟢 نشط",
    "inv_status_paused": "⏸ متوقف يدوياً",
    "inv_status_expired": "⌛️ منتهي الصلاحية",
    "inv_type_permanent": "♾ دائم",
    "inv_type_temporary": "⏳ مؤقت",
    "inv_list_title": "🔗 <b>إدارة روابط دعوة البوت (للمالك):</b>\n\n",
    "inv_list_empty": "لا توجد روابط دعوة مولدة حتى الآن.",
    "inv_list_choose": "اختر رابطاً من القائمة لعرض تفاصيله أو إيقافه أو حذفه:\n\n",
    "inv_list_item": "{icon} <b>{title}</b> ({type_label}) — المنضمون: <b>{joins}</b> | النقرات: {clicks}\n",
    "inv_list_btn_item": "{icon} {title} ({joins} منضم)",
    "inv_default_title": "رابط #{id}",
    "inv_btn_create": "➕ توليد رابط دعوة جديد",
    "inv_create_prompt": (
        "🏷 <b>توليد رابط دعوة جديد</b>\n\n"
        "أرسل اسماً توضيحياً للرابط (مثلاً: <i>إعلان قناة التوصيات</i>)، أو أرسل /skip للتخطي.\n"
        "لإلغاء العملية أرسل /cancel"
    ),
    "inv_label_invalid": "❌ يرجى إرسال اسم الرابط كنص أو /skip أو /cancel.",
    "inv_create_cancelled": "❌ تم إلغاء توليد الرابط.",
    "inv_choose_type_prompt": (
        "⚙️ <b>اختر نوع رابط الدعوة:</b>\n\n"
        "• <b>♾ دائم:</b> يعمل باستمرار حتى تقوم بإيقافه يدوياً أو حذفه.\n"
        "• <b>⏳ مؤقت:</b> ينتهي تلقائياً بعد عدد الساعات الذي تحدده."
    ),
    "inv_btn_type_perm": "♾ رابط دائم",
    "inv_btn_type_temp": "⏳ رابط مؤقت (بمدة محددة)",
    "inv_not_found": "❌ هذا الرابط غير موجود أو تم حذفه.",
    "inv_exp_line": "⏰ <b>ينتهي في:</b> <code>{expires_at}</code>\n",
    "inv_detail_body": (
        "{prefix}"
        "🔗 <b>تفاصيل رابط الدعوة: {title}</b>\n\n"
        "📎 <b>الرابط:</b>\n<code>{url}</code>\n\n"
        "📌 <b>النوع:</b> {type_text}\n"
        "📊 <b>الحالة:</b> {status_text}\n"
        "{exp_line}"
        "👆 <b>إجمالي النقرات:</b> {clicks}\n"
        "👥 <b>المستخدمون المنضمون:</b> {joins}\n"
        "📅 <b>تاريخ الإنشاء:</b> <code>{created_at}</code>"
    ),
    "inv_btn_pause": "⏸ إيقاف الرابط يدوياً",
    "inv_btn_resume": "▶️ إعادة تفعيل الرابط",
    "inv_btn_delete": "🗑 حذف الرابط نهائياً",
    "inv_btn_back_list": "🔙 رجوع لقائمة الروابط",
    "inv_created_perm_notice": "✅ <b>تم توليد رابط الدعوة الدائم بنجاح!</b>\n\n",
    "inv_created_perm_toast": "✅ تم توليد الرابط الدائم",
    "inv_created_temp_notice": "✅ <b>تم توليد رابط الدعوة المؤقت ({hours} ساعة) بنجاح!</b>\n\n",
    "inv_created_temp_toast": "✅ تم توليد الرابط المؤقت",
    "inv_choose_hours_prompt": (
        "⏳ <b>تحديد مدة الرابط المؤقت:</b>\n\n"
        "اختر مدة جاهزة من الأزرار أدناه، أو أرسل عدد الساعات رقماً (بين 1 و 8760):"
    ),
    "inv_dur_1h": "ساعة واحدة (1h)",
    "inv_dur_6h": "6 ساعات (6h)",
    "inv_dur_24h": "24 ساعة (1d)",
    "inv_dur_168h": "7 أيام (168h)",
    "inv_hours_invalid_type": "❌ يرجى إرسال عدد الساعات كأرقام فقط (مثلاً 12) أو /cancel.",
    "inv_hours_invalid_range": "❌ يرجى إرسال رقم صحيح بين 1 و 8760 ساعة.",
    "inv_paused_notice": "⏸ <b>تم إيقاف الرابط يدوياً.</b>\n\n",
    "inv_paused_toast": "⏸ تم إيقاف الرابط يدوياً",
    "inv_resumed_notice": "▶️ <b>تمت إعادة تفعيل الرابط بنجاح.</b>\n\n",
    "inv_resumed_toast": "▶️ تم تفعيل الرابط",
    "inv_del_confirm_prompt": (
        "⚠️ <b>تأكيد الحذف:</b>\n\n"
        "هل أنت متأكد من حذف رابط الدعوة #{id} نهائياً؟ لا يمكن التراجع عن هذا الإجراء."
    ),
    "inv_btn_del_confirm": "✅ نعم، احذف الرابط نهائياً",
    "inv_btn_del_cancel": "🔙 تراجع",
    "inv_deleted_toast": "🗑 تم حذف الرابط نهائياً",

    # ── Phase 6: Admin management ──────────────────────────────────────────
    "admin_owner_protected": "⛔️ لا يمكنك تعديل صلاحيات المالك الرئيسي.",
    "admin_id_invalid": "❌ يرجى إرسال معرف رقمي صالح.\nحاول مجدداً أو أرسل /cancel",
    "admin_added_success": "✅ تم إضافة المشرف <code>{tid}</code> بنجاح!",
    "admin_removed_success": "✅ تم إزالة المشرف <code>{tid}</code> بنجاح!",

    # ── Phase 6: Broadcast & campaign completion ───────────────────────────
    "admin_bcast_done": "✅ اكتملت الإذاعة! تم الإرسال بنجاح إلى <b>{success}</b> جهة.",
    "admin_camp_not_found": "❌ الحملة غير موجودة.",
    "admin_camp_bcast_done": "✅ اكتمل نشر الحملة! تم الإرسال إلى <b>{success}</b> جهة.",
}
