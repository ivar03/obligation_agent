"""
Phase 19 Database Configuration.

Supports both SQLite (development/test) and PostgreSQL (staging/production).
PostgreSQL connections use a sized connection pool with health-check ping.
SQLite uses check_same_thread=False for async compatibility.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


def _build_engine() -> AsyncEngine:
    """Build the SQLAlchemy async engine with environment-appropriate settings."""
    if settings.is_sqlite():
        # SQLite: single-file dev/test mode
        return create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DB_ECHO,
            connect_args={"check_same_thread": False},
            future=True,
        )
    else:
        # PostgreSQL: production-grade connection pool
        return create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DB_ECHO,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            pool_recycle=settings.DB_POOL_RECYCLE,
            pool_pre_ping=True,   # verify connections before use
            future=True,
        )


engine: AsyncEngine = _build_engine()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency providing a transactional database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
