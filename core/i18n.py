"""
i18n engine for Deploy Links Bot (aiogram 3).

Usage:
    from core.i18n import t, get_lang, set_lang_ctx, LanguageMiddleware

    # In a handler:
    lang = get_lang(update.from_user)
    text = t("btn_my_referral", lang)
"""

from contextvars import ContextVar
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from locales import t as _t, SUPPORTED_LANGS

# Per-request context variable — holds the resolved language for the current request
_lang_ctx: ContextVar[str] = ContextVar("lang", default="en")


def get_lang_ctx() -> str:
    """Return the language set for the current async context (default 'en')."""
    return _lang_ctx.get()


def set_lang_ctx(lang: str) -> None:
    """Set the language for the current async context."""
    _lang_ctx.set(lang if lang in SUPPORTED_LANGS else "en")


def resolve_lang(language_code: str | None) -> str:
    """
    Resolve a Telegram language_code (e.g. 'ar', 'ar-SA', 'en-US') to a supported lang key.
    Falls back to 'en' if not supported.
    """
    if not language_code:
        return "en"
    code = language_code.split("-")[0].lower()
    return code if code in SUPPORTED_LANGS else "en"


def get_lang(user) -> str:
    """
    Get the language for a Telegram user object.
    Checks the per-request context first (set by LanguageMiddleware from DB),
    then falls back to the user's Telegram language_code.
    """
    ctx_lang = _lang_ctx.get()
    if ctx_lang and ctx_lang != "en":
        # Non-default context means middleware set it from DB
        return ctx_lang
    # Fallback: use Telegram's reported language_code
    return resolve_lang(getattr(user, "language_code", None))


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
# aiogram 3 Middleware
# ---------------------------------------------------------------------------
class LanguageMiddleware(BaseMiddleware):
    """
    Middleware that resolves the user's preferred language from the DB (or cache)
    and sets it in the per-request ContextVar before the handler runs.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user:
            lang = await self._resolve(user)
            set_lang_ctx(lang)
            data["lang"] = lang
        return await handler(event, data)

    @staticmethod
    async def _resolve(user) -> str:
        """Resolve user lang: cache → DB → Telegram language_code → 'en'."""
        uid = user.id
        cached = get_cached_lang(uid)
        if cached:
            return cached

        # Try to load from DB
        try:
            from models.users import get_user_lang as _get_user_lang
            db_lang = await _get_user_lang(uid)
            if db_lang and db_lang in SUPPORTED_LANGS:
                cache_user_lang(uid, db_lang)
                return db_lang
        except Exception:
            pass

        # Fallback: Telegram reported language_code
        lang = resolve_lang(getattr(user, "language_code", None))
        return lang
