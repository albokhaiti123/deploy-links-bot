"""
Tests for user campaigns system.
Tests run entirely against a temp SQLite DB — no Telegram API calls.
"""

import asyncio
import json
import sys
import os
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use a temp file DB (aiosqlite opens new connections, :memory: doesn't share state)
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
TEST_DB = _tmp_db.name

os.environ["DB_NAME"] = TEST_DB
os.environ["ADMIN_ID"] = "999999"
os.environ["BOT_TOKEN"] = "0:test"
os.environ["BOT_USERNAME"] = "testbot"
os.environ["QUOTA_TIMEZONE"] = "UTC"

ADMIN_ID = 999999
USER_A = 111111
USER_B = 222222



async def setup_db():
    from core.database import init_db
    await init_db()


async def _create_campaign(user_id, text="Hello", mode="immediate", repeat_hours=0, groups=None):
    from services.user_broadcast import create_user_campaign
    groups = groups or [100, 200]
    cid, err = await create_user_campaign(
        user_id=user_id,
        text=text,
        photo_file_id=None,
        buttons_json=None,
        target_chat_ids=groups,
        mode=mode,
        repeat_hours=repeat_hours,
    )
    return cid, err


async def _add_group(chat_id, user_id, title="Test Group"):
    from models.groups import upsert_group
    await upsert_group(chat_id, title, "group", added_by=user_id)


async def _make_user_own_group(chat_id, user_id):
    """Directly set reward_owner_id for testing."""
    from core.database import get_db
    async with get_db() as db:
        await db.execute(
            "INSERT INTO groups (chat_id, title, chat_type, status, added_at, updated_at, reward_owner_id, added_by) "
            "VALUES (?,?,?,?,datetime('now'),datetime('now'),?,?) "
            "ON CONFLICT(chat_id) DO UPDATE SET reward_owner_id=?",
            (chat_id, f"Group{chat_id}", "group", "active", user_id, user_id, user_id)
        )
        await db.commit()


async def _enable_feature():
    from models.settings import set_setting
    await set_setting("user_campaigns_enabled", "true")


async def _insert_user(user_id):
    from core.database import get_db
    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username, first_name, created_at) VALUES (?,?,?,datetime('now'))",
            (user_id, f"user{user_id}", f"User{user_id}")
        )
        await db.commit()


# ── Tests ────────────────────────────────────────────────────────────────────

async def test_01_quota_two_per_day():
    """Create 2 campaigns → allowed. 3rd → rejected."""
    await _insert_user(USER_A)
    await _make_user_own_group(100, USER_A)
    await _make_user_own_group(200, USER_A)
    await _enable_feature()

    cid1, err1 = await _create_campaign(USER_A, "Camp 1")
    assert cid1 is not None, f"Campaign 1 failed: {err1}"

    cid2, err2 = await _create_campaign(USER_A, "Camp 2")
    assert cid2 is not None, f"Campaign 2 failed: {err2}"

    cid3, err3 = await _create_campaign(USER_A, "Camp 3")
    assert cid3 is None, "Campaign 3 should have been rejected (quota)"
    assert "daily" in err3.lower() or "limit" in err3.lower(), f"Wrong error: {err3}"
    print("  PASS test_01_quota_two_per_day")


async def test_02_quota_not_restored_on_delete():
    """Delete campaign → quota unchanged."""
    from models.user_campaigns import get_quota, _today, update_campaign_status, get_current_campaign
    # USER_B starts fresh
    await _insert_user(USER_B)
    await _make_user_own_group(300, USER_B)
    await _make_user_own_group(400, USER_B)
    await _enable_feature()

    cid, err = await _create_campaign(USER_B, "B Camp", groups=[300, 400])
    assert cid is not None, f"Failed: {err}"

    q_before = await get_quota(USER_B, _today())
    assert q_before == 1

    await update_campaign_status(cid, "deleted")

    q_after = await get_quota(USER_B, _today())
    assert q_after == 1, f"Quota should still be 1 after delete, got {q_after}"
    print("  PASS test_02_quota_not_restored_on_delete")


