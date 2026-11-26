"""
Locales package — multi-language support for Deploy Links Bot.
Supported languages: ar (Arabic), en (English — default/fallback).
"""

from locales.ar import STRINGS as AR_STRINGS
from locales.en import STRINGS as EN_STRINGS

_LOCALES: dict[str, dict[str, str]] = {
    "ar": AR_STRINGS,
    "en": EN_STRINGS,
}

SUPPORTED_LANGS = list(_LOCALES.keys())


def get_strings(lang: str) -> dict[str, str]:
    """Return the string dictionary for the given language code (falls back to 'en')."""
    return _LOCALES.get(lang, _LOCALES["en"])


def t(key: str, lang: str, **kwargs) -> str:
    """
    Translate a key into the target language with optional format substitutions.
    Falls back to English if the key or language is missing.
    """
    strings = get_strings(lang)
    template = strings.get(key) or _LOCALES["en"].get(key, key)
    try:
        return template.format(**kwargs) if kwargs else template
    except (KeyError, IndexError):
        return template
