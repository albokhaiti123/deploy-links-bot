#!/usr/bin/env python3
"""
Cumulative Test Suite — Phase 1 (tests/phase1_test.py)
Includes:
  - Suite A: All 12 foundational tests from test_user_campaigns.py
  - Suite B: All 6 worker safety tests from test_worker_safety.py
  - Suite C: 7 new verification tests for Phase 1 repairs (ISS-01, ISS-02, ISS-03, ISS-04, ISS-06, ISS-11)
Total: 25 cumulative tests.
"""

import asyncio
import json
import os
import sys
import tempfile
import unittest.mock as mock
from datetime import datetime, timedelta

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
TEST_DB = _tmp_db.name

os.environ["DB_NAME"] = TEST_DB
os.environ["ADMIN_ID"] = "999999"
os.environ["BOT_TOKEN"] = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
os.environ["BOT_USERNAME"] = "testbot"
os.environ["QUOTA_TIMEZONE"] = "UTC"

from tests.test_user_campaigns import (
    setup_db,
    test_01_quota_two_per_day,
    test_02_quota_not_restored_on_delete,
    test_03_replacement_consumes_quota,
    test_04_one_active_campaign_per_user,
    test_05_reward_owner_preserved_on_readd,
    test_06_user_cannot_access_other_groups,
    test_07_user_cannot_target_others_groups,
    test_08_feature_disabled_blocks_creation,
    test_09_recurring_minimum_6_hours,
    test_10_generation_fencing,
    test_11_quota_not_consumed_without_commit,
    test_12_buttons_validation,
)
from tests.test_worker_safety import (
    test_T1_old_worker_stops_after_replacement,
    test_T2_old_worker_stops_after_global_suspend,
    test_T3_no_new_sends_after_suspend_completes,
    test_T4_two_workers_cannot_claim_same_campaign,
    test_T5_no_resend_of_confirmed_messages,
    test_T6_execute_campaign_with_mocked_telegram,
)


# ── Phase 1 Specific Tests (Suite C) ─────────────────────────────────────────

async def test_P1_01_verify_campaign_groups_unpacking_iss01():
    """ISS-01: verify_campaign_groups unpacks 3-tuple from get_user_active_groups without ValueError."""
    from models.campaigns import create_campaign, get_user_progress
    from models.groups import upsert_group
    import services.campaign as camp_service

    user_id = 910001
    await upsert_group(-1009101, "Alpha Group", "supergroup", added_by=user_id)
    await upsert_group(-1009102, "Beta Group", "supergroup", added_by=user_id)

    cid = await create_campaign({
        "name": "Phase1 Unlock Test",
        "promo_text": "Join to unlock",
        "button_text": "Unlock",
        "required_groups": 2,
        "unlock_content": "Secret Link",
    })

    # Mock bot methods used in verify_campaign_groups & show_campaign_progress
    fake_bot = mock.MagicMock()
    me_obj = mock.MagicMock()
    me_obj.id = 777000
    me_obj.username = "testbot"
    fake_bot.get_me = mock.AsyncMock(return_value=me_obj)

    member_obj = mock.MagicMock()
    member_obj.status = "administrator"
    fake_bot.get_chat_member = mock.AsyncMock(return_value=member_obj)

    fake_callback = mock.MagicMock()
    fake_callback.from_user.id = user_id
    fake_callback.answer = mock.AsyncMock()
    fake_callback.message.edit_text = mock.AsyncMock()
    fake_callback.message.answer = mock.AsyncMock()

    orig_bot = camp_service.bot
    camp_service.bot = fake_bot
    try:
        await camp_service.verify_campaign_groups(fake_callback, cid)
    finally:
        camp_service.bot = orig_bot

    progress = await get_user_progress(cid, user_id)
    assert progress is not None, "Progress record should exist"
    assert progress[0] == 2, f"Expected 2 verified groups, got {progress[0]}"
    assert progress[1] == "unlocked", f"Expected status='unlocked', got {progress[1]}"
    print("  PASS test_P1_01_verify_campaign_groups_unpacking_iss01")


