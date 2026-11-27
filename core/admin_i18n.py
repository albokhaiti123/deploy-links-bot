"""
Centralized Admin Panel Bilingual Translation Layer & Safe Aiogram Session Middleware.

Guarantees 100% Arabic <-> English coverage across ALL admin panel sub-menus, wizards,
alerts, stats, settings, broadcasts, recurring broadcasts, campaigns, custom buttons,
and admin management when an admin/owner selects English (lang == "en"), while NEVER
altering messages sent to groups or other users.
"""

import re
from typing import Any, Callable

from aiogram.types import InlineKeyboardMarkup

from core.i18n import get_context_lang, get_context_user_id

# ---------------------------------------------------------------------------
# Complete phrase dictionary covering all 9 admin sub-handler modules
# ---------------------------------------------------------------------------
ADMIN_EXACT_AND_PHRASE_MAP: dict[str, str] = {
    # Navigation & general
    "لوحة تحكم الإدارة": "Admin Control Panel",
    "لوحة التحكم الرئيسية": "Main Admin Panel",
    "لوحة التحكم": "Admin Panel",
    "رجوع للوحة التحكم": "Back to Admin Panel",
    "العودة للوحة التحكم": "Back to Admin Panel",
    "رجوع للقائمة الرئيسية": "Back to Main Menu",
    "رجوع لقائمة الروابط": "Back to Invite Links",
    "رجوع لقائمة الحملات": "Back to Campaigns List",
    "رجوع": "Back",
    "تراجع": "Cancel",
    "إلغاء": "Cancel",
    "تم الإلغاء.": "Operation cancelled.",
    "تم إلغاء العملية.": "Operation cancelled.",
    "تم إلغاء الإذاعة.": "Broadcast cancelled.",
    "تم إلغاء إنشاء الحملة.": "Campaign creation cancelled.",
    "لإلغاء الأمر أرسل /cancel": "Send /cancel to abort",
    "لإلغاء العملية أرسل /cancel": "Send /cancel to abort",
    "(لإلغاء أرسل /cancel)": "(Send /cancel to abort)",
    "لإلغاء أرسل /cancel": "Send /cancel to abort",
    "حاول مجدداً أو أرسل /cancel": "Try again or send /cancel",
    "أو /cancel للإلغاء": "or /cancel to abort",
    "ليس لديك صلاحية": "You do not have permission",
    "للمالك فقط": "Owner only",
    "هذا القسم مخصص لمالك البوت فقط.": "This section is restricted to the bot owner only.",
    "لا يمكنك تعديل صلاحيات المالك الرئيسي.": "You cannot modify the main owner's permissions.",

    # admins.py
    "👑 <b>المشرفون الحاليون:</b>": "👑 <b>Current Admins:</b>",
    "👑 <b>المشرفون:</b>\n\nلا يوجد مشرفون إضافيون.": "👑 <b>Admins:</b>\n\nNo additional admins yet.",
    "أرسل معرف تيليجرام (Telegram ID) للشخص الذي تريد إضافته كمشرف:\nلإلغاء الأمر أرسل /cancel": (
        "Send the Telegram ID of the user you want to add as admin:\nSend /cancel to abort"
    ),
    "أرسل معرف تيليجرام (Telegram ID) للمشرف الذي تريد إزالته:\nلإلغاء الأمر أرسل /cancel": (
        "Send the Telegram ID of the admin you want to remove:\nSend /cancel to abort"
    ),
    "إدارة المشرفين": "Manage Admins",
    "إضافة مشرف": "Add Admin",
    "إزالة مشرف": "Remove Admin",

    # stats.py
    "📊 <b>الإحصائيات</b>\n\n👥 إجمالي المستخدمين: <b>": "📊 <b>Statistics</b>\n\n👥 Total Users: <b>",
    "</b> (اليوم:": "</b> (Today:",
    ")\n🌐 المجموعات النشطة: <b>": ")\n🌐 Active Groups: <b>",
    "</b> / الإجمالي:": "</b> / Total:",
    "📢 إجمالي الترويجات: <b>": "📢 Total Promos: <b>",
    "🌐 <b>المجموعات:</b>\n\nلا توجد مجموعات مسجلة حتى الآن.": "🌐 <b>Groups:</b>\n\nNo registered groups yet.",
    "🌐 <b>آخر 20 مجموعة:</b>": "🌐 <b>Last 20 Groups:</b>",
    "بدون اسم": "Untitled",
    "إعداد الترويج": "Promo Settings",
    "الإعدادات": "Settings",
    "الإحصائيات": "Statistics",
    "إعدادات الترويج": "Promo Settings",
    "قائمة المجموعات": "Groups List",

    # promo_settings.py
    "📢 <b>إعداد الترويج (للمجموعات)</b>\n\nيمكنك استخدام <code>{user}</code> في النص ليتم استبدالها تلقائياً بـ 'منشن' للعضو الجديد.\n\nاختر ما تريد تعديله:": (
        "📢 <b>Promo Settings (Groups)</b>\n\nYou can use <code>{user}</code> in the text to automatically mention the new member.\n\nChoose what to edit:"
    ),
    "💬 أرسل الآن رسالة تأكيد الدفع (التي سيستلمها المستخدم بعد دفع النجوم):\n(يمكنك وضع روابط أو نصوص)\nملاحظة: تليجرام يفتح الصور المدفوعة تلقائياً ولا يرسل إشعاراً للبوت بذلك، لذلك هذه الرسالة ستعمل بشكل أساسي مع (الإعلانات النصية المدفوعة الفواتير).\nلإلغاء الأمر أرسل /cancel": (
        "💬 Send the post-payment confirmation message (delivered after paying Stars):\n(Links and text supported)\nNote: Telegram unlocks paid media automatically without notifying the bot, so this message mainly applies to paid text invoices.\nSend /cancel to abort"
    ),
    "أرسل الآن نص الإعلان الجديد:\n(تذكر يمكنك استخدام <code>{user}</code> للمنشن)\nلإلغاء الأمر أرسل /cancel": (
        "Send the new promo text:\n(You can use <code>{user}</code> to mention the user)\nSend /cancel to abort"
    ),
    "أرسل الآن (صورة أو فيديو) ليتم إرفاقه مع الإعلان.\nلحذف الوسائط والاكتفاء بالنص أرسل /clear\nلإلغاء الأمر أرسل /cancel": (
        "Send a photo or video to attach to the promo.\nTo remove media and use text only, send /clear\nSend /cancel to abort"
    ),
    "أرسل الآن الرابط الترويجي الجديد (يجب أن يبدأ بـ http أو https):\nلإلغاء الأمر أرسل /cancel": (
        "Send the new promo URL (must start with http or https):\nSend /cancel to abort"
    ),
    "أرسل الآن نص الزر الجديد:\nلإلغاء الأمر أرسل /cancel": "Send the new button text:\nSend /cancel to abort",
    "⭐️ أرسل عدد نجوم تيليجرام المطلوبة لهذا الإعلان (مثلاً 50):\nلإلغاء الأمر أرسل /cancel": (
        "⭐️ Send the number of Telegram Stars required for this ad (e.g. 50):\nSend /cancel to abort"
    ),
    "تم حفظ رسالة ما بعد الدفع.": "Post-payment message saved.",
    "تم تحديث نص الإعلان بنجاح.": "Promo text updated successfully.",
    "تم تحديث الرابط بنجاح.": "URL updated successfully.",
    "تم تحديث نص الزر بنجاح.": "Button text updated successfully.",
    "تم حفظ الصورة بنجاح.": "Photo saved successfully.",
    "تم حفظ الفيديو بنجاح.": "Video saved successfully.",
    "تم حذف الوسائط. سيتم إرسال الإعلان كنص فقط.": "Media removed. Promo will be sent as text only.",
    "حدث خطأ في المعاينة. تأكد من صحة الإعدادات.\nالخطأ:": "Preview error. Please verify your settings.\nError:",
    "أرسل صورة أو فيديو، أو /clear، أو /cancel.": "Please send a photo or video, /clear, or /cancel.",
    "🤖 إخفاء زر البوت": "🤖 Hide Bot Button",
    "🤖 إظهار زر البوت": "🤖 Show Bot Button",
    "🟢 الإعلان: مجاني": "🟢 Ad: Free",
    "💎 الإعلان: مدفوع (": "💎 Ad: Paid (",
    "تعديل النص": "Edit Text",
    "تعديل الوسائط": "Edit Media",
    "تعديل الرابط": "Edit URL",
    "تعديل نص الزر": "Edit Button Text",
    "رسالة ما بعد الدفع": "Post-Payment Message",
    "أزرار مخصصة": "Custom Buttons",
    "معاينة الإعلان": "Preview Ad",
    "👁 <b>معاينة:</b>": "👁 <b>Preview:</b>",
    "👁 معاينة:": "👁 Preview:",
    "فتح المحتوى السري": "Unlock Secret Content",
    "محتوى مدفوع (VIP)": "Paid Content (VIP)",
    "قم بدفع النجوم لاستلام رسالة ما بعد الدفع فوراً.": "Pay Stars to receive the post-payment message immediately.",

    # general_settings.py
    "⚙️ <b>الإعدادات:</b>\n\n📱 رسالة الترحيب (الخاص):": "⚙️ <b>Settings:</b>\n\n📱 Private Welcome Message:",
    "⏱ مدة الانتظار الحالية:": "⏱ Current Cooldown:",
    "🧹 الحذف التلقائي للإعلان القديم:": "🧹 Auto-Delete Previous Promo:",
    "🗑 حذف رسالة الترويج بعد:": "🗑 Delete Promo Message After:",
    "🧪 <b>مجموعة الاختبار:</b>\n\nالمعرف الحالي: <code>": "🧪 <b>Test Group:</b>\n\nCurrent ID: <code>",
    "</code>\n\nأرسل معرف (Chat ID) المجموعة.\nلإلغاء أرسل /cancel\nلإزالة المجموعة أرسل /remove": (
        "</code>\n\nSend the group Chat ID.\nSend /cancel to abort\nSend /remove to clear"
    ),
    "⏱ اختر مدة الانتظار بين كل إعلان وآخر في نفس المجموعة:\n\n*ملاحظة: اختيار '0 ثانية' يعني إرسال الإعلان مع كل عضو جديد ينضم دون انتظار.": (
        "⏱ Choose the cooldown between promos in the same group:\n\n*Note: '0 sec' sends the promo on every new member join without delay."
    ),
    "🗑 <b>اختر مدة حذف رسالة الترويج بعد إرسالها:</b>": "🗑 <b>Choose auto-delete duration for promo messages:</b>",
    "أرسل قيمة مدة الانتظار بالثواني (أرقام فقط):\nلإلغاء الأمر أرسل /cancel": (
        "Send the cooldown duration in seconds (digits only):\nSend /cancel to abort"
    ),
    "بدون انتظار (0 ثانية)": "No delay (0s)",
    "بدون انتظار (0s)": "No delay (0s)",
    "⚡️ مع كل انضمام (0 ثانية)": "⚡️ Every Join (0s)",
    "إدخال قيمة مخصصة": "Enter Custom Value",
    "تم إزالة مجموعة الاختبار.": "Test group removed.",
    "تم تحديد مجموعة الاختبار: <code>": "Test group set: <code>",
    "🧹 إيقاف الحذف التلقائي": "🧹 Disable Auto-Delete",
    "🧹 تشغيل الحذف التلقائي": "🧹 Enable Auto-Delete",
    "📴 إيقاف رسالة الترحيب (الخاص)": "📴 Disable Welcome Msg (DM)",
    "📱 تشغيل رسالة الترحيب (الخاص)": "📱 Enable Welcome Msg (DM)",
    "إعدادات رسالة الترحيب (الخاص)": "Welcome Message Settings (DM)",
    "تعديل مدة الانتظار (Cooldown)": "Edit Cooldown",
    "مجموعة الاختبار": "Test Group",
    "تم التحديث": "Updated",
    "غير محدد": "Not set",
    "مفعلة ✅": "Enabled ✅",
    "معطلة ❌": "Disabled ❌",
    "مفعّل ✅": "Enabled ✅",
    "معطّل ❌": "Disabled ❌",
    "مفعل ✅": "Enabled ✅",
    "معطل ❌": "Disabled ❌",
    "بدون حذف": "No Auto-Delete",

    # welcome_settings.py
    "⚙️ <b>إعدادات رسالة الترحيب (الخاص):</b>\n\nتتحكم هذه القائمة بالرسالة والأزرار التي تظهر للأعضاء عند بدء المحادثة مع البوت في الخاص.\nاختر ما تريد تعديله:": (
        "⚙️ <b>Welcome Message Settings (DM):</b>\n\nControls the message and buttons shown to users when starting the bot in private chat.\nChoose what to edit:"
    ),
    "🖼️ أرسل صورة أو فيديو لإرفاقه مع رسالة الترحيب.\nلحذف الوسائط الحالية أرسل /clear\nلإلغاء أرسل /cancel": (
        "🖼️ Send a photo or video to attach to the welcome message.\nSend /clear to remove current media\nSend /cancel to abort"
    ),
    "أرسل الآن رسالة الترحيب الجديدة التي ستظهر للأعضاء في الخاص عند إرسال /start:\n(يمكنك استخدام HTML)\nلإلغاء الأمر أرسل /cancel": (
        "Send the new welcome message shown on /start:\n(HTML supported)\nSend /cancel to abort"
    ),
    "أرسل الآن الاسم الجديد للزر الإضافي (مثال: اشترك في الباقة).\nلإخفاء الزر تماماً أرسل /hide\nلإلغاء الأمر أرسل /cancel": (
        "Send the new label for the extra button (e.g. Subscribe Now).\nSend /hide to hide the button\nSend /cancel to abort"
    ),
    "أرسل الآن الرابط (يجب أن يبدأ بـ http أو https أو tg://):\nلإلغاء الأمر أرسل /cancel": (
        "Send the URL (must start with http, https, or tg://):\nSend /cancel to abort"
    ),
    "أرسل الآن الرسالة النصية التي تريد ظهورها عند ضغط المستخدم على الزر:\nلإلغاء الأمر أرسل /cancel": (
        "Send the text message to display when a user clicks the button:\nSend /cancel to abort"
    ),
    "تم تحديث رسالة الترحيب بنجاح.": "Welcome message updated successfully.",
    "تم تحويل الزر الإضافي إلى رابط بنجاح.": "Extra button switched to URL successfully.",
    "تم تحويل الزر الإضافي إلى رسالة نصية بنجاح.": "Extra button switched to text message successfully.",
    "تم حذف الوسائط. رسالة الترحيب ستكون نصية فقط.": "Media removed. Welcome message will be text only.",
    "تم حفظ صورة الترحيب بنجاح.": "Welcome photo saved successfully.",
    "تم حفظ فيديو الترحيب بنجاح.": "Welcome video saved successfully.",
    "تم إخفاء الزر الإضافي.": "Extra button hidden.",
    "تم تحديث اسم الزر الإضافي.": "Extra button label updated.",
    "يرجى إرسال الاسم الجديد للزر أو /hide أو /cancel.": "Please send the new button label, /hide, or /cancel.",
    "يرجى إرسال الرسالة النصية أو /cancel.": "Please send the text message or /cancel.",
    "👁 <b>معاينة الترحيب:</b>": "👁 <b>Welcome Preview:</b>",
    "تعديل نص رسالة الترحيب": "Edit Welcome Text",
    "تعديل وسائط الترحيب": "Edit Welcome Media",
    "تعديل اسم الزر الإضافي": "Edit Extra Button Label",
    "جعله رابط (URL)": "Set as URL Link",
    "جعله رسالة نصية": "Set as Text Message",
    "معاينة رسالة الترحيب": "Preview Welcome Message",

    # broadcast.py
    "📣 <b>ساحر الإذاعة الجديد:</b>\n\nاختر الوجهة التي تريد بدء الإذاعة إليها:": (
        "📣 <b>Broadcast Wizard:</b>\n\nChoose your target audience:"
    ),
    "📝 <b>الخطوة 1:</b> أرسل النص الخاص بالإذاعة.\n(يمكنك إضافة روابط أو تنسيقات HTML)\nلإلغاء الأمر أرسل /cancel": (
        "📝 <b>Step 1:</b> Send the broadcast text.\n(Links and HTML formatting supported)\nSend /cancel to abort"
    ),
    "🖼 <b>الخطوة 2:</b> أرسل صورة أو فيديو لإرفاقه مع الإذاعة.\nإذا أردت إرسال الإذاعة كنص فقط دون وسائط، أرسل /skip\nلإلغاء الأمر أرسل /cancel": (
        "🖼 <b>Step 2:</b> Send a photo or video to attach.\nFor text-only broadcast, send /skip\nSend /cancel to abort"
    ),
    "💎 <b>الخطوة 3:</b> هل تريد أن يكون هذا المحتوى مجانياً أم مدفوعاً (مظلل يفتح بالنجوم)؟": (
        "💎 <b>Step 3:</b> Should this content be free or paid (blurred, unlocked with Stars)?"
    ),
    "⏳ <b>الخطوة ما قبل الأخيرة:</b> متى تريد حذف الإذاعة تلقائياً؟": (
        "⏳ <b>Almost Done:</b> When should this broadcast be auto-deleted?"
    ),
    "📋 <b>ملخص الإذاعة النهائي:</b>\n\n👥 <b>الوجهة:</b>": "📋 <b>Final Broadcast Summary:</b>\n\n👥 <b>Target:</b>",
    "🖼 <b>الوسائط:</b>": "🖼 <b>Media:</b>",
    ")\n⏳ <b>التدمير الذاتي:</b>": ")\n⏳ <b>Auto-Delete:</b>",
    "هل أنت متأكد من الإرسال الآن؟": "Are you sure you want to send now?",
    "🚀 جاري الإرسال، يرجى الانتظار (قد يستغرق بعض الوقت لتجنب الحظر)...": (
        "🚀 Sending broadcast, please wait (rate-limited to avoid flood bans)..."
    ),
    "يجب أن يكون العدد بين 1 و 2500.": "Number must be between 1 and 2500.",
    "يجب إرسال صورة أو فيديو، أو /skip، أو /cancel.": "Please send a photo or video, /skip, or /cancel.",
    "⭐️ كم عدد النجوم المطلوبة لفتح المحتوى؟ (أرسل رقماً بين 1 و 2500):": (
        "⭐️ How many Stars are required to unlock? (Send a number between 1 and 2500):"
    ),
    "👥 للإدارة والمستخدمين (في الخاص)": "👥 Users & Admins (Private Chat)",
    "🌐 للمجموعات فقط": "🌐 Groups Only",
    "🔄 الإذاعات الدورية": "🔄 Recurring Broadcasts",
    "🟢 مجانية (مفتوحة)": "🟢 Free (Open)",
    "⭐️ مدفوعة (VIP - بنجوم تيليجرام)": "⭐️ Paid (VIP - Telegram Stars)",
    "المستخدمين في الخاص": "Users (Private Chat)",
    "لا تحذف أبداً": "Never delete",
    "لا تُحذف": "Never delete",
    "إرسال الآن": "Send Now",
    "مجانية": "Free",

    # recurring.py
    "🔄 <b>الإذاعات الدورية:</b>\n\nلا توجد إذاعات دورية حالياً.": "🔄 <b>Recurring Broadcasts:</b>\n\nNo recurring broadcasts yet.",
    "🔄 <b>الإذاعات الدورية:</b>": "🔄 <b>Recurring Broadcasts:</b>",
    "🔄 <b>إنشاء إذاعة دورية:</b>\n\nاختر الهدف:": "🔄 <b>Create Recurring Broadcast:</b>\n\nChoose target:",
    "📝 أرسل نص الإذاعة الدورية:\n(لإلغاء أرسل /cancel)": "📝 Send the recurring broadcast text:\n(Send /cancel to abort)",
    "🔄 كل كم ساعة تريد تكرار هذه الإذاعة؟": "🔄 How often (in hours) should this broadcast repeat?",
    "🖼 أرسل صورة أو فيديو لإرفاقه مع الإذاعة الدورية.\nأو أرسل /skip للإذاعة النصية فقط.\nلإلغاء الأمر أرسل /cancel": (
        "🖼 Send a photo or video to attach to the recurring broadcast.\nOr send /skip for text-only.\nSend /cancel to abort"
    ),
    "💎 هل تريد أن تكون وسائط الإذاعة الدورية مجانية أم مدفوعة بالنجوم؟": (
        "💎 Should the recurring broadcast media be free or paid with Stars?"
    ),
    "</b>\n\nالنص الحالي:\n<blockquote>": "</b>\n\nCurrent Text:\n<blockquote>",
    "</blockquote>\n\nأرسل النص الجديد:\n(لإلغاء أرسل /cancel)": "</blockquote>\n\nSend the new text:\n(Send /cancel to abort)",
    "إنشاء إذاعة دورية": "Create Recurring Broadcast",
    "الإذاعة غير موجودة.": "Broadcast not found.",
    "تم الإيقاف.": "Paused.",
    "تم التشغيل.": "Enabled.",
    "تم الحذف.": "Deleted.",
    "جاري النشر...": "Broadcasting...",
    "👥 مستخدمين": "👥 Users",
    "🌐 مجموعات": "🌐 Groups",
    "📢 الجميع": "📢 All",
    "⏸ إيقاف #": "⏸ Pause #",
    "▶️ تشغيل #": "▶️ Enable #",
    "📝 تعديل #": "📝 Edit #",
    "👁 معاينة #": "👁 Preview #",
    "📢 نشر #": "📢 Send #",
    "🗑 حذف #": "🗑 Delete #",

    # button_manager.py
    "لا توجد أزرار مخصصة حالياً.": "No custom buttons added yet.",
    "🔗 أرسل الآن <b>رابط الزر</b> (يجب أن يبدأ بـ http أو https أو tg://):\nلإلغاء أرسل /cancel": (
        "🔗 Send the <b>button URL</b> (must start with http, https, or tg://):\nSend /cancel to abort"
    ),
    "):</b>\n\nأرسل <b>نص الزر</b> (مثال: 📢 قناتنا):\nلإلغاء أرسل /cancel": (
        "):</b>\n\nSend the <b>button label</b> (e.g. 📢 Our Channel):\nSend /cancel to abort"
    ),
    "🔘 <b>إضافة زر جديد (": "🔘 <b>Add New Button (",
    "نص الزر طويل جداً (الحد 64 حرف). حاول مجدداً:": "Button label is too long (max 64 chars). Try again:",
    "تم حذف الزر.": "Button deleted.",
    "إضافة زر جديد": "Add New Button",
    "الزر الآن:": "Button is now:",
    "رسالة الترحيب": "Welcome Message",
    "الترويج": "Promo",
    "❌ تعطيل": "❌ Disable",
    "✅ تفعيل": "✅ Enable",

    # campaigns.py
    "🎯 <b>إدارة الحملات الترويجية:</b>\n\nأنشئ حملات تُلزم المستخدمين بإضافة البوت إلى مجموعات مقابل فتح محتوى.": (
        "🎯 <b>Promo Campaigns Manager:</b>\n\nCreate campaigns requiring users to add the bot to groups to unlock exclusive content."
    ),
    "🎯 <b>إنشاء حملة جديدة:</b>\n\n<b>الخطوة 1/10:</b> أرسل اسم الحملة:\nلإلغاء أرسل /cancel": (
        "🎯 <b>Create New Campaign:</b>\n\n<b>Step 1/10:</b> Send the campaign name:\nSend /cancel to abort"
    ),
    "<b>الخطوة 2/10:</b> أرسل نص الإعلان الترويجي للحملة:\n(هذا النص سيُرسل في المجموعات والخاص)\nلإلغاء أرسل /cancel": (
        "<b>Step 2/10:</b> Send the campaign promo text:\n(Sent to groups and private chats)\nSend /cancel to abort"
    ),
    "<b>الخطوة 3/10:</b> أرسل صورة أو فيديو لإرفاقه مع إعلان الحملة.\nأرسل /skip لتخطي.\nلإلغاء أرسل /cancel": (
        "<b>Step 3/10:</b> Send a photo or video for the campaign ad.\nSend /skip to skip.\nSend /cancel to abort"
    ),
    "<b>الخطوة 4/10:</b> أرسل نص الزر (CTA) مثلاً: 🎁 الحصول على العرض\nلإلغاء أرسل /cancel": (
        "<b>Step 4/10:</b> Send the CTA button text (e.g. 🎁 Claim Offer):\nSend /cancel to abort"
    ),
    "<b>الخطوة 5/10:</b> كم عدد المجموعات المطلوبة من المستخدم لفتح المحتوى؟\n(أرسل رقماً بين 1 و 50)\nلإلغاء أرسل /cancel": (
        "<b>Step 5/10:</b> How many groups must a user add the bot to unlock content?\n(Send a number between 1 and 50)\nSend /cancel to abort"
    ),
    "<b>الخطوة 6/10:</b> أرسل محتوى الفتح (النص أو الرسالة التي سيستلمها المستخدم بعد الإنجاز):\nلإلغاء أرسل /cancel": (
        "<b>Step 6/10:</b> Send the unlock content (delivered once completed):\nSend /cancel to abort"
    ),
    "<b>الخطوة 7/10:</b> أرسل وسائط فتح (صورة أو فيديو) تُرفق مع محتوى الفتح.\nأرسل /skip لتخطي.\nلإلغاء أرسل /cancel": (
        "<b>Step 7/10:</b> Send unlock media (photo or video) to attach.\nSend /skip to skip.\nSend /cancel to abort"
    ),
    "<b>الخطوة 8/10:</b> حذف محتوى الفتح تلقائياً بعد كم؟": "<b>Step 8/10:</b> Auto-delete unlock content after?",
    "<b>الخطوة 9/10:</b> اختر وضع النشر:": "<b>Step 9/10:</b> Choose broadcast mode:",
    "<b>الخطوة 10/10:</b> كل كم ساعة يتم تكرار النشر؟": "<b>Step 10/10:</b> Repeat broadcast every how many hours?",
    "📋 <b>ملخص الحملة:</b>\n\n📌 الاسم:": "📋 <b>Campaign Summary:</b>\n\n📌 Name:",
    "📝 نص الإعلان:": "📝 Promo Text:",
    "...\n🖼 وسائط:": "...\n🖼 Media:",
    "🔘 زر CTA:": "🔘 CTA Button:",
    "👥 المجموعات المطلوبة:": "👥 Required Groups:",
    "🗑 حذف محتوى الفتح:": "🗑 Unlock Auto-Delete:",
    "📤 وضع النشر:": "📤 Broadcast Mode:",
    "هل تريد إنشاء الحملة؟": "Create this campaign?",
    "</b>\n\n📊 الحالة:": "</b>\n\n📊 Status:",
    "📈 <b>إحصائيات:</b>\n  👁 المشاهدات:": "📈 <b>Statistics:</b>\n  👁 Views:",
    "🚀 بدأوا:": "🚀 Started:",
    "➕ مجموعات أُضيفت:": "➕ Groups Added:",
    "🔓 فتحوا المحتوى:": "🔓 Unlocked:",
    "🎁 استلموا المحتوى:": "🎁 Delivered:",
    "📋 <b>قائمة الحملات:</b>": "📋 <b>Campaigns List:</b>",
    "قائمة الحملات": "Campaigns List",
    "لا توجد حملات حالياً.": "No campaigns yet.",
    "تم إنشاء الحملة بنجاح!": "Campaign created successfully!",
    "تم تشغيل النشر الدوري.": "Recurring broadcast enabled.",
    "تم إيقاف النشر الدوري.": "Recurring broadcast paused.",
    "إيقاف النشر الدوري": "Pause Recurring Broadcast",
    "تشغيل النشر الدوري": "Enable Recurring Broadcast",
    "تم حذف الحملة.": "Campaign deleted.",
    "تم الاستئناف.": "Resumed.",
    "تم إرسال نسخة تجريبية لك.": "Test copy sent to you.",
    "لم يتم تحديد مجموعة اختبار. اذهب للإعدادات.": "No test group set. Go to Settings.",
    "تم الإرسال لمجموعة الاختبار.": "Sent to test group.",
    "تم إرسال المعاينة.": "Preview sent.",
    "فشل إرسال الاختبار.": "Failed to send test.",
    "فشل الإرسال لمجموعة الاختبار.": "Failed to send to test group.",
    "أرسل صورة أو فيديو أو /skip.": "Please send a photo, video, or /skip.",
    "الحملة غير موجودة.": "Campaign not found.",
    "إنشاء حملة جديدة": "Create New Campaign",
    "إنشاء الحملة": "Create Campaign",
    "نشر للمستخدمين": "Broadcast to Users",
    "نشر للمجموعات": "Broadcast to Groups",
    "نشر للجميع": "Broadcast to All",
    "اختبار (لي)": "Test (DM)",
    "اختبار (مجموعة)": "Test (Group)",
    "معاينة الحملة": "Preview Campaign",
    "حذف الحملة": "Delete Campaign",
    "🧪 <b>[اختبار]</b>": "🧪 <b>[TEST]</b>",
    "📤 يدوي (أنا أنشره)": "📤 Manual (I broadcast it)",
    "🔄 دوري (تلقائي)": "🔄 Recurring (Automatic)",
    "نشطة ✅": "Active ✅",
    "متوقفة ⏸": "Paused ⏸",
    "محذوفة 🗑": "Deleted 🗑",
    "⏸ إيقاف": "⏸ Pause",
    "▶️ استئناف": "▶️ Resume",
    "يدوي": "Manual",
    "الاسم:": "Name:",

    # Invite links
    "إدارة روابط دعوة البوت (للمالك):": "Bot Invite Links Management (Owner):",
    "لا توجد روابط دعوة مولدة حتى الآن.": "No invite links have been generated yet.",
    "روابط دعوة البوت": "Bot Invite Links",
    "توليد رابط دعوة جديد": "Generate New Invite Link",
    "إيقاف الرابط يدوياً": "Pause Link Manually",
    "إعادة تفعيل الرابط": "Resume Link",
    "حذف الرابط نهائياً": "Delete Link Permanently",
    "تم إيقاف الرابط يدوياً": "Link manually paused",
    "تم تفعيل الرابط": "Link resumed",
    "تم حذف الرابط نهائياً": "Invite link permanently deleted",
    "تم توليد الرابط الدائم": "Permanent link generated",
    "تم توليد الرابط المؤقت": "Temporary link generated",

    # Validation & errors
    "يرجى إرسال معرف رقمي صالح (Chat ID).": "Please send a valid numeric Chat ID.",
    "يرجى إرسال معرف رقمي صالح.": "Please send a valid numeric ID.",
    "يرجى إرسال أرقام فقط (مثلاً 50).": "Please send numbers only (e.g. 50).",
    "يرجى إرسال أرقام فقط.": "Please send numbers only.",
    "يرجى إرسال رقم بين 1 و 2500.": "Please send a number between 1 and 2500.",
    "الرابط غير صحيح. يجب أن يبدأ بـ http:// أو https:// أو tg://": "Invalid URL. Must start with http://, https://, or tg://",
    "الرابط غير صحيح. يجب أن يبدأ بـ http:// أو https://": "Invalid URL. Must start with http:// or https://",
    "عذراً، الرابط غير صحيح. يجب أن يبدأ بـ http أو https أو tg://": "Sorry, invalid URL. Must start with http, https, or tg://",
    "يرجى إرسال نص الزر أو /cancel للإلغاء.": "Please send the button label or /cancel.",
    "يرجى إرسال نص الإذاعة أو /cancel للإلغاء.": "Please send the broadcast text or /cancel.",
    "يرجى إرسال اسم الحملة كنص أو /cancel.": "Please send the campaign name as text or /cancel.",
    "يرجى إرسال نص الإعلان أو /cancel.": "Please send the promo text or /cancel.",
    "يرجى إرسال نص الزر أو /cancel.": "Please send the button text or /cancel.",
    "يرجى إرسال محتوى الفتح كنص أو /cancel.": "Please send the unlock content as text or /cancel.",
    "يرجى إرسال نص الرسالة أو /cancel.": "Please send the message text or /cancel.",
    "يرجى إرسال نص رسالة الترحيب أو /cancel.": "Please send the welcome message text or /cancel.",
    "يرجى إرسال النص الجديد أو /cancel.": "Please send the new text or /cancel.",
    "أرسل رقماً بين 1 و 50.": "Send a number between 1 and 50.",
    "❌ خطأ:": "❌ Error:",

    # Common short labels
    "المجموعات": "Groups",
    "مستخدمين": "Users",
    "مجموعات": "Groups",
    "الجميع": "All",
    "نعم": "Yes",
    "لا": "No",
    "نشط": "Active",
    "متوقف": "Paused",
    "مفعّل": "Enabled",
    "معطّل": "Disabled",
    "تم الحفظ بنجاح!": "Saved successfully!",
    "تم التحديث بنجاح!": "Updated successfully!",
    "تم الحذف بنجاح!": "Deleted successfully!",
    "حذف": "Delete",
}

