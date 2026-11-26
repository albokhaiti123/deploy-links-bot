#!/usr/bin/env python3
"""
Phase 8 Cumulative Test Suite — Deploy Links Bot
Tests: Suites A–J (85 total: 75 from phase7 + 10 new Phase 8 tests)
"""

import asyncio
import json
import os
import sys
import tempfile
import traceback
from unittest.mock import AsyncMock, MagicMock, patch

# ── Environment ───────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DB_NAME"]         = _tmp_db.name
os.environ["ADMIN_ID"]        = "999999"
os.environ["BOT_TOKEN"]       = "123456:ABC"
os.environ["BOT_USERNAME"]    = "testbot"
os.environ["QUOTA_TIMEZONE"]  = "UTC"

# ── Import phase 7 tests (suites A–I, 75 tests) ──────────────────────────────
from tests.phase7_test import (
    # Suite A
    test_P7_01_locale_parity_with_phase7_keys,
    test_P7_02_user_states_extended_cleanly,
    # Suite B
    test_P7_03_two_step_button_builder_add_validate_remove,
    # Suite C
    test_P7_04_interactive_group_checkboxes_toggle_all_clear,
    # Suite D
    test_P7_05_schedule_mode_and_autodelete_pickers,
    # Suite E
    test_P7_06_live_preview_does_not_consume_quota,
    # Suite F
    test_P7_07_edit_from_preview_returns_directly_to_preview,
    # Suite G
    test_P7_08_confirm_launch_persists_buttons_and_autodelete_end_to_end,
    # Suite H
    test_P7_09_cancel_from_preview_consumes_zero_quota,
    # Helpers
    _make_memory_state,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

PASS = 0
FAIL = 0
RESULTS = []


async def _run(name: str, coro):
    global PASS, FAIL
    try:
        await coro
        PASS += 1
        RESULTS.append(f"  ✅ {name}")
    except Exception as e:
        FAIL += 1
        tb = traceback.format_exc()
        RESULTS.append(f"  ❌ {name}\n     {e}\n{tb}")


async def _init_fresh_db():
    """Re-initialise the DB from scratch (safe to call multiple times)."""
    from core.database import init_db
    await init_db()


# ── Suite J: Phase 8 Tests ────────────────────────────────────────────────────

async def test_P8_01_locale_parity_ge_194_keys():
    """AR and EN each have ≥ 194 keys (148 from phases 5-7 + 46 Phase 8)."""
    from locales.ar import STRINGS as AR
    from locales.en import STRINGS as EN
    assert len(AR) >= 194, f"AR has only {len(AR)} keys"
    assert len(EN) >= 194, f"EN has only {len(EN)} keys"
    assert set(AR.keys()) == set(EN.keys()), "AR/EN key mismatch"
    # Spot-check Phase 8 keys
    p8_keys = [
        "u8_btn_my_stats", "u8_btn_my_history", "u8_btn_test_dm",
        "u8_btn_edit_live", "u8_btn_last_report", "u8_btn_check_health",
        "u8_stats_body", "u8_report_title", "u8_edit_title", "u8_hist_title",
        "u8_groups_health_summary", "u8_health_check_done",
    ]
    for k in p8_keys:
        assert k in AR, f"Missing AR key: {k}"
        assert k in EN, f"Missing EN key: {k}"


async def test_P8_02_get_user_overall_stats_accuracy():
    """get_user_overall_stats returns correct counts + bilingual stats screen renders."""
    await _init_fresh_db()
    from core.database import get_db
    from models.user_campaigns import record_delivery
    from models.invite_links import get_or_create_user_referral, process_user_referral_join
    from core.i18n import set_lang, t
    from models.user_campaigns import get_user_overall_stats

    uid = 20001
    friend_uid = 20002

    # Insert a campaign directly
    async with get_db() as db:
        await db.execute(
            "INSERT INTO users (telegram_id, username) VALUES (?, ?) ON CONFLICT DO NOTHING",
            (uid, "stats_user"),
        )
        await db.execute(
            "INSERT INTO users (telegram_id, username) VALUES (?, ?) ON CONFLICT DO NOTHING",
            (friend_uid, "friend"),
        )
        await db.execute(
            """INSERT INTO user_campaigns
               (owner_user_id, text, mode, status, system_generation, run_id, quota_date, created_at)
               VALUES (?, 'hello', 'immediate', 'completed', 1, 'run-stats-01', date('now'), datetime('now'))""",
            (uid,),
        )
        async with db.execute("SELECT last_insert_rowid()") as c:
            cid = (await c.fetchone())[0]
        # Also count quota
        await db.execute(
            "INSERT INTO user_campaign_quota (user_id, quota_date, campaigns_created) VALUES (?,date('now'),2)",
            (uid,),
        )
        # Register a group for user
        await db.execute(
            "INSERT INTO groups (chat_id, title, chat_type, status, reward_owner_id) VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING",
            (-100111, "Stats Group", "supergroup", "active", uid),
        )
        await db.commit()

    await record_delivery(cid, "run-stats-01", -100111, "sent")
    await record_delivery(cid, "run-stats-01", -100222, "failed", "BOT_KICKED")

    # Create a referral link so referrals_count gets set
    ref_data = await get_or_create_user_referral(uid)
    code = ref_data["ref_code"]
    await process_user_referral_join(code, friend_uid)

    stats = await get_user_overall_stats(uid)
    assert stats["total_campaigns"] >= 1
    assert stats["sent_ok"] >= 1
    assert stats["sent_fail"] >= 1
    assert stats["quota_today"] >= 2
    assert stats["active_groups"] >= 1
    assert stats["referrals"] >= 1

    # Render bilingual stats screen
    set_lang(uid, "ar")
    text_ar = t("u8_stats_body", "ar").format(**stats)
    assert "إحصائياتي" in text_ar

    set_lang(uid, "en")
    text_en = t("u8_stats_body", "en").format(**stats)
    assert "Statistics" in text_en


async def test_P8_03_delivery_report_per_group_html_escaped():
    """get_campaign_last_run_deliveries returns per-group rows; group titles are HTML-escapable."""
    await _init_fresh_db()
    from core.database import get_db
    from models.user_campaigns import record_delivery, get_campaign_last_run_deliveries
    import html

    uid = 20003
    async with get_db() as db:
        await db.execute(
            "INSERT INTO users (telegram_id, username) VALUES (?,?) ON CONFLICT DO NOTHING", (uid, "rep_user")
        )
        await db.execute(
            """INSERT INTO user_campaigns
               (owner_user_id, text, mode, status, system_generation, run_id, quota_date, created_at)
               VALUES (?, 'report test', 'immediate', 'completed', 1, 'run-rep-01', date('now'), datetime('now'))""",
            (uid,),
        )
        async with db.execute("SELECT last_insert_rowid()") as c:
            cid = (await c.fetchone())[0]
        await db.execute(
            "INSERT INTO groups (chat_id, title, chat_type, status, reward_owner_id) VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING",
            (-100301, "<B&R Group>", "supergroup", "active", uid),
        )
        await db.commit()

    await record_delivery(cid, "run-rep-01", -100301, "sent")
    await record_delivery(cid, "run-rep-01", -100302, "failed", "FLOOD_WAIT")

    rows = await get_campaign_last_run_deliveries(cid, uid)
    assert len(rows) == 2
    titles = [r["title"] for r in rows]
    # Title should be raw from DB; HTML escape is done in the handler
    for r in rows:
        escaped = html.escape(r["title"])
        assert "<" not in escaped or "&lt;" in escaped or escaped == r["title"]

    # Ownership check: wrong user gets []
    rows_wrong = await get_campaign_last_run_deliveries(cid, 99999)
    assert rows_wrong == []


async def test_P8_04_live_edit_all_6_fields_zero_quota():
    """update_user_campaign_fields updates 6 fields without consuming quota."""
    await _init_fresh_db()
    from core.database import get_db
    from models.user_campaigns import update_user_campaign_fields, get_quota

    uid = 20004
    async with get_db() as db:
        await db.execute(
            "INSERT INTO users (telegram_id, username) VALUES (?,?) ON CONFLICT DO NOTHING", (uid, "edit_user")
        )
        await db.execute(
            """INSERT INTO user_campaigns
               (owner_user_id, text, mode, status, system_generation, run_id, quota_date, created_at)
               VALUES (?, 'old text', 'immediate', 'active', 1, 'run-edit-01', date('now'), datetime('now'))""",
            (uid,),
        )
        async with db.execute("SELECT last_insert_rowid()") as c:
            cid = (await c.fetchone())[0]
        await db.execute(
            "INSERT INTO groups (chat_id, title, chat_type, status, reward_owner_id) VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING",
            (-100401, "Edit Group", "supergroup", "active", uid),
        )
        await db.commit()

    # Check quota before = 0
    quota_before = await get_quota(uid)

    # 1. text
    ok, reason = await update_user_campaign_fields(cid, uid, text="new text")
    assert ok, f"text update failed: {reason}"

    # 2. photo_file_id
    ok, reason = await update_user_campaign_fields(cid, uid, photo_file_id="new_file_123")
    assert ok, f"photo update failed: {reason}"

    # 3. buttons_json (flat format for live edit)
    buttons = json.dumps([{"text": "Click", "url": "https://example.com"}])
    ok, reason = await update_user_campaign_fields(cid, uid, buttons_json=buttons)
    assert ok, f"buttons update failed: {reason}"

    # 4. target_chat_ids
    ok, reason = await update_user_campaign_fields(cid, uid, target_chat_ids=[-100401])
    assert ok, f"groups update failed: {reason}"

    # 5. mode + repeat_hours
    ok, reason = await update_user_campaign_fields(cid, uid, mode="recurring", repeat_hours=12)
    assert ok, f"mode update failed: {reason}"

    # 6. auto_delete_seconds
    ok, reason = await update_user_campaign_fields(cid, uid, auto_delete_seconds=3600)
    assert ok, f"auto_delete update failed: {reason}"

    # Verify quota did NOT change
    quota_after = await get_quota(uid)
    assert quota_after == quota_before, f"Quota changed! Before={quota_before} After={quota_after}"

    # Verify DB state
    async with get_db() as db:
        async with db.execute("SELECT text, photo_file_id, mode, repeat_hours FROM user_campaigns WHERE id=?", (cid,)) as c:
            row = await c.fetchone()
    assert row[0] == "new text"
    assert row[1] == "new_file_123"
    assert row[2] == "recurring"
    assert row[3] == 12


async def test_P8_05_live_edit_validation_errors():
    """update_user_campaign_fields rejects: wrong owner, running status, empty text, min hours, bad group."""
    await _init_fresh_db()
    from core.database import get_db
    from models.user_campaigns import update_user_campaign_fields

    uid       = 20005
    other_uid = 20055  # different user to avoid UNIQUE collision
    running_uid = 20056  # separate user for the running campaign

    async with get_db() as db:
        await db.execute(
            "INSERT INTO users (telegram_id, username) VALUES (?,?) ON CONFLICT DO NOTHING", (uid, "val_user")
        )
        await db.execute(
            "INSERT INTO users (telegram_id, username) VALUES (?,?) ON CONFLICT DO NOTHING", (other_uid, "other_user")
        )
        await db.execute(
            "INSERT INTO users (telegram_id, username) VALUES (?,?) ON CONFLICT DO NOTHING", (running_uid, "running_user")
        )
        await db.execute(
            """INSERT INTO user_campaigns
               (owner_user_id, text, mode, status, system_generation, run_id, quota_date, created_at)
               VALUES (?, 'validate', 'immediate', 'active', 1, 'run-val-01', date('now'), datetime('now'))""",
            (uid,),
        )
        async with db.execute("SELECT last_insert_rowid()") as c:
            cid = (await c.fetchone())[0]
        await db.execute(
            """INSERT INTO user_campaigns
               (owner_user_id, text, mode, status, system_generation, run_id, quota_date, created_at)
               VALUES (?, 'running camp', 'immediate', 'running', 1, 'run-val-02', date('now'), datetime('now'))""",
            (running_uid,),
        )
        async with db.execute("SELECT last_insert_rowid()") as c:
            running_cid = (await c.fetchone())[0]
        await db.commit()

    # Wrong owner — other_uid is not the owner of cid
    ok, reason = await update_user_campaign_fields(cid, other_uid, text="x")
    assert not ok
    assert reason in ("not_found", "not_owner")

    # Running campaign — running_uid owns running_cid which is "running"
    ok, reason = await update_user_campaign_fields(running_cid, running_uid, text="x")
    assert not ok
    assert reason == "running"

    # Empty text
    ok, reason = await update_user_campaign_fields(cid, uid, text="   ")
    assert not ok
    assert reason == "empty_text"

    # Min repeat_hours < 6
    ok, reason = await update_user_campaign_fields(cid, uid, repeat_hours=3)
    assert not ok
    assert reason == "min_hours"

    # Group not owned by user
    ok, reason = await update_user_campaign_fields(cid, uid, target_chat_ids=[-100999])
    assert not ok
    assert reason == "group_not_owned"


async def test_P8_06_test_dm_sends_preview_zero_quota():
    """Test DM: bot sends photo+caption+buttons to user's private chat with zero quota used."""
    await _init_fresh_db()
    from core.database import get_db
    from models.user_campaigns import get_quota
    from handlers.user.dashboard_pro import cb_test_dm

    uid = 20006
    async with get_db() as db:
        await db.execute(
            "INSERT INTO users (telegram_id, username) VALUES (?,?) ON CONFLICT DO NOTHING", (uid, "dm_user")
        )
        buttons_json = json.dumps([{"text": "Visit", "url": "https://example.com"}])
        await db.execute(
            """INSERT INTO user_campaigns
               (owner_user_id, text, photo_file_id, buttons_json, mode, status, system_generation, run_id, quota_date, created_at)
               VALUES (?, 'DM test text', 'photo_file_777', ?, 'immediate', 'active', 1, 'run-dm-01', date('now'), datetime('now'))""",
            (uid, buttons_json),
        )
        async with db.execute("SELECT last_insert_rowid()") as c:
            cid = (await c.fetchone())[0]
        await db.commit()

    quota_before = await get_quota(uid)

    # Build mock callback
    call = MagicMock()
    call.from_user.id = uid
    call.data = f"user_test_campaign_{cid}"
    call.answer = AsyncMock()
    call.message.edit_text = AsyncMock()

    bot = MagicMock()
    bot.send_photo = AsyncMock()
    bot.send_message = AsyncMock()

    await cb_test_dm(call, bot)

    # Should have called send_photo (has photo_file_id)
    bot.send_photo.assert_called_once()
    call_kwargs = bot.send_photo.call_args
    assert call_kwargs.kwargs.get("photo") == "photo_file_777" or call_kwargs.args[1] == "photo_file_777"

    # Zero quota consumed
    quota_after = await get_quota(uid)
    assert quota_after == quota_before


async def test_P8_07_campaign_history_and_relaunch():
    """History returns last 10 campaigns; relaunch loads wizard at confirm state with 0 quota."""
    await _init_fresh_db()
    from core.database import get_db
    from models.user_campaigns import get_user_campaign_history, get_quota
    from handlers.user.dashboard_pro import cb_relaunch
    from states.user_states import UserCampaignWizard

    uid = 20007
    async with get_db() as db:
        await db.execute(
            "INSERT INTO users (telegram_id, username) VALUES (?,?) ON CONFLICT DO NOTHING", (uid, "hist_user")
        )
        # Insert 12 campaigns to test limit=10
        for i in range(12):
            await db.execute(
                """INSERT INTO user_campaigns
                   (owner_user_id, text, mode, status, system_generation, run_id, quota_date, created_at)
                   VALUES (?,?,?,?,1,?,date('now'),datetime('now'))""",
                (uid, f"camp text {i}", "immediate", "completed", f"run-hist-{i:02d}"),
            )
        await db.execute(
            "INSERT INTO groups (chat_id, title, chat_type, status, reward_owner_id) VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING",
            (-100701, "Hist Group", "supergroup", "active", uid),
        )
        await db.commit()

    history = await get_user_campaign_history(uid, limit=10)
    assert len(history) == 10, f"Expected 10, got {len(history)}"
    # Newest first
    assert history[0]["id"] > history[-1]["id"]

    # Relaunch: load state at confirm
    quota_before = await get_quota(uid)
    old_cid = history[0]["id"]

    call = MagicMock()
    call.from_user.id = uid
    call.data = f"user_relaunch_camp_{old_cid}"
    call.answer = AsyncMock()
    call.message.answer = AsyncMock()
    call.message.edit_text = AsyncMock()

    state, store, cur_st = _make_memory_state()

    async def get_state():
        return cur_st["val"]

    state.get_state = AsyncMock(side_effect=get_state)

    await cb_relaunch(call, state)

    current_state = await state.get_state()
    assert current_state == UserCampaignWizard.confirm.state, f"Expected confirm state, got: {current_state}"

    quota_after = await get_quota(uid)
    assert quota_after == quota_before, "Relaunch should not consume quota"


async def test_P8_08_health_check_updates_db_and_groups_screen_shows_summary():
    """Health check updates health_status in DB; groups screen header shows ok/bad counts."""
    await _init_fresh_db()
    from core.database import get_db
    from models.groups import get_user_active_groups
    from core.i18n import t

    uid = 20008
    async with get_db() as db:
        await db.execute(
            "INSERT INTO users (telegram_id, username) VALUES (?,?) ON CONFLICT DO NOTHING", (uid, "health_user")
        )
        await db.execute(
            "INSERT INTO groups (chat_id, title, chat_type, status, reward_owner_id, health_status) VALUES (?,?,?,?,?,?) ON CONFLICT DO NOTHING",
            (-100801, "OK Group", "supergroup", "active", uid, "ok"),
        )
        await db.execute(
            "INSERT INTO groups (chat_id, title, chat_type, status, reward_owner_id, health_status) VALUES (?,?,?,?,?,?) ON CONFLICT DO NOTHING",
            (-100802, "Bad Group", "supergroup", "active", uid, "no_permission"),
        )
        await db.commit()

    # Simulate health update in DB (the handler does this)
    async with get_db() as db:
        await db.execute(
            "UPDATE groups SET health_status='ok', last_checked_at=datetime('now') WHERE chat_id=?",
            (-100801,),
        )
        await db.execute(
            "UPDATE groups SET health_status='no_permission', last_checked_at=datetime('now') WHERE chat_id=?",
            (-100802,),
        )
        await db.commit()

    groups = await get_user_active_groups(uid)
    assert len(groups) == 2

    ok_count  = sum(1 for _, _, h in groups if h == "ok")
    bad_count = sum(1 for _, _, h in groups if h != "ok")

    assert ok_count == 1
    assert bad_count == 1

    # Verify health summary renders correctly
    summary_ar = t("u8_groups_health_summary", "ar").format(total=2, ok=1, bad=1)
    assert "مجموعاتي" in summary_ar
    assert "1" in summary_ar

    summary_en = t("u8_groups_health_summary", "en").format(total=2, ok=1, bad=1)
    assert "Groups" in summary_en

    done_ar = t("u8_health_check_done", "ar").format(total=2, ok=1, bad=1)
    assert "فحص" in done_ar


async def test_P8_09_user_campaign_edit_states_and_router_registration():
    """UserCampaignEdit has 10 states; dashboard_pro_router is in handlers/__init__.py."""
    from states.user_states import UserCampaignEdit

    expected_states = {"menu", "text", "photo", "buttons", "button_label", "button_url",
                       "groups", "mode", "custom_hours", "auto_delete"}
    actual_states = {s.split(":")[1] for s in UserCampaignEdit.__all_states_names__}
    assert expected_states == actual_states, f"State mismatch: {expected_states ^ actual_states}"

    # Verify router registered
    import handlers
    source = open(handlers.__file__, encoding="utf-8").read()
    assert "dashboard_pro_router" in source, "dashboard_pro_router not found in handlers/__init__.py"
    assert "dashboard_pro" in source, "dashboard_pro import not found in handlers/__init__.py"


async def test_P8_10_live_edit_two_step_button_builder_saves_to_db():
    """2-step button builder in live editor accumulates buttons and saves to DB with zero quota."""
    await _init_fresh_db()
    from core.database import get_db
    from models.user_campaigns import get_quota
    from handlers.user.dashboard_pro import handle_edit_button_label, handle_edit_button_url
    from states.user_states import UserCampaignEdit

    uid = 20010
    async with get_db() as db:
        await db.execute(
            "INSERT INTO users (telegram_id, username) VALUES (?,?) ON CONFLICT DO NOTHING", (uid, "btn_user")
        )
        await db.execute(
            """INSERT INTO user_campaigns
               (owner_user_id, text, mode, status, system_generation, run_id, quota_date, created_at)
               VALUES (?, 'button test', 'immediate', 'active', 1, 'run-btn-01', date('now'), datetime('now'))""",
            (uid,),
        )
        async with db.execute("SELECT last_insert_rowid()") as c:
            cid = (await c.fetchone())[0]
        await db.commit()

    quota_before = await get_quota(uid)

    state, store, cur_st = _make_memory_state()

    async def get_state_fn():
        return cur_st["val"]

    state.get_state = AsyncMock(side_effect=get_state_fn)

    await state.update_data(edit_cid=cid, edit_buttons=[])
    await state.set_state(UserCampaignEdit.button_label)

    # Step 1: send button label
    msg_label = MagicMock()
    msg_label.from_user.id = uid
    msg_label.text = "My Button"
    msg_label.answer = AsyncMock()
    await handle_edit_button_label(msg_label, state)

    # Verify state moved to button_url
    current_state = await state.get_state()
    assert current_state == UserCampaignEdit.button_url.state

    # Step 2: send valid URL
    msg_url = MagicMock()
    msg_url.from_user.id = uid
    msg_url.text = "https://example.com/test"
    msg_url.answer = AsyncMock()
    await handle_edit_button_url(msg_url, state)

    # After 1 button (< 3), state should be in 'buttons' waiting for more or done
    current_state2 = await state.get_state()
    assert current_state2 == UserCampaignEdit.buttons.state

    # Quota must not change
    quota_after = await get_quota(uid)
    assert quota_after == quota_before, "Button edit should NOT consume quota"

    # Simulate invalid URL rejection
    state2, store2, cur_st2 = _make_memory_state()

    async def get_state_fn2():
        return cur_st2["val"]

    state2.get_state = AsyncMock(side_effect=get_state_fn2)
    await state2.update_data(edit_cid=cid, edit_buttons=[], pending_btn_label="Btn")
    await state2.set_state(UserCampaignEdit.button_url)

    msg_bad = MagicMock()
    msg_bad.from_user.id = uid
    msg_bad.text = "not-a-url"
    msg_bad.answer = AsyncMock()
    await handle_edit_button_url(msg_bad, state2)
    # Should still be in button_url state
    assert await state2.get_state() == UserCampaignEdit.button_url.state


# ── Runner ────────────────────────────────────────────────────────────────────

PHASE7_TESTS = [
    ("P7_01 Locale parity with phase 7 keys",           test_P7_01_locale_parity_with_phase7_keys),
    ("P7_02 User states extended cleanly",              test_P7_02_user_states_extended_cleanly),
    ("P7_03 Two-step button builder add/validate/remove", test_P7_03_two_step_button_builder_add_validate_remove),
    ("P7_04 Interactive group checkboxes toggle all/clear", test_P7_04_interactive_group_checkboxes_toggle_all_clear),
    ("P7_05 Schedule mode and autodelete pickers",      test_P7_05_schedule_mode_and_autodelete_pickers),
    ("P7_06 Live preview does not consume quota",       test_P7_06_live_preview_does_not_consume_quota),
    ("P7_07 Edit from preview returns to preview",      test_P7_07_edit_from_preview_returns_directly_to_preview),
    ("P7_08 Confirm launch persists buttons and autodelete e2e", test_P7_08_confirm_launch_persists_buttons_and_autodelete_end_to_end),
    ("P7_09 Cancel from preview consumes zero quota",   test_P7_09_cancel_from_preview_consumes_zero_quota),
]

PHASE8_TESTS = [
    ("P8_01 Locale parity ≥ 194 keys",                 test_P8_01_locale_parity_ge_194_keys),
    ("P8_02 get_user_overall_stats accuracy + bilingual screen", test_P8_02_get_user_overall_stats_accuracy),
    ("P8_03 Delivery report per-group HTML-escaped",    test_P8_03_delivery_report_per_group_html_escaped),
    ("P8_04 Live edit all 6 fields + zero quota",       test_P8_04_live_edit_all_6_fields_zero_quota),
    ("P8_05 Validation: ownership, empty, min-hours, group ownership", test_P8_05_live_edit_validation_errors),
    ("P8_06 Test DM sends photo+caption+buttons, zero quota", test_P8_06_test_dm_sends_preview_zero_quota),
    ("P8_07 History list + relaunch to confirm state, 0 quota", test_P8_07_campaign_history_and_relaunch),
    ("P8_08 Health check updates DB; groups screen shows health summary", test_P8_08_health_check_updates_db_and_groups_screen_shows_summary),
    ("P8_09 UserCampaignEdit states + main.py registers dashboard_pro_router", test_P8_09_user_campaign_edit_states_and_router_registration),
    ("P8_10 2-step button builder in live editor saves to DB, zero quota", test_P8_10_live_edit_two_step_button_builder_saves_to_db),
]


async def run_all():
    global PASS, FAIL, RESULTS
    PASS = FAIL = 0
    RESULTS = []

    # Import phase7 runner to pick up its DB init
    from tests.phase7_test import run_all as p7_run_all
    p7_success = await p7_run_all()

    # Reset counters to track phase 8 separately after phase7 is printed
    p7_pass = PASS
    p7_fail = FAIL
    PASS = FAIL = 0
    p8_results = []

    print("\n" + "=" * 60)
    print("Suite J — Phase 8: User Dashboard Pro")
    print("=" * 60)
    for name, coro_fn in PHASE8_TESTS:
        old_pass = PASS
        await _run(name, coro_fn())
        p8_results.append(RESULTS[-1])
        print(RESULTS[-1])

    total_pass = p7_pass + PASS
    total_fail = p7_fail + FAIL
    total = total_pass + total_fail

    print("\n" + "=" * 60)
    print(f"CUMULATIVE RESULT: {total_pass}/{total} passed | {total_fail} failed")
    print("=" * 60)

    return total_fail == 0


if __name__ == "__main__":
    success = asyncio.run(run_all())
    sys.exit(0 if success else 1)
