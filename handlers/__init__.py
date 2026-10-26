"""
Handler registration — collects all routers and includes them into the dispatcher.
"""

from aiogram import Dispatcher

from handlers.start import router as start_router
from handlers.payments import router as payments_router
from handlers.groups import router as groups_router
from handlers.campaigns.user import router as campaigns_user_router
from handlers.admin.panel import router as admin_panel_router
from handlers.admin.promo_settings import router as admin_promo_router
from handlers.admin.general_settings import router as admin_general_router
from handlers.admin.welcome_settings import router as admin_welcome_router
from handlers.admin.broadcast import router as admin_broadcast_router
from handlers.admin.recurring import router as admin_recurring_router
from handlers.admin.stats import router as admin_stats_router
from handlers.admin.admins import router as admin_admins_router
from handlers.admin.campaigns import router as admin_campaigns_router
from handlers.admin.button_manager import router as admin_button_manager_router


def register_all_routers(dp: Dispatcher) -> None:
    """Register all handler routers with the dispatcher."""
    dp.include_routers(
        # Core user handlers
        start_router,
        payments_router,
        groups_router,
        campaigns_user_router,
        # Admin handlers
        admin_panel_router,
        admin_promo_router,
        admin_general_router,
        admin_welcome_router,
        admin_broadcast_router,
        admin_recurring_router,
        admin_stats_router,
        admin_admins_router,
        admin_campaigns_router,
        admin_button_manager_router,
    )
