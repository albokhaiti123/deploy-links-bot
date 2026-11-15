"""
Users model — CRUD for the `users` table.
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
