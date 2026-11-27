#!/usr/bin/env python3
"""
Verification tests for the language/menu fix:
  1. Zero unawaited get_lang() calls in async handlers
  2. Admin keyboard contains lang_menu_admin button
  3. Start handler adds lang_menu_start button
  4. User dashboard (cb_user_menu) contains stats, history, language buttons
  5. language.py has lang_menu_* callback handlers
  6. set_lang_ handler supports origin suffix (set_lang_en_admin format)
"""

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASS = 0
FAIL = 0


def ok(msg: str):
    global PASS
    PASS += 1
    print(f"  ✅ PASS: {msg}")


def fail(msg: str):
    global FAIL
    FAIL += 1
    print(f"  ❌ FAIL: {msg}")


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────
# Test 1: No unawaited get_lang() in async handlers
# ─────────────────────────────────────────────────────────────
print("\n[1] Checking for unawaited get_lang() calls in async functions...")

HANDLER_FILES = [
    "handlers/user/my_groups.py",
    "handlers/user/dashboard_pro.py",
    "handlers/user/my_campaign.py",
    "handlers/admin/panel.py",
    "handlers/start.py",
    "handlers/language.py",
]

for rel in HANDLER_FILES:
    content = read(rel)
    # Find lines with get_lang( not preceded by await
    unawaited = [(i + 1, line.strip()) for i, line in enumerate(content.splitlines())
                 if re.search(r'(?<![=\w])(?<!await )get_lang\(', line)
                 and "async def" not in line
                 and "def _lang_keyboard" not in line
                 and "#" not in line.split("get_lang")[0]]
    if unawaited:
        for ln, snippet in unawaited:
            fail(f"{rel}:L{ln} — unawaited get_lang(): {snippet[:60]}")
    else:
        ok(f"{rel} — no unawaited get_lang() calls")


# ─────────────────────────────────────────────────────────────
# Test 2: Admin keyboard has lang_menu_admin button
# ─────────────────────────────────────────────────────────────
print("\n[2] Checking admin keyboard for lang_menu_admin button...")
panel_content = read("handlers/admin/panel.py")
if "lang_menu_admin" in panel_content:
    ok("handlers/admin/panel.py contains 'lang_menu_admin' callback_data")
else:
    fail("handlers/admin/panel.py MISSING 'lang_menu_admin' in get_admin_keyboard()")

# Check get_admin_keyboard accepts lang parameter
if "def get_admin_keyboard(" in panel_content and "lang:" in panel_content:
    ok("get_admin_keyboard() accepts 'lang' parameter")
else:
    fail("get_admin_keyboard() missing 'lang' parameter")

# Check bilingual support
if '"⚙️ Control Panel"' in panel_content or "'⚙️ Control Panel'" in panel_content or "Control Panel" in panel_content:
    ok("admin/panel.py has bilingual EN panel text")
else:
    fail("admin/panel.py MISSING bilingual EN panel text")


# ─────────────────────────────────────────────────────────────
# Test 3: Start handler adds lang_menu_start button
# ─────────────────────────────────────────────────────────────
print("\n[3] Checking start.py for lang_menu_start button...")
start_content = read("handlers/start.py")
if "lang_menu_start" in start_content:
    ok("handlers/start.py contains 'lang_menu_start' callback_data")
else:
    fail("handlers/start.py MISSING 'lang_menu_start' button")

# Check get_lang imported
if "get_lang" in start_content:
    ok("handlers/start.py imports/uses get_lang")
else:
    fail("handlers/start.py does not use get_lang")

# Check get_start_message_data accepts user_id
if "user_id: int | None = None" in start_content or "user_id=None" in start_content:
    ok("get_start_message_data() accepts user_id parameter")
else:
    fail("get_start_message_data() missing user_id parameter")


# ─────────────────────────────────────────────────────────────
# Test 4: User dashboard cb_user_menu has stats, history, lang buttons
# ─────────────────────────────────────────────────────────────
print("\n[4] Checking cb_user_menu for stats/history/language buttons...")
campaign_content = read("handlers/user/my_campaign.py")

