from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger

from config import settings
from wb_api import WildberriesAPI
from database import DatabaseManager

router = Router()

# Admin user IDs (можно вынести в переменные окружения)
ADMIN_USER_IDS = [
    # Добавьте ваш Telegram ID
    # Например: 123456789
]


def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in ADMIN_USER_IDS


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Get admin control keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="🔧 Настройки API",
            callback_data="admin_api_settings"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="📊 Статистика",
            callback_data="admin_stats"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🔄 Тест API",
            callback_data="admin_test_api"
        )
    )
    
    return builder.as_markup()


def get_api_settings_keyboard() -> InlineKeyboardMarkup:
    """Get API settings keyboard"""
    builder = InlineKeyboardBuilder()
    
    # Current demo mode status
    demo_status = "✅ Включен" if settings.WB_API_FORCE_DEMO_MODE else "❌ Выключен"
    fallback_status = "✅ Включен" if settings.WB_API_ALLOW_DEMO_FALLBACK else "❌ Выключен"
    
    builder.row(
        InlineKeyboardButton(
            text=f"🎭 Принудительный демо-режим: {demo_status}",
            callback_data="admin_toggle_force_demo"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text=f"🔄 Fallback в демо: {fallback_status}",
            callback_data="admin_toggle_demo_fallback"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🌐 Переключить на основной URL",
            callback_data="admin_use_main_url"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🔀 Переключить на резервный URL",
            callback_data="admin_use_backup_url"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="admin_back"
        )
    )
    
    return builder.as_markup()


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Admin panel command"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    await message.answer(
        "🛠 **Админ-панель**\n\n"
        "Выберите действие:",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin_api_settings")
async def handle_api_settings(callback: CallbackQuery):
    """Handle API settings"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    text = (
        "⚙️ **Настройки API**\n\n"
        f"🌐 **Основной URL**: `{settings.WB_API_BASE_URL}`\n"
        f"🔀 **Резервный URL**: `{settings.WB_API_BACKUP_URL}`\n\n"
        f"🎭 **Принудительный демо**: {'Включен' if settings.WB_API_FORCE_DEMO_MODE else 'Выключен'}\n"
        f"🔄 **Fallback в демо**: {'Включен' if settings.WB_API_ALLOW_DEMO_FALLBACK else 'Выключен'}\n\n"
        "Выберите действие:"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_api_settings_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin_toggle_force_demo")
async def handle_toggle_force_demo(callback: CallbackQuery):
    """Toggle force demo mode"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    # Toggle setting
    settings.WB_API_FORCE_DEMO_MODE = not settings.WB_API_FORCE_DEMO_MODE
    
    status = "включен" if settings.WB_API_FORCE_DEMO_MODE else "выключен"
    await callback.answer(f"✅ Принудительный демо-режим {status}", show_alert=True)
    
    # Update keyboard
    await handle_api_settings(callback)


@router.callback_query(F.data == "admin_toggle_demo_fallback")
async def handle_toggle_demo_fallback(callback: CallbackQuery):
    """Toggle demo fallback"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    # Toggle setting
    settings.WB_API_ALLOW_DEMO_FALLBACK = not settings.WB_API_ALLOW_DEMO_FALLBACK
    
    status = "включен" if settings.WB_API_ALLOW_DEMO_FALLBACK else "выключен"
    await callback.answer(f"✅ Fallback в демо-режим {status}", show_alert=True)
    
    # Update keyboard
    await handle_api_settings(callback)


@router.callback_query(F.data == "admin_use_main_url")
async def handle_use_main_url(callback: CallbackQuery):
    """Switch to main URL"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    settings.WB_API_USE_BACKUP = False
    await callback.answer("✅ Переключен на основной URL", show_alert=True)
    
    # Update keyboard
    await handle_api_settings(callback)


@router.callback_query(F.data == "admin_use_backup_url")
async def handle_use_backup_url(callback: CallbackQuery):
    """Switch to backup URL"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    settings.WB_API_USE_BACKUP = True
    await callback.answer("✅ Переключен на резервный URL", show_alert=True)
    
    # Update keyboard
    await handle_api_settings(callback)


@router.callback_query(F.data == "admin_test_api")
async def handle_test_api(callback: CallbackQuery, db: DatabaseManager):
    """Test API connectivity"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    await callback.message.edit_text("🔄 Тестирование API...")
    
    try:
        # Get first user with API key for testing
        users = await db.get_active_users()
        if not users:
            await callback.message.edit_text("❌ Нет пользователей с API ключами для тестирования")
            return
        
        test_user = users[0]
        if not test_user.wb_accounts:
            await callback.message.edit_text("❌ У пользователей нет API ключей")
            return
        
        test_account = test_user.wb_accounts[0]
        
        # Test API
        async with WildberriesAPI(test_account.api_key, force_demo=False) as api:
            is_valid = await api.validate_api_key()
            warehouses = await api.get_warehouses()
            slots = await api.get_supply_slots()
        
        mode = "🎭 Демо-режим" if api.demo_mode else "🌐 Реальный API"
        
        text = (
            "✅ **Тест API завершен**\n\n"
            f"**Режим**: {mode}\n"
            f"**API ключ**: {'Валиден' if is_valid else 'Невалиден'}\n"
            f"**Склады**: {len(warehouses)} найдено\n"
            f"**Слоты**: {len(slots)} найдено\n\n"
            f"**URL**: `{api.current_url}`"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_admin_keyboard(),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        await callback.message.edit_text(
            f"❌ **Ошибка тестирования API**\n\n"
            f"```\n{str(e)}\n```",
            reply_markup=get_admin_keyboard(),
            parse_mode="Markdown"
        )


@router.callback_query(F.data == "admin_stats")
async def handle_admin_stats(callback: CallbackQuery, db: DatabaseManager):
    """Show admin statistics"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    try:
        # Get statistics
        users = await db.get_active_users()
        total_users = len(users)
        total_accounts = sum(len(user.wb_accounts) for user in users)
        active_accounts = sum(len([acc for acc in user.wb_accounts if acc.is_active]) for user in users)
        
        text = (
            "📊 **Статистика системы**\n\n"
            f"👥 **Пользователи**: {total_users}\n"
            f"💼 **Всего аккаунтов**: {total_accounts}\n"
            f"✅ **Активных аккаунтов**: {active_accounts}\n\n"
            f"⚙️ **Настройки API**:\n"
            f"• Принудительный демо: {'Да' if settings.WB_API_FORCE_DEMO_MODE else 'Нет'}\n"
            f"• Fallback в демо: {'Да' if settings.WB_API_ALLOW_DEMO_FALLBACK else 'Нет'}\n"
            f"• Используется резерв: {'Да' if settings.WB_API_USE_BACKUP else 'Нет'}"
        )
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data="admin_back"
            )
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка получения статистики: {e}",
            reply_markup=get_admin_keyboard()
        )


@router.callback_query(F.data == "admin_back")
async def handle_admin_back(callback: CallbackQuery):
    """Return to admin main menu"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🛠 **Админ-панель**\n\n"
        "Выберите действие:",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown"
    ) 