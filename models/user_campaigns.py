"""
User campaigns model — CRUD for user_campaigns, quota, deliveries, execution claims.

All write operations that check ownership are enforced at service layer (services/user_broadcast.py).
This module provides raw DB access; callers must enforce authorization.
"""

import json
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from core.config import QUOTA_TIMEZONE
from core.database import get_db

# Campaign statuses
CURRENT_STATUSES = ("active", "running", "paused", "suspended_admin")
TERMINAL_STATUSES = ("completed", "replaced", "deleted")

CLAIM_TTL_MINUTES = 30


def _today(tz: str = QUOTA_TIMEZONE) -> str:
    return datetime.now(tz=ZoneInfo(tz)).date().isoformat()


# ── Quota ────────────────────────────────────────────────────────────────────

async def get_quota(user_id: int, today: str | None = None) -> int:
    """Return campaigns created today for user."""
    today = today or _today()
    async with get_db() as db:
        async with db.execute(
            "SELECT campaigns_created FROM user_campaign_quota WHERE user_id=? AND quota_date=?",
            (user_id, today),
        ) as c:
            row = await c.fetchone()
    return row[0] if row else 0


# ── Campaign CRUD ────────────────────────────────────────────────────────────

async def get_current_campaign(user_id: int) -> dict | None:
    """Return the user's current campaign (any CURRENT_STATUSES) or None."""
    async with get_db() as db:
        placeholders = ",".join("?" * len(CURRENT_STATUSES))
        async with db.execute(
            f"SELECT * FROM user_campaigns WHERE owner_user_id=? AND status IN ({placeholders})",
            (user_id, *CURRENT_STATUSES),
        ) as c:
            row = await c.fetchone()
            if not row:
                return None
            cols = [d[0] for d in c.description]
            return dict(zip(cols, row))


async def get_campaign_by_id(campaign_id: int) -> dict | None:
    """Return campaign by id as dict, or None."""
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM user_campaigns WHERE id=?", (campaign_id,)
        ) as c:
            row = await c.fetchone()
            if not row:
                return None
            cols = [d[0] for d in c.description]
            return dict(zip(cols, row))


async def create_campaign_atomic(
    user_id: int,
    text: str | None,
    photo_file_id: str | None,
    buttons_json: str | None,
    target_groups_json: str,
    mode: str,
    repeat_hours: int,
    auto_delete_seconds: int,
    system_generation: int,
) -> int | None:
    """
    Atomically:
    1. Check daily quota (max 2).
    2. Mark old current campaign as 'replaced'.
    3. Clear its execution claim.
    4. Insert new campaign as 'active'.
    5. Increment quota.
    Returns new campaign id, or None if quota exhausted.
    Raises sqlite IntegrityError if partial index violation (concurrent call).
    """
    today = _today()
    now = datetime.now()

    async with get_db() as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            # 1. Quota check
            async with db.execute(
                "SELECT campaigns_created FROM user_campaign_quota WHERE user_id=? AND quota_date=?",
                (user_id, today),
            ) as c:
                row = await c.fetchone()
            count = row[0] if row else 0
            if count >= 2:
                await db.execute("ROLLBACK")
                return None

            # 2. Find and replace current campaign
            placeholders = ",".join("?" * len(CURRENT_STATUSES))
            async with db.execute(
                f"SELECT id FROM user_campaigns WHERE owner_user_id=? AND status IN ({placeholders})",
                (user_id, *CURRENT_STATUSES),
            ) as c:
                old = await c.fetchone()

            if old:
                old_id = old[0]
                await db.execute(
                    "UPDATE user_campaigns SET status='replaced', completed_at=?, run_id=NULL WHERE id=?",
                    (now, old_id),
                )
                await db.execute(
                    "DELETE FROM user_campaign_execution_claims WHERE campaign_id=?",
                    (old_id,),
                )

            # 3. Insert new
            cursor = await db.execute(
                """INSERT INTO user_campaigns
                   (owner_user_id, text, photo_file_id, buttons_json,
                    target_groups_json, mode, repeat_hours, auto_delete_seconds,
                    status, system_generation, created_at, activated_at, quota_date)
                   VALUES (?,?,?,?,?,?,?,?,'active',?,?,?,?)""",
                (user_id, text, photo_file_id, buttons_json,
                 target_groups_json, mode, repeat_hours, auto_delete_seconds,
                 system_generation, now, now, today),
            )
            new_id = cursor.lastrowid

            # 4. Increment quota
            await db.execute(
                "INSERT INTO user_campaign_quota (user_id, quota_date, campaigns_created) VALUES (?,?,1) "
                "ON CONFLICT(user_id, quota_date) DO UPDATE SET campaigns_created=campaigns_created+1",
                (user_id, today),
            )

            await db.commit()
            return new_id
        except Exception:
            await db.execute("ROLLBACK")
            raise


