from typing import List, Optional
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from loguru import logger

from wb_api.models import SupplySlot
from bot.keyboards import get_slot_keyboard


class NotificationService:
    """Service for sending notifications"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
    
    async def notify_new_slots(self, user_id: int, account_name: str, 
                             slots: List[SupplySlot]):
        """Send notification about new slots"""
        for slot in slots[:5]:  # Limit to 5 slots per notification
            try:
                message = self._format_slot_message(slot, account_name)
                keyboard = get_slot_keyboard(slot.id)
                
                await self.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                
            except TelegramBadRequest as e:
                if "chat not found" in str(e):
                    logger.warning(f"User {user_id} blocked the bot")
                    # Should mark user as inactive in DB
                    break
                else:
                    logger.error(f"Error sending notification to {user_id}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error sending notification: {e}")
    
    async def notify_booking_success(self, user_id: int, slot: SupplySlot, 
                                   account_name: str, auto_booked: bool = False):
        """Send notification about successful booking"""
        prefix = "🤖 Автоматически забронирован" if auto_booked else "✅ Успешно забронирован"
        
        message = (
            f"{prefix} слот!\n\n"
            f"💼 Аккаунт: {account_name}\n"
            f"📦 Склад: {slot.warehouse_name}\n"
            f"📅 Дата: {slot.date_str}\n"
            f"🕒 Время: {slot.time_slot}\n"
            f"💰 Коэффициент: {slot.coefficient}"
        )
        
        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error sending booking notification: {e}")
    
    async def notify_booking_error(self, user_id: int, error_message: str):
        """Send notification about booking error"""
        message = f"❌ Ошибка бронирования:\n{error_message}"
        
        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=message
            )
        except Exception as e:
            logger.error(f"Error sending error notification: {e}")
    
    async def send_message(self, user_id: int, message: str, 
                          reply_markup=None, parse_mode: Optional[str] = None):
        """Send generic message"""
        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        except Exception as e:
            logger.error(f"Error sending message to {user_id}: {e}")
    
    def _format_slot_message(self, slot: SupplySlot, account_name: str) -> str:
        """Format slot message"""
        return (
            f"🆕 <b>НОВЫЙ СЛОТ!</b>\n\n"
            f"💼 Аккаунт: {account_name}\n"
            f"📦 Склад: <b>{slot.warehouse_name}</b>\n"
            f"📅 Дата: <b>{slot.date_str}</b>\n"
            f"🕒 Время: <b>{slot.time_slot}</b>\n"
            f"💰 Коэффициент: <b>{slot.coefficient}</b>"
        ) 