"""
FSM State definitions for all multi-step admin wizards.

Moved verbatim from the original bot.py (lines 218-255).
"""

from aiogram.fsm.state import StatesGroup, State


class AdminEdit(StatesGroup):
    """States for single-field admin editing operations."""
    waiting_for_promo_text = State()
    waiting_for_promo_url = State()
    waiting_for_promo_button = State()
    waiting_for_cooldown = State()
    waiting_for_admin_id = State()
    waiting_for_media = State()
    waiting_for_start_msg = State()
    waiting_for_start_btn2_name = State()
    waiting_for_start_btn2_url = State()
    waiting_for_start_btn2_text = State()
    waiting_for_promo_stars = State()
    waiting_for_post_payment_msg = State()
    waiting_for_test_group = State()
    waiting_for_start_media = State()
    waiting_for_rbw_text = State()
    waiting_for_rbw_hours = State()


class BroadcastWizard(StatesGroup):
    """States for the broadcast creation wizard."""
    target = State()
    text = State()
    media = State()
    media_type_vip = State()
    stars = State()
    duration = State()
    confirm = State()


class CampaignWizard(StatesGroup):
    """States for the campaign creation wizard."""
    name = State()
    promo_text = State()
    media = State()
    button_text = State()
    required_groups = State()
    unlock_content = State()
    unlock_media = State()
    unlock_delete = State()
    mode_select = State()
    repeat_hours = State()
    confirm = State()
