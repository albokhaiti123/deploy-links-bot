import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode, ChatType
from aiogram.filters import CommandStart, Command, IS_MEMBER, IS_NOT_MEMBER, ChatMemberUpdatedFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated, InputPaidMediaPhoto, InputPaidMediaVideo
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter, TelegramForbiddenError

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0)) if os.getenv("ADMIN_ID") else 0
BOT_USERNAME = os.getenv("BOT_USERNAME", "")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_NAME = "bot.db"

# --- Database Initialization ---
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                chat_id INTEGER PRIMARY KEY,
                title TEXT,
                chat_type TEXT,
                status TEXT,
                added_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        
        try:
            await db.execute("ALTER TABLE groups ADD COLUMN last_promo_msg_id INTEGER")
        except aiosqlite.OperationalError:
            pass
        
        try:
            await db.execute("ALTER TABLE groups ADD COLUMN added_by INTEGER")
        except aiosqlite.OperationalError:
            pass
            
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                created_at TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                telegram_user_id INTEGER,
                event_type TEXT,
                created_at TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                telegram_id INTEGER PRIMARY KEY,
                added_at TIMESTAMP
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                message_id INTEGER,
                delete_at TIMESTAMP
            )
        """)
        
        # --- Campaign Tables ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                promo_text TEXT,
                media_type TEXT,
                media_file_id TEXT,
                button_text TEXT DEFAULT '🎁 الحصول على العرض',
                required_groups INTEGER DEFAULT 5,
                unlock_content TEXT,
                unlock_media_type TEXT,
                unlock_media_file_id TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS campaign_user_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                verified_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'in_progress',
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                UNIQUE(campaign_id, user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS campaign_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                chat_title TEXT,
                verified INTEGER DEFAULT 0,
                verified_at TIMESTAMP,
                UNIQUE(campaign_id, user_id, chat_id)
            )
        """)
        
        default_settings = {
            "promo_enabled": "true",
            "promo_text": "🔥 مرحبًا بك يا {user}!\nاكتشف خدماتنا ومحتوانا من خلال الرابط التالي.",
            "promo_url": "https://t.me/example",
            "promo_button_text": "🚀 اشترك الآن",
            "cooldown": "60",
            "promo_media_id": "",
            "promo_media_type": "",
            "auto_delete": "false",
            "show_add_bot_button": "true",
            "promo_is_vip": "false",
            "promo_stars": "50",
            "promo_post_payment_msg": "✅ شكراً لك! لقد تم الدفع بنجاح.",
            "start_message": "🤖 أهلاً بك في البوت!\n\nهذا البوت يساعدك على إضافة رسائل ترويجية إلى مجموعتك عند انضمام أعضاء جدد.\nأضف البوت إلى مجموعتك وسيبدأ العمل تلقائياً بناءً على إعدادات الإدارة.",
            "start_btn2_name": "ℹ️ طريقة الاستخدام",
            "start_btn2_type": "text",
            "start_btn2_content": "ℹ️ <b>طريقة الاستخدام:</b>\n\n1. اضغط على زر 'إضافة البوت إلى مجموعتي'.\n2. اختر المجموعة التي تريد إضافة البوت إليها.\n3. عند انضمام أي عضو جديد، سيقوم البوت بإرسال رسالة ترحيبية ترويجية.\n4. يمتلك البوت نظام حماية من التكرار (Cooldown) لمنع الإزعاج."
        }
        
        for k, v in default_settings.items():
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
            
        await db.commit()

async def get_setting(key: str) -> str:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else ""

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
        await db.commit()

async def is_admin(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT 1 FROM admins WHERE telegram_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone() is not None

# --- Cache for Cooldown ---
last_promo_times = {}

# --- FSM States ---
class AdminEdit(StatesGroup):
    waiting_for_promo_text = State()
    waiting_for_promo_url = State()
    waiting_for_promo_button = State()
    waiting_for_cooldown = State()
    waiting_for_admin_id = State()
    waiting_for_media = State()
    waiting_for_start_msg = State()
    waiting_for_start_btn2_name = State()
    waiting_for_start_btn2_url = State()
    waiting_for_start_btn2_text = State()
    waiting_for_promo_stars = State()
    waiting_for_post_payment_msg = State()

class BroadcastWizard(StatesGroup):
    target = State()
    text = State()
    media = State()
    media_type_vip = State()
    stars = State()
    duration = State()
    confirm = State()

class CampaignWizard(StatesGroup):
    name = State()
    promo_text = State()
    media = State()
    button_text = State()
    required_groups = State()
    unlock_content = State()
    unlock_media = State()
    confirm = State()

# --- Bot & Dispatcher ---
bot = Bot(token=BOT_TOKEN) 
dp = Dispatcher(storage=MemoryStorage())

def get_bot_add_url(bot_username: str) -> str:
    return f"https://t.me/{bot_username}?startgroup=add"

def build_promo_keyboard(promo_url: str, promo_button_text: str, bot_username: str, show_bot_btn: str = "true") -> InlineKeyboardMarkup:
    keyboard = []
    if promo_button_text and promo_url:
        keyboard.append([InlineKeyboardButton(text=promo_button_text, url=promo_url)])
    if show_bot_btn == "true":
        keyboard.append([InlineKeyboardButton(text="🤖 أضف البوت إلى مجموعتك", url=get_bot_add_url(bot_username))])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def get_start_message_data(bot_username: str):
    start_text = await get_setting("start_message")
    if not start_text:
        start_text = "🤖 أهلاً بك في البوت!"
        
    btn2_name = await get_setting("start_btn2_name")
    btn2_type = await get_setting("start_btn2_type")
    btn2_content = await get_setting("start_btn2_content")
    
    kb = [[InlineKeyboardButton(text="➕ إضافة البوت إلى مجموعتي", url=get_bot_add_url(bot_username))]]
    
    if btn2_name:
        if btn2_type == "url":
            kb.append([InlineKeyboardButton(text=btn2_name, url=btn2_content)])
        else:
            kb.append([InlineKeyboardButton(text=btn2_name, callback_data="start_btn2_click")])
            
    return start_text, InlineKeyboardMarkup(inline_keyboard=kb)

# --- Utilities ---
async def log_event(chat_id: int, user_id: int, event_type: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO events (chat_id, telegram_user_id, event_type, created_at) VALUES (?, ?, ?, ?)",
                         (chat_id, user_id, event_type, datetime.now()))
        await db.commit()

async def trigger_group_promo(message: types.Message, target_user: types.User):
    bot_info = await bot.get_me()
    chat_id = message.chat.id
    
    promo_enabled = await get_setting("promo_enabled")
    if promo_enabled != "true":
        return

    cooldown_val = await get_setting("cooldown")
    cooldown = int(cooldown_val) if cooldown_val and cooldown_val.isdigit() else 60
    current_time = time.time()
    
    if cooldown > 0 and chat_id in last_promo_times:
        if current_time - last_promo_times[chat_id] < cooldown:
            logger.info(f"Promo skipped in {chat_id} due to cooldown active.")
            return

    last_promo_times[chat_id] = current_time

    promo_text = await get_setting("promo_text")
    promo_url = await get_setting("promo_url")
    promo_button_text = await get_setting("promo_button_text")
    promo_media_id = await get_setting("promo_media_id")
    promo_media_type = await get_setting("promo_media_type")
    show_add_bot_button = await get_setting("show_add_bot_button")
    auto_delete = await get_setting("auto_delete")
    is_vip = await get_setting("promo_is_vip") == "true"
    stars_val = await get_setting("promo_stars")
    stars = int(stars_val) if stars_val and stars_val.isdigit() else 50
    
    # Format text with mention
    user_name = target_user.first_name.replace('<', '&lt;').replace('>', '&gt;')
    mention = f"<a href='tg://user?id={target_user.id}'>{user_name}</a>"
    promo_text_formatted = promo_text.replace("{user}", mention)
    
    keyboard = build_promo_keyboard(promo_url, promo_button_text, bot_info.username or BOT_USERNAME, show_add_bot_button)
    
    # Auto Delete old message
    if auto_delete == "true":
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT last_promo_msg_id FROM groups WHERE chat_id=?", (chat_id,)) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    try:
                        await bot.delete_message(chat_id, row[0])
                    except TelegramAPIError:
                        pass
    
    try:
        sent_msg = None
        if is_vip:
            if promo_media_id:
                # Paid Media
                media_payload = [InputPaidMediaPhoto(media=promo_media_id)] if promo_media_type == 'photo' else [InputPaidMediaVideo(media=promo_media_id)]
                sent_msg = await bot.send_paid_media(
                    chat_id=chat_id,
                    star_count=stars,
                    media=media_payload,
                    caption=promo_text_formatted,
                    parse_mode=ParseMode.HTML
                )
            else:
                # Paid Text (Invoice)
                text_msg = await bot.send_message(chat_id, promo_text_formatted, reply_markup=keyboard, parse_mode=ParseMode.HTML)
                prices = [types.LabeledPrice(label="فتح المحتوى السري", amount=stars)]
                sent_msg = await bot.send_invoice(
                    chat_id=chat_id,
                    title="محتوى مدفوع (VIP)",
                    description="قم بدفع النجوم لاستلام رسالة ما بعد الدفع فوراً.",
                    payload="paid_promo",
                    provider_token="", 
                    currency="XTR",
                    prices=prices,
                    reply_to_message_id=text_msg.message_id
                )
        else:
            if promo_media_id and promo_media_type == "photo":
                sent_msg = await message.answer_photo(photo=promo_media_id, caption=promo_text_formatted, reply_markup=keyboard, parse_mode=ParseMode.HTML)
            elif promo_media_id and promo_media_type == "video":
                sent_msg = await message.answer_video(video=promo_media_id, caption=promo_text_formatted, reply_markup=keyboard, parse_mode=ParseMode.HTML)
            else:
                sent_msg = await message.answer(
                    promo_text_formatted,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML,
                    link_preview_options=types.LinkPreviewOptions(is_disabled=True)
                )
            
        if sent_msg:
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("UPDATE groups SET last_promo_msg_id=? WHERE chat_id=?", (sent_msg.message_id, chat_id))
                await db.commit()
                
        await log_event(chat_id, target_user.id, "promo_sent")
        logger.info(f"Promo sent in {chat_id}")
    except TelegramRetryAfter as e:
        logger.warning(f"Rate limited in {chat_id}. Retry after {e.retry_after}")
    except TelegramForbiddenError:
        logger.warning(f"Forbidden to send message in {chat_id}. Marking inactive.")
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE groups SET status='inactive', updated_at=? WHERE chat_id=?", (datetime.now(), chat_id))
            await db.commit()
    except TelegramAPIError as e:
        logger.error(f"Failed to send promo in {chat_id}: {e}")

# --- Background Tasks ---
async def auto_delete_broadcasts():
    while True:
        try:
            await asyncio.sleep(60)
            async with aiosqlite.connect(DB_NAME) as db:
                cursor = await db.execute("SELECT id, chat_id, message_id FROM broadcast_messages WHERE delete_at <= ?", (datetime.now(),))
                expired_messages = await cursor.fetchall()
                for row in expired_messages:
                    db_id, chat_id, message_id = row
                    try:
                        await bot.delete_message(chat_id, message_id)
                    except TelegramAPIError:
                        pass
                    await db.execute("DELETE FROM broadcast_messages WHERE id = ?", (db_id,))
                await db.commit()
        except Exception as e:
            logger.error(f"Error in auto_delete_broadcasts task: {e}")

# --- Handlers ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    if message.chat.type != ChatType.PRIVATE:
        await trigger_group_promo(message, message.from_user)
        return
        
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (telegram_id, username, first_name, created_at) VALUES (?, ?, ?, ?)",
                         (message.from_user.id, message.from_user.username, message.from_user.first_name, datetime.now()))
        await db.commit()
    
    # Campaign deep link: /start camp_123
    parts = message.text.split()
    if len(parts) > 1 and parts[1].startswith("camp_"):
        try:
            campaign_id = int(parts[1].replace("camp_", ""))
            await show_campaign_progress(message, campaign_id, message.from_user.id)
            return
        except (ValueError, TypeError):
            pass
        
    bot_info = await bot.get_me()
    text, kb = await get_start_message_data(bot_info.username or BOT_USERNAME)
    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)

