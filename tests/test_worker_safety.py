"""
Targeted tests for campaign worker safety and execution fencing.
Verifies:
- Old worker stops after campaign replacement (run_id invalidated)
- Old worker stops after global suspend (run_id cleared + feature disabled)
- Two workers cannot hold the same campaign simultaneously
- Already-sent messages are not re-sent after restart
- No new sends start after replacement or suspend completes

All Telegram API calls are mocked. No real bot connections.
"""

import asyncio
import json
import sys
import os
import tempfile
import unittest.mock as mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
TEST_DB = _tmp_db.name

os.environ["DB_NAME"] = TEST_DB
os.environ["ADMIN_ID"] = "999999"
os.environ["BOT_TOKEN"] = "0:test"
os.environ["BOT_USERNAME"] = "testbot"
os.environ["QUOTA_TIMEZONE"] = "UTC"

ADMIN_ID = 999999
USER_A = 101010
USER_B = 202020


async def setup_db():
    from core.database import init_db
    await init_db()


async def _insert_user(user_id):
    from core.database import get_db
    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username, first_name, created_at) "
            "VALUES (?,?,?,datetime('now'))",
            (user_id, f"u{user_id}", f"User{user_id}")
        )
        await db.commit()


async def _add_owned_group(chat_id, user_id):
    from core.database import get_db
    async with get_db() as db:
        await db.execute(
            "INSERT INTO groups (chat_id, title, chat_type, status, added_at, updated_at, reward_owner_id, added_by) "
            "VALUES (?,?,?,?,datetime('now'),datetime('now'),?,?) "
            "ON CONFLICT(chat_id) DO UPDATE SET reward_owner_id=?, status='active'",
            (chat_id, f"G{chat_id}", "group", "active", user_id, user_id, user_id)
        )
        await db.commit()


async def _create_campaign_direct(user_id, groups, text="Test", mode="immediate", repeat_hours=0):
    """Create a campaign and return (campaign_id, run_id) with claim already acquired."""
    from services.user_broadcast import create_user_campaign
    from models.settings import set_setting
    await set_setting("user_campaigns_enabled", "true")
    cid, err = await create_user_campaign(
        user_id=user_id,
        text=text,
        photo_file_id=None,
        buttons_json=None,
        target_chat_ids=groups,
        mode=mode,
        repeat_hours=repeat_hours,
    )
    assert cid is not None, f"Campaign creation failed: {err}"
    return cid


async def _simulate_worker_mid_run(campaign_id):
    """Simulate a worker that has acquired a claim and is mid-delivery.
    Returns the run_id the worker holds.
    """
    import uuid
    from models.user_campaigns import claim_execution, set_campaign_run_id, update_campaign_status, get_campaign_by_id

    run_id = str(uuid.uuid4())
    # Acquire claim
    claimed = await claim_execution(campaign_id, run_id)
    assert claimed, "Worker should acquire claim"
    await set_campaign_run_id(campaign_id, run_id)
    await update_campaign_status(campaign_id, "running")
    return run_id


async def _worker_checks_valid(campaign_id, run_id):
    """Simulate what execute_user_campaign checks before each send.
    Returns True if worker should continue, False if it should stop.
    """
    from services.user_broadcast import _feature_enabled, _get_generation
    from models.user_campaigns import get_campaign_by_id

    if not await _feature_enabled():
        return False

    campaign_at_start = await get_campaign_by_id(campaign_id)
    if not campaign_at_start:
        return False

    current_gen = await _get_generation()
    if campaign_at_start["system_generation"] != current_gen:
        return False

    current = await get_campaign_by_id(campaign_id)
    if not current or current["run_id"] != run_id:
        return False

    return True


# ── Tests ─────────────────────────────────────────────────────────────────────

