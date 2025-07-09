from aiogram import Dispatcher

from .auth import DatabaseMiddleware, BookingServiceMiddleware


def setup_middlewares(dp: Dispatcher, db, booking_service, supply_finder_service=None):
    """Setup all middlewares"""
    # Add database middleware
    dp.message.middleware(DatabaseMiddleware(db))
    dp.callback_query.middleware(DatabaseMiddleware(db))
    
    # Add booking service middleware
    dp.callback_query.middleware(BookingServiceMiddleware(booking_service))
    
    # Add supply finder service middleware 
    if supply_finder_service:
        from .auth import SupplyFinderMiddleware
        dp.message.middleware(SupplyFinderMiddleware(supply_finder_service))
        dp.callback_query.middleware(SupplyFinderMiddleware(supply_finder_service)) 