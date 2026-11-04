"""
Database manager — handles SQLite initialization, migrations, and connection access.

Usage:
    from core.database import init_db, get_db

    # At startup:
    await init_db()

    # In any async function:
    async with get_db() as db:
        await db.execute(...)
"""

import aiosqlite
from contextlib import asynccontextmanager

from core.config import DB_NAME
from core.logging_config import logger


@asynccontextmanager
async def get_db():
    """Async context manager that yields an aiosqlite connection."""
    db = await aiosqlite.connect(DB_NAME)
    try:
        yield db
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# Default settings inserted on first run (INSERT OR IGNORE — never overwrites)
# ---------------------------------------------------------------------------
_DEFAULT_SETTINGS = {
    "promo_enabled": "true",
    "promo_text": (
        "🔥 مرحبًا بك يا {user}!\n"
        "اكتشف خدماتنا ومحتوانا من خلال الرابط التالي."
    ),
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
    "start_message": (
        "🤖 أهلاً بك في البوت!\n\n"
        "هذا البوت يساعدك على إضافة رسائل ترويجية إلى مجموعتك عند انضمام أعضاء جدد.\n"
        "أضف البوت إلى مجموعتك وسيبدأ العمل تلقائياً بناءً على إعدادات الإدارة."
    ),
    "start_btn2_name": "ℹ️ طريقة الاستخدام",
    "start_btn2_type": "text",
    "start_btn2_content": (
        "ℹ️ <b>طريقة الاستخدام:</b>\n\n"
        "1. اضغط على زر 'إضافة البوت إلى مجموعتي'.\n"
        "2. اختر المجموعة التي تريد إضافة البوت إليها.\n"
        "3. عند انضمام أي عضو جديد، سيقوم البوت بإرسال رسالة ترحيبية ترويجية.\n"
        "4. يمتلك البوت نظام حماية من التكرار (Cooldown) لمنع الإزعاج."
    ),
    "private_welcome_enabled": "true",
    "promo_delete_seconds": "0",
    "test_group_chat_id": "",
    "start_media_id": "",
    "start_media_type": "",
    # ── User campaigns feature switch ────────────────────────────
    "user_campaigns_enabled": "true",
    "user_campaigns_generation": "1",
}



async def _try_add_column(db, table: str, column: str, coldef: str) -> None:
    """Safely add a column — ignore if it already exists."""
    try:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coldef}")
    except aiosqlite.OperationalError:
        pass


async def init_db() -> None:
    """
    Create all tables, run column migrations, and insert default settings.
    Safe to call on every startup — uses IF NOT EXISTS and INSERT OR IGNORE.
    """
    async with get_db() as db:
        # ── Core tables ─────────────────────────────────────────
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
        await _try_add_column(db, "groups", "last_promo_msg_id", "INTEGER")
        await _try_add_column(db, "groups", "added_by", "INTEGER")
        # ── Group health & reward ownership (new) ────────────────
        await _try_add_column(db, "groups", "reward_owner_id", "INTEGER")
        await _try_add_column(db, "groups", "health_status", "TEXT DEFAULT 'unknown'")
        await _try_add_column(db, "groups", "last_error", "TEXT")
        await _try_add_column(db, "groups", "fail_count", "INTEGER DEFAULT 0")
        await _try_add_column(db, "groups", "last_checked_at", "TIMESTAMP")

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

        # ── Campaign tables ──────────────────────────────────────
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
        for col, coldef in [
            ("unlock_delete_seconds", "INTEGER DEFAULT 0"),
            ("mode", "TEXT DEFAULT 'manual'"),
            ("repeat_hours", "INTEGER DEFAULT 0"),
            ("recurring_active", "INTEGER DEFAULT 0"),
            ("last_broadcast_at", "TIMESTAMP"),
        ]:
            await _try_add_column(db, "campaigns", col, coldef)

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

        # ── Recurring broadcasts table ───────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS recurring_broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target TEXT NOT NULL,
                text TEXT,
                media_id TEXT,
                media_type TEXT,
                is_vip INTEGER DEFAULT 0,
                stars INTEGER DEFAULT 0,
                repeat_hours INTEGER DEFAULT 24,
                is_active INTEGER DEFAULT 1,
                last_broadcast_at TIMESTAMP,
                created_at TIMESTAMP
            )
        """)

        # ── Custom buttons table ─────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS custom_buttons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                context TEXT NOT NULL,
                label TEXT NOT NULL,
                url TEXT NOT NULL,
                position INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP
            )
        """)

        # ── User campaigns (new) ─────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_campaigns (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_user_id       INTEGER NOT NULL,
                text                TEXT,
                photo_file_id       TEXT,
                buttons_json        TEXT,
                auto_delete_seconds INTEGER DEFAULT 0,
                target_groups_json  TEXT NOT NULL DEFAULT '[]',
                mode                TEXT DEFAULT 'immediate',
                repeat_hours        INTEGER DEFAULT 0,
                status              TEXT DEFAULT 'draft',
                system_generation   INTEGER DEFAULT 1,
                run_id              TEXT,
                created_at          TIMESTAMP NOT NULL,
                activated_at        TIMESTAMP,
                last_run_at         TIMESTAMP,
                next_run_at         TIMESTAMP,
                completed_at        TIMESTAMP,
                quota_date          TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(owner_user_id) REFERENCES users(telegram_id)
            )
        """)
        # Partial unique index: one "current" campaign per user
        await db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_one_current_per_user
            ON user_campaigns(owner_user_id)
            WHERE status IN ('active', 'running', 'paused', 'suspended_admin')
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_campaign_quota (
                user_id         INTEGER NOT NULL,
                quota_date      TEXT NOT NULL,
                campaigns_created INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, quota_date)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_campaign_deliveries (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id     INTEGER NOT NULL,
                run_id          TEXT NOT NULL,
                chat_id         INTEGER NOT NULL,
                status          TEXT,
                error_code      TEXT,
                attempted_at    TIMESTAMP NOT NULL,
                confirmed_at    TIMESTAMP,
                UNIQUE(campaign_id, run_id, chat_id),
                FOREIGN KEY(campaign_id) REFERENCES user_campaigns(id)
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_deliveries_campaign_run
            ON user_campaign_deliveries(campaign_id, run_id)
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_campaign_execution_claims (
                campaign_id     INTEGER PRIMARY KEY,
                run_id          TEXT NOT NULL,
                claimed_at      TIMESTAMP NOT NULL,
                heartbeat_at    TIMESTAMP NOT NULL,
                expires_at      TIMESTAMP NOT NULL,
                FOREIGN KEY(campaign_id) REFERENCES user_campaigns(id)
            )
        """)

        # ── Default settings ─────────────────────────────────────
        for key, value in _DEFAULT_SETTINGS.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )

        await db.commit()

    logger.info("Database initialized successfully.")

