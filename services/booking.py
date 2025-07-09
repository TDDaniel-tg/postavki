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
            async with WildberriesAPI(account.api_key, force_demo=False) as api:
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
                    async with WildberriesAPI(account.api_key, force_demo=False) as api:
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
    
    async def auto_book_supply(self, user_id: int, account_id: int, supply_number: str) -> bool:
        """Automatically find and book supply slot based on user filters"""
        try:
            # Get user with accounts and filters
            user = await self.db.get_user_with_accounts(user_id)
            if not user:
                logger.error(f"User {user_id} not found")
                return False
            
            # Get specific account
            account = next((acc for acc in user.wb_accounts if acc.id == account_id), None)
            if not account or not account.is_active:
                logger.error(f"Account {account_id} not found or inactive")
                return False
            
            # Get user filters
            filters = await self.db.get_user_filters(user.id)
            
            logger.info(f"Starting auto booking for supply {supply_number}, user {user_id}, account {account.name}")
            
            # Get available slots from API
            async with WildberriesAPI(account.api_key, force_demo=False) as api:
                available_slots = await api.get_supply_slots(days_ahead=14)
            
            if not available_slots:
                logger.warning("No available slots found")
                return False
            
            # Filter slots based on user preferences
            suitable_slots = []
            
            for slot in available_slots:
                if not slot.is_available:
                    continue
                
                # Apply filters
                if filters:
                    # Filter by warehouses
                    if filters.warehouses:
                        allowed_warehouses = filters.warehouses
                        if slot.warehouse_id not in allowed_warehouses:
                            continue
                    
                    # Filter by regions
                    if filters.regions:
                        allowed_regions = filters.regions
                        if slot.region and slot.region not in allowed_regions:
                            continue
                    
                    # Filter by coefficient
                    if filters.min_coefficient is not None and slot.coefficient < filters.min_coefficient:
                        continue
                    if filters.max_coefficient is not None and slot.coefficient > filters.max_coefficient:
                        continue
                    
                    # Filter by time slots (simplified check)
                    if filters.time_slots:
                        allowed_times = filters.time_slots
                        slot_time = f"{slot.time_start}-{slot.time_end}"
                        if not any(time in slot_time for time in allowed_times):
                            continue
                
                suitable_slots.append(slot)
            
            if not suitable_slots:
                logger.warning("No suitable slots found after applying filters")
                return False
            
            # Sort slots by preference (earliest date, best coefficient)
            suitable_slots.sort(key=lambda x: (x.date, -x.coefficient))
            
            # Try to book the best slot
            best_slot = suitable_slots[0]
            
            logger.info(f"Found suitable slot: {best_slot.warehouse_name} on {best_slot.date} {best_slot.time_start}-{best_slot.time_end}")
            
            # Book the slot
            success = await self.book_slot(
                user_id=user.id,
                account=account,
                slot=best_slot,
                auto_booked=True
            )
            
            if success:
                # Update booking record with supply number
                await self.db.update_booked_slot_supply_number(
                    user_id=user.id,
                    slot_id=best_slot.id,
                    supply_number=supply_number
                )
                
                logger.info(f"Successfully auto-booked supply {supply_number} to slot {best_slot.id}")
                return True
            else:
                logger.warning(f"Failed to book slot {best_slot.id}")
                return False
            
        except Exception as e:
            logger.error(f"Error in auto_book_supply: {e}")
            return False 