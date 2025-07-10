from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from loguru import logger

from database import DatabaseManager
from bot.keyboards import (
    get_settings_keyboard, 
    get_auto_booking_keyboard,
    get_warehouses_keyboard,
    get_regions_keyboard,
    get_time_slots_keyboard
)
from bot.states import FilterStates
from wb_api.client import WildberriesAPI

router = Router()

# Список реальных регионов WB для настройки фильтров
WB_REGIONS = [
    {"id": "msk", "name": "Московская область", "cities": ["Москва", "Подольск", "Коледино"]},
    {"id": "spb", "name": "Санкт-Петербург", "cities": ["СПб", "Уткина Заводе"]},
    {"id": "krd", "name": "Краснодарский край", "cities": ["Краснодар", "Тихорецкая"]},
    {"id": "ekb", "name": "Свердловская область", "cities": ["Екатеринбург", "Перспективная"]},
    {"id": "tul", "name": "Тульская область", "cities": ["Тула"]},
    {"id": "stv", "name": "Ставропольский край", "cities": ["Невинномысск"]},
    {"id": "tat", "name": "Республика Татарстан", "cities": ["Казань"]},
    {"id": "nsk", "name": "Новосибирская область", "cities": ["Новосибирск"]},
    {"id": "ros", "name": "Ростовская область", "cities": ["Ростов-на-Дону"]},
    {"id": "sam", "name": "Самарская область", "cities": ["Самара"]}
]

# Временные слоты как в реальном WB
TIME_SLOTS = [
    {"id": "morning", "name": "🌅 Утро (9:00-12:00)", "start": "09:00", "end": "12:00"},
    {"id": "day", "name": "☀️ День (12:00-15:00)", "start": "12:00", "end": "15:00"},
    {"id": "afternoon", "name": "🌤️ После обеда (15:00-18:00)", "start": "15:00", "end": "18:00"},
    {"id": "evening", "name": "🌆 Вечер (18:00-21:00)", "start": "18:00", "end": "21:00"},
    {"id": "night", "name": "🌙 Ночь (21:00-00:00)", "start": "21:00", "end": "00:00"},
    {"id": "early", "name": "🌄 Раннее утро (6:00-9:00)", "start": "06:00", "end": "09:00"}
]


@router.message(Command("settings"))
@router.message(F.text == "⚙️ Настройки")
async def cmd_settings(message: Message, db: DatabaseManager):
    """Handle settings command"""
    user = await db.get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ Вы не зарегистрированы. Используйте /start")
        return
    
    # Get current filters info
    filters = await db.get_user_filters(user.id)
    
    settings_info = "⚙️ <b>Настройки фильтров</b>\n\n"
    
    if filters:
        # Warehouses info
        if filters.warehouses:
            settings_info += f"🏭 Склады: {len(filters.warehouses)} выбрано\n"
        else:
            settings_info += "🏭 Склады: Все\n"
        
        # Regions info
        if filters.regions:
            settings_info += f"📍 Регионы: {len(filters.regions)} выбрано\n"
        else:
            settings_info += "📍 Регионы: Все\n"
        
        # Coefficient
        settings_info += f"📊 Мин. коэффициент: {filters.min_coefficient}\n"
        
        # Time slots
        if filters.time_slots:
            settings_info += f"🕐 Время: {len(filters.time_slots)} слотов\n"
        else:
            settings_info += "🕐 Время: Любое\n"
        
        # Auto booking
        auto_status = "✅ Включено" if filters.auto_booking_enabled else "❌ Выключено"
        settings_info += f"🤖 Автобронирование: {auto_status}\n"
        
        if filters.auto_booking_enabled:
            settings_info += f"   Лимит: {filters.auto_booking_limit}/день\n"
    else:
        settings_info += "⚠️ Фильтры не настроены\n"
    
    settings_info += "\nВыберите параметр для настройки:"
    
    await message.answer(
        settings_info,
        reply_markup=get_settings_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "settings")
async def handle_settings_callback(callback: CallbackQuery, db: DatabaseManager):
    """Handle settings callback"""
    await cmd_settings(callback.message, db)
    await callback.answer()


