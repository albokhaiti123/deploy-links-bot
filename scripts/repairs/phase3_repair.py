#!/usr/bin/env python3
"""
Phase 3 Repair Script — Deploy Links Bot
Addresses confirmed issues: ISS-12, ISS-13, ISS-14, ISS-15, ISS-18, ISS-19

Features:
  - Idempotent execution (safe to run multiple times)
  - Automatic backup before modification (.backups/phase3/)
  - AST syntax verification before writing any file
  - Supports --dry-run and --rollback modes
"""

import argparse
import ast
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKUP_DIR = PROJECT_ROOT / ".backups" / "phase3"

TARGET_FILES = [
    "states/states.py",
    "models/users.py",
    "models/events.py",
    "models/campaigns.py",
    "services/promo.py",
    "services/campaign.py",
    "services/broadcast.py",
    "services/user_broadcast.py",
    "handlers/admin/admins.py",
    "handlers/admin/broadcast.py",
    "handlers/admin/button_manager.py",
    "handlers/admin/campaigns.py",
    "handlers/admin/general_settings.py",
    "handlers/admin/promo_settings.py",
    "handlers/admin/welcome_settings.py",
    "handlers/admin/recurring.py",
    "handlers/user/my_campaign.py",
]


def verify_python_syntax(code: str, filepath: str) -> None:
    """Parse Python source with AST to guarantee zero syntax errors."""
    try:
        ast.parse(code, filename=filepath)
    except SyntaxError as exc:
        raise RuntimeError(f"AST syntax check failed for {filepath}: {exc}") from exc


def create_backups(dry_run: bool = False) -> None:
    if dry_run:
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for rel_path in TARGET_FILES:
        src = PROJECT_ROOT / rel_path
        dst = BACKUP_DIR / rel_path
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def rollback() -> int:
    if not BACKUP_DIR.exists():
        print("[ROLLBACK] No backup directory found at .backups/phase3/")
        return 1
    for rel_path in TARGET_FILES:
        bkp = BACKUP_DIR / rel_path
        dst = PROJECT_ROOT / rel_path
        if bkp.exists():
            shutil.copy2(bkp, dst)
            print(f"[ROLLBACK] Restored {rel_path}")
    print("[ROLLBACK] Phase 3 rollback completed successfully.")
    return 0


# ── 1. states/states.py (ISS-13) ─────────────────────────────────────────────

def patch_states(content: str) -> tuple[str, list[str]]:
    applied = []
    old_block = (
        "    waiting_for_rbw_text = State()\n"
        "    waiting_for_rbw_edit_text = State()\n"
        "    waiting_for_rbw_hours = State()"
    )
    new_block = (
        "    waiting_for_rbw_text = State()\n"
        "    waiting_for_rbw_edit_text = State()\n"
        "    waiting_for_rbw_media = State()\n"
        "    waiting_for_rbw_vip = State()\n"
        "    waiting_for_rbw_stars = State()\n"
        "    waiting_for_rbw_hours = State()"
    )
    if "waiting_for_rbw_media = State()" not in content:
        if old_block not in content:
            raise RuntimeError("Could not locate rbw states in states/states.py")
        content = content.replace(old_block, new_block, 1)
        applied.append("ISS-13: Added media and VIP states for recurring broadcasts in states/states.py")
    return content, applied


# ── 2. models/users.py & models/events.py (ISS-19) ───────────────────────────

def patch_models_users(content: str) -> tuple[str, list[str]]:
    applied = []
    if "timedelta" not in content:
        content = content.replace("from datetime import datetime", "from datetime import datetime, timedelta", 1)

    old_fn = (
        'async def get_users_since(since: str) -> int:\n'
        '    """Count users created since a datetime expression (e.g. \\"datetime(\'now\', \'-1 day\')\\")."""\n'
        '    async with get_db() as db:\n'
        '        async with db.execute(\n'
        '            f"SELECT COUNT(*) FROM users WHERE created_at >= {since}"\n'
        '        ) as cursor:\n'
        '            return (await cursor.fetchone())[0]'
    )
    new_fn = (
        'async def get_users_since(since: str | datetime | None = None, hours: int = 24) -> int:\n'
        '    """Count users created since a cutoff timestamp using parameterized query."""\n'
        '    if isinstance(since, datetime):\n'
        '        cutoff = since\n'
        '    else:\n'
        '        cutoff = datetime.now() - timedelta(hours=hours)\n'
        '    async with get_db() as db:\n'
        '        async with db.execute(\n'
        '            "SELECT COUNT(*) FROM users WHERE created_at >= ?",\n'
        '            (cutoff,),\n'
        '        ) as cursor:\n'
        '            return (await cursor.fetchone())[0]'
    )
    if 'f"SELECT COUNT(*) FROM users WHERE created_at >= {since}"' in content:
        content = content.replace(old_fn, new_fn, 1)
        applied.append("ISS-19: Replaced SQL string interpolation with parameterized cutoff in get_users_since()")
    return content, applied


def patch_models_events(content: str) -> tuple[str, list[str]]:
    applied = []
    if "timedelta" not in content:
        content = content.replace("from datetime import datetime", "from datetime import datetime, timedelta", 1)

    old_fn = (
        'async def count_events_since(event_type: str, since: str) -> int:\n'
        '    """Count events of a type since a datetime expression."""\n'
        '    async with get_db() as db:\n'
        '        async with db.execute(\n'
        '            f"SELECT COUNT(*) FROM events WHERE event_type=? AND created_at >= {since}",\n'
        '            (event_type,),\n'
        '        ) as cursor:\n'
        '            return (await cursor.fetchone())[0]'
    )
    new_fn = (
        'async def count_events_since(event_type: str, since: str | datetime | None = None, hours: int = 24) -> int:\n'
        '    """Count events of a type since a cutoff timestamp using parameterized query."""\n'
        '    if isinstance(since, datetime):\n'
        '        cutoff = since\n'
        '    else:\n'
        '        cutoff = datetime.now() - timedelta(hours=hours)\n'
        '    async with get_db() as db:\n'
        '        async with db.execute(\n'
        '            "SELECT COUNT(*) FROM events WHERE event_type=? AND created_at >= ?",\n'
        '            (event_type, cutoff),\n'
        '        ) as cursor:\n'
        '            return (await cursor.fetchone())[0]'
    )
    if 'f"SELECT COUNT(*) FROM events WHERE event_type=? AND created_at >= {since}"' in content:
        content = content.replace(old_fn, new_fn, 1)
        applied.append("ISS-19: Replaced SQL string interpolation with parameterized cutoff in count_events_since()")
    return content, applied


# ── 3. models/campaigns.py (ISS-18b) ─────────────────────────────────────────

