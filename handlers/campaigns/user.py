"""
Campaign user handlers — verify groups, unlock content.
"""

from aiogram import Router, F, types

from services.campaign import verify_campaign_groups, deliver_unlock_content

router = Router(name="campaigns_user")


@router.callback_query(F.data.startswith("camp_verify_"))
async def cb_camp_verify(callback: types.CallbackQuery):
    campaign_id = int(callback.data.split("_")[-1])
    await verify_campaign_groups(callback, campaign_id)


@router.callback_query(F.data.startswith("camp_unlock_"))
async def cb_camp_unlock(callback: types.CallbackQuery):
    campaign_id = int(callback.data.split("_")[-1])
    await deliver_unlock_content(callback, campaign_id)
