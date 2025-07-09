from typing import Optional, List
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy import update, delete
from loguru import logger

from config import settings
from .models import Base, User, WBAccount, UserFilters, BookedSlot


class DatabaseManager:
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or settings.DATABASE_URL
        
        # Convert sqlite URL for async
        if self.database_url.startswith("sqlite://"):
            self.database_url = self.database_url.replace("sqlite://", "sqlite+aiosqlite://")
        
        self.engine = create_async_engine(self.database_url, echo=False)
        self.async_session = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def init_db(self):
        """Initialize database tables"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized")
    
    async def close(self):
        """Close database connection"""
        await self.engine.dispose()
    
    @asynccontextmanager
    async def session(self):
        """Get database session"""
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    # User methods
    async def create_user(self, telegram_id: int, username: Optional[str] = None,
                         first_name: Optional[str] = None, last_name: Optional[str] = None) -> User:
        """Create new user"""
        async with self.session() as session:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name
            )
            session.add(user)
            await session.flush()
            
            # Create default filters
            filters = UserFilters(user_id=user.id)
            session.add(filters)
            
            await session.refresh(user)
            return user
    
    async def get_user(self, telegram_id: int) -> Optional[User]:
        """Get user by telegram ID"""
        async with self.session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            return result.scalar_one_or_none()
    
    async def get_user_with_accounts(self, telegram_id: int) -> Optional[User]:
        """Get user with WB accounts"""
        async with self.session() as session:
            from sqlalchemy.orm import selectinload
            result = await session.execute(
                select(User)
                .where(User.telegram_id == telegram_id)
                .options(selectinload(User.wb_accounts))
            )
            return result.scalar_one_or_none()
    
    # WB Account methods
    async def add_wb_account(self, user_id: int, api_key: str, name: str) -> WBAccount:
        """Add WB account to user"""
        async with self.session() as session:
            account = WBAccount(
                user_id=user_id,
                api_key=api_key,  # Should be encrypted in production
                name=name
            )
            session.add(account)
            await session.flush()
            await session.refresh(account)
            return account
    
    async def get_user_accounts(self, user_id: int) -> List[WBAccount]:
        """Get all WB accounts for user"""
        async with self.session() as session:
            result = await session.execute(
                select(WBAccount).where(WBAccount.user_id == user_id)
            )
            return result.scalars().all()
    
    async def delete_wb_account(self, account_id: int, user_id: int) -> bool:
        """Delete WB account"""
        async with self.session() as session:
            result = await session.execute(
                delete(WBAccount).where(
                    WBAccount.id == account_id,
                    WBAccount.user_id == user_id
                )
            )
            return result.rowcount > 0
    
    # Filters methods
    async def get_user_filters(self, user_id: int) -> Optional[UserFilters]:
        """Get user filters"""
        async with self.session() as session:
            result = await session.execute(
                select(UserFilters).where(UserFilters.user_id == user_id)
            )
            return result.scalar_one_or_none()
    
    async def update_user_filters(self, user_id: int, **kwargs) -> UserFilters:
        """Update user filters"""
        async with self.session() as session:
            await session.execute(
                update(UserFilters)
                .where(UserFilters.user_id == user_id)
                .values(**kwargs)
            )
            
            result = await session.execute(
                select(UserFilters).where(UserFilters.user_id == user_id)
            )
            return result.scalar_one()
    
    # Booked slots methods
    async def add_booked_slot(self, user_id: int, wb_account_id: int, slot_data: dict, 
                            auto_booked: bool = False) -> BookedSlot:
        """Add booked slot record"""
        async with self.session() as session:
            slot = BookedSlot(
                user_id=user_id,
                wb_account_id=wb_account_id,
                slot_id=slot_data["id"],
                warehouse_id=slot_data["warehouse_id"],
                warehouse_name=slot_data["warehouse_name"],
                supply_date=slot_data["date"],
                time_slot=slot_data["time_slot"],
                coefficient=slot_data["coefficient"],
                auto_booked=auto_booked
            )
            session.add(slot)
            await session.flush()
            await session.refresh(slot)
            return slot
    
    async def get_user_booked_slots(self, user_id: int, limit: int = 10) -> List[BookedSlot]:
        """Get user's booked slots"""
        async with self.session() as session:
            result = await session.execute(
                select(BookedSlot)
                .where(BookedSlot.user_id == user_id)
                .order_by(BookedSlot.booked_at.desc())
                .limit(limit)
            )
            return result.scalars().all()
    
    async def get_active_users(self) -> List[User]:
        """Get all active users with active accounts"""
        async with self.session() as session:
            from sqlalchemy.orm import selectinload
            result = await session.execute(
                select(User)
                .where(User.is_active == True)
                .options(
                    selectinload(User.wb_accounts),
                    selectinload(User.filters)
                )
            )
            users = result.scalars().all()
            # Filter users with at least one active account
            return [u for u in users if any(acc.is_active for acc in u.wb_accounts)] 