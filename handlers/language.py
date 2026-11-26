"""
Language switcher handler — /lang command and inline buttons.
"""

from aiogram import Router, F, types
from aiogram.filters import Command

from core.i18n import t, cache_user_lang, invalidate_user_lang, SUPPORTED_LANGS
from locales import SUPPORTED_LANGS  # noqa: F811

router = Router(name="language")


def _lang_keyboard(current_lang: str) -> types.InlineKeyboardMarkup:
    buttons = []
    for code in SUPPORTED_LANGS:
        label_key = f"btn_lang_{code}"
        label = t(label_key, current_lang)
        marker = " ✓" if code == current_lang else ""
        buttons.append([types.InlineKeyboardButton(
            text=label + marker,
            callback_data=f"set_lang_{code}",
        )])
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("lang"))
async def cmd_lang(message: types.Message):
    """Show language selection menu."""
    from core.i18n import resolve_lang
    try:
        from models.users import get_user_lang as _get_user_lang
        lang = await _get_user_lang(message.from_user.id) or "en"
    except Exception:
        lang = resolve_lang(getattr(message.from_user, "language_code", None))

    text = t("lang_title", lang)
    await message.answer(text, reply_markup=_lang_keyboard(lang))


@router.callback_query(F.data.startswith("set_lang_"))
async def cb_set_lang(callback: types.CallbackQuery):
    """Handle language selection button press."""
    new_lang = callback.data.split("set_lang_")[1]
    if new_lang not in SUPPORTED_LANGS:
        await callback.answer("Unsupported language.", show_alert=True)
        return

    user_id = callback.from_user.id

    # Persist in DB
    try:
        from models.users import set_user_lang as _set_user_lang
        await _set_user_lang(user_id, new_lang)
    except Exception:
        pass

    # Update in-memory cache
    invalidate_user_lang(user_id)
    cache_user_lang(user_id, new_lang)

    confirmation = t("lang_changed", new_lang)
    await callback.answer(confirmation, show_alert=False)

    # Update the message keyboard to reflect new selection
    try:
        await callback.message.edit_text(
            t("lang_title", new_lang),
            reply_markup=_lang_keyboard(new_lang),
        )
    except Exception:
        pass
