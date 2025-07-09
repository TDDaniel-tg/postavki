from aiogram import Router

from .start import router as start_router
from .account import router as account_router
from .settings import router as settings_router
from .booking import router as booking_router


def setup_handlers() -> Router:
    """Setup all handlers"""
    router = Router()
    
    # Include all routers
    router.include_router(start_router)
    router.include_router(account_router)
    router.include_router(settings_router)
    router.include_router(booking_router)
    
    return router 