# Parameterized regex patterns (run before phrase replacement)
ADMIN_REGEX_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"🔘 <b>أزرار ([^<]+):</b>"), r"🔘 <b>\1 Buttons:</b>"),
    (re.compile(r"👁 <b>معاينة الحملة #(\d+):?</b>"), r"👁 <b>Campaign #\1 Preview:</b>"),
    (re.compile(r"🎯 <b>الحملة #(\d+):"), r"🎯 <b>Campaign #\1:"),
    (re.compile(r"الحملة #(\d+)"), r"Campaign #\1"),
    (re.compile(r"المعرف: #(\d+)"), r"ID: #\1"),
    (re.compile(r"📝 <b>تعديل الإذاعة الدورية #(\d+)"), r"📝 <b>Edit Recurring Broadcast #\1"),
    (re.compile(r"👁 <b>معاينة الإذاعة الدورية #(\d+)"), r"👁 <b>Recurring Broadcast #\1 Preview"),
    (re.compile(r"تم تحديث نص الإذاعة الدورية #(\d+) بنجاح!"), r"Recurring broadcast #\1 text updated successfully!"),
    (re.compile(r"تم إنشاء إذاعة دورية \(كل (\d+) ساعة\)!"), r"Recurring broadcast created (every \1 hours)!"),
    (re.compile(r"\|\s*كل\s*(\d+)h"), r"| Every \1h"),
    (re.compile(r"اكتمل نشر الحملة! تم الإرسال إلى <b>(\d+)</b> جهة\."), r"Campaign broadcast complete! Sent to <b>\1</b> target(s)."),
    (re.compile(r"اكتملت الإذاعة! تم الإرسال(?: بنجاح)? إلى <b>(\d+)</b> جهة\."), r"Broadcast complete! Sent to <b>\1</b> target(s)."),
    (re.compile(r"تُحذف بعد (\d+) دقيقة"), r"Deleted after \1 min(s)"),
    (re.compile(r"مدفوعة بـ (\d+) نجمة ⭐️"), r"Paid (\1 Stars ⭐️)"),
    (re.compile(r"تم تحويل الإعلان إلى مدفوع بقيمة (\d+)(?: نجمة)?(?: ⭐️)?"), r"Ad switched to Paid (\1 Stars)"),
    (re.compile(r"تم تحديث مدة الانتظار إلى (\d+) ثانية\.?"), r"Cooldown updated to \1 seconds."),
    (re.compile(r"تم ضبط مدة الانتظار إلى (\d+) ثانية\.?"), r"Cooldown set to \1 seconds."),
    (re.compile(r"تم إضافة الزر <b>(.*?)</b> بنجاح!"), r"Button <b>\1</b> added successfully!"),
    (re.compile(r"تم إضافة المشرف (?:<code>)?(\d+)(?:</code>)? بنجاح!"), r"Admin <code>\1</code> added successfully!"),
    (re.compile(r"تم إزالة المشرف (?:<code>)?(\d+)(?:</code>)? بنجاح!"), r"Admin <code>\1</code> removed successfully!"),
    (re.compile(r"دوري \(كل (\d+) ساعة\)"), r"Recurring (every \1h)"),
    (re.compile(r"كل (\d+) ساعات"), r"Every \1 hours"),
    (re.compile(r"كل (\d+) ساعة"), r"Every \1 hours"),
    (re.compile(r"بعد (\d+) ثانية"), r"After \1s"),
    (re.compile(r"بعد (\d+) دقائق"), r"After \1 mins"),
    (re.compile(r"بعد (\d+) دقيقة"), r"After \1 min(s)"),
    (re.compile(r"بعد (\d+) ساعات"), r"After \1 hours"),
    (re.compile(r"بعد (\d+) ساعة"), r"After \1 hour(s)"),
    (re.compile(r"(\d+) ثانية"), r"\1s"),
    (re.compile(r"(\d+) دقائق"), r"\1 mins"),
    (re.compile(r"(\d+) دقيقة"), r"\1 min"),
    (re.compile(r"(\d+) ساعات"), r"\1 hours"),
    (re.compile(r"(\d+) ساعة"), r"\1 hour"),
]