def patch_models_campaigns(content: str) -> tuple[str, list[str]]:
    applied = []
    old_stats = (
        'async def get_campaign_stats(campaign_id: int) -> dict:\n'
        '    """Return campaign statistics as a dict."""\n'
        '    async with get_db() as db:\n'
        '        stats = {}\n'
        '\n'
        '        async with db.execute(\n'
        '            "SELECT COUNT(*) FROM campaign_user_progress WHERE campaign_id=?",\n'
        '            (campaign_id,),\n'
        '        ) as c:\n'
        '            stats["started"] = (await c.fetchone())[0]\n'
        '\n'
        '        async with db.execute(\n'
        '            "SELECT COUNT(*) FROM campaign_groups WHERE campaign_id=? AND verified=1",\n'
        '            (campaign_id,),\n'
        '        ) as c:\n'
        '            stats["groups_added"] = (await c.fetchone())[0]\n'
        '\n'
        '        async with db.execute(\n'
        '            "SELECT COUNT(*) FROM campaign_user_progress WHERE campaign_id=? AND status=\'unlocked\'",\n'
        '            (campaign_id,),\n'
        '        ) as c:\n'
        '            stats["unlocked"] = (await c.fetchone())[0]\n'
        '\n'
        '    return stats'
    )
    new_stats = (
        'async def get_campaign_stats(campaign_id: int) -> dict:\n'
        '    """Return campaign statistics as a dict (views, started, groups_added, unlocked, delivered)."""\n'
        '    async with get_db() as db:\n'
        '        stats = {}\n'
        '\n'
        '        async with db.execute(\n'
        '            "SELECT COUNT(*) FROM events WHERE event_type=?",\n'
        '            (f"campaign_{campaign_id}_viewed",),\n'
        '        ) as c:\n'
        '            stats["views"] = (await c.fetchone())[0]\n'
        '\n'
        '        async with db.execute(\n'
        '            "SELECT COUNT(*) FROM campaign_user_progress WHERE campaign_id=?",\n'
        '            (campaign_id,),\n'
        '        ) as c:\n'
        '            stats["started"] = (await c.fetchone())[0]\n'
        '\n'
        '        async with db.execute(\n'
        '            "SELECT COUNT(*) FROM campaign_groups WHERE campaign_id=? AND verified=1",\n'
        '            (campaign_id,),\n'
        '        ) as c:\n'
        '            stats["groups_added"] = (await c.fetchone())[0]\n'
        '\n'
        '        async with db.execute(\n'
        '            "SELECT COUNT(*) FROM campaign_user_progress WHERE campaign_id=? AND status=\'unlocked\'",\n'
        '            (campaign_id,),\n'
        '        ) as c:\n'
        '            stats["unlocked"] = (await c.fetchone())[0]\n'
        '\n'
        '        async with db.execute(\n'
        '            "SELECT COUNT(*) FROM events WHERE event_type=?",\n'
        '            (f"campaign_{campaign_id}_content_delivered",),\n'
        '        ) as c:\n'
        '            stats["delivered"] = (await c.fetchone())[0]\n'
        '\n'
        '    return stats'
    )
    if 'stats["views"]' not in content:
        if old_stats not in content:
            raise RuntimeError("Could not locate get_campaign_stats in models/campaigns.py")
        content = content.replace(old_stats, new_stats, 1)
        applied.append("ISS-18: Restored views and delivered metrics to get_campaign_stats()")
    return content, applied


# ── 4. services/promo.py (ISS-19) ────────────────────────────────────────────

def patch_services_promo(content: str) -> tuple[str, list[str]]:
    applied = []
    old_cooldown = (
        "    if cooldown > 0 and chat_id in _last_promo_times:\n"
        "        if current_time - _last_promo_times[chat_id] < cooldown:\n"
        '            logger.info(f"Promo skipped in {chat_id} due to cooldown active.")\n'
        "            return\n"
        "\n"
        "    _last_promo_times[chat_id] = current_time"
    )
    new_cooldown = (
        "    if len(_last_promo_times) > 500:\n"
        "        cutoff_ts = current_time - max(cooldown, 3600)\n"
        "        expired_keys = [k for k, ts in _last_promo_times.items() if ts < cutoff_ts]\n"
        "        for k in expired_keys:\n"
        "            _last_promo_times.pop(k, None)\n"
        "\n"
        "    if cooldown > 0 and chat_id in _last_promo_times:\n"
        "        if current_time - _last_promo_times[chat_id] < cooldown:\n"
        '            logger.info(f"Promo skipped in {chat_id} due to cooldown active.")\n'
        "            return\n"
        "\n"
        "    _last_promo_times[chat_id] = current_time"
    )
    if "expired_keys = [k for k, ts in _last_promo_times.items()" not in content:
        if old_cooldown not in content:
            raise RuntimeError("Could not locate cooldown block in services/promo.py")
        content = content.replace(old_cooldown, new_cooldown, 1)
        applied.append("ISS-19: Added automatic pruning for _last_promo_times in services/promo.py")
    return content, applied


# ── 5. services/campaign.py (ISS-13b & ISS-19) ───────────────────────────────

def patch_services_campaign(content: str) -> tuple[str, list[str]]:
    applied = []

    # 1. ISS-19: Prune _campaign_verify_cooldown
    old_verify_cd = (
        "    # Rate limit\n"
        "    key = (user_id, campaign_id)\n"
        "    now = time.time()\n"
        "    if key in _campaign_verify_cooldown:\n"
        "        elapsed = now - _campaign_verify_cooldown[key]\n"
        "        if elapsed < VERIFY_COOLDOWN_SECONDS:\n"
        "            remaining = int(VERIFY_COOLDOWN_SECONDS - elapsed)\n"
        "            await callback.answer(\n"
        '                f"⏳ Please wait {remaining} seconds before verifying again.",\n'
        "                show_alert=True,\n"
        "            )\n"
        "            return\n"
        "    _campaign_verify_cooldown[key] = now"
    )
    new_verify_cd = (
        "    # Rate limit with automatic stale-entry cleanup\n"
        "    key = (user_id, campaign_id)\n"
        "    now = time.time()\n"
        "    if len(_campaign_verify_cooldown) > 500:\n"
        "        stale_keys = [k for k, ts in _campaign_verify_cooldown.items() if now - ts > VERIFY_COOLDOWN_SECONDS * 6]\n"
        "        for k in stale_keys:\n"
        "            _campaign_verify_cooldown.pop(k, None)\n"
        "    if key in _campaign_verify_cooldown:\n"
        "        elapsed = now - _campaign_verify_cooldown[key]\n"
        "        if elapsed < VERIFY_COOLDOWN_SECONDS:\n"
        "            remaining = int(VERIFY_COOLDOWN_SECONDS - elapsed)\n"
        "            await callback.answer(\n"
        '                f"⏳ Please wait {remaining} seconds before verifying again.",\n'
        "                show_alert=True,\n"
        "            )\n"
        "            return\n"
        "    _campaign_verify_cooldown[key] = now"
    )
    if "stale_keys = [k for k, ts in _campaign_verify_cooldown.items()" not in content:
        if old_verify_cd not in content:
            raise RuntimeError("Could not locate verify cooldown block in services/campaign.py")
        content = content.replace(old_verify_cd, new_verify_cd, 1)
        applied.append("ISS-19: Added automatic pruning for _campaign_verify_cooldown in services/campaign.py")

    # 2. ISS-13b: Only deactivate actual group IDs on TelegramForbiddenError
    old_camp_bcast = (
        '    targets_list: list[int] = []\n'
        '    if target in ("users", "all"):\n'
        '        targets_list += await get_all_user_ids()\n'
        '    if target in ("groups", "all"):\n'
        '        targets_list += await get_active_group_ids()'
    )
    new_camp_bcast = (
        '    targets_list: list[int] = []\n'
        '    group_set: set[int] = set()\n'
        '    if target in ("users", "all"):\n'
        '        targets_list += await get_all_user_ids()\n'
        '    if target in ("groups", "all"):\n'
        '        g_ids = await get_active_group_ids()\n'
        '        targets_list += g_ids\n'
        '        group_set = set(g_ids)'
    )
    if "group_set: set[int] = set()" not in content:
        if old_camp_bcast not in content:
            raise RuntimeError("Could not locate targets_list block in execute_campaign_broadcast")
        content = content.replace(old_camp_bcast, new_camp_bcast, 1)
        content = content.replace(
            '        except TelegramForbiddenError:\n'
            '            if target in ("groups", "all"):\n'
            '                await deactivate_group(chat_id)',
            '        except TelegramForbiddenError:\n'
            '            if chat_id in group_set:\n'
            '                await deactivate_group(chat_id)',
            1,
        )

    old_rec_camp = (
        '    targets: list[int] = []\n'
        '    targets += await get_all_user_ids()\n'
        '    targets += await get_active_group_ids()'
    )
    new_rec_camp = (
        '    targets: list[int] = []\n'
        '    targets += await get_all_user_ids()\n'
        '    g_ids = await get_active_group_ids()\n'
        '    targets += g_ids\n'
        '    group_set = set(g_ids)'
    )
    if "g_ids = await get_active_group_ids()" not in content:
        if old_rec_camp not in content:
            raise RuntimeError("Could not locate targets block in execute_recurring_campaign_cycle")
        content = content.replace(old_rec_camp, new_rec_camp, 1)
        content = content.replace(
            '        except TelegramForbiddenError:\n'
            '            await deactivate_group(chat_id)',
            '        except TelegramForbiddenError:\n'
            '            if chat_id in group_set:\n'
            '                await deactivate_group(chat_id)',
            1,
        )
        applied.append("ISS-13: Restricted deactivate_group() to actual group chat_ids in services/campaign.py")

    return content, applied


