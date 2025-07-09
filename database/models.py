from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float, 
    ForeignKey, JSON, Text, BigInteger
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    wb_accounts = relationship("WBAccount", back_populates="user", cascade="all, delete-orphan")
    filters = relationship("UserFilters", back_populates="user", uselist=False, cascade="all, delete-orphan")
    booked_slots = relationship("BookedSlot", back_populates="user", cascade="all, delete-orphan")


class WBAccount(Base):
    __tablename__ = "wb_accounts"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    api_key = Column(Text, nullable=False)  # Will be encrypted
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_check = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="wb_accounts")


class UserFilters(Base):
    __tablename__ = "user_filters"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    # Filter settings
    warehouses = Column(JSON, default=list)  # List of warehouse IDs
    regions = Column(JSON, default=list)  # List of regions
    min_coefficient = Column(Float, default=1.0)
    max_coefficient = Column(Float, nullable=True)
    time_slots = Column(JSON, default=list)  # List of preferred time slots
    
    # Auto booking settings
    auto_booking_enabled = Column(Boolean, default=False)
    auto_booking_limit = Column(Integer, default=5)  # Per day
    auto_booking_filters = Column(JSON, default=dict)  # Additional filters for auto booking
    
    # Notification settings
    notifications_enabled = Column(Boolean, default=True)
    quiet_hours_start = Column(Integer, nullable=True)  # Hour (0-23)
    quiet_hours_end = Column(Integer, nullable=True)  # Hour (0-23)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="filters")


class BookedSlot(Base):
    __tablename__ = "booked_slots"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    wb_account_id = Column(Integer, ForeignKey("wb_accounts.id"), nullable=False)
    
    # Slot information
    slot_id = Column(String(255), nullable=False)
    warehouse_id = Column(String(255), nullable=False)
    warehouse_name = Column(String(255), nullable=False)
    supply_date = Column(DateTime, nullable=False)
    time_slot = Column(String(50), nullable=False)
    coefficient = Column(Float, nullable=False)
    supply_number = Column(String(255), nullable=True)  # User's supply number
    
    # Booking details
    booked_at = Column(DateTime, default=datetime.utcnow)
    auto_booked = Column(Boolean, default=False)
    status = Column(String(50), default="booked")  # booked, cancelled, completed
    
    # Relationships
    user = relationship("User", back_populates="booked_slots")
    wb_account = relationship("WBAccount") 