#!/usr/bin/env python3
"""Verify all 5 user dashboard bug fixes end-to-end."""

import asyncio
import json
import os
import sys
import tempfile
import unittest.mock as mock
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DB_NAME"] = _tmp.name
os.environ["ADMIN_ID"] = "999999"
os.environ["BOT_TOKEN"] = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
os.environ["BOT_USERNAME"] = "testbot"


async def run_checks():
    from core.database import init_db, get_db
    from core.i18n import set_lang
    from models.groups import upsert_group
    from models.settings import set_setting
    from models.user_campaigns import get_user_campaign_history
    from services.user_broadcast import create_user_campaign
    from handlers.user.my_campaign import _p7_validate_single_button
    from handlers.user.dashboard_pro import cb_my_stats, cb_campaign_history, cb_relaunch

    await init_db()
    await set_setting("user_campaigns_enabled", "true")

    uid = 909001
    g1 = -100909001
    await set_lang(uid, "ar")
    await upsert_group(g1, "Test Group 1", "supergroup", added_by=uid)

    # ── Fix 4: _p7_validate_single_button uses correct schema ─────────────────
    assert _p7_validate_single_button("قناتنا", "https://t.me/mychannel") == (True, None), \
        "Should accept https://t.me links"
    assert _p7_validate_single_button("الموقع", "http://example.com/page?a=1") == (True, None), \
        "Should accept http:// links"
    assert _p7_validate_single_button("مباشر", "tg://resolve?domain=telegram") == (True, None), \
        "Should accept tg:// links"
    ok, reason = _p7_validate_single_button("خطأ", "not-a-link")
    assert ok is False, "Should reject non-URL"
    ok2, _ = _p7_validate_single_button("خطأ", "https://bad url.com")
    assert ok2 is False, "Should reject URL with space"
    print("  PASS Fix-4: _p7_validate_single_button accepts valid https/http/tg URLs, rejects invalid")

    # Create a campaign with buttons
    btns_json = json.dumps([[{"label": "اشترك", "url": "https://t.me/testchan"}]])
    cid, err = await create_user_campaign(
        user_id=uid,
        text="حملة اختبار",
        photo_file_id=None,
        buttons_json=btns_json,
        target_chat_ids=[g1],
        mode="recurring",
        repeat_hours=6,
    )
    assert cid and not err, f"Campaign creation failed: {err}"

    # Insert delivery records with realistic status values (attempted_at is NOT NULL)
    async with get_db() as db:
        await db.execute(
            "INSERT INTO user_campaign_deliveries (campaign_id, run_id, chat_id, status, attempted_at) VALUES (?, 'r1', ?, 'sent_confirmed', datetime('now'))",
            (cid, g1),
        )
        await db.execute(
            "INSERT INTO user_campaign_deliveries (campaign_id, run_id, chat_id, status, attempted_at) VALUES (?, 'r1', ?, 'failed_permanent', datetime('now'))",
            (cid, -100909002),
        )
        await db.commit()

    # ── Fix 5: History aggregates sent_confirmed/failed_permanent & returns buttons_json ──
    hist = await get_user_campaign_history(uid, limit=10)
    assert len(hist) == 1, f"Expected 1 campaign, got {len(hist)}"
    assert hist[0]["sent_ok"] == 1, f"Expected sent_ok=1, got {hist[0]['sent_ok']}"
    assert hist[0]["sent_fail"] == 1, f"Expected sent_fail=1, got {hist[0]['sent_fail']}"
    assert hist[0]["buttons_json"] == btns_json, "buttons_json should be returned"
    assert "auto_delete_seconds" in hist[0], "auto_delete_seconds should be in result"
    print("  PASS Fix-5: get_user_campaign_history counts sent_confirmed/failed_permanent & returns buttons_json")

    # ── Fix 1: cb_my_stats attaches reply_markup with Back button ─────────────
    call_stats = mock.MagicMock()
    call_stats.from_user.id = uid
    call_stats.answer = mock.AsyncMock()
    call_stats.message.edit_text = mock.AsyncMock()
    await cb_my_stats(call_stats)
    edit_kwargs = call_stats.message.edit_text.call_args[1]
    stats_kb = edit_kwargs.get("reply_markup")
    assert stats_kb is not None, "cb_my_stats must attach reply_markup!"
    stats_cbs = [b.callback_data for r in stats_kb.inline_keyboard for b in r]
    assert "user_menu" in stats_cbs, f"Missing user_menu Back button in cb_my_stats! Got: {stats_cbs}"
    assert "user_campaign_history" in stats_cbs, f"Missing history button in cb_my_stats! Got: {stats_cbs}"
    print("  PASS Fix-1: cb_my_stats includes Back (user_menu) + History buttons")

    # ── Fix 2: cb_campaign_history Back -> user_menu, NOT user_my_stats ───────
    call_hist = mock.MagicMock()
    call_hist.from_user.id = uid
    call_hist.answer = mock.AsyncMock()
    call_hist.message.edit_text = mock.AsyncMock()
    await cb_campaign_history(call_hist)
    hist_kb = call_hist.message.edit_text.call_args[1]["reply_markup"]
    hist_cbs = [b.callback_data for r in hist_kb.inline_keyboard for b in r]
    assert "user_menu" in hist_cbs, f"cb_campaign_history Back must point to user_menu, got: {hist_cbs}"
    assert "user_my_stats" not in hist_cbs, f"cb_campaign_history must NOT point to user_my_stats, got: {hist_cbs}"
    print("  PASS Fix-2: cb_campaign_history Back button -> user_menu (not user_my_stats)")

    # ── Fix 3: cb_relaunch populates target_chat_ids, buttons_list, auto_delete ──
    store = {}
    state = mock.MagicMock()
    state.update_data = mock.AsyncMock(side_effect=lambda **kw: store.update(kw))
    state.get_data = mock.AsyncMock(side_effect=lambda: dict(store))
    state.set_state = mock.AsyncMock()
    state.clear = mock.AsyncMock(side_effect=lambda: store.clear())

    call_rel = mock.MagicMock()
    call_rel.from_user.id = uid
    call_rel.data = f"user_relaunch_camp_{cid}"
    call_rel.answer = mock.AsyncMock()
    call_rel.message.answer = mock.AsyncMock()
    await cb_relaunch(call_rel, state)

    assert store.get("target_chat_ids") == [g1], \
        f"target_chat_ids must be set, got: {store.get('target_chat_ids')}"
    assert store.get("buttons_list") == [{"text": "اشترك", "url": "https://t.me/testchan"}], \
        f"buttons_list mismatch: {store.get('buttons_list')}"
    assert "auto_delete_seconds" in store, "auto_delete_seconds must be set in state"

    # Verify Cancel button appears in relaunch keyboard
    answer_kwargs = call_rel.message.answer.call_args[1]
    relaunch_kb = answer_kwargs.get("reply_markup")
    relaunch_flat = [b.callback_data for r in relaunch_kb.inline_keyboard for b in r]
    assert "ucw_cancel_wizard" in relaunch_flat, f"Cancel button missing in relaunch KB: {relaunch_flat}"
    print("  PASS Fix-3: cb_relaunch sets target_chat_ids, buttons_list, auto_delete, Cancel button")

    print("\nALL 5 USER DASHBOARD BUG FIXES VERIFIED!")


if __name__ == "__main__":
    try:
        asyncio.run(run_checks())
    finally:
        try:
            os.unlink(_tmp.name)
        except OSError:
            pass
