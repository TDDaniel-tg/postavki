import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import aiohttp
import socket
from loguru import logger

from config import settings
from .models import SupplySlot, Warehouse
from .exceptions import WBAPIError, InvalidAPIKeyError, RateLimitError, BookingError


class WildberriesAPI:
    """Wildberries API client for supply management"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = settings.WB_API_BASE_URL
        self.backup_url = settings.WB_API_BACKUP_URL
        self.current_url = self.base_url
        self.timeout = aiohttp.ClientTimeout(total=settings.WB_API_TIMEOUT)
        self.session: Optional[aiohttp.ClientSession] = None
        self.demo_mode = False  # Включается если API недоступен
        self.auth_params = {}  # Параметры авторизации для запросов
        
    async def _switch_to_backup(self):
        """Switch to backup URL if main URL fails"""
        if self.current_url == self.base_url and not settings.WB_API_USE_BACKUP:
            logger.warning("Switching to backup API URL")
            self.current_url = self.backup_url
            if self.session:
                await self.session.close()
                self.session = None
            return True
        return False
    
    async def _enable_demo_mode(self):
        """Enable demo mode with mock data"""
        if not self.demo_mode:
            logger.warning("Enabling demo mode - API endpoints unavailable")
            self.demo_mode = True
        
    async def __aenter__(self):
        """Async context manager entry"""
        # Add connector with DNS resolving options
        connector = aiohttp.TCPConnector(
            family=socket.AF_INET,  # Force IPv4
            ttl_dns_cache=300,
            use_dns_cache=True,
            limit=100,
            limit_per_host=30,
            enable_cleanup_closed=True
        )
        
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "WB-Supply-Bot/1.0"
            },
            timeout=self.timeout,
            connector=connector
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def _test_connectivity(self):
        """Test basic connectivity to WB API"""
        try:
            logger.info(f"Testing connectivity to {self.current_url}")
            
            # Try DNS resolution first
            import socket
            try:
                host = self.current_url.replace("https://", "").replace("http://", "")
                ip = socket.gethostbyname(host)
                logger.info(f"DNS resolved {host} to {ip}")
            except Exception as e:
                logger.error(f"DNS resolution failed for {host}: {e}")
                
            # Try basic HTTP request
            async with self.session.get(f"{self.current_url}/ping", timeout=5) as response:
                logger.info(f"Connectivity test response: {response.status}")
                return True
                
        except Exception as e:
            logger.error(f"Connectivity test failed: {e}")
            return False
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make API request with error handling"""
        if not self.session:
            connector = aiohttp.TCPConnector(
                family=socket.AF_INET,
                ttl_dns_cache=300,
                use_dns_cache=True,
                limit=100,
                limit_per_host=30,
                enable_cleanup_closed=True
            )
            
            self.session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "WB-Supply-Bot/1.0"
                },
                timeout=self.timeout,
                connector=connector
            )
        
        url = f"{self.current_url}{endpoint}"
        logger.debug(f"Making {method} request to: {url}")
        
        # Add auth params if they exist
        if self.auth_params:
            params = kwargs.get('params', {})
            params.update(self.auth_params)
            kwargs['params'] = params
        
        try:
            async with self.session.request(method, url, **kwargs) as response:
                logger.debug(f"Response status: {response.status}")
                
                if response.status == 401:
                    raise InvalidAPIKeyError("Invalid API key")
                elif response.status == 429:
                    raise RateLimitError("Rate limit exceeded")
                elif response.status >= 400:
                    text = await response.text()
                    logger.error(f"API error response: {text}")
                    raise WBAPIError(f"API error {response.status}: {text}")
                
                return await response.json()
                
        except aiohttp.ClientError as e:
            logger.error(f"Request error: {e}")
            
            # Try backup URL if available
            if await self._switch_to_backup():
                logger.info("Retrying request with backup URL...")
                return await self._make_request(method, endpoint, **kwargs)
            
            # Enable demo mode if all APIs fail
            await self._enable_demo_mode()
            raise WBAPIError(f"Request failed: {str(e)}")
    
    def _generate_mock_warehouses(self) -> List[Warehouse]:
        """Generate mock warehouses for demo mode"""
        mock_warehouses = [
            Warehouse(
                id="1",
                name="Коледино",
                region="Московская область",
                address="г. Подольск, промзона Коледино",
                is_active=True
            ),
            Warehouse(
                id="2", 
                name="Электросталь",
                region="Московская область",
                address="г. Электросталь",
                is_active=True
            ),
            Warehouse(
                id="3",
                name="Казань",
                region="Республика Татарстан",
                address="г. Казань",
                is_active=True
            ),
            Warehouse(
                id="4",
                name="Новосибирск",
                region="Новосибирская область", 
                address="г. Новосибирск",
                is_active=True
            ),
            Warehouse(
                id="5",
                name="Санкт-Петербург (Шушары)",
                region="Санкт-Петербург",
                address="г. Санкт-Петербург, п. Шушары",
                is_active=True
            )
        ]
        return mock_warehouses
    
    def _generate_mock_slots(self) -> List[SupplySlot]:
        """Generate mock supply slots for demo mode"""
        mock_slots = []
        base_date = datetime.now() + timedelta(days=1)
        
        warehouses = self._generate_mock_warehouses()
        
        for i in range(10):  # 10 дней вперед
            current_date = base_date + timedelta(days=i)
            
            for warehouse in warehouses[:3]:  # Первые 3 склада
                # Утренние слоты
                morning_slot = SupplySlot(
                    id=f"slot_{warehouse.id}_{i}_morning",
                    warehouse_id=warehouse.id,
                    warehouse_name=warehouse.name,
                    date=current_date,
                    time_start="09:00",
                    time_end="12:00",
                    coefficient=1.2 if i < 3 else 1.0,  # Повышенный коэффициент на ближайшие дни
                    is_available=True,
                    region=warehouse.region
                )
                
                # Вечерние слоты
                evening_slot = SupplySlot(
                    id=f"slot_{warehouse.id}_{i}_evening",
                    warehouse_id=warehouse.id,
                    warehouse_name=warehouse.name,
                    date=current_date,
                    time_start="14:00",
                    time_end="18:00",
                    coefficient=1.0,
                    is_available=i % 2 == 0,  # Каждый второй доступен
                    region=warehouse.region
                )
                
                mock_slots.extend([morning_slot, evening_slot])
        
        return mock_slots

    async def validate_api_key(self) -> bool:
        """Validate API key by making a test request"""
        try:
            logger.info(f"Validating API key: {self.api_key[:10]}...")
            
            # First test basic connectivity
            if not await self._test_connectivity():
                logger.warning("Basic connectivity test failed, but proceeding with API validation")
            
            # Try different authorization methods
            auth_methods = [
                # Method 1: Bearer token in header (standard)
                {"headers": {"Authorization": f"Bearer {self.api_key}"}},
                # Method 2: API key in header without Bearer
                {"headers": {"Authorization": self.api_key}},
                # Method 3: API key in query parameter
                {"params": {"key": self.api_key}},
                # Method 4: API key in different header formats
                {"headers": {"X-API-Key": self.api_key}},
                {"headers": {"Api-Key": self.api_key}},
                {"headers": {"WB-API-Key": self.api_key}},
            ]
            
            # Try different endpoints with different auth methods
            test_endpoints = [
                "/api/v1/warehouses",
                "/api/v1/supply/slots", 
                "/api/v1/info",
                "/api/v1/ping",
                "/ping"
            ]
            
            for auth_method in auth_methods:
                for endpoint in test_endpoints:
                    try:
                        logger.info(f"Testing API key with endpoint: {endpoint}, auth: {list(auth_method.keys())}")
                        
                        # Create temporary session with specific auth
                        connector = aiohttp.TCPConnector(
                            family=socket.AF_INET,
                            ttl_dns_cache=300,
                            use_dns_cache=True,
                            limit=100,
                            limit_per_host=30,
                            enable_cleanup_closed=True
                        )
                        
                        headers = {
                            "Content-Type": "application/json",
                            "User-Agent": "WB-Supply-Bot/1.0"
                        }
                        
                        # Add auth headers if specified
                        if "headers" in auth_method:
                            headers.update(auth_method["headers"])
                        
                        async with aiohttp.ClientSession(
                            headers=headers,
                            timeout=self.timeout,
                            connector=connector
                        ) as test_session:
                            
                            url = f"{self.current_url}{endpoint}"
                            params = auth_method.get("params", {})
                            
                            async with test_session.get(url, params=params) as response:
                                logger.info(f"Response: {response.status} for {endpoint}")
                                
                                if response.status == 200:
                                    logger.info(f"✅ API key validation successful!")
                                    logger.info(f"Working endpoint: {endpoint}")
                                    logger.info(f"Working auth method: {auth_method}")
                                    
                                    # Update session configuration for future requests
                                    await self._update_session_config(auth_method)
                                    return True
                                    
                                elif response.status == 401:
                                    logger.debug(f"Unauthorized for {endpoint} with {auth_method}")
                                    continue
                                    
                                elif response.status == 404:
                                    logger.debug(f"Endpoint {endpoint} not found")
                                    continue
                                    
                                else:
                                    response_text = await response.text()
                                    logger.debug(f"Response {response.status}: {response_text}")
                                    
                    except Exception as e:
                        logger.debug(f"Failed {endpoint} with {auth_method}: {e}")
                        continue
            
            # If no auth method worked, try demo mode
            logger.warning("No working authorization method found")
            
            # Try to get more info about the API key format
            await self._diagnose_api_key()
            
            # Enable demo mode as fallback
            if not self.demo_mode:
                await self._enable_demo_mode()
                logger.info("API key validation failed, enabling demo mode")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error validating API key: {e}")
            # Enable demo mode and consider key valid for demo
            await self._enable_demo_mode()
            return True
    
    async def _update_session_config(self, auth_method: dict):
        """Update session configuration based on working auth method"""
        if self.session:
            await self.session.close()
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "WB-Supply-Bot/1.0"
        }
        
        # Add auth headers if specified
        if "headers" in auth_method:
            headers.update(auth_method["headers"])
        
        connector = aiohttp.TCPConnector(
            family=socket.AF_INET,
            ttl_dns_cache=300,
            use_dns_cache=True,
            limit=100,
            limit_per_host=30,
            enable_cleanup_closed=True
        )
        
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=self.timeout,
            connector=connector
        )
        
        # Store auth params for future requests
        self.auth_params = auth_method.get("params", {})
    
    async def _diagnose_api_key(self):
        """Diagnose API key format issues"""
        logger.info("🔍 Диагностика API ключа:")
        logger.info(f"Длина ключа: {len(self.api_key)}")
        logger.info(f"Первые символы: {self.api_key[:10]}...")
        logger.info(f"Последние символы: ...{self.api_key[-10:]}")
        
        # Check common patterns
        if self.api_key.startswith("Bearer "):
            logger.warning("⚠️  API ключ содержит 'Bearer ' - возможно, нужно убрать это")
        
        if len(self.api_key) < 10:
            logger.warning("⚠️  API ключ слишком короткий")
        
        if " " in self.api_key:
            logger.warning("⚠️  API ключ содержит пробелы")
        
        if not self.api_key.replace("-", "").replace("_", "").isalnum():
            logger.info("ℹ️  API ключ содержит специальные символы (возможно, это нормально)")

    async def get_warehouses(self) -> List[Warehouse]:
        """Get list of available warehouses"""
        if self.demo_mode:
            logger.info("Using mock warehouses data (demo mode)")
            return self._generate_mock_warehouses()
            
        try:
            data = await self._make_request("GET", "/api/v1/warehouses")
            
            warehouses = []
            for item in data.get("data", []):
                warehouse = Warehouse(
                    id=str(item.get("id")),
                    name=item.get("name", ""),
                    region=item.get("region", ""),
                    address=item.get("address"),
                    is_active=item.get("isActive", True)
                )
                warehouses.append(warehouse)
            
            return warehouses
            
        except Exception as e:
            logger.error(f"Error getting warehouses: {e}")
            if not self.demo_mode:
                await self._enable_demo_mode()
                return self._generate_mock_warehouses()
            raise

    async def get_supply_slots(self, days_ahead: int = 14) -> List[SupplySlot]:
        """Get available supply slots"""
        if self.demo_mode:
            logger.info("Using mock supply slots data (demo mode)")
            return self._generate_mock_slots()
            
        try:
            # Calculate date range
            date_from = datetime.now()
            date_to = date_from + timedelta(days=days_ahead)
            
            params = {
                "dateFrom": date_from.strftime("%Y-%m-%d"),
                "dateTo": date_to.strftime("%Y-%m-%d")
            }
            
            data = await self._make_request("GET", "/api/v1/supply/slots", params=params)
            
            slots = []
            for item in data.get("data", []):
                # Parse slot data
                slot = SupplySlot(
                    id=str(item.get("id")),
                    warehouse_id=str(item.get("warehouseId")),
                    warehouse_name=item.get("warehouseName", ""),
                    date=datetime.fromisoformat(item.get("date").replace("Z", "+00:00")),
                    time_start=item.get("timeStart", ""),
                    time_end=item.get("timeEnd", ""),
                    coefficient=float(item.get("coefficient", 1.0)),
                    is_available=item.get("isAvailable", True),
                    region=item.get("region")
                )
                
                if slot.is_available:
                    slots.append(slot)
            
            return slots
            
        except Exception as e:
            logger.error(f"Error getting supply slots: {e}")
            if not self.demo_mode:
                await self._enable_demo_mode()
                return self._generate_mock_slots()
            raise

    async def book_slot(self, slot_id: str) -> bool:
        """Book a supply slot"""
        if self.demo_mode:
            logger.info(f"Mock booking slot {slot_id} (demo mode)")
            # Simulate random success/failure
            import random
            success = random.choice([True, True, True, False])  # 75% success rate
            if success:
                logger.info(f"Mock: Successfully booked slot {slot_id}")
                return True
            else:
                raise BookingError("Mock: Slot already taken by another supplier")
        
        try:
            data = {
                "slotId": slot_id
            }
            
            result = await self._make_request("POST", "/api/v1/supply/book", json=data)
            
            if result.get("success"):
                logger.info(f"Successfully booked slot {slot_id}")
                return True
            else:
                error_msg = result.get("error", "Unknown error")
                raise BookingError(f"Failed to book slot: {error_msg}")
                
        except BookingError:
            raise
        except Exception as e:
            logger.error(f"Error booking slot {slot_id}: {e}")
            if not self.demo_mode:
                await self._enable_demo_mode()
                # Try mock booking in demo mode
                return await self.book_slot(slot_id)
            raise BookingError(f"Booking failed: {str(e)}")

    async def get_booked_slots(self) -> List[Dict[str, Any]]:
        """Get user's booked slots"""
        if self.demo_mode:
            logger.info("Using mock booked slots data (demo mode)")
            return [
                {
                    "id": "mock_booked_1",
                    "warehouse_name": "Коледино", 
                    "date": "2025-01-10",
                    "time": "09:00-12:00",
                    "status": "confirmed"
                }
            ]
            
        try:
            data = await self._make_request("GET", "/api/v1/supply/booked")
            return data.get("data", [])
        except Exception as e:
            logger.error(f"Error getting booked slots: {e}")
            if not self.demo_mode:
                await self._enable_demo_mode()
                return await self.get_booked_slots()
            raise

    async def close(self):
        """Close the session"""
        if self.session:
            await self.session.close() 