#!/usr/bin/env python3
"""
Phase 4 Feature & Integration Script — Deploy Links Bot
Implements:
  1. Bot Owner Invite Links (Permanent & Temporary, Manual Pause/Resume, Delete, Join Stats)
  2. User Permanent Referral Link ("🔗 رابط الاحالة الخاص بي" generated in background on first click,
     permanently stored and accessible at any time)

Features:
  - Idempotent execution (safe to run multiple times)
  - Automatic backup before modification (.backups/phase4/)
  - AST syntax verification before writing any Python file
  - Supports --dry-run and --rollback modes
"""

import argparse
import ast
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKUP_DIR = PROJECT_ROOT / ".backups" / "phase4"

MODIFIED_FILES = [
    "core/database.py",
    "states/states.py",
    "handlers/start.py",
    "handlers/__init__.py",
]

CREATED_FILES = [
    "models/invite_links.py",
    "handlers/admin/invite_links.py",
]


def verify_python_syntax(code: str, filepath: str) -> None:
    """Parse Python source with AST to guarantee zero syntax errors."""
    try:
        ast.parse(code, filename=filepath)
    except SyntaxError as exc:
        raise RuntimeError(f"AST syntax check failed for {filepath}: {exc}") from exc


def create_backups(extra_files: list[str], dry_run: bool = False) -> None:
    if dry_run:
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    tracked = list(dict.fromkeys(MODIFIED_FILES + extra_files))
    (BACKUP_DIR / "manifest.json").write_text(
        json.dumps({"modified": tracked, "created": CREATED_FILES}, indent=2),
        encoding="utf-8",
    )
    for rel_path in tracked:
        src = PROJECT_ROOT / rel_path
        dst = BACKUP_DIR / rel_path
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    db_file = PROJECT_ROOT / "bot.db"
    db_backup = BACKUP_DIR / "bot.db"
    if db_file.exists() and not db_backup.exists():
        shutil.copy2(db_file, db_backup)


def rollback() -> int:
    if not BACKUP_DIR.exists():
        print("[ROLLBACK] No backup directory found at .backups/phase4/")
        return 1
    manifest_file = BACKUP_DIR / "manifest.json"
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        modified = manifest.get("modified", MODIFIED_FILES)
        created = manifest.get("created", CREATED_FILES)
    else:
        modified = MODIFIED_FILES
        created = CREATED_FILES

    for rel_path in modified:
        bkp = BACKUP_DIR / rel_path
        dst = PROJECT_ROOT / rel_path
        if bkp.exists():
            shutil.copy2(bkp, dst)
            print(f"[ROLLBACK] Restored {rel_path}")

    for rel_path in created:
        dst = PROJECT_ROOT / rel_path
        if dst.exists():
            dst.unlink()
            print(f"[ROLLBACK] Removed created file {rel_path}")

    db_backup = BACKUP_DIR / "bot.db"
    if db_backup.exists():
        shutil.copy2(db_backup, PROJECT_ROOT / "bot.db")
        print("[ROLLBACK] Restored bot.db")

    print("[ROLLBACK] Phase 4 rollback completed successfully.")
    return 0


# ── 1. New File: models/invite_links.py ──────────────────────────────────────

