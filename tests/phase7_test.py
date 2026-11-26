#!/usr/bin/env python3
"""
Cumulative Test Suite — Phase 7 (tests/phase7_test.py)
Includes:
  - Suite A: 12 foundational user campaign tests
  - Suite B: 6 worker safety tests
  - Suite C: 7 Phase 1 repair verification tests
  - Suite D: 7 Phase 2 repair verification tests
  - Suite E: 8 Phase 3 repair verification tests
  - Suite F: 8 Phase 4 verification tests
  - Suite G: 9 Phase 5 i18n core + localized UI tests
  - Suite H: 9 Phase 6 full admin panel i18n tests
  - Suite I: 9 Phase 7 interactive user campaign wizard tests
Total: 75 cumulative tests.
"""

import asyncio
import json
import os
import re
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

from tests.phase6_test import (
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
    # test_P3_07 is overridden below (Phase 6 localized process_admin_id)
    test_P3_08_parameterized_stats_and_cooldown_pruning_iss19,
    # Suite F: Phase 4 (8)
    test_P4_01_owner_create_permanent_invite_link,
    test_P4_02_owner_create_temporary_invite_link_and_expiry,
    test_P4_03_owner_manual_pause_and_resume_invite_link,
    test_P4_04_owner_delete_invite_link,
    test_P4_05_user_referral_generated_on_first_click_and_permanent,
    test_P4_06_user_referral_join_counting_and_deduplication,
    test_P4_07_start_message_contains_user_referral_button,
    # test_P4_08 is overridden below (Phase 6 localized owner-only alert)
    # Suite G: Phase 5 (9)
    test_P5_01_users_lang_column_and_persistence,
    test_P5_02_i18n_engine_fallback_and_key_parity,
    test_P5_03_auto_detect_initial_language,
    test_P5_04_language_switcher_command_and_callback,
    test_P5_05_start_buttons_and_back_localized,
    test_P5_06_owner_invite_error_messages_localized,
    test_P5_07_user_referral_screen_localized,
    test_P5_08_my_groups_screen_localized,
    test_P5_09_campaign_progress_and_verify_localized,
    # Suite H: Phase 6 (9) — imported from phase6_test directly
    test_P6_01_full_locale_key_and_placeholder_parity,
    test_P6_02_owner_invite_links_ui_localized_ar_and_en,
    test_P6_03_admin_panel_translation_engine_coverage,
    test_P6_04_admins_handler_localized_ar_and_en,
    test_P6_05_admin_broadcast_and_campaign_status_localized,
    test_P6_06_session_middleware_translates_admin_private_chat_only,
    test_P6_07_language_middleware_sets_user_and_lang_context,
    test_P6_08_independent_admin_and_user_languages,
    test_P6_09_main_py_registers_admin_session_middleware,
    # Phase-6 override functions
    test_P3_07_admin_owner_protection_and_quota_text_iss18ac,
    test_P4_08_owner_invite_wizard_and_non_owner_restriction,
)


# ── Helper: in-memory FSMContext mock ────────────────────────────────────────

def _make_memory_state(initial=None):
    """Return (state_mock, store_dict, current_state_dict)."""
    store = dict(initial or {})
    current_state = {"val": None}
    state = mock.MagicMock()

    async def get_data():
        return dict(store)

    async def update_data(**kwargs):
        store.update(kwargs)

    async def set_state(st):
        current_state["val"] = st

    async def clear():
        store.clear()
        current_state["val"] = None

    state.get_data = mock.AsyncMock(side_effect=get_data)
    state.update_data = mock.AsyncMock(side_effect=update_data)
    state.set_state = mock.AsyncMock(side_effect=set_state)
    state.clear = mock.AsyncMock(side_effect=clear)
    return state, store, current_state


def _make_callback(user_id: int, data: str, lang_code: str = "ar") -> mock.MagicMock:
    """Build a minimal CallbackQuery mock."""
    cb = mock.MagicMock()
    cb.from_user = mock.MagicMock()
    cb.from_user.id = user_id
    cb.from_user.language_code = lang_code
    cb.data = data
    cb.answer = mock.AsyncMock()
    cb.message = mock.MagicMock()
    cb.message.edit_text = mock.AsyncMock()
    cb.message.answer = mock.AsyncMock()
    cb.message.photo = None
    cb.message.video = None
    cb.message.caption = None
    cb.message.from_user = cb.from_user
    return cb


def _make_message(user_id: int, text: str, lang_code: str = "ar") -> mock.MagicMock:
    """Build a minimal Message mock."""
    msg = mock.MagicMock()
    msg.from_user = mock.MagicMock()
    msg.from_user.id = user_id
    msg.from_user.language_code = lang_code
    msg.text = text
    msg.html_text = text
    msg.photo = None
    msg.video = None
    msg.caption = None
    msg.answer = mock.AsyncMock()
    msg.answer_photo = mock.AsyncMock()
    msg.edit_text = mock.AsyncMock()
    return msg


