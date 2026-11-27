"""
i18n engine for Deploy Links Bot (aiogram 3).
Phase 6: Added user_id ContextVar tracking for AdminSessionI18nMiddleware safety boundary.

Usage:
    from core.i18n import t, get_lang, set_lang, LanguageMiddleware
"""

from contextvars import ContextVar, Token
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from locales import t as _t, SUPPORTED_LANGS

# Per-request context variables
_lang_ctx: ContextVar[str] = ContextVar("lang", default="en")
_user_id_ctx: ContextVar[int | None] = ContextVar("user_id", default=None)


# ---------------------------------------------------------------------------
# Context accessors
# ---------------------------------------------------------------------------

def get_lang_ctx() -> str:
    """Return the language set for the current async context (default 'en')."""
    return _lang_ctx.get()

# Alias used by admin_i18n.py
get_context_lang = get_lang_ctx


def set_lang_ctx(lang: str) -> Token:
    """Set the language for the current async context. Returns the reset token."""
    return _lang_ctx.set(lang if lang in SUPPORTED_LANGS else "en")


def reset_context_lang(token: Token) -> None:
    """Reset ContextVar after update completes."""
    _lang_ctx.reset(token)


def get_context_user_id() -> int | None:
    """Return active request user_id from ContextVar if set."""
    return _user_id_ctx.get()


def set_context_user_id(user_id: int | None) -> Token:
    """Set active request user_id in ContextVar. Returns the reset token."""
    return _user_id_ctx.set(int(user_id) if isinstance(user_id, int) else None)


def reset_context_user_id(token: Token) -> None:
    """Reset active user_id ContextVar after update completes."""
    _user_id_ctx.reset(token)


# ---------------------------------------------------------------------------
# Language resolution
# ---------------------------------------------------------------------------

def resolve_lang(language_code: str | None) -> str:
    """
    Resolve a Telegram language_code (e.g. 'ar', 'ar-SA', 'en-US') to a supported lang key.
    Falls back to 'en' if not supported.
    """
    if not language_code:
        return "en"
    code = language_code.split("-")[0].lower()
    return code if code in SUPPORTED_LANGS else "en"


def t(key: str, lang: str, **kwargs) -> str:
    """Shorthand: translate key into lang with optional format kwargs."""
    return _t(key, lang, **kwargs)


# ---------------------------------------------------------------------------
# In-memory lang cache:  user_id -> lang
# ---------------------------------------------------------------------------
_lang_cache: dict[int, str] = {}


def cache_user_lang(user_id: int, lang: str) -> None:
    _lang_cache[user_id] = lang


def get_cached_lang(user_id: int) -> str | None:
    return _lang_cache.get(user_id)


def invalidate_user_lang(user_id: int) -> None:
    _lang_cache.pop(user_id, None)


# ---------------------------------------------------------------------------
# Public get_lang / set_lang helpers (for handlers and tests)
# ---------------------------------------------------------------------------

async def get_lang(user_id: int | None, telegram_lang_code: str | None = None) -> str:
    """
    Resolve user lang: cache → DB → Telegram language_code → 'en'.
    Safe to call with non-int user_id (returns 'en' fallback).
    """
    if not isinstance(user_id, int):
        return resolve_lang(telegram_lang_code)
    cached = get_cached_lang(user_id)
    if cached:
        return cached
    try:
        from models.users import get_user_lang as _db_get
        db_lang = await _db_get(user_id)
        if db_lang and db_lang in SUPPORTED_LANGS:
            cache_user_lang(user_id, db_lang)
            return db_lang
    except Exception:
        pass
    return resolve_lang(telegram_lang_code)


async def set_lang(user_id: int, lang: str) -> None:
    """Persist lang to DB and update in-memory cache."""
    if not isinstance(user_id, int):
        return
    if lang not in SUPPORTED_LANGS:
        lang = "en"
    try:
        from models.users import set_user_lang as _db_set
        await _db_set(user_id, lang)
    except Exception:
        pass
    invalidate_user_lang(user_id)
    cache_user_lang(user_id, lang)


# ---------------------------------------------------------------------------
# aiogram 3 Middleware
# ---------------------------------------------------------------------------

class LanguageMiddleware(BaseMiddleware):
    """
    Middleware that resolves the user's preferred language from DB (or cache)
    and sets it in per-request ContextVars before the handler runs.
    Phase 6: Also tracks user_id via _user_id_ctx for AdminSessionI18nMiddleware.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            for _attr in ("callback_query", "message", "edited_message", "pre_checkout_query", "my_chat_member", "chat_member"):
                _sub = getattr(event, _attr, None)
                if _sub is not None and getattr(_sub, "from_user", None) is not None:
                    user = _sub.from_user
                    break
        uid = getattr(user, "id", None) if user is not None else None
        tg_code = getattr(user, "language_code", None) if user is not None else None

        lang = await get_lang(uid if isinstance(uid, int) else None, tg_code)
        lang_token = set_lang_ctx(lang)
        user_token = set_context_user_id(uid if isinstance(uid, int) else None)
        data["lang"] = lang

        try:
            return await handler(event, data)
        finally:
            reset_context_lang(lang_token)
            reset_context_user_id(user_token)