MODELS_INVITE_LINKS_CODE = '''"""
Database models and business queries for:
  1. Owner Invite Links (permanent & temporary, manual pause/resume, delete)
  2. User Permanent Referral Links (generated on first button click, persisted forever)
"""

import secrets
from datetime import datetime, timedelta
from core.database import get_db


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _compute_effective_status(row_dict: dict, now_str: str | None = None) -> dict:
    """Compute effective_status ('active', 'paused', or 'expired') for an owner invite link."""
    now_val = now_str or _now_str()
    status = row_dict.get("status", "active")
    link_type = row_dict.get("link_type", "permanent")
    expires_at = row_dict.get("expires_at")
    if status == "paused":
        effective = "paused"
    elif link_type == "temporary" and expires_at:
        norm_exp = str(expires_at).replace("T", " ")[:19]
        effective = "expired" if norm_exp <= now_val else "active"
    else:
        effective = "active"
    row_dict["effective_status"] = effective
    return row_dict


async def create_owner_invite_link(
    label: str | None = None,
    link_type: str = "permanent",
    duration_hours: int | None = None,
    created_by: int | None = None,
) -> dict:
    """Create a permanent or temporary invite link for the bot owner."""
    if link_type not in ("permanent", "temporary"):
        raise ValueError("link_type must be 'permanent' or 'temporary'")

    now_str = _now_str()
    expires_at = None
    if link_type == "temporary":
        if not duration_hours or duration_hours <= 0:
            raise ValueError("duration_hours must be > 0 for temporary links")
        expires_at = (datetime.now() + timedelta(hours=int(duration_hours))).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    async with get_db() as db:
        for _ in range(10):
            code = secrets.token_hex(4)
            async with db.execute(
                "SELECT 1 FROM owner_invite_links WHERE code = ?", (code,)
            ) as c:
                if not await c.fetchone():
                    break
        cursor = await db.execute(
            """
            INSERT INTO owner_invite_links
                (code, label, link_type, expires_at, status, clicks_count, joins_count, created_by, created_at)
            VALUES (?, ?, ?, ?, 'active', 0, 0, ?, ?)
            """,
            (code, label, link_type, expires_at, created_by, now_str),
        )
        link_id = cursor.lastrowid
        await db.commit()

    return await get_owner_invite_link(link_id)


async def get_owner_invite_link(link_id: int) -> dict | None:
    """Fetch a single owner invite link by ID."""
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM owner_invite_links WHERE id = ?", (link_id,)
        ) as c:
            row = await c.fetchone()
            if not row:
                return None
            cols = [d[0] for d in c.description]
            return _compute_effective_status(dict(zip(cols, row)))


async def get_owner_invite_link_by_code(code: str) -> dict | None:
    """Fetch a single owner invite link by its unique code."""
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM owner_invite_links WHERE code = ?", (code,)
        ) as c:
            row = await c.fetchone()
            if not row:
                return None
            cols = [d[0] for d in c.description]
            return _compute_effective_status(dict(zip(cols, row)))


async def list_owner_invite_links() -> list[dict]:
    """Return all owner invite links ordered newest first."""
    now_str = _now_str()
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM owner_invite_links ORDER BY id DESC"
        ) as c:
            rows = await c.fetchall()
            cols = [d[0] for d in c.description]
    return [_compute_effective_status(dict(zip(cols, r)), now_str) for r in rows]


async def set_owner_invite_status(link_id: int, status: str) -> bool:
    """Manually pause ('paused') or resume ('active') an owner invite link."""
    if status not in ("active", "paused"):
        raise ValueError("status must be 'active' or 'paused'")
    async with get_db() as db:
        cursor = await db.execute(
            "UPDATE owner_invite_links SET status = ? WHERE id = ?",
            (status, link_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def delete_owner_invite_link(link_id: int) -> bool:
    """Permanently delete an owner invite link."""
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM owner_invite_links WHERE id = ?", (link_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def process_owner_invite_join(
    code: str, user_id: int
) -> tuple[bool, str, dict | None]:
    """
    Validate and record a user joining via an owner invite link (`inv_<code>`).
    Returns (is_valid, reason, link_dict).
    reason in ('active', 'not_found', 'paused', 'expired').
    """
    link = await get_owner_invite_link_by_code(code)
    if not link:
        return False, "not_found", None

    eff_status = link["effective_status"]
    if eff_status == "paused":
        return False, "paused", link
    if eff_status == "expired":
        return False, "expired", link

    now_str = _now_str()
    async with get_db() as db:
        await db.execute(
            "UPDATE owner_invite_links SET clicks_count = clicks_count + 1 WHERE id = ?",
            (link["id"],),
        )
        ins = await db.execute(
            """
            INSERT OR IGNORE INTO invite_join_logs (user_id, source_type, source_code, joined_at)
            VALUES (?, 'owner', ?, ?)
            """,
            (user_id, code, now_str),
        )
        if ins.rowcount > 0:
            await db.execute(
                "UPDATE owner_invite_links SET joins_count = joins_count + 1 WHERE id = ?",
                (link["id"],),
            )
        await db.commit()

    updated = await get_owner_invite_link(link["id"])
    return True, "active", updated


async def get_user_referral(user_id: int) -> dict | None:
    """Return existing referral record for a user if already generated, else None."""
    async with get_db() as db:
        async with db.execute(
            "SELECT user_id, ref_code, referrals_count, created_at "
            "FROM user_referral_links WHERE user_id = ?",
            (user_id,),
        ) as c:
            row = await c.fetchone()
            if not row:
                return None
            cols = [d[0] for d in c.description]
            return dict(zip(cols, row))


async def get_or_create_user_referral(user_id: int) -> dict:
    """
    Atomically retrieve the user's permanent referral link, or generate and save it
    in the background on their very first click.
    """
    now_str = _now_str()
    async with get_db() as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await db.execute(
                "INSERT OR IGNORE INTO users (telegram_id, created_at) VALUES (?, ?)",
                (user_id, now_str),
            )
            async with db.execute(
                "SELECT user_id, ref_code, referrals_count, created_at "
                "FROM user_referral_links WHERE user_id = ?",
                (user_id,),
            ) as c:
                row = await c.fetchone()
                if row:
                    cols = [d[0] for d in c.description]
                    await db.commit()
                    return dict(zip(cols, row))

            for _ in range(10):
                ref_code = f"u{user_id}_{secrets.token_hex(3)}"
                async with db.execute(
                    "SELECT 1 FROM user_referral_links WHERE ref_code = ?", (ref_code,)
                ) as chk:
                    if not await chk.fetchone():
                        break

            await db.execute(
                """
                INSERT INTO user_referral_links (user_id, ref_code, referrals_count, created_at)
                VALUES (?, ?, 0, ?)
                """,
                (user_id, ref_code, now_str),
            )
            await db.commit()
            return {
                "user_id": user_id,
                "ref_code": ref_code,
                "referrals_count": 0,
                "created_at": now_str,
            }
        except Exception:
            await db.rollback()
            raise


async def process_user_referral_join(
    ref_code: str, new_user_id: int
) -> tuple[bool, str, int | None]:
    """
    Process a user starting the bot via `ref_<ref_code>`.
    Returns (counted, reason, referrer_user_id).
    reason in ('counted', 'not_found', 'self_referral', 'already_counted').
    """
    now_str = _now_str()
    async with get_db() as db:
        async with db.execute(
            "SELECT user_id FROM user_referral_links WHERE ref_code = ?",
            (ref_code,),
        ) as c:
            row = await c.fetchone()
            if not row:
                return False, "not_found", None
            referrer_id = int(row[0])

        if referrer_id == int(new_user_id):
            return False, "self_referral", referrer_id

        ins = await db.execute(
            """
            INSERT OR IGNORE INTO invite_join_logs (user_id, source_type, source_code, joined_at)
            VALUES (?, 'referral', ?, ?)
            """,
            (new_user_id, ref_code, now_str),
        )
        if ins.rowcount == 0:
            await db.commit()
            return False, "already_counted", referrer_id

        await db.execute(
            "UPDATE user_referral_links SET referrals_count = referrals_count + 1 WHERE user_id = ?",
            (referrer_id,),
        )
        await db.execute(
            "INSERT INTO events (chat_id, user_id, event_type, created_at) VALUES (0, ?, 'referral_joined', ?)",
            (new_user_id, now_str),
        )
        await db.commit()
        return True, "counted", referrer_id
'''


