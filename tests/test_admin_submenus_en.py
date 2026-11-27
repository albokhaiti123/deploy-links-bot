#!/usr/bin/env python3
"""
Verify LanguageMiddleware outer registration and 100% EN translation
of all 9 admin sub-handler text samples.
"""

import asyncio
import os
import re
import sys
import tempfile
from pathlib import Path
import unittest.mock as mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ.setdefault("DB_NAME", _tmp.name)
os.environ.setdefault("ADMIN_ID", "999999")
os.environ.setdefault("BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
os.environ.setdefault("BOT_USERNAME", "testbot")

PASS = 0
FAIL = 0
AR_RE = re.compile(r"[\u0600-\u06FF]")


def ok(msg: str):
    global PASS
    PASS += 1
    print(f"  ✅ PASS: {msg}")


def fail(msg: str, detail: str = ""):
    global FAIL
    FAIL += 1
    print(f"  ❌ FAIL: {msg}")
    if detail:
        print(f"           {detail}")


async def run_checks():
    from core.database import init_db
    from core.i18n import set_lang, LanguageMiddleware
    from core.admin_i18n import translate_admin_text, translate_admin_markup, AdminSessionI18nMiddleware
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.methods import SendMessage, EditMessageReplyMarkup

    await init_db()

    # ── Test 1: outer_middleware registration ────────────────────────────────
    print("\n[1] Checking LanguageMiddleware is registered as outer_middleware...")
    from aiogram import Dispatcher
    from handlers import register_all_routers
    dp = Dispatcher()
    register_all_routers(dp)
    outer_names = [type(m).__name__ for m in dp.update.outer_middleware]
    if "LanguageMiddleware" in outer_names:
        ok("LanguageMiddleware found in dp.update.outer_middleware")
    else:
        fail("LanguageMiddleware NOT in outer_middleware", f"Found: {outer_names}")

    inner_names = [type(m).__name__ for m in dp.update.middleware]
    if "LanguageMiddleware" not in inner_names:
        ok("LanguageMiddleware correctly NOT in inner middleware")
    else:
        fail("LanguageMiddleware is STILL in inner middleware (duplicate)")

    # ── Test 2: end-to-end middleware chain ──────────────────────────────────
    print("\n[2] End-to-end: outer_middleware -> AdminSessionI18nMiddleware...")
    admin_uid = 999999
    await set_lang(admin_uid, "en")

    lang_mw = LanguageMiddleware()
    sess_mw = AdminSessionI18nMiddleware()
    sent = []

    async def fake_make_request(bot, method):
        sent.append(method)
        return method

    async def fake_handler(event, data):
        # Private admin message → must translate
        m1 = SendMessage(
            chat_id=admin_uid,
            text="📢 <b>إعداد الترويج (للمجموعات)</b>\n\nيمكنك استخدام <code>{user}</code> في النص ليتم استبدالها تلقائياً بـ 'منشن' للعضو الجديد.\n\nاختر ما تريد تعديله:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="تعديل النص", callback_data="admin_edit_text")],
                [InlineKeyboardButton(text="رجوع", callback_data="admin_main")],
            ]),
        )
        await sess_mw(fake_make_request, None, m1)

        # EditMessageReplyMarkup → must also translate
        m2 = EditMessageReplyMarkup(
            chat_id=admin_uid,
            message_id=10,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🧹 إيقاف الحذف التلقائي", callback_data="x")]
            ]),
        )
        await sess_mw(fake_make_request, None, m2)

        # Group broadcast → must NOT translate
        m3 = SendMessage(chat_id=-100123456, text="إعلان عربي للمجموعة")
        await sess_mw(fake_make_request, None, m3)

    fake_event = mock.MagicMock()
    fake_event.callback_query.from_user.id = admin_uid
    fake_event.callback_query.from_user.language_code = "ar"
    await lang_mw(fake_handler, fake_event, {})

    if "Promo Settings (Groups)" in sent[0].text:
        ok("SendMessage text translated (Promo Settings)")
    else:
        fail("SendMessage text NOT translated", f"Got: {sent[0].text[:60]}")

    if sent[0].reply_markup.inline_keyboard[0][0].text == "Edit Text":
        ok("SendMessage markup btn translated (Edit Text)")
    else:
        fail("SendMessage markup btn NOT translated", f"Got: {sent[0].reply_markup.inline_keyboard[0][0].text}")

    if sent[0].reply_markup.inline_keyboard[1][0].text == "Back":
        ok("SendMessage markup btn translated (Back)")
    else:
        fail("SendMessage markup Back NOT translated", f"Got: {sent[0].reply_markup.inline_keyboard[1][0].text}")

    if sent[1].reply_markup.inline_keyboard[0][0].text == "🧹 Disable Auto-Delete":
        ok("EditMessageReplyMarkup translated correctly")
    else:
        fail("EditMessageReplyMarkup NOT translated", f"Got: {sent[1].reply_markup.inline_keyboard[0][0].text}")

    if sent[2].text == "إعلان عربي للمجموعة":
        ok("Group broadcast NOT modified (safety boundary holds)")
    else:
        fail("Group broadcast was modified (safety boundary broken!)")

    # ── Test 3: 100% translation of real samples from all 9 admin files ─────
    print("\n[3] Checking 100% translation of 9 admin sub-handler samples...")

    samples = [
        # admins.py
        ("admins", "👑 <b>المشرفون الحاليون:</b>"),
        ("admins", "أرسل معرف تيليجرام (Telegram ID) للشخص الذي تريد إضافته كمشرف:\nلإلغاء الأمر أرسل /cancel"),
        # stats.py
        ("stats", "📊 <b>الإحصائيات</b>\n\n👥 إجمالي المستخدمين: <b>100</b> (اليوم: 5)\n🌐 المجموعات النشطة: <b>20</b> / الإجمالي: 25\n📢 إجمالي الترويجات: <b>500</b> (اليوم: 12)"),
        ("stats", "🌐 <b>المجموعات:</b>\n\nلا توجد مجموعات مسجلة حتى الآن."),
        # promo_settings.py
        ("promo_settings", "📢 <b>إعداد الترويج (للمجموعات)</b>\n\nيمكنك استخدام <code>{user}</code> في النص ليتم استبدالها تلقائياً بـ 'منشن' للعضو الجديد.\n\nاختر ما تريد تعديله:"),
        ("promo_settings", "أرسل الآن نص الإعلان الجديد:\n(تذكر يمكنك استخدام <code>{user}</code> للمنشن)\nلإلغاء الأمر أرسل /cancel"),
        # general_settings.py
        ("general_settings", "⚙️ <b>الإعدادات:</b>\n\n📱 رسالة الترحيب (الخاص): مفعلة ✅\n⏱ مدة الانتظار الحالية: بدون انتظار (0 ثانية)\n🧹 الحذف التلقائي للإعلان القديم: مفعل ✅\n🗑 حذف رسالة الترويج بعد: بدون حذف"),
        ("general_settings", "✅ تم تحديث مدة الانتظار إلى 60 ثانية."),
        # welcome_settings.py
        ("welcome_settings", "⚙️ <b>إعدادات رسالة الترحيب (الخاص):</b>\n\nتتحكم هذه القائمة بالرسالة والأزرار التي تظهر للأعضاء عند بدء المحادثة مع البوت في الخاص.\nاختر ما تريد تعديله:"),
        ("welcome_settings", "تم تحديث رسالة الترحيب بنجاح."),
        # broadcast.py
        ("broadcast", "📣 <b>ساحر الإذاعة الجديد:</b>\n\nاختر الوجهة التي تريد بدء الإذاعة إليها:"),
        ("broadcast", "📋 <b>ملخص الإذاعة النهائي:</b>\n\n👥 <b>الوجهة:</b> المجموعات\n🖼 <b>الوسائط:</b> نعم (مدفوعة بـ 50 نجمة ⭐️)\n)\n⏳ <b>التدمير الذاتي:</b> تُحذف بعد 30 دقيقة\n\nهل أنت متأكد من الإرسال الآن؟"),
        # recurring.py
        ("recurring", "🔄 <b>الإذاعات الدورية:</b>\n\nلا توجد إذاعات دورية حالياً."),
        ("recurring", "تم إنشاء إذاعة دورية (كل 12 ساعة)!"),
        # button_manager.py
        ("button_manager", "لا توجد أزرار مخصصة حالياً."),
        ("button_manager", "تم حذف الزر."),
        # campaigns.py
        ("campaigns", "🎯 <b>إدارة الحملات الترويجية:</b>\n\nأنشئ حملات تُلزم المستخدمين بإضافة البوت إلى مجموعات مقابل فتح محتوى."),
        ("campaigns", "📋 <b>ملخص الحملة:</b>\n\n📌 الاسم: Test\n📝 نص الإعلان: Hi...\n🖼 وسائط: لا\n🔘 زر CTA: Go\n👥 المجموعات المطلوبة: 3\n🗑 حذف محتوى الفتح: بعد 30 ثانية\n📤 وضع النشر: دوري (كل 12 ساعة)\n\nهل تريد إنشاء الحملة؟"),
        ("campaigns", "تم إنشاء الحملة بنجاح!"),
        ("campaigns", "اكتملت الإذاعة! تم الإرسال بنجاح إلى <b>42</b> جهة."),
    ]

    all_ok = True
    for module, text in samples:
        out = translate_admin_text(text, "en")
        if AR_RE.search(out):
            fail(f"{module}: Arabic chars remain in translation", f"IN:  {text[:60]}...\n           OUT: {out[:80]}")
            all_ok = False
        else:
            ok(f"{module}: '{text[:50]}...' → EN clean")

    # ── Test 4: markup translation ──────────────────────────────────────────
    print("\n[4] Checking markup button translation...")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 إعداد الترويج", callback_data="x")],
        [InlineKeyboardButton(text="🧹 تشغيل الحذف التلقائي", callback_data="y")],
        [InlineKeyboardButton(text="لا توجد أزرار مخصصة حالياً.", callback_data="z")],
    ])
    translated_kb = translate_admin_markup(kb, "en")
    for row in translated_kb.inline_keyboard:
        for btn in row:
            if AR_RE.search(btn.text):
                fail(f"Markup btn still has Arabic: '{btn.text}'")
                all_ok = False
            else:
                ok(f"Markup btn translated: '{btn.text}'")

    # ── Summary ──────────────────────────────────────────────────────────────
    total = PASS + FAIL
    print(f"\n{'='*55}")
    print(f"Results: {PASS}/{total} passed, {FAIL} failed")
    print("=" * 55)
    if FAIL == 0:
        print("🎉 All admin sub-menu i18n checks passed!")
    return FAIL


if __name__ == "__main__":
    try:
        result = asyncio.run(run_checks())
    finally:
        try:
            os.unlink(_tmp.name)
        except OSError:
            pass
    sys.exit(result)