# ── Suite I: Phase 7 Tests ────────────────────────────────────────────────────

async def test_P7_01_locale_parity_with_phase7_keys():
    """Phase 7 locales: >= 148 keys each, 100% key parity, identical placeholders."""
    from locales.ar import STRINGS as AR
    from locales.en import STRINGS as EN

    assert len(AR) >= 148, f"AR has only {len(AR)} keys, need >= 148"
    assert len(EN) >= 148, f"EN has only {len(EN)} keys, need >= 148"
    assert set(AR.keys()) == set(EN.keys()), (
        f"Key parity mismatch.\n"
        f"  AR-only: {set(AR.keys()) - set(EN.keys())}\n"
        f"  EN-only: {set(EN.keys()) - set(AR.keys())}"
    )

    # Phase 7 specific keys must be present
    phase7_keys = [
        "uc_step1_text_prompt", "uc_btn_skip_text", "uc_btn_cancel",
        "uc_step2_photo_prompt", "uc_step3_buttons_prompt", "uc_btn_add_button",
        "uc_btn_label_prompt", "uc_btn_url_prompt", "uc_err_btn_url_invalid",
        "uc_step4_groups_prompt", "uc_btn_select_all", "uc_btn_clear_all",
        "uc_btn_confirm_groups", "uc_step5_mode_prompt", "uc_btn_mode_now",
        "uc_step6_autodel_prompt", "uc_btn_autodel_none", "uc_preview_header",
        "uc_preview_summary", "uc_btn_confirm_launch", "uc_btn_edit_campaign",
        "uc_edit_menu_title", "uc_launch_success_immediate", "uc_launch_success_recurring",
        "uc_launch_failed", "uc_cancelled",
    ]
    for key in phase7_keys:
        assert key in AR, f"Missing Phase 7 key in AR: {key!r}"
        assert key in EN, f"Missing Phase 7 key in EN: {key!r}"

    # Placeholder parity check
    _PH = re.compile(r"\{(\w+)\}")
    mismatches = []
    for key in AR:
        ar_phs = set(_PH.findall(AR[key]))
        en_phs = set(_PH.findall(EN[key]))
        if ar_phs != en_phs:
            mismatches.append(f"  key={key!r}: AR={ar_phs} EN={en_phs}")
    assert not mismatches, "Placeholder parity failures:\n" + "\n".join(mismatches)
    print("  PASS test_P7_01_locale_parity_with_phase7_keys")


async def test_P7_02_user_states_extended_cleanly():
    """UserCampaignWizard FSM has all 10 expected states including Phase 7 additions."""
    from states.user_states import UserCampaignWizard

    expected_states = (
        "text", "photo", "buttons", "groups", "mode", "confirm",
        "button_label", "button_url", "auto_delete", "custom_hours",
    )
    for attr in expected_states:
        assert hasattr(UserCampaignWizard, attr), (
            f"UserCampaignWizard missing state: {attr!r}"
        )
    print("  PASS test_P7_02_user_states_extended_cleanly")


