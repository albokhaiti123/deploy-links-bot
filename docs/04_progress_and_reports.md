# 04 — Progress & Reports

## Phase Status Tracker

| # | Phase | Status | Started | Completed | Notes |
|---|-------|--------|---------|-----------|-------|
| 0 | Revert `30139dd` → `c5da191` | ✅ Done | 2026-10-18 | 2026-10-18 | Commit `af995ed`, pushed to main |
| 1 | Infrastructure | 🔲 Not Started | — | — | |
| 2 | Data Layer | 🔲 Not Started | — | — | |
| 3 | Services | 🔲 Not Started | — | — | |
| 4 | Handlers — Core | 🔲 Not Started | — | — | |
| 5 | Handlers — Admin | 🔲 Not Started | — | — | |
| 6 | Background Tasks + Main | 🔲 Not Started | — | — | |
| 7 | Verification | 🔲 Not Started | — | — | |
| 8 | New Features | 🔲 Not Started | — | — | |
| 9 | Final Testing | 🔲 Not Started | — | — | |
| 10 | Reports & Deployment | 🔲 Not Started | — | — | |

---

## Phase Reports

### Phase 0: Revert Report

**Date:** 2026-10-18  
**Commit reverted:** `30139dd` (feat: custom buttons, media, preview, self-destruct enhancements)  
**Restored to:** `c5da191` (feat: add all 12 post-testing modifications)  
**Method:** `git checkout c5da191 -- bot.py` → new commit `af995ed`  
**Files affected:** `bot.py` only (341 insertions removed, 20 deletions restored)  
**Database impact:** None — the reverted code only read from `settings` table using existing keys; no schema changes were applied to `bot.db`  
**Verification:** `py_compile` passed, pushed to `main` branch  

---

### Phase 1 Report
> *Pending*

### Phase 2 Report
> *Pending*

### Phase 3 Report
> *Pending*

### Phase 4 Report
> *Pending*

### Phase 5 Report
> *Pending*

### Phase 6 Report
> *Pending*

### Phase 7 Report
> *Pending*

### Phase 8 Report
> *Pending*

### Phase 9 Report
> *Pending*

### Phase 10 Report
> *Pending*

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-18 | Keep `aiosqlite` without ORM | Project simplicity, no need for SQLAlchemy overhead |
| 2026-10-18 | Keep `MemoryStorage` for FSM | Only admins use wizards; restart clears in-progress wizards which is acceptable |
| 2026-10-18 | Use aiogram `Router()` for modular handlers | Native aiogram 3.x pattern, avoids circular imports with `dp` |
| 2026-10-18 | Create `custom_buttons` DB table instead of JSON in settings | Proper CRUD, toggle, ordering; JSON blob doesn't support individual button management |
| 2026-10-18 | Separate `services/media.py` for unified message sending | Eliminates 8+ copies of photo/video/text branching throughout the codebase |
| 2026-10-18 | Keep `callback_data` patterns unchanged | Existing users may have open inline keyboards with old data |

---

## Issues & Blockers

| # | Issue | Status | Resolution |
|---|-------|--------|------------|
| — | *None yet* | — | — |
