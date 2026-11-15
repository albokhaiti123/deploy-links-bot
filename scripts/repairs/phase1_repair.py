#!/usr/bin/env python3
"""
Phase 1 Repair Script — Deploy Links Bot
Addresses confirmed issues: ISS-01, ISS-02, ISS-03, ISS-04, ISS-06, ISS-11

Features:
  - Idempotent execution (safe to run multiple times)
  - Automatic backup before modification (.backups/phase1/)
  - AST syntax verification before writing any Python file
  - Supports --dry-run and --rollback modes
  - Safely migrates existing bot.db if present
"""

import argparse
import ast
import shutil
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKUP_DIR = PROJECT_ROOT / ".backups" / "phase1"

TARGET_FILES = [
    "core/database.py",
    "services/campaign.py",
    "models/user_campaigns.py",
    "handlers/user/my_campaign.py",
    "main.py",
    "tasks/background.py",
]


def verify_python_syntax(code: str, filepath: str) -> None:
    """Parse Python source with AST to guarantee zero syntax errors."""
    try:
        ast.parse(code, filename=filepath)
    except SyntaxError as exc:
        raise RuntimeError(f"AST syntax check failed for {filepath}: {exc}") from exc


def create_backups(dry_run: bool = False) -> None:
    """Backup target files and bot.db before applying changes."""
    if dry_run:
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for rel_path in TARGET_FILES:
        src = PROJECT_ROOT / rel_path
        dst = BACKUP_DIR / rel_path
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    db_file = PROJECT_ROOT / "bot.db"
    db_backup = BACKUP_DIR / "bot.db"
    if db_file.exists() and not db_backup.exists():
        shutil.copy2(db_file, db_backup)


def rollback() -> int:
    """Restore all backed-up files from .backups/phase1/."""
    if not BACKUP_DIR.exists():
        print("[ROLLBACK] No backup directory found at .backups/phase1/")
        return 1
    for rel_path in TARGET_FILES:
        bkp = BACKUP_DIR / rel_path
        dst = PROJECT_ROOT / rel_path
        if bkp.exists():
            shutil.copy2(bkp, dst)
            print(f"[ROLLBACK] Restored {rel_path}")
    db_backup = BACKUP_DIR / "bot.db"
    if db_backup.exists():
        shutil.copy2(db_backup, PROJECT_ROOT / "bot.db")
        print("[ROLLBACK] Restored bot.db")
    print("[ROLLBACK] Phase 1 rollback completed successfully.")
    return 0