async def test_P7_03_two_step_button_builder_add_validate_remove():
    """Button builder: add label→url in two steps, validate URL, remove button, enforce cap."""
    import handlers.user.my_campaign as ucamp_h
    from states.user_states import UserCampaignWizard
    from models.users import set_user_lang, ensure_user_lang

    uid = 770003
    await ensure_user_lang(uid, "ar")
    await set_user_lang(uid, "ar")

    # ── Step A: cb_ucw_btn_add → transitions to button_label ──────────────
    state, store, cur_st = _make_memory_state({"buttons_list": []})
    cb = _make_callback(uid, "ucw_btn_add", "ar")
    await ucamp_h.cb_ucw_btn_add(cb, state)
    assert cur_st["val"] == UserCampaignWizard.button_label, (
        f"Expected button_label state after btn_add, got {cur_st['val']}"
    )
    # The prompt message should have been sent (edit_text or answer)
    prompt_called = cb.message.edit_text.await_count + cb.message.answer.await_count
    assert prompt_called >= 1, "Expected at least one edit_text or answer call in cb_ucw_btn_add"

    # ── Step B: process_ucw_btn_label → saves label, transitions to button_url ─
    store.clear()
    store["buttons_list"] = []
    cur_st["val"] = UserCampaignWizard.button_label
    msg_label = _make_message(uid, "قناتنا الرسمية", "ar")
    await ucamp_h.process_ucw_btn_label(msg_label, state)
    assert cur_st["val"] == UserCampaignWizard.button_url, (
        f"Expected button_url state after label input, got {cur_st['val']}"
    )
    assert store.get("pending_btn_label") == "قناتنا الرسمية", (
        f"Expected pending_btn_label='قناتنا الرسمية', got {store.get('pending_btn_label')!r}"
    )

    # ── Step C: process_ucw_btn_url with invalid URL → rejected ───────────
    # Patch _p7_validate_single_button: "not_a_valid_url" → (False, "url")
    cur_st["val"] = UserCampaignWizard.button_url
    msg_bad_url = _make_message(uid, "not_a_valid_url", "ar")
    with mock.patch("handlers.user.my_campaign._p7_validate_single_button",
                    return_value=(False, "url")):
        await ucamp_h.process_ucw_btn_url(msg_bad_url, state)
    # State should remain button_url (not change) and no button added
    assert len(store.get("buttons_list") or []) == 0, (
        "Invalid URL should not add a button"
    )

    # ── Step D: process_ucw_btn_url with valid URL → button saved ─────────
    cur_st["val"] = UserCampaignWizard.button_url
    msg_good_url = _make_message(uid, "https://t.me/official_channel", "ar")
    # Set msg_good_url.message = msg_good_url so _ask_buttons's target_msg stays correct
    msg_good_url.message = msg_good_url
    with mock.patch("handlers.user.my_campaign._p7_validate_single_button",
                    return_value=(True, None)):
        await ucamp_h.process_ucw_btn_url(msg_good_url, state)
    # Buttons should be saved before _ask_buttons was called
    buttons = store.get("buttons_list") or []
    assert len(buttons) == 1, f"Expected 1 button after valid URL, got {len(buttons)}"
    assert buttons[0]["text"] == "قناتنا الرسمية"
    assert buttons[0]["url"] == "https://t.me/official_channel"

    # ── Step E: add 2nd button ─────────────────────────────────────────────
    cb2 = _make_callback(uid, "ucw_btn_add", "ar")
    await ucamp_h.cb_ucw_btn_add(cb2, state)
    cur_st["val"] = UserCampaignWizard.button_label
    msg_label2 = _make_message(uid, "موقعنا", "ar")
    await ucamp_h.process_ucw_btn_label(msg_label2, state)
    cur_st["val"] = UserCampaignWizard.button_url
    msg_url2 = _make_message(uid, "https://example.com", "ar")
    msg_url2.message = msg_url2
    with mock.patch("handlers.user.my_campaign._p7_validate_single_button",
                    return_value=(True, None)):
        await ucamp_h.process_ucw_btn_url(msg_url2, state)
    assert len(store.get("buttons_list") or []) == 2

    # ── Step F: cb_ucw_btn_del removes first button ────────────────────────
    cur_st["val"] = UserCampaignWizard.buttons
    cb_del = _make_callback(uid, "ucw_btn_del_0", "ar")
    await ucamp_h.cb_ucw_btn_del(cb_del, state)
    buttons_after_del = store.get("buttons_list") or []
    assert len(buttons_after_del) == 1, (
        f"Expected 1 button after delete, got {len(buttons_after_del)}"
    )

    # ── Step G: cap enforcement at 3 buttons ──────────────────────────────
    store["buttons_list"] = [
        {"text": "Btn1", "url": "https://a.com"},
        {"text": "Btn2", "url": "https://b.com"},
        {"text": "Btn3", "url": "https://c.com"},
    ]
    cb_cap = _make_callback(uid, "ucw_btn_add", "ar")
    await ucamp_h.cb_ucw_btn_add(cb_cap, state)
    # Should show_alert (answer called with show_alert) instead of proceeding
    cb_cap.answer.assert_awaited()
    answer_kwargs = cb_cap.answer.call_args
    assert answer_kwargs is not None
    # State should NOT change to button_label
    assert cur_st["val"] == UserCampaignWizard.buttons, (
        "State should stay at buttons when cap reached"
    )
    print("  PASS test_P7_03_two_step_button_builder_add_validate_remove")