@router.callback_query(F.data == "filter_warehouses")
async def handle_filter_warehouses(callback: CallbackQuery, state: FSMContext, db: DatabaseManager):
    """Handle warehouse filter settings"""
    user = await db.get_user_with_accounts(callback.from_user.id)
    
    if not user or not user.wb_accounts:
        await callback.answer("Сначала добавьте аккаунт WB", show_alert=True)
        return
    
    await callback.message.edit_text("🔄 Загружаю список складов...")
    
    try:
        # Get warehouses from first active account
        active_account = next((acc for acc in user.wb_accounts if acc.is_active), None)
        if not active_account:
            await callback.answer("Нет активных аккаунтов WB", show_alert=True)
            return
        
        # Get warehouses from API
        async with WildberriesAPI(active_account.api_key) as api:
            warehouses = await api.get_warehouses()
        
        # Get current selected warehouses
        filters = await db.get_user_filters(user.id)
        selected_warehouses = filters.warehouses if filters else []
        
        await state.set_state(FilterStates.selecting_warehouses)
        await state.update_data(warehouses=warehouses, selected=selected_warehouses)
        
        await callback.message.edit_text(
            "🏭 <b>Выбор складов</b>\n\n"
            "Выберите склады для мониторинга:\n"
            "✅ - склад включен в мониторинг\n"
            "⬜ - склад отключен",
            reply_markup=get_warehouses_keyboard(warehouses, selected_warehouses),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error loading warehouses: {e}")
        await callback.message.edit_text(
            "❌ Ошибка загрузки складов. Попробуйте позже.",
            reply_markup=get_settings_keyboard()
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_wh_"))
async def handle_toggle_warehouse(callback: CallbackQuery, state: FSMContext):
    """Toggle warehouse selection"""
    warehouse_id = callback.data.replace("toggle_wh_", "")
    
    data = await state.get_data()
    warehouses = data.get("warehouses", [])
    selected = data.get("selected", [])
    
    # Toggle selection
    if warehouse_id in selected:
        selected.remove(warehouse_id)
    else:
        selected.append(warehouse_id)
    
    await state.update_data(selected=selected)
    
    # Update keyboard
    await callback.message.edit_reply_markup(
        reply_markup=get_warehouses_keyboard(warehouses, selected)
    )
    await callback.answer()


@router.callback_query(F.data == "save_warehouses")
async def handle_save_warehouses(callback: CallbackQuery, state: FSMContext, db: DatabaseManager):
    """Save warehouse selections"""
    data = await state.get_data()
    selected = data.get("selected", [])
    
    user = await db.get_user(callback.from_user.id)
    
    # Update user filters
    await db.update_user_filters(
        user_id=user.id,
        warehouses=selected
    )
    
    count = len(selected)
    status = f"{count} складов выбрано" if count > 0 else "Все склады"
    
    await state.clear()
    await callback.message.edit_text(
        f"✅ Настройки складов сохранены\n\n"
        f"📊 Статус: {status}\n\n"
        f"Теперь мониторинг будет отслеживать только выбранные склады.",
        reply_markup=get_settings_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "filter_regions")
async def handle_filter_regions(callback: CallbackQuery, state: FSMContext, db: DatabaseManager):
    """Handle region filter settings"""
    user = await db.get_user(callback.from_user.id)
    filters = await db.get_user_filters(user.id)
    selected_regions = filters.regions if filters else []
    
    await state.set_state(FilterStates.selecting_regions)
    await state.update_data(selected=selected_regions)
    
    await callback.message.edit_text(
        "📍 <b>Выбор регионов</b>\n\n"
        "Выберите регионы для мониторинга:\n"
        "✅ - регион включен\n"
        "⬜ - регион отключен",
        reply_markup=get_regions_keyboard(WB_REGIONS, selected_regions),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_reg_"))
async def handle_toggle_region(callback: CallbackQuery, state: FSMContext):
    """Toggle region selection"""
    region_id = callback.data.replace("toggle_reg_", "")
    
    data = await state.get_data()
    selected = data.get("selected", [])
    
    # Toggle selection
    if region_id in selected:
        selected.remove(region_id)
    else:
        selected.append(region_id)
    
    await state.update_data(selected=selected)
    
    # Update keyboard
    await callback.message.edit_reply_markup(
        reply_markup=get_regions_keyboard(WB_REGIONS, selected)
    )
    await callback.answer()


@router.callback_query(F.data == "save_regions")
async def handle_save_regions(callback: CallbackQuery, state: FSMContext, db: DatabaseManager):
    """Save region selections"""
    data = await state.get_data()
    selected = data.get("selected", [])
    
    user = await db.get_user(callback.from_user.id)
    
    # Update user filters
    await db.update_user_filters(
        user_id=user.id,
        regions=selected
    )
    
    count = len(selected)
    status = f"{count} регионов выбрано" if count > 0 else "Все регионы"
    
    await state.clear()
    await callback.message.edit_text(
        f"✅ Настройки регионов сохранены\n\n"
        f"📊 Статус: {status}\n\n"
        f"Теперь мониторинг будет отслеживать только выбранные регионы.",
        reply_markup=get_settings_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "filter_coefficient")
async def handle_filter_coefficient(callback: CallbackQuery, state: FSMContext, db: DatabaseManager):
    """Handle coefficient filter settings"""
    await state.set_state(FilterStates.setting_coefficient)
    
    filters = await db.get_user_filters(callback.from_user.id)
    current_min = filters.min_coefficient if filters else 1.0
    
    await callback.message.edit_text(
        f"📊 <b>Настройка коэффициента</b>\n\n"
        f"Текущий минимальный коэффициент: <b>{current_min}</b>\n\n"
        f"Коэффициент определяет приоритет склада.\n"
        f"Чем выше коэффициент, тем выгоднее поставка.\n\n"
        f"💡 Рекомендуемые значения:\n"
        f"• 1.0 - любые слоты\n"
        f"• 1.2 - хорошие слоты\n"
        f"• 1.5 - отличные слоты\n"
        f"• 2.0+ - премиум слоты\n\n"
        f"Отправьте новое значение (например: <code>1.2</code>):",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(FilterStates.setting_coefficient)
async def process_coefficient(message: Message, state: FSMContext, db: DatabaseManager):
    """Process coefficient input"""
    try:
        coefficient = float(message.text.replace(",", "."))
        
        if coefficient < 0 or coefficient > 10:
            await message.answer("❌ Коэффициент должен быть от 0 до 10")
            return
        
        # Update user filters
        user = await db.get_user(message.from_user.id)
        await db.update_user_filters(
            user_id=user.id,
            min_coefficient=coefficient
        )
        
        await state.clear()
        await message.answer(
            f"✅ Минимальный коэффициент установлен: <b>{coefficient}</b>\n\n"
            f"Теперь вы будете получать уведомления только о слотах "
            f"с коэффициентом {coefficient} и выше.",
            reply_markup=get_settings_keyboard(),
            parse_mode="HTML"
        )
        
    except ValueError:
        await message.answer("❌ Введите число (например: 1.2)")


@router.callback_query(F.data == "filter_time")
async def handle_filter_time(callback: CallbackQuery, state: FSMContext, db: DatabaseManager):
    """Handle time slots filter settings"""
    user = await db.get_user(callback.from_user.id)
    filters = await db.get_user_filters(user.id)
    selected_times = filters.time_slots if filters else []
    
    await state.set_state(FilterStates.setting_time_slots)
    await state.update_data(selected=selected_times)
    
    await callback.message.edit_text(
        "🕐 <b>Выбор временных слотов</b>\n\n"
        "Выберите удобное время для поставок:\n"
        "✅ - время включено\n"
        "⬜ - время отключено\n\n"
        "💡 Если ничего не выбрано - подойдет любое время",
        reply_markup=get_time_slots_keyboard(TIME_SLOTS, selected_times),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_time_"))
async def handle_toggle_time(callback: CallbackQuery, state: FSMContext):
    """Toggle time slot selection"""
    time_id = callback.data.replace("toggle_time_", "")
    
    data = await state.get_data()
    selected = data.get("selected", [])
    
    # Toggle selection
    if time_id in selected:
        selected.remove(time_id)
    else:
        selected.append(time_id)
    
    await state.update_data(selected=selected)
    
    # Update keyboard
    await callback.message.edit_reply_markup(
        reply_markup=get_time_slots_keyboard(TIME_SLOTS, selected)
    )
    await callback.answer()


@router.callback_query(F.data == "save_time_slots")
async def handle_save_time_slots(callback: CallbackQuery, state: FSMContext, db: DatabaseManager):
    """Save time slots selections"""
    data = await state.get_data()
    selected = data.get("selected", [])
    
    user = await db.get_user(callback.from_user.id)
    
    # Update user filters
    await db.update_user_filters(
        user_id=user.id,
        time_slots=selected
    )
    
    count = len(selected)
    status = f"{count} временных слотов выбрано" if count > 0 else "Любое время"
    
    await state.clear()
    await callback.message.edit_text(
        f"✅ Настройки времени сохранены\n\n"
        f"📊 Статус: {status}\n\n"
        f"Теперь мониторинг будет отслеживать только выбранные временные слоты.",
        reply_markup=get_settings_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "auto_booking")
async def handle_auto_booking(callback: CallbackQuery, db: DatabaseManager):
    """Handle auto booking settings"""
    filters = await db.get_user_filters(callback.from_user.id)
    enabled = filters.auto_booking_enabled if filters else False
    limit = filters.auto_booking_limit if filters else 5
    
    status_text = "включено ✅" if enabled else "выключено ❌"
    
    text = (
        "🤖 <b>Настройки автобронирования</b>\n\n"
        f"Статус: <b>{status_text}</b>\n"
    )
    
    if enabled:
        text += (
            f"Лимит: <b>{limit} слотов/день</b>\n\n"
            "📋 <b>Как работает:</b>\n"
            "• Бот автоматически отслеживает новые слоты\n"
            "• Выбирает лучшие по вашим фильтрам\n"
            "• Бронирует слоты с наивысшим коэффициентом\n"
            "• Учитывает дневной лимит бронирований\n\n"
            "⚡ Автобронирование работает в режиме реального времени!"
        )
    else:
        text += (
            "\n📋 <b>Преимущества автобронирования:</b>\n"
            "• Мгновенная реакция на новые слоты\n"
            "• Автоматический выбор лучших коэффициентов\n"
            "• Работает 24/7 без вашего участия\n"
            "• Настраиваемые лимиты безопасности\n\n"
            "💡 Включите для максимальной эффективности!"
        )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_auto_booking_keyboard(enabled, limit),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "toggle_auto_booking")
async def handle_toggle_auto_booking(callback: CallbackQuery, db: DatabaseManager):
    """Toggle auto booking on/off"""
    user = await db.get_user(callback.from_user.id)
    filters = await db.get_user_filters(user.id)
    
    new_state = not filters.auto_booking_enabled
    
    await db.update_user_filters(
        user_id=user.id,
        auto_booking_enabled=new_state
    )
    
    # Refresh the auto booking menu
    await handle_auto_booking(callback, db)
    
    status = "включено ✅" if new_state else "выключено ❌"
    await callback.answer(f"Автобронирование {status}")


@router.callback_query(F.data == "auto_booking_settings")
async def handle_auto_booking_settings(callback: CallbackQuery, state: FSMContext, db: DatabaseManager):
    """Handle auto booking advanced settings"""
    await state.set_state(FilterStates.setting_auto_booking)
    
    filters = await db.get_user_filters(callback.from_user.id)
    current_limit = filters.auto_booking_limit if filters else 5
    
    await callback.message.edit_text(
        f"⚙️ <b>Настройки автобронирования</b>\n\n"
        f"Текущий лимит: <b>{current_limit} слотов/день</b>\n\n"
        f"💡 <b>Рекомендации:</b>\n"
        f"• 1-3 слота - для тестирования\n"
        f"• 5-10 слотов - стандартный режим\n"
        f"• 15+ слотов - активная работа\n\n"
        f"⚠️ <b>Лимиты помогают контролировать расходы</b>\n\n"
        f"Введите новый лимит (1-50):",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(FilterStates.setting_auto_booking)
async def process_auto_booking_limit(message: Message, state: FSMContext, db: DatabaseManager):
    """Process auto booking limit input"""
    try:
        limit = int(message.text)
        
        if limit < 1 or limit > 50:
            await message.answer("❌ Лимит должен быть от 1 до 50 слотов")
            return
        
        # Update user filters
        user = await db.get_user(message.from_user.id)
        await db.update_user_filters(
            user_id=user.id,
            auto_booking_limit=limit
        )
        
        await state.clear()
        await message.answer(
            f"✅ Лимит автобронирования установлен: <b>{limit} слотов/день</b>\n\n"
            f"Бот будет автоматически бронировать до {limit} лучших слотов в день.",
            reply_markup=get_settings_keyboard(),
            parse_mode="HTML"
        )
        
    except ValueError:
        await message.answer("❌ Введите число от 1 до 50")


@router.callback_query(F.data == "notifications")
async def handle_notifications(callback: CallbackQuery, db: DatabaseManager):
    """Handle notification settings"""
    filters = await db.get_user_filters(callback.from_user.id)
    enabled = filters.notifications_enabled if filters else True
    quiet_start = filters.quiet_hours_start if filters else None
    quiet_end = filters.quiet_hours_end if filters else None
    
    status = "включены ✅" if enabled else "выключены ❌"
    toggle_text = "Выключить 🔕" if enabled else "Включить 🔔"
    
    text = (
        "🔔 <b>Настройки уведомлений</b>\n\n"
        f"Статус: <b>{status}</b>\n\n"
    )
    
    if quiet_start is not None and quiet_end is not None:
        text += f"🌙 Тихие часы: {quiet_start:02d}:00 - {quiet_end:02d}:00\n\n"
    
    text += (
        "📱 <b>Типы уведомлений:</b>\n"
        "• Новые доступные слоты\n"
        "• Успешные бронирования\n"
        "• Ошибки и предупреждения\n"
        "• Статистика работы бота\n\n"
        "💡 Настройте тихие часы для комфорта"
    )
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=toggle_text,
            callback_data="toggle_notifications"
        )
    )
    
    if enabled:
        builder.row(
            InlineKeyboardButton(
                text="🌙 Тихие часы",
                callback_data="set_quiet_hours"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="settings"
        )
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "toggle_notifications")
async def handle_toggle_notifications(callback: CallbackQuery, db: DatabaseManager):
    """Toggle notifications on/off"""
    user = await db.get_user(callback.from_user.id)
    filters = await db.get_user_filters(user.id)
    
    new_state = not filters.notifications_enabled
    
    await db.update_user_filters(
        user_id=user.id,
        notifications_enabled=new_state
    )
    
    await handle_notifications(callback, db)
    
    status = "включены ✅" if new_state else "выключены ❌"
    await callback.answer(f"Уведомления {status}")


@router.callback_query(F.data == "set_quiet_hours")
async def handle_set_quiet_hours(callback: CallbackQuery, state: FSMContext):
    """Set quiet hours for notifications"""
    await state.set_state(FilterStates.setting_quiet_hours)
    
    await callback.message.edit_text(
        "🌙 <b>Настройка тихих часов</b>\n\n"
        "В это время бот не будет отправлять уведомления.\n\n"
        "Введите время в формате: <code>22 06</code>\n"
        "(тихие часы с 22:00 до 06:00)\n\n"
        "Или отправьте <code>отключить</code> для отмены тихих часов.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(FilterStates.setting_quiet_hours)
async def process_quiet_hours(message: Message, state: FSMContext, db: DatabaseManager):
    """Process quiet hours input"""
    if message.text.lower() in ["отключить", "отмена", "нет"]:
        user = await db.get_user(message.from_user.id)
        await db.update_user_filters(
            user_id=user.id,
            quiet_hours_start=None,
            quiet_hours_end=None
        )
        
        await state.clear()
        await message.answer(
            "✅ Тихие часы отключены\n\n"
            "Уведомления будут приходить в любое время.",
            reply_markup=get_settings_keyboard()
        )
        return
    
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            raise ValueError()
        
        start_hour = int(parts[0])
        end_hour = int(parts[1])
        
        if not (0 <= start_hour <= 23) or not (0 <= end_hour <= 23):
            raise ValueError()
        
        user = await db.get_user(message.from_user.id)
        await db.update_user_filters(
            user_id=user.id,
            quiet_hours_start=start_hour,
            quiet_hours_end=end_hour
        )
        
        await state.clear()
        await message.answer(
            f"✅ Тихие часы установлены: <b>{start_hour:02d}:00 - {end_hour:02d}:00</b>\n\n"
            f"В это время уведомления приходить не будут.",
            reply_markup=get_settings_keyboard(),
            parse_mode="HTML"
        )
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат\n\n"
            "Введите два числа от 0 до 23, например: <code>22 06</code>",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "back_to_main")
async def handle_back_to_main(callback: CallbackQuery):
    """Handle back to main menu"""
    await callback.message.delete()
    await callback.answer() 