# ── 2. New File: handlers/admin/invite_links.py ──────────────────────────────

HANDLERS_INVITE_LINKS_CODE = '''"""
Handlers for:
  1. Bot Owner Invite Links Management (permanent/temporary, manual pause/resume, delete)
  2. Regular User "🔗 رابط الاحالة الخاص بي" button (background generation on first click, permanent access)
"""

import html
from urllib.parse import quote
from aiogram import Router, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.bot import bot
from core.config import ADMIN_ID, BOT_USERNAME
from states.states import AdminEdit
from models.invite_links import (
    create_owner_invite_link,
    get_owner_invite_link,
    list_owner_invite_links,
    set_owner_invite_status,
    delete_owner_invite_link,
    get_or_create_user_referral,
)

router = Router()

STATUS_LABELS = {
    "active": "🟢 نشط",
    "paused": "⏸ متوقف يدوياً",
    "expired": "⌛️ منتهي الصلاحية",
}


async def _safe_edit_or_answer(
    message: types.Message, text: str, kb: InlineKeyboardMarkup | None = None
) -> None:
    """Safely edit a text or media-caption message, falling back to answer()."""
    is_media = bool(
        getattr(message, "photo", None)
        or getattr(message, "video", None)
        or getattr(message, "caption", None) is not None
    )
    try:
        if is_media:
            await message.edit_caption(caption=text, reply_markup=kb, parse_mode=ParseMode.HTML)
        else:
            await message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception:
        await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


async def _get_bot_username() -> str:
    try:
        me = await bot.get_me()
        if getattr(me, "username", None):
            return me.username
    except Exception:
        pass
    return BOT_USERNAME or "bot"


# ── A. User Permanent Referral Link ("🔗 رابط الاحالة الخاص بي") ──────────────

@router.callback_query(F.data == "user_my_referral")
async def cb_user_my_referral(callback: types.CallbackQuery):
    """
    On first click: generates a permanent referral link for the user in the background.
    On every click: retrieves and displays the permanent referral link immediately.
    """
    user_id = callback.from_user.id
    ref = await get_or_create_user_referral(user_id)
    bot_username = await _get_bot_username()
    ref_url = f"https://t.me/{bot_username}?start=ref_{ref['ref_code']}"
    share_url = f"https://t.me/share/url?url={quote(ref_url)}&text={quote('انضم إلى البوت عبر رابط الإحالة الخاص بي!')}"

    text = (
        "🔗 <b>رابط الإحالة الخاص بك (دائم):</b>\\n\\n"
        f"<code>{html.escape(ref_url)}</code>\\n\\n"
        f"👥 <b>عدد المنضمين عبر رابطك:</b> {ref['referrals_count']}\\n\\n"
        "💡 <i>اضغط على الرابط أعلاه لنسخه، ويمكنك الوصول إليه في أي وقت عبر هذا الزر.</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 مشاركة الرابط", url=share_url)],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="start_back")],
    ])
    await _safe_edit_or_answer(callback.message, text, kb)
    try:
        await callback.answer()
    except Exception:
        pass


# ── B. Owner Invite Links Management (Strictly ADMIN_ID) ─────────────────────

def _is_owner(user_id: int) -> bool:
    return int(user_id) == int(ADMIN_ID)


@router.callback_query(F.data == "admin_invite_links")
async def cb_admin_invite_links(callback: types.CallbackQuery, state: FSMContext | None = None):
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔️ هذا القسم مخصص لمالك البوت فقط.", show_alert=True)
    if state:
        await state.clear()

    links = await list_owner_invite_links()
    text = "🔗 <b>إدارة روابط دعوة البوت (للمالك):</b>\\n\\n"
    kb_rows = [
        [InlineKeyboardButton(text="➕ توليد رابط دعوة جديد", callback_data="owner_inv_create")]
    ]

    if not links:
        text += "لا توجد روابط دعوة مولدة حتى الآن."
    else:
        text += "اختر رابطاً من القائمة لعرض تفاصيله أو إيقافه أو حذفه:\\n\\n"
        for lnk in links[:15]:
            st_icon = STATUS_LABELS.get(lnk["effective_status"], "🟢").split()[0]
            type_label = "♾ دائم" if lnk["link_type"] == "permanent" else "⏳ مؤقت"
            title = html.escape((lnk.get("label") or f"رابط #{lnk['id']}")[:25])
            text += (
                f"{st_icon} <b>{title}</b> ({type_label}) — "
                f"المنضمون: <b>{lnk['joins_count']}</b> | النقرات: {lnk['clicks_count']}\\n"
            )
            lnk_id = lnk["id"]
            lnk_label = lnk.get("label") or f"رابط #{lnk_id}"
            lnk_joins = lnk["joins_count"]
            kb_rows.append([
                InlineKeyboardButton(
                    text=f"{st_icon} {lnk_label[:20]} ({lnk_joins} منضم)",
                    callback_data=f"owner_inv_view_{lnk_id}",
                )
            ])

    kb_rows.append([InlineKeyboardButton(text="🔙 رجوع للوحة التحكم", callback_data="admin_back")])
    await _safe_edit_or_answer(callback.message, text, InlineKeyboardMarkup(inline_keyboard=kb_rows))
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "owner_inv_create")
async def cb_owner_inv_create(callback: types.CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔️ للمالك فقط.", show_alert=True)
    await state.clear()
    await state.set_state(AdminEdit.waiting_for_inv_label)
    await callback.message.answer(
        "🏷 <b>توليد رابط دعوة جديد</b>\\n\\n"
        "أرسل اسماً توضيحياً للرابط (مثلاً: <i>إعلان قناة التوصيات</i>)، أو أرسل /skip للتخطي.\\n"
        "لإلغاء العملية أرسل /cancel",
        parse_mode=ParseMode.HTML,
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(AdminEdit.waiting_for_inv_label)
async def process_owner_inv_label(message: types.Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    if not message.text:
        return await message.answer("❌ يرجى إرسال اسم الرابط كنص أو /skip أو /cancel.")
    if message.text.strip() == "/cancel":
        await state.clear()
        return await message.answer("❌ تم إلغاء توليد الرابط.")

    label = None if message.text.strip() == "/skip" else message.text.strip()[:60]
    await state.update_data(inv_label=label)
    await state.set_state(AdminEdit.waiting_for_inv_type)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="♾ رابط دائم", callback_data="owner_inv_type_perm")],
        [InlineKeyboardButton(text="⏳ رابط مؤقت (بمدة محددة)", callback_data="owner_inv_type_temp")],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_invite_links")],
    ])
    await message.answer(
        "⚙️ <b>اختر نوع رابط الدعوة:</b>\\n\\n"
        "• <b>♾ دائم:</b> يعمل باستمرار حتى تقوم بإيقافه يدوياً أو حذفه.\\n"
        "• <b>⏳ مؤقت:</b> ينتهي تلقائياً بعد عدد الساعات الذي تحدده (مع إمكانية إيقافه أو حذفه يدوياً أيضاً).",
        reply_markup=kb,
        parse_mode=ParseMode.HTML,
    )


async def _render_owner_link_details(
    target_msg: types.Message, link_id: int, prefix_notice: str = ""
) -> None:
    lnk = await get_owner_invite_link(link_id)
    if not lnk:
        await _safe_edit_or_answer(
            target_msg,
            "❌ هذا الرابط غير موجود أو تم حذفه.",
            InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_invite_links")]
            ]),
        )
        return

    bot_username = await _get_bot_username()
    full_url = f"https://t.me/{bot_username}?start=inv_{lnk['code']}"
    title = html.escape(lnk.get("label") or f"رابط #{lnk['id']}")
    type_text = "♾ دائم" if lnk["link_type"] == "permanent" else "⏳ مؤقت"
    status_text = STATUS_LABELS.get(lnk["effective_status"], lnk["effective_status"])
    exp_line = (
        f"⏰ <b>ينتهي في:</b> <code>{lnk['expires_at']}</code>\\n"
        if lnk["link_type"] == "temporary" and lnk.get("expires_at")
        else ""
    )

    text = (
        f"{prefix_notice}"
        f"🔗 <b>تفاصيل رابط الدعوة: {title}</b>\\n\\n"
        f"📎 <b>الرابط:</b>\\n<code>{html.escape(full_url)}</code>\\n\\n"
        f"📌 <b>النوع:</b> {type_text}\\n"
        f"📊 <b>الحالة:</b> {status_text}\\n"
        f"{exp_line}"
        f"👆 <b>إجمالي النقرات:</b> {lnk['clicks_count']}\\n"
        f"👥 <b>المستخدمون المنضمون:</b> {lnk['joins_count']}\\n"
        f"📅 <b>تاريخ الإنشاء:</b> <code>{lnk['created_at']}</code>"
    )

    kb_rows = []
    if lnk["status"] == "active":
        kb_rows.append([
            InlineKeyboardButton(
                text="⏸ إيقاف الرابط يدوياً",
                callback_data=f"owner_inv_pause_{lnk['id']}",
            )
        ])
    else:
        kb_rows.append([
            InlineKeyboardButton(
                text="▶️ إعادة تفعيل الرابط",
                callback_data=f"owner_inv_resume_{lnk['id']}",
            )
        ])

    kb_rows.append([
        InlineKeyboardButton(
            text="🗑 حذف الرابط نهائياً",
            callback_data=f"owner_inv_del_ask_{lnk['id']}",
        )
    ])
    kb_rows.append([
        InlineKeyboardButton(text="🔙 رجوع لقائمة الروابط", callback_data="admin_invite_links")
    ])
    await _safe_edit_or_answer(target_msg, text, InlineKeyboardMarkup(inline_keyboard=kb_rows))


@router.callback_query(
    AdminEdit.waiting_for_inv_type,
    F.data.in_({"owner_inv_type_perm", "owner_inv_type_temp"}),
)
async def cb_owner_inv_type(callback: types.CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔️ للمالك فقط.", show_alert=True)

    data = await state.get_data()
    label = data.get("inv_label")

    if callback.data == "owner_inv_type_perm":
        await state.clear()
        created = await create_owner_invite_link(
            label=label,
            link_type="permanent",
            duration_hours=None,
            created_by=callback.from_user.id,
        )
        await _render_owner_link_details(
            callback.message,
            created["id"],
            prefix_notice="✅ <b>تم توليد رابط الدعوة الدائم بنجاح!</b>\\n\\n",
        )
        try:
            await callback.answer("✅ تم توليد الرابط الدائم")
        except Exception:
            pass
        return

    # Temporary link -> ask for duration in hours
    await state.set_state(AdminEdit.waiting_for_inv_hours)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="ساعة واحدة (1h)", callback_data="owner_inv_dur_1"),
            InlineKeyboardButton(text="6 ساعات (6h)", callback_data="owner_inv_dur_6"),
        ],
        [
            InlineKeyboardButton(text="24 ساعة (1d)", callback_data="owner_inv_dur_24"),
            InlineKeyboardButton(text="7 أيام (168h)", callback_data="owner_inv_dur_168"),
        ],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_invite_links")],
    ])
    await _safe_edit_or_answer(
        callback.message,
        "⏳ <b>تحديد مدة الرابط المؤقت:</b>\\n\\n"
        "اختر مدة جاهزة من الأزرار أدناه، أو أرسل عدد الساعات رقماً (بين 1 و 8760):",
        kb,
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(
    AdminEdit.waiting_for_inv_hours,
    F.data.startswith("owner_inv_dur_"),
)
async def cb_owner_inv_duration_preset(callback: types.CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔️ للمالك فقط.", show_alert=True)
    hours = int(callback.data.replace("owner_inv_dur_", ""))
    data = await state.get_data()
    label = data.get("inv_label")
    await state.clear()

    created = await create_owner_invite_link(
        label=label,
        link_type="temporary",
        duration_hours=hours,
        created_by=callback.from_user.id,
    )
    await _render_owner_link_details(
        callback.message,
        created["id"],
        prefix_notice=f"✅ <b>تم توليد رابط الدعوة المؤقت ({hours} ساعة) بنجاح!</b>\\n\\n",
    )
    try:
        await callback.answer("✅ تم توليد الرابط المؤقت")
    except Exception:
        pass


@router.message(AdminEdit.waiting_for_inv_hours)
async def process_owner_inv_hours(message: types.Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    if not message.text:
        return await message.answer("❌ يرجى إرسال عدد الساعات كأرقام فقط (مثلاً 12) أو /cancel.")
    if message.text.strip() == "/cancel":
        await state.clear()
        return await message.answer("❌ تم إلغاء العملية.")
    if not message.text.strip().isdigit() or not (1 <= int(message.text.strip()) <= 8760):
        return await message.answer("❌ يرجى إرسال رقم صحيح بين 1 و 8760 ساعة.")

    hours = int(message.text.strip())
    data = await state.get_data()
    label = data.get("inv_label")
    await state.clear()

    created = await create_owner_invite_link(
        label=label,
        link_type="temporary",
        duration_hours=hours,
        created_by=message.from_user.id,
    )
    await _render_owner_link_details(
        message,
        created["id"],
        prefix_notice=f"✅ <b>تم توليد رابط الدعوة المؤقت ({hours} ساعة) بنجاح!</b>\\n\\n",
    )


@router.callback_query(F.data.startswith("owner_inv_view_"))
async def cb_owner_inv_view(callback: types.CallbackQuery):
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔️ للمالك فقط.", show_alert=True)
    link_id = int(callback.data.replace("owner_inv_view_", ""))
    await _render_owner_link_details(callback.message, link_id)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("owner_inv_pause_"))
async def cb_owner_inv_pause(callback: types.CallbackQuery):
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔️ للمالك فقط.", show_alert=True)
    link_id = int(callback.data.replace("owner_inv_pause_", ""))
    await set_owner_invite_status(link_id, "paused")
    await _render_owner_link_details(
        callback.message,
        link_id,
        prefix_notice="⏸ <b>تم إيقاف الرابط يدوياً.</b>\\n\\n",
    )
    try:
        await callback.answer("⏸ تم إيقاف الرابط يدوياً")
    except Exception:
        pass


@router.callback_query(F.data.startswith("owner_inv_resume_"))
async def cb_owner_inv_resume(callback: types.CallbackQuery):
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔️ للمالك فقط.", show_alert=True)
    link_id = int(callback.data.replace("owner_inv_resume_", ""))
    await set_owner_invite_status(link_id, "active")
    await _render_owner_link_details(
        callback.message,
        link_id,
        prefix_notice="▶️ <b>تمت إعادة تفعيل الرابط بنجاح.</b>\\n\\n",
    )
    try:
        await callback.answer("▶️ تم تفعيل الرابط")
    except Exception:
        pass


@router.callback_query(F.data.startswith("owner_inv_del_ask_"))
async def cb_owner_inv_del_ask(callback: types.CallbackQuery):
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔️ للمالك فقط.", show_alert=True)
    link_id = int(callback.data.replace("owner_inv_del_ask_", ""))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ نعم، احذف الرابط نهائياً",
                callback_data=f"owner_inv_del_confirm_{link_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="🔙 تراجع",
                callback_data=f"owner_inv_view_{link_id}",
            )
        ],
    ])
    await _safe_edit_or_answer(
        callback.message,
        f"⚠️ <b>تأكيد الحذف:</b>\\n\\nهل أنت متأكد من حذف رابط الدعوة #{link_id} نهائياً؟ لا يمكن التراجع عن هذا الإجراء.",
        kb,
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("owner_inv_del_confirm_"))
async def cb_owner_inv_del_confirm(callback: types.CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        return await callback.answer("⛔️ للمالك فقط.", show_alert=True)
    link_id = int(callback.data.replace("owner_inv_del_confirm_", ""))
    await delete_owner_invite_link(link_id)
    try:
        await callback.answer("🗑 تم حذف الرابط نهائياً")
    except Exception:
        pass
    await cb_admin_invite_links(callback, state)
'''


