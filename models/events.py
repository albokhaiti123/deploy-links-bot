"""
Events model — event logging and statistics queries.
"""

from datetime import datetime

from core.database import get_db


async def log_event(chat_id: int, user_id: int, event_type: str) -> None:
    """Log an event (promo_sent, campaign viewed, etc.)."""
    async with get_db() as db:
        await db.execute(
            "INSERT INTO events (chat_id, telegram_user_id, event_type, created_at) VALUES (?, ?, ?, ?)",
            (chat_id, user_id, event_type, datetime.now()),
        )
        await db.commit()


async def count_events(event_type: str) -> int:
    """Count total events of a given type."""
    async with get_db() as db:
        async with db.execute(
            "SELECT COUNT(*) FROM events WHERE event_type=?", (event_type,)
        ) as cursor:
            return (await cursor.fetchone())[0]


async def count_events_since(event_type: str, since: str) -> int:
    """Count events of a type since a datetime expression."""
    async with get_db() as db:
        async with db.execute(
            f"SELECT COUNT(*) FROM events WHERE event_type=? AND created_at >= {since}",
            (event_type,),
        ) as cursor:
            return (await cursor.fetchone())[0]