# ── 6. services/broadcast.py (ISS-13b) ───────────────────────────────────────

def patch_services_broadcast(content: str) -> tuple[str, list[str]]:
    applied = []
    old_rec_targets = (
        '    targets: list[int] = []\n'
        '    if target in ("users", "all"):\n'
        '        targets += await get_all_user_ids()\n'
        '    if target in ("groups", "all"):\n'
        '        targets += await get_active_group_ids()'
    )
    new_rec_targets = (
        '    targets: list[int] = []\n'
        '    group_set: set[int] = set()\n'
        '    if target in ("users", "all"):\n'
        '        targets += await get_all_user_ids()\n'
        '    if target in ("groups", "all"):\n'
        '        g_ids = await get_active_group_ids()\n'
        '        targets += g_ids\n'
        '        group_set = set(g_ids)'
    )
    if "group_set: set[int] = set()" not in content:
        if old_rec_targets not in content:
            raise RuntimeError("Could not locate targets block in execute_recurring_broadcast_cycle")
        content = content.replace(old_rec_targets, new_rec_targets, 1)
        content = content.replace(
            '        except TelegramForbiddenError:\n'
            '            await deactivate_group(chat_id)',
            '        except TelegramForbiddenError:\n'
            '            if chat_id in group_set:\n'
            '                await deactivate_group(chat_id)',
            1,
        )
        applied.append("ISS-13: Restricted deactivate_group() to actual group chat_ids in services/broadcast.py")
    return content, applied


# ── 7. services/user_broadcast.py (ISS-14b & ISS-15a) ────────────────────────

def patch_services_user_broadcast(content: str) -> tuple[str, list[str]]:
    applied = []

    if "from models.broadcasts import schedule_delete_after" not in content:
        content = content.replace(
            "from services.group_manager import handle_send_error",
            "from models.broadcasts import schedule_delete_after\nfrom services.group_manager import handle_send_error",
            1,
        )

    # 1. ISS-14b: Ensure campaign status is 'active' before executing
    old_start = (
        '    campaign = await get_campaign_by_id(campaign_id)\n'
        '    if not campaign:\n'
        '        return {"sent": 0, "failed": 0, "skipped": 0, "error": "Campaign not found"}\n'
        '\n'
        '    # Fencing: check feature enabled and generation'
    )
    new_start = (
        '    campaign = await get_campaign_by_id(campaign_id)\n'
        '    if not campaign:\n'
        '        return {"sent": 0, "failed": 0, "skipped": 0, "error": "Campaign not found"}\n'
        '\n'
        '    if campaign["status"] != "active":\n'
        '        logger.info(f"UserCampaign {campaign_id}: status is {campaign[\'status\']} (not active), aborting")\n'
        '        return {"sent": 0, "failed": 0, "skipped": 0, "error": f"Campaign is {campaign[\'status\']}"}\n'
        '\n'
        '    # Fencing: check feature enabled and generation'
    )
    if 'if campaign["status"] != "active":' not in content:
        if old_start not in content:
            raise RuntimeError("Could not locate campaign start check in execute_user_campaign")
        content = content.replace(old_start, new_start, 1)
        applied.append("ISS-14: Enforced status == 'active' precondition in execute_user_campaign()")

    # 2. ISS-15a: Schedule auto-deletion when auto_delete_seconds > 0
    old_send_block = (
        '            try:\n'
        '                await _send_user_campaign_message(\n'
        '                    chat_id, campaign["text"], campaign["photo_file_id"], keyboard\n'
        '                )\n'
        '                await record_delivery(campaign_id, run_id, chat_id, "sent")\n'
        '                await update_group_health_ok(chat_id)\n'
        '                stats["sent"] += 1\n'
        '            except TelegramRetryAfter as e:\n'
        '                await asyncio.sleep(e.retry_after + 1)\n'
        '                try:\n'
        '                    await _send_user_campaign_message(\n'
        '                        chat_id, campaign["text"], campaign["photo_file_id"], keyboard\n'
        '                    )\n'
        '                    await record_delivery(campaign_id, run_id, chat_id, "sent")\n'
        '                    stats["sent"] += 1'
    )
    new_send_block = (
        '            auto_del_sec = int(campaign.get("auto_delete_seconds") or 0)\n'
        '            try:\n'
        '                sent_msg_id = await _send_user_campaign_message(\n'
        '                    chat_id, campaign["text"], campaign["photo_file_id"], keyboard\n'
        '                )\n'
        '                await record_delivery(campaign_id, run_id, chat_id, "sent")\n'
        '                await update_group_health_ok(chat_id)\n'
        '                if sent_msg_id and auto_del_sec > 0:\n'
        '                    await schedule_delete_after(chat_id, sent_msg_id, auto_del_sec)\n'
        '                stats["sent"] += 1\n'
        '            except TelegramRetryAfter as e:\n'
        '                await asyncio.sleep(e.retry_after + 1)\n'
        '                try:\n'
        '                    sent_msg_id = await _send_user_campaign_message(\n'
        '                        chat_id, campaign["text"], campaign["photo_file_id"], keyboard\n'
        '                    )\n'
        '                    await record_delivery(campaign_id, run_id, chat_id, "sent")\n'
        '                    if sent_msg_id and auto_del_sec > 0:\n'
        '                        await schedule_delete_after(chat_id, sent_msg_id, auto_del_sec)\n'
        '                    stats["sent"] += 1'
    )
    if "auto_del_sec = int(campaign.get(" not in content:
        if old_send_block not in content:
            raise RuntimeError("Could not locate send block in execute_user_campaign")
        content = content.replace(old_send_block, new_send_block, 1)
        applied.append("ISS-15: Wired auto_delete_seconds to schedule_delete_after() in execute_user_campaign()")

    return content, applied


# ── 8. handlers/admin/admins.py (ISS-12 & ISS-18c) ───────────────────────────

