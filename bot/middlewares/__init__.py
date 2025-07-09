from aiogram import Dispatcher

from .auth import DatabaseMiddleware, BookingServiceMiddleware


def setup_middlewares(dp: Dispatcher, db, booking_service):
    """Setup all middlewares"""
    # Add database middleware
    dp.message.middleware(DatabaseMiddleware(db))
    dp.callback_query.middleware(DatabaseMiddleware(db))
    
    # Add booking service middleware
    dp.callback_query.middleware(BookingServiceMiddleware(booking_service)) 