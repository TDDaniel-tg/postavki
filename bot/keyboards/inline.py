from typing import List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from wb_api.models import SupplySlot, Warehouse


def get_slot_keyboard(slot_id: str) -> InlineKeyboardMarkup:
    """Get keyboard for supply slot notification"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="🎯 Забронировать",
            callback_data=f"book_{slot_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="❌ Пропустить",
            callback_data=f"skip_{slot_id}"
        ),
        InlineKeyboardButton(
            text="⚙️ Настройки",
            callback_data="settings"
        )
    )
    
    return builder.as_markup()


def get_account_list_keyboard(accounts: List[dict]) -> InlineKeyboardMarkup:
    """Get keyboard with account list"""
    builder = InlineKeyboardBuilder()
    
    for account in accounts:
        status = "🟢" if account.get("is_active") else "🔴"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {account['name']}",
                callback_data=f"account_{account['id']}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text="➕ Добавить аккаунт",
            callback_data="add_account"
        )
    )
    
    return builder.as_markup()


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Get settings keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="🏭 Склады",
            callback_data="filter_warehouses"
        ),
        InlineKeyboardButton(
            text="📍 Регионы",
            callback_data="filter_regions"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📊 Коэффициент",
            callback_data="filter_coefficient"
        ),
        InlineKeyboardButton(
            text="🕐 Время",
            callback_data="filter_time"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🤖 Автобронирование",
            callback_data="auto_booking"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔔 Уведомления",
            callback_data="notifications"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="back_to_main"
        )
    )
    
    return builder.as_markup()


def get_filter_keyboard(filter_type: str, current_values: List[str] = None) -> InlineKeyboardMarkup:
    """Get filter selection keyboard"""
    builder = InlineKeyboardBuilder()
    
    # This would be populated with actual data
    # For now, just show structure
    if filter_type == "warehouses":
        # Would show actual warehouses
        builder.row(
            InlineKeyboardButton(
                text="✅ Коледино",
                callback_data="toggle_warehouse_koledino"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="⬜ Электросталь",
                callback_data="toggle_warehouse_elektrostal"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text="💾 Сохранить",
            callback_data=f"save_{filter_type}"
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="settings"
        )
    )
    
    return builder.as_markup()


def get_warehouses_keyboard(
    warehouses: List[Warehouse], 
    selected: List[str] = None
) -> InlineKeyboardMarkup:
    """Get warehouses selection keyboard"""
    builder = InlineKeyboardBuilder()
    selected = selected or []
    
    for warehouse in warehouses:
        check = "✅" if warehouse.id in selected else "⬜"
        builder.row(
            InlineKeyboardButton(
                text=f"{check} {warehouse.name}",
                callback_data=f"toggle_wh_{warehouse.id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text="💾 Сохранить",
            callback_data="save_warehouses"
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="settings"
        )
    )
    
    return builder.as_markup()


def get_auto_booking_keyboard(enabled: bool = False) -> InlineKeyboardMarkup:
    """Get auto booking settings keyboard"""
    builder = InlineKeyboardBuilder()
    
    status = "включено ✅" if enabled else "выключено ❌"
    toggle_text = "Выключить ❌" if enabled else "Включить ✅"
    
    builder.row(
        InlineKeyboardButton(
            text=f"Статус: {status}",
            callback_data="none"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=toggle_text,
            callback_data="toggle_auto_booking"
        )
    )
    
    if enabled:
        builder.row(
            InlineKeyboardButton(
                text="⚙️ Настройки автобронирования",
                callback_data="auto_booking_settings"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="settings"
        )
    )
    
    return builder.as_markup()


def get_account_selection_keyboard(accounts: List) -> InlineKeyboardMarkup:
    """Get keyboard for account selection during booking"""
    builder = InlineKeyboardBuilder()
    
    for account in accounts:
        builder.row(
            InlineKeyboardButton(
                text=f"👤 {account.name}",
                callback_data=f"select_account_{account.id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="cancel_booking"
        )
    )
    
    return builder.as_markup() 