def patch_handlers_admin_admins(content: str) -> tuple[str, list[str]]:
    applied = []
    old_fn = (
        '@router.message(AdminEdit.waiting_for_admin_id)\n'
        'async def process_admin_id(message: types.Message, state: FSMContext):\n'
        '    if message.text == "/cancel":\n'
        '        await message.answer("❌ تم الإلغاء.")\n'
        '        await state.clear()\n'
        '        return\n'
        '    if not message.text.strip().isdigit():\n'
        '        await message.answer("❌ يرجى إرسال معرف رقمي صالح.\\nحاول مجدداً أو أرسل /cancel")\n'
        '        return\n'
        '    tid = int(message.text.strip())\n'
        '    data = await state.get_data()\n'
        '    action = data.get("admin_action")'
    )
    new_fn = (
        '@router.message(AdminEdit.waiting_for_admin_id)\n'
        'async def process_admin_id(message: types.Message, state: FSMContext):\n'
        '    if not message.text:\n'
        '        await message.answer("❌ يرجى إرسال معرف رقمي صالح.\\nحاول مجدداً أو أرسل /cancel")\n'
        '        return\n'
        '    if message.text == "/cancel":\n'
        '        await message.answer("❌ تم الإلغاء.")\n'
        '        await state.clear()\n'
        '        return\n'
        '    if not message.text.strip().isdigit():\n'
        '        await message.answer("❌ يرجى إرسال معرف رقمي صالح.\\nحاول مجدداً أو أرسل /cancel")\n'
        '        return\n'
        '    tid = int(message.text.strip())\n'
        '    if tid == ADMIN_ID:\n'
        '        await message.answer("⛔️ لا يمكنك تعديل صلاحيات المالك الرئيسي.")\n'
        '        await state.clear()\n'
        '        return\n'
        '    data = await state.get_data()\n'
        '    action = data.get("admin_action")'
    )
    if "if tid == ADMIN_ID:" not in content:
        if old_fn not in content:
            raise RuntimeError("Could not locate process_admin_id in handlers/admin/admins.py")
        content = content.replace(old_fn, new_fn, 1)
        applied.append("ISS-12 & ISS-18: Added non-text guard and ADMIN_ID protection in process_admin_id()")
    return content, applied


# ── 9. FSM Guards in Admin Handlers (ISS-12, ISS-13a, ISS-18b) ───────────────

def patch_handlers_admin_broadcast(content: str) -> tuple[str, list[str]]:
    applied = []
    old_bw_text = (
        '@router.message(BroadcastWizard.text)\n'
        'async def process_bw_text(message: types.Message, state: FSMContext):\n'
        '    if message.text == "/cancel":'
    )
    new_bw_text = (
        '@router.message(BroadcastWizard.text)\n'
        'async def process_bw_text(message: types.Message, state: FSMContext):\n'
        '    if not message.text:\n'
        '        return await message.answer("❌ يرجى إرسال نص الإذاعة أو /cancel للإلغاء.")\n'
        '    if message.text == "/cancel":'
    )
    if "يرجى إرسال نص الإذاعة أو /cancel" not in content:
        content = content.replace(old_bw_text, new_bw_text, 1)
        content = content.replace(
            '@router.message(BroadcastWizard.stars)\n'
            'async def process_bw_stars(message: types.Message, state: FSMContext):\n'
            '    if message.text == "/cancel":',
            '@router.message(BroadcastWizard.stars)\n'
            'async def process_bw_stars(message: types.Message, state: FSMContext):\n'
            '    if not message.text:\n'
            '        return await message.answer("❌ يرجى إرسال أرقام فقط (مثلاً 50).")\n'
            '    if message.text == "/cancel":',
            1,
        )
        applied.append("ISS-12: Added non-text guards in handlers/admin/broadcast.py")
    return content, applied


def patch_handlers_admin_button_manager(content: str) -> tuple[str, list[str]]:
    applied = []
    old_label = (
        '@router.message(ButtonWizard.waiting_for_label)\n'
        'async def process_btn_label(message: types.Message, state: FSMContext):\n'
        '    if message.text == "/cancel":'
    )
    new_label = (
        '@router.message(ButtonWizard.waiting_for_label)\n'
        'async def process_btn_label(message: types.Message, state: FSMContext):\n'
        '    if not message.text:\n'
        '        return await message.answer("❌ يرجى إرسال نص الزر أو /cancel للإلغاء.")\n'
        '    if message.text == "/cancel":'
    )
    if "يرجى إرسال نص الزر أو /cancel" not in content:
        content = content.replace(old_label, new_label, 1)
        content = content.replace(
            '@router.message(ButtonWizard.waiting_for_url)\n'
            'async def process_btn_url(message: types.Message, state: FSMContext):\n'
            '    if message.text == "/cancel":',
            '@router.message(ButtonWizard.waiting_for_url)\n'
            'async def process_btn_url(message: types.Message, state: FSMContext):\n'
            '    if not message.text:\n'
            '        return await message.answer("❌ الرابط غير صحيح. يجب أن يبدأ بـ http:// أو https:// أو tg://")\n'
            '    if message.text == "/cancel":',
            1,
        )
        applied.append("ISS-12: Added non-text guards in handlers/admin/button_manager.py")
    return content, applied


def patch_handlers_admin_campaigns(content: str) -> tuple[str, list[str]]:
    applied = []

    # 1. ISS-12 guards in CampaignWizard steps
    guards = [
        (
            '@router.message(CampaignWizard.name)\n'
            'async def process_cw_name(message: types.Message, state: FSMContext):\n'
            '    if message.text == "/cancel":',
            '@router.message(CampaignWizard.name)\n'
            'async def process_cw_name(message: types.Message, state: FSMContext):\n'
            '    if not message.text:\n'
            '        return await message.answer("❌ يرجى إرسال اسم الحملة كنص أو /cancel.")\n'
            '    if message.text == "/cancel":',
        ),
        (
            '@router.message(CampaignWizard.promo_text)\n'
            'async def process_cw_promo_text(message: types.Message, state: FSMContext):\n'
            '    if message.text == "/cancel":',
            '@router.message(CampaignWizard.promo_text)\n'
            'async def process_cw_promo_text(message: types.Message, state: FSMContext):\n'
            '    if not message.text:\n'
            '        return await message.answer("❌ يرجى إرسال نص الإعلان أو /cancel.")\n'
            '    if message.text == "/cancel":',
        ),
        (
            '@router.message(CampaignWizard.button_text)\n'
            'async def process_cw_button_text(message: types.Message, state: FSMContext):\n'
            '    if message.text == "/cancel":',
            '@router.message(CampaignWizard.button_text)\n'
            'async def process_cw_button_text(message: types.Message, state: FSMContext):\n'
            '    if not message.text:\n'
            '        return await message.answer("❌ يرجى إرسال نص الزر أو /cancel.")\n'
            '    if message.text == "/cancel":',
        ),
        (
            '@router.message(CampaignWizard.required_groups)\n'
            'async def process_cw_required_groups(message: types.Message, state: FSMContext):\n'
            '    if message.text == "/cancel":',
            '@router.message(CampaignWizard.required_groups)\n'
            'async def process_cw_required_groups(message: types.Message, state: FSMContext):\n'
            '    if not message.text:\n'
            '        return await message.answer("❌ أرسل رقماً بين 1 و 50.")\n'
            '    if message.text == "/cancel":',
        ),
        (
            '@router.message(CampaignWizard.unlock_content)\n'
            'async def process_cw_unlock_content(message: types.Message, state: FSMContext):\n'
            '    if message.text == "/cancel":',
            '@router.message(CampaignWizard.unlock_content)\n'
            'async def process_cw_unlock_content(message: types.Message, state: FSMContext):\n'
            '    if not message.text:\n'
            '        return await message.answer("❌ يرجى إرسال محتوى الفتح كنص أو /cancel.")\n'
            '    if message.text == "/cancel":',
        ),
    ]
    for old_g, new_g in guards:
        if old_g in content:
            content = content.replace(old_g, new_g, 1)
            if "ISS-12: Added non-text guards in handlers/admin/campaigns.py" not in applied:
                applied.append("ISS-12: Added non-text guards in handlers/admin/campaigns.py")

    # 2. ISS-18b: Display views and delivered in show_campaign_admin_view
    old_stats_view = (
        '        f"📈 <b>إحصائيات:</b>\\n"\n'
        '        f"  🚀 بدأوا: {stats[\'started\']}\\n"\n'
        '        f"  ➕ مجموعات أُضيفت: {stats[\'groups_added\']}\\n"\n'
        '        f"  🔓 فتحوا المحتوى: {stats[\'unlocked\']}\\n"'
    )
    new_stats_view = (
        '        f"📈 <b>إحصائيات:</b>\\n"\n'
        '        f"  👁 المشاهدات: {stats.get(\'views\', 0)}\\n"\n'
        '        f"  🚀 بدأوا: {stats[\'started\']}\\n"\n'
        '        f"  ➕ مجموعات أُضيفت: {stats[\'groups_added\']}\\n"\n'
        '        f"  🔓 فتحوا المحتوى: {stats[\'unlocked\']}\\n"\n'
        '        f"  🎁 استلموا المحتوى: {stats.get(\'delivered\', 0)}\\n"'
    )
    if "👁 المشاهدات:" not in content:
        if old_stats_view not in content:
            raise RuntimeError("Could not locate stats view block in handlers/admin/campaigns.py")
        content = content.replace(old_stats_view, new_stats_view, 1)
        applied.append("ISS-18: Added views and delivered metrics to show_campaign_admin_view()")

    return content, applied


