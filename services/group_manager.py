"""
Group manager service — error classification, health updates, group leave operations.

classify_telegram_error() is the single source of truth for Telegram error handling.
Used by broadcast.py, campaign.py, promo.py, and user_broadcast.py.
"""

from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramBadRequest,
    TelegramRetryAfter,
    TelegramNetworkError,
    TelegramServerError,
    TelegramAPIError,
)

from core.bot import bot
from core.config import ADMIN_ID
from core.logging_config import logger
from models.groups import deactivate_group, update_group_health, get_group_by_id


def classify_telegram_error(e: Exception) -> tuple[str, bool, bool]:
    """
    Returns (health_status, should_deactivate, is_temporary).

    health_status: one of 'banned','left','no_permission','upgraded','unreachable','unknown'
    should_deactivate: True means set group status=inactive
    is_temporary: True means do NOT change health status (rate limits, network)
    """
    msg = str(e).lower()

    if isinstance(e, TelegramForbiddenError):
        if "bot was kicked" in msg or "chat not found" in msg or "not a member" in msg:
            return ("banned", True, False)
        return ("banned", True, False)

    if isinstance(e, TelegramBadRequest):
        if "upgraded to a supergroup" in msg:
            return ("upgraded", True, False)
        if "not enough rights" in msg or "need administrator rights" in msg:
            return ("no_permission", False, False)
        if "chat not found" in msg or "bot is not a member" in msg:
            return ("left", True, False)
        return ("unknown", False, False)

    if isinstance(e, TelegramRetryAfter):
        return ("ok", False, True)  # Temporary — do not change health

    if isinstance(e, TelegramNetworkError):
        return ("unreachable", False, True)  # Temporary

    if isinstance(e, TelegramServerError):
        return ("unknown", False, True)  # Temporary

    return ("unknown", False, True)


async def handle_send_error(chat_id: int, e: Exception) -> None:
    """Apply health classification and optionally deactivate group."""
    health_status, should_deactivate, is_temporary = classify_telegram_error(e)

    if is_temporary:
        await update_group_health(chat_id, health_status or "unreachable",
                                  str(e)[:200], increment_fail=True)
        return

    if should_deactivate:
        await deactivate_group(chat_id)
        await update_group_health(chat_id, health_status, str(e)[:200], increment_fail=False)
        logger.info(f"Group {chat_id} deactivated: {health_status} — {e}")
    else:
        await update_group_health(chat_id, health_status, str(e)[:200], increment_fail=True)
        logger.info(f"Group {chat_id} health={health_status}: {e}")


async def leave_group(chat_id: int, requesting_user_id: int) -> tuple[bool, str]:
    """
    Leave a group. Authorization:
    - ADMIN_ID: can leave any group.
    - Ordinary user: must be reward_owner_id of the group.
    Returns (success, message).
    """
    group = await get_group_by_id(chat_id)
    if not group:
        return False, "Group not found in registry."

    # group: (chat_id, title, status, health_status, reward_owner_id, added_by, fail_count)
    reward_owner_id = group[4]

    if requesting_user_id != ADMIN_ID and requesting_user_id != reward_owner_id:
        return False, "You are not authorized to remove this group."

    try:
        await bot.leave_chat(chat_id)
        await deactivate_group(chat_id)
        await update_group_health(chat_id, "left", "Bot left by user request")
        logger.info(f"Bot left group {chat_id} at request of user {requesting_user_id}")
        return True, "Bot successfully removed from the group."
    except TelegramForbiddenError:
        # Bot already removed
        await deactivate_group(chat_id)
        await update_group_health(chat_id, "banned", "Bot already removed")
        return True, "Bot was already removed from the group."
    except Exception as e:
        logger.error(f"Failed to leave group {chat_id}: {e}")
        return False, f"Error: {e}"
