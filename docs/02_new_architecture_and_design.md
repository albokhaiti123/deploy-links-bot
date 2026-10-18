# 02 — New Architecture & Design

## 1. Design Principles

1. **Module-per-responsibility** — Each file handles one concern.
2. **Shared `bot` and `dp` instances** — Created once in `core/bot.py`, imported everywhere.
3. **Router-based handlers** — Each handler group uses an `aiogram.Router`, registered in `main.py`.
4. **Database manager** — One shared connection pool, no scattered `aiosqlite.connect()`.
5. **Service layer** — Business logic separated from handler code.
6. **Zero behavior change** — The refactored bot must produce identical user/admin experience.

---

## 2. Directory Structure

```
deploy-links-bot/
├── main.py                     # Entry point: init DB, register routers, start polling
├── .env                        # Secrets (unchanged)
├── .env.example                # Template (unchanged)
├── requirements.txt            # Dependencies (unchanged)
├── bot.db                      # SQLite database (unchanged, .gitignored)
├── README.md                   # Project docs (updated)
│
├── core/                       # Framework & infrastructure
│   ├── __init__.py
│   ├── bot.py                  # Bot + Dispatcher + MemoryStorage creation
│   ├── config.py               # Load .env, expose BOT_TOKEN, ADMIN_ID, etc.
│   ├── database.py             # DB manager: init_db(), get_db(), migration
│   └── logging.py              # Logging configuration
│
├── models/                     # Data access (repository pattern)
│   ├── __init__.py
│   ├── settings.py             # get_setting(), set_setting()
│   ├── groups.py               # Group CRUD
│   ├── users.py                # User CRUD
│   ├── admins.py               # Admin check & CRUD
│   ├── events.py               # log_event()
│   ├── broadcasts.py           # broadcast_messages CRUD, recurring_broadcasts CRUD
│   └── campaigns.py            # campaigns, campaign_user_progress, campaign_groups
│
├── services/                   # Business logic
│   ├── __init__.py
│   ├── promo.py                # trigger_group_promo() + build_promo_keyboard()
│   ├── broadcast.py            # execute_broadcast(), recurring broadcast logic
│   ├── campaign.py             # Campaign helpers, verification, unlock, broadcast
│   └── media.py                # send_media_message() — unified photo/video/text sender
│
├── handlers/                   # Telegram update handlers (Routers)
│   ├── __init__.py             # register_all_routers()
│   ├── start.py                # /start, welcome, btn2, back
│   ├── payments.py             # Pre-checkout, successful payment
│   ├── groups.py               # Bot added/removed, new_chat_members
│   ├── admin/
│   │   ├── __init__.py
│   │   ├── panel.py            # /admin, main menu, toggle promo
│   │   ├── promo_settings.py   # Promo text/url/button/media/VIP/preview
│   │   ├── general_settings.py # Cooldown, auto-delete, welcome toggle, promo del, test group
│   │   ├── welcome_settings.py # Start message text, btn2 name/type/content, preview
│   │   ├── broadcast.py        # Broadcast wizard (all steps)
│   │   ├── recurring.py        # Recurring broadcasts CRUD
│   │   ├── stats.py            # Stats + Groups list
│   │   ├── admins.py           # Admin management (add/remove)
│   │   └── campaigns.py        # Campaign wizard, admin view, publish, test, pause/resume/delete, stats, recurring
│   └── campaigns/
│       ├── __init__.py
│       └── user.py             # camp_verify, camp_unlock, show_campaign_progress
│
├── states/                     # FSM state definitions
│   ├── __init__.py
│   └── states.py               # AdminEdit, BroadcastWizard, CampaignWizard
│
├── tasks/                      # Background tasks
│   ├── __init__.py
│   └── background.py           # auto_delete_broadcasts, auto_recurring_campaigns, auto_recurring_broadcasts
│
├── utils/                      # Shared utilities
│   ├── __init__.py
│   └── helpers.py              # get_bot_add_url(), admin check middleware, etc.
│
└── docs/                       # Documentation (this folder)
    ├── 01_project_vision_and_goals.md
    ├── 02_new_architecture_and_design.md
    ├── 03_execution_masterplan.md
    └── 04_progress_and_reports.md
```

---

## 3. Module Responsibilities

### `main.py` — Entry Point
```
- Load config
- Initialize database (create tables, run migrations)
- Create bot & dispatcher (from core/bot.py)
- Register all routers
- Start background tasks
- Start self-healing polling loop
- Graceful shutdown
```

### `core/bot.py` — Shared Instances
```
- bot = Bot(token=...)
- dp = Dispatcher(storage=MemoryStorage())
- Exported for use by all handlers and services
```

### `core/database.py` — Database Manager
```
- init_db(): Create all tables, run column migrations, insert defaults
- get_db(): Async context manager returning aiosqlite connection
- All tables defined in one place
```

### `models/` — Data Access Layer
```
- Each model file wraps SQL queries for one table or table group
- Functions return Python dicts or primitives
- No Telegram-specific logic here
```

### `services/` — Business Logic
```
- promo.py: Builds keyboard, formats text, sends promo with all variants (VIP/free/media)
- broadcast.py: Iterates targets, sends messages, handles errors
- campaign.py: Verification logic, unlock delivery, progress tracking
- media.py: Unified send_media_message(chat_id, text, media_id, media_type, kb) helper
```

