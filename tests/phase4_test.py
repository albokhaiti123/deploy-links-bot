#!/usr/bin/env python3
"""
Cumulative Test Suite — Phase 4 (tests/phase4_test.py)
Includes:
  - Suite A: 12 foundational user campaign tests
  - Suite B: 6 worker safety tests
  - Suite C: 7 Phase 1 repair verification tests
  - Suite D: 7 Phase 2 repair verification tests
  - Suite E: 8 Phase 3 repair verification tests
  - Suite F: 8 Phase 4 verification tests (Owner Invite Links & User Permanent Referral Link)
Total: 48 cumulative tests.
"""

import asyncio
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

from tests.phase3_test import (
    setup_db,
    # Suite A (12)
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
    # Suite B (6)
    test_T1_old_worker_stops_after_replacement,
    test_T2_old_worker_stops_after_global_suspend,
    test_T3_no_new_sends_after_suspend_completes,
    test_T4_two_workers_cannot_claim_same_campaign,
    test_T5_no_resend_of_confirmed_messages,
    test_T6_execute_campaign_with_mocked_telegram,
    # Suite C: Phase 1 (7)
    test_P1_01_verify_campaign_groups_unpacking_iss01,
    test_P1_02_recurring_campaign_schedule_comparison_iss02,
    test_P1_03_legacy_groups_reward_owner_backfill_iss03,
    test_P1_04_resume_suspended_admin_campaign_iss04,
    test_P1_05_sqlite_pragmas_and_indexes_iss06,
    test_P1_06_fk_safety_for_unregistered_user_iss06,
    test_P1_07_recover_stale_claims_force_and_ttl_iss11,
    # Suite D: Phase 2 (7)
    test_P2_01_welcome_media_callbacks_and_user_dashboard_iss05,
    test_P2_02_html_escaping_in_groups_campaigns_and_buttons_iss07,
    test_P2_03_prevent_reusing_verified_groups_across_campaigns_iss08,
    test_P2_04_custom_buttons_included_in_campaign_broadcast_and_test_iss09,
    test_P2_05_user_campaign_no_duplicate_send_on_forbidden_or_rate_limit_iss10,
    test_P2_06_admin_broadcast_and_campaign_retry_after_handling_iss16,
    test_P2_07_preserve_html_text_and_paid_media_keyboard_iss17,
    # Suite E: Phase 3 (8)
    test_P3_01_fsm_non_text_input_guards_iss12,
    test_P3_02_recurring_broadcast_media_vip_wizard_iss13a,
    test_P3_03_broadcast_forbidden_does_not_deactivate_users_iss13b,
    test_P3_04_prevent_empty_user_campaign_and_paused_execution_iss14,
    test_P3_05_user_campaign_auto_delete_scheduled_iss15,
    test_P3_06_campaign_stats_views_and_delivered_iss18b,
    test_P3_07_admin_owner_protection_and_quota_text_iss18ac,
    test_P3_08_parameterized_stats_and_cooldown_pruning_iss19,
)


# ── Phase 4 Specific Tests (Suite F) ─────────────────────────────────────────

async def test_P4_01_owner_create_permanent_invite_link():
    """Owner can create a permanent invite link and track unique joins and total clicks."""
    from models.invite_links import create_owner_invite_link, process_owner_invite_join

    lnk = await create_owner_invite_link(
        label="Permanent Main Ad",
        link_type="permanent",
        created_by=999999,
    )
    assert lnk["link_type"] == "permanent"
    assert lnk["expires_at"] is None
    assert lnk["effective_status"] == "active"

    # First join by user 640001
    ok1, reason1, updated1 = await process_owner_invite_join(lnk["code"], 640001)
    assert ok1 is True and reason1 == "active"
    assert updated1["clicks_count"] == 1
    assert updated1["joins_count"] == 1

    # Second click by same user 640001 -> clicks_count increments to 2, joins_count stays 1
    ok2, reason2, updated2 = await process_owner_invite_join(lnk["code"], 640001)
    assert ok2 is True and reason2 == "active"
    assert updated2["clicks_count"] == 2
    assert updated2["joins_count"] == 1
    print("  PASS test_P4_01_owner_create_permanent_invite_link")


