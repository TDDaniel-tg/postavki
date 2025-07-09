from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from loguru import logger

from database import DatabaseManager
from bot.keyboards import get_settings_keyboard, get_auto_booking_keyboard
from bot.states import FilterStates


router = Router()


@router.message(Command("settings"))
@router.message(F.text == "⚙️ Настройки")
async def cmd_settings(message: Message, db: DatabaseManager):
    """Handle settings command"""
    user = await db.get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ Вы не зарегистрированы. Используйте /start")
        return
    
    await message.answer(
        "⚙️ <b>Настройки</b>\n\n"
        "Выберите, что хотите настроить:",
        reply_markup=get_settings_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "settings")
async def handle_settings_callback(callback: CallbackQuery, db: DatabaseManager):
    """Handle settings callback"""
    await callback.message.edit_text(
        "⚙️ <b>Настройки</b>\n\n"
        "Выберите, что хотите настроить:",
        reply_markup=get_settings_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "filter_warehouses")
async def handle_filter_warehouses(callback: CallbackQuery, state: FSMContext, db: DatabaseManager):
    """Handle warehouse filter settings"""
    user = await db.get_user_with_accounts(callback.from_user.id)
    
    if not user or not user.wb_accounts:
        await callback.answer("Сначала добавьте аккаунт WB", show_alert=True)
        return
    
    # TODO: Get warehouses from WB API
    await callback.answer("🏗 Функция в разработке", show_alert=True)


@router.callback_query(F.data == "filter_coefficient")
async def handle_filter_coefficient(callback: CallbackQuery, state: FSMContext, db: DatabaseManager):
    """Handle coefficient filter settings"""
    await state.set_state(FilterStates.setting_coefficient)
    
    filters = await db.get_user_filters(callback.from_user.id)
    current_min = filters.min_coefficient if filters else 1.0
    
    await callback.message.edit_text(
        f"📊 <b>Настройка коэффициента</b>\n\n"
        f"Текущий минимальный коэффициент: {current_min}\n\n"
        f"Отправьте новое значение (например: 1.2):",
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
            f"✅ Минимальный коэффициент установлен: {coefficient}\n\n"
            f"Теперь вы будете получать уведомления только о слотах "
            f"с коэффициентом {coefficient} и выше.",
            reply_markup=get_settings_keyboard()
        )
        
    except ValueError:
        await message.answer("❌ Введите число (например: 1.2)")


@router.callback_query(F.data == "auto_booking")
async def handle_auto_booking(callback: CallbackQuery, db: DatabaseManager):
    """Handle auto booking settings"""
    filters = await db.get_user_filters(callback.from_user.id)
    enabled = filters.auto_booking_enabled if filters else False
    
    await callback.message.edit_text(
        "🤖 <b>Настройки автобронирования</b>\n\n"
        "Бот может автоматически бронировать слоты по вашим фильтрам.\n"
        "Будут выбраны слоты с наивысшим коэффициентом.",
        reply_markup=get_auto_booking_keyboard(enabled),
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
    
    await callback.message.edit_text(
        "🤖 <b>Настройки автобронирования</b>\n\n"
        "Бот может автоматически бронировать слоты по вашим фильтрам.\n"
        "Будут выбраны слоты с наивысшим коэффициентом.",
        reply_markup=get_auto_booking_keyboard(new_state),
        parse_mode="HTML"
    )
    
    status = "включено ✅" if new_state else "выключено ❌"
    await callback.answer(f"Автобронирование {status}")


@router.callback_query(F.data == "notifications")
async def handle_notifications(callback: CallbackQuery, db: DatabaseManager):
    """Handle notification settings"""
    filters = await db.get_user_filters(callback.from_user.id)
    enabled = filters.notifications_enabled if filters else True
    
    status = "включены ✅" if enabled else "выключены ❌"
    toggle_text = "Выключить 🔕" if enabled else "Включить 🔔"
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=f"Уведомления: {status}",
            callback_data="none"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=toggle_text,
            callback_data="toggle_notifications"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="settings"
        )
    )
    
    await callback.message.edit_text(
        "🔔 <b>Настройки уведомлений</b>\n\n"
        "Управление уведомлениями о новых слотах.",
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


@router.callback_query(F.data == "back_to_main")
async def handle_back_to_main(callback: CallbackQuery):
    """Handle back to main menu"""
    await callback.message.delete()
    await callback.answer() 