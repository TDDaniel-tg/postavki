from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List


@dataclass
class Warehouse:
    """Warehouse model"""
    id: str
    name: str
    region: str
    address: Optional[str] = None
    is_active: bool = True


@dataclass
class SupplySlot:
    """Supply slot model"""
    id: str
    warehouse_id: str
    warehouse_name: str
    date: datetime
    time_start: str
    time_end: str
    coefficient: float
    is_available: bool = True
    region: Optional[str] = None
    
    @property
    def time_slot(self) -> str:
        """Get formatted time slot"""
        return f"{self.time_start}-{self.time_end}"
    
    @property
    def date_str(self) -> str:
        """Get formatted date"""
        return self.date.strftime("%d.%m.%Y")
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "warehouse_id": self.warehouse_id,
            "warehouse_name": self.warehouse_name,
            "date": self.date,
            "time_slot": self.time_slot,
            "coefficient": self.coefficient,
            "is_available": self.is_available,
            "region": self.region
        } 