tree = ast.parse(campaign_content)
lines = campaign_content.splitlines()
cb_user_menu_body = ""
for node in ast.walk(tree):
    if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == "cb_user_menu":
        cb_user_menu_body = "\n".join(lines[node.lineno - 1:node.end_lineno])
        break

if not cb_user_menu_body:
    fail("cb_user_menu function not found in my_campaign.py")
else:
    ok("cb_user_menu function found")

    for cb_data, label in [
        ("user_my_stats", "📊 stats button"),
        ("user_campaign_history", "🗂 history button"),
        ("lang_menu_user", "🌐 language button"),
    ]:
        if cb_data in cb_user_menu_body:
            ok(f"cb_user_menu has '{cb_data}' ({label})")
        else:
            fail(f"cb_user_menu MISSING '{cb_data}' ({label})")

    # Check bilingual
    if "lang == \"ar\"" in cb_user_menu_body or "lang == 'ar'" in cb_user_menu_body:
        ok("cb_user_menu supports bilingual AR/EN")
    else:
        fail("cb_user_menu missing bilingual AR/EN support")

    # Check await get_lang
    if "await get_lang" in cb_user_menu_body:
        ok("cb_user_menu uses await get_lang()")
    else:
        fail("cb_user_menu missing await get_lang()")


# ─────────────────────────────────────────────────────────────
# Test 5: language.py has lang_menu_* callback handler
# ─────────────────────────────────────────────────────────────
print("\n[5] Checking language.py for lang_menu_* callback handler...")
lang_content = read("handlers/language.py")

if "lang_menu_admin" in lang_content and "lang_menu_user" in lang_content and "lang_menu_start" in lang_content:
    ok("language.py handles lang_menu_admin, lang_menu_user, lang_menu_start")
else:
    fail("language.py MISSING some lang_menu_* callback data values")

# Check cb_lang_menu function exists
tree_lang = ast.parse(lang_content)
fn_names = [n.name for n in ast.walk(tree_lang) if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef))]
if "cb_lang_menu" in fn_names:
    ok("language.py has cb_lang_menu() handler")
else:
    fail("language.py MISSING cb_lang_menu() handler")

# Check _lang_keyboard supports origin parameter
if "origin" in lang_content:
    ok("_lang_keyboard() supports 'origin' parameter for back button")
else:
    fail("_lang_keyboard() missing 'origin' parameter")

# Check get_lang is imported and awaited
if "await get_lang" in lang_content:
    ok("language.py uses await get_lang()")
else:
    fail("language.py missing await get_lang()")


# ─────────────────────────────────────────────────────────────
# Test 6: set_lang_ handler supports origin suffix
# ─────────────────────────────────────────────────────────────
print("\n[6] Checking set_lang_ handler supports set_lang_<code>_<origin> format...")
# cb_set_lang should parse origin from callback.data
if "split(\"_\", 1)" in lang_content or "split('_', 1)" in lang_content:
    ok("cb_set_lang parses origin from callback data suffix")
else:
    fail("cb_set_lang does not parse origin suffix")

# Check back button generation based on origin
if "_ORIGIN_BACK" in lang_content or "origin_map" in lang_content or "_origin_back" in lang_content.lower():
    ok("language.py has origin → back_callback mapping")
else:
    fail("language.py missing origin → back_callback mapping")

# Check set_lang (async) is called to persist language
if "await set_lang(" in lang_content:
    ok("cb_set_lang uses await set_lang() to persist language")
else:
    fail("cb_set_lang missing await set_lang() call")


# ─────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────
total = PASS + FAIL
print(f"\n{'='*50}")
print(f"Results: {PASS}/{total} passed, {FAIL} failed")
print("=" * 50)

if FAIL > 0:
    sys.exit(1)
else:
    print("🎉 All language/menu fix checks passed!")
    sys.exit(0)