async def test_03_replacement_consumes_quota():
    """Creating a new campaign when one exists consumes quota (replacement = new creation)."""
    USER_C = 333333
    await _insert_user(USER_C)
    await _make_user_own_group(500, USER_C)
    await _make_user_own_group(600, USER_C)
    await _enable_feature()

    from models.user_campaigns import get_quota, _today, get_current_campaign

    cid1, err1 = await _create_campaign(USER_C, "C Camp 1", groups=[500, 600])
    assert cid1 is not None, f"Camp1 failed: {err1}"

    q1 = await get_quota(USER_C, _today())
    assert q1 == 1

    # Replace — should consume quota
    cid2, err2 = await _create_campaign(USER_C, "C Camp 2", groups=[500])
    assert cid2 is not None, f"Camp2 replacement failed: {err2}"

    q2 = await get_quota(USER_C, _today())
    assert q2 == 2, f"Quota should be 2 after replacement, got {q2}"

    # Old campaign should be replaced
    current = await get_current_campaign(USER_C)
    assert current is not None
    assert current["id"] == cid2, "Current campaign should be the new one"
    print("  PASS test_03_replacement_consumes_quota")


async def test_04_one_active_campaign_per_user():
    """Partial unique index prevents two current campaigns for same user."""
    USER_D = 444444
    await _insert_user(USER_D)
    await _make_user_own_group(700, USER_D)
    await _enable_feature()

    from models.user_campaigns import get_current_campaign

    cid1, _ = await _create_campaign(USER_D, "D1", groups=[700])
    assert cid1 is not None

    # Try to directly insert a second active row — should fail index
    from core.database import get_db
    violated = False
    async with get_db() as db:
        try:
            await db.execute(
                "INSERT INTO user_campaigns (owner_user_id, text, target_groups_json, mode, "
                "status, system_generation, created_at, quota_date) VALUES (?,?,?,?,?,?,datetime('now'),?)",
                (USER_D, "D2 direct", "[]", "immediate", "active", 1, "2099-01-01")
            )
            await db.commit()
        except Exception as e:
            if "UNIQUE" in str(e).upper():
                violated = True

    assert violated, "Partial unique index should have prevented second active campaign"
    print("  PASS test_04_one_active_campaign_per_user")


async def test_05_reward_owner_preserved_on_readd():
    """Re-adding bot by different user does NOT change reward_owner_id."""
    from models.groups import upsert_group
    from core.database import get_db

    await upsert_group(800, "Group800", "group", added_by=USER_A)

    async with get_db() as db:
        async with db.execute("SELECT reward_owner_id FROM groups WHERE chat_id=800") as c:
            row = await c.fetchone()
    original_owner = row[0] if row else None
    assert original_owner == USER_A, f"Initial reward_owner_id should be USER_A, got {original_owner}"

    # Re-add by USER_B
    await upsert_group(800, "Group800 Updated", "supergroup", added_by=USER_B)

    async with get_db() as db:
        async with db.execute("SELECT reward_owner_id, added_by FROM groups WHERE chat_id=800") as c:
            row = await c.fetchone()

    assert row[0] == USER_A, f"reward_owner_id must stay USER_A after re-add, got {row[0]}"
    assert row[1] == USER_B, f"added_by should update to USER_B, got {row[1]}"
    print("  PASS test_05_reward_owner_preserved_on_readd")


async def test_06_user_cannot_access_other_groups():
    """User can only see groups where reward_owner_id == user_id."""
    from models.groups import get_user_active_groups
    await _make_user_own_group(900, USER_A)
    await _make_user_own_group(901, USER_B)

    groups_a = await get_user_active_groups(USER_A)
    ids_a = [g[0] for g in groups_a]
    assert 900 in ids_a, "USER_A should see group 900"
    assert 901 not in ids_a, "USER_A must NOT see group 901 (owned by USER_B)"

    groups_b = await get_user_active_groups(USER_B)
    ids_b = [g[0] for g in groups_b]
    assert 901 in ids_b, "USER_B should see group 901"
    assert 900 not in ids_b, "USER_B must NOT see group 900 (owned by USER_A)"
    print("  PASS test_06_user_cannot_access_other_groups")


