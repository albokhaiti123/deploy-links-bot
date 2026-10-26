"""
Campaign admin handlers — menu, creation wizard, admin view, list,
stats, publish, test, pause/resume/delete, recurring.
"""

import asyncio
from datetime import datetime

from aiogram import Router, F, types
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.bot import bot
from core.config import BOT_USERNAME
from models.admins import is_admin
from models.settings import get_setting
from models.campaigns import (
    get_campaign, create_campaign, update_campaign_status,
    set_campaign_recurring, list_campaigns, get_campaign_stats,
)
from services.campaign import execute_campaign_broadcast
from services.media import send_media_message
from states.states import CampaignWizard

router = Router(name="admin_campaigns")


# ── Campaign Menu ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "cmp_menu")
async def cb_cmp_menu(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ إنشاء حملة جديدة", callback_data="cmp_create")],
        [InlineKeyboardButton(text="📋 قائمة الحملات", callback_data="cmp_list")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_main")],
    ])
    await callback.message.edit_text(
        "🎯 <b>إدارة الحملات الترويجية:</b>\n\n"
        "أنشئ حملات تُلزم المستخدمين بإضافة البوت إلى مجموعات مقابل فتح محتوى.",
        reply_markup=kb, parse_mode=ParseMode.HTML,
    )
    await callback.answer()


# ── Campaign Creation Wizard ─────────────────────────────────────────────────

