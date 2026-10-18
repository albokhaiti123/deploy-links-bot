# 03 — Execution Masterplan

## Phase Overview

| Phase | Name | Goal | Dependencies |
|-------|------|------|-------------|
| 1 | Infrastructure | Skeleton, config, DB, logging | None |
| 2 | Data Layer | Models (all CRUD) | Phase 1 |
| 3 | Services | Business logic (promo, broadcast, campaign, media) | Phase 2 |
| 4 | Handlers — Core | start, groups, payments | Phase 3 |
| 5 | Handlers — Admin | Full admin panel (all sub-pages) | Phase 3 |
| 6 | Background Tasks + Main | Tasks, error handler, entry point | Phase 3 |
| 7 | Verification | Syntax, import, structural tests | Phase 4-6 |
| 8 | New Features | Button management, welcome media, previews, back/cancel | Phase 7 |
| 9 | Final Testing | Full integration pass | Phase 8 |
| 10 | Documentation & Deployment | Reports, VPS guide | Phase 9 |

---

## Phase 1: Infrastructure

**Goal:** Create project skeleton with config, database, logging, shared bot instance.

### Tasks:
1. Create directory structure (`core/`, `models/`, `services/`, `handlers/`, `handlers/admin/`, `handlers/campaigns/`, `states/`, `tasks/`, `utils/`).
2. Create all `__init__.py` files.
3. **`core/config.py`** — Load `.env`, export `BOT_TOKEN`, `ADMIN_ID`, `BOT_USERNAME`, `DB_NAME`.
4. **`core/logging_config.py`** — Configure logging (same format as current).
5. **`core/bot.py`** — Create `bot` and `dp` instances.
6. **`core/database.py`** — `init_db()` with all CREATE TABLE statements and ALTER migrations. `get_db()` context manager.
7. **`states/states.py`** — Move `AdminEdit`, `BroadcastWizard`, `CampaignWizard` verbatim.

### Verification:
- All imports resolve.
- `python -c "from core.config import BOT_TOKEN"` works.
- `python -c "from core.bot import bot, dp"` works.
- `python -c "from states.states import AdminEdit"` works.

---

## Phase 2: Data Layer

**Goal:** Extract all database operations into model files.

### Tasks:
1. **`models/settings.py`** — `get_setting()`, `set_setting()`.
2. **`models/admins.py`** — `is_admin()`, `add_admin()`, `remove_admin()`, `list_admins()`.
3. **`models/users.py`** — `upsert_user()`, `get_all_user_ids()`.
4. **`models/groups.py`** — `upsert_group()`, `deactivate_group()`, `get_active_group_ids()`, `get_recent_groups()`, `update_last_promo_msg()`, `get_last_promo_msg()`.
5. **`models/events.py`** — `log_event()`, counts for stats.
6. **`models/broadcasts.py`** — `schedule_delete()`, `get_expired()`, `delete_record()`, recurring broadcast CRUD.
7. **`models/campaigns.py`** — `get_campaign()`, `create_campaign()`, `update_campaign_status()`, progress CRUD, group verification CRUD.

### Verification:
- Each model imports `get_db` from `core.database`.
- No circular imports.
- Compile check passes.

---

## Phase 3: Services

**Goal:** Extract business logic from handlers into service functions.

### Tasks:
1. **`services/media.py`** — `send_media_message(bot, chat_id, text, media_id, media_type, keyboard, parse_mode)`. Handles photo/video/text branching in one place.
2. **`services/promo.py`** — `build_promo_keyboard()`, `get_start_message_data()`, `trigger_group_promo()`. Uses models for DB, `send_media_message` for delivery.
3. **`services/broadcast.py`** — `execute_broadcast()`, recurring broadcast execution logic.
4. **`services/campaign.py`** — `show_campaign_progress()`, `verify_campaign_groups()`, `deliver_unlock_content()`, `execute_campaign_broadcast()`.

### Verification:
- Services only import from `core/`, `models/`, `utils/`.
- Compile check passes.

---

## Phase 4: Handlers — Core

**Goal:** Move user-facing (non-admin) handlers to router files.

### Tasks:
1. **`handlers/start.py`** — Router with `cmd_start`, `cb_start_btn2_click`, `cb_start_back`.
2. **`handlers/payments.py`** — Router with `process_pre_checkout_query`, `process_successful_payment`.
3. **`handlers/groups.py`** — Router with `bot_added_to_group`, `bot_removed_from_group`, `new_chat_member_handler`.
4. **`handlers/campaigns/user.py`** — Router with `cb_camp_verify`, `cb_camp_unlock`.
5. **`handlers/__init__.py`** — `register_all_routers(dp)` function.

### Verification:
- Each router registers handlers using `router.message()`, `router.callback_query()`, etc.
- `register_all_routers(dp)` includes all routers.
- No handler registered twice.

---

