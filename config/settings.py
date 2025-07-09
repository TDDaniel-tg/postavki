import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telegram Bot
    BOT_TOKEN: str
    
    # Database
    DATABASE_URL: str = "sqlite:///bot.db"
    
    # Monitoring
    MONITORING_INTERVAL: int = 5
    MAX_ACCOUNTS_PER_USER: int = 5
    
    # WB API
    WB_API_BASE_URL: str = "https://supplies-api.wildberries.ru"
    WB_API_BACKUP_URL: str = "https://marketplace-api.wildberries.ru"
    WB_API_TIMEOUT: int = 30
    WB_API_USE_BACKUP: bool = False
    
    # Demo mode settings
    WB_API_FORCE_DEMO_MODE: bool = False  # Принудительный демо-режим
    WB_API_ALLOW_DEMO_FALLBACK: bool = True  # Разрешить fallback в демо при ошибках API
    
    # API Endpoints (реальные эндпоинты WB API)
    WB_API_WAREHOUSES_ENDPOINT: str = "/api/v3/warehouses"
    WB_API_SLOTS_ENDPOINT: str = "/api/v3/supplies/acceptance/list"
    WB_API_BOOK_ENDPOINT: str = "/api/v3/supplies/acceptance/book"
    WB_API_BOOKED_ENDPOINT: str = "/api/v3/supplies/acceptance/booked"
    
    # Alternative endpoints to try
    WB_API_ALT_WAREHOUSES: str = "/api/v1/warehouses"
    WB_API_ALT_SLOTS: str = "/api/v1/supply/schedule"
    WB_API_ALT_BOOK: str = "/api/v1/supply/book"
    
    # Network settings
    WB_API_USE_IPV4_ONLY: bool = True
    WB_API_DNS_TIMEOUT: int = 10
    
    # Redis (опционально)
    REDIS_URL: str = ""
    
    # Admin
    ADMIN_IDS: list[int] = []
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings() 