def patch_handlers_admin_general_settings(content: str) -> tuple[str, list[str]]:
    applied = []
    old_cd = (
        '@router.message(AdminEdit.waiting_for_cooldown)\n'
        'async def process_cooldown(message: types.Message, state: FSMContext):\n'
        '    if message.text == "/cancel":'
    )
    new_cd = (
        '@router.message(AdminEdit.waiting_for_cooldown)\n'
        'async def process_cooldown(message: types.Message, state: FSMContext):\n'
        '    if not message.text:\n'
        '        return await message.answer("❌ يرجى إرسال أرقام فقط.\\nحاول مجدداً أو أرسل /cancel")\n'
        '    if message.text == "/cancel":'
    )
    if old_cd in content:
        content = content.replace(old_cd, new_cd, 1)
        content = content.replace(
            '@router.message(AdminEdit.waiting_for_test_group)\n'
            'async def process_test_group(message: types.Message, state: FSMContext):\n'
            '    if message.text == "/cancel":',
            '@router.message(AdminEdit.waiting_for_test_group)\n'
            'async def process_test_group(message: types.Message, state: FSMContext):\n'
            '    if not message.text:\n'
            '        return await message.answer("❌ يرجى إرسال معرف رقمي صالح (Chat ID).")\n'
            '    if message.text == "/cancel":',
            1,
        )
        applied.append("ISS-12: Added non-text guards in handlers/admin/general_settings.py")
    return content, applied


def patch_handlers_admin_promo_settings(content: str) -> tuple[str, list[str]]:
    applied = []
    replacements = [
        (
            '@router.message(AdminEdit.waiting_for_promo_stars)\n'
            'async def process_promo_stars(message: types.Message, state: FSMContext):\n'
            '    if message.text == "/cancel":',
            '@router.message(AdminEdit.waiting_for_promo_stars)\n'
            'async def process_promo_stars(message: types.Message, state: FSMContext):\n'
            '    if not message.text:\n'
            '        return await message.answer("❌ يرجى إرسال أرقام فقط.")\n'
            '    if message.text == "/cancel":',
        ),
        (
            '@router.message(AdminEdit.waiting_for_post_payment_msg)\n'
            'async def process_post_payment_msg(message: types.Message, state: FSMContext):\n'
            '    if message.text == "/cancel":',
            '@router.message(AdminEdit.waiting_for_post_payment_msg)\n'
            'async def process_post_payment_msg(message: types.Message, state: FSMContext):\n'
            '    if not message.text:\n'
            '        return await message.answer("❌ يرجى إرسال نص الرسالة أو /cancel.")\n'
            '    if message.text == "/cancel":',
        ),
        (
            '@router.message(AdminEdit.waiting_for_promo_text)\n'
            'async def process_promo_text(message: types.Message, state: FSMContext):\n'
            '    if message.text == "/cancel":',
            '@router.message(AdminEdit.waiting_for_promo_text)\n'
            'async def process_promo_text(message: types.Message, state: FSMContext):\n'
            '    if not message.text:\n'
            '        return await message.answer("❌ يرجى إرسال نص الإعلان أو /cancel.")\n'
            '    if message.text == "/cancel":',
        ),
        (
            '@router.message(AdminEdit.waiting_for_promo_url)\n'
            'async def process_promo_url(message: types.Message, state: FSMContext):\n'
            '    if message.text == "/cancel":',
            '@router.message(AdminEdit.waiting_for_promo_url)\n'
            'async def process_promo_url(message: types.Message, state: FSMContext):\n'
            '    if not message.text:\n'
            '        return await message.answer("❌ الرابط غير صحيح. يجب أن يبدأ بـ http:// أو https://\\nحاول مجدداً أو أرسل /cancel")\n'
            '    if message.text == "/cancel":',
        ),
        (
            '@router.message(AdminEdit.waiting_for_promo_button)\n'
            'async def process_promo_button(message: types.Message, state: FSMContext):\n'
            '    if message.text == "/cancel":',
            '@router.message(AdminEdit.waiting_for_promo_button)\n'
            'async def process_promo_button(message: types.Message, state: FSMContext):\n'
            '    if not message.text:\n'
            '        return await message.answer("❌ يرجى إرسال نص الزر أو /cancel.")\n'
            '    if message.text == "/cancel":',
        ),
    ]
    for old_s, new_s in replacements:
        if old_s in content:
            content = content.replace(old_s, new_s, 1)
            if "ISS-12: Added non-text guards in handlers/admin/promo_settings.py" not in applied:
                applied.append("ISS-12: Added non-text guards in handlers/admin/promo_settings.py")
    return content, applied


def patch_handlers_admin_welcome_settings(content: str) -> tuple[str, list[str]]:
    applied = []
    replacements = [
        (
            '@router.message(AdminEdit.waiting_for_start_msg)\n'
            'async def process_start_msg(message: types.Message, state: FSMContext):\n'
            '    if message.text == "/cancel":',
            '@router.message(AdminEdit.waiting_for_start_msg)\n'
            'async def process_start_msg(message: types.Message, state: FSMContext):\n'
            '    if not message.text:\n'
            '        return await message.answer("❌ يرجى إرسال نص رسالة الترحيب أو /cancel.")\n'
            '    if message.text == "/cancel":',
        ),
        (
            '@router.message(AdminEdit.waiting_for_start_btn2_name)\n'
            'async def process_start_btn2_name(message: types.Message, state: FSMContext):\n'
            '    if message.text == "/cancel":',
            '@router.message(AdminEdit.waiting_for_start_btn2_name)\n'
            'async def process_start_btn2_name(message: types.Message, state: FSMContext):\n'
            '    if not message.text:\n'
            '        return await message.answer("❌ يرجى إرسال الاسم الجديد للزر أو /hide أو /cancel.")\n'
            '    if message.text == "/cancel":',
        ),
        (
            '@router.message(AdminEdit.waiting_for_start_btn2_url)\n'
            'async def process_start_btn2_url(message: types.Message, state: FSMContext):\n'
            '    if message.text == "/cancel":',
            '@router.message(AdminEdit.waiting_for_start_btn2_url)\n'
            'async def process_start_btn2_url(message: types.Message, state: FSMContext):\n'
            '    if not message.text:\n'
            '        return await message.answer("❌ عذراً، الرابط غير صحيح. يجب أن يبدأ بـ http أو https أو tg://")\n'
            '    if message.text == "/cancel":',
        ),
        (
            '@router.message(AdminEdit.waiting_for_start_btn2_text)\n'
            'async def process_start_btn2_text(message: types.Message, state: FSMContext):\n'
            '    if message.text == "/cancel":',
            '@router.message(AdminEdit.waiting_for_start_btn2_text)\n'
            'async def process_start_btn2_text(message: types.Message, state: FSMContext):\n'
            '    if not message.text:\n'
            '        return await message.answer("❌ يرجى إرسال الرسالة النصية أو /cancel.")\n'
            '    if message.text == "/cancel":',
        ),
    ]
    for old_s, new_s in replacements:
        if old_s in content:
            content = content.replace(old_s, new_s, 1)
            if "ISS-12: Added non-text guards in handlers/admin/welcome_settings.py" not in applied:
                applied.append("ISS-12: Added non-text guards in handlers/admin/welcome_settings.py")
    return content, applied