@router.callback_query(F.data == "cmp_create")
async def cb_cmp_create(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.answer(
        "🎯 <b>إنشاء حملة جديدة:</b>\n\n"
        "<b>الخطوة 1/10:</b> أرسل اسم الحملة:\n"
        "لإلغاء أرسل /cancel",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(CampaignWizard.name)
    await callback.answer()


@router.message(CampaignWizard.name)
async def process_cw_name(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ تم إلغاء إنشاء الحملة.")
        await state.clear()
        return
    await state.update_data(name=message.text)
    await message.answer(
        "<b>الخطوة 2/10:</b> أرسل نص الإعلان الترويجي للحملة:\n"
        "(هذا النص سيُرسل في المجموعات والخاص)\n"
        "لإلغاء أرسل /cancel",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(CampaignWizard.promo_text)


@router.message(CampaignWizard.promo_text)
async def process_cw_promo_text(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
    await state.update_data(promo_text=message.html_text or message.text)
    await message.answer(
        "<b>الخطوة 3/10:</b> أرسل صورة أو فيديو لإرفاقه مع إعلان الحملة.\n"
        "أرسل /skip لتخطي.\nلإلغاء أرسل /cancel",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(CampaignWizard.media)


@router.message(CampaignWizard.media, F.photo | F.video | F.text)
async def process_cw_media(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
    if message.text == "/skip":
        await state.update_data(media_file_id=None, media_type=None)
    elif message.photo:
        await state.update_data(media_file_id=message.photo[-1].file_id, media_type="photo")
    elif message.video:
        await state.update_data(media_file_id=message.video.file_id, media_type="video")
    else:
        return await message.answer("❌ أرسل صورة أو فيديو أو /skip.")
    await message.answer(
        "<b>الخطوة 4/10:</b> أرسل نص الزر (CTA) مثلاً: 🎁 الحصول على العرض\n"
        "لإلغاء أرسل /cancel",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(CampaignWizard.button_text)


@router.message(CampaignWizard.button_text)
async def process_cw_button_text(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
    await state.update_data(button_text=message.text)
    await message.answer(
        "<b>الخطوة 5/10:</b> كم عدد المجموعات المطلوبة من المستخدم لفتح المحتوى؟\n"
        "(أرسل رقماً بين 1 و 50)\nلإلغاء أرسل /cancel",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(CampaignWizard.required_groups)


@router.message(CampaignWizard.required_groups)
async def process_cw_required_groups(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
    if not message.text.isdigit() or not 1 <= int(message.text) <= 50:
        return await message.answer("❌ أرسل رقماً بين 1 و 50.")
    await state.update_data(required_groups=int(message.text))
    await message.answer(
        "<b>الخطوة 6/10:</b> أرسل محتوى الفتح (النص أو الرسالة التي سيستلمها المستخدم بعد الإنجاز):\n"
        "لإلغاء أرسل /cancel",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(CampaignWizard.unlock_content)


@router.message(CampaignWizard.unlock_content)
async def process_cw_unlock_content(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
    await state.update_data(unlock_content=message.html_text or message.text)
    await message.answer(
        "<b>الخطوة 7/10:</b> أرسل وسائط فتح (صورة أو فيديو) تُرفق مع محتوى الفتح.\n"
        "أرسل /skip لتخطي.\nلإلغاء أرسل /cancel",
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(CampaignWizard.unlock_media)


@router.message(CampaignWizard.unlock_media, F.photo | F.video | F.text)
async def process_cw_unlock_media(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
    if message.text == "/skip":
        await state.update_data(unlock_media_file_id=None, unlock_media_type=None)
    elif message.photo:
        await state.update_data(unlock_media_file_id=message.photo[-1].file_id, unlock_media_type="photo")
    elif message.video:
        await state.update_data(unlock_media_file_id=message.video.file_id, unlock_media_type="video")
    else:
        return await message.answer("❌ أرسل صورة أو فيديو أو /skip.")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="بدون حذف", callback_data="cw_del_0")],
        [InlineKeyboardButton(text="30 ثانية", callback_data="cw_del_30"),
         InlineKeyboardButton(text="1 دقيقة", callback_data="cw_del_60")],
        [InlineKeyboardButton(text="5 دقائق", callback_data="cw_del_300"),
         InlineKeyboardButton(text="30 دقيقة", callback_data="cw_del_1800")],
    ])
    await message.answer(
        "<b>الخطوة 8/10:</b> حذف محتوى الفتح تلقائياً بعد كم؟",
        reply_markup=kb, parse_mode=ParseMode.HTML,
    )
    await state.set_state(CampaignWizard.unlock_delete)


@router.callback_query(CampaignWizard.unlock_delete, F.data.startswith("cw_del_"))
async def cb_cw_unlock_delete(callback: types.CallbackQuery, state: FSMContext):
    sec = int(callback.data.split("_")[-1])
    await state.update_data(unlock_delete_seconds=sec)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 يدوي (أنا أنشره)", callback_data="cw_mode_manual")],
        [InlineKeyboardButton(text="🔄 دوري (تلقائي)", callback_data="cw_mode_recurring")],
    ])
    await callback.message.answer(
        "<b>الخطوة 9/10:</b> اختر وضع النشر:",
        reply_markup=kb, parse_mode=ParseMode.HTML,
    )
    await state.set_state(CampaignWizard.mode_select)
    await callback.answer()


@router.callback_query(CampaignWizard.mode_select)
async def cb_cw_mode(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "cw_mode_manual":
        await state.update_data(mode="manual", repeat_hours=0)
        await _show_confirm(callback, state)
    elif callback.data == "cw_mode_recurring":
        await state.update_data(mode="recurring")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="كل 6 ساعات", callback_data="cw_rh_6"),
             InlineKeyboardButton(text="كل 12 ساعة", callback_data="cw_rh_12")],
            [InlineKeyboardButton(text="كل 24 ساعة", callback_data="cw_rh_24"),
             InlineKeyboardButton(text="كل 48 ساعة", callback_data="cw_rh_48")],
        ])
        await callback.message.answer(
            "<b>الخطوة 10/10:</b> كل كم ساعة يتم تكرار النشر؟",
            reply_markup=kb, parse_mode=ParseMode.HTML,
        )
        await state.set_state(CampaignWizard.repeat_hours)
    await callback.answer()


@router.callback_query(CampaignWizard.repeat_hours, F.data.startswith("cw_rh_"))
async def cb_cw_repeat_hours(callback: types.CallbackQuery, state: FSMContext):
    hours = int(callback.data.split("_")[-1])
    await state.update_data(repeat_hours=hours)
    await _show_confirm(callback, state)
    await callback.answer()


async def _show_confirm(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mode_ar = "يدوي" if data.get("mode") == "manual" else f"دوري (كل {data.get('repeat_hours', 0)} ساعة)"
    del_sec = data.get("unlock_delete_seconds", 0)
    del_ar = "بدون حذف" if del_sec == 0 else f"بعد {del_sec} ثانية"
    text = (
        f"📋 <b>ملخص الحملة:</b>\n\n"
        f"📌 الاسم: {data['name']}\n"
        f"📝 نص الإعلان: {data['promo_text'][:50]}...\n"
        f"🖼 وسائط: {'نعم' if data.get('media_file_id') else 'لا'}\n"
        f"🔘 زر CTA: {data['button_text']}\n"
        f"👥 المجموعات المطلوبة: {data['required_groups']}\n"
        f"🗑 حذف محتوى الفتح: {del_ar}\n"
        f"📤 وضع النشر: {mode_ar}\n\n"
        f"هل تريد إنشاء الحملة؟"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ إنشاء الحملة", callback_data="cmp_confirm_create")],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="cmp_cancel_create")],
    ])
    await callback.message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await state.set_state(CampaignWizard.confirm)


@router.callback_query(CampaignWizard.confirm)
async def cb_cw_confirm(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    if callback.data == "cmp_cancel_create":
        await callback.message.answer("❌ تم إلغاء إنشاء الحملة.")
        await state.clear()
        await callback.answer()
        return
    data = await state.get_data()
    await state.clear()
    campaign_id = await create_campaign(data)
    await callback.message.answer(
        f"✅ <b>تم إنشاء الحملة بنجاح!</b>\n\nالمعرف: #{campaign_id}\nالاسم: {data['name']}",
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


# ── Campaign List ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "cmp_list")
async def cb_cmp_list(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    camps = await list_campaigns()
    if not camps:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 رجوع", callback_data="cmp_menu")],
        ])
        await callback.message.edit_text("📋 لا توجد حملات حالياً.", reply_markup=kb)
        await callback.answer()
        return
    buttons = []
    for cid, name, status, required in camps:
        s_icon = {"active": "✅", "paused": "⏸", "deleted": "🗑"}.get(status, "❓")
        buttons.append([InlineKeyboardButton(
            text=f"{s_icon} {name} (#{cid})", callback_data=f"cmp_view_{cid}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="cmp_menu")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("📋 <b>قائمة الحملات:</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()


# ── Campaign Admin View ──────────────────────────────────────────────────────

async def show_campaign_admin_view(message: types.Message, campaign_id: int):
    campaign = await get_campaign(campaign_id)
    if not campaign:
        await message.answer("❌ الحملة غير موجودة.")
        return
    stats = await get_campaign_stats(campaign_id)
    status_map = {"active": "نشطة ✅", "paused": "متوقفة ⏸", "deleted": "محذوفة 🗑"}
    mode_ar = "يدوي" if campaign.get("mode") == "manual" else f"دوري (كل {campaign.get('repeat_hours', 0)} ساعة)"
    text = (
        f"🎯 <b>الحملة #{campaign_id}: {campaign['name']}</b>\n\n"
        f"📊 الحالة: {status_map.get(campaign['status'], campaign['status'])}\n"
        f"📤 وضع النشر: {mode_ar}\n"
        f"👥 المجموعات المطلوبة: {campaign['required_groups']}\n\n"
        f"📈 <b>إحصائيات:</b>\n"
        f"  🚀 بدأوا: {stats['started']}\n"
        f"  ➕ مجموعات أُضيفت: {stats['groups_added']}\n"
        f"  🔓 فتحوا المحتوى: {stats['unlocked']}\n"
    )
    buttons = []
    if campaign["status"] == "active":
        buttons.append([InlineKeyboardButton(text="⏸ إيقاف", callback_data=f"cmp_pause_{campaign_id}")])
    elif campaign["status"] == "paused":
        buttons.append([InlineKeyboardButton(text="▶️ استئناف", callback_data=f"cmp_resume_{campaign_id}")])
    buttons.append([
        InlineKeyboardButton(text="📢 نشر للمستخدمين", callback_data=f"cmp_pub_users_{campaign_id}"),
        InlineKeyboardButton(text="📢 نشر للمجموعات", callback_data=f"cmp_pub_groups_{campaign_id}"),
    ])
    buttons.append([InlineKeyboardButton(text="📢 نشر للجميع", callback_data=f"cmp_pub_all_{campaign_id}")])
    buttons.append([
        InlineKeyboardButton(text="🧪 اختبار (لي)", callback_data=f"cmp_test_{campaign_id}"),
        InlineKeyboardButton(text="🧪 اختبار (مجموعة)", callback_data=f"cmp_testgrp_{campaign_id}"),
    ])
    if campaign.get("mode") == "recurring":
        if campaign.get("recurring_active"):
            buttons.append([InlineKeyboardButton(text="⏸ إيقاف النشر الدوري", callback_data=f"cmp_recstop_{campaign_id}")])
        else:
            buttons.append([InlineKeyboardButton(text="▶️ تشغيل النشر الدوري", callback_data=f"cmp_recstart_{campaign_id}")])
    buttons.append([InlineKeyboardButton(text="🗑 حذف الحملة", callback_data=f"cmp_delete_{campaign_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="cmp_list")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except TelegramAPIError:
        await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("cmp_view_"))
async def cb_cmp_view(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    campaign_id = int(callback.data.split("_")[-1])
    await show_campaign_admin_view(callback.message, campaign_id)
    await callback.answer()


# ── Pause / Resume / Delete ──────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cmp_pause_"))
async def cb_cmp_pause(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    cid = int(callback.data.split("_")[-1])
    await update_campaign_status(cid, "paused")
    await callback.answer("⏸ تم الإيقاف.", show_alert=True)
    await show_campaign_admin_view(callback.message, cid)


@router.callback_query(F.data.startswith("cmp_resume_"))
async def cb_cmp_resume(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    cid = int(callback.data.split("_")[-1])
    await update_campaign_status(cid, "active")
    await callback.answer("▶️ تم الاستئناف.", show_alert=True)
    await show_campaign_admin_view(callback.message, cid)


@router.callback_query(F.data.startswith("cmp_delete_"))
async def cb_cmp_delete(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    cid = int(callback.data.split("_")[-1])
    await update_campaign_status(cid, "deleted")
    await callback.answer("🗑 تم حذف الحملة.", show_alert=True)
    await cb_cmp_list(callback)


# ── Publish ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cmp_pub_"))
async def cb_cmp_pub(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    parts = callback.data.split("_")
    target = parts[2]  # users, groups, or all
    cid = int(parts[3])
    status_msg = await callback.message.answer("🚀 جاري النشر...")
    asyncio.create_task(execute_campaign_broadcast(cid, target, status_msg))
    await callback.answer()


# ── Test (to self) ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cmp_test_"))
async def cb_cmp_test(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    cid = int(callback.data.split("_")[-1])
    campaign = await get_campaign(cid)
    if not campaign:
        await callback.answer("❌ الحملة غير موجودة.", show_alert=True)
        return
    bot_info = await bot.get_me()
    cta = InlineKeyboardButton(text=campaign["button_text"], url=f"https://t.me/{bot_info.username}?start=camp_{cid}")
    kb = InlineKeyboardMarkup(inline_keyboard=[[cta]])
    try:
        await send_media_message(
            bot, callback.from_user.id,
            f"🧪 <b>[اختبار]</b>\n\n{campaign['promo_text']}",
            media_id=campaign.get("media_file_id"),
            media_type=campaign.get("media_type"),
            keyboard=kb,
        )
        await callback.answer("✅ تم إرسال نسخة تجريبية لك.", show_alert=True)
    except Exception as e:
        await callback.answer("❌ فشل إرسال الاختبار.", show_alert=True)


# ── Test (to group) ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cmp_testgrp_"))
async def cb_cmp_test_group(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    cid = int(callback.data.split("_")[-1])
    test_group = await get_setting("test_group_chat_id")
    if not test_group:
        await callback.answer("❌ لم يتم تحديد مجموعة اختبار. اذهب للإعدادات.", show_alert=True)
        return
    campaign = await get_campaign(cid)
    if not campaign:
        await callback.answer("❌ الحملة غير موجودة.", show_alert=True)
        return
    bot_info = await bot.get_me()
    cta = InlineKeyboardButton(text=campaign["button_text"], url=f"https://t.me/{bot_info.username}?start=camp_{cid}")
    kb = InlineKeyboardMarkup(inline_keyboard=[[cta]])
    try:
        chat_id = int(test_group)
        await send_media_message(
            bot, chat_id,
            f"🧪 [Test]\n\n{campaign['promo_text']}",
            media_id=campaign.get("media_file_id"),
            media_type=campaign.get("media_type"),
            keyboard=kb,
        )
        await callback.answer("✅ تم الإرسال لمجموعة الاختبار.", show_alert=True)
    except Exception:
        await callback.answer("❌ فشل الإرسال لمجموعة الاختبار.", show_alert=True)


# ── Recurring Start/Stop ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cmp_recstart_"))
async def cb_cmp_rec_start(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    cid = int(callback.data.split("_")[-1])
    await set_campaign_recurring(cid, True)
    await callback.answer("▶️ تم تشغيل النشر الدوري.", show_alert=True)
    await show_campaign_admin_view(callback.message, cid)


@router.callback_query(F.data.startswith("cmp_recstop_"))
async def cb_cmp_rec_stop(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    cid = int(callback.data.split("_")[-1])
    await set_campaign_recurring(cid, False)
    await callback.answer("⏸ تم إيقاف النشر الدوري.", show_alert=True)
    await show_campaign_admin_view(callback.message, cid)
