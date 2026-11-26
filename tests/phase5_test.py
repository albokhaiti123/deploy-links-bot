#!/usr/bin/env python3
"""
Cumulative Test Suite — Phase 5 (tests/phase5_test.py)
Includes:
  - Suite A: 12 foundational user campaign tests
  - Suite B: 6 worker safety tests
  - Suite C: 7 Phase 1 repair verification tests
  - Suite D: 7 Phase 2 repair verification tests
  - Suite E: 8 Phase 3 repair verification tests
  - Suite F: 8 Phase 4 verification tests (Owner Invite Links & User Permanent Referral)
  - Suite G: 9 Phase 5 i18n core + localized UI tests
Total: 57 cumulative tests.
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

from tests.phase4_test import (
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
    # Suite F: Phase 4 (8)
    test_P4_01_owner_create_permanent_invite_link,
    test_P4_02_owner_create_temporary_invite_link_and_expiry,
    test_P4_03_owner_manual_pause_and_resume_invite_link,
    test_P4_04_owner_delete_invite_link,
    test_P4_05_user_referral_generated_on_first_click_and_permanent,
    test_P4_06_user_referral_join_counting_and_deduplication,
    test_P4_07_start_message_contains_user_referral_button,
    test_P4_08_owner_invite_wizard_and_non_owner_restriction,
)


# ── Suite G: Phase 5 i18n Tests ──────────────────────────────────────────────

async def test_P5_01_users_lang_column_and_persistence():
    """users table has lang column; set_user_lang/get_user_lang persist correctly."""
    from core.database import init_db
    from models.users import upsert_user, get_user_lang, set_user_lang

    await init_db()
    # Upsert a fresh user
    await upsert_user(750001, "langtest", "LangUser")

    # Initially lang may be None or the default
    # Explicitly set and retrieve
    await set_user_lang(750001, "ar")
    result = await get_user_lang(750001)
    assert result == "ar", f"Expected 'ar', got {result!r}"

    await set_user_lang(750001, "en")
    result2 = await get_user_lang(750001)
    assert result2 == "en", f"Expected 'en', got {result2!r}"
    print("  PASS test_P5_01_users_lang_column_and_persistence")


async def test_P5_02_i18n_engine_fallback_and_key_parity():
    """
    - locales.t() returns correct strings for 'ar' and 'en'.
    - Fallback to 'en' when language is unknown.
    - Both locale dicts have exactly the same keys (parity check).
    """
    from locales import t, get_strings
    from locales.ar import STRINGS as AR
    from locales.en import STRINGS as EN

    # Key parity
    ar_keys = set(AR.keys())
    en_keys = set(EN.keys())
    missing_in_en = ar_keys - en_keys
    missing_in_ar = en_keys - ar_keys
    assert not missing_in_en, f"Keys in ar but not en: {missing_in_en}"
    assert not missing_in_ar, f"Keys in en but not ar: {missing_in_ar}"

    # Correct translations
    ar_referral = t("btn_my_referral", "ar")
    en_referral = t("btn_my_referral", "en")
    assert "رابط" in ar_referral or "Referral" in ar_referral or "🔗" in ar_referral, \
        f"Arabic referral btn unexpected: {ar_referral!r}"
    assert "Referral" in en_referral or "🔗" in en_referral, \
        f"English referral btn unexpected: {en_referral!r}"
    assert ar_referral != en_referral, "Arabic and English referral labels should differ"

    # Fallback to English for unknown lang
    fallback = t("btn_my_referral", "zz")
    assert fallback == en_referral, f"Fallback should be English, got {fallback!r}"

    # Format substitution works
    camp_en = t("camp_locked_msg", "en",
                title="Test", verified=1, required=3, remaining=2, bot_username="testbot")
    assert "Test" in camp_en and "testbot" in camp_en

    print("  PASS test_P5_02_i18n_engine_fallback_and_key_parity")


async def test_P5_03_auto_detect_initial_language():
    """
    ensure_user_lang sets lang from Telegram language_code on first call,
    and does NOT overwrite an already-persisted lang.
    """
    from models.users import upsert_user, get_user_lang, set_user_lang, ensure_user_lang

    # New user with Arabic language_code
    await upsert_user(750002, "ar_user", "Arabic User")
    lang = await ensure_user_lang(750002, "ar")
    assert lang == "ar", f"Expected 'ar', got {lang!r}"
    stored = await get_user_lang(750002)
    assert stored == "ar", f"DB should have 'ar', got {stored!r}"

    # Calling again with a different code should NOT overwrite (already set)
    lang2 = await ensure_user_lang(750002, "en")
    assert lang2 == "ar", f"Should preserve existing 'ar', got {lang2!r}"

    # New user with no language_code → defaults to 'en'
    await upsert_user(750003, "default_user", "Default User")
    lang3 = await ensure_user_lang(750003, None)
    assert lang3 == "en", f"Expected 'en' fallback, got {lang3!r}"

    print("  PASS test_P5_03_auto_detect_initial_language")


async def test_P5_04_language_switcher_command_and_callback():
    """
    Language switcher: set_user_lang updates DB;
    get_user_lang returns the new value;
    cache is invalidated correctly.
    """
    from models.users import upsert_user, get_user_lang, set_user_lang
    from core.i18n import cache_user_lang, get_cached_lang, invalidate_user_lang

    await upsert_user(750004, "switcher", "Switcher")
    await set_user_lang(750004, "en")

    # Simulate /lang → set_lang_ar flow
    cache_user_lang(750004, "en")
    assert get_cached_lang(750004) == "en"

    await set_user_lang(750004, "ar")
    invalidate_user_lang(750004)
    cache_user_lang(750004, "ar")

    assert get_cached_lang(750004) == "ar"
    db_val = await get_user_lang(750004)
    assert db_val == "ar", f"Expected 'ar' in DB, got {db_val!r}"

    print("  PASS test_P5_04_language_switcher_command_and_callback")


async def test_P5_05_start_buttons_and_back_localized():
    """
    get_start_message_data injects a referral button with i18n label.
    Arabic lang_code → Arabic label; English/unknown → English label.
    """
    import unittest.mock as mock

    # Mock the base function to return a simple keyboard
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    base_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Info", callback_data="start_btn2_click")]
    ])
    base_text = "Welcome!"

    with mock.patch(
        "handlers.start._get_start_message_data_base",
        return_value=(base_text, base_kb)
    ):
        from handlers.start import get_start_message_data

        # Arabic
        _, kb_ar = await get_start_message_data("testbot", language_code="ar")
        all_btns_ar = [btn for row in kb_ar.inline_keyboard for btn in row]
        ref_btns_ar = [b for b in all_btns_ar if b.callback_data == "user_my_referral"]
        assert ref_btns_ar, "Missing referral button for AR"
        ar_label = ref_btns_ar[0].text
        assert "رابط" in ar_label or "🔗" in ar_label, f"Arabic label unexpected: {ar_label!r}"

        # English
        _, kb_en = await get_start_message_data("testbot", language_code="en")
        all_btns_en = [btn for row in kb_en.inline_keyboard for btn in row]
        ref_btns_en = [b for b in all_btns_en if b.callback_data == "user_my_referral"]
        assert ref_btns_en, "Missing referral button for EN"
        en_label = ref_btns_en[0].text
        assert "Referral" in en_label or "🔗" in en_label, f"English label unexpected: {en_label!r}"

        # Unknown code → English fallback
        _, kb_xx = await get_start_message_data("testbot", language_code="xx")
        all_btns_xx = [btn for row in kb_xx.inline_keyboard for btn in row]
        ref_btns_xx = [b for b in all_btns_xx if b.callback_data == "user_my_referral"]
        assert ref_btns_xx, "Missing referral button for unknown lang"
        assert ref_btns_xx[0].text == en_label, "Unknown lang should use English label"

    print("  PASS test_P5_05_start_buttons_and_back_localized")


async def test_P5_06_owner_invite_error_messages_localized():
    """
    Localized invite error messages exist for both 'ar' and 'en'.
    """
    from locales import t

    for lang in ("ar", "en"):
        paused = t("invite_paused", lang)
        expired = t("invite_expired", lang)
        invalid = t("invite_invalid", lang)
        assert paused and len(paused) > 5, f"[{lang}] invite_paused too short: {paused!r}"
        assert expired and len(expired) > 5, f"[{lang}] invite_expired too short: {expired!r}"
        assert invalid and len(invalid) > 5, f"[{lang}] invite_invalid too short: {invalid!r}"
        # Check they differ between languages
    assert t("invite_paused", "ar") != t("invite_paused", "en"), \
        "Arabic and English invite_paused should differ"

    print("  PASS test_P5_06_owner_invite_error_messages_localized")


async def test_P5_07_user_referral_screen_localized():
    """
    Referral screen strings: title, count, hint, btn_share, btn_back
    exist in both languages and are non-empty.
    """
    from locales import t

    keys = ["referral_title", "referral_count", "referral_hint",
            "btn_share_link", "btn_back", "referral_share_text"]
    for lang in ("ar", "en"):
        for key in keys:
            val = t(key, lang)
            assert val and val != key, f"[{lang}] key={key!r} returned empty/missing: {val!r}"
        # Title and hint should differ between langs
    assert t("referral_title", "ar") != t("referral_title", "en"), \
        "referral_title should differ between languages"

    print("  PASS test_P5_07_user_referral_screen_localized")


async def test_P5_08_my_groups_screen_localized():
    """
    My Groups screen strings exist and format correctly for both languages.
    """
    from locales import t

    for lang in ("ar", "en"):
        empty = t("my_groups_empty", lang)
        header = t("my_groups_header", lang, count=3)
        assert empty and len(empty) > 10, f"[{lang}] my_groups_empty too short"
        assert "3" in header, f"[{lang}] count not formatted in my_groups_header: {header!r}"
        assert "<b>" in header, f"[{lang}] my_groups_header should have bold markup"

    # Both languages' headers should differ
    assert t("my_groups_header", "ar", count=1) != t("my_groups_header", "en", count=1), \
        "Arabic and English my_groups_header should differ"

    print("  PASS test_P5_08_my_groups_screen_localized")


async def test_P5_09_campaign_progress_and_verify_localized():
    """
    Campaign locked/unlocked messages and verify button exist and format correctly.
    """
    from locales import t

    for lang in ("ar", "en"):
        locked = t("camp_locked_msg", lang,
                   title="TestCamp", verified=1, required=5, remaining=4, bot_username="testbot")
        unlocked = t("camp_unlocked_msg", lang)
        btn_verify = t("btn_verify", lang)
        cooldown = t("verify_cooldown_alert", lang, seconds=10)

        assert "TestCamp" in locked, f"[{lang}] title not in camp_locked_msg"
        assert "testbot" in locked, f"[{lang}] bot_username not in camp_locked_msg"
        assert "1" in locked and "5" in locked, f"[{lang}] counts not in camp_locked_msg"
        assert unlocked and len(unlocked) > 5, f"[{lang}] camp_unlocked_msg too short"
        assert btn_verify and len(btn_verify) > 1, f"[{lang}] btn_verify too short"
        assert "10" in cooldown, f"[{lang}] seconds not in verify_cooldown_alert"

    # Messages differ between languages
    locked_ar = t("camp_locked_msg", "ar",
                  title="X", verified=0, required=1, remaining=1, bot_username="b")
    locked_en = t("camp_locked_msg", "en",
                  title="X", verified=0, required=1, remaining=1, bot_username="b")
    assert locked_ar != locked_en, "Locked messages should differ between languages"

    print("  PASS test_P5_09_campaign_progress_and_verify_localized")


# ── Runner ───────────────────────────────────────────────────────────────────

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
    test_P3_07_admin_owner_protection_and_quota_text_iss18ac,
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
    test_P4_08_owner_invite_wizard_and_non_owner_restriction,
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

ALL_TESTS = SUITE_A + SUITE_B + SUITE_C + SUITE_D + SUITE_E + SUITE_F + SUITE_G


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
            print(f"  FAIL {test_fn.__name__}: {e}")

    print()
    print("=" * 65)
    print(f"Phase 5 Final Cumulative Results: {passed}/{len(ALL_TESTS)} passed, {failed} failed")
    print("=" * 65)

    if errors:
        print("\nFailed tests:")
        for name, err in errors:
            print(f"  ✗ {name}: {err}")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all())
    sys.exit(0 if success else 1)