async def test_07_user_cannot_target_others_groups():
    """create_user_campaign rejects groups not owned by user."""
    await _insert_user(USER_A)
    await _make_user_own_group(1000, USER_A)
    await _make_user_own_group(1001, USER_B)
    await _enable_feature()

    # USER_A tries to target USER_B's group
    cid, err = await _create_campaign(USER_A, "Attack", groups=[1001])
    assert cid is None, "Should fail — group 1001 belongs to USER_B"
    assert "not belong" in err.lower() or "not authorized" in err.lower() or "do not belong" in err.lower(), f"Wrong error: {err}"
    print("  PASS test_07_user_cannot_target_others_groups")


async def test_08_feature_disabled_blocks_creation():
    """When user_campaigns_enabled=false, creation is blocked."""
    from models.settings import set_setting
    await set_setting("user_campaigns_enabled", "false")

    USER_E = 555555
    await _insert_user(USER_E)
    await _make_user_own_group(1100, USER_E)

    cid, err = await _create_campaign(USER_E, "Blocked", groups=[1100])
    assert cid is None, "Should fail when feature disabled"
    assert "disabled" in err.lower(), f"Wrong error: {err}"

    await set_setting("user_campaigns_enabled", "true")
    print("  PASS test_08_feature_disabled_blocks_creation")


async def test_09_recurring_minimum_6_hours():
    """Recurring campaigns with < 6h interval are rejected at service layer."""
    USER_F = 666666
    await _insert_user(USER_F)
    await _make_user_own_group(1200, USER_F)
    await _enable_feature()

    cid, err = await _create_campaign(USER_F, "Too frequent", mode="recurring", repeat_hours=3, groups=[1200])
    assert cid is None, "Should reject < 6h interval"
    assert "6" in err, f"Wrong error: {err}"

    cid2, err2 = await _create_campaign(USER_F, "OK", mode="recurring", repeat_hours=6, groups=[1200])
    assert cid2 is not None, f"6h should be allowed: {err2}"
    print("  PASS test_09_recurring_minimum_6_hours")


async def test_10_generation_fencing():
    """Campaigns created before generation increment are invalidated."""
    from models.user_campaigns import get_campaign_by_id, _today
    from models.settings import set_setting, get_setting
    from core.database import get_db

    USER_G = 777777
    await _insert_user(USER_G)
    await _make_user_own_group(1300, USER_G)
    await set_setting("user_campaigns_enabled", "true")

    gen_before = int(await get_setting("user_campaigns_generation"))

    # Create campaign with current generation
    cid, err = await _create_campaign(USER_G, "Gen test", groups=[1300])
    assert cid is not None, f"Failed: {err}"
    c = await get_campaign_by_id(cid)
    assert c["system_generation"] == gen_before

    # Simulate owner disabling (increments generation)
    await set_setting("user_campaigns_generation", str(gen_before + 1))
    new_gen = int(await get_setting("user_campaigns_generation"))
    assert new_gen == gen_before + 1
    assert c["system_generation"] != new_gen, "Campaign should be stale now"
    print("  PASS test_10_generation_fencing")


async def test_11_quota_not_consumed_without_commit():
    """Wizard abandonment = no DB row = no quota consumed."""
    from models.user_campaigns import get_quota, _today
    USER_H = 888888
    await _insert_user(USER_H)

    q_before = await get_quota(USER_H, _today())
    # No campaign created (wizard abandoned = nothing saved)
    q_after = await get_quota(USER_H, _today())
    assert q_before == q_after == 0, "Quota should be 0 for user who never completed wizard"
    print("  PASS test_11_quota_not_consumed_without_commit")


async def test_12_buttons_validation():
    """Invalid button URLs are rejected."""
    from services.user_broadcast import validate_buttons

    ok, err = validate_buttons(json.dumps([[{"label": "Click", "url": "https://example.com"}]]))
    assert ok, f"Valid button rejected: {err}"

    ok2, err2 = validate_buttons(json.dumps([[{"label": "Bad", "url": "javascript:alert(1)"}]]))
    assert not ok2, "Invalid URL should be rejected"

    ok3, err3 = validate_buttons("not json")
    assert not ok3, "Invalid JSON should be rejected"
    print("  PASS test_12_buttons_validation")


async def run_all_tests():
    await setup_db()
    tests = [
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
            print(f"  ERROR {t.__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed}/{len(tests)} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
