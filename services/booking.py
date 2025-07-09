from typing import Optional
from loguru import logger

from database import DatabaseManager, WBAccount
from wb_api import WildberriesAPI, SupplySlot, BookingError
from .notification import NotificationService


class BookingService:
    """Service for booking supply slots"""
    
    def __init__(self, db: DatabaseManager, notification_service: NotificationService):
        self.db = db
        self.notification_service = notification_service
    
    async def book_slot(self, user_id: int, account: WBAccount, 
                       slot: SupplySlot, auto_booked: bool = False) -> bool:
        """Book a supply slot"""
        try:
            # Get user
            user = await self.db.get_user(account.user_id)
            if not user:
                logger.error(f"User {account.user_id} not found")
                return False
            
            # Try to book slot
            async with WildberriesAPI(account.api_key) as api:
                success = await api.book_slot(slot.id)
            
            if success:
                # Save booking to database
                await self.db.add_booked_slot(
                    user_id=user.id,
                    wb_account_id=account.id,
                    slot_data=slot.to_dict(),
                    auto_booked=auto_booked
                )
                
                # Send success notification
                await self.notification_service.notify_booking_success(
                    user_id=user.telegram_id,
                    slot=slot,
                    account_name=account.name,
                    auto_booked=auto_booked
                )
                
                logger.info(f"Successfully booked slot {slot.id} for user {user.id}")
                return True
            
            return False
            
        except BookingError as e:
            # Send error notification
            if user:
                await self.notification_service.notify_booking_error(
                    user_id=user.telegram_id,
                    error_message=str(e)
                )
            logger.error(f"Booking error: {e}")
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error booking slot: {e}")
            if user:
                await self.notification_service.notify_booking_error(
                    user_id=user.telegram_id,
                    error_message="Неизвестная ошибка при бронировании"
                )
            return False
    
    async def book_slot_by_id(self, user_id: int, slot_id: str) -> bool:
        """Book slot by ID (for callback handlers)"""
        try:
            # Get user with accounts
            user = await self.db.get_user_with_accounts(user_id)
            if not user or not user.wb_accounts:
                return False
            
            # Try to find and book slot with each account
            for account in user.wb_accounts:
                if not account.is_active:
                    continue
                
                try:
                    async with WildberriesAPI(account.api_key) as api:
                        # Get current slots
                        slots = await api.get_supply_slots()
                        
                        # Find the slot
                        slot = next((s for s in slots if s.id == slot_id), None)
                        if not slot:
                            continue
                        
                        # Try to book
                        return await self.book_slot(
                            user_id=user.id,
                            account=account,
                            slot=slot,
                            auto_booked=False
                        )
                        
                except Exception as e:
                    logger.error(f"Error checking account {account.id}: {e}")
                    continue
            
            # Slot not found or booking failed with all accounts
            await self.notification_service.notify_booking_error(
                user_id=user_id,
                error_message="Слот не найден или уже занят"
            )
            return False
            
        except Exception as e:
            logger.error(f"Error in book_slot_by_id: {e}")
            return False 