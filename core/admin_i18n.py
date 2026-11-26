"""
Centralized Admin Panel Bilingual Translation Layer (Phase 6).

Translates Arabic admin UI text → English when the active user lang == 'en'.
Safety boundary: ONLY translates private messages addressed to the active user/admin.
Group broadcasts and messages to other users are NEVER modified.
"""

import re
from typing import Any, Awaitable, Callable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.i18n import get_context_lang, get_context_user_id

# ---------------------------------------------------------------------------
# Phrase translation map (longest first at sort time to prevent partial match)
# ---------------------------------------------------------------------------
_PHRASE_MAP: dict[str, str] = {
    # Navigation & general
    "لوحة تحكم الإدارة": "Admin Control Panel",
    "لوحة التحكم الرئيسية": "Main Admin Panel",
    "لوحة التحكم": "Admin Panel",
    "رجوع للوحة التحكم": "Back to Admin Panel",
    "العودة للوحة التحكم": "Back to Admin Panel",
    "رجوع لقائمة الروابط": "Back to Invite Links",
    "رجوع لقائمة الحملات": "Back to Campaigns List",
    "رجوع للقائمة الرئيسية": "Back to Main Menu",
    "رجوع": "Back",
    "تراجع": "Cancel",
    "إلغاء": "Cancel",
    "تم الإلغاء.": "Operation cancelled.",
    "للمالك فقط": "Owner only",
    "ليس لديك صلاحية": "You do not have permission",
    "هذا القسم مخصص لمالك البوت فقط.": "This section is restricted to the bot owner only.",
    "لا يمكنك تعديل صلاحيات المالك الرئيسي.": "You cannot modify the main owner's permissions.",

    # Sections
    "إعدادات الترويج": "Promo Settings",
    "إعدادات الترحيب": "Welcome Settings",
    "الإعدادات العامة": "General Settings",
    "إذاعة فورية": "Instant Broadcast",
    "إذاعات دورية": "Recurring Broadcasts",
    "الحملات الترويجية": "Promo Campaigns",
    "الأزرار المخصصة": "Custom Buttons",
    "إدارة المشرفين": "Manage Admins",
    "حملات المستخدمين": "User Campaigns",
    "روابط دعوة البوت": "Bot Invite Links",
    "الإحصائيات": "Statistics",
    "المجموعات": "Groups",

    # Invite links
    "إدارة روابط دعوة البوت (للمالك):": "Bot Invite Links Management (Owner):",
    "لا توجد روابط دعوة مولدة حتى الآن.": "No invite links have been generated yet.",
    "توليد رابط دعوة جديد": "Generate New Invite Link",
    "إيقاف الرابط يدوياً": "Pause Link Manually",
    "إعادة تفعيل الرابط": "Resume Link",
    "حذف الرابط نهائياً": "Delete Link Permanently",
    "رجوع لقائمة الروابط": "Back to Invite Links",
    "تم إيقاف الرابط يدوياً": "Link manually paused",
    "تم تفعيل الرابط": "Link resumed",
    "تم حذف الرابط نهائياً": "Invite link permanently deleted",
    "تم توليد الرابط الدائم": "Permanent link generated",
    "تم توليد الرابط المؤقت": "Temporary link generated",

    # Admin management
    "إضافة مشرف": "Add Admin",
    "إزالة مشرف": "Remove Admin",
    "بدون اسم": "Untitled",
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

# Sorted longest-first to prevent partial phrase overlap
_SORTED_PHRASES: list[tuple[str, str]] = sorted(
    _PHRASE_MAP.items(), key=lambda kv: len(kv[0]), reverse=True
)

# Regex patterns for dynamic admin messages
_REGEX_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"اكتملت الإذاعة! تم الإرسال(?: بنجاح)? إلى <b>(\d+)</b> جهة\."),
        r"Broadcast complete! Sent to <b>\1</b> target(s).",
    ),
    (
        re.compile(r"اكتمل نشر الحملة! تم الإرسال إلى <b>(\d+)</b> جهة\."),
        r"Campaign broadcast complete! Sent to <b>\1</b> target(s).",
    ),
    (
        re.compile(r"تم إضافة المشرف <code>(\d+)</code> بنجاح!"),
        r"Admin <code>\1</code> added successfully!",
    ),
    (
        re.compile(r"تم إزالة المشرف <code>(\d+)</code>(?: بنجاح)?\.?"),
        r"Admin <code>\1</code> removed successfully!",
    ),
    (
        re.compile(r"كل (\d+) ساعا?ت?"),
        r"Every \1 hours",
    ),
]


def translate_admin_text(text: str | None, lang: str | None = None) -> str | None:
    """Translate Arabic admin UI text into English when lang == 'en'."""
    if not text or not isinstance(text, str):
        return text
    resolved = lang or get_context_lang() or "ar"
    if resolved != "en":
        return text

    result = text
    for pattern, repl in _REGEX_PATTERNS:
        result = pattern.sub(repl, result)
    for ar_phrase, en_phrase in _SORTED_PHRASES:
        if ar_phrase in result:
            result = result.replace(ar_phrase, en_phrase)
    return result


def translate_admin_markup(
    markup: InlineKeyboardMarkup | None, lang: str | None = None
) -> InlineKeyboardMarkup | None:
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


# ---------------------------------------------------------------------------
# Aiogram 3 Bot Session Middleware
# ---------------------------------------------------------------------------

class AdminSessionI18nMiddleware:
    """
    Bot session middleware for seamless Admin Panel localization (Phase 6).

    Safety boundary:
    - Activates ONLY when active ContextVar lang == 'en'.
    - For message send/edit methods: ONLY translates when chat_id matches the
      active user (get_context_user_id()), i.e. the admin's own private chat.
    - Translates AnswerCallbackQuery toasts for the active English admin.
    - Group broadcasts and messages to other users are NEVER touched.
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

        # AnswerCallbackQuery — translate toast/alert for English admin
        if method_name == "AnswerCallbackQuery":
            if getattr(method, "text", None):
                new_text = translate_admin_text(method.text, lang)
                if new_text != method.text:
                    method = method.model_copy(update={"text": new_text})
            return await make_request(bot, method)

        # Message send/edit methods — strict safety check
        if method_name in (
            "SendMessage", "EditMessageText", "EditMessageCaption",
            "SendPhoto", "SendVideo",
        ):
            chat_id = getattr(method, "chat_id", None)
            is_self_private = (
                ctx_uid is not None
                and isinstance(chat_id, int)
                and chat_id > 0
                and chat_id == ctx_uid
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