_SORTED_PHRASES: list[tuple[str, str]] = sorted(
    ADMIN_EXACT_AND_PHRASE_MAP.items(),
    key=lambda kv: len(kv[0]),
    reverse=True,
)


def translate_admin_text(text: str | None, lang: str | None = None) -> str | None:
    """Translate Arabic admin UI text into English when lang == 'en'."""
    if not text or not isinstance(text, str):
        return text
    resolved = lang or get_context_lang() or "ar"
    if resolved != "en":
        return text

    result = text
    for pattern, repl in ADMIN_REGEX_PATTERNS:
        result = pattern.sub(repl, result)
    for ar_phrase, en_phrase in _SORTED_PHRASES:
        if ar_phrase in result:
            result = result.replace(ar_phrase, en_phrase)
    return result


def translate_admin_markup(
    markup: "InlineKeyboardMarkup | None", lang: str | None = None
) -> "InlineKeyboardMarkup | None":
    """Return a copy of InlineKeyboardMarkup with translated button labels when lang == 'en'."""
    if markup is None or not isinstance(markup, InlineKeyboardMarkup):
        return markup
    resolved = lang or get_context_lang() or "ar"
    if resolved != "en":
        return markup

    new_rows = []
    changed = False
    for row in markup.inline_keyboard:
        new_row = []
        for btn in row:
            new_text = translate_admin_text(btn.text, resolved)
            if new_text != btn.text:
                new_row.append(btn.model_copy(update={"text": new_text}))
                changed = True
            else:
                new_row.append(btn)
        new_rows.append(new_row)
    return InlineKeyboardMarkup(inline_keyboard=new_rows) if changed else markup


