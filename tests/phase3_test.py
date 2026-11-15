#!/usr/bin/env python3
"""
Cumulative Test Suite — Phase 3 (tests/phase3_test.py)
Includes:
  - Suite A: 12 foundational user campaign tests
  - Suite B: 6 worker safety tests
  - Suite C: 7 Phase 1 repair verification tests (ISS-01, ISS-02, ISS-03, ISS-04, ISS-06, ISS-11)
  - Suite D: 7 Phase 2 repair verification tests (ISS-05, ISS-07, ISS-08, ISS-09, ISS-10, ISS-16, ISS-17)
  - Suite E: 8 Phase 3 repair verification tests (ISS-12, ISS-13, ISS-14, ISS-15, ISS-18, ISS-19)
Total: 40 cumulative tests.
"""

import asyncio
import os
import sys
import tempfile
import time
import unittest.mock as mock

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

from tests.phase2_test import (
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
)


# ── Phase 3 Specific Tests (Suite E) ─────────────────────────────────────────

async def test_P3_01_fsm_non_text_input_guards_iss12():
    """ISS-12: Sending a sticker/photo (message.text=None) in text FSM steps does not raise AttributeError."""
    import handlers.admin.promo_settings as promo_h
    import handlers.admin.general_settings as gen_h
    import handlers.admin.button_manager as btn_h
    import handlers.admin.campaigns as camp_h
    import handlers.user.my_campaign as ucamp_h

    non_text_msg = mock.MagicMock()
    non_text_msg.text = None
    non_text_msg.html_text = None
    non_text_msg.answer = mock.AsyncMock()
    state = mock.MagicMock()
    state.clear = mock.AsyncMock()

    handlers_to_check = [
        promo_h.process_promo_stars,
        promo_h.process_promo_url,
        promo_h.process_promo_text,
        gen_h.process_cooldown,
        gen_h.process_test_group,
        btn_h.process_btn_label,
        btn_h.process_btn_url,
        camp_h.process_cw_required_groups,
        ucamp_h.process_ucw_text,
        ucamp_h.process_ucw_groups,
        ucamp_h.process_ucw_mode,
    ]

    for fn in handlers_to_check:
        await fn(non_text_msg, state)

    assert non_text_msg.answer.await_count == len(handlers_to_check), (
        f"Expected {len(handlers_to_check)} friendly error replies, got {non_text_msg.answer.await_count}"
    )
    print("  PASS test_P3_01_fsm_non_text_input_guards_iss12")