async def update_campaign_status(campaign_id: int, status: str) -> None:
    async with get_db() as db:
        extra = ", completed_at=?" if status in ("completed", "replaced", "deleted") else ""
        args = [status]
        if extra:
            args.append(datetime.now())
        args.append(campaign_id)
        await db.execute(
            f"UPDATE user_campaigns SET status=?{extra} WHERE id=?", args
        )
        await db.commit()


async def update_campaign_next_run(campaign_id: int, next_run_at: datetime) -> None:
    async with get_db() as db:
        await db.execute(
            "UPDATE user_campaigns SET next_run_at=?, last_run_at=? WHERE id=?",
            (next_run_at, datetime.now(), campaign_id),
        )
        await db.commit()


async def set_campaign_run_id(campaign_id: int, run_id: str | None) -> None:
    async with get_db() as db:
        await db.execute(
            "UPDATE user_campaigns SET run_id=? WHERE id=?", (run_id, campaign_id)
        )
        await db.commit()


async def get_due_recurring_campaigns() -> list[dict]:
    """Return recurring active campaigns where next_run_at <= now."""
    now = datetime.now().isoformat()
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM user_campaigns WHERE mode='recurring' AND status='active' "
            "AND (next_run_at IS NULL OR next_run_at <= ?)",
            (now,),
        ) as c:
            rows = await c.fetchall()
            cols = [d[0] for d in c.description]
    return [dict(zip(cols, r)) for r in rows]


async def suspend_all_active_campaigns() -> int:
    """Owner global disable: suspend all current campaigns. Returns count.
    Clears run_id and deletes execution claims so running workers detect invalidation.
    """
    async with get_db() as db:
        placeholders = ",".join("?" * len(CURRENT_STATUSES))
        async with db.execute(
            f"SELECT COUNT(*) FROM user_campaigns WHERE status IN ({placeholders})",
            CURRENT_STATUSES,
        ) as c:
            count = (await c.fetchone())[0]
        if count > 0:
            # Collect campaign ids to delete claims
            async with db.execute(
                f"SELECT id FROM user_campaigns WHERE status IN ({placeholders})",
                CURRENT_STATUSES,
            ) as c:
                ids = [r[0] for r in await c.fetchall()]
            # Clear run_id so workers detect invalidation on next fencing check
            await db.execute(
                f"UPDATE user_campaigns SET status='suspended_admin', run_id=NULL "
                f"WHERE status IN ({placeholders})",
                CURRENT_STATUSES,
            )
            # Delete all execution claims for suspended campaigns
            if ids:
                id_placeholders = ",".join("?" * len(ids))
                await db.execute(
                    f"DELETE FROM user_campaign_execution_claims WHERE campaign_id IN ({id_placeholders})",
                    ids,
                )
            await db.commit()
    return count


# ── Execution Claims ─────────────────────────────────────────────────────────