## Phase 5: Handlers — Admin

**Goal:** Move all admin handlers to organized router files.

### Tasks:
1. **`handlers/admin/panel.py`** — `cmd_admin`, `cb_admin_main`, `cb_admin_toggle_promo`.
2. **`handlers/admin/promo_settings.py`** — All promo editing handlers (text, media, URL, button, VIP, post-payment, preview, toggle bot button).
3. **`handlers/admin/general_settings.py`** — Settings page, cooldown, auto-delete toggle, welcome toggle, promo delete duration, test group.
4. **`handlers/admin/welcome_settings.py`** — Start message settings page, edit msg, btn2 name/url/text, preview.
5. **`handlers/admin/broadcast.py`** — Full broadcast wizard (target → text → media → VIP → stars → duration → confirm → execute).
6. **`handlers/admin/recurring.py`** — Recurring broadcasts list, start/stop/delete/create.
7. **`handlers/admin/stats.py`** — Stats page, groups list page.
8. **`handlers/admin/admins.py`** — Admin management (add/remove admins).
9. **`handlers/admin/campaigns.py`** — Campaign menu, wizard, admin view, list, stats, publish, test, pause/resume/delete, recurring start/stop.

### Verification:
- All callback_data patterns match original code exactly.
- All FSM state transitions are correct.
- Admin check in every handler.

---

## Phase 6: Background Tasks + Main Entry Point

### Tasks:
1. **`tasks/background.py`** — Move `auto_delete_broadcasts`, `auto_recurring_campaigns`, `auto_recurring_broadcasts`.
2. **`main.py`** — Entry point:
   - Import config
   - Call `init_db()`
   - Register all routers
   - Start background tasks
   - Self-healing polling loop
   - Graceful shutdown
3. **Global error handler** — Register on `dp` in `main.py`.

### Verification:
- `python main.py` starts without errors (with valid .env).
- All background tasks launch.
- Self-healing loop works.

---

## Phase 7: Verification & Testing

### Structural Tests:
1. **Syntax check:** `python -m py_compile main.py` + all modules.
2. **Import check:** `python -c "from handlers import register_all_routers"`.
3. **No duplicate handlers:** Grep for `@router.` patterns, ensure no callback_data is registered twice.
4. **DB compatibility:** Run `init_db()` against existing `bot.db`, verify no data loss.
5. **Callback data audit:** List all callback_data patterns, compare with legacy code.

### What Cannot Be Tested Locally:
- Actual Telegram API calls (require valid bot token + internet).
- FSM flows (require interactive Telegram conversation).
- Background task execution (require running bot + time).
- PM2 deployment (requires VPS).

---

## Phase 8: New Features

> **Only after Phase 7 passes.**

### 8A: Button Management System
1. Create `custom_buttons` table: `id, context (promo/welcome/campaign_<id>), text, url, is_active, position, created_at`.
2. Create `models/custom_buttons.py` — CRUD for buttons.
3. Create `services/buttons.py` — Shared button management logic.
4. Add `handlers/admin/button_manager.py` — Generic 3-step wizard (name → URL → confirm), list, edit, toggle, delete.
5. Integrate into promo settings, welcome settings, campaign admin view.
6. Update `build_promo_keyboard()`, `get_start_message_data()`, campaign broadcast to include active custom buttons.

### 8B: Welcome Media Support
1. Add `start_media_id` and `start_media_type` settings.
2. Add media editing handler in welcome settings.
3. Update `cmd_start` and welcome preview to send media.

### 8C: Campaign Preview
1. Add preview button in campaign admin view.
2. Reuse `send_media_message()` to render exact preview.

### 8D: Back & Cancel System
1. Audit all FSM steps and admin pages.
2. Add `🔙 رجوع` inline button to every input prompt (using `ReplyKeyboardMarkup` or inline).
3. Add `❌ إلغاء` option alongside `/cancel`.
4. Implement state-aware back navigation preserving entered data.

---

## Phase 9: Final Integration Testing

1. Run full syntax + import check.
2. Verify all callback_data patterns exist and are handled.
3. Verify DB schema compatibility.
4. Document what requires manual testing.
5. Create test scenarios document.

---

## Phase 10: Reports & Deployment Guide

1. Write final report artifact.
2. Write VPS update guide with actual paths.
3. Write new-instance setup guide.
4. Commit all changes to `v2-redesign` branch.
5. Push to GitHub.

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Circular imports | Strict one-way import hierarchy (see architecture doc) |
| Missing handler registration | Checklist audit of all callback_data patterns |
| DB schema mismatch | `init_db()` uses CREATE IF NOT EXISTS + ALTER TRY/EXCEPT |
| Different behavior after refactor | No logic changes during refactor, only code movement |
| Lost features | Feature inventory checklist verification |
| PM2 config change | Keep same entry command, just point to `main.py` instead of `bot.py` |
