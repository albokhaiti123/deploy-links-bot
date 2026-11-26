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


class UserCampaignEdit(StatesGroup):
    """Phase 8: Live-edit states for an already-active campaign (zero quota)."""
    menu = State()
    text = State()
    photo = State()
    buttons = State()
    button_label = State()
    button_url = State()
    groups = State()
    mode = State()
    custom_hours = State()
    auto_delete = State()