@dp.callback_query(F.data == "start_btn2_click")
async def cb_start_btn2_click(callback: types.CallbackQuery):
    content = await get_setting("start_btn2_content")
    if not content:
        content = "لا توجد رسالة."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 رجوع", callback_data="start_back")]])
    await callback.message.edit_text(content, reply_markup=kb, parse_mode=ParseMode.HTML)

@dp.callback_query(F.data == "start_back")
async def cb_start_back(callback: types.CallbackQuery):
    bot_info = await bot.get_me()
    text, kb = await get_start_message_data(bot_info.username or BOT_USERNAME)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

# --- Payment Handlers ---
@dp.pre_checkout_query(lambda query: query.invoice_payload == "paid_promo")
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    if message.successful_payment.invoice_payload == "paid_promo":
        post_msg = await get_setting("promo_post_payment_msg")
        if not post_msg:
            post_msg = "✅ تم تأكيد الدفع بنجاح!"
        try:
            await message.reply(f"⭐️ <b>تم تأكيد الدفع!</b>\n\n{post_msg}", parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Failed to send post payment msg: {e}")

# --- Group Events ---
@dp.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=IS_NOT_MEMBER >> IS_MEMBER))
async def bot_added_to_group(event: ChatMemberUpdated):
    chat = event.chat
    if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                INSERT INTO groups (chat_id, title, chat_type, status, added_at, updated_at, added_by) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET status='active', title=?, updated_at=?, added_by=?
            """, (chat.id, chat.title, chat.type, 'active', datetime.now(), datetime.now(), event.from_user.id, chat.title, datetime.now(), event.from_user.id))
            await db.commit()
        logger.info(f"Bot added to group {chat.title} ({chat.id})")

@dp.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=IS_MEMBER >> IS_NOT_MEMBER))
async def bot_removed_from_group(event: ChatMemberUpdated):
    chat = event.chat
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE groups SET status='inactive', updated_at=? WHERE chat_id=?", (datetime.now(), chat.id))
        await db.commit()
    logger.info(f"Bot removed from group {chat.title} ({chat.id})")

@dp.message(F.new_chat_members)
async def new_chat_member_handler(message: types.Message):
    bot_info = await bot.get_me()
    
    has_real_users = False
    new_member = None
    for member in message.new_chat_members:
        if member.id != bot_info.id:
            has_real_users = True
            new_member = member
            
    if not has_real_users or not new_member:
        return

    await trigger_group_promo(message, new_member)

# --- Admin Panel ---
def get_admin_keyboard(promo_enabled: str, user_id: int) -> InlineKeyboardMarkup:
    toggle_text = "⏸️ إيقاف الترويج" if promo_enabled == "true" else "▶️ تشغيل الترويج"
    
    keyboard = [
        [InlineKeyboardButton(text="📢 إعداد الترويج", callback_data="admin_promo_settings")],
        [InlineKeyboardButton(text="👥 المجموعات", callback_data="admin_groups"),
         InlineKeyboardButton(text="📊 الإحصائيات", callback_data="admin_stats")],
        [InlineKeyboardButton(text="⚙️ الإعدادات", callback_data="admin_settings")],
        [InlineKeyboardButton(text="📣 ساحر الإذاعة (جديد ⭐️)", callback_data="admin_broadcast_menu")],
        [InlineKeyboardButton(text="🎯 الحملات الترويجية", callback_data="cmp_menu")],
        [InlineKeyboardButton(text=toggle_text, callback_data="admin_toggle_promo")]
    ]
    
    if user_id == ADMIN_ID:
        keyboard.insert(4, [InlineKeyboardButton(text="👑 إدارة المشرفين", callback_data="admin_manage_admins")])
        
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
        
    await state.clear()
    promo_enabled = await get_setting("promo_enabled")
    text = "━━━━━━━━━━━━━━\n⚙️ <b>لوحة التحكم</b>\n━━━━━━━━━━━━━━"
    await message.answer(text, reply_markup=get_admin_keyboard(promo_enabled, message.from_user.id), parse_mode=ParseMode.HTML)

@dp.callback_query(F.data == "admin_main")
async def cb_admin_main(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.clear()
    promo_enabled = await get_setting("promo_enabled")
    text = "━━━━━━━━━━━━━━\n⚙️ <b>لوحة التحكم</b>\n━━━━━━━━━━━━━━"
    await callback.message.edit_text(text, reply_markup=get_admin_keyboard(promo_enabled, callback.from_user.id), parse_mode=ParseMode.HTML)
    await callback.answer()

@dp.callback_query(F.data == "admin_toggle_promo")
async def cb_admin_toggle_promo(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    current = await get_setting("promo_enabled")
    new_val = "false" if current == "true" else "true"
    await set_setting("promo_enabled", new_val)
    
    await callback.message.edit_reply_markup(reply_markup=get_admin_keyboard(new_val, callback.from_user.id))
    status_text = "تم تشغيل الترويج" if new_val == "true" else "تم إيقاف الترويج"
    await callback.answer(status_text)

# --- Promo Settings ---
@dp.callback_query(F.data == "admin_promo_settings")
async def cb_admin_promo_settings(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.clear()
    show_bot_btn = await get_setting("show_add_bot_button")
    btn_text = "🤖 إخفاء زر البوت" if show_bot_btn == "true" else "🤖 إظهار زر البوت"
    
    is_vip = await get_setting("promo_is_vip") == "true"
    stars = await get_setting("promo_stars") or "50"
    vip_text = f"💎 الإعلان: مدفوع ({stars}⭐️)" if is_vip else "🟢 الإعلان: مجاني"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 تعديل النص", callback_data="admin_edit_text"),
         InlineKeyboardButton(text="🖼️ تعديل الوسائط", callback_data="admin_edit_media")],
        [InlineKeyboardButton(text="🔗 تعديل الرابط / الزر", callback_data="admin_edit_button"),
         InlineKeyboardButton(text=btn_text, callback_data="admin_toggle_bot_btn")],
        [InlineKeyboardButton(text=vip_text, callback_data="admin_toggle_promo_vip")],
        [InlineKeyboardButton(text="💬 رسالة ما بعد الدفع", callback_data="admin_edit_post_payment_msg")],
        [InlineKeyboardButton(text="👁 معاينة الإعلان", callback_data="admin_preview_promo")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_main")]
    ])
    text = (
        "📢 <b>إعداد الترويج (للمجموعات)</b>\n\n"
        "يمكنك استخدام <code>{user}</code> في النص ليتم استبدالها تلقائياً بـ 'منشن' للعضو الجديد.\n\n"
        "اختر ما تريد تعديله:"
    )
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    except TelegramAPIError:
        pass
    await callback.answer()

@dp.callback_query(F.data == "admin_toggle_promo_vip")
async def cb_admin_toggle_promo_vip(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    is_vip = await get_setting("promo_is_vip") == "true"
    if is_vip:
        await set_setting("promo_is_vip", "false")
        await cb_admin_promo_settings(callback, state)
    else:
        await callback.message.answer("⭐️ أرسل عدد نجوم تيليجرام المطلوبة لهذا الإعلان (مثلاً 50):\nلإلغاء الأمر أرسل /cancel")
        await state.set_state(AdminEdit.waiting_for_promo_stars)
        await callback.answer()

@dp.message(AdminEdit.waiting_for_promo_stars)
async def process_promo_stars(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
    if not message.text.isdigit():
        return await message.answer("❌ يرجى إرسال أرقام فقط.")
        
    await set_setting("promo_stars", message.text)
    await set_setting("promo_is_vip", "true")
    await message.answer(f"✅ تم تحويل الإعلان إلى مدفوع بقيمة {message.text} ⭐️")
    await state.clear()

@dp.callback_query(F.data == "admin_edit_post_payment_msg")
async def cb_admin_edit_post_payment_msg(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    await callback.message.answer(
        "💬 أرسل الآن رسالة تأكيد الدفع (التي سيستلمها المستخدم بعد دفع النجوم):\n(يمكنك وضع روابط أو نصوص)\n"
        "ملاحظة: تليجرام يفتح الصور المدفوعة تلقائياً ولا يرسل إشعاراً للبوت بذلك، لذلك هذه الرسالة ستعمل بشكل أساسي مع (الإعلانات النصية المدفوعة الفواتير).\n"
        "لإلغاء الأمر أرسل /cancel"
    )
    await state.set_state(AdminEdit.waiting_for_post_payment_msg)
    await callback.answer()

@dp.message(AdminEdit.waiting_for_post_payment_msg)
async def process_post_payment_msg(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
    await set_setting("promo_post_payment_msg", message.html_text or message.text)
    await message.answer("✅ تم حفظ رسالة ما بعد الدفع.")
    await state.clear()

@dp.callback_query(F.data == "admin_toggle_bot_btn")
async def cb_admin_toggle_bot_btn(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    current = await get_setting("show_add_bot_button")
    new_val = "false" if current == "true" else "true"
    await set_setting("show_add_bot_button", new_val)
    await callback.answer("✅ تم التحديث")
    await cb_admin_promo_settings(callback, state)

@dp.callback_query(F.data == "admin_preview_promo")
async def cb_admin_preview_promo(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    
    promo_text = await get_setting("promo_text")
    promo_url = await get_setting("promo_url")
    promo_button_text = await get_setting("promo_button_text")
    promo_media_id = await get_setting("promo_media_id")
    promo_media_type = await get_setting("promo_media_type")
    show_bot_btn = await get_setting("show_add_bot_button")
    is_vip = await get_setting("promo_is_vip") == "true"
    stars = int(await get_setting("promo_stars") or 50)
    
    bot_info = await bot.get_me()
    
    user_name = callback.from_user.first_name.replace('<', '&lt;').replace('>', '&gt;')
    mention = f"<a href='tg://user?id={callback.from_user.id}'>{user_name}</a>"
    promo_text_formatted = promo_text.replace("{user}", mention)
    
    keyboard = build_promo_keyboard(promo_url, promo_button_text, bot_info.username or BOT_USERNAME, show_bot_btn)
    
    try:
        if is_vip:
            if promo_media_id:
                media_payload = [InputPaidMediaPhoto(media=promo_media_id)] if promo_media_type == 'photo' else [InputPaidMediaVideo(media=promo_media_id)]
                await bot.send_paid_media(chat_id=callback.from_user.id, star_count=stars, media=media_payload, caption=f"👁 معاينة:\n\n{promo_text_formatted}", parse_mode=ParseMode.HTML)
            else:
                text_msg = await callback.message.answer(f"👁 معاينة:\n\n{promo_text_formatted}", reply_markup=keyboard, parse_mode=ParseMode.HTML)
                prices = [types.LabeledPrice(label="فتح المحتوى السري", amount=stars)]
                await bot.send_invoice(
                    chat_id=callback.from_user.id,
                    title="محتوى مدفوع (VIP)",
                    description="قم بدفع النجوم لاستلام رسالة ما بعد الدفع فوراً.",
                    payload="paid_promo",
                    provider_token="", 
                    currency="XTR",
                    prices=prices,
                    reply_to_message_id=text_msg.message_id
                )
        else:
            if promo_media_id and promo_media_type == "photo":
                await callback.message.answer_photo(photo=promo_media_id, caption=f"👁 <b>معاينة:</b>\n\n{promo_text_formatted}", reply_markup=keyboard, parse_mode=ParseMode.HTML)
            elif promo_media_id and promo_media_type == "video":
                await callback.message.answer_video(video=promo_media_id, caption=f"👁 <b>معاينة:</b>\n\n{promo_text_formatted}", reply_markup=keyboard, parse_mode=ParseMode.HTML)
            else:
                await callback.message.answer(f"👁 <b>معاينة:</b>\n\n{promo_text_formatted}", reply_markup=keyboard, parse_mode=ParseMode.HTML)
    except Exception as e:
        await callback.message.answer(f"❌ حدث خطأ في المعاينة. تأكد من صحة الإعدادات.\nالخطأ: {e}")
    await callback.answer()

@dp.callback_query(F.data == "admin_edit_text")
async def cb_admin_edit_text(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.answer("أرسل الآن نص الإعلان الجديد:\n(تذكر يمكنك استخدام <code>{user}</code> للمنشن)\nلإلغاء الأمر أرسل /cancel", parse_mode=ParseMode.HTML)
    await state.set_state(AdminEdit.waiting_for_promo_text)
    await callback.answer()

@dp.message(AdminEdit.waiting_for_promo_text)
async def process_promo_text(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("تم الإلغاء.")
        await state.clear()
        return
    await set_setting("promo_text", message.text)
    await message.answer("✅ تم تحديث نص الإعلان بنجاح.")
    await state.clear()
    
@dp.callback_query(F.data == "admin_edit_media")
async def cb_admin_edit_media(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    await callback.message.answer("أرسل الآن (صورة أو فيديو) ليتم إرفاقه مع الإعلان.\nلحذف الوسائط والاكتفاء بالنص أرسل /clear\nلإلغاء الأمر أرسل /cancel")
    await state.set_state(AdminEdit.waiting_for_media)
    await callback.answer()

@dp.message(AdminEdit.waiting_for_media, F.photo | F.video | F.text)
async def process_promo_media(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("تم الإلغاء.")
        await state.clear()
        return
    elif message.text == '/clear':
        await set_setting("promo_media_id", "")
        await set_setting("promo_media_type", "")
        await message.answer("✅ تم حذف الوسائط. سيتم إرسال الإعلان كنص فقط.")
        await state.clear()
        return
        
    if message.photo:
        await set_setting("promo_media_id", message.photo[-1].file_id)
        await set_setting("promo_media_type", "photo")
        await message.answer("✅ تم حفظ الصورة بنجاح.")
    elif message.video:
        await set_setting("promo_media_id", message.video.file_id)
        await set_setting("promo_media_type", "video")
        await message.answer("✅ تم حفظ الفيديو بنجاح.")
    else:
        await message.answer("❌ أرسل صورة أو فيديو، أو /clear، أو /cancel.")
        return
    await state.clear()

@dp.callback_query(F.data == "admin_edit_url")
async def cb_admin_edit_url(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.answer("أرسل الآن الرابط الترويجي الجديد (يجب أن يبدأ بـ http أو https):\nلإلغاء الأمر أرسل /cancel")
    await state.set_state(AdminEdit.waiting_for_promo_url)
    await callback.answer()

@dp.message(AdminEdit.waiting_for_promo_url)
async def process_promo_url(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("تم الإلغاء.")
        await state.clear()
        return
    if not message.text.startswith(("http://", "https://")):
        await message.answer("❌ الرابط غير صحيح. يجب أن يبدأ بـ http:// أو https://\nحاول مجدداً أو أرسل /cancel")
        return
    await set_setting("promo_url", message.text)
    await message.answer("✅ تم تحديث الرابط بنجاح.")
    await state.clear()

@dp.callback_query(F.data == "admin_edit_button")
async def cb_admin_edit_button(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.answer("أرسل الآن نص الزر الجديد:\nلإلغاء الأمر أرسل /cancel")
    await state.set_state(AdminEdit.waiting_for_promo_button)
    await callback.answer()

@dp.message(AdminEdit.waiting_for_promo_button)
async def process_promo_button(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("تم الإلغاء.")
        await state.clear()
        return
    await set_setting("promo_button_text", message.text)
    await message.answer("✅ تم تحديث نص الزر بنجاح.")
    await state.clear()

# --- Broadcast Wizard (VIP & Auto-delete) ---
@dp.callback_query(F.data == "admin_broadcast_menu")
async def cb_admin_broadcast_menu(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    await state.clear()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 للإدارة والمستخدمين (في الخاص)", callback_data="start_bw_users")],
        [InlineKeyboardButton(text="🌐 للمجموعات فقط", callback_data="start_bw_groups")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_main")]
    ])
    await callback.message.edit_text("📣 <b>ساحر الإذاعة الجديد:</b>\n\nاختر الوجهة التي تريد بدء الإذاعة إليها:", reply_markup=keyboard, parse_mode=ParseMode.HTML)
    await callback.answer()

@dp.callback_query(F.data.startswith("start_bw_"))
async def cb_start_bw(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    target = callback.data.split("_")[2]
    await state.update_data(target=target)
    await callback.message.answer("📝 <b>الخطوة 1:</b> أرسل النص الخاص بالإذاعة.\n(يمكنك إضافة روابط أو تنسيقات HTML)\nلإلغاء الأمر أرسل /cancel", parse_mode=ParseMode.HTML)
    await state.set_state(BroadcastWizard.text)
    await callback.answer()

@dp.message(BroadcastWizard.text)
async def process_bw_text(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
        
    await state.update_data(text=message.html_text or message.text)
    await message.answer("🖼 <b>الخطوة 2:</b> أرسل صورة أو فيديو لإرفاقه مع الإذاعة.\nإذا أردت إرسال الإذاعة كنص فقط دون وسائط، أرسل /skip\nلإلغاء الأمر أرسل /cancel", parse_mode=ParseMode.HTML)
    await state.set_state(BroadcastWizard.media)

@dp.message(BroadcastWizard.media, F.photo | F.video | F.text)
async def process_bw_media(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
        
    if message.text == '/skip':
        await state.update_data(media_id=None, media_type=None)
        await ask_duration(message, state)
        return
        
    if message.photo:
        await state.update_data(media_id=message.photo[-1].file_id, media_type="photo")
    elif message.video:
        await state.update_data(media_id=message.video.file_id, media_type="video")
    else:
        await message.answer("❌ يجب إرسال صورة أو فيديو، أو /skip، أو /cancel.")
        return
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 مجانية (مفتوحة)", callback_data="media_free")],
        [InlineKeyboardButton(text="⭐️ مدفوعة (VIP - بنجوم تيليجرام)", callback_data="media_vip")]
    ])
    await message.answer("💎 <b>الخطوة 3:</b> هل تريد أن يكون هذا المحتوى مجانياً أم مدفوعاً (مظلل يفتح بالنجوم)؟", reply_markup=kb, parse_mode=ParseMode.HTML)
    await state.set_state(BroadcastWizard.media_type_vip)

@dp.callback_query(BroadcastWizard.media_type_vip)
async def cb_bw_media_type(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    if callback.data == "media_free":
        await state.update_data(is_vip=False, stars=0)
        await ask_duration(callback.message, state)
    elif callback.data == "media_vip":
        await state.update_data(is_vip=True)
        await callback.message.answer("⭐️ كم عدد النجوم المطلوبة لفتح المحتوى؟ (أرسل رقماً بين 1 و 2500):")
        await state.set_state(BroadcastWizard.stars)
    await callback.answer()

@dp.message(BroadcastWizard.stars)
async def process_bw_stars(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
        
    if not message.text.isdigit():
        return await message.answer("❌ يرجى إرسال أرقام فقط (مثلاً 50).")
        
    stars = int(message.text)
    if stars < 1 or stars > 2500:
        return await message.answer("❌ يجب أن يكون العدد بين 1 و 2500.")
        
    await state.update_data(stars=stars)
    await ask_duration(message, state)
    
async def ask_duration(message: types.Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="لا تحذف أبداً", callback_data="duration_0")],
        [InlineKeyboardButton(text="بعد 10 دقائق", callback_data="duration_10"),
         InlineKeyboardButton(text="بعد 30 دقيقة", callback_data="duration_30")],
        [InlineKeyboardButton(text="بعد 1 ساعة", callback_data="duration_60"),
         InlineKeyboardButton(text="بعد 6 ساعات", callback_data="duration_360")],
        [InlineKeyboardButton(text="بعد 24 ساعة", callback_data="duration_1440")]
    ])
    await message.answer("⏳ <b>الخطوة ما قبل الأخيرة:</b> متى تريد حذف الإذاعة تلقائياً؟", reply_markup=kb, parse_mode=ParseMode.HTML)
    await state.set_state(BroadcastWizard.duration)

@dp.callback_query(BroadcastWizard.duration)
async def cb_bw_duration(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    mins = int(callback.data.split("_")[1])
    await state.update_data(duration_mins=mins)
    
    data = await state.get_data()
    target_ar = "المستخدمين في الخاص" if data['target'] == 'users' else "المجموعات"
    dur_ar = "لا تُحذف" if mins == 0 else f"تُحذف بعد {mins} دقيقة"
    vip_ar = f"مدفوعة بـ {data.get('stars', 0)} نجمة ⭐️" if data.get('is_vip') else "مجانية"
    
    summary = (
        f"📋 <b>ملخص الإذاعة النهائي:</b>\n\n"
        f"👥 <b>الوجهة:</b> {target_ar}\n"
        f"🖼 <b>الوسائط:</b> {'نعم' if data.get('media_id') else 'لا'} ({vip_ar})\n"
        f"⏳ <b>التدمير الذاتي:</b> {dur_ar}\n\n"
        f"هل أنت متأكد من الإرسال الآن؟"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ إرسال الآن", callback_data="confirm_send")],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="cancel_wizard")]
    ])
    await callback.message.answer(summary, reply_markup=kb, parse_mode=ParseMode.HTML)
    await state.set_state(BroadcastWizard.confirm)
    await callback.answer()

@dp.callback_query(BroadcastWizard.confirm)
async def cb_bw_confirm(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    if callback.data == "cancel_wizard":
        await callback.message.answer("❌ تم إلغاء الإذاعة.")
        await state.clear()
        return
        
    data = await state.get_data()
    await state.clear()
    
    status_msg = await callback.message.answer("🚀 جاري الإرسال، يرجى الانتظار (قد يستغرق بعض الوقت لتجنب الحظر)...")
    asyncio.create_task(execute_broadcast(data, status_msg))
    await callback.answer()
    
async def execute_broadcast(data: dict, status_msg: types.Message):
    target = data['target']
    if target == 'users':
        query = "SELECT telegram_id FROM users"
    else:
        query = "SELECT chat_id FROM groups WHERE status='active'"
        
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(query) as cursor:
            targets = await cursor.fetchall()
            
    success = 0
    dur = data.get('duration_mins', 0)
    delete_at = datetime.now() + timedelta(minutes=dur) if dur > 0 else None
    
    for t in targets:
        chat_id = t[0]
        try:
            sent_msg = None
            if data.get('is_vip') and data.get('media_id'):
                if data['media_type'] == 'photo':
                    media_payload = [InputPaidMediaPhoto(media=data['media_id'])]
                else:
                    media_payload = [InputPaidMediaVideo(media=data['media_id'])]
                    
                sent_msg = await bot.send_paid_media(
                    chat_id=chat_id,
                    star_count=data['stars'],
                    media=media_payload,
                    caption=data['text'],
                    parse_mode=ParseMode.HTML
                )
            elif data.get('media_id'):
                if data['media_type'] == 'photo':
                    sent_msg = await bot.send_photo(chat_id, photo=data['media_id'], caption=data['text'], parse_mode=ParseMode.HTML)
                else:
                    sent_msg = await bot.send_video(chat_id, video=data['media_id'], caption=data['text'], parse_mode=ParseMode.HTML)
            else:
                sent_msg = await bot.send_message(chat_id, data['text'], parse_mode=ParseMode.HTML)
                
            if sent_msg and delete_at:
                async with aiosqlite.connect(DB_NAME) as db2:
                    await db2.execute("INSERT INTO broadcast_messages (chat_id, message_id, delete_at) VALUES (?, ?, ?)",
                                      (chat_id, sent_msg.message_id, delete_at))
                    await db2.commit()
                    
            success += 1
        except TelegramForbiddenError:
            if target == 'groups':
                async with aiosqlite.connect(DB_NAME) as db2:
                    await db2.execute("UPDATE groups SET status='inactive' WHERE chat_id=?", (chat_id,))
                    await db2.commit()
        except Exception as e:
            pass
        
        await asyncio.sleep(0.05) # Prevent flood limit
        
    await status_msg.edit_text(f"✅ اكتملت المهمة! تمت الإذاعة بنجاح إلى {success} جهة.")


# --- Settings ---
@dp.callback_query(F.data == "admin_settings")
async def cb_admin_settings(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.clear()
    cooldown = await get_setting("cooldown")
    auto_del = await get_setting("auto_delete")
    auto_del_text = "🧹 إيقاف الحذف التلقائي" if auto_del == "true" else "🧹 تشغيل الحذف التلقائي"
    
    cooldown_display = "بدون انتظار (0 ثانية)" if cooldown == "0" else f"{cooldown} ثانية"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 إعدادات رسالة الترحيب (الخاص)", callback_data="admin_start_settings")],
        [InlineKeyboardButton(text="⏱ تعديل مدة الانتظار (Cooldown)", callback_data="admin_edit_cooldown")],
        [InlineKeyboardButton(text=auto_del_text, callback_data="admin_toggle_autodelete")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_main")]
    ])
    text = (
        "⚙️ <b>الإعدادات:</b>\n\n"
        f"⏱ مدة الانتظار الحالية: {cooldown_display}\n"
        f"🧹 الحذف التلقائي للإعلان القديم: {'مفعل ✅' if auto_del == 'true' else 'معطل ❌'}"
    )
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    await callback.answer()

# --- Start Message Settings ---
@dp.callback_query(F.data == "admin_start_settings")
async def cb_admin_start_settings(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 تعديل نص رسالة الترحيب", callback_data="admin_edit_start_msg")],
        [InlineKeyboardButton(text="🔘 تعديل اسم الزر الإضافي", callback_data="admin_edit_btn2_name")],
        [InlineKeyboardButton(text="🔗 جعله رابط (URL)", callback_data="admin_edit_btn2_url"),
         InlineKeyboardButton(text="💬 جعله رسالة نصية", callback_data="admin_edit_btn2_text")],
        [InlineKeyboardButton(text="👁 معاينة رسالة الترحيب", callback_data="admin_preview_start")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_settings")]
    ])
    await callback.message.edit_text(
        "⚙️ <b>إعدادات رسالة الترحيب (الخاص):</b>\n\nتتحكم هذه القائمة بالرسالة والأزرار التي تظهر للأعضاء عند بدء المحادثة مع البوت في الخاص.\nاختر ما تريد تعديله:", 
        reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()

@dp.callback_query(F.data == "admin_preview_start")
async def cb_admin_preview_start(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    bot_info = await bot.get_me()
    text, kb = await get_start_message_data(bot_info.username or BOT_USERNAME)
    await callback.message.answer(f"👁 <b>معاينة الترحيب:</b>\n\n{text}", reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()

@dp.callback_query(F.data == "admin_edit_start_msg")
async def cb_admin_edit_start_msg(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    await callback.message.answer("أرسل الآن رسالة الترحيب الجديدة التي ستظهر للأعضاء في الخاص عند إرسال /start:\n(يمكنك استخدام HTML)\nلإلغاء الأمر أرسل /cancel")
    await state.set_state(AdminEdit.waiting_for_start_msg)
    await callback.answer()

@dp.message(AdminEdit.waiting_for_start_msg)
async def process_start_msg(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("تم الإلغاء.")
        await state.clear()
        return
    await set_setting("start_message", message.text)
    await message.answer("✅ تم تحديث رسالة الترحيب بنجاح.")
    await state.clear()

@dp.callback_query(F.data == "admin_edit_btn2_name")
async def cb_admin_edit_btn2_name(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    await callback.message.answer("أرسل الآن الاسم الجديد للزر الإضافي (مثال: اشترك في الباقة).\nلإخفاء الزر تماماً أرسل /hide\nلإلغاء الأمر أرسل /cancel")
    await state.set_state(AdminEdit.waiting_for_start_btn2_name)
    await callback.answer()

@dp.message(AdminEdit.waiting_for_start_btn2_name)
async def process_start_btn2_name(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("تم الإلغاء.")
        await state.clear()
        return
    if message.text == '/hide':
        await set_setting("start_btn2_name", "")
        await message.answer("✅ تم إخفاء الزر الإضافي.")
    else:
        await set_setting("start_btn2_name", message.text)
        await message.answer("✅ تم تحديث اسم الزر الإضافي.")
    await state.clear()

@dp.callback_query(F.data == "admin_edit_btn2_url")
async def cb_admin_edit_btn2_url(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    await callback.message.answer("أرسل الآن الرابط (يجب أن يبدأ بـ http أو https أو tg://):\nلإلغاء الأمر أرسل /cancel")
    await state.set_state(AdminEdit.waiting_for_start_btn2_url)
    await callback.answer()

@dp.message(AdminEdit.waiting_for_start_btn2_url)
async def process_start_btn2_url(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("تم الإلغاء.")
        await state.clear()
        return
    if not message.text.startswith(("http://", "https://", "tg://")):
        await message.answer("❌ عذراً، الرابط غير صحيح. يجب أن يبدأ بـ http أو https أو tg://")
        return
    await set_setting("start_btn2_type", "url")
    await set_setting("start_btn2_content", message.text)
    await message.answer("✅ تم تحويل الزر الإضافي إلى رابط بنجاح.")
    await state.clear()

@dp.callback_query(F.data == "admin_edit_btn2_text")
async def cb_admin_edit_btn2_text(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    await callback.message.answer("أرسل الآن الرسالة النصية التي تريد ظهورها عند ضغط المستخدم على الزر:\nلإلغاء الأمر أرسل /cancel")
    await state.set_state(AdminEdit.waiting_for_start_btn2_text)
    await callback.answer()

@dp.message(AdminEdit.waiting_for_start_btn2_text)
async def process_start_btn2_text(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("تم الإلغاء.")
        await state.clear()
        return
    await set_setting("start_btn2_type", "text")
    await set_setting("start_btn2_content", message.text)
    await message.answer("✅ تم تحويل الزر الإضافي إلى رسالة نصية بنجاح.")
    await state.clear()

@dp.callback_query(F.data == "admin_toggle_autodelete")
async def cb_admin_toggle_autodelete(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    current = await get_setting("auto_delete")
    new_val = "false" if current == "true" else "true"
    await set_setting("auto_delete", new_val)
    await callback.answer("✅ تم التحديث")
    await cb_admin_settings(callback, state)

@dp.callback_query(F.data == "admin_edit_cooldown")
async def cb_admin_edit_cooldown(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡️ مع كل انضمام (0 ثانية)", callback_data="set_cooldown_0")],
        [InlineKeyboardButton(text="30 ثانية", callback_data="set_cooldown_30"),
         InlineKeyboardButton(text="60 ثانية", callback_data="set_cooldown_60")],
        [InlineKeyboardButton(text="120 ثانية", callback_data="set_cooldown_120"),
         InlineKeyboardButton(text="300 ثانية", callback_data="set_cooldown_300")],
        [InlineKeyboardButton(text="إدخال قيمة مخصصة", callback_data="set_cooldown_custom")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_settings")]
    ])
    await callback.message.edit_text("⏱ اختر مدة الانتظار بين كل إعلان وآخر في نفس المجموعة:\n\n*ملاحظة: اختيار '0 ثانية' يعني إرسال الإعلان مع كل عضو جديد ينضم دون انتظار.", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("set_cooldown_"))
async def cb_set_cooldown(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    val = callback.data.split("_")[2]
    if val == "custom":
        await callback.message.answer("أرسل قيمة مدة الانتظار بالثواني (أرقام فقط):\nلإلغاء الأمر أرسل /cancel")
        await state.set_state(AdminEdit.waiting_for_cooldown)
    else:
        await set_setting("cooldown", val)
        await callback.answer(f"✅ تم ضبط مدة الانتظار إلى {val} ثانية", show_alert=True)
        await cb_admin_settings(callback, state)
    await callback.answer()

@dp.message(AdminEdit.waiting_for_cooldown)
async def process_cooldown(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("تم الإلغاء.")
        await state.clear()
        return
    if not message.text.isdigit():
        await message.answer("❌ يرجى إرسال أرقام فقط.\nحاول مجدداً أو أرسل /cancel")
        return
    await set_setting("cooldown", message.text)
    await message.answer(f"✅ تم تحديث مدة الانتظار إلى {message.text} ثانية.")
    await state.clear()

# --- Stats Handler ---
@dp.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            total_users = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM groups WHERE status='active'") as cursor:
            active_groups = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM groups") as cursor:
            total_groups = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM events WHERE event_type='promo_sent'") as cursor:
            total_promos = (await cursor.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM events WHERE event_type='promo_sent' AND created_at >= datetime('now', '-1 day')"
        ) as cursor:
            promos_today = (await cursor.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-1 day')"
        ) as cursor:
            users_today = (await cursor.fetchone())[0]

    text = (
        "📊 <b>الإحصائيات العامة</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        f"👤 <b>إجمالي المستخدمين:</b> {total_users}\n"
        f"👤 <b>مستخدمون جدد (آخر 24س):</b> {users_today}\n\n"
        f"👥 <b>إجمالي المجموعات:</b> {total_groups}\n"
        f"✅ <b>المجموعات النشطة:</b> {active_groups}\n\n"
        f"📢 <b>إجمالي الإعلانات المرسلة:</b> {total_promos}\n"
        f"📢 <b>إعلانات اليوم (آخر 24س):</b> {promos_today}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_main")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()

# --- Groups Handler ---
@dp.callback_query(F.data == "admin_groups")
async def cb_admin_groups(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT chat_id, title, status, added_at FROM groups ORDER BY added_at DESC LIMIT 20"
        ) as cursor:
            groups = await cursor.fetchall()

    if not groups:
        text = "👥 <b>المجموعات</b>\n━━━━━━━━━━━━━━\n\nلا توجد مجموعات مسجلة بعد."
    else:
        lines = ["👥 <b>قائمة المجموعات (آخر 20)</b>\n━━━━━━━━━━━━━━\n"]
        for chat_id, title, status, added_at in groups:
            icon = "✅" if status == "active" else "❌"
            date_str = added_at[:10] if added_at else "غير معروف"
            lines.append(f"{icon} <b>{title or 'بدون اسم'}</b>\n   🆔 <code>{chat_id}</code> | 📅 {date_str}")
        text = "\n\n".join(lines)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_main")]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except TelegramAPIError:
        # Message too long, send summary instead
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT COUNT(*) FROM groups WHERE status='active'") as cursor:
                active = (await cursor.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM groups") as cursor:
                total = (await cursor.fetchone())[0]
        await callback.message.edit_text(
            f"👥 <b>المجموعات</b>\n━━━━━━━━━━━━━━\n\n"
            f"✅ نشطة: {active}\n❌ غير نشطة: {total - active}\n📊 الإجمالي: {total}",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )
    await callback.answer()

# --- Manage Admins Handler ---
@dp.callback_query(F.data == "admin_manage_admins")
async def cb_admin_manage_admins(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔️ هذا القسم للمالك الرئيسي فقط.", show_alert=True)
        return
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT telegram_id, added_at FROM admins") as cursor:
            admins = await cursor.fetchall()

    lines = ["👑 <b>قائمة المشرفين</b>\n━━━━━━━━━━━━━━\n"]
    if admins:
        for admin_id, added_at in admins:
            date_str = added_at[:10] if added_at else "غير معروف"
            lines.append(f"• <code>{admin_id}</code> | 📅 {date_str}")
    else:
        lines.append("لا يوجد مشرفون مضافون حتى الآن.")

    text = "\n".join(lines)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ إضافة مشرف", callback_data="admin_add_admin"),
         InlineKeyboardButton(text="➖ حذف مشرف", callback_data="admin_remove_admin")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_main")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()

@dp.callback_query(F.data == "admin_add_admin")
async def cb_admin_add_admin(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔️ هذا القسم للمالك الرئيسي فقط.", show_alert=True)
        return
    await callback.message.answer("أرسل الآن <b>ID تيليجرام</b> للمشرف الجديد (أرقام فقط):\nلإلغاء الأمر أرسل /cancel", parse_mode=ParseMode.HTML)
    await state.set_state(AdminEdit.waiting_for_admin_id)
    await state.update_data(admin_action="add")
    await callback.answer()

@dp.callback_query(F.data == "admin_remove_admin")
async def cb_admin_remove_admin(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔️ هذا القسم للمالك الرئيسي فقط.", show_alert=True)
        return
    await callback.message.answer("أرسل الآن <b>ID تيليجرام</b> للمشرف الذي تريد حذفه:\nلإلغاء الأمر أرسل /cancel", parse_mode=ParseMode.HTML)
    await state.set_state(AdminEdit.waiting_for_admin_id)
    await state.update_data(admin_action="remove")
    await callback.answer()

@dp.message(AdminEdit.waiting_for_admin_id)
async def process_admin_id(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("❌ تم الإلغاء.")
        await state.clear()
        return
    if not message.text.isdigit():
        await message.answer("❌ يرجى إرسال أرقام فقط (ID تيليجرام).")
        return
    data = await state.get_data()
    action = data.get("admin_action", "add")
    target_id = int(message.text)
    if target_id == ADMIN_ID:
        await message.answer("⛔️ لا يمكنك تعديل صلاحيات المالك الرئيسي.")
        await state.clear()
        return
    async with aiosqlite.connect(DB_NAME) as db:
        if action == "add":
            await db.execute(
                "INSERT OR IGNORE INTO admins (telegram_id, added_at) VALUES (?, ?)",
                (target_id, datetime.now())
            )
            await db.commit()
            await message.answer(f"✅ تمت إضافة <code>{target_id}</code> كمشرف بنجاح.", parse_mode=ParseMode.HTML)
        else:
            await db.execute("DELETE FROM admins WHERE telegram_id = ?", (target_id,))
            await db.commit()
            await message.answer(f"✅ تمت إزالة <code>{target_id}</code> من المشرفين.", parse_mode=ParseMode.HTML)
    await state.clear()

# ========================================
# === CAMPAIGN UNLOCK SYSTEM ===
# ========================================

# Verify cooldown: {(user_id, campaign_id): timestamp}
_campaign_verify_cooldown = {}
VERIFY_COOLDOWN_SECONDS = 10

# --- Campaign Helpers ---

async def get_campaign(campaign_id: int):
    """Get campaign by ID as a dict."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            cols = [desc[0] for desc in cursor.description]
            return dict(zip(cols, row))

