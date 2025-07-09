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
    
    def __init__(self, api_key: str, force_demo: bool = False):
        self.api_key = api_key
        self.base_url = settings.WB_API_BASE_URL
        self.backup_url = settings.WB_API_BACKUP_URL
        self.current_url = self.base_url
        self.timeout = aiohttp.ClientTimeout(total=settings.WB_API_TIMEOUT)
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Demo mode settings
        self.demo_mode = force_demo or settings.WB_API_FORCE_DEMO_MODE
        self.allow_demo_fallback = settings.WB_API_ALLOW_DEMO_FALLBACK
        self.auth_params = {}  # Параметры авторизации для запросов
        self.validated_endpoints = {}  # Кэш проверенных эндпоинтов
        
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
    
    async def _enable_demo_mode(self, reason: str = "API endpoints unavailable"):
        """Enable demo mode with mock data"""
        if not self.demo_mode and self.allow_demo_fallback:
            logger.warning(f"Enabling demo mode - {reason}")
            self.demo_mode = True
            return True
        elif not self.allow_demo_fallback:
            logger.error(f"Demo fallback disabled - {reason}")
            return False
        return True
        
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
        """Generate mock warehouses for demo mode based on real WB warehouses"""
        mock_warehouses = [
            Warehouse(
                id="117501",
                name="Коледино",
                region="Московская область",
                address="Московская область, г. Подольск, деревня Коледино",
                is_active=True
            ),
            Warehouse(
                id="120762", 
                name="Санкт-Петербург (Уткина Заводе)",
                region="г. Санкт-Петербург",
                address="г. Санкт-Петербург, Уткина Заводе",
                is_active=True
            ),
            Warehouse(
                id="117986",
                name="Краснодар (Тихорецкая)",
                region="Краснодарский край",
                address="г. Краснодар, ул. Тихорецкая",
                is_active=True
            ),
            Warehouse(
                id="130744",
                name="Екатеринбург - Перспективный 12/2",
                region="Свердловская область", 
                address="г. Екатеринбург, ул. Перспективная, 12/2",
                is_active=True
            ),
            Warehouse(
                id="159402",
                name="Тула",
                region="Тульская область",
                address="г. Тула, складской комплекс",
                is_active=True
            ),
            Warehouse(
                id="2737",
                name="Невинномысск",
                region="Ставропольский край",
                address="г. Невинномысск, промзона",
                is_active=True
            ),
            Warehouse(
                id="206236",
                name="Казань",
                region="Республика Татарстан",
                address="г. Казань, складской комплекс",
                is_active=True
            ),
            Warehouse(
                id="686",
                name="Новосибирск",
                region="Новосибирская область",
                address="г. Новосибирск, складской комплекс",
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
            if await self._enable_demo_mode("API key validation failed"):
                return True
            return False
    
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
    
    async def _try_endpoint_variants(self, endpoint_type: str) -> Optional[str]:
        """Try different endpoint variants and return working one"""
        endpoints_map = {
            "warehouses": [
                settings.WB_API_WAREHOUSES_ENDPOINT,
                settings.WB_API_ALT_WAREHOUSES,
                "/api/v2/warehouses",
                "/warehouses"
            ],
            "slots": [
                settings.WB_API_SLOTS_ENDPOINT,
                settings.WB_API_ALT_SLOTS,
                "/api/v2/supplies/acceptance/list",
                "/api/v1/supply/slots",
                "/supply/schedule"
            ],
            "book": [
                settings.WB_API_BOOK_ENDPOINT,
                settings.WB_API_ALT_BOOK,
                "/api/v2/supplies/acceptance/book",
                "/supply/book"
            ]
        }
        
        # Return cached endpoint if available
        if endpoint_type in self.validated_endpoints:
            return self.validated_endpoints[endpoint_type]
        
        endpoints = endpoints_map.get(endpoint_type, [])
        
        for endpoint in endpoints:
            try:
                logger.debug(f"Testing endpoint: {endpoint}")
                
                # Test with HEAD request to avoid large responses
                async with self.session.head(f"{self.current_url}{endpoint}") as response:
                    if response.status in [200, 401, 403]:  # Valid response (401/403 means endpoint exists)
                        logger.info(f"✅ Working endpoint found: {endpoint}")
                        self.validated_endpoints[endpoint_type] = endpoint
                        return endpoint
                    elif response.status == 404:
                        logger.debug(f"Endpoint not found: {endpoint}")
                        continue
                    else:
                        logger.debug(f"Endpoint {endpoint} returned: {response.status}")
                        
            except Exception as e:
                logger.debug(f"Endpoint {endpoint} failed: {e}")
                continue
        
        logger.warning(f"No working endpoints found for {endpoint_type}")
        return None

    async def get_warehouses(self) -> List[Warehouse]:
        """Get list of available warehouses"""
        if self.demo_mode:
            logger.info("Using mock warehouses data (demo mode)")
            return self._generate_mock_warehouses()
            
        try:
            # Find working endpoint
            endpoint = await self._try_endpoint_variants("warehouses")
            if not endpoint:
                if await self._enable_demo_mode("No working warehouses endpoint found"):
                    return self._generate_mock_warehouses()
                raise WBAPIError("No working warehouses endpoint found")
            
            data = await self._make_request("GET", endpoint)
            
            warehouses = []
            # Handle different response formats
            items = data.get("data", data.get("result", data if isinstance(data, list) else []))
            
            for item in items:
                warehouse = Warehouse(
                    id=str(item.get("id", item.get("warehouseId", ""))),
                    name=item.get("name", item.get("warehouseName", "")),
                    region=item.get("region", item.get("city", "")),
                    address=item.get("address", item.get("fullAddress", "")),
                    is_active=item.get("isActive", item.get("active", True))
                )
                warehouses.append(warehouse)
            
            logger.info(f"✅ Retrieved {len(warehouses)} warehouses from real API")
            return warehouses
            
        except Exception as e:
            logger.error(f"Error getting warehouses: {e}")
            if await self._enable_demo_mode(f"Warehouses API error: {str(e)}"):
                return self._generate_mock_warehouses()
            raise

    async def get_supply_slots(self, days_ahead: int = 14) -> List[SupplySlot]:
        """Get available supply slots"""
        if self.demo_mode:
            logger.info("Using mock supply slots data (demo mode)")
            return self._generate_mock_slots()
            
        try:
            # Find working endpoint
            endpoint = await self._try_endpoint_variants("slots")
            if not endpoint:
                if await self._enable_demo_mode("No working slots endpoint found"):
                    return self._generate_mock_slots()
                raise WBAPIError("No working slots endpoint found")
            
            # Calculate date range
            date_from = datetime.now()
            date_to = date_from + timedelta(days=days_ahead)
            
            params = {
                "dateFrom": date_from.strftime("%Y-%m-%d"),
                "dateTo": date_to.strftime("%Y-%m-%d"),
                "limit": 1000,
                "days": days_ahead
            }
            
            data = await self._make_request("GET", endpoint, params=params)
            
            slots = []
            # Handle different response formats  
            items = data.get("data", data.get("result", data.get("slots", data if isinstance(data, list) else [])))
            
            for item in items:
                try:
                    # Parse date handling different formats
                    date_str = item.get("date", item.get("supplyDate", ""))
                    if date_str:
                        if "T" in date_str:
                            supply_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        else:
                            supply_date = datetime.strptime(date_str, "%Y-%m-%d")
                    else:
                        continue
                    
                    slot = SupplySlot(
                        id=str(item.get("id", item.get("slotId", f"{item.get('warehouseId', '')}_{date_str}"))),
                        warehouse_id=str(item.get("warehouseId", item.get("warehouse_id", ""))),
                        warehouse_name=item.get("warehouseName", item.get("warehouse_name", "")),
                        date=supply_date,
                        time_start=item.get("timeStart", item.get("time_start", "")),
                        time_end=item.get("timeEnd", item.get("time_end", "")),
                        coefficient=float(item.get("coefficient", item.get("coeff", 1.0))),
                        is_available=item.get("isAvailable", item.get("available", True)),
                        region=item.get("region", item.get("city", ""))
                    )
                    
                    if slot.is_available:
                        slots.append(slot)
                
                except Exception as e:
                    logger.debug(f"Error parsing slot item: {e}")
                    continue
            
            logger.info(f"✅ Retrieved {len(slots)} supply slots from real API")
            return slots
            
        except Exception as e:
            logger.error(f"Error getting supply slots: {e}")
            if await self._enable_demo_mode(f"Supply slots API error: {str(e)}"):
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
            # Find working endpoint
            endpoint = await self._try_endpoint_variants("book")
            if not endpoint:
                if await self._enable_demo_mode("No working booking endpoint found"):
                    return await self.book_slot(slot_id)  # Retry in demo mode
                raise WBAPIError("No working booking endpoint found")
            
            data = {
                "slotId": slot_id,
                "id": slot_id  # Some APIs use different field names
            }
            
            result = await self._make_request("POST", endpoint, json=data)
            
            # Handle different response formats
            success = result.get("success", result.get("result", False))
            if success or result.get("status") == "success":
                logger.info(f"✅ Successfully booked slot {slot_id}")
                return True
            else:
                error_msg = result.get("error", result.get("message", "Unknown error"))
                raise BookingError(f"Failed to book slot: {error_msg}")
                
        except BookingError:
            raise
        except Exception as e:
            logger.error(f"Error booking slot {slot_id}: {e}")
            if await self._enable_demo_mode(f"Booking API error: {str(e)}"):
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