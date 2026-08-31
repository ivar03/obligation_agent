"""
Phase 19 Test Suite: Database Configuration & PostgreSQL Pooling Helpers.
Tests configuration helpers, environment detection, and SQLite rejection in production.
"""

import pytest
from app.core.config import Settings


def test_settings_environment_helpers():
    dev_settings = Settings(APP_ENV="development", DATABASE_URL="sqlite+aiosqlite:///./test.db")
    assert dev_settings.is_development() is True
    assert dev_settings.is_production() is False
    assert dev_settings.is_sqlite() is True
    assert dev_settings.is_postgres() is False

    prod_settings = Settings(
        APP_ENV="production",
        AUTH_MODE="production",
        DEBUG=False,
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
        JWT_SECRET_KEY="a" * 36,
        ENCRYPTION_KEY="k" * 32,
    )
    assert prod_settings.is_production() is True
    assert prod_settings.is_postgres() is True
    assert prod_settings.is_sqlite() is False
    errors = prod_settings.validate_production_config()
    assert len(errors) == 0


def test_production_sqlite_rejection():
    invalid_prod = Settings(
        APP_ENV="production",
        AUTH_MODE="production",
        DEBUG=False,
        DATABASE_URL="sqlite+aiosqlite:///./obligations.db",
        JWT_SECRET_KEY="a" * 36,
        ENCRYPTION_KEY="k" * 32,
    )
    errors = invalid_prod.validate_production_config()
    assert any("SQLite is not supported in production" in err or "PostgreSQL" in err for err in errors)