# ── 3. Patchers for Existing Files ───────────────────────────────────────────

def patch_core_database(content: str) -> tuple[str, list[str]]:
    applied = []
    anchor = (
        '        await db.execute(\n'
        '            "CREATE INDEX IF NOT EXISTS idx_broadcast_messages_delete_at "\n'
        '            "ON broadcast_messages(delete_at)"\n'
        '        )'
    )
    invite_tables_sql = (
        '        await db.execute(\n'
        '            "CREATE INDEX IF NOT EXISTS idx_broadcast_messages_delete_at "\n'
        '            "ON broadcast_messages(delete_at)"\n'
        '        )\n'
        '        await db.execute("""\n'
        '            CREATE TABLE IF NOT EXISTS owner_invite_links (\n'
        '                id INTEGER PRIMARY KEY AUTOINCREMENT,\n'
        '                code TEXT UNIQUE NOT NULL,\n'
        '                label TEXT,\n'
        '                link_type TEXT NOT NULL DEFAULT \'permanent\',\n'
        '                expires_at TIMESTAMP,\n'
        '                status TEXT NOT NULL DEFAULT \'active\',\n'
        '                clicks_count INTEGER NOT NULL DEFAULT 0,\n'
        '                joins_count INTEGER NOT NULL DEFAULT 0,\n'
        '                created_by INTEGER,\n'
        '                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n'
        '            )\n'
        '        """)\n'
        '        await db.execute("""\n'
        '            CREATE TABLE IF NOT EXISTS user_referral_links (\n'
        '                user_id INTEGER PRIMARY KEY,\n'
        '                ref_code TEXT UNIQUE NOT NULL,\n'
        '                referrals_count INTEGER NOT NULL DEFAULT 0,\n'
        '                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n'
        '                FOREIGN KEY (user_id) REFERENCES users(telegram_id)\n'
        '            )\n'
        '        """)\n'
        '        await db.execute("""\n'
        '            CREATE TABLE IF NOT EXISTS invite_join_logs (\n'
        '                id INTEGER PRIMARY KEY AUTOINCREMENT,\n'
        '                user_id INTEGER NOT NULL,\n'
        '                source_type TEXT NOT NULL,\n'
        '                source_code TEXT NOT NULL,\n'
        '                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n'
        '                UNIQUE(user_id, source_type, source_code)\n'
        '            )\n'
        '        """)\n'
        '        await db.execute(\n'
        '            "CREATE INDEX IF NOT EXISTS idx_owner_invite_links_code ON owner_invite_links(code)"\n'
        '        )\n'
        '        await db.execute(\n'
        '            "CREATE INDEX IF NOT EXISTS idx_user_referral_links_code ON user_referral_links(ref_code)"\n'
        '        )\n'
        '        await db.execute(\n'
        '            "CREATE INDEX IF NOT EXISTS idx_invite_join_logs_user ON invite_join_logs(user_id)"\n'
        '        )'
    )
    if "CREATE TABLE IF NOT EXISTS owner_invite_links" not in content:
        if anchor not in content:
            raise RuntimeError("Could not locate idx_broadcast_messages_delete_at anchor in core/database.py")
        content = content.replace(anchor, invite_tables_sql, 1)
        applied.append("core/database.py: Added owner_invite_links, user_referral_links, and invite_join_logs tables")
    return content, applied