async def test_P3_02_recurring_broadcast_media_vip_wizard_iss13a():
    """ISS-13a: Recurring broadcast creation wizard supports photo/video media and VIP stars."""
    import handlers.admin.recurring as rec_h
    from models.broadcasts import list_recurring_broadcasts, get_recurring_broadcast

    state_data = {"rbw_target": "groups"}
    state = mock.MagicMock()
    state.set_state = mock.AsyncMock()
    state.clear = mock.AsyncMock()

    async def update_data(**kwargs):
        state_data.update(kwargs)

    async def get_data():
        return dict(state_data)

    state.update_data = mock.AsyncMock(side_effect=update_data)
    state.get_data = mock.AsyncMock(side_effect=get_data)

    # Step 1: Text
    msg_text = mock.MagicMock()
    msg_text.text = "Recurring VIP Offer"
    msg_text.html_text = "<b>Recurring VIP Offer</b>"
    msg_text.answer = mock.AsyncMock()
    await rec_h.process_rbw_text(msg_text, state)

    # Step 2: Photo media
    msg_photo = mock.MagicMock()
    msg_photo.text = None
    photo_obj = mock.MagicMock()
    photo_obj.file_id = "vip_photo_file_id_99"
    msg_photo.photo = [photo_obj]
    msg_photo.video = None
    msg_photo.answer = mock.AsyncMock()
    await rec_h.process_rbw_media(msg_photo, state)

    # Step 3: Select VIP paid
    cb_vip = mock.MagicMock()
    cb_vip.from_user.id = 999999  # ADMIN_ID
    cb_vip.data = "rbw_vip_paid"
    cb_vip.message.answer = mock.AsyncMock()
    cb_vip.answer = mock.AsyncMock()
    await rec_h.cb_rbw_vip(cb_vip, state)

    # Step 4: Enter stars
    msg_stars = mock.MagicMock()
    msg_stars.text = "75"
    msg_stars.answer = mock.AsyncMock()
    await rec_h.process_rbw_stars(msg_stars, state)

    # Step 5: Select hours
    cb_hours = mock.MagicMock()
    cb_hours.from_user.id = 999999
    cb_hours.data = "rbw_hours_12"
    cb_hours.message.answer = mock.AsyncMock()
    cb_hours.answer = mock.AsyncMock()
    await rec_h.cb_rbw_hours(cb_hours, state)

    rows = await list_recurring_broadcasts()
    assert rows, "Recurring broadcast should be created"
    latest_id = rows[0][0]
    rb = await get_recurring_broadcast(latest_id)
    assert rb["media_id"] == "vip_photo_file_id_99"
    assert rb["media_type"] == "photo"
    assert bool(rb["is_vip"]) is True
    assert rb["stars"] == 75
    assert rb["repeat_hours"] == 12
    print("  PASS test_P3_02_recurring_broadcast_media_vip_wizard_iss13a")


async def test_P3_03_broadcast_forbidden_does_not_deactivate_users_iss13b():
    """ISS-13b: TelegramForbiddenError during 'all' broadcast only deactivates groups, not user IDs."""
    from aiogram.exceptions import TelegramForbiddenError
    from aiogram.methods import SendMessage
    import services.broadcast as bcast_srv

    method = SendMessage(chat_id=1, text="test")
    forbid_exc = TelegramForbiddenError(method=method, message="Forbidden: bot was blocked by the user")

    deactivated = []

    async def fake_deactivate(cid):
        deactivated.append(cid)

    with mock.patch.object(bcast_srv, "get_all_user_ids", mock.AsyncMock(return_value=[500001])), \
         mock.patch.object(bcast_srv, "get_active_group_ids", mock.AsyncMock(return_value=[-1005001])), \
         mock.patch.object(bcast_srv, "send_media_message", mock.AsyncMock(side_effect=forbid_exc)), \
         mock.patch.object(bcast_srv, "deactivate_group", side_effect=fake_deactivate), \
         mock.patch("models.broadcasts.update_recurring_broadcast_time", mock.AsyncMock()), \
         mock.patch("services.broadcast.asyncio.sleep", mock.AsyncMock()):
        await bcast_srv.execute_recurring_broadcast_cycle(
            rb_id=1, target="all", text="Hello", media_id=None, media_type=None, is_vip=False, stars=0
        )

    assert 500001 not in deactivated, "User ID 500001 must NOT be passed to deactivate_group!"
    assert -1005001 in deactivated, "Group ID -1005001 SHOULD be deactivated on Forbidden"
    print("  PASS test_P3_03_broadcast_forbidden_does_not_deactivate_users_iss13b")