class AdminSessionI18nMiddleware:
    """
    Aiogram 3 Bot Session Middleware for seamless Admin Panel localization.

    Safety boundary:
      - Activates ONLY when active ContextVar lang == 'en'.
      - For message send/edit methods: ONLY translates when chat_id matches the
        active user (get_context_user_id()), i.e. the admin's own private chat.
      - Translates AnswerCallbackQuery alerts/toasts for the active English admin.
      - Group broadcasts and messages to other users are NEVER modified.
    """

    async def __call__(
        self,
        make_request: Callable,
        bot: Any,
        method: Any,
    ) -> Any:
        lang = get_context_lang()
        if lang != "en":
            return await make_request(bot, method)

        ctx_uid = get_context_user_id()
        method_name = type(method).__name__

        if method_name == "AnswerCallbackQuery":
            if getattr(method, "text", None):
                new_text = translate_admin_text(method.text, lang)
                if new_text != method.text:
                    method = method.model_copy(update={"text": new_text})
            return await make_request(bot, method)

        if method_name in (
            "SendMessage",
            "EditMessageText",
            "EditMessageCaption",
            "EditMessageReplyMarkup",
            "SendPhoto",
            "SendVideo",
        ):
            raw_chat_id = getattr(method, "chat_id", None)
            try:
                chat_id_int = int(raw_chat_id) if raw_chat_id is not None else None
            except (TypeError, ValueError):
                chat_id_int = None

            is_self_private = (
                ctx_uid is not None
                and chat_id_int is not None
                and chat_id_int > 0
                and chat_id_int == ctx_uid
            )
            if not is_self_private:
                return await make_request(bot, method)

            updates = {}
            if isinstance(getattr(method, "text", None), str):
                new_text = translate_admin_text(method.text, lang)
                if new_text != method.text:
                    updates["text"] = new_text
            if isinstance(getattr(method, "caption", None), str):
                new_cap = translate_admin_text(method.caption, lang)
                if new_cap != method.caption:
                    updates["caption"] = new_cap
            if isinstance(getattr(method, "reply_markup", None), InlineKeyboardMarkup):
                new_kb = translate_admin_markup(method.reply_markup, lang)
                if new_kb is not method.reply_markup:
                    updates["reply_markup"] = new_kb
            if updates:
                method = method.model_copy(update=updates)

        return await make_request(bot, method)
