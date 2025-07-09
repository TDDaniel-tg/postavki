from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from loguru import logger

from database import DatabaseManager
from services.booking import BookingService


router = Router()


@router.callback_query(F.data.startswith("book_"))
async def handle_book_slot(callback: CallbackQuery, db: DatabaseManager, booking_service: BookingService):
    """Handle slot booking"""
    slot_id = callback.data.split("_", 1)[1]
    
    # Acknowledge callback immediately
    await callback.answer("🔄 Бронирую слот...")
    
    # Try to book slot
    success = await booking_service.book_slot_by_id(
        user_id=callback.from_user.id,
        slot_id=slot_id
    )
    
    if success:
        # Update message to show success
        try:
            await callback.message.edit_text(
                callback.message.text + "\n\n✅ <b>ЗАБРОНИРОВАНО!</b>",
                parse_mode="HTML"
            )
        except:
            pass
    else:
        # Booking failed - notification already sent by booking service
        try:
            await callback.message.edit_text(
                callback.message.text + "\n\n❌ <b>НЕ УДАЛОСЬ ЗАБРОНИРОВАТЬ</b>",
                parse_mode="HTML"
            )
        except:
            pass


@router.callback_query(F.data.startswith("skip_"))
async def handle_skip_slot(callback: CallbackQuery):
    """Handle skip slot"""
    await callback.answer("Слот пропущен")
    
    try:
        # Update message to show it was skipped
        await callback.message.edit_text(
            callback.message.text + "\n\n⏭ <i>Пропущено</i>",
            parse_mode="HTML"
        )
    except:
        pass


@router.message(F.text == "📋 История бронирований")
async def cmd_booking_history(message: Message, db: DatabaseManager):
    """Show booking history"""
    user = await db.get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ Вы не зарегистрированы. Используйте /start")
        return
    
    # Get recent bookings
    bookings = await db.get_user_booked_slots(user.id, limit=10)
    
    if not bookings:
        await message.answer(
            "📋 У вас пока нет забронированных слотов.\n\n"
            "Слоты будут отображаться здесь после бронирования."
        )
        return
    
    # Format bookings list
    text = "📋 <b>История бронирований</b>\n\n"
    
    for booking in bookings:
        icon = "🤖" if booking.auto_booked else "👤"
        status_icon = {
            "booked": "✅",
            "cancelled": "❌",
            "completed": "✔️"
        }.get(booking.status, "❓")
        
        text += (
            f"{icon} {status_icon} <b>{booking.warehouse_name}</b>\n"
            f"📅 {booking.supply_date.strftime('%d.%m.%Y')} "
            f"🕒 {booking.time_slot}\n"
            f"💰 Коэффициент: {booking.coefficient}\n"
            f"🕐 Забронировано: {booking.booked_at.strftime('%d.%m %H:%M')}\n\n"
        )
    
    await message.answer(text, parse_mode="HTML") 