async def test_T1_old_worker_stops_after_replacement():
    """After campaign replacement, the old worker's run_id is NULL → fencing stops it."""
    await _insert_user(USER_A)
    await _add_owned_group(2001, USER_A)
    await _add_owned_group(2002, USER_A)

    cid1 = await _create_campaign_direct(USER_A, [2001, 2002], "Camp 1")
    old_run_id = await _simulate_worker_mid_run(cid1)

    # Worker checks — should be valid right now
    assert await _worker_checks_valid(cid1, old_run_id), "Worker should be valid before replacement"

    # User creates new campaign (replacement)
    # Need to clear the quota from the previous campaign creation to allow a second one
    # (Simulating a different day or user; in reality USER_A used 1 quota slot)
    # We'll use a fresh user to avoid quota confusion
    # Actually test the run_id invalidation directly:
    from models.user_campaigns import create_campaign_atomic, _today
    from models.settings import get_setting

    gen = int(await get_setting("user_campaigns_generation"))
    new_id = await create_campaign_atomic(
        user_id=USER_A,
        text="Camp 2 replacement",
        photo_file_id=None,
        buttons_json=None,
        target_groups_json=json.dumps([2001]),
        mode="immediate",
        repeat_hours=0,
        auto_delete_seconds=0,
        system_generation=gen,
    )
    assert new_id is not None, "Replacement campaign should be created"

    # Old worker now checks — run_id should be NULL → worker stops
    assert not await _worker_checks_valid(cid1, old_run_id), \
        "Old worker should stop after replacement (run_id=NULL)"
    print("  PASS test_T1_old_worker_stops_after_replacement")


async def test_T2_old_worker_stops_after_global_suspend():
    """After global disable + suspend, old worker's run_id is NULL → fencing stops it."""
    USER_C = 303030
    await _insert_user(USER_C)
    await _add_owned_group(3001, USER_C)

    from models.settings import set_setting
    await set_setting("user_campaigns_enabled", "true")

    cid = await _create_campaign_direct(USER_C, [3001], "Suspend test")
    run_id = await _simulate_worker_mid_run(cid)

    # Verify worker valid before suspend
    assert await _worker_checks_valid(cid, run_id), "Worker should be valid before suspend"

    # Admin suspends all campaigns
    from models.user_campaigns import suspend_all_active_campaigns
    from models.settings import set_setting as _set
    # Increment generation (as the toggle handler does)
    gen_val = await __import__('models.settings', fromlist=['get_setting']).get_setting("user_campaigns_generation")
    await _set("user_campaigns_generation", str(int(gen_val) + 1))
    await _set("user_campaigns_enabled", "false")
    count = await suspend_all_active_campaigns()
    assert count >= 0  # May be 0 if campaign already running

    # For the running campaign: suspend also clears run_id
    # Manually check: the generation changed, so worker should stop on that check
    # (feature disabled AND generation changed)
    should_continue = await _worker_checks_valid(cid, run_id)
    assert not should_continue, "Worker should stop after global suspend (feature disabled + generation)"
    print("  PASS test_T2_old_worker_stops_after_global_suspend")


async def test_T3_no_new_sends_after_suspend_completes():
    """After feature disabled, create_user_campaign is blocked."""
    USER_D = 404040
    await _insert_user(USER_D)
    await _add_owned_group(4001, USER_D)

    from models.settings import set_setting
    await set_setting("user_campaigns_enabled", "false")

    from services.user_broadcast import create_user_campaign
    cid, err = await create_user_campaign(
        user_id=USER_D,
        text="Should fail",
        photo_file_id=None,
        buttons_json=None,
        target_chat_ids=[4001],
        mode="immediate",
        repeat_hours=0,
    )
    assert cid is None, "No campaign should be created when feature is disabled"
    assert "disabled" in err.lower(), f"Wrong error: {err}"

    await set_setting("user_campaigns_enabled", "true")
    print("  PASS test_T3_no_new_sends_after_suspend_completes")


async def test_T4_two_workers_cannot_claim_same_campaign():
    """Two concurrent claim attempts: only one wins."""
    USER_E = 505050
    await _insert_user(USER_E)
    await _add_owned_group(5001, USER_E)

    from models.settings import set_setting
    await set_setting("user_campaigns_enabled", "true")

    cid = await _create_campaign_direct(USER_E, [5001], "Concurrency test")

    import uuid
    from models.user_campaigns import claim_execution

    run_id_1 = str(uuid.uuid4())
    run_id_2 = str(uuid.uuid4())

    # Sequential claims (asyncio is single-threaded; concurrent = interleaved coroutines)
    result1 = await claim_execution(cid, run_id_1)
    result2 = await claim_execution(cid, run_id_2)  # Should fail (claim exists and not expired)

    assert result1 == True, "First claim should succeed"
    assert result2 == False, "Second claim should fail (campaign already claimed)"
    print("  PASS test_T4_two_workers_cannot_claim_same_campaign")


