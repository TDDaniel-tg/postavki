import asyncio
from typing import Optional, List
from datetime import datetime, timedelta
from loguru import logger

from database import DatabaseManager
from wb_api import WildberriesAPI, SupplySlot
from services.booking import BookingService
from services.notification import NotificationService


class SupplyFinderService:
    """Service for continuous supply slot finding and booking"""
    
    def __init__(self, db: DatabaseManager, booking_service: BookingService, notification_service: NotificationService):
        self.db = db
        self.booking_service = booking_service
        self.notification_service = notification_service
        self.active_searches = {}  # user_id -> search task
        self.search_interval = 30  # Интервал поиска в секундах
        
    async def start_supply_search(self, user_id: int, account_id: int, supply_number: str) -> bool:
        """Start continuous search for supply slots"""
        try:
            # Stop existing search if any
            await self.stop_supply_search(user_id)
            
            # Get user and account
            user = await self.db.get_user_with_accounts(user_id)
            if not user:
                logger.error(f"User {user_id} not found")
                return False
            
            account = next((acc for acc in user.wb_accounts if acc.id == account_id), None)
            if not account or not account.is_active:
                logger.error(f"Account {account_id} not found or inactive")
                return False
            
            # Create search task
            task = asyncio.create_task(
                self._continuous_search(user_id, account_id, supply_number)
            )
            self.active_searches[user_id] = {
                'task': task,
                'supply_number': supply_number,
                'account_id': account_id,
                'started_at': datetime.now()
            }
            
            logger.info(f"Started continuous search for supply {supply_number}, user {user_id}")
            
            # Notify user about search start
            await self.notification_service.send_message(
                user_id=user_id,
                message=(
                    f"🔍 **Поиск слота запущен**\n\n"
                    f"📦 **Поставка**: {supply_number}\n"
                    f"💼 **Аккаунт**: {account.name}\n\n"
                    f"⏰ Поиск подходящих слотов каждые {self.search_interval} секунд\n"
                    f"🎯 Как только найдется подходящий слот - автоматически забронирую!\n\n"
                    f"❌ Для остановки поиска используйте кнопку 'Остановить поиск'"
                ),
                parse_mode="Markdown"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting supply search: {e}")
            return False
    
    async def stop_supply_search(self, user_id: int) -> bool:
        """Stop continuous search for user"""
        try:
            if user_id in self.active_searches:
                search_info = self.active_searches[user_id]
                search_info['task'].cancel()
                
                try:
                    await search_info['task']
                except asyncio.CancelledError:
                    pass
                
                del self.active_searches[user_id]
                
                # Calculate search duration
                duration = datetime.now() - search_info['started_at']
                hours = int(duration.total_seconds() // 3600)
                minutes = int((duration.total_seconds() % 3600) // 60)
                
                # Notify user about search stop
                await self.notification_service.send_message(
                    user_id=user_id,
                    message=(
                        f"⏹️ **Поиск остановлен**\n\n"
                        f"📦 **Поставка**: {search_info['supply_number']}\n"
                        f"⏱️ **Время поиска**: {hours}ч {minutes}м\n\n"
                        f"💡 Можете запустить новый поиск через меню"
                    ),
                    parse_mode="Markdown"
                )
                
                logger.info(f"Stopped supply search for user {user_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error stopping supply search: {e}")
            return False
    
    async def _continuous_search(self, user_id: int, account_id: int, supply_number: str):
        """Continuous search loop"""
        search_attempts = 0
        
        try:
            while True:
                search_attempts += 1
                logger.debug(f"Search attempt #{search_attempts} for supply {supply_number}")
                
                try:
                    # Try to find and book slot
                    success = await self.booking_service.auto_book_supply(
                        user_id=user_id,
                        account_id=account_id,
                        supply_number=supply_number
                    )
                    
                    if success:
                        # Booking successful - stop search
                        logger.info(f"Successfully booked supply {supply_number} after {search_attempts} attempts")
                        
                        # Remove from active searches
                        if user_id in self.active_searches:
                            del self.active_searches[user_id]
                        
                        # Notify about successful booking
                        await self.notification_service.send_message(
                            user_id=user_id,
                            message=(
                                f"✅ **Поставка забронирована!**\n\n"
                                f"📦 **Номер поставки**: {supply_number}\n"
                                f"🔢 **Попыток поиска**: {search_attempts}\n\n"
                                f"🎉 Поиск завершен успешно!"
                            ),
                            parse_mode="Markdown"
                        )
                        
                        break
                    
                    else:
                        # No suitable slot found, continue searching
                        logger.debug(f"No suitable slot found for supply {supply_number}, attempt #{search_attempts}")
                        
                        # Send periodic status update (every 10 attempts)
                        if search_attempts % 10 == 0:
                            await self.notification_service.send_message(
                                user_id=user_id,
                                message=(
                                    f"🔍 **Поиск продолжается...**\n\n"
                                    f"📦 **Поставка**: {supply_number}\n"
                                    f"🔢 **Попыток**: {search_attempts}\n"
                                    f"⏰ **Последняя проверка**: {datetime.now().strftime('%H:%M:%S')}\n\n"
                                    f"💡 Продолжаю искать подходящие слоты..."
                                ),
                                parse_mode="Markdown"
                            )
                    
                except Exception as e:
                    logger.error(f"Error in search attempt #{search_attempts}: {e}")
                    
                    # Send error notification (every 20 failed attempts)
                    if search_attempts % 20 == 0:
                        await self.notification_service.send_message(
                            user_id=user_id,
                            message=(
                                f"⚠️ **Проблемы с поиском**\n\n"
                                f"📦 **Поставка**: {supply_number}\n"
                                f"❌ **Ошибок**: {search_attempts}\n\n"
                                f"🔄 Продолжаю попытки поиска...\n"
                                f"📞 Если проблема не решается - обратитесь в поддержку"
                            ),
                            parse_mode="Markdown"
                        )
                
                # Wait before next attempt
                await asyncio.sleep(self.search_interval)
                
        except asyncio.CancelledError:
            logger.info(f"Search cancelled for supply {supply_number}")
            raise
        except Exception as e:
            logger.error(f"Fatal error in continuous search: {e}")
            
            # Notify about fatal error
            await self.notification_service.send_message(
                user_id=user_id,
                message=(
                    f"❌ **Критическая ошибка поиска**\n\n"
                    f"📦 **Поставка**: {supply_number}\n"
                    f"🔢 **Попыток до ошибки**: {search_attempts}\n\n"
                    f"💭 **Ошибка**: {str(e)[:100]}...\n\n"
                    f"🔄 Попробуйте запустить поиск заново"
                ),
                parse_mode="Markdown"
            )
            
            # Remove from active searches
            if user_id in self.active_searches:
                del self.active_searches[user_id]
    
    def get_active_searches(self) -> List[dict]:
        """Get list of active searches"""
        result = []
        for user_id, search_info in self.active_searches.items():
            result.append({
                'user_id': user_id,
                'supply_number': search_info['supply_number'],
                'account_id': search_info['account_id'],
                'started_at': search_info['started_at'],
                'duration': datetime.now() - search_info['started_at']
            })
        return result
    
    def is_user_searching(self, user_id: int) -> bool:
        """Check if user has active search"""
        return user_id in self.active_searches
    
    def get_user_search_info(self, user_id: int) -> Optional[dict]:
        """Get user's current search info"""
        return self.active_searches.get(user_id)
    
    async def stop_all_searches(self):
        """Stop all active searches (for shutdown)"""
        logger.info(f"Stopping {len(self.active_searches)} active searches...")
        
        for user_id in list(self.active_searches.keys()):
            await self.stop_supply_search(user_id)
        
        logger.info("All searches stopped") 