async def show_campaign_progress(target, campaign_id: int, user_id: int):
    """Show campaign progress. 'target' can be Message or CallbackQuery."""
    is_callback = isinstance(target, types.CallbackQuery)
    msg = target.message if is_callback else target
    
    campaign = await get_campaign(campaign_id)
    if not campaign or campaign['status'] == 'deleted':
        text = "❌ هذه الحملة غير متوفرة."
        if is_callback:
            try:
                await msg.edit_text(text)
            except TelegramAPIError:
                await msg.answer(text)
            await target.answer()
        else:
            await msg.answer(text)
        return
    
    # Get or create progress
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT verified_count, status FROM campaign_user_progress WHERE campaign_id=? AND user_id=?",
            (campaign_id, user_id)
        ) as cursor:
            row = await cursor.fetchone()
        
        if not row:
            await db.execute(
                "INSERT OR IGNORE INTO campaign_user_progress (campaign_id, user_id, verified_count, status, created_at, updated_at) VALUES (?, ?, 0, 'in_progress', ?, ?)",
                (campaign_id, user_id, datetime.now(), datetime.now())
            )
            await db.commit()
            verified_count, status = 0, 'in_progress'
        else:
            verified_count, status = row
    
    required = campaign['required_groups']
    await log_event(0, user_id, f"campaign_{campaign_id}_viewed")
    
    if status == 'unlocked':
        text = (
            f"🎉 <b>تم فتح العرض!</b>\n\n"
            f"📣 <b>{campaign['name']}</b>\n\n"
            f"✅ لقد أكملت الشرط بنجاح ({required}/{required} مجموعات).\n\n"
            f"اضغط الزر أدناه للحصول على العرض."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 الحصول على العرض", callback_data=f"camp_unlock_{campaign_id}")]
        ])
    elif campaign['status'] == 'paused' and verified_count == 0:
        text = "⏸ هذه الحملة متوقفة حالياً."
        kb = None
    else:
        bar_filled = min(verified_count, required)
        bar = "▓" * bar_filled + "░" * (required - bar_filled)
        bot_info = await bot.get_me()
        text = (
            f"🔒 <b>العرض مغلق</b>\n\n"
            f"📣 <b>{campaign['name']}</b>\n\n"
            f"للحصول على العرض يجب عليك إضافة البوت إلى <b>{required}</b> مجموعات.\n\n"
            f"📊 التقدم: <b>{verified_count}</b> / <b>{required}</b>\n"
            f"<code>{bar}</code>\n"
        )
        if 0 < verified_count < required:
            text += f"\n⏳ أكمل <b>{required - verified_count}</b> مجموعات أخرى."
        
        buttons = [
            [InlineKeyboardButton(text="➕ إضافة البوت إلى المجموعات", url=f"https://t.me/{bot_info.username}?startgroup=camp_{campaign_id}")],
            [InlineKeyboardButton(text="🔄 تحقق من الإضافة", callback_data=f"camp_verify_{campaign_id}")]
        ]
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    try:
        if is_callback:
            await msg.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
            await target.answer()
        else:
            await msg.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except TelegramAPIError:
        await msg.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        if is_callback:
            await target.answer()


