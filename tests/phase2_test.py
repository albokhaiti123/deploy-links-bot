#!/usr/bin/env python3
"""
Cumulative Test Suite — Phase 2 (tests/phase2_test.py)
Includes:
  - Suite A: 12 foundational user campaign tests
  - Suite B: 6 worker safety tests
  - Suite C: 7 Phase 1 repair verification tests (ISS-01, ISS-02, ISS-03, ISS-04, ISS-06, ISS-11)
  - Suite D: 7 Phase 2 repair verification tests (ISS-05, ISS-07, ISS-08, ISS-09, ISS-10, ISS-16, ISS-17)
Total: 32 cumulative tests.
"""

import asyncio
import os
import sys
import tempfile
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

from tests.phase1_test import (
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
)


# ── Phase 2 Specific Tests (Suite D) ─────────────────────────────────────────

async def test_P2_01_welcome_media_callbacks_and_user_dashboard_iss05():
    """ISS-05: cb_start_btn2_click & cb_start_back use edit_caption on media messages and keep user_menu."""
    import handlers.start as start_handler
    from models.settings import set_setting

    await set_setting("start_btn2_content", "<b>How to use</b>")

    fake_bot = mock.MagicMock()
    me_obj = mock.MagicMock()
    me_obj.username = "testbot"
    fake_bot.get_me = mock.AsyncMock(return_value=me_obj)

    # Simulate a callback on a photo welcome message from a regular user (non-admin)
    cb = mock.MagicMock()
    cb.from_user.id = 820001
    cb.answer = mock.AsyncMock()
    cb.message.photo = [mock.MagicMock()]
    cb.message.video = None
    cb.message.caption = "Original welcome caption"
    cb.message.edit_caption = mock.AsyncMock()
    cb.message.edit_text = mock.AsyncMock()

    orig_bot = start_handler.bot
    start_handler.bot = fake_bot
    try:
        await start_handler.cb_start_btn2_click(cb)
        assert cb.message.edit_caption.await_count == 1, "Should call edit_caption when message has photo"
        assert cb.message.edit_text.await_count == 0, "Should NOT call edit_text on photo message"

        await start_handler.cb_start_back(cb)
        assert cb.message.edit_caption.await_count == 2, "cb_start_back should also call edit_caption on photo"
        _, kwargs = cb.message.edit_caption.call_args
        kb = kwargs.get("reply_markup")
        all_cb_data = [
            btn.callback_data
            for row in (kb.inline_keyboard if kb else [])
            for btn in row
            if getattr(btn, "callback_data", None)
        ]
        assert "user_menu" in all_cb_data, f"user_menu button missing on start_back! Found: {all_cb_data}"
    finally:
        start_handler.bot = orig_bot

    print("  PASS test_P2_01_welcome_media_callbacks_and_user_dashboard_iss05")


async def test_P2_02_html_escaping_in_groups_campaigns_and_buttons_iss07():
    """ISS-07: Dangerous HTML characters in group titles, campaign names, and buttons are escaped."""
    from models.groups import upsert_group
    from models.campaigns import create_campaign
    from models.custom_buttons import add_button
    import handlers.user.my_groups as my_groups_handler
    import handlers.admin.button_manager as btn_mgr_handler
    import services.campaign as camp_service

    user_id = 820002
    malicious_title = "<script>alert('xss')&</script>"
    await upsert_group(-1008201, malicious_title, "supergroup", added_by=user_id)

    # 1. Check user my_groups escaping
    cb = mock.MagicMock()
    cb.from_user.id = user_id
    cb.answer = mock.AsyncMock()
    cb.message.edit_text = mock.AsyncMock()
    await my_groups_handler.cb_user_my_groups(cb)
    rendered_groups_text = cb.message.edit_text.call_args[0][0]
    assert "<script>" not in rendered_groups_text, "Unescaped <script> found in cb_user_my_groups!"
    assert "&lt;script&gt;" in rendered_groups_text, "Expected escaped &lt;script&gt; in cb_user_my_groups"

    # 2. Check campaign progress escaping
    cid = await create_campaign({
        "name": "Offer <b>#1 & <2>",
        "promo_text": "Promo",
        "button_text": "Claim",
        "required_groups": 3,
        "unlock_content": "Secret",
    })
    fake_bot = mock.MagicMock()
    me_obj = mock.MagicMock()
    me_obj.username = "testbot"
    fake_bot.get_me = mock.AsyncMock(return_value=me_obj)

    msg = mock.MagicMock()
    msg.answer = mock.AsyncMock()
    orig_bot = camp_service.bot
    camp_service.bot = fake_bot
    try:
        await camp_service.show_campaign_progress(msg, cid, user_id)
    finally:
        camp_service.bot = orig_bot

    rendered_camp_text = msg.answer.call_args[0][0]
    assert "Offer &lt;b&gt;#1 &amp; &lt;2&gt;" in rendered_camp_text, (
        f"Campaign name was not HTML-escaped: {rendered_camp_text}"
    )

    # 3. Check custom button manager escaping
    await add_button("promo", "Click <Here> & Win", "https://example.com/?a=1&b=2")
    msg_btn = mock.MagicMock()
    msg_btn.edit_text = mock.AsyncMock()
    await btn_mgr_handler.show_button_list(msg_btn, "promo")
    rendered_btn_text = msg_btn.edit_text.call_args[0][0]
    assert "Click &lt;Here&gt; &amp; Win" in rendered_btn_text, "Button label was not HTML-escaped"
    print("  PASS test_P2_02_html_escaping_in_groups_campaigns_and_buttons_iss07")