def patch_core_database(content: str) -> tuple[str, list[str]]:
    """Apply ISS-06 (SQLite WAL, busy_timeout, foreign_keys, indexes) & ISS-03 (reward_owner_id backfill)."""
    applied = []

    # 1. ISS-06: PRAGMAs in get_db()
    old_get_db = (
        '@asynccontextmanager\n'
        'async def get_db():\n'
        '    """Async context manager that yields an aiosqlite connection."""\n'
        '    db = await aiosqlite.connect(DB_NAME)\n'
        '    try:\n'
        '        yield db\n'
        '    finally:\n'
        '        await db.close()'
    )
    new_get_db = (
        '@asynccontextmanager\n'
        'async def get_db():\n'
        '    """Async context manager that yields an aiosqlite connection."""\n'
        '    db = await aiosqlite.connect(DB_NAME, timeout=30.0)\n'
        '    try:\n'
        '        await db.execute("PRAGMA journal_mode=WAL")\n'
        '        await db.execute("PRAGMA busy_timeout=5000")\n'
        '        await db.execute("PRAGMA foreign_keys=ON")\n'
        '        yield db\n'
        '    finally:\n'
        '        await db.close()'
    )
    if "PRAGMA journal_mode=WAL" not in content:
        if old_get_db not in content:
            raise RuntimeError("Could not locate expected get_db() block in core/database.py")
        content = content.replace(old_get_db, new_get_db, 1)
        applied.append("ISS-06: Enabled WAL mode, busy_timeout=5000, and foreign_keys=ON in get_db()")

    # 2. ISS-03 & ISS-06: Backfill reward_owner_id and add indexes in init_db()
    old_group_cols = (
        '        await _try_add_column(db, "groups", "last_checked_at", "TIMESTAMP")'
    )
    new_group_cols = (
        '        await _try_add_column(db, "groups", "last_checked_at", "TIMESTAMP")\n'
        '        # Backfill reward_owner_id from added_by for legacy groups (ISS-03)\n'
        '        await db.execute(\n'
        '            "UPDATE groups SET reward_owner_id = added_by "\n'
        '            "WHERE reward_owner_id IS NULL AND added_by IS NOT NULL"\n'
        '        )\n'
        '        await db.execute(\n'
        '            "CREATE INDEX IF NOT EXISTS idx_groups_reward_owner_status "\n'
        '            "ON groups(reward_owner_id, status)"\n'
        '        )'
    )
    if "UPDATE groups SET reward_owner_id = added_by" not in content:
        if old_group_cols not in content:
            raise RuntimeError("Could not locate groups migration block in core/database.py")
        content = content.replace(old_group_cols, new_group_cols, 1)
        applied.append("ISS-03: Added reward_owner_id backfill migration and index on groups")

    # 3. ISS-06: Indexes on events and broadcast_messages
    old_bm_table = (
        '        await db.execute("""\n'
        '            CREATE TABLE IF NOT EXISTS broadcast_messages (\n'
        '                id INTEGER PRIMARY KEY AUTOINCREMENT,\n'
        '                chat_id INTEGER,\n'
        '                message_id INTEGER,\n'
        '                delete_at TIMESTAMP\n'
        '            )\n'
        '        """)'
    )
    new_bm_table = (
        '        await db.execute("""\n'
        '            CREATE TABLE IF NOT EXISTS broadcast_messages (\n'
        '                id INTEGER PRIMARY KEY AUTOINCREMENT,\n'
        '                chat_id INTEGER,\n'
        '                message_id INTEGER,\n'
        '                delete_at TIMESTAMP\n'
        '            )\n'
        '        """)\n'
        '        await db.execute(\n'
        '            "CREATE INDEX IF NOT EXISTS idx_events_type_created "\n'
        '            "ON events(event_type, created_at)"\n'
        '        )\n'
        '        await db.execute(\n'
        '            "CREATE INDEX IF NOT EXISTS idx_broadcast_messages_delete_at "\n'
        '            "ON broadcast_messages(delete_at)"\n'
        '        )'
    )
    if "idx_broadcast_messages_delete_at" not in content:
        if old_bm_table not in content:
            raise RuntimeError("Could not locate broadcast_messages table block in core/database.py")
        content = content.replace(old_bm_table, new_bm_table, 1)
        applied.append("ISS-06: Added indexes on events(event_type, created_at) and broadcast_messages(delete_at)")

    return content, applied


def patch_services_campaign(content: str) -> tuple[str, list[str]]:
    """Apply ISS-01 fix in services/campaign.py (safe tuple unpacking)."""
    applied = []
    old_loop = (
        "    new_verified = 0\n"
        "    for chat_id, title in user_groups:\n"
        "        if chat_id in already_verified:"
    )
    new_loop = (
        "    new_verified = 0\n"
        "    for group_row in user_groups:\n"
        "        chat_id, title = group_row[0], group_row[1]\n"
        "        if chat_id in already_verified:"
    )
    if "for group_row in user_groups:" not in content:
        if old_loop not in content:
            raise RuntimeError("Could not locate user_groups loop in services/campaign.py")
        content = content.replace(old_loop, new_loop, 1)
        applied.append("ISS-01: Fixed 3-tuple unpacking in verify_campaign_groups()")
    return content, applied


