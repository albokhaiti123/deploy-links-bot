"""
Users model — CRUD for the `users` table.
Phase 5: Added lang column helpers (get_user_lang, set_user_lang, ensure_user_lang).
"""

from datetime import datetime, timedelta

from core.database import get_db


async def upsert_user(telegram_id: int, username: str | None, first_name: str | None) -> None:
    """Insert a user or ignore if already exists."""
    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username, first_name, created_at) VALUES (?, ?, ?, ?)",
            (telegram_id, username, first_name, datetime.now()),
        )
        await db.commit()


async def get_all_user_ids() -> list[int]:
    """Return all user telegram_ids."""
    async with get_db() as db:
        async with db.execute("SELECT telegram_id FROM users") as cursor:
            return [row[0] for row in await cursor.fetchall()]


async def get_total_users() -> int:
    """Total number of registered users."""
    async with get_db() as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            return (await cursor.fetchone())[0]


async def get_users_since(since: str | datetime | None = None, hours: int = 24) -> int:
    """Count users created since a cutoff timestamp using parameterized query."""
    if isinstance(since, datetime):
        cutoff = since
    else:
        cutoff = datetime.now() - timedelta(hours=hours)
    async with get_db() as db:
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE created_at >= ?",
            (cutoff,),
        ) as cursor:
            return (await cursor.fetchone())[0]


# ---------------------------------------------------------------------------
# Phase 5 — Language helpers
# ---------------------------------------------------------------------------

async def get_user_lang(telegram_id: int) -> str | None:
    """Return the stored language code for a user, or None if not set."""
    async with get_db() as db:
        try:
            async with db.execute(
                "SELECT lang FROM users WHERE telegram_id = ?", (telegram_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
        except Exception:
            return None


async def set_user_lang(telegram_id: int, lang: str) -> None:
    """Persist the language preference for a user."""
    async with get_db() as db:
        try:
            await db.execute(
                "UPDATE users SET lang = ? WHERE telegram_id = ?", (lang, telegram_id)
            )
            await db.commit()
        except Exception:
            pass


async def ensure_user_lang(telegram_id: int, language_code: str | None) -> str:
    """
    Ensure a user has a lang value in the DB.
    If lang column is NULL (not yet detected), auto-detect from language_code and persist.
    Returns the resolved lang ('ar' or 'en').
    """
    from core.i18n import resolve_lang
    existing = await get_user_lang(telegram_id)
    if existing is not None:
        # Already explicitly set — preserve it
        return existing
    # NULL means first time — auto-detect and persist
    lang = resolve_lang(language_code)
    await set_user_lang(telegram_id, lang)
    return lang