async def claim_execution(campaign_id: int, run_id: str) -> bool:
    """Attempt to claim execution. Returns False if another valid claim exists.
    Uses BEGIN IMMEDIATE to atomically delete expired claim and insert new one.
    All timestamps stored and compared as identical format strings to prevent ASCII ordering bugs.
    """
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    expires_str = (now + timedelta(minutes=CLAIM_TTL_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")

    async with get_db() as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            # Remove expired claim if any (only if expires_at < now)
            await db.execute(
                "DELETE FROM user_campaign_execution_claims WHERE campaign_id=? AND expires_at < ?",
                (campaign_id, now_str),
            )
            await db.execute(
                "INSERT INTO user_campaign_execution_claims "
                "(campaign_id, run_id, claimed_at, heartbeat_at, expires_at) VALUES (?,?,?,?,?)",
                (campaign_id, run_id, now_str, now_str, expires_str),
            )
            await db.commit()
            return True
        except Exception:
            try:
                await db.execute("ROLLBACK")
            except Exception:
                pass
            return False


async def heartbeat_claim(campaign_id: int, run_id: str) -> None:
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    expires_str = (now + timedelta(minutes=CLAIM_TTL_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
    async with get_db() as db:
        await db.execute(
            "UPDATE user_campaign_execution_claims SET heartbeat_at=?, expires_at=? "
            "WHERE campaign_id=? AND run_id=?",
            (now_str, expires_str, campaign_id, run_id),
        )
        await db.commit()


async def release_claim(campaign_id: int) -> None:
    async with get_db() as db:
        await db.execute(
            "DELETE FROM user_campaign_execution_claims WHERE campaign_id=?", (campaign_id,)
        )
        await db.commit()


async def recover_stale_claims() -> None:
    """On startup: clear expired claims and reset those campaigns to 'active'."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with get_db() as db:
        async with db.execute(
            "SELECT campaign_id FROM user_campaign_execution_claims WHERE expires_at < ?", (now_str,)
        ) as c:
            stale = [r[0] for r in await c.fetchall()]
        if stale:
            for cid in stale:
                await db.execute(
                    "UPDATE user_campaigns SET status='active', run_id=NULL WHERE id=? AND status='running'",
                    (cid,),
                )
            await db.execute(
                f"DELETE FROM user_campaign_execution_claims WHERE campaign_id IN "
                f"({','.join('?'*len(stale))})",
                stale,
            )
            await db.commit()



# ── Deliveries ───────────────────────────────────────────────────────────────

async def record_delivery(
    campaign_id: int, run_id: str, chat_id: int, status: str, error_code: str | None = None
) -> None:
    now = datetime.now()
    confirmed = now if status == "sent" else None
    async with get_db() as db:
        await db.execute(
            "INSERT INTO user_campaign_deliveries "
            "(campaign_id, run_id, chat_id, status, error_code, attempted_at, confirmed_at) "
            "VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(campaign_id, run_id, chat_id) DO UPDATE SET status=?, error_code=?, confirmed_at=?",
            (campaign_id, run_id, chat_id, status, error_code, now, confirmed,
             status, error_code, confirmed),
        )
        await db.commit()


async def get_delivery_status(campaign_id: int, run_id: str, chat_id: int) -> str | None:
    async with get_db() as db:
        async with db.execute(
            "SELECT status FROM user_campaign_deliveries WHERE campaign_id=? AND run_id=? AND chat_id=?",
            (campaign_id, run_id, chat_id),
        ) as c:
            row = await c.fetchone()
    return row[0] if row else None


async def get_delivery_stats(campaign_id: int) -> dict:
    async with get_db() as db:
        async with db.execute(
            "SELECT status, COUNT(*) FROM user_campaign_deliveries WHERE campaign_id=? GROUP BY status",
            (campaign_id,),
        ) as c:
            rows = await c.fetchall()
    return {r[0]: r[1] for r in rows}