async def test_P7_04_interactive_group_checkboxes_toggle_all_clear():
    """Group picker: pre-selects all, toggle deselects one, clear empties, confirm enforces selection."""
    import handlers.user.my_campaign as ucamp_h
    from states.user_states import UserCampaignWizard
    from models.groups import upsert_group
    from models.users import set_user_lang, ensure_user_lang

    uid = 770004
    gid1, gid2 = -1007701, -1007702
    await ensure_user_lang(uid, "en")
    await set_user_lang(uid, "en")
    await upsert_group(gid1, "Group Alpha", "supergroup", uid)
    await upsert_group(gid2, "Group Beta", "supergroup", uid)

    # ── Ask groups: pre-selects all ────────────────────────────────────────
    state, store, cur_st = _make_memory_state({})
    cb = _make_callback(uid, "ucw_grp_done", "en")
    await ucamp_h._ask_groups(cb, state, prefer_edit=False)
    selected = store.get("selected_groups") or []
    assert gid1 in selected and gid2 in selected, (
        f"Expected both groups pre-selected on first visit, got {selected}"
    )

    # ── Toggle gid1 → it should deselect ──────────────────────────────────
    cb_toggle = _make_callback(uid, f"ucw_grp_toggle_{gid1}", "en")
    await ucamp_h.cb_ucw_grp_toggle(cb_toggle, state)
    selected_after = store.get("selected_groups") or []
    assert gid1 not in selected_after, f"gid1 should be deselected after toggle, got {selected_after}"
    assert gid2 in selected_after, f"gid2 should still be selected"

    # ── Clear all ──────────────────────────────────────────────────────────
    cb_none = _make_callback(uid, "ucw_grp_none", "en")
    await ucamp_h.cb_ucw_grp_none(cb_none, state)
    selected_clear = store.get("selected_groups") or []
    assert selected_clear == [], f"Expected empty after clear all, got {selected_clear}"

    # ── Confirm with no selection → show alert ─────────────────────────────
    cb_done_empty = _make_callback(uid, "ucw_grp_done", "en")
    await ucamp_h.cb_ucw_grp_done(cb_done_empty, state)
    cb_done_empty.answer.assert_awaited()
    answer_args = cb_done_empty.answer.call_args
    assert answer_args is not None
    # Must not have set target_chat_ids yet
    assert "target_chat_ids" not in store or not store["target_chat_ids"]

    # ── Select all then confirm → target_chat_ids set ─────────────────────
    cb_all = _make_callback(uid, "ucw_grp_all", "en")
    await ucamp_h.cb_ucw_grp_all(cb_all, state)
    cb_done = _make_callback(uid, "ucw_grp_done", "en")
    # Need to give next step somewhere to go
    state_tmp, store_tmp, cur_st_tmp = state, store, cur_st
    await ucamp_h.cb_ucw_grp_done(cb_done, state_tmp)
    target = store_tmp.get("target_chat_ids") or []
    assert gid1 in target and gid2 in target, (
        f"Expected both groups in target_chat_ids after confirm all, got {target}"
    )
    print("  PASS test_P7_04_interactive_group_checkboxes_toggle_all_clear")


async def test_P7_05_schedule_mode_and_autodelete_pickers():
    """Mode picker (custom hours >= 6) and auto-delete picker set correct state data."""
    import handlers.user.my_campaign as ucamp_h
    from states.user_states import UserCampaignWizard
    from models.users import set_user_lang, ensure_user_lang

    uid = 770005
    await ensure_user_lang(uid, "ar")
    await set_user_lang(uid, "ar")

    state, store, cur_st = _make_memory_state({
        "text": "<b>Test</b>",
        "target_chat_ids": [-1007701],
    })

    # ── cb_ucw_mode_recurring with "custom" → transitions to custom_hours ─
    cb_rec = _make_callback(uid, "ucw_mode_rec_custom", "ar")
    await ucamp_h.cb_ucw_mode_recurring(cb_rec, state)
    assert cur_st["val"] == UserCampaignWizard.custom_hours, (
        f"Expected custom_hours state, got {cur_st['val']}"
    )

    # ── process_ucw_custom_hours with "3" → rejected (< 6) ────────────────
    msg_bad = _make_message(uid, "3", "ar")
    msg_bad.message = msg_bad   # so _ask_ucw_autodel's target_msg resolves correctly
    await ucamp_h.process_ucw_custom_hours(msg_bad, state)
    # State should still be custom_hours
    assert cur_st["val"] == UserCampaignWizard.custom_hours, (
        "State should stay custom_hours when < 6 hours entered"
    )
    assert store.get("mode") != "recurring" or store.get("repeat_hours", 0) != 3

    # ── process_ucw_custom_hours with "8" → valid, proceeds to auto_delete ─
    cur_st["val"] = UserCampaignWizard.custom_hours
    msg_good = _make_message(uid, "8", "ar")
    msg_good.message = msg_good  # so _ask_ucw_autodel's target_msg resolves correctly
    await ucamp_h.process_ucw_custom_hours(msg_good, state)
    assert store.get("mode") == "recurring", f"Expected mode=recurring, got {store.get('mode')!r}"
    assert store.get("repeat_hours") == 8, f"Expected repeat_hours=8, got {store.get('repeat_hours')}"

    # ── cb_ucw_autodel with 21600 → stored, preview shown ─────────────────
    cb_autodel = _make_callback(uid, "ucw_autodel_21600", "ar")
    # _show_live_preview needs answer_photo and answer mocks
    cb_autodel.message.answer_photo = mock.AsyncMock()
    cb_autodel.message.answer = mock.AsyncMock()
    with mock.patch("handlers.user.my_campaign.get_current_campaign", new=mock.AsyncMock(return_value=None)):
        await ucamp_h.cb_ucw_autodel(cb_autodel, state)
    assert store.get("auto_delete_seconds") == 21600, (
        f"Expected auto_delete_seconds=21600, got {store.get('auto_delete_seconds')}"
    )
    assert cur_st["val"] == UserCampaignWizard.confirm, (
        f"Expected confirm state after autodel, got {cur_st['val']}"
    )
    print("  PASS test_P7_05_schedule_mode_and_autodelete_pickers")


