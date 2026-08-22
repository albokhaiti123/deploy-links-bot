import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv

import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode, ChatType
from aiogram.filters import CommandStart, Command, IS_MEMBER, IS_NOT_MEMBER, ChatMemberUpdatedFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated
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
            "start_message": "🤖 أهلاً بك في البوت!\n\nهذا البوت يساعدك على إضافة رسائل ترويجية إلى مجموعتك عند انضمام أعضاء جدد.\nأضف البوت إلى مجموعتك وسيبدأ العمل تلقائياً بناءً على إعدادات الإدارة."
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
    waiting_for_broadcast_users = State()
    waiting_for_broadcast_groups = State()
    waiting_for_start_msg = State()

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

# --- Utilities ---
async def log_event(chat_id: int, user_id: int, event_type: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO events (chat_id, telegram_user_id, event_type, created_at) VALUES (?, ?, ?, ?)",
                         (chat_id, user_id, event_type, datetime.now()))
        await db.commit()

# --- Handlers ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    if message.chat.type != ChatType.PRIVATE:
        return
        
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (telegram_id, username, first_name, created_at) VALUES (?, ?, ?, ?)",
                         (message.from_user.id, message.from_user.username, message.from_user.first_name, datetime.now()))
        await db.commit()
        
    bot_info = await bot.get_me()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ إضافة البوت إلى مجموعتي", url=get_bot_add_url(bot_info.username or BOT_USERNAME))],
        [InlineKeyboardButton(text="ℹ️ طريقة الاستخدام", callback_data="help_usage")]
    ])
    
    start_text = await get_setting("start_message")
    if not start_text:
        start_text = (
            "🤖 أهلاً بك في البوت!\n\n"
            "هذا البوت يساعدك على إضافة رسائل ترويجية إلى مجموعتك عند انضمام أعضاء جدد.\n"
            "أضف البوت إلى مجموعتك وسيبدأ العمل تلقائياً بناءً على إعدادات الإدارة."
        )
        
    await message.answer(start_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

@dp.callback_query(F.data == "help_usage")
async def cb_help_usage(callback: types.CallbackQuery):
    text = (
        "ℹ️ <b>طريقة الاستخدام:</b>\n\n"
        "1. اضغط على زر 'إضافة البوت إلى مجموعتي'.\n"
        "2. اختر المجموعة التي تريد إضافة البوت إليها.\n"
        "3. عند انضمام أي عضو جديد، سيقوم البوت بإرسال رسالة ترحيبية ترويجية.\n"
        "4. يمتلك البوت نظام حماية من التكرار (Cooldown) لمنع الإزعاج."
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML)
    await callback.answer()

# --- Group Events ---
@dp.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=IS_NOT_MEMBER >> IS_MEMBER))
async def bot_added_to_group(event: ChatMemberUpdated):
    chat = event.chat
    if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                INSERT INTO groups (chat_id, title, chat_type, status, added_at, updated_at) 
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET status='active', title=?, updated_at=?
            """, (chat.id, chat.title, chat.type, 'active', datetime.now(), datetime.now(), chat.title, datetime.now()))
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
    
    # Format text with mention
    user_name = new_member.first_name.replace('<', '&lt;').replace('>', '&gt;')
    mention = f"<a href='tg://user?id={new_member.id}'>{user_name}</a>"
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
                
        await log_event(chat_id, message.from_user.id, "promo_sent")
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

# --- Admin Panel ---
def get_admin_keyboard(promo_enabled: str, user_id: int) -> InlineKeyboardMarkup:
    toggle_text = "⏸️ إيقاف الترويج" if promo_enabled == "true" else "▶️ تشغيل الترويج"
    
    keyboard = [
        [InlineKeyboardButton(text="📢 إعداد الترويج", callback_data="admin_promo_settings")],
        [InlineKeyboardButton(text="👥 المجموعات", callback_data="admin_groups"),
         InlineKeyboardButton(text="📊 الإحصائيات", callback_data="admin_stats")],
        [InlineKeyboardButton(text="⚙️ الإعدادات", callback_data="admin_settings")],
        [InlineKeyboardButton(text="📣 رسالة إذاعة", callback_data="admin_broadcast_menu")],
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

# --- Manage Admins ---
@dp.callback_query(F.data == "admin_manage_admins")
async def cb_admin_manage_admins(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: 
        return
    await state.clear()
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT telegram_id FROM admins") as cursor:
            admins = await cursor.fetchall()
            
    keyboard = [[InlineKeyboardButton(text="➕ إضافة مشرف", callback_data="admin_add_admin")]]
    
    text = "👑 <b>إدارة المشرفين</b>\n\nالمشرفون الحاليون:\n"
    text += f"1. {ADMIN_ID} (المالك)\n"
    
    for idx, adm in enumerate(admins, start=2):
        text += f"{idx}. {adm[0]}\n"
        keyboard.append([InlineKeyboardButton(text=f"❌ حذف {adm[0]}", callback_data=f"admin_del_admin_{adm[0]}")])
        
    keyboard.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_main")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode=ParseMode.HTML)
    await callback.answer()

@dp.callback_query(F.data == "admin_add_admin")
async def cb_admin_add_admin(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await callback.message.answer("أرسل الآن Telegram ID للمشرف الجديد (أرقام فقط):\nلإلغاء الأمر أرسل /cancel")
    await state.set_state(AdminEdit.waiting_for_admin_id)
    await callback.answer()

@dp.message(AdminEdit.waiting_for_admin_id)
async def process_admin_id(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("تم الإلغاء.")
        await state.clear()
        return
    if not message.text.isdigit():
        await message.answer("❌ يرجى إرسال ID صحيح (أرقام فقط).\nحاول مجدداً أو أرسل /cancel")
        return
        
    new_admin_id = int(message.text)
    if new_admin_id == ADMIN_ID:
        await message.answer("❌ هذا الـ ID خاص بالمالك.")
        return
        
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO admins (telegram_id, added_at) VALUES (?, ?)", (new_admin_id, datetime.now()))
        await db.commit()
        
    await message.answer(f"✅ تم إضافة المشرف {new_admin_id} بنجاح.")
    await state.clear()

@dp.callback_query(F.data.startswith("admin_del_admin_"))
async def cb_admin_del_admin(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    del_id = int(callback.data.split("_")[3])
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM admins WHERE telegram_id = ?", (del_id,))
        await db.commit()
        
    await callback.answer(f"تم حذف المشرف {del_id}", show_alert=True)
    await cb_admin_manage_admins(callback, state)

# --- Promo Settings ---
@dp.callback_query(F.data == "admin_promo_settings")
async def cb_admin_promo_settings(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.clear()
    show_bot_btn = await get_setting("show_add_bot_button")
    btn_text = "🤖 إخفاء زر البوت" if show_bot_btn == "true" else "🤖 إظهار زر البوت"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 تعديل النص", callback_data="admin_edit_text"),
         InlineKeyboardButton(text="🖼️ تعديل الوسائط", callback_data="admin_edit_media")],
        [InlineKeyboardButton(text="🔗 تعديل الرابط", callback_data="admin_edit_url"),
         InlineKeyboardButton(text="🔘 تعديل الزر", callback_data="admin_edit_button")],
        [InlineKeyboardButton(text=btn_text, callback_data="admin_toggle_bot_btn")],
        [InlineKeyboardButton(text="👁 معاينة الإعلان", callback_data="admin_preview_promo")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_main")]
    ])
    text = (
        "📢 <b>إعداد الترويج</b>\n\n"
        "يمكنك استخدام <code>{user}</code> في النص ليتم استبدالها تلقائياً بـ 'منشن' للعضو الجديد.\n\n"
        "اختر ما تريد تعديله:"
    )
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    await callback.answer()

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
    
    bot_info = await bot.get_me()
    
    user_name = callback.from_user.first_name.replace('<', '&lt;').replace('>', '&gt;')
    mention = f"<a href='tg://user?id={callback.from_user.id}'>{user_name}</a>"
    promo_text_formatted = promo_text.replace("{user}", mention)
    
    keyboard = build_promo_keyboard(promo_url, promo_button_text, bot_info.username or BOT_USERNAME, show_bot_btn)
    
    try:
        if promo_media_id and promo_media_type == "photo":
            await callback.message.answer_photo(photo=promo_media_id, caption=f"👁 <b>معاينة:</b>\n\n{promo_text_formatted}", reply_markup=keyboard, parse_mode=ParseMode.HTML)
        elif promo_media_id and promo_media_type == "video":
            await callback.message.answer_video(video=promo_media_id, caption=f"👁 <b>معاينة:</b>\n\n{promo_text_formatted}", reply_markup=keyboard, parse_mode=ParseMode.HTML)
        else:
            await callback.message.answer(f"👁 <b>معاينة:</b>\n\n{promo_text_formatted}", reply_markup=keyboard, parse_mode=ParseMode.HTML)
    except Exception as e:
        await callback.message.answer(f"❌ حدث خطأ في المعاينة. تأكد من صحة الرابط أو النص.\nالخطأ: {e}")
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

# --- Groups ---
@dp.callback_query(F.data == "admin_groups")
async def cb_admin_groups(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM groups WHERE status='active'") as cursor:
            active_count = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM groups WHERE status='inactive'") as cursor:
            inactive_count = (await cursor.fetchone())[0]
            
    text = (
        "👥 <b>إحصائيات المجموعات:</b>\n\n"
        f"✅ المجموعات النشطة: {active_count}\n"
        f"❌ المجموعات غير النشطة: {inactive_count}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ إدارة المجموعات (تصفح/مغادرة)", callback_data="admin_list_groups_0")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_main")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_list_groups_"))
async def cb_admin_list_groups(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    page = int(callback.data.split("_")[3])
    offset = page * 5
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT chat_id, title FROM groups WHERE status='active' LIMIT 5 OFFSET ?", (offset,)) as cursor:
            groups = await cursor.fetchall()
        async with db.execute("SELECT COUNT(*) FROM groups WHERE status='active'") as cursor:
            total = (await cursor.fetchone())[0]
            
    keyboard = []
    for g in groups:
        title = g[1][:20] if g[1] else "مجموعة"
        keyboard.append([InlineKeyboardButton(text=f"🚪 مغادرة: {title}", callback_data=f"admin_leave_{g[0]}")])
        
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ السابق", callback_data=f"admin_list_groups_{page-1}"))
    if offset + 5 < total:
        nav.append(InlineKeyboardButton(text="التالي ➡️", callback_data=f"admin_list_groups_{page+1}"))
    if nav:
        keyboard.append(nav)
        
    keyboard.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_groups")])
    await callback.message.edit_text("⚙️ <b>تصفح المجموعات:</b>\n\nاضغط على أي مجموعة لمغادرتها فوراً:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode=ParseMode.HTML)
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_leave_"))
async def cb_admin_leave(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    chat_id = int(callback.data.split("_")[2])
    try:
        await bot.leave_chat(chat_id)
        await callback.answer("✅ تمت مغادرة المجموعة بنجاح", show_alert=True)
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE groups SET status='inactive' WHERE chat_id=?", (chat_id,))
            await db.commit()
    except Exception as e:
        await callback.answer(f"❌ لم أتمكن من المغادرة: {e}", show_alert=True)
    await cb_admin_groups(callback)

# --- Stats ---
@dp.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            users_count = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM events WHERE event_type='promo_sent'") as cursor:
            promos_count = (await cursor.fetchone())[0]
        
        today_str = datetime.now().strftime('%Y-%m-%d')
        async with db.execute("SELECT COUNT(*) FROM events WHERE event_type='promo_sent' AND date(created_at) = ?", (today_str,)) as cursor:
            today_promos = (await cursor.fetchone())[0]
            
    text = (
        "📊 <b>الإحصائيات:</b>\n\n"
        f"👥 المستخدمون المسجلون: {users_count}\n"
        f"📨 إجمالي الإعلانات المرسلة: {promos_count}\n"
        f"📅 إعلانات اليوم: {today_promos}\n"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_main")]])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    await callback.answer()

# --- Broadcast ---
@dp.callback_query(F.data == "admin_broadcast_menu")
async def cb_admin_broadcast_menu(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    await state.clear()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 إذاعة للمستخدمين (في الخاص)", callback_data="admin_broadcast_users")],
        [InlineKeyboardButton(text="🌐 إذاعة للمجموعات", callback_data="admin_broadcast_groups")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_main")]
    ])
    await callback.message.edit_text("📣 <b>خيارات الإذاعة:</b>\nاختر الوجهة التي تريد إرسال الإذاعة إليها:", reply_markup=keyboard, parse_mode=ParseMode.HTML)
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast_users")
async def cb_admin_broadcast_users(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    await callback.message.answer("📢 أرسل الرسالة التي تريد إذاعتها لجميع المستخدمين (في الخاص):\nلإلغاء الأمر أرسل /cancel")
    await state.set_state(AdminEdit.waiting_for_broadcast_users)
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast_groups")
async def cb_admin_broadcast_groups(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    await callback.message.answer("🌐 أرسل الرسالة التي تريد إذاعتها لجميع المجموعات النشطة:\nلإلغاء الأمر أرسل /cancel")
    await state.set_state(AdminEdit.waiting_for_broadcast_groups)
    await callback.answer()

@dp.message(AdminEdit.waiting_for_broadcast_users)
async def process_broadcast_users(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("تم الإلغاء.")
        await state.clear()
        return
        
    status_msg = await message.answer("🚀 جاري الإرسال للمستخدمين، يرجى الانتظار...")
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT telegram_id FROM users") as cursor:
            users = await cursor.fetchall()
            
    success = 0
    for u in users:
        try:
            await message.copy_to(u[0])
            success += 1
            await asyncio.sleep(0.05) # Prevent flood limit
        except Exception:
            pass
            
    await status_msg.edit_text(f"✅ تمت الإذاعة بنجاح لـ {success} مستخدم.")
    await state.clear()

@dp.message(AdminEdit.waiting_for_broadcast_groups)
async def process_broadcast_groups(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await message.answer("تم الإلغاء.")
        await state.clear()
        return
        
    status_msg = await message.answer("🚀 جاري الإرسال للمجموعات، يرجى الانتظار...")
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT chat_id FROM groups WHERE status='active'") as cursor:
            groups = await cursor.fetchall()
            
    success = 0
    for g in groups:
        try:
            await message.copy_to(g[0])
            success += 1
            await asyncio.sleep(0.05) # Prevent flood limit
        except TelegramForbiddenError:
            async with aiosqlite.connect(DB_NAME) as db2:
                await db2.execute("UPDATE groups SET status='inactive' WHERE chat_id=?", (g[0],))
                await db2.commit()
        except Exception:
            pass
            
    await status_msg.edit_text(f"✅ تمت الإذاعة بنجاح لـ {success} مجموعة.")
    await state.clear()

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
        [InlineKeyboardButton(text="💬 تعديل رسالة الترحيب (/start)", callback_data="admin_edit_start_msg")],
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
    
@dp.callback_query(F.data == "admin_edit_start_msg")
async def cb_admin_edit_start_msg(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    await callback.message.answer("أرسل الآن رسالة الترحيب الجديدة التي ستظهر للأعضاء في الخاص عند الدخول للبوت وإرسال /start:\n(يمكنك استخدام HTML)\nلإلغاء الأمر أرسل /cancel")
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

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set in .env")
        sys.exit(1)
    if not ADMIN_ID:
        logger.error("ADMIN_ID is not set in .env")
        sys.exit(1)
        
    await init_db()
    logger.info("Database initialized.")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
