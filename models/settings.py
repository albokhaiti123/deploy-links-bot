"""
Settings model — key-value configuration stored in the `settings` table.

Usage:
    from models.settings import get_setting, set_setting

    value = await get_setting("promo_enabled")
    await set_setting("promo_enabled", "false")
"""

from core.database import get_db


async def get_setting(key: str) -> str:
    """Get a setting value by key. Returns empty string if not found."""
    async with get_db() as db:
        async with db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else ""


async def set_setting(key: str, value: str) -> None:
    """Update an existing setting value."""
    async with get_db() as db:
        await db.execute(
            "UPDATE settings SET value = ? WHERE key = ?", (value, key)
        )
        await db.commit()


async def get_many_settings(*keys: str) -> dict[str, str]:
    """
    Fetch multiple settings in a single DB call.
    Returns a dict mapping key → value (empty string for missing keys).
    """
    if not keys:
        return {}
    placeholders = ",".join("?" for _ in keys)
    async with get_db() as db:
        async with db.execute(
            f"SELECT key, value FROM settings WHERE key IN ({placeholders})",
            keys,
        ) as cursor:
            rows = await cursor.fetchall()
    result = {k: "" for k in keys}
    for k, v in rows:
        result[k] = v
    return result