def patch_models_user_campaigns(content: str) -> tuple[str, list[str]]:
    """Apply ISS-02, ISS-04, ISS-06 (FK user guard), and ISS-11 in models/user_campaigns.py."""
    applied = []

    # 1. ISS-06 FK safety: ensure user exists in `users` inside create_campaign_atomic
    old_begin = (
        '    async with get_db() as db:\n'
        '        await db.execute("BEGIN IMMEDIATE")\n'
        '        try:\n'
        '            # 1. Quota check'
    )
    new_begin = (
        '    async with get_db() as db:\n'
        '        await db.execute("BEGIN IMMEDIATE")\n'
        '        try:\n'
        '            # Ensure user row exists for FOREIGN KEY constraint safety\n'
        '            await db.execute(\n'
        '                "INSERT OR IGNORE INTO users (telegram_id, created_at) VALUES (?, ?)",\n'
        '                (user_id, now),\n'
        '            )\n'
        '            # 1. Quota check'
    )
    if "INSERT OR IGNORE INTO users (telegram_id, created_at)" not in content:
        if old_begin not in content:
            raise RuntimeError("Could not locate BEGIN IMMEDIATE block in create_campaign_atomic()")
        content = content.replace(old_begin, new_begin, 1)
        applied.append("ISS-06: Added automatic user row guard in create_campaign_atomic() for FK integrity")

    # 2. ISS-02 & ISS-04: Fix timestamp format in update_campaign_next_run, add resume_user_campaign, fix get_due_recurring_campaigns
    old_next_run_and_due = (
        'async def update_campaign_next_run(campaign_id: int, next_run_at: datetime) -> None:\n'
        '    async with get_db() as db:\n'
        '        await db.execute(\n'
        '            "UPDATE user_campaigns SET next_run_at=?, last_run_at=? WHERE id=?",\n'
        '            (next_run_at, datetime.now(), campaign_id),\n'
        '        )\n'
        '        await db.commit()\n'
        '\n'
        '\n'
        'async def set_campaign_run_id(campaign_id: int, run_id: str | None) -> None:\n'
        '    async with get_db() as db:\n'
        '        await db.execute(\n'
        '            "UPDATE user_campaigns SET run_id=? WHERE id=?", (run_id, campaign_id)\n'
        '        )\n'
        '        await db.commit()\n'
        '\n'
        '\n'
        'async def get_due_recurring_campaigns() -> list[dict]:\n'
        '    """Return recurring active campaigns where next_run_at <= now."""\n'
        '    now = datetime.now().isoformat()\n'
        '    async with get_db() as db:\n'
        '        async with db.execute(\n'
        '            "SELECT * FROM user_campaigns WHERE mode=\'recurring\' AND status=\'active\' "\n'
        '            "AND (next_run_at IS NULL OR next_run_at <= ?)",\n'
        '            (now,),\n'
        '        ) as c:\n'
        '            rows = await c.fetchall()\n'
        '            cols = [d[0] for d in c.description]\n'
        '    return [dict(zip(cols, r)) for r in rows]'
    )
    new_next_run_and_due = (
        'async def update_campaign_next_run(campaign_id: int, next_run_at: datetime) -> None:\n'
        '    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")\n'
        '    next_str = (\n'
        '        next_run_at.strftime("%Y-%m-%d %H:%M:%S")\n'
        '        if isinstance(next_run_at, datetime)\n'
        '        else str(next_run_at).replace("T", " ")[:19]\n'
        '    )\n'
        '    async with get_db() as db:\n'
        '        await db.execute(\n'
        '            "UPDATE user_campaigns SET next_run_at=?, last_run_at=? WHERE id=?",\n'
        '            (next_str, now_str, campaign_id),\n'
        '        )\n'
        '        await db.commit()\n'
        '\n'
        '\n'
        'async def resume_user_campaign(campaign_id: int, system_generation: int) -> None:\n'
        '    """Resume a paused or admin-suspended campaign and sync its system_generation."""\n'
        '    async with get_db() as db:\n'
        '        await db.execute(\n'
        '            "UPDATE user_campaigns SET status=\'active\', system_generation=? WHERE id=?",\n'
        '            (system_generation, campaign_id),\n'
        '        )\n'
        '        await db.commit()\n'
        '\n'
        '\n'
        'async def set_campaign_run_id(campaign_id: int, run_id: str | None) -> None:\n'
        '    async with get_db() as db:\n'
        '        await db.execute(\n'
        '            "UPDATE user_campaigns SET run_id=? WHERE id=?", (run_id, campaign_id)\n'
        '        )\n'
        '        await db.commit()\n'
        '\n'
        '\n'
        'async def get_due_recurring_campaigns() -> list[dict]:\n'
        '    """Return recurring active campaigns where next_run_at <= now."""\n'
        '    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")\n'
        '    async with get_db() as db:\n'
        '        async with db.execute(\n'
        '            "SELECT * FROM user_campaigns WHERE mode=\'recurring\' AND status=\'active\' "\n'
        '            "AND (next_run_at IS NULL OR substr(replace(next_run_at, \'T\', \' \'), 1, 19) <= ?)",\n'
        '            (now_str,),\n'
        '        ) as c:\n'
        '            rows = await c.fetchall()\n'
        '            cols = [d[0] for d in c.description]\n'
        '    return [dict(zip(cols, r)) for r in rows]'
    )
    if "async def resume_user_campaign" not in content:
        if old_next_run_and_due not in content:
            raise RuntimeError("Could not locate update_campaign_next_run / get_due_recurring_campaigns block")
        content = content.replace(old_next_run_and_due, new_next_run_and_due, 1)
        applied.append("ISS-02 & ISS-04: Fixed timestamp comparison in get_due_recurring_campaigns() and added resume_user_campaign()")

    # 3. ISS-11: Enhance recover_stale_claims(force_all: bool = False)
    old_recover = (
        'async def recover_stale_claims() -> None:\n'
        '    """On startup: clear expired claims and reset those campaigns to \'active\'."""\n'
        '    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")\n'
        '    async with get_db() as db:\n'
        '        async with db.execute(\n'
        '            "SELECT campaign_id FROM user_campaign_execution_claims WHERE expires_at < ?", (now_str,)\n'
        '        ) as c:\n'
        '            stale = [r[0] for r in await c.fetchall()]\n'
        '        if stale:\n'
        '            for cid in stale:\n'
        '                await db.execute(\n'
        '                    "UPDATE user_campaigns SET status=\'active\', run_id=NULL WHERE id=? AND status=\'running\'",\n'
        '                    (cid,),\n'
        '                )\n'
        '            await db.execute(\n'
        '                f"DELETE FROM user_campaign_execution_claims WHERE campaign_id IN "\n'
        '                f"({\',\'.join(\'?\'*len(stale))})",\n'
        '                stale,\n'
        '            )\n'
        '            await db.commit()'
    )
    new_recover = (
        'async def recover_stale_claims(force_all: bool = False) -> None:\n'
        '    """Clear expired claims (or all claims on fresh startup) and reset running campaigns to \'active\'."""\n'
        '    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")\n'
        '    async with get_db() as db:\n'
        '        if force_all:\n'
        '            await db.execute(\n'
        '                "UPDATE user_campaigns SET status=\'active\', run_id=NULL WHERE status=\'running\'"\n'
        '            )\n'
        '            await db.execute("DELETE FROM user_campaign_execution_claims")\n'
        '            await db.commit()\n'
        '            return\n'
        '        async with db.execute(\n'
        '            "SELECT campaign_id FROM user_campaign_execution_claims WHERE expires_at < ?", (now_str,)\n'
        '        ) as c:\n'
        '            stale = [r[0] for r in await c.fetchall()]\n'
        '        if stale:\n'
        '            for cid in stale:\n'
        '                await db.execute(\n'
        '                    "UPDATE user_campaigns SET status=\'active\', run_id=NULL WHERE id=? AND status=\'running\'",\n'
        '                    (cid,),\n'
        '                )\n'
        '            await db.execute(\n'
        '                f"DELETE FROM user_campaign_execution_claims WHERE campaign_id IN "\n'
        '                f"({\',\'.join(\'?\'*len(stale))})",\n'
        '                stale,\n'
        '            )\n'
        '            await db.commit()'
    )
    if "force_all: bool = False" not in content:
        if old_recover not in content:
            raise RuntimeError("Could not locate recover_stale_claims() block in models/user_campaigns.py")
        content = content.replace(old_recover, new_recover, 1)
        applied.append("ISS-11: Enhanced recover_stale_claims(force_all) to recover interrupted campaigns on fast restart")

    return content, applied


