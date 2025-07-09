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
    WB_API_BASE_URL: str = "https://suppliers-api.wildberries.ru"
    WB_API_TIMEOUT: int = 30
    
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