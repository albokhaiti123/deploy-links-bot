"""
Group event handlers — bot added/removed from groups, new member joins.
"""

from aiogram import Router, F, types
from aiogram.enums import ChatType
from aiogram.filters import IS_MEMBER, IS_NOT_MEMBER, ChatMemberUpdatedFilter
from aiogram.types import ChatMemberUpdated

from core.bot import bot
from core.logging_config import logger
from models.groups import upsert_group, deactivate_group
from services.promo import trigger_group_promo

router = Router(name="groups")


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=IS_NOT_MEMBER >> IS_MEMBER))
async def bot_added_to_group(event: ChatMemberUpdated):
    chat = event.chat
    if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await upsert_group(
            chat_id=chat.id,
            title=chat.title,
            chat_type=chat.type,
            added_by=event.from_user.id,
        )
        logger.info(f"Bot added to group {chat.title} ({chat.id})")


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=IS_MEMBER >> IS_NOT_MEMBER))
async def bot_removed_from_group(event: ChatMemberUpdated):
    chat = event.chat
    await deactivate_group(chat.id)
    logger.info(f"Bot removed from group {chat.title} ({chat.id})")


@router.message(F.new_chat_members)
async def new_chat_member_handler(message: types.Message):
    bot_info = await bot.get_me()

    has_real_users = False
    new_member = None
    for member in message.new_chat_members:
        if member.id != bot_info.id:
            has_real_users = True
            new_member = member

    if not has_real_users or not new_member:
        return

    await trigger_group_promo(message, new_member)