def patch_handlers_user_my_campaign(content: str) -> tuple[str, list[str]]:
    """Apply ISS-04 fix in handlers/user/my_campaign.py."""
    applied = []

    old_imports = (
        "from models.user_campaigns import (\n"
        "    get_current_campaign, get_quota, update_campaign_status,\n"
        "    get_delivery_stats, _today,\n"
        ")\n"
        "from services.user_broadcast import (\n"
        "    create_user_campaign, execute_user_campaign,\n"
        "    _feature_enabled, validate_buttons,\n"
        ")"
    )
    new_imports = (
        "from models.user_campaigns import (\n"
        "    get_current_campaign, get_quota, update_campaign_status,\n"
        "    resume_user_campaign, get_delivery_stats, _today,\n"
        ")\n"
        "from services.user_broadcast import (\n"
        "    create_user_campaign, execute_user_campaign,\n"
        "    _feature_enabled, _get_generation, validate_buttons,\n"
        ")"
    )
    if "resume_user_campaign" not in content:
        if old_imports not in content:
            raise RuntimeError("Could not locate imports block in handlers/user/my_campaign.py")
        content = content.replace(old_imports, new_imports, 1)

    old_view_buttons = (
        '    if current["status"] == "active":\n'
        '        buttons.append([types.InlineKeyboardButton(text="⏸ Pause", callback_data=f"user_pause_campaign_{current[\'id\']}")])\n'
        '    elif current["status"] == "paused":\n'
        '        buttons.append([types.InlineKeyboardButton(text="▶️ Resume", callback_data=f"user_resume_campaign_{current[\'id\']}")])'
    )
    new_view_buttons = (
        '    if current["status"] == "active":\n'
        '        buttons.append([types.InlineKeyboardButton(text="⏸ Pause", callback_data=f"user_pause_campaign_{current[\'id\']}")])\n'
        '    elif current["status"] in ("paused", "suspended_admin"):\n'
        '        buttons.append([types.InlineKeyboardButton(text="▶️ Resume", callback_data=f"user_resume_campaign_{current[\'id\']}")])'
    )
    if 'current["status"] in ("paused", "suspended_admin")' not in content:
        if old_view_buttons not in content:
            raise RuntimeError("Could not locate view buttons block in handlers/user/my_campaign.py")
        content = content.replace(old_view_buttons, new_view_buttons, 1)
        applied.append("ISS-04: Displayed Resume button for suspended_admin campaigns")

    old_resume_handler = (
        '@router.callback_query(F.data.startswith("user_resume_campaign_"))\n'
        'async def cb_user_resume_campaign(callback: types.CallbackQuery):\n'
        '    cid = int(callback.data.split("_")[-1])\n'
        '    user_id = callback.from_user.id\n'
        '    if not await _check_feature(callback):\n'
        '        return\n'
        '    current = await get_current_campaign(user_id)\n'
        '    if not current or current["id"] != cid:\n'
        '        await callback.answer("Campaign not found.", show_alert=True)\n'
        '        return\n'
        '    await update_campaign_status(cid, "active")\n'
        '    await callback.answer("▶️ Campaign resumed.")\n'
        '    await cb_user_view_campaign(callback)'
    )
    new_resume_handler = (
        '@router.callback_query(F.data.startswith("user_resume_campaign_"))\n'
        'async def cb_user_resume_campaign(callback: types.CallbackQuery):\n'
        '    cid = int(callback.data.split("_")[-1])\n'
        '    user_id = callback.from_user.id\n'
        '    if not await _check_feature(callback):\n'
        '        return\n'
        '    current = await get_current_campaign(user_id)\n'
        '    if not current or current["id"] != cid:\n'
        '        await callback.answer("Campaign not found.", show_alert=True)\n'
        '        return\n'
        '    gen = await _get_generation()\n'
        '    await resume_user_campaign(cid, gen)\n'
        '    await callback.answer("▶️ Campaign resumed.")\n'
        '    await cb_user_view_campaign(callback)'
    )
    if "await resume_user_campaign(cid, gen)" not in content:
        if old_resume_handler not in content:
            raise RuntimeError("Could not locate cb_user_resume_campaign in handlers/user/my_campaign.py")
        content = content.replace(old_resume_handler, new_resume_handler, 1)
        applied.append("ISS-04: Updated cb_user_resume_campaign to sync system_generation on resume")

    old_replace_warn = 'if current and current["status"] in ("active", "paused"):'
    new_replace_warn = 'if current and current["status"] in ("active", "paused", "suspended_admin"):'
    if old_replace_warn in content:
        content = content.replace(old_replace_warn, new_replace_warn, 1)

    return content, applied