async def test_P3_04_prevent_empty_user_campaign_and_paused_execution_iss14():
    """ISS-14: User cannot skip both text and photo in wizard, and paused campaign cannot be executed."""
    import handlers.user.my_campaign as ucamp_h
    from services.user_broadcast import create_user_campaign, execute_user_campaign
    from models.user_campaigns import update_campaign_status
    from models.groups import upsert_group
    from models.settings import set_setting

    # 1. Skipping photo when text is already None must be rejected in wizard
    state = mock.MagicMock()
    state.get_data = mock.AsyncMock(return_value={"text": None})
    state.update_data = mock.AsyncMock()
    msg_skip = mock.MagicMock()
    msg_skip.text = "/skip"
    msg_skip.answer = mock.AsyncMock()

    await ucamp_h.process_ucw_photo_text(msg_skip, state)
    assert state.update_data.await_count == 0, "Should NOT advance wizard when both text and photo are skipped"
    reply_text = msg_skip.answer.call_args[0][0]
    assert "cannot skip photo" in reply_text.lower()

    # 2. Paused campaign must not execute in execute_user_campaign
    user_id = 730004
    chat_id = -1007304
    await set_setting("user_campaigns_enabled", "true")
    await upsert_group(chat_id, "Pause Guard Group", "supergroup", added_by=user_id)

    cid, err = await create_user_campaign(
        user_id=user_id,
        text="Paused test",
        photo_file_id=None,
        buttons_json=None,
        target_chat_ids=[chat_id],
        mode="immediate",
        repeat_hours=0,
    )
    assert cid is not None, f"Failed to create campaign: {err}"
    await update_campaign_status(cid, "paused")

    res = await execute_user_campaign(cid)
    assert res.get("sent") == 0 and "paused" in res.get("error", "").lower(), (
        f"Paused campaign should abort execution, got: {res}"
    )
    print("  PASS test_P3_04_prevent_empty_user_campaign_and_paused_execution_iss14")


async def test_P3_05_user_campaign_auto_delete_scheduled_iss15():
    """ISS-15: User campaign with auto_delete_seconds > 0 schedules message deletion."""
    from services.user_broadcast import create_user_campaign, execute_user_campaign
    from models.groups import upsert_group
    from models.settings import set_setting
    from core.database import get_db
    import services.user_broadcast as ub_module

    user_id = 730005
    chat_id = -1007305
    await set_setting("user_campaigns_enabled", "true")
    await upsert_group(chat_id, "AutoDelete Group", "supergroup", added_by=user_id)

    cid, err = await create_user_campaign(
        user_id=user_id,
        text="Self destruct message",
        photo_file_id=None,
        buttons_json=None,
        target_chat_ids=[chat_id],
        mode="immediate",
        repeat_hours=0,
        auto_delete_seconds=120,
    )
    assert cid is not None, f"Creation failed: {err}"

    fake_bot = mock.MagicMock()
    sent_obj = mock.MagicMock()
    sent_obj.message_id = 987654
    fake_bot.send_message = mock.AsyncMock(return_value=sent_obj)

    orig_bot = ub_module.bot
    ub_module.bot = fake_bot
    try:
        stats = await execute_user_campaign(cid)
    finally:
        ub_module.bot = orig_bot

    assert stats.get("sent") == 1
    async with get_db() as db:
        async with db.execute(
            "SELECT chat_id, message_id FROM broadcast_messages WHERE chat_id=? AND message_id=?",
            (chat_id, 987654),
        ) as c:
            row = await c.fetchone()
    assert row is not None, "Message should be scheduled in broadcast_messages for auto-deletion"
    print("  PASS test_P3_05_user_campaign_auto_delete_scheduled_iss15")


async def test_P3_06_campaign_stats_views_and_delivered_iss18b():
    """ISS-18b: get_campaign_stats returns views and delivered counts logged in events."""
    from models.campaigns import create_campaign, get_campaign_stats
    from models.events import log_event

    cid = await create_campaign({
        "name": "Stats Test Campaign",
        "promo_text": "Promo",
        "button_text": "CTA",
        "required_groups": 1,
        "unlock_content": "Reward",
    })
    await log_event(0, 730006, f"campaign_{cid}_viewed")
    await log_event(0, 730007, f"campaign_{cid}_viewed")
    await log_event(0, 730006, f"campaign_{cid}_content_delivered")

    stats = await get_campaign_stats(cid)
    assert stats.get("views") == 2, f"Expected 2 views, got {stats.get('views')}"
    assert stats.get("delivered") == 1, f"Expected 1 delivered, got {stats.get('delivered')}"
    print("  PASS test_P3_06_campaign_stats_views_and_delivered_iss18b")