async def test_P4_02_owner_create_temporary_invite_link_and_expiry():
    """Temporary owner invite link works while valid and automatically expires after expires_at."""
    from models.invite_links import create_owner_invite_link, process_owner_invite_join
    from core.database import get_db

    lnk = await create_owner_invite_link(
        label="24h Flash Invite",
        link_type="temporary",
        duration_hours=24,
        created_by=999999,
    )
    assert lnk["link_type"] == "temporary"
    assert lnk["expires_at"] is not None
    assert lnk["effective_status"] == "active"

    # Valid before expiration
    ok_before, reason_before, _ = await process_owner_invite_join(lnk["code"], 640002)
    assert ok_before is True and reason_before == "active"

    # Simulate expiration in the past
    past_str = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    async with get_db() as db:
        await db.execute(
            "UPDATE owner_invite_links SET expires_at = ? WHERE id = ?",
            (past_str, lnk["id"]),
        )
        await db.commit()

    ok_after, reason_after, expired_lnk = await process_owner_invite_join(lnk["code"], 640003)
    assert ok_after is False, "Expired temporary invite link must reject joins"
    assert reason_after == "expired"
    assert expired_lnk["effective_status"] == "expired"
    print("  PASS test_P4_02_owner_create_temporary_invite_link_and_expiry")


async def test_P4_03_owner_manual_pause_and_resume_invite_link():
    """Owner can manually pause an invite link and resume it at any time."""
    from models.invite_links import (
        create_owner_invite_link,
        set_owner_invite_status,
        process_owner_invite_join,
    )

    lnk = await create_owner_invite_link(label="Pausable Link", link_type="permanent", created_by=999999)

    # Pause manually
    await set_owner_invite_status(lnk["id"], "paused")
    ok_paused, reason_paused, _ = await process_owner_invite_join(lnk["code"], 640004)
    assert ok_paused is False and reason_paused == "paused"

    # Resume manually
    await set_owner_invite_status(lnk["id"], "active")
    ok_resumed, reason_resumed, updated = await process_owner_invite_join(lnk["code"], 640004)
    assert ok_resumed is True and reason_resumed == "active"
    assert updated["joins_count"] == 1
    print("  PASS test_P4_03_owner_manual_pause_and_resume_invite_link")


async def test_P4_04_owner_delete_invite_link():
    """Owner can permanently delete an invite link."""
    from models.invite_links import (
        create_owner_invite_link,
        delete_owner_invite_link,
        get_owner_invite_link,
        process_owner_invite_join,
    )

    lnk = await create_owner_invite_link(label="Deletable Link", link_type="permanent", created_by=999999)
    deleted = await delete_owner_invite_link(lnk["id"])
    assert deleted is True
    assert await get_owner_invite_link(lnk["id"]) is None

    ok, reason, _ = await process_owner_invite_join(lnk["code"], 640005)
    assert ok is False and reason == "not_found"
    print("  PASS test_P4_04_owner_delete_invite_link")


async def test_P4_05_user_referral_generated_on_first_click_and_permanent():
    """
    User has no referral link before first click.
    On first click of 'رابط الاحالة الخاص بي', link is generated in background and returned.
    On all subsequent clicks, the exact same permanent link is returned.
    """
    from models.invite_links import get_user_referral
    import handlers.admin.invite_links as inv_handler

    user_id = 640006
    # Before first click: no record exists
    assert await get_user_referral(user_id) is None

    fake_bot = mock.MagicMock()
    me_obj = mock.MagicMock()
    me_obj.username = "testbot"
    fake_bot.get_me = mock.AsyncMock(return_value=me_obj)

    cb1 = mock.MagicMock()
    cb1.from_user.id = user_id
    cb1.answer = mock.AsyncMock()
    cb1.message.photo = None
    cb1.message.video = None
    cb1.message.caption = None
    cb1.message.edit_text = mock.AsyncMock()
    cb1.message.answer = mock.AsyncMock()

    orig_bot = inv_handler.bot
    inv_handler.bot = fake_bot
    try:
        # 1st click: generates link in background and replies
        await inv_handler.cb_user_my_referral(cb1)
        first_reply_text = cb1.message.edit_text.call_args[0][0]
        ref_after_first = await get_user_referral(user_id)
        assert ref_after_first is not None, "Referral record must be created on first click"
        expected_url = f"https://t.me/testbot?start=ref_{ref_after_first['ref_code']}"
        assert expected_url in first_reply_text, f"Expected {expected_url} in reply, got: {first_reply_text}"

        # 2nd and 3rd clicks later: must return the exact same permanent ref_code and URL
        await inv_handler.cb_user_my_referral(cb1)
        second_reply_text = cb1.message.edit_text.call_args[0][0]
        ref_after_second = await get_user_referral(user_id)
        assert ref_after_second["ref_code"] == ref_after_first["ref_code"], (
            "User referral link must be permanent and never change across clicks!"
        )
        assert expected_url in second_reply_text
    finally:
        inv_handler.bot = orig_bot

    print("  PASS test_P4_05_user_referral_generated_on_first_click_and_permanent")