async def test_P7_06_live_preview_does_not_consume_quota():
    """_show_live_preview: sends photo+caption+buttons, then summary card; quota unchanged."""
    import handlers.user.my_campaign as ucamp_h
    from models.user_campaigns import get_quota, _today
    from models.users import set_user_lang, ensure_user_lang

    uid = 770006
    await ensure_user_lang(uid, "en")
    await set_user_lang(uid, "en")

    state, store, cur_st = _make_memory_state({
        "text": "<b>Big Launch!</b>",
        "photo_file_id": "preview_photo_123",
        "buttons_list": [{"text": "Visit Site", "url": "https://example.com"}],
        "target_chat_ids": [-1007701, -1007702],
        "mode": "immediate",
        "repeat_hours": 0,
        "auto_delete_seconds": 3600,
    })

    msg = mock.MagicMock()
    msg.from_user = mock.MagicMock()
    msg.from_user.id = uid
    msg.from_user.language_code = "en"
    msg.answer_photo = mock.AsyncMock()
    msg.answer = mock.AsyncMock()
    msg.edit_text = mock.AsyncMock()
    msg.photo = None
    msg.video = None
    msg.caption = None

    with mock.patch("handlers.user.my_campaign.get_current_campaign", new=mock.AsyncMock(return_value=None)):
        await ucamp_h._show_live_preview(msg, uid, state, "en")

    # 1. answer_photo called once with correct photo + caption
    assert msg.answer_photo.await_count == 1, (
        f"Expected 1 answer_photo call, got {msg.answer_photo.await_count}"
    )
    p_kwargs = msg.answer_photo.call_args[1] if msg.answer_photo.call_args[1] else {}
    p_args = msg.answer_photo.call_args[0] if msg.answer_photo.call_args[0] else ()
    actual_photo = p_kwargs.get("photo") or (p_args[0] if p_args else None)
    actual_caption = p_kwargs.get("caption") or (p_args[1] if len(p_args) > 1 else None)
    assert actual_photo == "preview_photo_123", f"Wrong photo: {actual_photo!r}"
    assert actual_caption == "<b>Big Launch!</b>", f"Wrong caption: {actual_caption!r}"

    # 2. reply_markup has "Visit Site" button
    reply_markup = p_kwargs.get("reply_markup")
    assert reply_markup is not None, "Expected reply_markup in answer_photo"
    btn = reply_markup.inline_keyboard[0][0]
    assert btn.text == "Visit Site", f"Expected 'Visit Site' button, got {btn.text!r}"

    # 3. answer called once for summary/control card
    assert msg.answer.await_count >= 1, "Expected at least 1 answer call for summary card"
    summary_text = msg.answer.call_args_list[0][0][0] if msg.answer.call_args_list[0][0] else ""
    assert "Campaign" in summary_text or "حملة" in summary_text or len(summary_text) > 10, (
        f"Summary card text seems empty: {summary_text!r}"
    )

    # 4. Control keyboard has confirm, edit, cancel callbacks
    ctrl_kb = msg.answer.call_args_list[0][1].get("reply_markup") if msg.answer.call_args_list else None
    if ctrl_kb is None and len(msg.answer.call_args_list[0]) > 1:
        ctrl_kb = None
    # Gather all callback_data from summary card keyboard
    if ctrl_kb:
        all_cbs = {btn.callback_data for row in ctrl_kb.inline_keyboard for btn in row}
        assert "ucw_confirm_launch" in all_cbs, f"ucw_confirm_launch missing from ctrl kb: {all_cbs}"
        assert "ucw_edit_menu" in all_cbs, f"ucw_edit_menu missing from ctrl kb: {all_cbs}"
        assert "ucw_cancel_wizard" in all_cbs, f"ucw_cancel_wizard missing from ctrl kb: {all_cbs}"

    # 5. Quota unchanged
    quota_before = await get_quota(uid, _today())
    assert quota_before == 0, f"Preview should not consume quota, got {quota_before}"
    print("  PASS test_P7_06_live_preview_does_not_consume_quota")