def patch_main_and_background(main_content: str, bg_content: str) -> tuple[str, str, list[str]]:
    """Apply ISS-11 startup force recovery in main.py and periodic recovery in tasks/background.py."""
    applied = []

    if "await recover_stale_claims(force_all=True)" not in main_content:
        if "await recover_stale_claims()" not in main_content:
            raise RuntimeError("Could not locate recover_stale_claims() in main.py")
        main_content = main_content.replace(
            "await recover_stale_claims()",
            "await recover_stale_claims(force_all=True)",
            1,
        )
        applied.append("ISS-11: Updated main.py to call recover_stale_claims(force_all=True) on startup")

    old_bg_block = (
        "    from models.user_campaigns import get_due_recurring_campaigns\n"
        "    from models.settings import get_setting as _get_setting\n"
        "    from services.user_broadcast import execute_user_campaign\n"
        "\n"
        "    _running: set[int] = set()\n"
        "\n"
        "    async def _run_safe(cid: int) -> None:\n"
        "        try:\n"
        "            await execute_user_campaign(cid)\n"
        "        finally:\n"
        "            _running.discard(cid)\n"
        "\n"
        "    while True:\n"
        "        try:\n"
        "            await _asyncio.sleep(300)\n"
        "            # Check global feature switch first\n"
        "            if await _get_setting(\"user_campaigns_enabled\") != \"true\":\n"
        "                continue\n"
        "            campaigns = await get_due_recurring_campaigns()"
    )
    new_bg_block = (
        "    from models.user_campaigns import get_due_recurring_campaigns, recover_stale_claims\n"
        "    from models.settings import get_setting as _get_setting\n"
        "    from services.user_broadcast import execute_user_campaign\n"
        "\n"
        "    _running: set[int] = set()\n"
        "\n"
        "    async def _run_safe(cid: int) -> None:\n"
        "        try:\n"
        "            await execute_user_campaign(cid)\n"
        "        finally:\n"
        "            _running.discard(cid)\n"
        "\n"
        "    while True:\n"
        "        try:\n"
        "            await _asyncio.sleep(300)\n"
        "            # Check global feature switch first\n"
        "            if await _get_setting(\"user_campaigns_enabled\") != \"true\":\n"
        "                continue\n"
        "            await recover_stale_claims(force_all=False)\n"
        "            campaigns = await get_due_recurring_campaigns()"
    )
    if "await recover_stale_claims(force_all=False)" not in bg_content:
        if old_bg_block not in bg_content:
            raise RuntimeError("Could not locate auto_user_recurring_campaigns block in tasks/background.py")
        bg_content = bg_content.replace(old_bg_block, new_bg_block, 1)
        applied.append("ISS-11: Added periodic recover_stale_claims(force_all=False) in tasks/background.py")

    return main_content, bg_content, applied


