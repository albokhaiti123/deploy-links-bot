"""
Media service — unified helper for sending text/photo/video messages.

Eliminates the 8+ duplicated if/elif branches scattered across the old bot.py.
Every module that needs to send a message with optional media calls this.
"""

from aiogram import Bot, types
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    InlineKeyboardMarkup,
    InputPaidMediaPhoto,
    InputPaidMediaVideo,
)

from core.logging_config import logger


async def send_media_message(
    bot: Bot,
    chat_id: int,
    text: str,
    *,
    media_id: str | None = None,
    media_type: str | None = None,
    keyboard: InlineKeyboardMarkup | None = None,
    parse_mode: str = ParseMode.HTML,
    is_vip: bool = False,
    stars: int = 0,
    reply_to: int | None = None,
) -> types.Message | None:
    """
    Send a message with optional media to a chat.

    Handles all combinations:
      - Text only
      - Photo + caption
      - Video + caption
      - VIP paid photo/video (Telegram Stars)
      - VIP text-only invoice

    Returns the sent Message object (or None if VIP paid-media which has no direct return).
    """
    # ── VIP (paid content) ──
    if is_vip:
        if media_id:
            if media_type == "photo":
                media_payload = [InputPaidMediaPhoto(media=media_id)]
            else:
                media_payload = [InputPaidMediaVideo(media=media_id)]
            try:
                sent = await bot.send_paid_media(
                    chat_id=chat_id,
                    star_count=stars,
                    media=media_payload,
                    caption=text,
                    parse_mode=parse_mode,
                )
            except TelegramBadRequest as e:
                if "can't parse entities" in str(e).lower():
                    logger.warning(f"HTML parse error in VIP media for {chat_id}, retrying without formatting")
                    sent = await bot.send_paid_media(
                        chat_id=chat_id,
                        star_count=stars,
                        media=media_payload,
                        caption=text,
                    )
                else:
                    raise
            return sent
        else:
            # Text-only VIP → send text first, then invoice reply
            try:
                text_msg = await bot.send_message(
                    chat_id, text,
                    reply_markup=keyboard,
                    parse_mode=parse_mode,
                )
            except TelegramBadRequest as e:
                if "can't parse entities" in str(e).lower():
                    logger.warning(f"HTML parse error in VIP text for {chat_id}, retrying without formatting")
                    text_msg = await bot.send_message(
                        chat_id, text,
                        reply_markup=keyboard,
                    )
                else:
                    raise
            prices = [types.LabeledPrice(label="Unlock Secret Content", amount=stars)]
            invoice_msg = await bot.send_invoice(
                chat_id=chat_id,
                title="VIP Paid Content",
                description="Pay Stars to receive the post-payment message instantly.",
                payload="paid_promo",
                provider_token="",
                currency="XTR",
                prices=prices,
                reply_to_message_id=text_msg.message_id,
            )
            return text_msg

    # ── Normal (free content) ──
    try:
        if media_id and media_type == "photo":
            return await bot.send_photo(
                chat_id, photo=media_id, caption=text,
                reply_markup=keyboard, parse_mode=parse_mode,
            )
        elif media_id and media_type == "video":
            return await bot.send_video(
                chat_id, video=media_id, caption=text,
                reply_markup=keyboard, parse_mode=parse_mode,
            )
        else:
            return await bot.send_message(
                chat_id, text,
                reply_markup=keyboard,
                parse_mode=parse_mode,
                link_preview_options=types.LinkPreviewOptions(is_disabled=True),
            )
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e).lower():
            logger.warning(f"HTML parse error in chat {chat_id}, retrying without formatting: {e}")
            # Retry without parse_mode
            if media_id and media_type == "photo":
                return await bot.send_photo(
                    chat_id, photo=media_id, caption=text,
                    reply_markup=keyboard,
                )
            elif media_id and media_type == "video":
                return await bot.send_video(
                    chat_id, video=media_id, caption=text,
                    reply_markup=keyboard,
                )
            else:
                return await bot.send_message(
                    chat_id, text,
                    reply_markup=keyboard,
                    link_preview_options=types.LinkPreviewOptions(is_disabled=True),
                )
        raise  # Re-raise non-HTML errors
