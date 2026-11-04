"""
Groups model — CRUD for the `groups` table.
"""

from datetime import datetime

from core.database import get_db


async def upsert_group(
    chat_id: int,
    title: str | None,
    chat_type: str,
    added_by: int | None = None,
) -> None:
    """Insert a new group or update if it already exists (reactivate).
    reward_owner_id is set only on INSERT, never overwritten.
    """
    now = datetime.now()
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO groups (chat_id, title, chat_type, status, added_at, updated_at, added_by, reward_owner_id)
            VALUES (?, ?, ?, 'active', ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                status='active', title=?, updated_at=?, added_by=?
                -- reward_owner_id intentionally NOT updated on conflict
            """,
            (chat_id, title, chat_type, now, now, added_by, added_by,
             title, now, added_by),
        )
        await db.commit()


async def update_group_health(
    chat_id: int,
    health_status: str,
    last_error: str | None = None,
    increment_fail: bool = False,
) -> None:
    """Update group health status and optionally increment fail counter."""
    now = datetime.now()
    async with get_db() as db:
        if increment_fail:
            await db.execute(
                """UPDATE groups SET health_status=?, last_error=?, last_checked_at=?,
                   fail_count=COALESCE(fail_count,0)+1
                   WHERE chat_id=?""",
                (health_status, last_error, now, chat_id),
            )
        else:
            await db.execute(
                """UPDATE groups SET health_status=?, last_error=?, last_checked_at=?,
                   fail_count=0
                   WHERE chat_id=?""",
                (health_status, last_error, now, chat_id),
            )
        await db.commit()



async def deactivate_group(chat_id: int) -> None:
    """Mark a group as inactive (bot removed)."""
    async with get_db() as db:
        await db.execute(
            "UPDATE groups SET status='inactive', updated_at=? WHERE chat_id=?",
            (datetime.now(), chat_id),
        )
        await db.commit()


async def get_active_group_ids() -> list[int]:
    """Return chat_ids of all active groups."""
    async with get_db() as db:
        async with db.execute(
            "SELECT chat_id FROM groups WHERE status='active'"
        ) as cursor:
            return [row[0] for row in await cursor.fetchall()]


async def get_recent_groups(limit: int = 20) -> list[tuple]:
    """Return recent groups as (chat_id, title, status, added_at)."""
    async with get_db() as db:
        async with db.execute(
            "SELECT chat_id, title, status, added_at FROM groups ORDER BY added_at DESC LIMIT ?",
            (limit,),
        ) as cursor:
            return await cursor.fetchall()


async def get_group_counts() -> tuple[int, int]:
    """Return (active_count, total_count)."""
    async with get_db() as db:
        async with db.execute("SELECT COUNT(*) FROM groups WHERE status='active'") as c:
            active = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM groups") as c:
            total = (await c.fetchone())[0]
    return active, total


async def get_last_promo_msg(chat_id: int) -> int | None:
    """Get the last promo message_id for a group."""
    async with get_db() as db:
        async with db.execute(
            "SELECT last_promo_msg_id FROM groups WHERE chat_id=?", (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row and row[0] else None


async def update_last_promo_msg(chat_id: int, message_id: int) -> None:
    """Store the last promo message_id for a group."""
    async with get_db() as db:
        await db.execute(
            "UPDATE groups SET last_promo_msg_id=? WHERE chat_id=?",
            (message_id, chat_id),
        )
        await db.commit()


async def get_user_active_groups(user_id: int) -> list[tuple[int, str | None, str | None]]:
    """Return (chat_id, title, health_status) of active groups owned by user (reward_owner_id)."""
    async with get_db() as db:
        async with db.execute(
            "SELECT chat_id, title, health_status FROM groups "
            "WHERE reward_owner_id = ? AND status = 'active'",
            (user_id,),
        ) as cursor:
            return await cursor.fetchall()


async def get_all_groups_paginated(
    limit: int = 20, offset: int = 0, health_filter: str | None = None
) -> list[tuple]:
    """Owner-level: return all groups (chat_id, title, status, health_status, reward_owner_id, fail_count).
    Optionally filtered by health_status.
    """
    async with get_db() as db:
        if health_filter:
            async with db.execute(
                "SELECT chat_id, title, status, health_status, reward_owner_id, fail_count "
                "FROM groups WHERE health_status=? ORDER BY added_at DESC LIMIT ? OFFSET ?",
                (health_filter, limit, offset),
            ) as cursor:
                return await cursor.fetchall()
        else:
            async with db.execute(
                "SELECT chat_id, title, status, health_status, reward_owner_id, fail_count "
                "FROM groups ORDER BY added_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ) as cursor:
                return await cursor.fetchall()


async def get_group_by_id(chat_id: int) -> tuple | None:
    """Return full group row or None."""
    async with get_db() as db:
        async with db.execute(
            "SELECT chat_id, title, status, health_status, reward_owner_id, added_by, fail_count "
            "FROM groups WHERE chat_id=?",
            (chat_id,),
        ) as cursor:
            return await cursor.fetchone()