def patch_states(content: str) -> tuple[str, list[str]]:
    applied = []
    old_block = "    waiting_for_rbw_hours = State()"
    new_block = (
        "    waiting_for_rbw_hours = State()\n"
        "    waiting_for_inv_label = State()\n"
        "    waiting_for_inv_type = State()\n"
        "    waiting_for_inv_hours = State()"
    )
    if "waiting_for_inv_label = State()" not in content:
        if old_block not in content:
            raise RuntimeError("Could not locate waiting_for_rbw_hours in states/states.py")
        content = content.replace(old_block, new_block, 1)
        applied.append("states/states.py: Added owner invite link wizard states")
    return content, applied


def patch_handlers_start(content: str) -> tuple[str, list[str]]:
    """
    Enhance handlers/start.py to:
      1. Include '🔗 رابط الاحالة الخاص بي' (user_my_referral) in get_start_message_data()
      2. Process deep-links `/start inv_<code>` and `/start ref_<code>` before or within the start handler.
    """
    applied = []
    if "# ── Phase 4 Invite & Referral Integration ──" in content:
        return content, applied

    # Find the name of the @router.message(CommandStart...) handler function using AST
    tree = ast.parse(content)
    start_fn_name = None
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.decorator_list:
            for dec in node.decorator_list:
                dec_src = ast.unparse(dec)
                if "router.message" in dec_src and ("CommandStart" in dec_src or '"start"' in dec_src or "'start'" in dec_src):
                    start_fn_name = node.name
                    break

    if not start_fn_name:
        raise RuntimeError("Could not locate /start message handler function in handlers/start.py")

    phase4_hook = f'''

# ── Phase 4 Invite & Referral Integration ──
_orig_get_start_message_data = get_start_message_data


async def get_start_message_data(bot_username: str):
    """Wrap get_start_message_data to always include '🔗 رابط الاحالة الخاص بي' button."""
    text, kb = await _orig_get_start_message_data(bot_username)
    rows = list(kb.inline_keyboard) if kb and getattr(kb, "inline_keyboard", None) else []
    has_ref_btn = any(
        getattr(btn, "callback_data", None) == "user_my_referral"
        for row in rows
        for btn in row
    )
    if not has_ref_btn:
        rows.append([InlineKeyboardButton(text="🔗 رابط الاحالة الخاص بي", callback_data="user_my_referral")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


_orig_{start_fn_name} = {start_fn_name}


async def _phase4_wrapped_start(message: types.Message, *args, **kwargs):
    """Intercept /start inv_<code> and /start ref_<code> deep links before standard /start flow."""
    raw_text = (getattr(message, "text", None) or "").strip()
    parts = raw_text.split(maxsplit=1)
    if len(parts) > 1:
        payload = parts[1].strip()
        if payload.startswith("inv_"):
            from models.invite_links import process_owner_invite_join
            from models.users import upsert_user
            code = payload[4:]
            user = message.from_user
            if user:
                await upsert_user(user.id, getattr(user, "username", None), getattr(user, "first_name", None))
                ok, reason, _ = await process_owner_invite_join(code, user.id)
                if not ok:
                    if reason == "paused":
                        await message.answer("⛔️ عذراً، رابط الدعوة هذا متوقف حالياً من قِبل إدارة البوت.")
                    elif reason == "expired":
                        await message.answer("⌛️ عذراً، انتهت صلاحية رابط الدعوة المؤقت هذا.")
                    else:
                        await message.answer("❌ عذراً، رابط الدعوة هذا غير صالح أو تم حذفه.")
                    return
        elif payload.startswith("ref_"):
            from models.invite_links import process_user_referral_join
            from models.users import upsert_user
            ref_code = payload[4:]
            user = message.from_user
            if user:
                await upsert_user(user.id, getattr(user, "username", None), getattr(user, "first_name", None))
                await process_user_referral_join(ref_code, user.id)

    return await _orig_{start_fn_name}(message, *args, **kwargs)


{start_fn_name} = _phase4_wrapped_start
for _obs_handler in router.message.handlers:
    if getattr(_obs_handler, "callback", None) is _orig_{start_fn_name}:
        _obs_handler.callback = _phase4_wrapped_start
'''
    content = content + phase4_hook
    applied.append("handlers/start.py: Added '🔗 رابط الاحالة الخاص بي' button and /start inv_ & ref_ deep-link handling")
    return content, applied


