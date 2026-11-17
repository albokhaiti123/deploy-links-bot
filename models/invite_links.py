"""
Database models and business queries for:
  1. Owner Invite Links (permanent & temporary, manual pause/resume, delete)
  2. User Permanent Referral Links (generated on first button click, persisted forever)
"""

import secrets
from datetime import datetime, timedelta
from core.database import get_db


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _compute_effective_status(row_dict: dict, now_str: str | None = None) -> dict:
    """Compute effective_status ('active', 'paused', or 'expired') for an owner invite link."""
    now_val = now_str or _now_str()
    status = row_dict.get("status", "active")
    link_type = row_dict.get("link_type", "permanent")
    expires_at = row_dict.get("expires_at")
    if status == "paused":
        effective = "paused"
    elif link_type == "temporary" and expires_at:
        norm_exp = str(expires_at).replace("T", " ")[:19]
        effective = "expired" if norm_exp <= now_val else "active"
    else:
        effective = "active"
    row_dict["effective_status"] = effective
    return row_dict


async def create_owner_invite_link(
    label: str | None = None,
    link_type: str = "permanent",
    duration_hours: int | None = None,
    created_by: int | None = None,
) -> dict:
    """Create a permanent or temporary invite link for the bot owner."""
    if link_type not in ("permanent", "temporary"):
        raise ValueError("link_type must be 'permanent' or 'temporary'")

    now_str = _now_str()
    expires_at = None
    if link_type == "temporary":
        if not duration_hours or duration_hours <= 0:
            raise ValueError("duration_hours must be > 0 for temporary links")
        expires_at = (datetime.now() + timedelta(hours=int(duration_hours))).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    async with get_db() as db:
        for _ in range(10):
            code = secrets.token_hex(4)
            async with db.execute(
                "SELECT 1 FROM owner_invite_links WHERE code = ?", (code,)
            ) as c:
                if not await c.fetchone():
                    break
        cursor = await db.execute(
            """
            INSERT INTO owner_invite_links
                (code, label, link_type, expires_at, status, clicks_count, joins_count, created_by, created_at)
            VALUES (?, ?, ?, ?, 'active', 0, 0, ?, ?)
            """,
            (code, label, link_type, expires_at, created_by, now_str),
        )
        link_id = cursor.lastrowid
        await db.commit()

    return await get_owner_invite_link(link_id)


async def get_owner_invite_link(link_id: int) -> dict | None:
    """Fetch a single owner invite link by ID."""
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM owner_invite_links WHERE id = ?", (link_id,)
        ) as c:
            row = await c.fetchone()
            if not row:
                return None
            cols = [d[0] for d in c.description]
            return _compute_effective_status(dict(zip(cols, row)))


async def get_owner_invite_link_by_code(code: str) -> dict | None:
    """Fetch a single owner invite link by its unique code."""
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM owner_invite_links WHERE code = ?", (code,)
        ) as c:
            row = await c.fetchone()
            if not row:
                return None
            cols = [d[0] for d in c.description]
            return _compute_effective_status(dict(zip(cols, row)))


async def list_owner_invite_links() -> list[dict]:
    """Return all owner invite links ordered newest first."""
    now_str = _now_str()
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM owner_invite_links ORDER BY id DESC"
        ) as c:
            rows = await c.fetchall()
            cols = [d[0] for d in c.description]
    return [_compute_effective_status(dict(zip(cols, r)), now_str) for r in rows]