def patch_handlers_admin_recurring(content: str) -> tuple[str, list[str]]:
    """Apply ISS-12 guard in process_rbw_edit_text and ISS-13a media/VIP steps in recurring wizard."""
    applied = []

    old_edit = (
        '@router.message(AdminEdit.waiting_for_rbw_edit_text)\n'
        'async def process_rbw_edit_text(message: types.Message, state: FSMContext):\n'
        '    if message.text == "/cancel":'
    )
    new_edit = (
        '@router.message(AdminEdit.waiting_for_rbw_edit_text)\n'
        'async def process_rbw_edit_text(message: types.Message, state: FSMContext):\n'
        '    if not message.text:\n'
        '        return await message.answer("❌ يرجى إرسال النص الجديد أو /cancel.")\n'
        '    if message.text == "/cancel":'
    )
    if old_edit in content:
        content = content.replace(old_edit, new_edit, 1)
        applied.append("ISS-12: Added non-text guard in process_rbw_edit_text()")

    old_wizard = (
        '@router.message(AdminEdit.waiting_for_rbw_text, F.text)\n'
        'async def process_rbw_text(message: types.Message, state: FSMContext):\n'
        '    if message.text == "/cancel":\n'
        '        await message.answer("❌ تم الإلغاء.")\n'
        '        await state.clear()\n'
        '        return\n'
        '    await state.update_data(rbw_text=message.html_text or message.text)\n'
        '    kb = InlineKeyboardMarkup(inline_keyboard=[\n'
        '        [InlineKeyboardButton(text="كل 6 ساعات", callback_data="rbw_hours_6"),\n'
        '         InlineKeyboardButton(text="كل 12 ساعة", callback_data="rbw_hours_12")],\n'
        '        [InlineKeyboardButton(text="كل 24 ساعة", callback_data="rbw_hours_24"),\n'
        '         InlineKeyboardButton(text="كل 48 ساعة", callback_data="rbw_hours_48")],\n'
        '    ])\n'
        '    await message.answer("🔄 كل كم ساعة تريد تكرار هذه الإذاعة؟", reply_markup=kb, parse_mode=ParseMode.HTML)\n'
        '    await state.set_state(AdminEdit.waiting_for_rbw_hours)\n'
        '\n'
        '\n'
        '@router.callback_query(AdminEdit.waiting_for_rbw_hours, F.data.startswith("rbw_hours_"))\n'
        'async def cb_rbw_hours(callback: types.CallbackQuery, state: FSMContext):\n'
        '    if not await is_admin(callback.from_user.id):\n'
        '        return\n'
        '    data = await state.get_data()\n'
        '    hours = int(callback.data.replace("rbw_hours_", ""))\n'
        '    await create_recurring_broadcast(\n'
        '        target=data.get("rbw_target", "all"),\n'
        '        text=data.get("rbw_text", ""),\n'
        '        repeat_hours=hours,\n'
        '    )\n'
        '    await state.clear()\n'
        '    await callback.message.answer(f"✅ تم إنشاء إذاعة دورية (كل {hours} ساعة)!")\n'
        '    await callback.answer()'
    )
    new_wizard = (
        'async def _ask_rbw_hours(message: types.Message, state: FSMContext) -> None:\n'
        '    kb = InlineKeyboardMarkup(inline_keyboard=[\n'
        '        [InlineKeyboardButton(text="كل 6 ساعات", callback_data="rbw_hours_6"),\n'
        '         InlineKeyboardButton(text="كل 12 ساعة", callback_data="rbw_hours_12")],\n'
        '        [InlineKeyboardButton(text="كل 24 ساعة", callback_data="rbw_hours_24"),\n'
        '         InlineKeyboardButton(text="كل 48 ساعة", callback_data="rbw_hours_48")],\n'
        '    ])\n'
        '    await message.answer("🔄 كل كم ساعة تريد تكرار هذه الإذاعة؟", reply_markup=kb, parse_mode=ParseMode.HTML)\n'
        '    await state.set_state(AdminEdit.waiting_for_rbw_hours)\n'
        '\n'
        '\n'
        '@router.message(AdminEdit.waiting_for_rbw_text, F.text)\n'
        'async def process_rbw_text(message: types.Message, state: FSMContext):\n'
        '    if message.text == "/cancel":\n'
        '        await message.answer("❌ تم الإلغاء.")\n'
        '        await state.clear()\n'
        '        return\n'
        '    await state.update_data(rbw_text=message.html_text or message.text)\n'
        '    await message.answer(\n'
        '        "🖼 أرسل صورة أو فيديو لإرفاقه مع الإذاعة الدورية.\\n"\n'
        '        "أو أرسل /skip للإذاعة النصية فقط.\\n"\n'
        '        "لإلغاء الأمر أرسل /cancel",\n'
        '        parse_mode=ParseMode.HTML,\n'
        '    )\n'
        '    await state.set_state(AdminEdit.waiting_for_rbw_media)\n'
        '\n'
        '\n'
        '@router.message(AdminEdit.waiting_for_rbw_media, F.photo | F.video | F.text)\n'
        'async def process_rbw_media(message: types.Message, state: FSMContext):\n'
        '    if message.text == "/cancel":\n'
        '        await message.answer("❌ تم الإلغاء.")\n'
        '        await state.clear()\n'
        '        return\n'
        '    if message.text == "/skip":\n'
        '        await state.update_data(rbw_media_id=None, rbw_media_type=None, rbw_is_vip=False, rbw_stars=0)\n'
        '        await _ask_rbw_hours(message, state)\n'
        '        return\n'
        '    if message.photo:\n'
        '        await state.update_data(rbw_media_id=message.photo[-1].file_id, rbw_media_type="photo")\n'
        '    elif message.video:\n'
        '        await state.update_data(rbw_media_id=message.video.file_id, rbw_media_type="video")\n'
        '    else:\n'
        '        await message.answer("❌ يجب إرسال صورة أو فيديو، أو /skip، أو /cancel.")\n'
        '        return\n'
        '    kb = InlineKeyboardMarkup(inline_keyboard=[\n'
        '        [InlineKeyboardButton(text="🟢 مجانية (مفتوحة)", callback_data="rbw_vip_free")],\n'
        '        [InlineKeyboardButton(text="⭐️ مدفوعة (VIP - بنجوم تيليجرام)", callback_data="rbw_vip_paid")],\n'
        '    ])\n'
        '    await message.answer(\n'
        '        "💎 هل تريد أن تكون وسائط الإذاعة الدورية مجانية أم مدفوعة بالنجوم؟",\n'
        '        reply_markup=kb,\n'
        '        parse_mode=ParseMode.HTML,\n'
        '    )\n'
        '    await state.set_state(AdminEdit.waiting_for_rbw_vip)\n'
        '\n'
        '\n'
        '@router.callback_query(AdminEdit.waiting_for_rbw_vip, F.data.startswith("rbw_vip_"))\n'
        'async def cb_rbw_vip(callback: types.CallbackQuery, state: FSMContext):\n'
        '    if not await is_admin(callback.from_user.id):\n'
        '        return\n'
        '    if callback.data == "rbw_vip_free":\n'
        '        await state.update_data(rbw_is_vip=False, rbw_stars=0)\n'
        '        await _ask_rbw_hours(callback.message, state)\n'
        '    else:\n'
        '        await state.update_data(rbw_is_vip=True)\n'
        '        await callback.message.answer("⭐️ كم عدد النجوم المطلوبة لفتح المحتوى؟ (أرسل رقماً بين 1 و 2500):")\n'
        '        await state.set_state(AdminEdit.waiting_for_rbw_stars)\n'
        '    await callback.answer()\n'
        '\n'
        '\n'
        '@router.message(AdminEdit.waiting_for_rbw_stars)\n'
        'async def process_rbw_stars(message: types.Message, state: FSMContext):\n'
        '    if not message.text:\n'
        '        return await message.answer("❌ يرجى إرسال أرقام فقط (مثلاً 50).")\n'
        '    if message.text == "/cancel":\n'
        '        await message.answer("❌ تم الإلغاء.")\n'
        '        await state.clear()\n'
        '        return\n'
        '    if not message.text.isdigit() or not (1 <= int(message.text) <= 2500):\n'
        '        return await message.answer("❌ يرجى إرسال رقم بين 1 و 2500.")\n'
        '    await state.update_data(rbw_stars=int(message.text))\n'
        '    await _ask_rbw_hours(message, state)\n'
        '\n'
        '\n'
        '@router.callback_query(AdminEdit.waiting_for_rbw_hours, F.data.startswith("rbw_hours_"))\n'
        'async def cb_rbw_hours(callback: types.CallbackQuery, state: FSMContext):\n'
        '    if not await is_admin(callback.from_user.id):\n'
        '        return\n'
        '    data = await state.get_data()\n'
        '    hours = int(callback.data.replace("rbw_hours_", ""))\n'
        '    await create_recurring_broadcast(\n'
        '        target=data.get("rbw_target", "all"),\n'
        '        text=data.get("rbw_text", ""),\n'
        '        repeat_hours=hours,\n'
        '        media_id=data.get("rbw_media_id"),\n'
        '        media_type=data.get("rbw_media_type"),\n'
        '        is_vip=bool(data.get("rbw_is_vip", False)),\n'
        '        stars=int(data.get("rbw_stars", 0)),\n'
        '    )\n'
        '    await state.clear()\n'
        '    await callback.message.answer(f"✅ تم إنشاء إذاعة دورية (كل {hours} ساعة)!")\n'
        '    await callback.answer()'
    )
    if "async def process_rbw_media" not in content:
        if old_wizard not in content:
            raise RuntimeError("Could not locate recurring broadcast wizard in handlers/admin/recurring.py")
        content = content.replace(old_wizard, new_wizard, 1)
        applied.append("ISS-13: Added media and VIP steps to recurring broadcast creation wizard")

    return content, applied