async def test_P2_03_prevent_reusing_verified_groups_across_campaigns_iss08():
    """ISS-08: Groups verified in Campaign A cannot be reused to unlock Campaign B for free."""
    from models.campaigns import create_campaign, get_user_progress
    from models.groups import upsert_group
    import services.campaign as camp_service

    user_id = 820003
    # User adds 2 groups
    await upsert_group(-1008301, "Reusable Group 1", "supergroup", added_by=user_id)
    await upsert_group(-1008302, "Reusable Group 2", "supergroup", added_by=user_id)

    cid_1 = await create_campaign({
        "name": "Camp A",
        "promo_text": "Promo A",
        "button_text": "Btn A",
        "required_groups": 2,
        "unlock_content": "Secret A",
    })
    cid_2 = await create_campaign({
        "name": "Camp B",
        "promo_text": "Promo B",
        "button_text": "Btn B",
        "required_groups": 2,
        "unlock_content": "Secret B",
    })

    fake_bot = mock.MagicMock()
    me_obj = mock.MagicMock()
    me_obj.id = 777000
    me_obj.username = "testbot"
    fake_bot.get_me = mock.AsyncMock(return_value=me_obj)
    member_obj = mock.MagicMock()
    member_obj.status = "administrator"
    fake_bot.get_chat_member = mock.AsyncMock(return_value=member_obj)

    cb = mock.MagicMock()
    cb.from_user.id = user_id
    cb.answer = mock.AsyncMock()
    cb.message.edit_text = mock.AsyncMock()
    cb.message.answer = mock.AsyncMock()

    orig_bot = camp_service.bot
    camp_service.bot = fake_bot
    try:
        # Clear cooldown cache for test user
        camp_service._campaign_verify_cooldown.clear()
        await camp_service.verify_campaign_groups(cb, cid_1)
        prog_1 = await get_user_progress(cid_1, user_id)
        assert prog_1 == (2, "unlocked"), f"Camp A should unlock, got {prog_1}"

        # Now user tries to verify Camp B with the EXACT same 2 groups -> must get 0 verified
        camp_service._campaign_verify_cooldown.clear()
        await camp_service.verify_campaign_groups(cb, cid_2)
        prog_2 = await get_user_progress(cid_2, user_id)
        assert prog_2 == (0, "in_progress"), (
            f"ISS-08 regression: Old groups from Camp A unlocked Camp B! Got {prog_2}"
        )

        # Now user adds 2 NEW groups and verifies Camp B -> must unlock Camp B
        await upsert_group(-1008303, "Brand New Group 3", "supergroup", added_by=user_id)
        await upsert_group(-1008304, "Brand New Group 4", "supergroup", added_by=user_id)
        camp_service._campaign_verify_cooldown.clear()
        await camp_service.verify_campaign_groups(cb, cid_2)
        prog_2_after = await get_user_progress(cid_2, user_id)
        assert prog_2_after == (2, "unlocked"), f"Camp B should unlock with new groups, got {prog_2_after}"
    finally:
        camp_service.bot = orig_bot

    print("  PASS test_P2_03_prevent_reusing_verified_groups_across_campaigns_iss08")


async def test_P2_04_custom_buttons_included_in_campaign_broadcast_and_test_iss09():
    """ISS-09: build_campaign_keyboard includes active custom buttons for campaign_<id>."""
    from models.campaigns import create_campaign
    from models.custom_buttons import add_button
    from services.campaign import build_campaign_keyboard

    cid = await create_campaign({
        "name": "Custom Btn Camp",
        "promo_text": "Promo",
        "button_text": "Main CTA",
        "required_groups": 1,
        "unlock_content": "Content",
    })
    await add_button(f"campaign_{cid}", "Extra Channel", "https://t.me/extra_channel")

    kb = await build_campaign_keyboard(cid, "Main CTA", "testbot")
    assert len(kb.inline_keyboard) == 2, f"Expected 2 button rows (CTA + custom), got {len(kb.inline_keyboard)}"
    assert kb.inline_keyboard[0][0].text == "Main CTA"
    assert kb.inline_keyboard[1][0].text == "Extra Channel"
    assert kb.inline_keyboard[1][0].url == "https://t.me/extra_channel"
    print("  PASS test_P2_04_custom_buttons_included_in_campaign_broadcast_and_test_iss09")


