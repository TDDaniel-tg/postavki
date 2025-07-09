#!/usr/bin/env python3
"""
Утилита для тестирования API ключей Wildberries
Использование: python test_api_key.py YOUR_API_KEY
"""

import asyncio
import sys
from wb_api.client import WildberriesAPI
from loguru import logger

async def test_api_key(api_key: str):
    """Тестирование API ключа с подробным выводом"""
    
    print("=" * 60)
    print("🔑 ТЕСТИРОВАНИЕ API КЛЮЧА WILDBERRIES")
    print("=" * 60)
    
    # Создаем клиент
    async with WildberriesAPI(api_key, force_demo=False) as client:
        
        # 1. Валидация ключа
        print("\n1️⃣ Валидация API ключа...")
        is_valid = await client.validate_api_key()
        
        if is_valid and not client.demo_mode:
            print("✅ API ключ валиден и работает!")
        elif is_valid and client.demo_mode:
            print("⚠️  API endpoints недоступны, но ключ принят (демо-режим)")
        else:
            print("❌ API ключ невалиден")
            return
        
        # 2. Получение складов
        print("\n2️⃣ Получение списка складов...")
        try:
            warehouses = await client.get_warehouses()
            print(f"✅ Найдено складов: {len(warehouses)}")
            
            for warehouse in warehouses[:3]:  # Показываем первые 3
                print(f"   📦 {warehouse.name} ({warehouse.region})")
            
            if len(warehouses) > 3:
                print(f"   ... и еще {len(warehouses) - 3} складов")
                
        except Exception as e:
            print(f"❌ Ошибка получения складов: {e}")
        
        # 3. Получение слотов поставок
        print("\n3️⃣ Получение слотов поставок...")
        try:
            slots = await client.get_supply_slots(days_ahead=7)
            print(f"✅ Найдено слотов на 7 дней: {len(slots)}")
            
            # Группируем по складам
            warehouses_with_slots = {}
            for slot in slots:
                if slot.warehouse_name not in warehouses_with_slots:
                    warehouses_with_slots[slot.warehouse_name] = []
                warehouses_with_slots[slot.warehouse_name].append(slot)
            
            for warehouse_name, warehouse_slots in list(warehouses_with_slots.items())[:3]:
                available_slots = [s for s in warehouse_slots if s.is_available]
                print(f"   🏪 {warehouse_name}: {len(available_slots)} доступных слотов")
                
        except Exception as e:
            print(f"❌ Ошибка получения слотов: {e}")
        
        # 4. Тест бронирования (только для демо)
        if client.demo_mode and slots:
            print("\n4️⃣ Тестирование бронирования (демо)...")
            try:
                test_slot = slots[0]
                success = await client.book_slot(test_slot.id)
                if success:
                    print("✅ Демо-бронирование прошло успешно")
                else:
                    print("⚠️  Демо-бронирование не удалось")
            except Exception as e:
                print(f"❌ Ошибка тестирования бронирования: {e}")
        
        # 5. Статус
        print("\n" + "=" * 60)
        print("📊 ИТОГОВЫЙ СТАТУС:")
        
        if client.demo_mode:
            print("🟡 ДЕМО-РЕЖИМ: API endpoints недоступны")
            print("   Бот будет работать с тестовыми данными")
            print("   Для реального использования нужен доступ к WB API")
        else:
            print("🟢 ПОЛНЫЙ РЕЖИМ: API ключ работает!")
            print("   Бот готов к реальному использованию")
        
        print("=" * 60)


async def main():
    """Главная функция"""
    
    # Настройка логирования
    logger.remove()
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}",
        colorize=True
    )
    
    # Проверка аргументов
    if len(sys.argv) != 2:
        print("❌ Использование: python test_api_key.py YOUR_API_KEY")
        print("\n📖 Как получить API ключ:")
        print("1. Зайдите в личный кабинет Wildberries")
        print("2. Профиль → Настройки → Доступ к новому API")
        print("3. Создайте ключ с правами на поставки")
        return
    
    api_key = sys.argv[1].strip()
    
    if not api_key:
        print("❌ API ключ не может быть пустым")
        return
    
    # Тестирование
    try:
        await test_api_key(api_key)
    except KeyboardInterrupt:
        print("\n\n⏹️  Тестирование прервано пользователем")
    except Exception as e:
        print(f"\n\n❌ Неожиданная ошибка: {e}")
        logger.exception("Детали ошибки:")


if __name__ == "__main__":
    asyncio.run(main()) 