async def test_P1_02_recurring_campaign_schedule_comparison_iss02():
    """ISS-02: Future next_run_at (+6h) must NOT be returned as due 5 minutes later."""
    from services.user_broadcast import create_user_campaign
    from models.user_campaigns import update_campaign_next_run, get_due_recurring_campaigns
    from models.groups import upsert_group
    from models.settings import set_setting

    user_id = 910002
    await set_setting("user_campaigns_enabled", "true")
    await upsert_group(-1009201, "Recurring Group", "supergroup", added_by=user_id)

    cid, err = await create_user_campaign(
        user_id=user_id,
        text="Recurring every 6h",
        photo_file_id=None,
        buttons_json=None,
        target_chat_ids=[-1009201],
        mode="recurring",
        repeat_hours=6,
    )
    assert cid is not None, f"Failed to create recurring campaign: {err}"

    # Schedule 6 hours in the future
    future_time = datetime.now() + timedelta(hours=6)
    await update_campaign_next_run(cid, future_time)

    due_now = await get_due_recurring_campaigns()
    due_ids = [c["id"] for c in due_now]
    assert cid not in due_ids, (
        f"ISS-02 regression: Campaign {cid} scheduled +6h in future was returned as due immediately!"
    )

    # Schedule 1 minute in the past -> must be returned as due
    past_time = datetime.now() - timedelta(minutes=1)
    await update_campaign_next_run(cid, past_time)

    due_after = await get_due_recurring_campaigns()
    due_after_ids = [c["id"] for c in due_after]
    assert cid in due_after_ids, f"Campaign {cid} with past next_run_at should be due"
    print("  PASS test_P1_02_recurring_campaign_schedule_comparison_iss02")


async def test_P1_03_legacy_groups_reward_owner_backfill_iss03():
    """ISS-03: Legacy groups with added_by set and reward_owner_id=NULL are backfilled by init_db()."""
    from core.database import get_db, init_db
    from models.groups import get_user_active_groups

    legacy_user = 910003
    legacy_chat_id = -1009301

    async with get_db() as db:
        await db.execute(
            "INSERT INTO groups (chat_id, title, chat_type, status, added_at, updated_at, added_by, reward_owner_id) "
            "VALUES (?, 'Legacy Group', 'supergroup', 'active', datetime('now'), datetime('now'), ?, NULL)",
            (legacy_chat_id, legacy_user),
        )
        await db.commit()

    # Before init_db backfill, reward_owner_id is NULL
    await init_db()

    owned_groups = await get_user_active_groups(legacy_user)
    owned_ids = [g[0] for g in owned_groups]
    assert legacy_chat_id in owned_ids, "Legacy group should be backfilled with reward_owner_id = added_by"
    print("  PASS test_P1_03_legacy_groups_reward_owner_backfill_iss03")