# --- Campaign User Handlers ---

@dp.callback_query(F.data.startswith("camp_verify_"))
async def cb_camp_verify(callback: types.CallbackQuery):
    campaign_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    # Rate limit
    key = (user_id, campaign_id)
    now = time.time()
    if key in _campaign_verify_cooldown:
        elapsed = now - _campaign_verify_cooldown[key]
        if elapsed < VERIFY_COOLDOWN_SECONDS:
            remaining = int(VERIFY_COOLDOWN_SECONDS - elapsed)
            await callback.answer(f"⏳ يرجى الانتظار {remaining} ثوانٍ قبل التحقق مجدداً.", show_alert=True)
            return
    _campaign_verify_cooldown[key] = now
    
    campaign = await get_campaign(campaign_id)
    if not campaign or campaign['status'] == 'deleted':
        await callback.answer("❌ هذه الحملة غير متوفرة.", show_alert=True)
        return
    
    # Check if already unlocked
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT status FROM campaign_user_progress WHERE campaign_id=? AND user_id=?",
            (campaign_id, user_id)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0] == 'unlocked':
                await show_campaign_progress(callback, campaign_id, user_id)
                return
    
    await callback.answer("🔄 جاري التحقق من المجموعات...")
    
    required = campaign['required_groups']
    bot_info = await bot.get_me()
    bot_id = bot_info.id
    
    # Get groups this user added the bot to
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT chat_id, title FROM groups WHERE added_by = ? AND status = 'active'",
            (user_id,)
        ) as cursor:
            user_groups = await cursor.fetchall()
        
        # Already verified for this campaign
        async with db.execute(
            "SELECT chat_id FROM campaign_groups WHERE campaign_id = ? AND user_id = ? AND verified = 1",
            (campaign_id, user_id)
        ) as cursor:
            already_verified = {row[0] for row in await cursor.fetchall()}
    
    new_verified = 0
    for chat_id, title in user_groups:
        if chat_id in already_verified:
            continue
        if len(already_verified) + new_verified >= required:
            break
        
        try:
            member = await bot.get_chat_member(chat_id, bot_id)
            if member.status in ['member', 'administrator', 'creator']:
                async with aiosqlite.connect(DB_NAME) as db:
                    await db.execute(
                        "INSERT OR IGNORE INTO campaign_groups (campaign_id, user_id, chat_id, chat_title, verified, verified_at) VALUES (?, ?, ?, ?, 1, ?)",
                        (campaign_id, user_id, chat_id, title, datetime.now())
                    )
                    await db.commit()
                new_verified += 1
                await log_event(chat_id, user_id, f"campaign_{campaign_id}_group_verified")
        except (TelegramForbiddenError, TelegramAPIError):
            pass
        await asyncio.sleep(0.1)
    
    total_verified = len(already_verified) + new_verified
    is_complete = total_verified >= required
    new_status = 'unlocked' if is_complete else 'in_progress'
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """INSERT INTO campaign_user_progress (campaign_id, user_id, verified_count, status, created_at, updated_at) 
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(campaign_id, user_id) DO UPDATE SET verified_count=?, status=?, updated_at=?""",
            (campaign_id, user_id, total_verified, new_status, datetime.now(), datetime.now(),
             total_verified, new_status, datetime.now())
        )
        await db.commit()
    
    if is_complete:
        await log_event(0, user_id, f"campaign_{campaign_id}_unlocked")
    
    await show_campaign_progress(callback, campaign_id, user_id)


