# 01 — Project Vision & Goals

## 1. Project Purpose

**Deploy Links Bot** is a Telegram bot that automates promotional messaging in groups. When a new member joins a group where the bot is installed, it sends a promotional message (text, media, or paid content). The bot also provides a campaign system where users must add the bot to a specified number of groups before unlocking exclusive content.

### Core Value Proposition
- **For bot owners:** Grow Telegram groups/channels by leveraging new-member-join events as distribution triggers.
- **For users:** Discover promoted content organically when joining groups.
- **For campaigns:** Create viral group-growth loops — users add the bot to groups to unlock content, generating more promotions.

---

## 2. Complete Feature Inventory (from code analysis)

### A. Promotion System (Group Auto-Promo)
| Feature | Status | Location |
|---------|--------|----------|
| Send promo message on new member join | ✅ | `trigger_group_promo()` L298-409 |
| Text-only, photo, or video promo | ✅ | Same function |
| VIP paid promo (Telegram Stars) | ✅ | Same function, `send_paid_media` / `send_invoice` |
| Customizable promo text with `{user}` mention | ✅ | L329-331 |
| Customizable promo URL button | ✅ | `build_promo_keyboard()` L264-270 |
| Show/hide "Add bot" button on promo | ✅ | Same function |
| Cooldown between promos per group | ✅ | In-memory dict `last_promo_times` L215, L310-313 |
| Auto-delete old promo in group | ✅ | L336-344 |
| Timed self-destruct of promo messages | ✅ | L392-399, uses `broadcast_messages` table |
| Post-payment confirmation message | ✅ | `process_successful_payment()` L480-489 |

### B. Private Welcome Message
| Feature | Status | Location |
|---------|--------|----------|
| Welcome message on `/start` in private chat | ✅ | `cmd_start()` L431-459 |
| Enable/disable private welcome | ✅ | `private_welcome_enabled` setting |
| Customizable welcome text | ✅ | `start_message` setting |
| Extra button (URL or text callback) | ✅ | `start_btn2_*` settings |
| Preview welcome message | ✅ | `cb_admin_preview_start()` L1071-1077 |

### C. Campaign Unlock System
| Feature | Status | Location |
|---------|--------|----------|
| Create campaigns with multi-step wizard (10 steps) | ✅ | `CampaignWizard` L244-255, handlers L1648-1907 |
| Campaign promo text + media | ✅ | Stored in `campaigns` table |
| Configurable required group count (1-50) | ✅ | `required_groups` column |
| User progress tracking with visual bar | ✅ | `show_campaign_progress()` L1384-1465 |
| Group verification via `get_chat_member` API | ✅ | `cb_camp_verify()` L1470-1562 |
| Unlock content delivery (text + media) | ✅ | `cb_camp_unlock()` L1565-1621 |
| Auto-delete unlock content (timed) | ✅ | L1609-1616 |
| Campaign pause/resume/delete | ✅ | L2073-2105 |
| Campaign stats (views, started, groups added, unlocked, delivered) | ✅ | L2019-2068 |
| Manual campaign broadcast (users/groups/all) | ✅ | L2108-2185 |
| Recurring campaign broadcast | ✅ | L2293-2312, `auto_recurring_campaigns()` L2344-2401 |
| Test campaign (send to admin / test group) | ✅ | L2190-2342 |
| Deep link `/start camp_<id>` | ✅ | L444-450 |
| Verify rate-limit (10s cooldown) | ✅ | L1368-1370 |
| Campaign mode: manual or recurring | ✅ | `mode` column |

### D. Broadcast Wizard
| Feature | Status | Location |
|---------|--------|----------|
| Send broadcast to users or groups | ✅ | `BroadcastWizard` L235-242 |
| Text + optional media (photo/video) | ✅ | L836-865 |
| VIP paid media option | ✅ | L867-884 |
| Auto-delete duration selection | ✅ | `ask_duration()` L903-913 |
| Broadcast execution with flood protection | ✅ | `execute_broadcast()` L956-1013 |
| Recurring broadcasts (CRUD + background task) | ✅ | L2403-2580 |

### E. Admin Panel
| Feature | Status | Location |
|---------|--------|----------|
| `/admin` command → main panel | ✅ | L548-566 |
| Promo settings (text, URL, button, media, VIP, preview) | ✅ | L580-721 |
| General settings (cooldown, auto-delete, welcome toggle, promo delete timer, test group) | ✅ | L1016-1051 |
| Welcome message settings (text, extra button name/type/content) | ✅ | L1053-1154 |
| Stats page (users, groups, promos) | ✅ | L1208-1245 |
| Groups list (last 20) | ✅ | L1247-1285 |
| Admin management (add/remove, owner-only) | ✅ | L1287-1362 |
| Broadcast wizard menu | ✅ | L813-825 |
| Campaign management menu | ✅ | L1626-1643 |