async def test_P1_04_resume_suspended_admin_campaign_iss04():
    """ISS-04: Campaign suspended by global disable can be resumed and executed after re-enable."""
    from services.user_broadcast import create_user_campaign, execute_user_campaign, _get_generation
    from models.user_campaigns import (
        suspend_all_active_campaigns,
        resume_user_campaign,
        get_campaign_by_id,
    )
    from models.groups import upsert_group
    from models.settings import get_setting, set_setting
    import services.user_broadcast as ub_module

    user_id = 910004
    chat_id = -1009401
    await set_setting("user_campaigns_enabled", "true")
    await upsert_group(chat_id, "Suspend Resume Group", "supergroup", added_by=user_id)

    cid, err = await create_user_campaign(
        user_id=user_id,
        text="Resumable campaign",
        photo_file_id=None,
        buttons_json=None,
        target_chat_ids=[chat_id],
        mode="recurring",
        repeat_hours=6,
    )
    assert cid is not None, f"Creation failed: {err}"

    # Simulate owner global disable
    gen_before = await _get_generation()
    await set_setting("user_campaigns_generation", str(gen_before + 1))
    await set_setting("user_campaigns_enabled", "false")
    await suspend_all_active_campaigns()

    c_suspended = await get_campaign_by_id(cid)
    assert c_suspended["status"] == "suspended_admin"

    # Simulate owner re-enabling feature and user resuming campaign
    await set_setting("user_campaigns_enabled", "true")
    new_gen = await _get_generation()
    await resume_user_campaign(cid, new_gen)

    c_resumed = await get_campaign_by_id(cid)
    assert c_resumed["status"] == "active"
    assert c_resumed["system_generation"] == new_gen

    # Execute with mocked Telegram send
    mock_bot = mock.MagicMock()
    fake_msg = mock.MagicMock()
    fake_msg.message_id = 12345
    mock_bot.send_message = mock.AsyncMock(return_value=fake_msg)

    orig_bot = ub_module.bot
    ub_module.bot = mock_bot
    try:
        stats = await execute_user_campaign(cid)
    finally:
        ub_module.bot = orig_bot

    assert stats.get("sent") == 1, f"Expected 1 sent message after resume, got: {stats}"
    print("  PASS test_P1_04_resume_suspended_admin_campaign_iss04")


async def test_P1_05_sqlite_pragmas_and_indexes_iss06():
    """ISS-06: Verify WAL mode, busy_timeout, foreign_keys=ON, and new indexes on get_db()."""
    from core.database import get_db

    async with get_db() as db:
        async with db.execute("PRAGMA journal_mode") as c:
            journal_mode = (await c.fetchone())[0]
        async with db.execute("PRAGMA busy_timeout") as c:
            busy_timeout = (await c.fetchone())[0]
        async with db.execute("PRAGMA foreign_keys") as c:
            fk_enabled = (await c.fetchone())[0]
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ) as c:
            indexes = {row[0] for row in await c.fetchall()}

    assert journal_mode.lower() == "wal", f"Expected WAL journal_mode, got {journal_mode}"
    assert int(busy_timeout) >= 5000, f"Expected busy_timeout >= 5000, got {busy_timeout}"
    assert int(fk_enabled) == 1, f"Expected foreign_keys=1, got {fk_enabled}"
    assert "idx_groups_reward_owner_status" in indexes, "Missing idx_groups_reward_owner_status"
    assert "idx_events_type_created" in indexes, "Missing idx_events_type_created"
    assert "idx_broadcast_messages_delete_at" in indexes, "Missing idx_broadcast_messages_delete_at"
    print("  PASS test_P1_05_sqlite_pragmas_and_indexes_iss06")


async def test_P1_06_fk_safety_for_unregistered_user_iss06():
    """ISS-06: Creating a campaign for a user not yet in `users` table succeeds with foreign_keys=ON."""
    from services.user_broadcast import create_user_campaign
    from models.groups import upsert_group
    from models.settings import set_setting

    unregistered_user = 910006
    chat_id = -1009601
    await set_setting("user_campaigns_enabled", "true")
    await upsert_group(chat_id, "FK Safety Group", "supergroup", added_by=unregistered_user)

    cid, err = await create_user_campaign(
        user_id=unregistered_user,
        text="FK safety test",
        photo_file_id=None,
        buttons_json=None,
        target_chat_ids=[chat_id],
        mode="immediate",
        repeat_hours=0,
    )
    assert cid is not None, f"Campaign creation failed under foreign_keys=ON: {err}"
    print("  PASS test_P1_06_fk_safety_for_unregistered_user_iss06")


