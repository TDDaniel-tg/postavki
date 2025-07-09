from aiogram.fsm.state import State, StatesGroup


class UserStates(StatesGroup):
    """Main user states"""
    waiting_for_api_key = State()
    main_menu = State()


class AccountStates(StatesGroup):
    """Account management states"""
    waiting_for_api_key = State()
    waiting_for_account_name = State()
    selecting_account_to_delete = State()


class FilterStates(StatesGroup):
    """Filter settings states"""
    selecting_warehouses = State()
    selecting_regions = State()
    setting_coefficient = State()
    setting_time_slots = State()
    setting_auto_booking = State() 