async def test_P3_07_admin_owner_protection_and_quota_text_iss18ac():
    """ISS-18a/c: Owner ADMIN_ID cannot be modified in process_admin_id, and quota alert says 5."""
    import handlers.admin.admins as admins_h
    import handlers.user.my_campaign as ucamp_h
    from models.admins import list_admins

    msg = mock.MagicMock()
    msg.text = "999999"  # ADMIN_ID
    msg.answer = mock.AsyncMock()
    state = mock.MagicMock()
    state.get_data = mock.AsyncMock(return_value={"admin_action": "remove"})
    state.clear = mock.AsyncMock()

    await admins_h.process_admin_id(msg, state)
    reply = msg.answer.call_args[0][0]
    assert "المالك الرئيسي" in reply, f"Expected owner protection message, got: {reply}"

    cb = mock.MagicMock()
    cb.answer = mock.AsyncMock()
    await ucamp_h.cb_user_quota_info(cb)
    quota_msg = cb.answer.call_args[0][0]
    assert "5" in quota_msg, f"Expected '5' in daily quota alert, got: {quota_msg}"
    print("  PASS test_P3_07_admin_owner_protection_and_quota_text_iss18ac")


async def test_P3_08_parameterized_stats_and_cooldown_pruning_iss19():
    """ISS-19: get_users_since & count_events_since count recent local-time records and caches prune."""
    from models.users import upsert_user, get_users_since
    from models.events import log_event, count_events_since
    import services.promo as promo_srv

    await upsert_user(730008, "recent_user", "Recent")
    await log_event(-1007308, 730008, "promo_sent")

    users_24h = await get_users_since("datetime('now', '-1 day')")
    promos_24h = await count_events_since("promo_sent", "datetime('now', '-1 day')")
    assert users_24h >= 1, f"Expected at least 1 user in last 24h, got {users_24h}"
    assert promos_24h >= 1, f"Expected at least 1 promo_sent event in last 24h, got {promos_24h}"

    # Verify cooldown cache pruning when > 500 entries exist
    old_ts = time.time() - 7200
    for i in range(510):
        promo_srv._last_promo_times[-900000 - i] = old_ts
    assert len(promo_srv._last_promo_times) >= 510

    # Trigger promo check with a mocked message/user
    fake_bot = mock.MagicMock()
    me_obj = mock.MagicMock()
    me_obj.username = "testbot"
    fake_bot.get_me = mock.AsyncMock(return_value=me_obj)

    fake_msg = mock.MagicMock()
    fake_msg.chat.id = -1007308
    fake_user = mock.MagicMock()
    fake_user.id = 730008
    fake_user.first_name = "Tester"

    orig_bot = promo_srv.bot
    promo_srv.bot = fake_bot
    try:
        with mock.patch.object(promo_srv, "send_media_message", mock.AsyncMock(return_value=None)):
            await promo_srv.trigger_group_promo(fake_msg, fake_user)
    finally:
        promo_srv.bot = orig_bot

    assert len(promo_srv._last_promo_times) < 50, (
        f"Expected expired entries in _last_promo_times to be pruned, size={len(promo_srv._last_promo_times)}"
    )
    print("  PASS test_P3_08_parameterized_stats_and_cooldown_pruning_iss19")


async def run_phase3_suite() -> bool:
    print("=" * 65)
    print("Running Phase 3 Cumulative Test Suite (40 tests: Phases 1 + 2 + 3)")
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
    print(f"Phase 3 Final Cumulative Results: {passed}/{len(all_tests)} passed, {failed} failed")
    print("=" * 65)
    return failed == 0


if __name__ == "__main__":
    ok = asyncio.run(run_phase3_suite())
    try:
        os.unlink(TEST_DB)
    except OSError:
        pass
    sys.exit(0 if ok else 1)
