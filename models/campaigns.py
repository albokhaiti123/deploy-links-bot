"""
Campaigns model — CRUD for campaigns, user progress, and campaign groups.

Tables:
  - campaigns: campaign definitions
  - campaign_user_progress: per-user progress toward unlocking
  - campaign_groups: verified groups per user per campaign
"""

from datetime import datetime

from core.database import get_db


# ── Campaign CRUD ────────────────────────────────────────────────────────────

async def get_campaign(campaign_id: int) -> dict | None:
    """Get campaign by ID as a dict. Returns None if not found."""
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            cols = [desc[0] for desc in cursor.description]
            return dict(zip(cols, row))


async def create_campaign(data: dict) -> int:
    """Create a new campaign from wizard data. Returns the new campaign ID."""
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO campaigns
               (name, promo_text, media_type, media_file_id, button_text, required_groups,
                unlock_content, unlock_media_type, unlock_media_file_id, unlock_delete_seconds,
                mode, repeat_hours, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)""",
            (
                data["name"], data["promo_text"],
                data.get("media_type"), data.get("media_file_id"),
                data["button_text"], data["required_groups"],
                data["unlock_content"],
                data.get("unlock_media_type"), data.get("unlock_media_file_id"),
                data.get("unlock_delete_seconds", 0),
                data.get("mode", "manual"), data.get("repeat_hours", 0),
                datetime.now(), datetime.now(),
            ),
        )
        await db.commit()
        return cursor.lastrowid


async def update_campaign_status(campaign_id: int, status: str) -> None:
    """Update campaign status (active/paused/deleted)."""
    async with get_db() as db:
        await db.execute(
            "UPDATE campaigns SET status=?, updated_at=? WHERE id=?",
            (status, datetime.now(), campaign_id),
        )
        await db.commit()


async def set_campaign_recurring(campaign_id: int, active: bool) -> None:
    """Enable or disable recurring broadcast for a campaign."""
    async with get_db() as db:
        await db.execute(
            "UPDATE campaigns SET recurring_active=?, updated_at=? WHERE id=?",
            (1 if active else 0, datetime.now(), campaign_id),
        )
        await db.commit()


async def update_campaign_last_broadcast(campaign_id: int) -> None:
    """Update last_broadcast_at to now."""
    async with get_db() as db:
        await db.execute(
            "UPDATE campaigns SET last_broadcast_at=? WHERE id=?",
            (datetime.now(), campaign_id),
        )
        await db.commit()


async def list_campaigns(exclude_deleted: bool = True, limit: int = 15) -> list[tuple]:
    """Return campaigns as (id, name, status, required_groups)."""
    where = "WHERE status != 'deleted'" if exclude_deleted else ""
    async with get_db() as db:
        async with db.execute(
            f"SELECT id, name, status, required_groups FROM campaigns {where} ORDER BY id DESC LIMIT ?",
            (limit,),
        ) as cursor:
            return await cursor.fetchall()


async def get_active_recurring_campaigns() -> list[tuple]:
    """Return recurring campaigns that are active and enabled, for background task."""
    async with get_db() as db:
        async with db.execute(
            "SELECT id, repeat_hours, last_broadcast_at FROM campaigns "
            "WHERE mode='recurring' AND recurring_active=1 AND status='active'"
        ) as cursor:
            return await cursor.fetchall()


# ── User Progress ────────────────────────────────────────────────────────────

async def get_user_progress(campaign_id: int, user_id: int) -> tuple[int, str] | None:
    """Return (verified_count, status) for a user in a campaign, or None."""
    async with get_db() as db:
        async with db.execute(
            "SELECT verified_count, status FROM campaign_user_progress WHERE campaign_id=? AND user_id=?",
            (campaign_id, user_id),
        ) as cursor:
            return await cursor.fetchone()


async def ensure_user_progress(campaign_id: int, user_id: int) -> tuple[int, str]:
    """Get or create user progress. Returns (verified_count, status)."""
    row = await get_user_progress(campaign_id, user_id)
    if row:
        return row
    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO campaign_user_progress "
            "(campaign_id, user_id, verified_count, status, created_at, updated_at) "
            "VALUES (?, ?, 0, 'in_progress', ?, ?)",
            (campaign_id, user_id, datetime.now(), datetime.now()),
        )
        await db.commit()
    return (0, "in_progress")


async def update_user_progress(campaign_id: int, user_id: int, verified_count: int, status: str) -> None:
    """Upsert user progress with new count and status."""
    now = datetime.now()
    async with get_db() as db:
        await db.execute(
            """INSERT INTO campaign_user_progress
               (campaign_id, user_id, verified_count, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(campaign_id, user_id) DO UPDATE SET verified_count=?, status=?, updated_at=?""",
            (campaign_id, user_id, verified_count, status, now, now,
             verified_count, status, now),
        )
        await db.commit()


# ── Campaign Groups (verification) ──────────────────────────────────────────

async def get_verified_group_ids(campaign_id: int, user_id: int) -> set[int]:
    """Return set of chat_ids already verified for a user in a campaign."""
    async with get_db() as db:
        async with db.execute(
            "SELECT chat_id FROM campaign_groups WHERE campaign_id = ? AND user_id = ? AND verified = 1",
            (campaign_id, user_id),
        ) as cursor:
            return {row[0] for row in await cursor.fetchall()}


async def add_verified_group(
    campaign_id: int, user_id: int, chat_id: int, chat_title: str | None
) -> None:
    """Record a verified group for a user in a campaign."""
    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO campaign_groups "
            "(campaign_id, user_id, chat_id, chat_title, verified, verified_at) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            (campaign_id, user_id, chat_id, chat_title, datetime.now()),
        )
        await db.commit()


# ── Campaign Stats ───────────────────────────────────────────────────────────

async def get_campaign_stats(campaign_id: int) -> dict:
    """Return campaign statistics as a dict."""
    async with get_db() as db:
        stats = {}

        async with db.execute(
            "SELECT COUNT(*) FROM campaign_user_progress WHERE campaign_id=?",
            (campaign_id,),
        ) as c:
            stats["started"] = (await c.fetchone())[0]

        async with db.execute(
            "SELECT COUNT(*) FROM campaign_groups WHERE campaign_id=? AND verified=1",
            (campaign_id,),
        ) as c:
            stats["groups_added"] = (await c.fetchone())[0]

        async with db.execute(
            "SELECT COUNT(*) FROM campaign_user_progress WHERE campaign_id=? AND status='unlocked'",
            (campaign_id,),
        ) as c:
            stats["unlocked"] = (await c.fetchone())[0]

    return stats