async def test_P4_06_user_referral_join_counting_and_deduplication():
    """User referral link counts unique referred users and blocks self-referral."""
    from models.invite_links import (
        get_or_create_user_referral,
        process_user_referral_join,
        get_user_referral,
    )

    referrer_id = 640007
    new_user_1 = 640008
    ref = await get_or_create_user_referral(referrer_id)
    code = ref["ref_code"]

    # Self-referral must be rejected
    ok_self, reason_self, _ = await process_user_referral_join(code, referrer_id)
    assert ok_self is False and reason_self == "self_referral"

    # First time new_user_1 joins via referral link -> counted
    ok_join, reason_join, owner_id = await process_user_referral_join(code, new_user_1)
    assert ok_join is True and reason_join == "counted" and owner_id == referrer_id

    # Duplicate join by new_user_1 -> not counted twice
    ok_dup, reason_dup, _ = await process_user_referral_join(code, new_user_1)
    assert ok_dup is False and reason_dup == "already_counted"

    updated_ref = await get_user_referral(referrer_id)
    assert updated_ref["referrals_count"] == 1, f"Expected referrals_count=1, got {updated_ref['referrals_count']}"
    print("  PASS test_P4_06_user_referral_join_counting_and_deduplication")


async def test_P4_07_start_message_contains_user_referral_button():
    """get_start_message_data includes '🔗 رابط الاحالة الخاص بي' (callback_data='user_my_referral')."""
    from handlers.start import get_start_message_data

    _, kb = await get_start_message_data("testbot")
    buttons = [
        (btn.text, btn.callback_data)
        for row in (kb.inline_keyboard if kb else [])
        for btn in row
        if getattr(btn, "callback_data", None)
    ]
    cb_map = {cb_data: text for text, cb_data in buttons}
    assert "user_my_referral" in cb_map, f"Expected user_my_referral in start keyboard, got {buttons}"
    assert "رابط الاحالة الخاص بي" in cb_map["user_my_referral"]
    print("  PASS test_P4_07_start_message_contains_user_referral_button")