### F. Background Tasks
| Task | Interval | Location |
|------|----------|----------|
| `auto_delete_broadcasts` — delete expired messages | 60s | L412-428 |
| `auto_recurring_campaigns` — send recurring campaigns | 300s | L2344-2401 |
| `auto_recurring_broadcasts` — send recurring broadcasts | 300s | L2403-2458 |

### G. Infrastructure
| Component | Details |
|-----------|---------|
| Framework | aiogram 3.x (≥3.15) |
| Database | SQLite via aiosqlite |
| State management | FSM with MemoryStorage |
| Config | `.env` file (BOT_TOKEN, ADMIN_ID, BOT_USERNAME) |
| Deployment | PM2 on Ubuntu VPS |
| Error handling | Global error handler (L2585-2589), self-healing polling loop (L2610-2618) |

---

## 3. Database Schema (7 tables)

```
groups          (chat_id PK, title, chat_type, status, added_at, updated_at, last_promo_msg_id, added_by)
users           (telegram_id PK, username, first_name, created_at)
settings        (key PK, value) — 17 default keys
events          (id PK, chat_id, telegram_user_id, event_type, created_at)
admins          (telegram_id PK, added_at)
broadcast_messages  (id PK, chat_id, message_id, delete_at) — used for timed deletion
campaigns       (id PK, name, promo_text, media_type, media_file_id, button_text, required_groups,
                 unlock_content, unlock_media_type, unlock_media_file_id, status, created_at, updated_at,
                 unlock_delete_seconds, mode, repeat_hours, recurring_active, last_broadcast_at)
campaign_user_progress (id PK, campaign_id, user_id, verified_count, status, created_at, updated_at, UNIQUE)
campaign_groups (id PK, campaign_id, user_id, chat_id, chat_title, verified, verified_at, UNIQUE)
recurring_broadcasts (id PK, target, text, media_id, media_type, is_vip, stars, repeat_hours, is_active, last_broadcast_at, created_at)
```

---

## 4. Design Problems in Legacy Code

### A. Architecture
| Problem | Impact | Fix Strategy |
|---------|--------|-------------|
| **Single 2627-line file** | Unmaintainable, impossible to review, merge conflicts | Split into modules by responsibility |
| **Global mutable state** (`bot`, `dp`, `last_promo_times`, `_campaign_verify_cooldown`) | Thread-safety risk, tight coupling | Move to proper singletons/DI pattern |
| **Database connection per query** (new `aiosqlite.connect()` on every operation) | Connection overhead, no pooling | Create a connection pool/manager |
| **No separation of concerns** | Handlers mix business logic, DB queries, and UI construction | Service layer + repository pattern |
| **Duplicate message-sending logic** | Same photo/video/text branching repeated 8+ times | Extract `send_media_message()` utility |

### B. UX/Workflow
| Problem | Impact | Fix Strategy |
|---------|--------|-------------|
| **No back buttons in input steps** | User stuck if they enter wrong state | Add back/cancel to every FSM step |
| **No custom inline URL buttons** for promo/welcome/campaigns | Limited promotion flexibility | Proper button management system |
| **No media on welcome message** | Less engaging welcome | Add media support |
| **No campaign preview** from admin view | Admin can't verify before publishing | Add preview button |
| **Settings stored as flat key-value** | Works but fragile for complex data | Keep for simple settings, use proper tables for structured data (buttons) |
| **`/cancel` is text-only** — no inline cancel button | Inconsistent UX | Provide inline keyboard cancel alongside text command |

### C. Reliability
| Problem | Impact | Fix Strategy |
|---------|--------|-------------|
| **MemoryStorage for FSM** | State lost on restart | Acceptable for admin-only wizards; not critical |
| **No graceful shutdown** | Background tasks may corrupt data | Add proper shutdown signals |
| **Broad `except Exception: pass`** in broadcasts | Silent failures | Log failures, add retry logic |
| **`init_db` uses ALTER TABLE in try/except** for migrations | Works but fragile | Create proper migration system |

---

## 5. What Must Be Preserved (Non-Negotiable)

1. All existing features listed in the inventory above.
2. The SQLite database file (`bot.db`) and all its data.
3. The `.env` configuration approach.
4. PM2 deployment model.
5. aiogram 3.x as the Telegram framework.
6. The admin panel design language (Arabic admin, English user-facing).
7. The campaign deep-link mechanism (`/start camp_<id>`).
8. The VIP/Stars payment flow.
9. The self-healing polling loop.
10. All callback_data patterns (existing deep links and buttons in use).
