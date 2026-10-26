"""
Payment handlers — pre-checkout query and successful payment processing.
"""

from aiogram import Router, F, types
from aiogram.enums import ParseMode

from core.bot import bot
from models.settings import get_setting

router = Router(name="payments")


@router.pre_checkout_query(lambda query: query.invoice_payload == "paid_promo")
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    if message.successful_payment.invoice_payload == "paid_promo":
        post_msg = await get_setting("promo_post_payment_msg")
        if not post_msg:
            post_msg = "✅ Payment confirmed successfully!"
        try:
            await message.reply(
                f"⭐️ <b>Payment Confirmed!</b>\n\n{post_msg}",
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            from core.logging_config import logger
            logger.error(f"Failed to send post payment msg: {e}")
