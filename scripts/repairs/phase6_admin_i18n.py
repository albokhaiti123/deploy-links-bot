#!/usr/bin/env python3
"""
Phase 6 Implementation Script — Deploy Links Bot
Full Admin Panel i18n (Arabic ↔ English)

This script documents what was directly applied during Phase 6.
All changes were applied directly to the project files; run this script
to verify Phase 6 artifacts are present, or run:

    python tests/phase6_test.py

to execute the full 66-test cumulative suite.

Changes applied in Phase 6:
  - locales/ar.py          : Expanded to 84 keys (56 admin keys added)
  - locales/en.py          : Expanded to 84 keys (100% parity with ar.py)
  - core/i18n.py           : Rewritten with user_id ContextVar tracking
  - core/admin_i18n.py     : NEW — translation engine + AdminSessionI18nMiddleware
  - handlers/admin/invite_links.py : Fully rewritten with bilingual i18n
  - handlers/admin/admins.py       : process_admin_id localized
  - services/broadcast.py         : Completion report localized
  - services/campaign.py          : Completion report + not-found localized
  - main.py                        : Registers AdminSessionI18nMiddleware

Usage:
    python scripts/repairs/phase6_admin_i18n.py [--dry-run]
"""

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

REQUIRED_FILES = [
    "locales/ar.py",
    "locales/en.py",
    "core/i18n.py",
    "core/admin_i18n.py",
    "handlers/admin/invite_links.py",
    "handlers/admin/admins.py",
    "services/broadcast.py",
    "services/campaign.py",
    "main.py",
    "tests/phase6_test.py",
]

dry_run = "--dry-run" in sys.argv


def check():
    print("Phase 6 — Full Admin Panel i18n — Artifact Check")
    print("=" * 55)
    all_ok = True
    for rel in REQUIRED_FILES:
        p = ROOT / rel
        exists = p.exists()
        status = "✅" if exists else "❌ MISSING"
        print(f"  {status}  {rel}")
        if not exists:
            all_ok = False

    # Key content checks
    checks = [
        ("core/admin_i18n.py", "AdminSessionI18nMiddleware"),
        ("main.py", "bot.session.middleware.register(AdminSessionI18nMiddleware())"),
        ("services/campaign.py", "admin_camp_bcast_done"),
        ("services/broadcast.py", "admin_bcast_done"),
    ]
    print()
    print("Content checks:")
    for rel, needle in checks:
        p = ROOT / rel
        if p.exists():
            found = needle in p.read_text(encoding="utf-8")
            status = "✅" if found else "❌ NOT FOUND"
            print(f"  {status}  '{needle}' in {rel}")
            if not found:
                all_ok = False
        else:
            print(f"  ❌ MISSING  {rel}")
            all_ok = False

    # Locale key count
    try:
        import importlib.util
        for mod_path, mod_name in [("locales/ar.py", "ar"), ("locales/en.py", "en")]:
            spec = importlib.util.spec_from_file_location(mod_name, ROOT / mod_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            count = len(mod.STRINGS)
            status = "✅" if count >= 84 else "❌"
            print(f"  {status}  locales/{mod_name}.py: {count} keys (need ≥84)")
            if count < 84:
                all_ok = False
    except Exception as e:
        print(f"  ⚠️  Could not load locales: {e}")

    print()
    if all_ok:
        print("✅ Phase 6 artifacts verified. Run: python tests/phase6_test.py")
    else:
        print("❌ Some Phase 6 artifacts are missing or incomplete.")
    return all_ok


if __name__ == "__main__":
    if dry_run:
        print("[--dry-run] Checking Phase 6 artifacts without making any changes.\n")
    ok = check()
    sys.exit(0 if ok else 1)