async def set_owner_invite_status(link_id: int, status: str) -> bool:
    """Manually pause ('paused') or resume ('active') an owner invite link."""
    if status not in ("active", "paused"):
        raise ValueError("status must be 'active' or 'paused'")
    async with get_db() as db:
        cursor = await db.execute(
            "UPDATE owner_invite_links SET status = ? WHERE id = ?",
            (status, link_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def delete_owner_invite_link(link_id: int) -> bool:
    """Permanently delete an owner invite link."""
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM owner_invite_links WHERE id = ?", (link_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def process_owner_invite_join(
    code: str, user_id: int
) -> tuple[bool, str, dict | None]:
    """
    Validate and record a user joining via an owner invite link (`inv_<code>`).
    Returns (is_valid, reason, link_dict).
    reason in ('active', 'not_found', 'paused', 'expired').
    """
    link = await get_owner_invite_link_by_code(code)
    if not link:
        return False, "not_found", None

    eff_status = link["effective_status"]
    if eff_status == "paused":
        return False, "paused", link
    if eff_status == "expired":
        return False, "expired", link

    now_str = _now_str()
    async with get_db() as db:
        await db.execute(
            "UPDATE owner_invite_links SET clicks_count = clicks_count + 1 WHERE id = ?",
            (link["id"],),
        )
        ins = await db.execute(
            """
            INSERT OR IGNORE INTO invite_join_logs (user_id, source_type, source_code, joined_at)
            VALUES (?, 'owner', ?, ?)
            """,
            (user_id, code, now_str),
        )
        if ins.rowcount > 0:
            await db.execute(
                "UPDATE owner_invite_links SET joins_count = joins_count + 1 WHERE id = ?",
                (link["id"],),
            )
        await db.commit()

    updated = await get_owner_invite_link(link["id"])
    return True, "active", updated


async def get_user_referral(user_id: int) -> dict | None:
    """Return existing referral record for a user if already generated, else None."""
    async with get_db() as db:
        async with db.execute(
            "SELECT user_id, ref_code, referrals_count, created_at "
            "FROM user_referral_links WHERE user_id = ?",
            (user_id,),
        ) as c:
            row = await c.fetchone()
            if not row:
                return None
            cols = [d[0] for d in c.description]
            return dict(zip(cols, row))


async def get_or_create_user_referral(user_id: int) -> dict:
    """
    Atomically retrieve the user's permanent referral link, or generate and save it
    in the background on their very first click.
    """
    now_str = _now_str()
    async with get_db() as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await db.execute(
                "INSERT OR IGNORE INTO users (telegram_id, created_at) VALUES (?, ?)",
                (user_id, now_str),
            )
            async with db.execute(
                "SELECT user_id, ref_code, referrals_count, created_at "
                "FROM user_referral_links WHERE user_id = ?",
                (user_id,),
            ) as c:
                row = await c.fetchone()
                if row:
                    cols = [d[0] for d in c.description]
                    await db.commit()
                    return dict(zip(cols, row))

            for _ in range(10):
                ref_code = f"u{user_id}_{secrets.token_hex(3)}"
                async with db.execute(
                    "SELECT 1 FROM user_referral_links WHERE ref_code = ?", (ref_code,)
                ) as chk:
                    if not await chk.fetchone():
                        break

            await db.execute(
                """
                INSERT INTO user_referral_links (user_id, ref_code, referrals_count, created_at)
                VALUES (?, ?, 0, ?)
                """,
                (user_id, ref_code, now_str),
            )
            await db.commit()
            return {
                "user_id": user_id,
                "ref_code": ref_code,
                "referrals_count": 0,
                "created_at": now_str,
            }
        except Exception:
            await db.rollback()
            raise


async def process_user_referral_join(
    ref_code: str, new_user_id: int
) -> tuple[bool, str, int | None]:
    """
    Process a user starting the bot via `ref_<ref_code>`.
    Returns (counted, reason, referrer_user_id).
    reason in ('counted', 'not_found', 'self_referral', 'already_counted').
    """
    now_str = _now_str()
    async with get_db() as db:
        async with db.execute(
            "SELECT user_id FROM user_referral_links WHERE ref_code = ?",
            (ref_code,),
        ) as c:
            row = await c.fetchone()
            if not row:
                return False, "not_found", None
            referrer_id = int(row[0])

        if referrer_id == int(new_user_id):
            return False, "self_referral", referrer_id

        ins = await db.execute(
            """
            INSERT OR IGNORE INTO invite_join_logs (user_id, source_type, source_code, joined_at)
            VALUES (?, 'referral', ?, ?)
            """,
            (new_user_id, ref_code, now_str),
        )
        if ins.rowcount == 0:
            await db.commit()
            return False, "already_counted", referrer_id

        await db.execute(
            "UPDATE user_referral_links SET referrals_count = referrals_count + 1 WHERE user_id = ?",
            (referrer_id,),
        )
        await db.execute(
            "INSERT INTO events (chat_id, telegram_user_id, event_type, created_at) VALUES (0, ?, 'referral_joined', ?)",
            (new_user_id, now_str),
        )
        await db.commit()
        return True, "counted", referrer_id