def migrate_existing_sqlite_db(dry_run: bool = False) -> list[str]:
    """If bot.db exists on disk, apply ISS-03 backfill and ISS-06 WAL/indexes directly."""
    db_path = PROJECT_ROOT / "bot.db"
    actions = []
    if not db_path.exists():
        return ["bot.db not present on disk (will be initialized on first run)"]
    if dry_run:
        return ["[DRY-RUN] Would migrate bot.db (WAL + reward_owner_id backfill + indexes)"]

    conn = sqlite3.connect(str(db_path), timeout=30.0)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        # Ensure reward_owner_id column exists
        cols = {row[1] for row in cur.execute("PRAGMA table_info(groups)").fetchall()}
        if "reward_owner_id" not in cols:
            cur.execute("ALTER TABLE groups ADD COLUMN reward_owner_id INTEGER")
            actions.append("bot.db: Added column reward_owner_id to groups")
        cur.execute(
            "UPDATE groups SET reward_owner_id = added_by "
            "WHERE reward_owner_id IS NULL AND added_by IS NOT NULL"
        )
        if cur.rowcount > 0:
            actions.append(f"bot.db: Backfilled reward_owner_id for {cur.rowcount} existing group(s)")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_groups_reward_owner_status ON groups(reward_owner_id, status)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_type_created ON events(event_type, created_at)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_broadcast_messages_delete_at ON broadcast_messages(delete_at)"
        )
        conn.commit()
        actions.append("bot.db: Verified WAL mode and performance indexes")
    finally:
        conn.close()
    return actions


