"""
Admins model — admin authorization and CRUD for the `admins` table.

The ADMIN_ID from .env is always considered an admin (owner).
Additional admins are stored in the `admins` table.
"""

from datetime import datetime

from core.config import ADMIN_ID
from core.database import get_db


async def is_admin(user_id: int) -> bool:
    """Check if a user is an admin (owner or added admin)."""
    if user_id == ADMIN_ID:
        return True
    async with get_db() as db:
        async with db.execute(
            "SELECT 1 FROM admins WHERE telegram_id = ?", (user_id,)
        ) as cursor:
            return await cursor.fetchone() is not None


async def add_admin(telegram_id: int) -> None:
    """Add a new admin. Ignores if already exists."""
    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO admins (telegram_id, added_at) VALUES (?, ?)",
            (telegram_id, datetime.now()),
        )
        await db.commit()


async def remove_admin(telegram_id: int) -> None:
    """Remove an admin by telegram_id."""
    async with get_db() as db:
        await db.execute(
            "DELETE FROM admins WHERE telegram_id = ?", (telegram_id,)
        )
        await db.commit()


async def list_admins() -> list[tuple[int, str]]:
    """Return list of (telegram_id, added_at) for all added admins."""
    async with get_db() as db:
        async with db.execute(
            "SELECT telegram_id, added_at FROM admins"
        ) as cursor:
            return await cursor.fetchall()