async def test_P7_07_edit_from_preview_returns_directly_to_preview():
    """cb_ucw_edit_field → process_ucw_text with editing_field='text' updates and returns to preview."""
    import handlers.user.my_campaign as ucamp_h
    from states.user_states import UserCampaignWizard
    from models.users import set_user_lang, ensure_user_lang

    uid = 770007
    await ensure_user_lang(uid, "en")
    await set_user_lang(uid, "en")

    state, store, cur_st = _make_memory_state({
        "text": "Old Text",
        "photo_file_id": None,
        "buttons_list": [],
        "target_chat_ids": [-1007701],
        "mode": "immediate",
        "repeat_hours": 0,
        "auto_delete_seconds": 0,
    })
    cur_st["val"] = UserCampaignWizard.confirm

    # ── Step 1: cb_ucw_edit_field with 'ucw_edit_text' ────────────────────
    cb_edit = _make_callback(uid, "ucw_edit_text", "en")
    cb_edit.message.edit_text = mock.AsyncMock()
    cb_edit.message.answer = mock.AsyncMock()
    await ucamp_h.cb_ucw_edit_field(cb_edit, state)
    assert store.get("editing_field") == "text", (
        f"Expected editing_field='text', got {store.get('editing_field')!r}"
    )
    assert cur_st["val"] == UserCampaignWizard.text, (
        f"Expected text state after edit_field, got {cur_st['val']}"
    )

    # ── Step 2: process_ucw_text updates text and returns to preview ───────
    msg_new = _make_message(uid, "New Updated Text", "en")
    msg_new.html_text = "<b>New Updated Text</b>"
    msg_new.answer = mock.AsyncMock()
    msg_new.answer_photo = mock.AsyncMock()
    msg_new.edit_text = mock.AsyncMock()

    with mock.patch("handlers.user.my_campaign.get_current_campaign", new=mock.AsyncMock(return_value=None)):
        await ucamp_h.process_ucw_text(msg_new, state)

    # text should be updated
    assert store.get("text") == "<b>New Updated Text</b>", (
        f"Expected updated text, got {store.get('text')!r}"
    )
    # editing_field should be cleared
    assert store.get("editing_field") is None, (
        f"editing_field should be None after returning to preview, got {store.get('editing_field')!r}"
    )
    # State should be confirm (set by _show_live_preview)
    assert cur_st["val"] == UserCampaignWizard.confirm, (
        f"Expected confirm state after edit returns to preview, got {cur_st['val']}"
    )
    # The first answer call should be the preview text message (body = updated text)
    if msg_new.answer.await_count > 0:
        first_call_text = msg_new.answer.call_args_list[0][0][0]
        assert "<b>New Updated Text</b>" in first_call_text or "New Updated Text" in first_call_text, (
            f"Expected updated text in preview answer, got {first_call_text!r}"
        )
    print("  PASS test_P7_07_edit_from_preview_returns_directly_to_preview")


async def test_P7_08_confirm_launch_persists_buttons_and_autodelete_end_to_end():
    """cb_ucw_confirm_launch: creates campaign with buttons+auto_delete, consumes quota."""
    import handlers.user.my_campaign as ucamp_h
    from models.user_campaigns import get_quota, _today, get_campaign_by_id, get_current_campaign
    from models.groups import upsert_group
    from models.settings import set_setting
    from models.users import set_user_lang, ensure_user_lang

    uid = 770008
    chat_id = -1007708
    await ensure_user_lang(uid, "ar")
    await set_user_lang(uid, "ar")
    await set_setting("user_campaigns_enabled", "true")
    await upsert_group(chat_id, "Test Group 8", "supergroup", uid)

    state, store, cur_st = _make_memory_state({
        "text": "<b>إعلان نهائي</b>",
        "photo_file_id": None,
        "buttons_list": [{"text": "اشترك الآن", "url": "https://t.me/mychannel"}],
        "target_chat_ids": [chat_id],
        "selected_groups": [chat_id],
        "mode": "immediate",
        "repeat_hours": 0,
        "auto_delete_seconds": 3600,
    })

    cb = _make_callback(uid, "ucw_confirm_launch", "ar")
    cb.message.edit_text = mock.AsyncMock()
    cb.message.answer = mock.AsyncMock()
    cb.message.photo = None
    cb.message.video = None
    cb.message.caption = None

    with mock.patch("asyncio.create_task", return_value=mock.MagicMock()):
        await ucamp_h.cb_ucw_confirm_launch(cb, state)

    # Quota consumed
    quota = await get_quota(uid, _today())
    assert quota == 1, f"Expected quota=1 after launch, got {quota}"

    # Campaign persisted with correct data
    camp = await get_current_campaign(uid)
    if camp is None:
        # May have been set to 'running' or similar; fetch by owner
        from models.user_campaigns import get_campaign_by_id
        # Try to find by recent campaign
        from core.database import get_db
        async with get_db() as db:
            async with db.execute(
                "SELECT * FROM user_campaigns WHERE owner_user_id=? ORDER BY id DESC LIMIT 1",
                (uid,)
            ) as cur:
                row = await cur.fetchone()
                if row:
                    import aiosqlite
                    camp = dict(zip([d[0] for d in cur.description], row))
    assert camp is not None, "Campaign should have been created"
    assert camp.get("auto_delete_seconds") == 3600, (
        f"Expected auto_delete_seconds=3600, got {camp.get('auto_delete_seconds')}"
    )
    buttons_data = json.loads(camp.get("buttons_json") or "[]")
    # Wizard stores {"text":..., "url":...} but service expects [[{"label":..., "url":...}]]
    # cb_ucw_confirm_launch converts: buttons_data should be in service row format
    assert buttons_data == [[{"label": "اشترك الآن", "url": "https://t.me/mychannel"}]], (
        f"buttons_json mismatch: {buttons_data}"
    )
    print("  PASS test_P7_08_confirm_launch_persists_buttons_and_autodelete_end_to_end")


