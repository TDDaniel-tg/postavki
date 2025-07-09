from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger

from database import DatabaseManager
from wb_api import WildberriesAPI, InvalidAPIKeyError
from bot.keyboards import get_cancel_keyboard, get_main_keyboard, get_account_list_keyboard
from bot.states import AccountStates
from config import settings


router = Router()


@router.message(Command("add_account"))
@router.message(F.text == "➕ Добавить аккаунт")
async def cmd_add_account(message: Message, state: FSMContext, db: DatabaseManager):
    """Handle add account command"""
    # Check user exists
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала используйте /start")
        return
    
    # Check account limit
    accounts = await db.get_user_accounts(user.id)
    if len(accounts) >= settings.MAX_ACCOUNTS_PER_USER:
        await message.answer(
            f"❌ Достигнут лимит аккаунтов ({settings.MAX_ACCOUNTS_PER_USER}).\n"
            f"Удалите неиспользуемые аккаунты."
        )
        return
    
    await state.set_state(AccountStates.waiting_for_api_key)
    await message.answer(
        "🔑 Отправьте API ключ от личного кабинета WB.\n\n"
        "Где взять ключ:\n"
        "1. Войдите в личный кабинет WB\n"
        "2. Перейдите в раздел 'Доступ к API'\n"
        "3. Создайте новый токен с правами на поставки\n"
        "4. Скопируйте и отправьте его сюда\n\n"
        "⚠️ Никому не передавайте ваш API ключ!",
        reply_markup=get_cancel_keyboard()
    )


@router.message(AccountStates.waiting_for_api_key)
async def process_api_key(message: Message, state: FSMContext, db: DatabaseManager):
    """Process API key input"""
    if message.text == "❌ Отмена":
        await state.clear()
        user = await db.get_user_with_accounts(message.from_user.id)
        has_accounts = len(user.wb_accounts) > 0 if user else False
        await message.answer(
            "Добавление аккаунта отменено.",
            reply_markup=get_main_keyboard(has_accounts)
        )
        return
    
    api_key = message.text.strip()
    
    # Delete message with API key for security
    try:
        await message.delete()
    except:
        pass
    
    # Show processing message
    processing_msg = await message.answer("🔄 Проверка API ключа...")
    
    try:
        # Validate API key
        async with WildberriesAPI(api_key) as api:
            is_valid = await api.validate_api_key()
        
        if not is_valid:
            await processing_msg.edit_text("❌ Неверный API ключ. Попробуйте еще раз.")
            return
        
        # API key is valid, ask for account name
        await state.update_data(api_key=api_key)
        await state.set_state(AccountStates.waiting_for_account_name)
        
        await processing_msg.edit_text(
            "✅ API ключ принят!\n\n"
            "Введите название для этого аккаунта (например: 'Основной' или 'ИП Иванов'):"
        )
        
    except InvalidAPIKeyError:
        await processing_msg.edit_text("❌ Неверный API ключ. Проверьте и попробуйте снова.")
    except Exception as e:
        logger.error(f"Error validating API key: {e}")
        await processing_msg.edit_text(
            "❌ Ошибка при проверке ключа. Попробуйте позже."
        )


@router.message(AccountStates.waiting_for_account_name)
async def process_account_name(message: Message, state: FSMContext, db: DatabaseManager):
    """Process account name input"""
    if message.text == "❌ Отмена":
        await state.clear()
        user = await db.get_user_with_accounts(message.from_user.id)
        has_accounts = len(user.wb_accounts) > 0 if user else False
        await message.answer(
            "Добавление аккаунта отменено.",
            reply_markup=get_main_keyboard(has_accounts)
        )
        return
    
    account_name = message.text.strip()[:100]  # Limit name length
    
    # Get data from state
    data = await state.get_data()
    api_key = data.get("api_key")
    
    if not api_key:
        await state.clear()
        await message.answer("❌ Ошибка. Начните заново с /add_account")
        return
    
    # Get user
    user = await db.get_user(message.from_user.id)
    
    try:
        # Add account to database
        account = await db.add_wb_account(
            user_id=user.id,
            api_key=api_key,
            name=account_name
        )
        
        await state.clear()
        
        # Update keyboard
        accounts = await db.get_user_accounts(user.id)
        
        await message.answer(
            f"✅ Аккаунт '{account_name}' успешно добавлен!\n\n"
            f"Теперь вы будете получать уведомления о новых слотах.\n"
            f"Настройте фильтры через меню 'Настройки'.",
            reply_markup=get_main_keyboard(has_accounts=True)
        )
        
        logger.info(f"Account added for user {user.id}: {account_name}")
        
    except Exception as e:
        logger.error(f"Error adding account: {e}")
        await message.answer(
            "❌ Ошибка при добавлении аккаунта. Попробуйте позже.",
            reply_markup=get_main_keyboard(has_accounts=False)
        )
        await state.clear()


@router.message(Command("list_accounts"))
@router.message(F.text == "💼 Мои аккаунты")
async def cmd_list_accounts(message: Message, db: DatabaseManager):
    """Handle list accounts command"""
    user = await db.get_user_with_accounts(message.from_user.id)
    
    if not user:
        await message.answer("❌ Вы не зарегистрированы. Используйте /start")
        return
    
    if not user.wb_accounts:
        await message.answer(
            "У вас нет подключенных аккаунтов.\n"
            "Используйте /add_account для добавления."
        )
        return
    
    # Format accounts list
    accounts_data = []
    for acc in user.wb_accounts:
        accounts_data.append({
            "id": acc.id,
            "name": acc.name,
            "is_active": acc.is_active
        })
    
    text = (
        "💼 <b>Ваши аккаунты WB:</b>\n\n"
        "Нажмите на аккаунт для управления:"
    )
    
    keyboard = get_account_list_keyboard(accounts_data)
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("account_"))
async def handle_account_action(callback: CallbackQuery, db: DatabaseManager):
    """Handle account actions"""
    account_id = int(callback.data.split("_")[1])
    
    # Get account info
    accounts = await db.get_user_accounts(callback.from_user.id)
    account = next((acc for acc in accounts if acc.id == account_id), None)
    
    if not account:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return
    
    # TODO: Show account menu with options to toggle, delete, etc.
    await callback.answer(f"Аккаунт: {account.name}", show_alert=True)


@router.callback_query(F.data == "add_account")
async def handle_add_account_callback(callback: CallbackQuery, state: FSMContext, db: DatabaseManager):
    """Handle add account from inline keyboard"""
    await callback.message.delete()
    await cmd_add_account(callback.message, state, db) 