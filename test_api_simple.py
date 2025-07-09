#!/usr/bin/env python3
"""
Упрощенная утилита для тестирования API ключей Wildberries
Использование: python test_api_simple.py YOUR_API_KEY
"""

import asyncio
import sys
import aiohttp
import socket


class SimpleAPITester:
    """Простое тестирование WB API ключей"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.timeout = aiohttp.ClientTimeout(total=10)
        
    async def test_key_formats(self):
        """Тестирование разных форматов API ключа"""
        
        print("=" * 60)
        print("🔑 ТЕСТИРОВАНИЕ API КЛЮЧА WILDBERRIES")
        print("=" * 60)
        
        print(f"\n📋 Информация о ключе:")
        print(f"   Длина: {len(self.api_key)} символов")
        print(f"   Первые символы: {self.api_key[:10]}...")
        print(f"   Последние символы: ...{self.api_key[-10:]}")
        
        # Проверяем формат
        if " " in self.api_key:
            print("   ⚠️  Ключ содержит пробелы")
        if self.api_key.startswith("Bearer "):
            print("   ⚠️  Ключ начинается с 'Bearer ' (возможно, лишнее)")
        if len(self.api_key) < 10:
            print("   ⚠️  Ключ слишком короткий")
        
        # Базовые URL для тестирования
        test_urls = [
            "https://supplies-api.wildberries.ru",
            "https://marketplace-api.wildberries.ru",
            "https://openapi.wildberries.ru"
        ]
        
        # Методы авторизации
        auth_methods = [
            {"headers": {"Authorization": f"Bearer {self.api_key}"}, "name": "Bearer token"},
            {"headers": {"Authorization": self.api_key}, "name": "Direct Authorization"},
            {"params": {"key": self.api_key}, "name": "Query parameter"},
            {"headers": {"X-API-Key": self.api_key}, "name": "X-API-Key header"},
            {"headers": {"Api-Key": self.api_key}, "name": "Api-Key header"},
        ]
        
        # Тестовые endpoints
        test_endpoints = ["/api/v1/warehouses", "/api/v1/info", "/ping"]
        
        print(f"\n🌐 Тестирование подключения к API...")
        
        for base_url in test_urls:
            print(f"\n🔗 {base_url}")
            
            # Проверяем DNS
            host = base_url.replace("https://", "").replace("http://", "")
            try:
                ip = socket.gethostbyname(host)
                print(f"   ✅ DNS: {host} → {ip}")
            except Exception as e:
                print(f"   ❌ DNS: {e}")
                continue
            
            # Тестируем методы авторизации
            success_found = False
            
            for auth_method in auth_methods:
                for endpoint in test_endpoints:
                    try:
                        url = f"{base_url}{endpoint}"
                        
                        headers = {
                            "Content-Type": "application/json",
                            "User-Agent": "WB-Supply-Bot-Test/1.0"
                        }
                        
                        if "headers" in auth_method:
                            headers.update(auth_method["headers"])
                        
                        params = auth_method.get("params", {})
                        
                        async with aiohttp.ClientSession(timeout=self.timeout) as session:
                            async with session.get(url, headers=headers, params=params) as response:
                                status = response.status
                                
                                if status == 200:
                                    print(f"   ✅ {auth_method['name']}: {endpoint} → 200 OK")
                                    success_found = True
                                elif status == 401:
                                    print(f"   🔒 {auth_method['name']}: {endpoint} → 401 Unauthorized")
                                elif status == 404:
                                    print(f"   🔍 {auth_method['name']}: {endpoint} → 404 Not Found")
                                elif status == 403:
                                    print(f"   🚫 {auth_method['name']}: {endpoint} → 403 Forbidden")
                                else:
                                    response_text = (await response.text())[:100]
                                    print(f"   ❓ {auth_method['name']}: {endpoint} → {status} {response_text}")
                                    
                    except asyncio.TimeoutError:
                        print(f"   ⏱️  {auth_method['name']}: {endpoint} → Timeout")
                    except Exception as e:
                        print(f"   ❌ {auth_method['name']}: {endpoint} → Error: {str(e)[:50]}")
                        
            if not success_found:
                print(f"   ⚠️  Ни один метод авторизации не сработал для {base_url}")
        
        print("\n" + "=" * 60)
        print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
        print("✅ = Ключ работает")
        print("🔒 = Неправильная авторизация")  
        print("🔍 = Endpoint не найден")
        print("❌ = Проблемы с подключением")
        print("=" * 60)


async def main():
    """Главная функция"""
    
    if len(sys.argv) != 2:
        print("❌ Использование: python test_api_simple.py YOUR_API_KEY")
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
        tester = SimpleAPITester(api_key)
        await tester.test_key_formats()
    except KeyboardInterrupt:
        print("\n\n⏹️  Тестирование прервано пользователем")
    except Exception as e:
        print(f"\n\n❌ Неожиданная ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 