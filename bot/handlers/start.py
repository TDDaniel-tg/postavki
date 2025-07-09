from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from loguru import logger

from database import DatabaseManager
from bot.keyboards import get_main_keyboard
from bot.states import UserStates
from services.supply_finder import SupplyFinderService


router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db: DatabaseManager, supply_finder: SupplyFinderService = None):
    """Handle /start command"""
    user_id = message.from_user.id
    
    # Check if user exists
    user = await db.get_user(user_id)
    
    if not user:
        # Create new user
        user = await db.create_user(
            telegram_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        logger.info(f"New user created: {user_id}")
        
        welcome_text = (
            f"👋 Привет, {message.from_user.first_name}!\n\n"
            "Я бот для отслеживания слотов поставок Wildberries.\n\n"
            "🚀 Мои возможности:\n"
            "• Мониторинг новых слотов каждые 5 секунд\n"
            "• Поддержка нескольких аккаунтов WB\n"
            "• Гибкие фильтры по складам и времени\n"
            "• Автоматическое бронирование\n"
            "• Мгновенные уведомления\n\n"
            "Для начала работы добавьте ваш API ключ WB.\n"
            "Нажмите кнопку 'Добавить аккаунт' ⬇️"
        )
    else:
        # Get user accounts
        accounts = await db.get_user_accounts(user.id)
        has_accounts = len(accounts) > 0
        
        welcome_text = (
            f"👋 С возвращением, {message.from_user.first_name}!\n\n"
        )
        
        if has_accounts:
            active_accounts = [acc for acc in accounts if acc.is_active]
            welcome_text += (
                f"✅ У вас подключено аккаунтов: {len(active_accounts)}/{len(accounts)}\n"
                f"📊 Мониторинг активен\n"
            )
            
            # Check for active search
            has_active_search = False
            if supply_finder and supply_finder.is_user_searching(user.id):
                has_active_search = True
                search_info = supply_finder.get_user_search_info(user.id)
                welcome_text += (
                    f"\n🔍 **АКТИВНЫЙ ПОИСК СЛОТА**\n"
                    f"📦 Поставка: {search_info['supply_number']}\n"
                    f"⏰ Запущен: {search_info['started_at'].strftime('%H:%M:%S')}\n"
                    f"⏹️ Для остановки используйте кнопку ниже\n"
                )
            
            welcome_text += f"\nИспользуйте меню для управления ⬇️"
        else:
            welcome_text += (
                "❗ У вас нет подключенных аккаунтов.\n"
                "Нажмите 'Добавить аккаунт' для начала работы ⬇️"
            )
            has_active_search = False
    
    # Clear state
    await state.clear()
    
    # Send welcome message
    final_has_accounts = user and len(await db.get_user_accounts(user.id)) > 0
    final_has_active_search = has_active_search if 'has_active_search' in locals() else False
    
    await message.answer(
        text=welcome_text,
        reply_markup=get_main_keyboard(
            has_accounts=final_has_accounts,
            has_active_search=final_has_active_search
        )
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command"""
    help_text = (
        "📖 <b>Справка по использованию бота</b>\n\n"
        
        "<b>Основные команды:</b>\n"
        "/start - Главное меню\n"
        "/add_account - Добавить аккаунт WB\n"
        "/list_accounts - Список аккаунтов\n"
        "/settings - Настройки фильтров\n"
        "/status - Статус мониторинга\n"
        "/help - Эта справка\n\n"
        
        "<b>Как начать:</b>\n"
        "1️⃣ Получите API ключ в личном кабинете WB\n"
        "2️⃣ Добавьте аккаунт через /add_account\n"
        "3️⃣ Настройте фильтры по складам\n"
        "4️⃣ Ожидайте уведомления о новых слотах\n\n"
        
        "<b>Автобронирование:</b>\n"
        "• Включите в настройках\n"
        "• Установите лимит слотов в день\n"
        "• Бот автоматически забронирует лучшие слоты\n\n"
        
        "<b>Фильтры:</b>\n"
        "• Склады - выберите нужные\n"
        "• Коэффициент - минимальное значение\n"
        "• Время - удобные часы для поставок\n\n"
        
        "❓ Вопросы? Напишите администратору."
    )
    
    await message.answer(help_text, parse_mode="HTML")


@router.message(F.text == "❓ Помощь")
async def help_button(message: Message):
    """Handle help button"""
    await cmd_help(message)


@router.message(Command("status"))
@router.message(F.text == "📊 Статус мониторинга")
async def cmd_status(message: Message, db: DatabaseManager, supply_finder: SupplyFinderService = None):
    """Handle /status command"""
    user = await db.get_user_with_accounts(message.from_user.id)
    
    if not user:
        await message.answer("❌ Вы не зарегистрированы. Используйте /start")
        return
    
    # Get accounts info
    total_accounts = len(user.wb_accounts)
    active_accounts = len([acc for acc in user.wb_accounts if acc.is_active])
    
    # Get filters info
    filters = await db.get_user_filters(user.id)
    
    status_text = (
        "📊 <b>Статус мониторинга</b>\n\n"
        f"👤 Пользователь: {user.first_name}\n"
        f"💼 Аккаунтов: {active_accounts}/{total_accounts}\n"
    )
    
    if active_accounts > 0:
        status_text += "✅ Мониторинг: <b>Активен</b>\n"
        status_text += "🔄 Интервал проверки: 5 сек\n\n"
        
        if filters:
            status_text += "<b>Настройки фильтров:</b>\n"
            
            if filters.warehouses:
                status_text += f"🏭 Склады: {len(filters.warehouses)} выбрано\n"
            else:
                status_text += "🏭 Склады: Все\n"
            
            status_text += f"📊 Мин. коэффициент: {filters.min_coefficient}\n"
            
            if filters.auto_booking_enabled:
                status_text += f"🤖 Автобронирование: ✅ (лимит {filters.auto_booking_limit}/день)\n"
            else:
                status_text += "🤖 Автобронирование: ❌\n"
            
            if filters.notifications_enabled:
                status_text += "🔔 Уведомления: ✅\n"
            else:
                status_text += "🔔 Уведомления: ❌\n"
    else:
        status_text += "❌ Мониторинг: <b>Неактивен</b>\n"
        status_text += "⚠️ Добавьте хотя бы один аккаунт\n"
    
    # Add active search info
    if supply_finder and supply_finder.is_user_searching(user.id):
        search_info = supply_finder.get_user_search_info(user.id)
        duration = search_info['started_at']
        
        status_text += "\n" + "="*30 + "\n"
        status_text += "🔍 <b>АКТИВНЫЙ ПОИСК СЛОТА</b>\n"
        status_text += f"📦 Поставка: <code>{search_info['supply_number']}</code>\n"
        status_text += f"⏰ Запущен: {duration.strftime('%H:%M:%S %d.%m.%Y')}\n"
        status_text += f"🔁 Интервал поиска: 30 сек\n"
        status_text += f"⏹️ Остановить: /stop_search\n"
    else:
        status_text += "\n💤 <i>Активных поисков нет</i>\n"
    
    await message.answer(status_text, parse_mode="HTML") 