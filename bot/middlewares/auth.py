from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class DatabaseMiddleware(BaseMiddleware):
    """Middleware to inject database into handlers"""
    
    def __init__(self, db):
        self.db = db
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        data["db"] = self.db
        return await handler(event, data)


class BookingServiceMiddleware(BaseMiddleware):
    """Middleware to inject booking service into handlers"""
    
    def __init__(self, booking_service):
        self.booking_service = booking_service
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        data["booking_service"] = self.booking_service
        return await handler(event, data)


class SupplyFinderMiddleware(BaseMiddleware):
    """Middleware to inject supply finder service into handlers"""
    
    def __init__(self, supply_finder_service):
        self.supply_finder_service = supply_finder_service
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        data["supply_finder"] = self.supply_finder_service
        return await handler(event, data) 