def patch_main_py(content: str) -> tuple[str, list[str]]:
    """
    This project uses register_all_routers(dp) from handlers/__init__.py.
    We patch handlers/__init__.py instead to register the new router there.
    This function patches handlers/__init__.py (passed as 'content').
    """
    applied = []
    if "invite_links" in content:
        return content, applied

    # Pattern: find the last router import line and add after it
    m = re.search(
        r"(from handlers\.\w+[\.\w]* import router as \w+\n)(\s*\n*def register_all_routers)",
        content, re.DOTALL
    )
    if m:
        anchor = m.group(1)
        new_block = anchor + "from handlers.admin.invite_links import router as invite_links_router\n"
        content = content.replace(anchor, new_block, 1)
        # Also add to include_routers call
        inc_anchor = "admin_user_mgmt_router,\n    )"
        if inc_anchor in content:
            content = content.replace(
                inc_anchor,
                "admin_user_mgmt_router,\n        invite_links_router,\n    )",
                1,
            )
        applied.append("handlers/__init__.py: Registered invite_links router in register_all_routers()")
        return content, applied

    # Fallback: append import and include at end of include_routers block
    old_anchor = "from handlers.user.my_campaign import router as user_campaign_router"
    if old_anchor in content:
        content = content.replace(
            old_anchor,
            old_anchor + "\nfrom handlers.admin.invite_links import router as invite_links_router",
            1,
        )
    # Find last dp.include_routers entry
    inc_anchor = "admin_user_mgmt_router,"
    if inc_anchor in content:
        content = content.replace(
            inc_anchor,
            "admin_user_mgmt_router,\n        invite_links_router,",
            1,
        )
        applied.append("handlers/__init__.py: Registered invite_links router in register_all_routers()")
        return content, applied

    raise RuntimeError("Could not patch handlers/__init__.py to register invite_links router")


