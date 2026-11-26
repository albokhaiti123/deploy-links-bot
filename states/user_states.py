"""
User campaign FSM states.
"""

from aiogram.fsm.state import StatesGroup, State


class UserCampaignWizard(StatesGroup):
    """6-step wizard: text → photo → buttons → groups → mode → auto_delete → confirm."""
    text = State()
    photo = State()
    buttons = State()
    groups = State()
    mode = State()
    confirm = State()
    # Phase 7 new states
    button_label = State()
    button_url = State()
    auto_delete = State()
    custom_hours = State()
