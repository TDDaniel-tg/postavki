import asyncio
from typing import List, Dict, Set, Optional
from datetime import datetime
from loguru import logger

from config import settings
from database import DatabaseManager, User, UserFilters
from wb_api import WildberriesAPI, SupplySlot
from .notification import NotificationService
from .booking import BookingService


class SupplyMonitor:
    """Service for monitoring supply slots"""
    
    def __init__(self, db: DatabaseManager, notification_service: NotificationService,
                 booking_service: BookingService):
        self.db = db
        self.notification_service = notification_service
        self.booking_service = booking_service
        self.active_users: Set[int] = set()
        self.last_slots: Dict[int, Dict[str, Set[str]]] = {}  # user_id -> account_id -> slot_ids
        self.monitoring_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        
    async def start(self):
        """Start monitoring"""
        if self.monitoring_task and not self.monitoring_task.done():
            logger.warning("Monitoring already running")
            return
            
        self._stop_event.clear()
        self.monitoring_task = asyncio.create_task(self._monitor_loop())
        logger.info("Supply monitoring started")
    
    async def stop(self):
        """Stop monitoring"""
        self._stop_event.set()
        if self.monitoring_task:
            await self.monitoring_task
        logger.info("Supply monitoring stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        while not self._stop_event.is_set():
            try:
                # Get active users
                active_users = await self.db.get_active_users()
                
                # Update active users set
                self.active_users = {user.id for user in active_users}
                
                # Check slots for each user
                for user in active_users:
                    if self._stop_event.is_set():
                        break
                    
                    try:
                        await self._check_user_slots(user)
                    except Exception as e:
                        logger.error(f"Error checking slots for user {user.id}: {e}")
                
                # Wait before next check
                await asyncio.sleep(settings.MONITORING_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(settings.MONITORING_INTERVAL)
    
    async def _check_user_slots(self, user: User):
        """Check slots for specific user"""
        if not user.wb_accounts:
            return
        
        # Initialize user in last_slots if needed
        if user.id not in self.last_slots:
            self.last_slots[user.id] = {}
        
        # Check each WB account
        for account in user.wb_accounts:
            if not account.is_active:
                continue
            
            try:
                # Get current slots
                async with WildberriesAPI(account.api_key, force_demo=False) as api:
                    current_slots = await api.get_supply_slots()
                
                # Apply user filters
                filtered_slots = await self._apply_filters(current_slots, user.filters)
                
                # Find new slots
                account_id = str(account.id)
                last_slot_ids = self.last_slots[user.id].get(account_id, set())
                current_slot_ids = {slot.id for slot in filtered_slots}
                new_slot_ids = current_slot_ids - last_slot_ids
                
                # Update last slots
                self.last_slots[user.id][account_id] = current_slot_ids
                
                # Process new slots
                if new_slot_ids:
                    new_slots = [slot for slot in filtered_slots if slot.id in new_slot_ids]
                    await self._process_new_slots(user, account, new_slots)
                
            except Exception as e:
                logger.error(f"Error checking account {account.id}: {e}")
    
    async def _apply_filters(self, slots: List[SupplySlot], 
                           filters: Optional[UserFilters]) -> List[SupplySlot]:
        """Apply user filters to slots"""
        if not filters:
            return slots
        
        filtered = []
        for slot in slots:
            # Check warehouse filter
            if filters.warehouses and slot.warehouse_id not in filters.warehouses:
                continue
            
            # Check region filter
            if filters.regions and slot.region not in filters.regions:
                continue
            
            # Check coefficient filter
            if slot.coefficient < filters.min_coefficient:
                continue
            
            if filters.max_coefficient and slot.coefficient > filters.max_coefficient:
                continue
            
            # Check time slots filter
            if filters.time_slots:
                slot_hour = int(slot.time_start.split(':')[0])
                if not any(
                    time_range["start"] <= slot_hour < time_range["end"]
                    for time_range in filters.time_slots
                ):
                    continue
            
            # Check quiet hours
            if filters.notifications_enabled and filters.quiet_hours_start is not None:
                current_hour = datetime.now().hour
                if filters.quiet_hours_end is not None:
                    if filters.quiet_hours_start <= filters.quiet_hours_end:
                        # Normal range (e.g., 22-06)
                        if filters.quiet_hours_start <= current_hour < filters.quiet_hours_end:
                            continue
                    else:
                        # Overnight range (e.g., 22-06)
                        if current_hour >= filters.quiet_hours_start or current_hour < filters.quiet_hours_end:
                            continue
            
            filtered.append(slot)
        
        return filtered
    
    async def _process_new_slots(self, user: User, account, slots: List[SupplySlot]):
        """Process new slots for user"""
        logger.info(f"Found {len(slots)} new slots for user {user.id}")
        
        # Check auto booking
        if user.filters and user.filters.auto_booking_enabled:
            # Get today's bookings count
            today_bookings = await self._get_today_bookings_count(user.id)
            remaining_limit = user.filters.auto_booking_limit - today_bookings
            
            if remaining_limit > 0:
                # Sort slots by coefficient (descending)
                slots_to_book = sorted(slots, key=lambda s: s.coefficient, reverse=True)
                
                # Try to book best slots
                for slot in slots_to_book[:remaining_limit]:
                    success = await self.booking_service.book_slot(
                        user_id=user.id,
                        account=account,
                        slot=slot,
                        auto_booked=True
                    )
                    
                    if success:
                        remaining_limit -= 1
                        # Remove from notification list
                        slots = [s for s in slots if s.id != slot.id]
                        
                        if remaining_limit <= 0:
                            break
        
        # Send notifications for remaining slots
        if slots and user.filters and user.filters.notifications_enabled:
            await self.notification_service.notify_new_slots(
                user_id=user.telegram_id,
                account_name=account.name,
                slots=slots
            )
    
    async def _get_today_bookings_count(self, user_id: int) -> int:
        """Get count of today's bookings for user"""
        # This should query the database for today's bookings
        # For now, return 0
        return 0
    
    def get_monitoring_status(self) -> Dict[str, any]:
        """Get monitoring status"""
        return {
            "is_running": self.monitoring_task and not self.monitoring_task.done(),
            "active_users": len(self.active_users),
            "interval": settings.MONITORING_INTERVAL
        }