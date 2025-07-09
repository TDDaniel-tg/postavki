from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def get_main_keyboard(has_accounts: bool = False) -> ReplyKeyboardMarkup:
    """Get main menu keyboard"""
    builder = ReplyKeyboardBuilder()
    
    if has_accounts:
        builder.row(
            KeyboardButton(text="📊 Статус мониторинга"),
            KeyboardButton(text="⚙️ Настройки")
        )
        builder.row(
            KeyboardButton(text="🚚 Забронировать поставку"),
            KeyboardButton(text="📋 История бронирований")
        )
        builder.row(
            KeyboardButton(text="💼 Мои аккаунты")
        )
    
    builder.row(
        KeyboardButton(text="➕ Добавить аккаунт"),
        KeyboardButton(text="❓ Помощь")
    )
    
    return builder.as_markup(resize_keyboard=True)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Get cancel keyboard"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True)


def get_yes_no_keyboard() -> ReplyKeyboardMarkup:
    """Get yes/no keyboard"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="✅ Да"),
        KeyboardButton(text="❌ Нет")
    )
    return builder.as_markup(resize_keyboard=True) 