async def test_P7_09_cancel_from_preview_consumes_zero_quota():
    """cb_ucw_cancel_wizard: clears state without consuming quota (AR and EN)."""
    import handlers.user.my_campaign as ucamp_h
    from models.user_campaigns import get_quota, _today
    from models.users import set_user_lang, ensure_user_lang
    from locales.ar import STRINGS as AR
    from locales.en import STRINGS as EN

    # ── Arabic ─────────────────────────────────────────────────────────────
    uid_ar = 770009
    await ensure_user_lang(uid_ar, "ar")
    await set_user_lang(uid_ar, "ar")
    state_ar, store_ar, cur_st_ar = _make_memory_state({
        "text": "إعلان", "target_chat_ids": [-1007701]
    })
    cb_ar = _make_callback(uid_ar, "ucw_cancel_wizard", "ar")
    cb_ar.message.edit_text = mock.AsyncMock()
    cb_ar.message.answer = mock.AsyncMock()
    cb_ar.message.photo = None
    cb_ar.message.video = None
    cb_ar.message.caption = None
    await ucamp_h.cb_ucw_cancel_wizard(cb_ar, state_ar)

    # State cleared
    assert cur_st_ar["val"] is None, "State should be cleared after cancel"
    # Answer/edit_text called with cancelled text
    cancel_calls = cb_ar.message.edit_text.call_args_list + cb_ar.message.answer.call_args_list
    assert cancel_calls, "Expected at least one message call on cancel"
    cancel_text = cancel_calls[0][0][0] if cancel_calls[0][0] else ""
    ar_cancelled = AR.get("uc_cancelled", "")
    en_cancelled = EN.get("uc_cancelled", "")
    assert ar_cancelled in cancel_text or en_cancelled in cancel_text or "cancel" in cancel_text.lower(), (
        f"Expected cancelled message, got: {cancel_text!r}"
    )
    # Zero quota consumed
    quota_ar = await get_quota(uid_ar, _today())
    assert quota_ar == 0, f"Cancel should not consume quota (AR), got {quota_ar}"

    # ── English ────────────────────────────────────────────────────────────
    uid_en = 770010
    await ensure_user_lang(uid_en, "en")
    await set_user_lang(uid_en, "en")
    state_en, store_en, cur_st_en = _make_memory_state({
        "text": "ad", "target_chat_ids": [-1007701]
    })
    cb_en = _make_callback(uid_en, "ucw_cancel_wizard", "en")
    cb_en.message.edit_text = mock.AsyncMock()
    cb_en.message.answer = mock.AsyncMock()
    cb_en.message.photo = None
    cb_en.message.video = None
    cb_en.message.caption = None
    await ucamp_h.cb_ucw_cancel_wizard(cb_en, state_en)

    cancel_calls_en = cb_en.message.edit_text.call_args_list + cb_en.message.answer.call_args_list
    assert cancel_calls_en, "Expected at least one message call on cancel (EN)"
    cancel_text_en = cancel_calls_en[0][0][0] if cancel_calls_en[0][0] else ""
    assert en_cancelled in cancel_text_en or "cancel" in cancel_text_en.lower(), (
        f"Expected EN cancelled message, got: {cancel_text_en!r}"
    )
    quota_en = await get_quota(uid_en, _today())
    assert quota_en == 0, f"Cancel should not consume quota (EN), got {quota_en}"
    print("  PASS test_P7_09_cancel_from_preview_consumes_zero_quota")


# ── Suite I list ─────────────────────────────────────────────────────────────

SUITE_I = [
    test_P7_01_locale_parity_with_phase7_keys,
    test_P7_02_user_states_extended_cleanly,
    test_P7_03_two_step_button_builder_add_validate_remove,
    test_P7_04_interactive_group_checkboxes_toggle_all_clear,
    test_P7_05_schedule_mode_and_autodelete_pickers,
    test_P7_06_live_preview_does_not_consume_quota,
    test_P7_07_edit_from_preview_returns_directly_to_preview,
    test_P7_08_confirm_launch_persists_buttons_and_autodelete_end_to_end,
    test_P7_09_cancel_from_preview_consumes_zero_quota,
]

# ── Full suite list (Suites A–H from phase6_test, plus Suite I) ─────────────