### `handlers/` — Routers
```
- Each file creates a Router(), registers handlers on it
- handlers/__init__.py has register_all_routers(dp) that includes all sub-routers
- admin/ handlers check is_admin() at each callback
- Handlers are thin: parse input → call service → send response
```

### `states/states.py` — FSM States
```
- AdminEdit, BroadcastWizard, CampaignWizard
- Identical to current code, just in their own file
```

### `tasks/background.py` — Background Tasks
```
- auto_delete_broadcasts(): Poll broadcast_messages, delete expired
- auto_recurring_campaigns(): Check and execute due campaigns
- auto_recurring_broadcasts(): Check and execute due broadcasts
```

---

## 4. Handler → Module Migration Map

| Current Location (bot.py lines) | New File |
|--------------------------------|----------|
| L1-28 (imports, config, constants) | `core/config.py`, `core/bot.py` |
| L30-200 (init_db, get/set_setting, is_admin) | `core/database.py`, `models/settings.py`, `models/admins.py` |
| L215-216 (cooldown cache) | `services/promo.py` |
| L218-259 (FSM states, Bot/Dp creation) | `states/states.py`, `core/bot.py` |
| L261-296 (helpers, log_event) | `utils/helpers.py`, `models/events.py` |
| L298-409 (trigger_group_promo) | `services/promo.py` |
| L411-428 (auto_delete_broadcasts) | `tasks/background.py` |
| L431-473 (cmd_start, btn2, back) | `handlers/start.py` |
| L476-489 (payments) | `handlers/payments.py` |
| L492-527 (group events) | `handlers/groups.py` |
| L529-578 (admin panel, toggle) | `handlers/admin/panel.py` |
| L580-721 (promo settings) | `handlers/admin/promo_settings.py` |
| L723-811 (promo text/media/url/button handlers) | `handlers/admin/promo_settings.py` |
| L813-1013 (broadcast wizard + execute) | `handlers/admin/broadcast.py`, `services/broadcast.py` |
| L1016-1206 (settings, welcome settings, cooldown) | `handlers/admin/general_settings.py`, `handlers/admin/welcome_settings.py` |
| L1208-1285 (stats, groups) | `handlers/admin/stats.py` |
| L1287-1362 (admin management) | `handlers/admin/admins.py` |
| L1364-1621 (campaign user handlers) | `handlers/campaigns/user.py`, `services/campaign.py` |
| L1624-1907 (campaign admin: menu, wizard, confirm) | `handlers/admin/campaigns.py` |
| L1910-2185 (campaign admin view, list, stats, publish) | `handlers/admin/campaigns.py` |
| L2190-2342 (campaign test, recurring toggle) | `handlers/admin/campaigns.py` |
| L2223-2291 (welcome toggle, promo del, test group) | `handlers/admin/general_settings.py` |
| L2344-2458 (recurring background tasks) | `tasks/background.py` |
| L2460-2580 (recurring broadcast admin) | `handlers/admin/recurring.py` |
| L2582-2627 (error handler, main) | `main.py` |

---

## 5. Data Flow

```
User sends /start
  → handlers/start.py → cmd_start()
    → models/users.py → upsert user
    → models/settings.py → check private_welcome_enabled
    → services/promo.py → get_start_message_data()
    → Send welcome message

New member joins group
  → handlers/groups.py → new_chat_member_handler()
    → services/promo.py → trigger_group_promo()
      → models/settings.py → read all promo settings
      → Check cooldown (in-memory)
      → services/media.py → send_media_message()
      → models/groups.py → update last_promo_msg_id
      → models/events.py → log event

Admin opens /admin
  → handlers/admin/panel.py → cmd_admin()
    → models/settings.py → read promo_enabled
    → Build admin keyboard → Send

Background: auto_delete_broadcasts
  → tasks/background.py → every 60s
    → models/broadcasts.py → get expired messages
    → Delete via Telegram API
    → models/broadcasts.py → remove records
```

---

## 6. Avoiding Circular Imports

The key rule: **`core/` and `models/` never import from `handlers/` or `services/`.**

```
Import hierarchy (one-way only):
  main.py
    ↓
  handlers/* → services/* → models/* → core/*
    ↓                         ↓
  states/*                   utils/*
    ↓
  tasks/* → services/* → models/* → core/*
```

**`core/bot.py`** exports `bot` and `dp`. Everyone imports from there.  
**`core/database.py`** exports `get_db()`. All models import from there.

---

## 7. Key Technical Decisions

| Decision | Rationale |
|----------|-----------|
| Keep `aiosqlite` (no SQLAlchemy) | Minimal change, same performance, project doesn't need ORM complexity |
| Keep `MemoryStorage` for FSM | Only admins use wizards, loss on restart is acceptable |
| Keep `bot` as module-level singleton | aiogram's standard pattern, works well with routers |
| Use `Router()` instead of decorating `dp` directly | Enables clean module separation, aiogram 3.x native approach |
| Keep `last_promo_times` as module dict | Simple, effective, acceptable for single-process bot |
| No middleware for admin check | Keep explicit `is_admin()` calls — clearer, matches existing pattern |
| Keep `callback_data` patterns identical | Existing users/admins may have open keyboards with old callback data |