# ── 10. handlers/user/my_campaign.py (ISS-12, ISS-14a, ISS-14b, ISS-18a) ─────

def patch_handlers_user_my_campaign(content: str) -> tuple[str, list[str]]:
    applied = []

    # 1. ISS-18a: Fix daily limit text (2 -> 5)
    if "You've used both campaigns for today." in content:
        content = content.replace(
            "You've used both campaigns for today. Try again tomorrow.",
            "You've used all 5 campaigns for today. Try again tomorrow.",
            1,
        )
        content = content.replace(
            "This will count as one of your 2 daily campaigns.",
            "This will count as one of your 5 daily campaigns.",
            1,
        )
        applied.append("ISS-18: Unified daily campaign quota messages to 5/day in handlers/user/my_campaign.py")

    # 2. ISS-14b: Only show Send Now when status == 'active', and verify in cb_user_send_now
    old_send_btn = '    if current["status"] in ("active", "paused") and current["mode"] == "immediate":'
    new_send_btn = '    if current["status"] == "active" and current["mode"] == "immediate":'
    if old_send_btn in content:
        content = content.replace(old_send_btn, new_send_btn, 1)

    old_send_now = (
        '@router.callback_query(F.data.startswith("user_send_now_"))\n'
        'async def cb_user_send_now(callback: types.CallbackQuery):\n'
        '    cid = int(callback.data.split("_")[-1])\n'
        '    user_id = callback.from_user.id\n'
        '    if not await _check_feature(callback):\n'
        '        return\n'
        '    current = await get_current_campaign(user_id)\n'
        '    if not current or current["id"] != cid:\n'
        '        await callback.answer("Campaign not found.", show_alert=True)\n'
        '        return\n'
        '    await callback.message.edit_text("🚀 Sending campaign... please wait.")'
    )
    new_send_now = (
        '@router.callback_query(F.data.startswith("user_send_now_"))\n'
        'async def cb_user_send_now(callback: types.CallbackQuery):\n'
        '    cid = int(callback.data.split("_")[-1])\n'
        '    user_id = callback.from_user.id\n'
        '    if not await _check_feature(callback):\n'
        '        return\n'
        '    current = await get_current_campaign(user_id)\n'
        '    if not current or current["id"] != cid:\n'
        '        await callback.answer("Campaign not found.", show_alert=True)\n'
        '        return\n'
        '    if current["status"] != "active":\n'
        '        await callback.answer("⏸ Campaign is not active. Resume it first.", show_alert=True)\n'
        '        return\n'
        '    await callback.message.edit_text("🚀 Sending campaign... please wait.")'
    )
    if 'if current["status"] != "active":' not in content:
        if old_send_now not in content:
            raise RuntimeError("Could not locate cb_user_send_now in handlers/user/my_campaign.py")
        content = content.replace(old_send_now, new_send_now, 1)
        applied.append("ISS-14: Blocked Send Now on paused/suspended campaigns in handlers/user/my_campaign.py")

    # 3. ISS-12 & ISS-14a: Guard non-text inputs and prevent skipping both text and photo
    old_ucw_text_and_photo = (
        '@router.message(UserCampaignWizard.text)\n'
        'async def process_ucw_text(message: types.Message, state: FSMContext):\n'
        '    text = message.text\n'
        '    if text == "/cancel":\n'
        '        await state.clear()\n'
        '        await message.answer("❌ Campaign creation cancelled. No quota consumed.")\n'
        '        return\n'
        '\n'
        '    skip = text == "/skip"\n'
        '    await state.update_data(text=None if skip else (message.html_text or text))\n'
        '    await message.answer(\n'
        '        "📸 <b>Step 2/5 — Photo (optional)</b>\\n\\n"\n'
        '        "Send a photo to include with the campaign, or /skip for text-only.",\n'
        '        parse_mode=ParseMode.HTML,\n'
        '    )\n'
        '    await state.set_state(UserCampaignWizard.photo)\n'
        '\n'
        '\n'
        '@router.message(UserCampaignWizard.photo, F.photo)\n'
        'async def process_ucw_photo(message: types.Message, state: FSMContext):\n'
        '    file_id = message.photo[-1].file_id\n'
        '    await state.update_data(photo_file_id=file_id)\n'
        '    await _ask_buttons(message, state)\n'
        '\n'
        '\n'
        '@router.message(UserCampaignWizard.photo, F.text)\n'
        'async def process_ucw_photo_text(message: types.Message, state: FSMContext):\n'
        '    if message.text == "/cancel":\n'
        '        await state.clear()\n'
        '        await message.answer("❌ Campaign creation cancelled.")\n'
        '        return\n'
        '    await state.update_data(photo_file_id=None)\n'
        '    await _ask_buttons(message, state)'
    )
    new_ucw_text_and_photo = (
        '@router.message(UserCampaignWizard.text)\n'
        'async def process_ucw_text(message: types.Message, state: FSMContext):\n'
        '    if not message.text:\n'
        '        await message.answer("❌ Please send text, /skip, or /cancel.")\n'
        '        return\n'
        '    text = message.text\n'
        '    if text == "/cancel":\n'
        '        await state.clear()\n'
        '        await message.answer("❌ Campaign creation cancelled. No quota consumed.")\n'
        '        return\n'
        '\n'
        '    skip = text == "/skip"\n'
        '    await state.update_data(text=None if skip else (message.html_text or text))\n'
        '    await message.answer(\n'
        '        "📸 <b>Step 2/5 — Photo (optional)</b>\\n\\n"\n'
        '        "Send a photo to include with the campaign, or /skip for text-only.",\n'
        '        parse_mode=ParseMode.HTML,\n'
        '    )\n'
        '    await state.set_state(UserCampaignWizard.photo)\n'
        '\n'
        '\n'
        '@router.message(UserCampaignWizard.photo, F.photo)\n'
        'async def process_ucw_photo(message: types.Message, state: FSMContext):\n'
        '    file_id = message.photo[-1].file_id\n'
        '    await state.update_data(photo_file_id=file_id)\n'
        '    await _ask_buttons(message, state)\n'
        '\n'
        '\n'
        '@router.message(UserCampaignWizard.photo, F.text)\n'
        'async def process_ucw_photo_text(message: types.Message, state: FSMContext):\n'
        '    if message.text == "/cancel":\n'
        '        await state.clear()\n'
        '        await message.answer("❌ Campaign creation cancelled.")\n'
        '        return\n'
        '    if message.text != "/skip":\n'
        '        await message.answer("❌ Please send a photo, /skip, or /cancel.")\n'
        '        return\n'
        '    data = await state.get_data()\n'
        '    if not data.get("text"):\n'
        '        await message.answer(\n'
        '            "❌ Cannot skip photo because you already skipped text. "\n'
        '            "A campaign must have either text or a photo.\\n"\n'
        '            "Please send a photo or /cancel."\n'
        '        )\n'
        '        return\n'
        '    await state.update_data(photo_file_id=None)\n'
        '    await _ask_buttons(message, state)'
    )
    if "Cannot skip photo because you already skipped text" not in content:
        if old_ucw_text_and_photo not in content:
            raise RuntimeError("Could not locate process_ucw_text / process_ucw_photo_text in handlers/user/my_campaign.py")
        content = content.replace(old_ucw_text_and_photo, new_ucw_text_and_photo, 1)
        applied.append("ISS-14: Prevented skipping both text and photo in UserCampaignWizard")

    # 4. ISS-12 guards in buttons, groups, mode steps
    other_guards = [
        (
            '@router.message(UserCampaignWizard.buttons)\n'
            'async def process_ucw_buttons(message: types.Message, state: FSMContext):\n'
            '    if message.text == "/cancel":',
            '@router.message(UserCampaignWizard.buttons)\n'
            'async def process_ucw_buttons(message: types.Message, state: FSMContext):\n'
            '    if not message.text:\n'
            '        return await message.answer("❌ Please send button definitions, /skip, or /cancel.")\n'
            '    if message.text == "/cancel":',
        ),
        (
            '@router.message(UserCampaignWizard.groups)\n'
            'async def process_ucw_groups(message: types.Message, state: FSMContext):\n'
            '    if message.text == "/cancel":',
            '@router.message(UserCampaignWizard.groups)\n'
            'async def process_ucw_groups(message: types.Message, state: FSMContext):\n'
            '    if not message.text:\n'
            '        return await message.answer("❌ Invalid selection. Enter group numbers like: 1,2,3")\n'
            '    if message.text == "/cancel":',
        ),
        (
            '@router.message(UserCampaignWizard.mode)\n'
            'async def process_ucw_mode(message: types.Message, state: FSMContext):\n'
            '    if message.text == "/cancel":',
            '@router.message(UserCampaignWizard.mode)\n'
            'async def process_ucw_mode(message: types.Message, state: FSMContext):\n'
            '    if not message.text:\n'
            '        return await message.answer("❌ Enter \'now\' for immediate or a number of hours (min 6).")\n'
            '    if message.text == "/cancel":',
        ),
    ]
    for old_g, new_g in other_guards:
        if old_g in content:
            content = content.replace(old_g, new_g, 1)
            if "ISS-12: Added non-text guards in UserCampaignWizard" not in applied:
                applied.append("ISS-12: Added non-text guards in UserCampaignWizard")

    return content, applied


