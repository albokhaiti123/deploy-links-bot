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

    # ── Phase 7: Interactive User Campaign Wizard ───────────────────────────
    # Step 1: Text
    "uc_step1_text_prompt": (
        "📝 <b>الخطوة 1/6 — نص الحملة (اختياري)</b>\n\n"
        "أرسل نص الإعلان الذي تريد نشره (يدعم التنسيقات والروابط).\n"
        "أو اضغط على زر التخطي أدناه إذا كنت تريد حملة بصورة فقط."
    ),
    "uc_btn_skip_text": "⏭ تخطي النص",
    "uc_btn_cancel": "❌ إلغاء الإنشاء",
    "uc_err_text_required": "❌ يرجى إرسال نص الحملة، أو اضغط تخطي، أو أرسل /cancel.",
    "uc_cancelled": "❌ تم إلغاء إنشاء الحملة. لم يتم خصم أي شيء من حصتك اليومية.",

    # Step 2: Photo
    "uc_step2_photo_prompt": (
        "📸 <b>الخطوة 2/6 — صورة الحملة (اختياري)</b>\n\n"
        "أرسل صورة لإرفاقها مع الحملة، أو اضغط تخطي للاكتفاء بالنص فقط."
    ),
    "uc_btn_skip_photo": "⏭ تخطي الصورة",
    "uc_err_photo_input": "❌ يرجى إرسال صورة، أو اضغط تخطي، أو أرسل /cancel.",
    "uc_err_cannot_skip_both": (
        "❌ لا يمكنك تخطي الصورة لأنك قمت بتخطي النص مسبقاً.\n"
        "يجب أن تحتوي الحملة على نص أو صورة على الأقل. أرسل صورة الآن أو /cancel."
    ),

    # Step 3: Two-Step Interactive Button Builder
    "uc_step3_buttons_prompt": (
        "🔘 <b>الخطوة 3/6 — أزرار الحملة ({count}/{max_buttons})</b>\n\n"
        "{list_text}\n\n"
        "يمكنك إضافة حتى {max_buttons} أزرار روابط تظهر أسفل رسالتك، أو المتابعة مباشرة."
    ),
    "uc_buttons_empty_list": "<i>لا توجد أزرار مضافة حالياً.</i>",
    "uc_btn_add_button": "➕ إضافة زر",
    "uc_btn_add_another_button": "➕ إضافة زر آخر",
    "uc_btn_remove_button": "🗑 حذف: {idx}. {label}",
    "uc_btn_continue": "✅ متابعة للخطوة التالية",
    "uc_btn_label_prompt": (
        "🏷 <b>إضافة زر ({num}/{max_buttons}) — الخطوة 1/2: اسم الزر</b>\n\n"
        "أرسل <b>اسم الزر</b> الذي سيظهر للمستخدمين (حتى 64 حرفاً):"
    ),
    "uc_err_btn_label_invalid": "❌ يرجى إرسال نص صالح لاسم الزر (بين 1 و 64 حرفاً) أو أرسل /cancel.",
    "uc_btn_url_prompt": (
        "🔗 <b>الخطوة 2/2: رابط الزر «{label}»</b>\n\n"
        "أرسل الآن <b>رابط الزر</b> (يجب أن يبدأ بـ <code>https://</code> أو <code>http://</code> أو <code>tg://</code>):"
    ),
    "uc_err_btn_url_invalid": (
        "❌ الرابط غير صالح.\n"
        "يجب أن يبدأ بـ <code>https://</code> أو <code>http://</code> أو <code>tg://</code> بدون مسافات."
    ),
    "uc_btn_added_toast": "✅ تمت إضافة الزر «{label}»",
    "uc_btn_removed_toast": "🗑 تم حذف الزر",
    "uc_btn_max_reached": "⚠️ وصلت للحد الأقصى ({max_buttons} أزرار).",

    # Step 4: Interactive Groups Picker
    "uc_step4_groups_prompt": (
        "👥 <b>الخطوة 4/6 — اختيار المجموعات المستهدفة</b>\n\n"
        "اضغط على المجموعات لتحديدها أو إلغاء تحديدها:\n"
        "📌 <b>المحدد حالياً:</b> {selected_count} من {total_count} مجموعة"
    ),
    "uc_no_groups": "⚠️ لا توجد لديك مجموعات نشطة حالياً. أضف البوت كمشرف في مجموعاتك أولاً.",
    "uc_btn_select_all": "☑️ تحديد الكل",
    "uc_btn_clear_all": "⬜ إلغاء التحديد",
    "uc_btn_confirm_groups": "✅ تأكيد المجموعات ({count})",
    "uc_err_no_groups_selected": "⚠️ يرجى تحديد مجموعة واحدة على الأقل قبل المتابعة.",
    "uc_err_groups_input": "❌ اختيار غير صالح. استخدم الأزرار أو أرسل أرقام المجموعات مثل: 1,2,3 أو all",

    # Step 5: Schedule Mode Picker
    "uc_step5_mode_prompt": (
        "⏰ <b>الخطوة 5/6 — توقيت وطريقة الإرسال</b>\n\n"
        "اختر الإرسال الفوري لمرة واحدة، أو التكرار التلقائي كل عدة ساعات:"
    ),
    "uc_btn_mode_now": "🚀 إرسال فوري (مرة واحدة)",
    "uc_btn_mode_rec_6": "🔄 كل 6 ساعات",
    "uc_btn_mode_rec_12": "🔄 كل 12 ساعة",
    "uc_btn_mode_rec_24": "🔄 كل 24 ساعة",
    "uc_btn_mode_rec_48": "🔄 كل 48 ساعة",
    "uc_btn_mode_rec_custom": "⚙️ مدة مخصصة (بالساعات)",
    "uc_custom_hours_prompt": "⏱ أرسل عدد ساعات التكرار رقماً صحيحاً (الحد الأدنى <b>6</b> ساعات، والأقصى <b>720</b>):",
    "uc_err_mode_input": "❌ يرجى اختيار التوقيت من الأزرار أو كتابة 'now' أو عدد ساعات (6 فأكثر).",
    "uc_err_min_hours": "❌ الحد الأدنى للتكرار الدوري هو 6 ساعات (وحتى 720 ساعة).",

    # Step 6: Auto-Delete Timer Picker
    "uc_step6_autodel_prompt": (
        "🗑 <b>الخطوة 6/6 — الحذف الذاتي للرسالة (اختياري)</b>\n\n"
        "هل تريد حذف رسالة الحملة تلقائياً من المجموعات بعد مدة معينة؟"
    ),
    "uc_btn_autodel_none": "♾ بدون حذف تلقائي",
    "uc_btn_autodel_1h": "⏱ بعد ساعة (1h)",
    "uc_btn_autodel_6h": "⏱ بعد 6 ساعات (6h)",
    "uc_btn_autodel_24h": "⏱ بعد 24 ساعة (24h)",

    # Step 7: Live Preview & Single-Field Edit
    "uc_preview_header": "👁 <b>معاينة حية لحملتك كما ستصل للمجموعات:</b>",
    "uc_preview_summary": (
        "📋 <b>ملخص الحملة قبل الإطلاق</b>\n\n"
        "👥 <b>المجموعات المستهدفة:</b> {groups_count}\n"
        "🔘 <b>الأزرار المرفقة:</b> {buttons_count}\n"
        "⏰ <b>طريقة الإرسال:</b> {mode_label}\n"
        "🗑 <b>الحذف الذاتي:</b> {autodel_label}\n"
        "{replace_note}\n"
        "💡 <i>لن يتم خصم شيء من حصتك اليومية (5 حملات/يوم) إلا عند الضغط على «تأكيد وإطلاق».</i>"
    ),
    "uc_mode_label_immediate": "🚀 إرسال فوري",
    "uc_mode_label_recurring": "🔄 دوري كل {hours} ساعة",
    "uc_autodel_label_none": "♾ بدون حذف تلقائي",
    "uc_autodel_label_hours": "⏱ بعد {hours} ساعة",
    "uc_replace_warning_note": "\n⚠️ <b>تنبيه:</b> إطلاق هذه الحملة سيستبدل حملتك الحالية النشطة/المتوقفة.\n",
    "uc_btn_confirm_launch": "🚀 تأكيد وإطلاق الحملة",
    "uc_btn_edit_campaign": "✏️ تعديل الحملة",
    "uc_edit_menu_title": "✏️ <b>اختر الجزء الذي تريد تعديله:</b>\n\nبعد تعديل أي جزء ستعود مباشرة إلى شاشة المعاينة.",
    "uc_btn_edit_text": "📝 تعديل النص",
    "uc_btn_edit_photo": "📸 تعديل الصورة",
    "uc_btn_edit_buttons": "🔘 تعديل الأزرار",
    "uc_btn_edit_groups": "👥 تعديل المجموعات",
    "uc_btn_edit_mode": "⏰ تعديل التوقيت",
    "uc_btn_edit_autodel": "🗑 تعديل الحذف الذاتي",
    "uc_btn_back_preview": "👁 العودة للمعاينة",
    "uc_launch_success_immediate": (
        "✅ <b>تم إطلاق حملتك الفورية #{cid} بنجاح!</b>\n\n"
        "🚀 جاري الإرسال الآن إلى <b>{groups_count}</b> مجموعة."
    ),
    "uc_launch_success_recurring": (
        "✅ <b>تم تفعيل حملتك الدورية #{cid} بنجاح!</b>\n\n"
        "🔄 سيتم النشر تلقائياً كل <b>{hours}</b> ساعة في <b>{groups_count}</b> مجموعة."
    ),
    "uc_launch_failed": "❌ تعذر إنشاء الحملة: {error}",
}