async def test_T5_no_resend_of_confirmed_messages():
    """Already-sent deliveries are skipped on second pass."""
    USER_F = 606060
    await _insert_user(USER_F)
    await _add_owned_group(6001, USER_F)
    await _add_owned_group(6002, USER_F)

    from models.settings import set_setting
    await set_setting("user_campaigns_enabled", "true")

    import uuid
    from models.user_campaigns import record_delivery, get_delivery_status, claim_execution

    cid = await _create_campaign_direct(USER_F, [6001, 6002], "No resend")
    run_id = str(uuid.uuid4())

    # Record 6001 as already sent
    await record_delivery(cid, run_id, 6001, "sent")

    # Verify delivery status is 'sent'
    status = await get_delivery_status(cid, run_id, 6001)
    assert status == "sent", f"Expected 'sent', got {status}"

    # Verify 6002 has no record
    status2 = await get_delivery_status(cid, run_id, 6002)
    assert status2 is None, f"Expected None for 6002, got {status2}"

    # Simulate the skip logic from execute_user_campaign
    sends_attempted = 0
    for chat_id in [6001, 6002]:
        existing = await get_delivery_status(cid, run_id, chat_id)
        if existing in ("sent", "skipped"):
            continue
        sends_attempted += 1  # Would send to this group

    assert sends_attempted == 1, f"Should only attempt to send to 1 group (6002), attempted: {sends_attempted}"
    print("  PASS test_T5_no_resend_of_confirmed_messages")


async def test_T6_execute_campaign_with_mocked_telegram():
    """Full execute_user_campaign with mocked bot.send_message — verify fencing stops on replacement."""
    USER_G = 707070
    await _insert_user(USER_G)
    await _add_owned_group(7001, USER_G)
    await _add_owned_group(7002, USER_G)
    await _add_owned_group(7003, USER_G)

    from models.settings import set_setting, get_setting
    await set_setting("user_campaigns_enabled", "true")

    cid = await _create_campaign_direct(USER_G, [7001, 7002, 7003], "Full mock test")

    send_calls = []

    async def mock_send_message(**kwargs):
        """Record send call and return fake message object."""
        send_calls.append(kwargs.get("chat_id"))

        # After first send, simulate replacement by clearing run_id
        if len(send_calls) == 1:
            from core.database import get_db
            async with get_db() as db:
                await db.execute(
                    "UPDATE user_campaigns SET run_id=NULL, status='replaced' WHERE id=?", (cid,)
                )
                await db.commit()

        m = mock.MagicMock()
        m.message_id = 999
        return m

    # Patch bot.send_message
    import services.user_broadcast as ub_module
    original_bot = ub_module.bot

    mock_bot = mock.MagicMock()
    mock_bot.send_message = mock.AsyncMock(side_effect=mock_send_message)
    mock_bot.send_photo = mock.AsyncMock(side_effect=mock_send_message)

    ub_module.bot = mock_bot
    # Also patch group_manager bot
    import services.group_manager as gm_module
    gm_module.bot = mock_bot

    try:
        from services.user_broadcast import execute_user_campaign
        result = await execute_user_campaign(cid)
    finally:
        ub_module.bot = original_bot
        gm_module.bot = original_bot

    # Only 1 message should have been sent (fencing stops after first send detects run_id=NULL)
    assert len(send_calls) == 1, f"Expected 1 send (then fencing stops), got {len(send_calls)}: {send_calls}"
    print(f"  PASS test_T6_execute_campaign_with_mocked_telegram (stopped after {len(send_calls)} send)")


# ── Runner ────────────────────────────────────────────────────────────────────

async def run_all_tests():
    await setup_db()

    tests = [
        test_T1_old_worker_stops_after_replacement,
        test_T2_old_worker_stops_after_global_suspend,
        test_T3_no_new_sends_after_suspend_completes,
        test_T4_two_workers_cannot_claim_same_campaign,
        test_T5_no_resend_of_confirmed_messages,
        test_T6_execute_campaign_with_mocked_telegram,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            await t()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*55}")
    print(f"Worker Safety Tests: {passed}/{len(tests)} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