def patch_optional_menus(dry_run: bool = False) -> tuple[list[str], list[str]]:
    """
    Locate admin panel and user panel files to add:
      - '🔗 روابط دعوة البوت' (admin_invite_links) in Admin Panel
      - '🔗 رابط الاحالة الخاص بي' (user_my_referral) in User Dashboard
    Returns (extra_backed_up_files, applied_messages).
    """
    extra_files: list[str] = []
    applied: list[str] = []

    for py_file in sorted((PROJECT_ROOT / "handlers").rglob("*.py")):
        rel_path = py_file.relative_to(PROJECT_ROOT).as_posix()
        if rel_path in ("handlers/start.py", "handlers/admin/invite_links.py"):
            continue
        text = py_file.read_text(encoding="utf-8")
        modified = False

        # 1. Inject '🔗 رابط الاحالة الخاص بي' in user dashboard menu if `user_my_groups` button exists
        if 'callback_data="user_my_groups"' in text and 'callback_data="user_my_referral"' not in text:
            old_ug = 'callback_data="user_my_groups")'
            # Find the line containing callback_data="user_my_groups"
            lines = text.splitlines()
            new_lines = []
            for line in lines:
                new_lines.append(line)
                if 'callback_data="user_my_groups"' in line and not modified:
                    indent = line[: len(line) - len(line.lstrip())]
                    btn_cls = "types.InlineKeyboardButton" if "types.InlineKeyboardButton" in line else "InlineKeyboardButton"
                    new_lines.append(
                        f'{indent}[{btn_cls}(text="🔗 رابط الاحالة الخاص بي", callback_data="user_my_referral")],'
                    )
                    modified = True
            candidate = "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")
            try:
                verify_python_syntax(candidate, rel_path)
                text = candidate
                extra_files.append(rel_path)
                applied.append(f"{rel_path}: Added '🔗 رابط الاحالة الخاص بي' button to User Dashboard")
            except RuntimeError:
                modified = False

        # 2. Inject '🔗 روابط دعوة البوت' in admin main panel if `admin_admins` or `admin_campaigns` exists
        if 'callback_data="admin_admins"' in text and 'callback_data="admin_invite_links"' not in text:
            lines = text.splitlines()
            new_lines = []
            inserted_admin = False
            for line in lines:
                new_lines.append(line)
                if 'callback_data="admin_admins"' in line and not inserted_admin:
                    indent = line[: len(line) - len(line.lstrip())]
                    btn_cls = "types.InlineKeyboardButton" if "types.InlineKeyboardButton" in line else "InlineKeyboardButton"
                    new_lines.append(
                        f'{indent}[{btn_cls}(text="🔗 روابط دعوة البوت", callback_data="admin_invite_links")],'
                    )
                    inserted_admin = True
            candidate = "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")
            try:
                verify_python_syntax(candidate, rel_path)
                text = candidate
                modified = True
                if rel_path not in extra_files:
                    extra_files.append(rel_path)
                applied.append(f"{rel_path}: Added '🔗 روابط دعوة البوت' button to Admin Panel")
            except RuntimeError:
                pass

        if modified and not dry_run:
            bkp_dst = BACKUP_DIR / rel_path
            if not bkp_dst.exists():
                bkp_dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(py_file, bkp_dst)
            py_file.write_text(text, encoding="utf-8")

    return extra_files, applied


