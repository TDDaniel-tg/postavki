import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import aiohttp
from loguru import logger

from config import settings
from .models import SupplySlot, Warehouse
from .exceptions import WBAPIError, InvalidAPIKeyError, RateLimitError, BookingError


class WildberriesAPI:
    """Wildberries API client for supply management"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = settings.WB_API_BASE_URL
        self.timeout = aiohttp.ClientTimeout(total=settings.WB_API_TIMEOUT)
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=self.timeout
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make API request with error handling"""
        if not self.session:
            self.session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=self.timeout
            )
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with self.session.request(method, url, **kwargs) as response:
                if response.status == 401:
                    raise InvalidAPIKeyError("Invalid API key")
                elif response.status == 429:
                    raise RateLimitError("Rate limit exceeded")
                elif response.status >= 400:
                    text = await response.text()
                    raise WBAPIError(f"API error {response.status}: {text}")
                
                return await response.json()
                
        except aiohttp.ClientError as e:
            logger.error(f"Request error: {e}")
            raise WBAPIError(f"Request failed: {str(e)}")
    
    async def validate_api_key(self) -> bool:
        """Validate API key by making a test request"""
        try:
            # Make a simple request to check if key is valid
            await self._make_request("GET", "/api/v1/warehouses")
            return True
        except InvalidAPIKeyError:
            return False
        except Exception as e:
            logger.error(f"Error validating API key: {e}")
            return False
    
    async def get_warehouses(self) -> List[Warehouse]:
        """Get list of available warehouses"""
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
            raise
    
    async def get_supply_slots(self, days_ahead: int = 14) -> List[SupplySlot]:
        """Get available supply slots"""
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
            raise
    
    async def book_slot(self, slot_id: str) -> bool:
        """Book a supply slot"""
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
            raise BookingError(f"Booking failed: {str(e)}")
    
    async def get_booked_slots(self) -> List[Dict[str, Any]]:
        """Get user's booked slots"""
        try:
            data = await self._make_request("GET", "/api/v1/supply/booked")
            return data.get("data", [])
        except Exception as e:
            logger.error(f"Error getting booked slots: {e}")
            raise
    
    async def close(self):
        """Close the session"""
        if self.session:
            await self.session.close() 