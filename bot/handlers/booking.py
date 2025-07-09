from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger

from database import DatabaseManager
from services.booking import BookingService
from wb_api import WildberriesAPI
from bot.states import BookingStates
from bot.keyboards.main import get_cancel_keyboard, get_main_keyboard
from bot.keyboards.inline import get_account_selection_keyboard


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


@router.message(F.text == "🚚 Забронировать поставку")
async def cmd_book_supply(message: Message, state: FSMContext, db: DatabaseManager):
    """Start supply booking process"""
    user = await db.get_user_with_accounts(message.from_user.id)
    
    if not user:
        await message.answer("❌ Вы не зарегистрированы. Используйте /start")
        return
    
    if not user.wb_accounts:
        await message.answer(
            "❌ У вас нет подключенных аккаунтов.\n"
            "Сначала добавьте аккаунт WB через меню."
        )
        return
    
    # Check if user has active accounts
    active_accounts = [acc for acc in user.wb_accounts if acc.is_active]
    if not active_accounts:
        await message.answer(
            "❌ У вас нет активных аккаунтов.\n"
            "Активируйте аккаунт в разделе 'Мои аккаунты'."
        )
        return
    
    # If user has only one account, skip account selection
    if len(active_accounts) == 1:
        await state.update_data(selected_account_id=active_accounts[0].id)
        await state.set_state(BookingStates.waiting_for_supply_number)
        
        await message.answer(
            "🚚 <b>Автобронирование поставки</b>\n\n"
            f"📱 Аккаунт: <b>{active_accounts[0].name}</b>\n\n"
            "📝 Введите номер поставки, которую нужно забронировать:\n\n"
            "📌 <i>Например: WB123456789</i>\n\n"
            "ℹ️ Бот автоматически найдет подходящий слот согласно вашим настройкам фильтров "
            "(склады, регионы, коэффициенты) и забронирует поставку.",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
    else:
        # Multiple accounts - show selection
        await state.set_state(BookingStates.selecting_account_for_booking)
        
        await message.answer(
            "🚚 <b>Автобронирование поставки</b>\n\n"
            "👤 Выберите аккаунт для бронирования:",
            parse_mode="HTML",
            reply_markup=get_account_selection_keyboard(active_accounts)
        )


@router.callback_query(F.data.startswith("select_account_"), BookingStates.selecting_account_for_booking)
async def handle_account_selection_for_booking(callback: CallbackQuery, state: FSMContext, db: DatabaseManager):
    """Handle account selection for booking"""
    account_id = int(callback.data.split("_")[-1])
    
    # Get account info
    user = await db.get_user_with_accounts(callback.from_user.id)
    account = next((acc for acc in user.wb_accounts if acc.id == account_id), None)
    
    if not account or not account.is_active:
        await callback.answer("❌ Аккаунт недоступен", show_alert=True)
        return
    
    await state.update_data(selected_account_id=account_id)
    await state.set_state(BookingStates.waiting_for_supply_number)
    
    await callback.message.edit_text(
        "🚚 <b>Автобронирование поставки</b>\n\n"
        f"📱 Аккаунт: <b>{account.name}</b>\n\n"
        "📝 Введите номер поставки, которую нужно забронировать:\n\n"
        "📌 <i>Например: WB123456789</i>\n\n"
        "ℹ️ Бот автоматически найдет подходящий слот согласно вашим настройкам фильтров "
        "(склады, регионы, коэффициенты) и забронирует поставку.",
        parse_mode="HTML",
        reply_markup=None
    )
    
    # Send new message with cancel keyboard
    await callback.message.answer(
        "✏️ Введите номер поставки:",
        reply_markup=get_cancel_keyboard()
    )


@router.message(BookingStates.waiting_for_supply_number)
async def process_supply_number(message: Message, state: FSMContext, db: DatabaseManager, booking_service: BookingService):
    """Process supply number input"""
    if message.text == "❌ Отмена":
        await state.clear()
        user = await db.get_user_with_accounts(message.from_user.id)
        has_accounts = len(user.wb_accounts) > 0 if user else False
        await message.answer(
            "❌ Бронирование отменено.",
            reply_markup=get_main_keyboard(has_accounts)
        )
        return
    
    supply_number = message.text.strip()
    
    # Validate supply number format
    if not supply_number:
        await message.answer("❌ Номер поставки не может быть пустым. Попробуйте еще раз:")
        return
    
    if len(supply_number) < 5:
        await message.answer("❌ Номер поставки слишком короткий. Попробуйте еще раз:")
        return
    
    # Get state data
    data = await state.get_data()
    account_id = data.get("selected_account_id")
    
    if not account_id:
        await state.clear()
        await message.answer("❌ Ошибка: аккаунт не выбран. Начните заново.")
        return
    
    # Store supply number and show confirmation
    await state.update_data(supply_number=supply_number)
    await state.set_state(BookingStates.confirming_booking)
    
    # Get account info
    user = await db.get_user_with_accounts(message.from_user.id)
    account = next((acc for acc in user.wb_accounts if acc.id == account_id), None)
    
    # Get user filters
    filters = await db.get_user_filters(user.id)
    
    # Format filter info
    filter_info = "📋 <b>Настройки поиска:</b>\n"
    
    if filters:
        if filters.warehouses:
            warehouses = filters.warehouses
            filter_info += f"🏪 Склады: {len(warehouses)} выбрано\n"
        else:
            filter_info += "🏪 Склады: все доступные\n"
            
        if filters.regions:
            regions = filters.regions
            filter_info += f"🌍 Регионы: {len(regions)} выбрано\n"
        else:
            filter_info += "🌍 Регионы: все доступные\n"
            
        if filters.min_coefficient is not None:
            filter_info += f"💰 Мин. коэффициент: {filters.min_coefficient}\n"
        if filters.max_coefficient is not None:
            filter_info += f"💰 Макс. коэффициент: {filters.max_coefficient}\n"
            
        if filters.time_slots:
            filter_info += f"🕒 Временные слоты: настроены\n"
        else:
            filter_info += "🕒 Временные слоты: любые\n"
    else:
        filter_info += "🔄 Используются настройки по умолчанию\n"
    
    confirmation_text = (
        "🚚 <b>Подтверждение бронирования</b>\n\n"
        f"📦 Номер поставки: <code>{supply_number}</code>\n"
        f"👤 Аккаунт: <b>{account.name}</b>\n\n"
        f"{filter_info}\n"
        "🤖 Бот найдет первый подходящий слот и автоматически забронирует поставку.\n\n"
        "✅ Подтвердить бронирование?"
    )
    
    from bot.keyboards.main import get_yes_no_keyboard
    await message.answer(
        confirmation_text,
        parse_mode="HTML",
        reply_markup=get_yes_no_keyboard()
    )


@router.message(BookingStates.confirming_booking)
async def confirm_supply_booking(message: Message, state: FSMContext, db: DatabaseManager, booking_service: BookingService):
    """Confirm and execute supply booking"""
    if message.text == "❌ Нет":
        await state.clear()
        user = await db.get_user_with_accounts(message.from_user.id)
        has_accounts = len(user.wb_accounts) > 0 if user else False
        await message.answer(
            "❌ Бронирование отменено.",
            reply_markup=get_main_keyboard(has_accounts)
        )
        return
    
    if message.text != "✅ Да":
        await message.answer("Выберите ✅ Да или ❌ Нет")
        return
    
    # Get state data
    data = await state.get_data()
    supply_number = data.get("supply_number")
    account_id = data.get("selected_account_id")
    
    if not supply_number or not account_id:
        await state.clear()
        await message.answer("❌ Ошибка: данные потеряны. Начните заново.")
        return
    
    # Clear state
    await state.clear()
    
    # Get user and account
    user = await db.get_user_with_accounts(message.from_user.id)
    account = next((acc for acc in user.wb_accounts if acc.id == account_id), None)
    
    if not account:
        await message.answer(
            "❌ Аккаунт не найден.",
            reply_markup=get_main_keyboard(True)
        )
        return
    
    # Show processing message
    processing_msg = await message.answer(
        "🔄 <b>Поиск и бронирование слота...</b>\n\n"
        f"📦 Поставка: <code>{supply_number}</code>\n"
        f"👤 Аккаунт: <b>{account.name}</b>\n\n"
        "⏳ Это может занять несколько секунд...",
        parse_mode="HTML",
        reply_markup=get_main_keyboard(True)
    )
    
    try:
        # Execute booking
        success = await booking_service.auto_book_supply(
            user_id=user.id,
            account_id=account_id,
            supply_number=supply_number
        )
        
        if success:
            await processing_msg.edit_text(
                "✅ <b>ПОСТАВКА УСПЕШНО ЗАБРОНИРОВАНА!</b>\n\n"
                f"📦 Поставка: <code>{supply_number}</code>\n"
                f"👤 Аккаунт: <b>{account.name}</b>\n\n"
                "🎉 Слот найден и забронирован автоматически!\n"
                "📱 Проверьте детали в 'История бронирований'.",
                parse_mode="HTML"
            )
        else:
            await processing_msg.edit_text(
                "❌ <b>НЕ УДАЛОСЬ ЗАБРОНИРОВАТЬ</b>\n\n"
                f"📦 Поставка: <code>{supply_number}</code>\n\n"
                "🔍 Возможные причины:\n"
                "• Нет доступных слотов по вашим фильтрам\n"
                "• Проблемы с подключением к WB API\n"
                "• Все подходящие слоты уже заняты\n\n"
                "💡 Попробуйте:\n"
                "• Изменить настройки фильтров\n"
                "• Повторить через несколько минут",
                parse_mode="HTML"
            )
        
    except Exception as e:
        logger.error(f"Error in auto booking: {e}")
        await processing_msg.edit_text(
            "❌ <b>ОШИБКА ПРИ БРОНИРОВАНИИ</b>\n\n"
            f"📦 Поставка: <code>{supply_number}</code>\n\n"
            f"🔧 Детали ошибки: {str(e)[:100]}...\n\n"
            "🔄 Попробуйте позже или обратитесь в поддержку.",
            parse_mode="HTML"
        ) 