def migrate_existing_sqlite_db(dry_run: bool = False) -> list[str]:
    db_path = PROJECT_ROOT / "bot.db"
    if not db_path.exists():
        return ["bot.db not present on disk (will be initialized on first run)"]
    if dry_run:
        return ["[DRY-RUN] Would create owner_invite_links, user_referral_links, invite_join_logs in bot.db"]

    conn = sqlite3.connect(str(db_path), timeout=30.0)
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS owner_invite_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                label TEXT,
                link_type TEXT NOT NULL DEFAULT 'permanent',
                expires_at TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'active',
                clicks_count INTEGER NOT NULL DEFAULT 0,
                joins_count INTEGER NOT NULL DEFAULT 0,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_referral_links (
                user_id INTEGER PRIMARY KEY,
                ref_code TEXT UNIQUE NOT NULL,
                referrals_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(telegram_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS invite_join_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                source_type TEXT NOT NULL,
                source_code TEXT NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, source_type, source_code)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_owner_invite_links_code ON owner_invite_links(code)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_user_referral_links_code ON user_referral_links(ref_code)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_invite_join_logs_user ON invite_join_logs(user_id)")
        conn.commit()
    finally:
        conn.close()
    return ["bot.db: Created Phase 4 invite & referral tables and indexes"]


def run_phase4(dry_run: bool = False) -> int:
    print("=" * 65)
    print(f"Deploy Links Bot — Phase 4 Invite & Referral Links ({'DRY-RUN' if dry_run else 'APPLY'})")
    print("=" * 65)

    for rel_path in MODIFIED_FILES:
        if not (PROJECT_ROOT / rel_path).exists():
            print(f"[ERROR] Missing required project file: {rel_path}")
            return 1

    create_backups(extra_files=[], dry_run=dry_run)

    # Validate syntax of new files
    verify_python_syntax(MODELS_INVITE_LINKS_CODE, "models/invite_links.py")
    verify_python_syntax(HANDLERS_INVITE_LINKS_CODE, "handlers/admin/invite_links.py")

    all_changes: list[str] = []

    db_raw = (PROJECT_ROOT / "core/database.py").read_text(encoding="utf-8")
    db_new, ch_db = patch_core_database(db_raw)
    verify_python_syntax(db_new, "core/database.py")
    all_changes.extend(ch_db)

    st_raw = (PROJECT_ROOT / "states/states.py").read_text(encoding="utf-8")
    st_new, ch_st = patch_states(st_raw)
    verify_python_syntax(st_new, "states/states.py")
    all_changes.extend(ch_st)

    start_raw = (PROJECT_ROOT / "handlers/start.py").read_text(encoding="utf-8")
    start_new, ch_start = patch_handlers_start(start_raw)
    verify_python_syntax(start_new, "handlers/start.py")
    all_changes.extend(ch_start)

    main_raw = (PROJECT_ROOT / "handlers/__init__.py").read_text(encoding="utf-8")
    main_new, ch_main = patch_main_py(main_raw)
    verify_python_syntax(main_new, "handlers/__init__.py")
    all_changes.extend(ch_main)

    if not dry_run:
        (PROJECT_ROOT / "models/invite_links.py").write_text(MODELS_INVITE_LINKS_CODE, encoding="utf-8")
        (PROJECT_ROOT / "handlers/admin/invite_links.py").write_text(HANDLERS_INVITE_LINKS_CODE, encoding="utf-8")
        (PROJECT_ROOT / "core/database.py").write_text(db_new, encoding="utf-8")
        (PROJECT_ROOT / "states/states.py").write_text(st_new, encoding="utf-8")
        (PROJECT_ROOT / "handlers/start.py").write_text(start_new, encoding="utf-8")
        (PROJECT_ROOT / "handlers/__init__.py").write_text(main_new, encoding="utf-8")
    all_changes.append("models/invite_links.py: Created invite & referral data model")
    all_changes.append("handlers/admin/invite_links.py: Created owner invite wizard & user referral handler")

    extra_files, menu_changes = patch_optional_menus(dry_run=dry_run)
    if extra_files and not dry_run:
        create_backups(extra_files=extra_files, dry_run=False)
    all_changes.extend(menu_changes)

    db_changes = migrate_existing_sqlite_db(dry_run=dry_run)
    all_changes.extend(db_changes)

    print("\nChanges applied:")
    for item in all_changes:
        print(f"  [OK] {item}")

    print("\n[SUCCESS] Phase 4 feature installation completed cleanly.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 4 Invite & Referral Links Script")
    parser.add_argument("--dry-run", action="store_true", help="Simulate changes without modifying files")
    parser.add_argument("--rollback", action="store_true", help="Restore files from Phase 4 backup")
    args = parser.parse_args()

    if args.rollback:
        sys.exit(rollback())
    sys.exit(run_phase4(dry_run=args.dry_run))
