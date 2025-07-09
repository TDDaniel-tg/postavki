import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from loguru import logger

from config import settings
from database import DatabaseManager
from services import SupplyMonitor, NotificationService, BookingService, SupplyFinderService
from .handlers import setup_handlers
from .middlewares import setup_middlewares


async def create_bot():
    """Create and configure bot instance"""
    # Initialize bot
    bot = Bot(token=settings.BOT_TOKEN)
    
    # Initialize dispatcher with memory storage
    dp = Dispatcher(storage=MemoryStorage())
    
    # Initialize database
    db = DatabaseManager()
    await db.init_db()
    
    # Initialize services
    notification_service = NotificationService(bot)
    booking_service = BookingService(db, notification_service)
    supply_finder_service = SupplyFinderService(db, booking_service, notification_service)
    monitor = SupplyMonitor(db, notification_service, booking_service)
    
    # Setup handlers
    router = setup_handlers()
    dp.include_router(router)
    
    # Setup middlewares
    setup_middlewares(dp, db, booking_service, supply_finder_service)
    
    # Start monitoring
    await monitor.start()
    
    # Store references for cleanup
    dp["bot"] = bot
    dp["db"] = db
    dp["monitor"] = monitor
    dp["supply_finder"] = supply_finder_service
    
    logger.info("Bot initialized successfully")
    
    return bot, dp


async def run_bot():
    """Run the bot"""
    bot, dp = await create_bot()
    
    try:
        logger.info("Starting bot...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        # Cleanup
        supply_finder = dp.get("supply_finder")
        if supply_finder:
            await supply_finder.stop_all_searches()
        
        monitor = dp.get("monitor")
        if monitor:
            await monitor.stop()
        
        db = dp.get("db")
        if db:
            await db.close()
        
        await bot.session.close()
        logger.info("Bot stopped") 