"""
Custom buttons model — CRUD for inline URL buttons.

The `context` field determines where buttons appear:
  - "promo"           → Group promo messages
  - "welcome"         → Private /start welcome message
  - "campaign_<id>"   → Specific campaign promo
"""

from datetime import datetime

from core.database import get_db


async def get_buttons(context: str, active_only: bool = True) -> list[dict]:
    """Get buttons for a context, ordered by position."""
    where = "WHERE context = ?" + (" AND is_active = 1" if active_only else "")
    async with get_db() as db:
        async with db.execute(
            f"SELECT id, context, label, url, position, is_active FROM custom_buttons {where} ORDER BY position ASC",
            (context,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [
        {"id": r[0], "context": r[1], "label": r[2], "url": r[3], "position": r[4], "is_active": r[5]}
        for r in rows
    ]


async def add_button(context: str, label: str, url: str) -> int:
    """Add a new button. Returns the new ID."""
    async with get_db() as db:
        # Get next position
        async with db.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM custom_buttons WHERE context = ?",
            (context,),
        ) as cursor:
            pos = (await cursor.fetchone())[0]
        cursor = await db.execute(
            "INSERT INTO custom_buttons (context, label, url, position, is_active, created_at) VALUES (?, ?, ?, ?, 1, ?)",
            (context, label, url, pos, datetime.now()),
        )
        await db.commit()
        return cursor.lastrowid


async def remove_button(button_id: int) -> None:
    """Delete a button permanently."""
    async with get_db() as db:
        await db.execute("DELETE FROM custom_buttons WHERE id = ?", (button_id,))
        await db.commit()


async def toggle_button(button_id: int) -> bool:
    """Toggle button active/inactive. Returns new state."""
    async with get_db() as db:
        async with db.execute(
            "SELECT is_active FROM custom_buttons WHERE id = ?", (button_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False
        new_state = 0 if row[0] else 1
        await db.execute(
            "UPDATE custom_buttons SET is_active = ? WHERE id = ?", (new_state, button_id)
        )
        await db.commit()
        return bool(new_state)


async def update_button(button_id: int, label: str, url: str) -> None:
    """Update a button's label and URL."""
    async with get_db() as db:
        await db.execute(
            "UPDATE custom_buttons SET label = ?, url = ? WHERE id = ?",
            (label, url, button_id),
        )
        await db.commit()


async def count_buttons(context: str) -> int:
    """Count total buttons for a context."""
    async with get_db() as db:
        async with db.execute(
            "SELECT COUNT(*) FROM custom_buttons WHERE context = ?", (context,)
        ) as cursor:
            return (await cursor.fetchone())[0]
