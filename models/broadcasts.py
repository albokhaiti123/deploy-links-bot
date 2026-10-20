"""
Broadcasts model — timed message deletion queue and recurring broadcasts CRUD.

Tables:
  - broadcast_messages: queue of messages scheduled for deletion
  - recurring_broadcasts: recurring broadcast configurations
"""

from datetime import datetime, timedelta

from core.database import get_db


# ── Timed Deletion Queue ────────────────────────────────────────────────────

async def schedule_delete(chat_id: int, message_id: int, delete_at: datetime) -> None:
    """Schedule a message for auto-deletion at a specific time."""
    async with get_db() as db:
        await db.execute(
            "INSERT INTO broadcast_messages (chat_id, message_id, delete_at) VALUES (?, ?, ?)",
            (chat_id, message_id, delete_at),
        )
        await db.commit()


async def schedule_delete_after(chat_id: int, message_id: int, seconds: int) -> None:
    """Schedule a message for auto-deletion after N seconds from now."""
    delete_at = datetime.now() + timedelta(seconds=seconds)
    await schedule_delete(chat_id, message_id, delete_at)


async def get_expired_messages() -> list[tuple[int, int, int]]:
    """Return list of (db_id, chat_id, message_id) for messages past their delete_at."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, chat_id, message_id FROM broadcast_messages WHERE delete_at <= ?",
            (datetime.now(),),
        )
        return await cursor.fetchall()


async def remove_delete_record(record_id: int) -> None:
    """Remove a broadcast_messages record after successful deletion."""
    async with get_db() as db:
        await db.execute(
            "DELETE FROM broadcast_messages WHERE id = ?", (record_id,)
        )
        await db.commit()


# ── Recurring Broadcasts ────────────────────────────────────────────────────

async def create_recurring_broadcast(
    target: str,
    text: str,
    repeat_hours: int,
    media_id: str | None = None,
    media_type: str | None = None,
    is_vip: bool = False,
    stars: int = 0,
) -> int:
    """Create a recurring broadcast. Returns the new record ID."""
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO recurring_broadcasts
               (target, text, media_id, media_type, is_vip, stars, repeat_hours, is_active, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (target, text, media_id, media_type, int(is_vip), stars, repeat_hours, datetime.now()),
        )
        await db.commit()
        return cursor.lastrowid


async def list_recurring_broadcasts() -> list[tuple]:
    """Return all recurring broadcasts as rows (id, target, repeat_hours, is_active, text, ...)."""
    async with get_db() as db:
        async with db.execute(
            "SELECT id, target, repeat_hours, is_active, text FROM recurring_broadcasts ORDER BY id DESC"
        ) as cursor:
            return await cursor.fetchall()


async def get_active_recurring_broadcasts() -> list[tuple]:
    """Return active recurring broadcasts with full info for execution."""
    async with get_db() as db:
        async with db.execute(
            "SELECT id, target, text, media_id, media_type, is_vip, stars, repeat_hours, last_broadcast_at "
            "FROM recurring_broadcasts WHERE is_active=1"
        ) as cursor:
            return await cursor.fetchall()


async def set_recurring_broadcast_active(rb_id: int, active: bool) -> None:
    """Enable or disable a recurring broadcast."""
    async with get_db() as db:
        await db.execute(
            "UPDATE recurring_broadcasts SET is_active=? WHERE id=?",
            (1 if active else 0, rb_id),
        )
        await db.commit()


async def delete_recurring_broadcast(rb_id: int) -> None:
    """Permanently delete a recurring broadcast."""
    async with get_db() as db:
        await db.execute("DELETE FROM recurring_broadcasts WHERE id=?", (rb_id,))
        await db.commit()


async def update_recurring_broadcast_time(rb_id: int) -> None:
    """Update last_broadcast_at to now (after successful send)."""
    async with get_db() as db:
        await db.execute(
            "UPDATE recurring_broadcasts SET last_broadcast_at=? WHERE id=?",
            (datetime.now(), rb_id),
        )
        await db.commit()
