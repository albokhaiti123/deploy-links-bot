"""
User campaign FSM states.
"""

from aiogram.fsm.state import StatesGroup, State


class UserCampaignWizard(StatesGroup):
    """5-step wizard: text → photo → buttons → groups → mode → confirm."""
    text = State()
    photo = State()
    buttons = State()
    groups = State()
    mode = State()
    confirm = State()