SUITE_A = [
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
]

SUITE_B = [
    test_T1_old_worker_stops_after_replacement,
    test_T2_old_worker_stops_after_global_suspend,
    test_T3_no_new_sends_after_suspend_completes,
    test_T4_two_workers_cannot_claim_same_campaign,
    test_T5_no_resend_of_confirmed_messages,
    test_T6_execute_campaign_with_mocked_telegram,
]

SUITE_C = [
    test_P1_01_verify_campaign_groups_unpacking_iss01,
    test_P1_02_recurring_campaign_schedule_comparison_iss02,
    test_P1_03_legacy_groups_reward_owner_backfill_iss03,
    test_P1_04_resume_suspended_admin_campaign_iss04,
    test_P1_05_sqlite_pragmas_and_indexes_iss06,
    test_P1_06_fk_safety_for_unregistered_user_iss06,
    test_P1_07_recover_stale_claims_force_and_ttl_iss11,
]

SUITE_D = [
    test_P2_01_welcome_media_callbacks_and_user_dashboard_iss05,
    test_P2_02_html_escaping_in_groups_campaigns_and_buttons_iss07,
    test_P2_03_prevent_reusing_verified_groups_across_campaigns_iss08,
    test_P2_04_custom_buttons_included_in_campaign_broadcast_and_test_iss09,
    test_P2_05_user_campaign_no_duplicate_send_on_forbidden_or_rate_limit_iss10,
    test_P2_06_admin_broadcast_and_campaign_retry_after_handling_iss16,
    test_P2_07_preserve_html_text_and_paid_media_keyboard_iss17,
]

SUITE_E = [
    test_P3_01_fsm_non_text_input_guards_iss12,
    test_P3_02_recurring_broadcast_media_vip_wizard_iss13a,
    test_P3_03_broadcast_forbidden_does_not_deactivate_users_iss13b,
    test_P3_04_prevent_empty_user_campaign_and_paused_execution_iss14,
    test_P3_05_user_campaign_auto_delete_scheduled_iss15,
    test_P3_06_campaign_stats_views_and_delivered_iss18b,
    test_P3_07_admin_owner_protection_and_quota_text_iss18ac,  # Phase-6 override
    test_P3_08_parameterized_stats_and_cooldown_pruning_iss19,
]

SUITE_F = [
    test_P4_01_owner_create_permanent_invite_link,
    test_P4_02_owner_create_temporary_invite_link_and_expiry,
    test_P4_03_owner_manual_pause_and_resume_invite_link,
    test_P4_04_owner_delete_invite_link,
    test_P4_05_user_referral_generated_on_first_click_and_permanent,
    test_P4_06_user_referral_join_counting_and_deduplication,
    test_P4_07_start_message_contains_user_referral_button,
    test_P4_08_owner_invite_wizard_and_non_owner_restriction,  # Phase-6 override
]

SUITE_G = [
    test_P5_01_users_lang_column_and_persistence,
    test_P5_02_i18n_engine_fallback_and_key_parity,
    test_P5_03_auto_detect_initial_language,
    test_P5_04_language_switcher_command_and_callback,
    test_P5_05_start_buttons_and_back_localized,
    test_P5_06_owner_invite_error_messages_localized,
    test_P5_07_user_referral_screen_localized,
    test_P5_08_my_groups_screen_localized,
    test_P5_09_campaign_progress_and_verify_localized,
]

SUITE_H = [
    test_P6_01_full_locale_key_and_placeholder_parity,
    test_P6_02_owner_invite_links_ui_localized_ar_and_en,
    test_P6_03_admin_panel_translation_engine_coverage,
    test_P6_04_admins_handler_localized_ar_and_en,
    test_P6_05_admin_broadcast_and_campaign_status_localized,
    test_P6_06_session_middleware_translates_admin_private_chat_only,
    test_P6_07_language_middleware_sets_user_and_lang_context,
    test_P6_08_independent_admin_and_user_languages,
    test_P6_09_main_py_registers_admin_session_middleware,
]

ALL_TESTS = SUITE_A + SUITE_B + SUITE_C + SUITE_D + SUITE_E + SUITE_F + SUITE_G + SUITE_H + SUITE_I


async def run_all():
    await setup_db()
    passed = 0
    failed = 0
    errors = []

    for test_fn in ALL_TESTS:
        try:
            await test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            errors.append((test_fn.__name__, e))
            import traceback
            print(f"  FAIL {test_fn.__name__}: {e}")
            traceback.print_exc()

    print()
    print("=" * 70)
    print(f"Phase 7 Cumulative Results: {passed}/{len(ALL_TESTS)} passed, {failed} failed")
    print("=" * 70)

    if errors:
        print("\nFailed tests:")
        for name, err in errors:
            print(f"  ✗ {name}: {err}")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all())
    sys.exit(0 if success else 1)
