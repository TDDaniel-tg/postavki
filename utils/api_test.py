"""
Диагностическая утилита для тестирования Wildberries API endpoints
"""
import asyncio
import aiohttp
import socket


class APITester:
    """Тестирование различных API endpoints"""
    
    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=10)
        
    async def test_dns_resolution(self, host: str) -> bool:
        """Тест DNS резолвинга"""
        try:
            ip = socket.gethostbyname(host)
            print(f"✓ DNS resolved {host} to {ip}")
            return True
        except Exception as e:
            print(f"✗ DNS resolution failed for {host}: {e}")
            return False
    
    async def test_http_connectivity(self, url: str, endpoint: str = "") -> bool:
        """Тест HTTP подключения"""
        try:
            test_url = f"{url}{endpoint}"
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(test_url) as response:
                    print(f"✓ HTTP connection to {test_url}: {response.status}")
                    return True
        except Exception as e:
            print(f"✗ HTTP connection failed to {test_url}: {e}")
            return False
    
    async def test_api_endpoints(self):
        """Тестирование различных WB API endpoints"""
        
        # Список возможных API URLs
        api_urls = [
            "https://suppliers-api.wildberries.ru",
            "https://supplies-api.wildberries.ru", 
            "https://api.wildberries.ru",
            "https://seller-api.wildberries.ru",
            "https://marketplace-api.wildberries.ru",
            "https://public-api.wildberries.ru",
            "https://openapi.wildberries.ru"
        ]
        
        # Список возможных endpoints
        test_endpoints = [
            "",
            "/ping",
            "/api/v1/ping",
            "/api/v1/warehouses",
            "/api/v1/supply/slots"
        ]
        
        print("=== WB API Connectivity Test ===")
        
        for url in api_urls:
            print(f"\nTesting: {url}")
            
            # Test DNS first
            host = url.replace("https://", "").replace("http://", "")
            if not await self.test_dns_resolution(host):
                continue
                
            # Test basic connectivity
            if await self.test_http_connectivity(url):
                # Test specific endpoints
                for endpoint in test_endpoints:
                    await self.test_http_connectivity(url, endpoint)
                    await asyncio.sleep(0.5)  # Rate limiting
    
    async def test_public_wb_api(self):
        """Тестирование публичного API WB (без авторизации)"""
        print("\n=== Testing Public WB API ===")
        
        public_urls = [
            "https://card.wb.ru/cards/detail?appType=1&curr=rub&dest=-1257786&regions=80,38,83,4,64,33,68,70,30,40,86,75,69,1,66,110,31,48,22,71,114&nm=162195684",
            "https://static-basket-01.wb.ru/vol0/data/main-menu-ru-ru-v3.json",
            "https://common-api.wildberries.ru/ping"
        ]
        
        for url in public_urls:
            await self.test_http_connectivity(url)
            await asyncio.sleep(1)


async def run_diagnostics():
    """Запуск диагностики"""
    tester = APITester()
    await tester.test_api_endpoints()
    await tester.test_public_wb_api()


if __name__ == "__main__":
    asyncio.run(run_diagnostics()) 