async def test_P1_07_recover_stale_claims_force_and_ttl_iss11():
    """ISS-11: recover_stale_claims(force_all=True) recovers running campaigns immediately on restart."""
    from services.user_broadcast import create_user_campaign
    from models.user_campaigns import (
        claim_execution,
        set_campaign_run_id,
        update_campaign_status,
        recover_stale_claims,
        get_campaign_by_id,
    )
    from models.groups import upsert_group
    from models.settings import set_setting

    user_id = 910007
    chat_id = -1009701
    await set_setting("user_campaigns_enabled", "true")
    await upsert_group(chat_id, "Recovery Group", "supergroup", added_by=user_id)

    cid, err = await create_user_campaign(
        user_id=user_id,
        text="Crash recovery test",
        photo_file_id=None,
        buttons_json=None,
        target_chat_ids=[chat_id],
        mode="recurring",
        repeat_hours=6,
    )
    assert cid is not None, f"Creation failed: {err}"

    # Simulate worker claiming execution just before process restart (TTL is still +30m in future)
    claimed = await claim_execution(cid, "run-before-crash")
    assert claimed is True
    await set_campaign_run_id(cid, "run-before-crash")
    await update_campaign_status(cid, "running")

    # Startup recovery with force_all=True must recover it immediately
    await recover_stale_claims(force_all=True)

    c_after = await get_campaign_by_id(cid)
    assert c_after["status"] == "active", f"Expected status='active', got {c_after['status']}"
    assert c_after["run_id"] is None, f"Expected run_id=None, got {c_after['run_id']}"

    # A new worker must now be able to claim execution
    reclaimed = await claim_execution(cid, "run-after-restart")
    assert reclaimed is True, "New worker should be able to claim execution after force recovery"
    await recover_stale_claims(force_all=True)
    print("  PASS test_P1_07_recover_stale_claims_force_and_ttl_iss11")


async def run_phase1_suite() -> bool:
    print("=" * 65)
    print("Running Phase 1 Cumulative Test Suite (25 tests)")
    print("=" * 65)
    await setup_db()

    all_tests = [
        # Suite A: Original user campaign tests (12)
        test_01_quota_two_per_day,
        test_02_quota_not_restored_on_delete,
        test_03_replacement_consumes_quota,
        test_04_one_active_campaign_per_user,
        test_05_reward_owner_preserved_on_readd,
        test_06_user_cannot_access_other_groups,
        test_07_user_cannot_target_others_groups,
        test_08_feature_disabled_blocks_creation,
        test_09_recurring_minimum_6_hours,
        test_10_generation_fencing,
        test_11_quota_not_consumed_without_commit,
        test_12_buttons_validation,
        # Suite B: Original worker safety tests (6)
        test_T1_old_worker_stops_after_replacement,
        test_T2_old_worker_stops_after_global_suspend,
        test_T3_no_new_sends_after_suspend_completes,
        test_T4_two_workers_cannot_claim_same_campaign,
        test_T5_no_resend_of_confirmed_messages,
        test_T6_execute_campaign_with_mocked_telegram,
        # Suite C: Phase 1 repair verification tests (7)
        test_P1_01_verify_campaign_groups_unpacking_iss01,
        test_P1_02_recurring_campaign_schedule_comparison_iss02,
        test_P1_03_legacy_groups_reward_owner_backfill_iss03,
        test_P1_04_resume_suspended_admin_campaign_iss04,
        test_P1_05_sqlite_pragmas_and_indexes_iss06,
        test_P1_06_fk_safety_for_unregistered_user_iss06,
        test_P1_07_recover_stale_claims_force_and_ttl_iss11,
    ]

    passed = 0
    failed = 0
    for test_fn in all_tests:
        try:
            await test_fn()
            passed += 1
        except Exception as exc:
            import traceback
            print(f"  FAIL {test_fn.__name__}: {type(exc).__name__}: {exc}")
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 65)
    print(f"Phase 1 Cumulative Results: {passed}/{len(all_tests)} passed, {failed} failed")
    print("=" * 65)
    return failed == 0


if __name__ == "__main__":
    ok = asyncio.run(run_phase1_suite())
    try:
        os.unlink(TEST_DB)
    except OSError:
        pass
    sys.exit(0 if ok else 1)
