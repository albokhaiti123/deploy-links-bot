"""
Language switcher handler — /lang command and inline buttons.
Supports lang_menu_*, set_lang_<code>_<origin> callbacks for back-navigation.
"""

from aiogram import Router, F, types
from aiogram.filters import Command

from core.i18n import t, get_lang, set_lang, cache_user_lang, invalidate_user_lang, SUPPORTED_LANGS
from locales import SUPPORTED_LANGS  # noqa: F811

router = Router(name="language")

_ORIGIN_BACK = {
    "admin": "admin_main",
    "user":  "user_menu",
    "start": "start_back",
}


def _lang_keyboard(current_lang: str, origin: str | None = None) -> types.InlineKeyboardMarkup:
    buttons = []
    for code in SUPPORTED_LANGS:
        label_key = f"btn_lang_{code}"
        label = t(label_key, current_lang)
        marker = " ✓" if code == current_lang else ""
        cb = f"set_lang_{code}_{origin}" if origin else f"set_lang_{code}"
        buttons.append([types.InlineKeyboardButton(
            text=label + marker,
            callback_data=cb,
        )])
    if origin and origin in _ORIGIN_BACK:
        back_label = "🔙 رجوع" if current_lang == "ar" else "🔙 Back"
        buttons.append([types.InlineKeyboardButton(
            text=back_label,
            callback_data=_ORIGIN_BACK[origin],
        )])
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("lang"))
async def cmd_lang(message: types.Message):
    """Show language selection menu."""
    lang = await get_lang(message.from_user.id)
    text = t("lang_title", lang)
    await message.answer(text, reply_markup=_lang_keyboard(lang))


@router.callback_query(F.data.in_({"lang_menu", "lang_menu_start", "lang_menu_user", "lang_menu_admin"}))
async def cb_lang_menu(callback: types.CallbackQuery):
    """Show language selection from inline button in various panels."""
    _origin_map = {
        "lang_menu_admin": "admin",
        "lang_menu_user":  "user",
        "lang_menu_start": "start",
        "lang_menu":       "start",
    }
    origin = _origin_map.get(callback.data)
    lang = await get_lang(callback.from_user.id)
    text = t("lang_title", lang)
    try:
        await callback.message.edit_text(text, reply_markup=_lang_keyboard(lang, origin))
    except Exception:
        await callback.message.answer(text, reply_markup=_lang_keyboard(lang, origin))
    await callback.answer()


@router.callback_query(F.data.startswith("set_lang_"))
async def cb_set_lang(callback: types.CallbackQuery):
    """Handle language selection button press — format: set_lang_<code> or set_lang_<code>_<origin>."""
    parts = callback.data.split("set_lang_", 1)[1].split("_", 1)
    new_lang = parts[0]
    origin = parts[1] if len(parts) > 1 else None

    if new_lang not in SUPPORTED_LANGS:
        await callback.answer("Unsupported language.", show_alert=True)
        return

    user_id = callback.from_user.id

    # Persist in DB and in-memory cache
    await set_lang(user_id, new_lang)
    invalidate_user_lang(user_id)
    cache_user_lang(user_id, new_lang)

    confirmation = t("lang_changed", new_lang)
    await callback.answer(confirmation, show_alert=False)

    # Update the message keyboard to reflect new selection
    try:
        await callback.message.edit_text(
            t("lang_title", new_lang),
            reply_markup=_lang_keyboard(new_lang, origin),
        )
    except Exception:
        pass
