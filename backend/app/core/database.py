"""
Database Connection Manager

Manages database connections and sessions using SQLAlchemy with async support.
Provides a clean interface for database operations throughout the application.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData, text
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
import logging

from .config import settings

# Create declarative base for models
Base = declarative_base()

# Metadata for table reflection
metadata = MetaData()

# Logger
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Database connection manager with async support
    
    Handles:
    - Database engine creation and management
    - Session management with proper cleanup
    - Connection health checks
    - Graceful startup and shutdown
    """
    
    def __init__(self):
        self.engine: Optional[object] = None
        self.session_factory: Optional[async_sessionmaker] = None
        self._is_connected: bool = False
    
    async def initialize(self) -> None:
        """Initialize database connection and session factory"""
        try:
            # Convert database URL for async if needed
            db_url = self._get_async_database_url()
            
            # Create async engine
            self.engine = create_async_engine(
                db_url,
                echo=settings.database_echo,
                future=True,
                # Connection pool settings
                pool_pre_ping=True,
                pool_recycle=3600,  # Recycle connections every hour
            )
            
            # Create session factory
            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )
            
            # Test connection
            await self._test_connection()
            self._is_connected = True
            
            logger.info(f"✅ Database initialized successfully: {db_url}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")
            self._is_connected = False
            raise
    
    async def close(self) -> None:
        """Close database connections gracefully"""
        try:
            if self.engine:
                await self.engine.dispose()
                logger.info("✅ Database connections closed successfully")
            self._is_connected = False
        except Exception as e:
            logger.error(f"❌ Error closing database connections: {e}")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get database session with automatic cleanup
        
        Usage:
            async with database_manager.get_session() as session:
                # Use session for database operations
                result = await session.execute(query)
        """
        if not self.session_factory:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def _test_connection(self) -> None:
        """Test database connection"""
        if not self.engine:
            raise RuntimeError("Database engine not initialized")
        
        async with self.engine.begin() as conn:
            # Simple test query
            await conn.execute(text("SELECT 1"))
    
    def _get_async_database_url(self) -> str:
        """Convert database URL to async version if needed"""
        db_url = settings.database_url
        
        # Convert sync URLs to async versions
        if db_url.startswith("postgresql://"):
            return db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif db_url.startswith("mysql://"):
            return db_url.replace("mysql://", "mysql+aiomysql://", 1)
        elif db_url.startswith("sqlite:///"):
            return db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        
        # Return as-is if already async or unknown
        return db_url
    
    @property
    def is_connected(self) -> bool:
        """Check if database is connected"""
        return self._is_connected
    
    async def health_check(self) -> dict:
        """
        Perform health check on database connection
        
        Returns:
            dict: Health status information
        """
        try:
            if not self.engine:
                return {
                    "status": "disconnected",
                    "message": "Database engine not initialized"
                }
            
            # Test connection
            await self._test_connection()
            
            return {
                "status": "healthy",
                "message": "Database connection is working",
                "url": self._get_async_database_url().split("@")[-1] if "@" in self._get_async_database_url() else "local"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Database connection failed: {str(e)}"
            }


# Global database manager instance
database_manager = DatabaseManager()


# Dependency for FastAPI routes
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions
    
    Usage in routes:
        @app.get("/users/")
        async def get_users(db: AsyncSession = Depends(get_db_session)):
            # Use db session
    """
    async with database_manager.get_session() as session:
        yield session


# Utility functions for database operations
async def create_tables() -> None:
    """Create all tables defined in models"""
    if not database_manager.engine:
        raise RuntimeError("Database not initialized")
    
    async with database_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("✅ Database tables created successfully")


async def drop_tables() -> None:
    """Drop all tables (use with caution!)"""
    if not database_manager.engine:
        raise RuntimeError("Database not initialized")
    
    async with database_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    logger.info("✅ Database tables dropped successfully")