def run_repair(dry_run: bool = False) -> int:
    print("=" * 65)
    print(f"Deploy Links Bot — Phase 3 Repair ({'DRY-RUN' if dry_run else 'APPLY'})")
    print("=" * 65)

    for rel_path in TARGET_FILES:
        if not (PROJECT_ROOT / rel_path).exists():
            print(f"[ERROR] Missing required file: {rel_path}")
            return 1

    create_backups(dry_run=dry_run)

    patchers = [
        ("states/states.py", patch_states),
        ("models/users.py", patch_models_users),
        ("models/events.py", patch_models_events),
        ("models/campaigns.py", patch_models_campaigns),
        ("services/promo.py", patch_services_promo),
        ("services/campaign.py", patch_services_campaign),
        ("services/broadcast.py", patch_services_broadcast),
        ("services/user_broadcast.py", patch_services_user_broadcast),
        ("handlers/admin/admins.py", patch_handlers_admin_admins),
        ("handlers/admin/broadcast.py", patch_handlers_admin_broadcast),
        ("handlers/admin/button_manager.py", patch_handlers_admin_button_manager),
        ("handlers/admin/campaigns.py", patch_handlers_admin_campaigns),
        ("handlers/admin/general_settings.py", patch_handlers_admin_general_settings),
        ("handlers/admin/promo_settings.py", patch_handlers_admin_promo_settings),
        ("handlers/admin/welcome_settings.py", patch_handlers_admin_welcome_settings),
        ("handlers/admin/recurring.py", patch_handlers_admin_recurring),
        ("handlers/user/my_campaign.py", patch_handlers_user_my_campaign),
    ]

    updated_contents: dict[str, str] = {}
    all_changes: list[str] = []

    for rel_path, patch_fn in patchers:
        raw = (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")
        new_code, changes = patch_fn(raw)
        verify_python_syntax(new_code, rel_path)
        updated_contents[rel_path] = new_code
        all_changes.extend(changes)

    if not dry_run:
        for rel_path, new_code in updated_contents.items():
            (PROJECT_ROOT / rel_path).write_text(new_code, encoding="utf-8")

    if all_changes:
        print("\nChanges applied:")
        for ch in all_changes:
            print(f"  [OK] {ch}")
    else:
        print("\n[INFO] All Phase 3 fixes are already applied (idempotent check passed).")

    print("\n[SUCCESS] Phase 3 repair completed cleanly.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 3 Repair Script")
    parser.add_argument("--dry-run", action="store_true", help="Simulate changes without modifying files")
    parser.add_argument("--rollback", action="store_true", help="Restore files from Phase 3 backup")
    args = parser.parse_args()

    if args.rollback:
        sys.exit(rollback())
    sys.exit(run_repair(dry_run=args.dry_run))
