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
    
    # API Endpoints (можно настроить разные варианты)
    WB_API_WAREHOUSES_ENDPOINT: str = "/api/v1/warehouses"
    WB_API_SLOTS_ENDPOINT: str = "/api/v1/supply/slots"
    WB_API_BOOK_ENDPOINT: str = "/api/v1/supply/book"
    WB_API_BOOKED_ENDPOINT: str = "/api/v1/supply/booked"
    
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