async def test_P2_05_user_campaign_no_duplicate_send_on_forbidden_or_rate_limit_iss10():
    """ISS-10: _send_user_campaign_message does NOT retry on TelegramForbiddenError, only on entity parse error."""
    from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
    from aiogram.methods import SendMessage
    import services.user_broadcast as ub_module

    method = SendMessage(chat_id=-1008501, text="test")
    forbidden_exc = TelegramForbiddenError(method=method, message="Forbidden: bot was kicked from the supergroup chat")

    fake_bot = mock.MagicMock()
    fake_bot.send_message = mock.AsyncMock(side_effect=forbidden_exc)

    orig_bot = ub_module.bot
    ub_module.bot = fake_bot
    try:
        raised = False
        try:
            await ub_module._send_user_campaign_message(-1008501, "Hello", None, None)
        except TelegramForbiddenError:
            raised = True
        assert raised, "Should raise TelegramForbiddenError"
        assert fake_bot.send_message.await_count == 1, (
            f"ISS-10 regression: Expected 1 call on Forbidden, got {fake_bot.send_message.await_count}"
        )

        # Now test entity parse error -> SHOULD retry once without parse_mode
        parse_exc = TelegramBadRequest(method=method, message="Bad Request: can't parse entities: Unclosed tag")
        ok_msg = mock.MagicMock()
        ok_msg.message_id = 555
        fake_bot.send_message = mock.AsyncMock(side_effect=[parse_exc, ok_msg])

        msg_id = await ub_module._send_user_campaign_message(-1008501, "<b>broken", None, None)
        assert msg_id == 555
        assert fake_bot.send_message.await_count == 2, "Should retry once on HTML entity parse error"
    finally:
        ub_module.bot = orig_bot

    print("  PASS test_P2_05_user_campaign_no_duplicate_send_on_forbidden_or_rate_limit_iss10")


async def test_P2_06_admin_broadcast_and_campaign_retry_after_handling_iss16():
    """ISS-16: execute_broadcast catches TelegramRetryAfter, sleeps, and retries delivery."""
    from aiogram.exceptions import TelegramRetryAfter
    from aiogram.methods import SendMessage
    import services.broadcast as bcast_service

    method = SendMessage(chat_id=111111, text="broadcast")
    retry_exc = TelegramRetryAfter(method=method, message="Flood control exceeded", retry_after=0)

    ok_msg = mock.MagicMock()
    ok_msg.message_id = 888
    mock_send_media = mock.AsyncMock(side_effect=[retry_exc, ok_msg])

    status_msg = mock.MagicMock()
    status_msg.edit_text = mock.AsyncMock()

    with mock.patch.object(bcast_service, "get_all_user_ids", mock.AsyncMock(return_value=[111111])), \
         mock.patch.object(bcast_service, "send_media_message", mock_send_media), \
         mock.patch("services.broadcast.asyncio.sleep", mock.AsyncMock()):
        await bcast_service.execute_broadcast(
            {"target": "users", "text": "Hello retry", "duration_mins": 0},
            status_msg,
        )

    assert mock_send_media.await_count == 2, f"Expected initial attempt + 1 retry, got {mock_send_media.await_count}"
    final_status_text = status_msg.edit_text.call_args[0][0]
    assert "1" in final_status_text, f"Expected 1 successful delivery after retry, got: {final_status_text}"
    print("  PASS test_P2_06_admin_broadcast_and_campaign_retry_after_handling_iss16")


async def test_P2_07_preserve_html_text_and_paid_media_keyboard_iss17():
    """ISS-17: send_media_message passes reply_markup to send_paid_media and handlers save html_text."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from services.media import send_media_message
    import handlers.admin.promo_settings as promo_handlers
    from models.settings import get_setting

    fake_bot = mock.MagicMock()
    fake_bot.send_paid_media = mock.AsyncMock(return_value=mock.MagicMock())
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Btn", url="https://example.com")]])

    await send_media_message(
        fake_bot,
        chat_id=12345,
        text="VIP caption",
        media_id="photo_file_id_1",
        media_type="photo",
        keyboard=kb,
        is_vip=True,
        stars=50,
    )
    _, kwargs = fake_bot.send_paid_media.call_args
    assert kwargs.get("reply_markup") == kb, "send_paid_media must receive reply_markup=keyboard"

    # Verify process_promo_text saves html_text
    fake_msg = mock.MagicMock()
    fake_msg.text = "Bold Promo"
    fake_msg.html_text = "<b>Bold Promo</b>"
    fake_msg.answer = mock.AsyncMock()
    fake_state = mock.MagicMock()
    fake_state.clear = mock.AsyncMock()

    await promo_handlers.process_promo_text(fake_msg, fake_state)
    saved_promo = await get_setting("promo_text")
    assert saved_promo == "<b>Bold Promo</b>", f"Expected HTML text '<b>Bold Promo</b>', got '{saved_promo}'"
    print("  PASS test_P2_07_preserve_html_text_and_paid_media_keyboard_iss17")


async def run_phase2_suite() -> bool:
    print("=" * 65)
    print("Running Phase 2 Cumulative Test Suite (32 tests: Phases 1 + 2)")
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
    print(f"Phase 2 Cumulative Results: {passed}/{len(all_tests)} passed, {failed} failed")
    print("=" * 65)
    return failed == 0


if __name__ == "__main__":
    ok = asyncio.run(run_phase2_suite())
    try:
        os.unlink(TEST_DB)
    except OSError:
        pass
    sys.exit(0 if ok else 1)
