"""
Handler registration — collects all routers and includes them into the dispatcher.
Phase 5: Added LanguageMiddleware and language_router.
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
from handlers.admin.user_management import router as admin_user_mgmt_router
from handlers.user.my_groups import router as user_groups_router
from handlers.user.my_campaign import router as user_campaign_router
from handlers.user.dashboard_pro import router as dashboard_pro_router
from handlers.admin.invite_links import router as invite_links_router
from handlers.language import router as language_router
from core.i18n import LanguageMiddleware


def register_all_routers(dp: Dispatcher) -> None:
    """Register all handler routers with the dispatcher."""
    # Phase 5: register language middleware globally
    dp.update.middleware(LanguageMiddleware())

    dp.include_routers(
        # Language switcher — register first so /lang is always available
        language_router,
        # Core user handlers
        start_router,
        payments_router,
        groups_router,
        campaigns_user_router,
        # User feature handlers
        user_groups_router,
        user_campaign_router,
        dashboard_pro_router,
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
        admin_user_mgmt_router,
        invite_links_router,
    )