@dp.callback_query(F.data.startswith("camp_unlock_"))
async def cb_camp_unlock(callback: types.CallbackQuery):
    campaign_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    campaign = await get_campaign(campaign_id)
    if not campaign:
        await callback.answer("❌ الحملة غير موجودة.", show_alert=True)
        return
    
    # Verify unlocked status
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT status FROM campaign_user_progress WHERE campaign_id=? AND user_id=?",
            (campaign_id, user_id)
        ) as cursor:
            row = await cursor.fetchone()
            if not row or row[0] != 'unlocked':
                await callback.answer("❌ لم تكمل الشرط بعد.", show_alert=True)
                return
    
    await log_event(0, user_id, f"campaign_{campaign_id}_content_delivered")
    
    unlock_text = campaign['unlock_content'] or "🎁 تم فتح العرض!"
    try:
        if campaign.get('unlock_media_file_id'):
            if campaign['unlock_media_type'] == 'photo':
                await callback.message.answer_photo(
                    photo=campaign['unlock_media_file_id'],
                    caption=f"🔓 <b>محتوى العرض:</b>\n\n{unlock_text}",
                    parse_mode=ParseMode.HTML
                )
            elif campaign['unlock_media_type'] == 'video':
                await callback.message.answer_video(
                    video=campaign['unlock_media_file_id'],
                    caption=f"🔓 <b>محتوى العرض:</b>\n\n{unlock_text}",
                    parse_mode=ParseMode.HTML
                )
        else:
            await callback.message.answer(
                f"🔓 <b>محتوى العرض:</b>\n\n{unlock_text}",
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        logger.error(f"Failed to deliver campaign {campaign_id} content: {e}")
        await callback.message.answer("❌ حدث خطأ أثناء تسليم المحتوى. حاول لاحقاً.")
    
    await callback.answer()


# --- Campaign Admin Menu ---

@dp.callback_query(F.data == "cmp_menu")
async def cb_campaign_menu(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ إنشاء حملة جديدة", callback_data="cmp_new")],
        [InlineKeyboardButton(text="📋 الحملات النشطة", callback_data="cmp_list")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_main")]
    ])
    await callback.message.edit_text(
        "🎯 <b>الحملات الترويجية</b>\n━━━━━━━━━━━━━━\n\n"
        "أنشئ حملات ترويجية تشترط على المستخدمين إضافة البوت\n"
        "لعدد محدد من المجموعات للحصول على المحتوى.\n\n"
        "اختر إجراء:",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )
    await callback.answer()


# --- Campaign Creation Wizard ---

@dp.callback_query(F.data == "cmp_new")
async def cb_campaign_new(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.answer(
        "🎯 <b>إنشاء حملة جديدة</b>\n\n"
        "<b>الخطوة 1/7:</b> أرسل اسم الحملة.\n"
        "(مثال: عرض القناة الجديد)\n\n"
        "لإلغاء الأمر أرسل /cancel",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(CampaignWizard.name)
    await callback.answer()

@dp.message(CampaignWizard.name)
async def process_cw_name(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("❌ تم إلغاء إنشاء الحملة.")
        await state.clear()
        return
    await state.update_data(name=message.text)
    await message.answer(
        "📝 <b>الخطوة 2/7:</b> أرسل النص الترويجي للحملة.\n"
        "(هذا النص سيظهر في رسالة البث)\n"
        "(يمكنك استخدام HTML)\n\n"
        "لإلغاء الأمر أرسل /cancel",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(CampaignWizard.promo_text)

@dp.message(CampaignWizard.promo_text)
async def process_cw_promo_text(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("❌ تم إلغاء إنشاء الحملة.")
        await state.clear()
        return
    await state.update_data(promo_text=message.html_text or message.text)
    await message.answer(
        "🖼 <b>الخطوة 3/7:</b> أرسل صورة أو فيديو لإرفاقه مع الإعلان.\n"
        "إذا أردت بدون وسائط أرسل /skip\n\n"
        "لإلغاء الأمر أرسل /cancel",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(CampaignWizard.media)

@dp.message(CampaignWizard.media, F.photo | F.video | F.text)
async def process_cw_media(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("❌ تم إلغاء إنشاء الحملة.")
        await state.clear()
        return
    if message.text == '/skip':
        await state.update_data(media_type=None, media_file_id=None)
    elif message.photo:
        await state.update_data(media_type="photo", media_file_id=message.photo[-1].file_id)
    elif message.video:
        await state.update_data(media_type="video", media_file_id=message.video.file_id)
    else:
        await message.answer("❌ أرسل صورة أو فيديو، أو /skip، أو /cancel.")
        return
    
    await message.answer(
        "🔘 <b>الخطوة 4/7:</b> أرسل نص زر الحملة.\n"
        "(هذا الزر سيظهر في رسالة البث ويوجه المستخدم للحملة)\n"
        "(مثال: 🎁 الحصول على العرض)\n\n"
        "أرسل /skip لاستخدام النص الافتراضي\n"
        "لإلغاء الأمر أرسل /cancel",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(CampaignWizard.button_text)

@dp.message(CampaignWizard.button_text)
async def process_cw_button_text(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("❌ تم إلغاء إنشاء الحملة.")
        await state.clear()
        return
    if message.text == '/skip':
        await state.update_data(button_text="🎁 الحصول على العرض")
    else:
        await state.update_data(button_text=message.text)
    
    await message.answer(
        "🔢 <b>الخطوة 5/7:</b> كم مجموعة يجب على المستخدم إضافة البوت إليها؟\n"
        "(أرسل رقماً بين 1 و 50)\n\n"
        "لإلغاء الأمر أرسل /cancel",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(CampaignWizard.required_groups)

@dp.message(CampaignWizard.required_groups)
async def process_cw_required_groups(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("❌ تم إلغاء إنشاء الحملة.")
        await state.clear()
        return
    if not message.text.isdigit():
        await message.answer("❌ يرجى إرسال أرقام فقط.")
        return
    num = int(message.text)
    if num < 1 or num > 50:
        await message.answer("❌ يجب أن يكون الرقم بين 1 و 50.")
        return
    await state.update_data(required_groups=num)
    
    await message.answer(
        "🔓 <b>الخطوة 6/7:</b> أرسل محتوى الفتح (ما سيحصل عليه المستخدم بعد إكمال الشرط).\n"
        "(مثال: رابط دعوة القناة، كود خصم، رسالة سرية...)\n\n"
        "لإلغاء الأمر أرسل /cancel",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(CampaignWizard.unlock_content)

@dp.message(CampaignWizard.unlock_content)
async def process_cw_unlock_content(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("❌ تم إلغاء إنشاء الحملة.")
        await state.clear()
        return
    await state.update_data(unlock_content=message.html_text or message.text)
    
    await message.answer(
        "🖼 <b>الخطوة 7/7:</b> أرسل صورة أو فيديو لإرفاقه مع محتوى الفتح.\n"
        "إذا أردت بدون وسائط أرسل /skip\n\n"
        "لإلغاء الأمر أرسل /cancel",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(CampaignWizard.unlock_media)

@dp.message(CampaignWizard.unlock_media, F.photo | F.video | F.text)
async def process_cw_unlock_media(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("❌ تم إلغاء إنشاء الحملة.")
        await state.clear()
        return
    if message.text == '/skip':
        await state.update_data(unlock_media_type=None, unlock_media_file_id=None)
    elif message.photo:
        await state.update_data(unlock_media_type="photo", unlock_media_file_id=message.photo[-1].file_id)
    elif message.video:
        await state.update_data(unlock_media_type="video", unlock_media_file_id=message.video.file_id)
    else:
        await message.answer("❌ أرسل صورة أو فيديو، أو /skip، أو /cancel.")
        return
    
    # Show summary
    data = await state.get_data()
    summary = (
        f"📋 <b>ملخص الحملة:</b>\n\n"
        f"📌 <b>الاسم:</b> {data['name']}\n"
        f"🖼 <b>وسائط الإعلان:</b> {'نعم (' + data.get('media_type', '') + ')' if data.get('media_file_id') else 'لا'}\n"
        f"🔘 <b>نص الزر:</b> {data['button_text']}\n"
        f"👥 <b>المجموعات المطلوبة:</b> {data['required_groups']}\n"
        f"🖼 <b>وسائط الفتح:</b> {'نعم' if data.get('unlock_media_file_id') else 'لا'}\n\n"
        f"هل تريد حفظ الحملة؟"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ حفظ الحملة", callback_data="cmp_save")],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="cmp_cancel_wizard")]
    ])
    await message.answer(summary, reply_markup=kb, parse_mode=ParseMode.HTML)
    await state.set_state(CampaignWizard.confirm)

@dp.callback_query(CampaignWizard.confirm)
async def cb_cw_confirm(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    if callback.data == "cmp_cancel_wizard":
        await callback.message.answer("❌ تم إلغاء إنشاء الحملة.")
        await state.clear()
        await callback.answer()
        return
    
    data = await state.get_data()
    await state.clear()
    
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """INSERT INTO campaigns (name, promo_text, media_type, media_file_id, button_text, required_groups, 
               unlock_content, unlock_media_type, unlock_media_file_id, status, created_at, updated_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)""",
            (data['name'], data['promo_text'], data.get('media_type'), data.get('media_file_id'),
             data['button_text'], data['required_groups'], data['unlock_content'],
             data.get('unlock_media_type'), data.get('unlock_media_file_id'),
             datetime.now(), datetime.now())
        )
        campaign_id = cursor.lastrowid
        await db.commit()
    
    await callback.message.answer(f"✅ تم حفظ الحملة بنجاح! (ID: {campaign_id})")
    await show_campaign_admin_view(callback.message, campaign_id)
    await callback.answer()


# --- Campaign Admin View ---

async def show_campaign_admin_view(message: types.Message, campaign_id: int):
    """Show campaign management view to admin."""
    campaign = await get_campaign(campaign_id)
    if not campaign:
        await message.answer("❌ الحملة غير موجودة.")
        return
    
    status_map = {'active': ('🟢', 'نشطة'), 'paused': ('⏸', 'متوقفة'), 'deleted': ('🗑', 'محذوفة')}
    icon, status_text = status_map.get(campaign['status'], ('❓', 'غير معروف'))
    
    text = (
        f"📣 <b>حملة: {campaign['name']}</b>\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"📌 <b>الحالة:</b> {icon} {status_text}\n"
        f"👥 <b>المجموعات المطلوبة:</b> {campaign['required_groups']}\n"
        f"🔘 <b>نص الزر:</b> {campaign['button_text']}\n"
        f"🖼 <b>وسائط:</b> {'نعم' if campaign.get('media_file_id') else 'لا'}\n"
    )
    
    buttons = []
    if campaign['status'] == 'active':
        buttons.append([
            InlineKeyboardButton(text="📢 نشر للمستخدمين", callback_data=f"cmp_pub_u_{campaign_id}"),
            InlineKeyboardButton(text="🌐 نشر للمجموعات", callback_data=f"cmp_pub_g_{campaign_id}")
        ])
        buttons.append([InlineKeyboardButton(text="📢 نشر للجميع", callback_data=f"cmp_pub_a_{campaign_id}")])
        buttons.append([InlineKeyboardButton(text="🧪 اختبار (إرسال لي)", callback_data=f"cmp_test_{campaign_id}")])
        buttons.append([
            InlineKeyboardButton(text="📊 الإحصائيات", callback_data=f"cmp_stats_{campaign_id}"),
            InlineKeyboardButton(text="⏸ إيقاف", callback_data=f"cmp_pause_{campaign_id}")
        ])
    elif campaign['status'] == 'paused':
        buttons.append([
            InlineKeyboardButton(text="📊 الإحصائيات", callback_data=f"cmp_stats_{campaign_id}"),
            InlineKeyboardButton(text="▶️ تفعيل", callback_data=f"cmp_resume_{campaign_id}")
        ])
    buttons.append([InlineKeyboardButton(text="🗑 حذف", callback_data=f"cmp_del_{campaign_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="cmp_list")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


# --- Campaign List ---

@dp.callback_query(F.data == "cmp_list")
async def cb_campaign_list(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, name, status, required_groups FROM campaigns WHERE status != 'deleted' ORDER BY id DESC LIMIT 15"
        ) as cursor:
            campaigns = await cursor.fetchall()
    
    if not campaigns:
        text = "📋 <b>الحملات</b>\n━━━━━━━━━━━━━━\n\nلا توجد حملات حتى الآن."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ إنشاء حملة جديدة", callback_data="cmp_new")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data="cmp_menu")]
        ])
    else:
        lines = ["📋 <b>الحملات (آخر 15)</b>\n━━━━━━━━━━━━━━\n"]
        buttons = []
        for cid, name, status, req in campaigns:
            icon = "🟢" if status == 'active' else "⏸"
            lines.append(f"{icon} <b>{name}</b> — {req} مجموعات")
            buttons.append([InlineKeyboardButton(text=f"{icon} {name}", callback_data=f"cmp_view_{cid}")])
        text = "\n".join(lines)
        buttons.append([InlineKeyboardButton(text="➕ إنشاء حملة جديدة", callback_data="cmp_new")])
        buttons.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="cmp_menu")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except TelegramAPIError:
        await callback.message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()


# --- Campaign View (Admin) ---

@dp.callback_query(F.data.startswith("cmp_view_"))
async def cb_campaign_view(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    campaign_id = int(callback.data.split("_")[-1])
    await show_campaign_admin_view(callback.message, campaign_id)
    await callback.answer()


# --- Campaign Stats ---

@dp.callback_query(F.data.startswith("cmp_stats_"))
async def cb_campaign_stats(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    campaign_id = int(callback.data.split("_")[-1])
    campaign = await get_campaign(campaign_id)
    if not campaign:
        await callback.answer("❌ الحملة غير موجودة.", show_alert=True)
        return
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM events WHERE event_type=?", (f"campaign_{campaign_id}_viewed",)
        ) as cursor:
            views = (await cursor.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM campaign_user_progress WHERE campaign_id=?", (campaign_id,)
        ) as cursor:
            started = (await cursor.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM campaign_groups WHERE campaign_id=? AND verified=1", (campaign_id,)
        ) as cursor:
            groups_added = (await cursor.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM campaign_user_progress WHERE campaign_id=? AND status='unlocked'", (campaign_id,)
        ) as cursor:
            unlocked = (await cursor.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM events WHERE event_type=?", (f"campaign_{campaign_id}_content_delivered",)
        ) as cursor:
            delivered = (await cursor.fetchone())[0]
    
    text = (
        f"📊 <b>إحصائيات الحملة</b>\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"📣 <b>{campaign['name']}</b>\n\n"
        f"👁 <b>شاهدوا الحملة:</b> {views}\n"
        f"🔒 <b>بدأوا الشرط:</b> {started}\n"
        f"➕ <b>مجموعات أضيف إليها البوت:</b> {groups_added}\n"
        f"🔓 <b>أكملوا الشرط:</b> {unlocked}\n"
        f"🎁 <b>حصلوا على المحتوى:</b> {delivered}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"cmp_view_{campaign_id}")]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except TelegramAPIError:
        await callback.message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()


# --- Campaign Pause/Resume/Delete ---

@dp.callback_query(F.data.startswith("cmp_pause_"))
async def cb_campaign_pause(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    campaign_id = int(callback.data.split("_")[-1])
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE campaigns SET status='paused', updated_at=? WHERE id=?", (datetime.now(), campaign_id))
        await db.commit()
    await callback.answer("⏸ تم إيقاف الحملة.", show_alert=True)
    await show_campaign_admin_view(callback.message, campaign_id)

@dp.callback_query(F.data.startswith("cmp_resume_"))
async def cb_campaign_resume(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    campaign_id = int(callback.data.split("_")[-1])
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE campaigns SET status='active', updated_at=? WHERE id=?", (datetime.now(), campaign_id))
        await db.commit()
    await callback.answer("▶️ تم تفعيل الحملة.", show_alert=True)
    await show_campaign_admin_view(callback.message, campaign_id)

@dp.callback_query(F.data.startswith("cmp_del_"))
async def cb_campaign_delete(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    campaign_id = int(callback.data.split("_")[-1])
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE campaigns SET status='deleted', updated_at=? WHERE id=?", (datetime.now(), campaign_id))
        await db.commit()
    await callback.answer("🗑 تم حذف الحملة.", show_alert=True)
    # Go back to list
    await cb_campaign_list(callback)


# --- Campaign Publish (Broadcast) ---

async def execute_campaign_broadcast(campaign_id: int, target: str, status_msg: types.Message):
    """Broadcast campaign promo to users/groups using existing broadcast pattern."""
    campaign = await get_campaign(campaign_id)
    if not campaign:
        await status_msg.edit_text("❌ الحملة غير موجودة.")
        return
    
    bot_info = await bot.get_me()
    cta_button = InlineKeyboardButton(
        text=campaign['button_text'],
        url=f"https://t.me/{bot_info.username}?start=camp_{campaign_id}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[cta_button]])
    
    if target in ('users', 'all'):
        query_users = "SELECT telegram_id FROM users"
    if target in ('groups', 'all'):
        query_groups = "SELECT chat_id FROM groups WHERE status='active'"
    
    targets_list = []
    async with aiosqlite.connect(DB_NAME) as db:
        if target in ('users', 'all'):
            async with db.execute(query_users) as cursor:
                targets_list.extend(await cursor.fetchall())
        if target in ('groups', 'all'):
            async with db.execute(query_groups) as cursor:
                targets_list.extend(await cursor.fetchall())
    
    success = 0
    for t in targets_list:
        chat_id = t[0]
        try:
            if campaign.get('media_file_id'):
                if campaign['media_type'] == 'photo':
                    await bot.send_photo(chat_id, photo=campaign['media_file_id'],
                                         caption=campaign['promo_text'], reply_markup=kb, parse_mode=ParseMode.HTML)
                else:
                    await bot.send_video(chat_id, video=campaign['media_file_id'],
                                         caption=campaign['promo_text'], reply_markup=kb, parse_mode=ParseMode.HTML)
            else:
                await bot.send_message(chat_id, campaign['promo_text'], reply_markup=kb, parse_mode=ParseMode.HTML)
            success += 1
        except TelegramForbiddenError:
            if target in ('groups', 'all'):
                async with aiosqlite.connect(DB_NAME) as db2:
                    await db2.execute("UPDATE groups SET status='inactive' WHERE chat_id=?", (chat_id,))
                    await db2.commit()
        except Exception:
            pass
        await asyncio.sleep(0.05)
    
    await status_msg.edit_text(f"✅ اكتمل نشر الحملة! تم الإرسال إلى <b>{success}</b> جهة.", parse_mode=ParseMode.HTML)


@dp.callback_query(F.data.startswith("cmp_pub_"))
async def cb_campaign_publish(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    
    parts = callback.data.split("_")
    # cmp_pub_u_5 → parts = ["cmp", "pub", "u", "5"]
    target_code = parts[2]  # u/g/a
    campaign_id = int(parts[3])
    
    target_map = {'u': 'users', 'g': 'groups', 'a': 'all'}
    target = target_map.get(target_code, 'users')
    target_ar = {'users': 'المستخدمين', 'groups': 'المجموعات', 'all': 'الجميع'}
    
    campaign = await get_campaign(campaign_id)
    if not campaign or campaign['status'] != 'active':
        await callback.answer("❌ الحملة غير متوفرة أو متوقفة.", show_alert=True)
        return
    
    status_msg = await callback.message.answer(f"🚀 جاري نشر الحملة إلى {target_ar[target]}، يرجى الانتظار...")
    asyncio.create_task(execute_campaign_broadcast(campaign_id, target, status_msg))
    await callback.answer()


# --- Campaign Test ---

@dp.callback_query(F.data.startswith("cmp_test_"))
async def cb_campaign_test(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    campaign_id = int(callback.data.split("_")[-1])
    campaign = await get_campaign(campaign_id)
    if not campaign:
        await callback.answer("❌ الحملة غير موجودة.", show_alert=True)
        return
    
    bot_info = await bot.get_me()
    cta_button = InlineKeyboardButton(
        text=campaign['button_text'],
        url=f"https://t.me/{bot_info.username}?start=camp_{campaign_id}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[cta_button]])
    
    admin_id = callback.from_user.id
    try:
        if campaign.get('media_file_id'):
            if campaign['media_type'] == 'photo':
                await bot.send_photo(admin_id, photo=campaign['media_file_id'],
                                     caption=f"🧪 <b>[اختبار]</b>\n\n{campaign['promo_text']}", reply_markup=kb, parse_mode=ParseMode.HTML)
            else:
                await bot.send_video(admin_id, video=campaign['media_file_id'],
                                     caption=f"🧪 <b>[اختبار]</b>\n\n{campaign['promo_text']}", reply_markup=kb, parse_mode=ParseMode.HTML)
        else:
            await bot.send_message(admin_id, f"🧪 <b>[اختبار]</b>\n\n{campaign['promo_text']}", reply_markup=kb, parse_mode=ParseMode.HTML)
        await callback.answer("✅ تم إرسال نسخة تجريبية لك.", show_alert=True)
    except Exception as e:
        logger.error(f"Campaign test send failed: {e}")
        await callback.answer("❌ فشل إرسال الاختبار.", show_alert=True)

# --- Global Error Handler ---
# This silently catches unknown/unsupported Telegram update types (e.g. new RichText fields)
# and prevents the bot from crashing when Telegram adds new API features.
@dp.errors()
async def global_error_handler(event: types.ErrorEvent) -> bool:
    logger.warning(f"Caught unhandled error: {event.exception.__class__.__name__}: {event.exception}")
    # Return True to mark the error as handled and prevent crash
    return True

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set in .env")
        sys.exit(1)
    if not ADMIN_ID:
        logger.error("ADMIN_ID is not set in .env")
        sys.exit(1)
        
    await init_db()
    logger.info("Database initialized.")
    
    # Start background task for auto-deleting broadcasts
    asyncio.create_task(auto_delete_broadcasts())
    
    # Self-Healing Polling Loop:
    # Catches pydantic validation errors caused by unknown Telegram API updates
    # drops the poisonous update, and restarts polling automatically.
    while True:
        try:
            logger.info("Starting bot polling...")
            await dp.start_polling(bot, drop_pending_updates=True)
            break  # If polling stops gracefully, break the loop
        except Exception as e:
            logger.error(f"Critical Polling Error (Poisonous Update): {e}")
            logger.info("Restarting polling in 3 seconds to auto-clean...")
            await asyncio.sleep(3)
            
    await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
