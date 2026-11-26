#!/usr/bin/env python3
"""
Phase 7 Implementation Script — Deploy Links Bot
Implements the upgraded bilingual Interactive User Campaign Wizard.
This script documents what was directly applied. Run:
    python tests/phase7_test.py
to verify all 75 cumulative tests pass.
"""
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

def check():
    print("Phase 7 — Interactive User Campaign Wizard — Artifact Check")
    print("=" * 60)
    checks = [
        ("locales/ar.py", "uc_step1_text_prompt"),
        ("locales/en.py", "uc_step1_text_prompt"),
        ("states/user_states.py", "button_label"),
        ("handlers/user/my_campaign.py", "# ── Phase 7 Interactive User Campaign Wizard"),
        ("tests/phase7_test.py", "test_P7_09"),
    ]
    all_ok = True
    for rel, needle in checks:
        p = ROOT / rel
        if p.exists():
            found = needle in p.read_text(encoding="utf-8")
            status = "✅" if found else "❌ NOT FOUND"
            print(f"  {status}  '{needle[:45]}' in {rel}")
            if not found:
                all_ok = False
        else:
            print(f"  ❌ MISSING  {rel}")
            all_ok = False
    print()
    if all_ok:
        print("✅ Phase 7 artifacts verified. Run: python tests/phase7_test.py")
    else:
        print("❌ Some Phase 7 artifacts are missing.")
    return all_ok

if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        print("[--dry-run] Checking Phase 7 artifacts.\n")
    ok = check()
    sys.exit(0 if ok else 1)