def run_repair(dry_run: bool = False) -> int:
    print("=" * 65)
    print(f"Deploy Links Bot — Phase 1 Repair ({'DRY-RUN' if dry_run else 'APPLY'})")
    print("=" * 65)

    for rel_path in TARGET_FILES:
        full_path = PROJECT_ROOT / rel_path
        if not full_path.exists():
            print(f"[ERROR] Missing required project file: {rel_path}")
            return 1

    create_backups(dry_run=dry_run)

    # Read current files
    db_py = (PROJECT_ROOT / "core/database.py").read_text(encoding="utf-8")
    camp_py = (PROJECT_ROOT / "services/campaign.py").read_text(encoding="utf-8")
    uc_py = (PROJECT_ROOT / "models/user_campaigns.py").read_text(encoding="utf-8")
    my_camp_py = (PROJECT_ROOT / "handlers/user/my_campaign.py").read_text(encoding="utf-8")
    main_py = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
    bg_py = (PROJECT_ROOT / "tasks/background.py").read_text(encoding="utf-8")

    all_changes: list[str] = []

    db_py_new, ch1 = patch_core_database(db_py)
    all_changes.extend(ch1)

    camp_py_new, ch2 = patch_services_campaign(camp_py)
    all_changes.extend(ch2)

    uc_py_new, ch3 = patch_models_user_campaigns(uc_py)
    all_changes.extend(ch3)

    my_camp_py_new, ch4 = patch_handlers_user_my_campaign(my_camp_py)
    all_changes.extend(ch4)

    main_py_new, bg_py_new, ch5 = patch_main_and_background(main_py, bg_py)
    all_changes.extend(ch5)

    updated_map = {
        "core/database.py": db_py_new,
        "services/campaign.py": camp_py_new,
        "models/user_campaigns.py": uc_py_new,
        "handlers/user/my_campaign.py": my_camp_py_new,
        "main.py": main_py_new,
        "tasks/background.py": bg_py_new,
    }

    # Verify AST syntax on all modified contents before touching disk
    for rel_path, new_code in updated_map.items():
        verify_python_syntax(new_code, rel_path)

    if not dry_run:
        for rel_path, new_code in updated_map.items():
            (PROJECT_ROOT / rel_path).write_text(new_code, encoding="utf-8")

    db_actions = migrate_existing_sqlite_db(dry_run=dry_run)
    all_changes.extend(db_actions)

    if all_changes:
        print("\nChanges applied:")
        for item in all_changes:
            print(f"  [OK] {item}")
    else:
        print("\n[INFO] All Phase 1 fixes are already applied (idempotent check passed).")

    print("\n[SUCCESS] Phase 1 repair completed cleanly.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 1 Repair Script")
    parser.add_argument("--dry-run", action="store_true", help="Simulate changes without modifying files")
    parser.add_argument("--rollback", action="store_true", help="Restore files from Phase 1 backup")
    args = parser.parse_args()

    if args.rollback:
        sys.exit(rollback())
    sys.exit(run_repair(dry_run=args.dry_run))