async def test_P4_08_owner_invite_wizard_and_non_owner_restriction():
    """Non-owners cannot access owner invite management; owner can create link via wizard."""
    import handlers.admin.invite_links as inv_handler
    from models.invite_links import list_owner_invite_links

    # 1. Non-owner attempt must be rejected
    cb_non_owner = mock.MagicMock()
    cb_non_owner.from_user.id = 123456  # Not ADMIN_ID (999999)
    cb_non_owner.answer = mock.AsyncMock()
    await inv_handler.cb_admin_invite_links(cb_non_owner)
    assert cb_non_owner.answer.await_count == 1
    alert_text = cb_non_owner.answer.call_args[0][0]
    assert "لمالك البوت" in alert_text

    # 2. Owner creates a temporary link via wizard preset
    state_data = {}
    state = mock.MagicMock()
    state.clear = mock.AsyncMock(side_effect=lambda: state_data.clear())
    state.set_state = mock.AsyncMock()
    state.update_data = mock.AsyncMock(side_effect=lambda **kw: state_data.update(kw))
    state.get_data = mock.AsyncMock(side_effect=lambda: dict(state_data))

    msg_label = mock.MagicMock()
    msg_label.from_user.id = 999999
    msg_label.text = "Telegram Ad Campaign"
    msg_label.answer = mock.AsyncMock()
    await inv_handler.process_owner_inv_label(msg_label, state)
    assert state_data.get("inv_label") == "Telegram Ad Campaign"

    cb_temp = mock.MagicMock()
    cb_temp.from_user.id = 999999
    cb_temp.data = "owner_inv_type_temp"
    cb_temp.message.photo = None
    cb_temp.message.video = None
    cb_temp.message.caption = None
    cb_temp.message.edit_text = mock.AsyncMock()
    cb_temp.answer = mock.AsyncMock()
    await inv_handler.cb_owner_inv_type(cb_temp, state)

    fake_bot = mock.MagicMock()
    me_obj = mock.MagicMock()
    me_obj.username = "testbot"
    fake_bot.get_me = mock.AsyncMock(return_value=me_obj)

    cb_dur = mock.MagicMock()
    cb_dur.from_user.id = 999999
    cb_dur.data = "owner_inv_dur_6"
    cb_dur.message.photo = None
    cb_dur.message.video = None
    cb_dur.message.caption = None
    cb_dur.message.edit_text = mock.AsyncMock()
    cb_dur.answer = mock.AsyncMock()

    orig_bot = inv_handler.bot
    inv_handler.bot = fake_bot
    try:
        await inv_handler.cb_owner_inv_duration_preset(cb_dur, state)
    finally:
        inv_handler.bot = orig_bot

    links = await list_owner_invite_links()
    created = next((l for l in links if l["label"] == "Telegram Ad Campaign"), None)
    assert created is not None, "Temporary invite link should be created by wizard"
    assert created["link_type"] == "temporary"
    print("  PASS test_P4_08_owner_invite_wizard_and_non_owner_restriction")


async def run_phase4_suite() -> bool:
    print("=" * 65)
    print("Running Phase 4 Cumulative Test Suite (48 tests: Phases 1 + 2 + 3 + 4)")
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
        # Suite D: Phase 2 repair verification tests (7)
        test_P2_01_welcome_media_callbacks_and_user_dashboard_iss05,
        test_P2_02_html_escaping_in_groups_campaigns_and_buttons_iss07,
        test_P2_03_prevent_reusing_verified_groups_across_campaigns_iss08,
        test_P2_04_custom_buttons_included_in_campaign_broadcast_and_test_iss09,
        test_P2_05_user_campaign_no_duplicate_send_on_forbidden_or_rate_limit_iss10,
        test_P2_06_admin_broadcast_and_campaign_retry_after_handling_iss16,
        test_P2_07_preserve_html_text_and_paid_media_keyboard_iss17,
        # Suite E: Phase 3 repair verification tests (8)
        test_P3_01_fsm_non_text_input_guards_iss12,
        test_P3_02_recurring_broadcast_media_vip_wizard_iss13a,
        test_P3_03_broadcast_forbidden_does_not_deactivate_users_iss13b,
        test_P3_04_prevent_empty_user_campaign_and_paused_execution_iss14,
        test_P3_05_user_campaign_auto_delete_scheduled_iss15,
        test_P3_06_campaign_stats_views_and_delivered_iss18b,
        test_P3_07_admin_owner_protection_and_quota_text_iss18ac,
        test_P3_08_parameterized_stats_and_cooldown_pruning_iss19,
        # Suite F: Phase 4 invite & referral verification tests (8)
        test_P4_01_owner_create_permanent_invite_link,
        test_P4_02_owner_create_temporary_invite_link_and_expiry,
        test_P4_03_owner_manual_pause_and_resume_invite_link,
        test_P4_04_owner_delete_invite_link,
        test_P4_05_user_referral_generated_on_first_click_and_permanent,
        test_P4_06_user_referral_join_counting_and_deduplication,
        test_P4_07_start_message_contains_user_referral_button,
        test_P4_08_owner_invite_wizard_and_non_owner_restriction,
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
    print(f"Phase 4 Final Cumulative Results: {passed}/{len(all_tests)} passed, {failed} failed")
    print("=" * 65)
    return failed == 0


if __name__ == "__main__":
    ok = asyncio.run(run_phase4_suite())
    try:
        os.unlink(TEST_DB)
    except OSError:
        pass
    sys.exit(0 if ok else 1)
