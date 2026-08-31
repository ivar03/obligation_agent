import os
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    PROJECT_NAME: str = "Obligation Agent API"
    VERSION: str = "0.2.0"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./obligations.db"
    
    # CORS
    FRONTEND_URL: Union[str, List[str]] = "http://localhost:3000"
    
    @property
    def cors_origins(self) -> List[str]:
        if isinstance(self.FRONTEND_URL, list):
            return self.FRONTEND_URL
        return [origin.strip() for origin in self.FRONTEND_URL.split(",") if origin.strip()]

    # LLM Settings
    LLM_PROVIDER: str = "DEV_MOCK"  # "DEV_MOCK", "OPENAI", "GEMINI"
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # Phase 8: Slack Integration Settings
    SLACK_ENABLED: bool = False
    SLACK_SIGNING_SECRET: str = ""
    SLACK_BOT_TOKEN: str = ""
    SLACK_CLIENT_ID: str = ""
    SLACK_CLIENT_SECRET: str = ""
    SLACK_REDIRECT_URI: str = "http://localhost:8000/api/integrations/slack/callback"
    SLACK_SIGNATURE_TOLERANCE_SECONDS: int = 300  # 5 minutes against replay attacks

    # Phase 9: Gmail Integration Settings
    GMAIL_ENABLED: bool = False
    GMAIL_CLIENT_ID: str = ""
    GMAIL_CLIENT_SECRET: str = ""
    GMAIL_REDIRECT_URI: str = "http://localhost:8000/api/integrations/gmail/callback"
    GMAIL_PUBSUB_TOPIC: str = ""
    GMAIL_PUBSUB_VERIFICATION_TOKEN: str = ""

    # Phase 10: Google Calendar Integration Settings
    GOOGLE_CALENDAR_ENABLED: bool = False
    GOOGLE_CALENDAR_CLIENT_ID: str = ""
    GOOGLE_CALENDAR_CLIENT_SECRET: str = ""
    GOOGLE_CALENDAR_REDIRECT_URI: str = "http://localhost:8000/api/integrations/google_calendar/callback"
    GOOGLE_CALENDAR_WEBHOOK_SECRET: str = ""

    # Environment and Security (Phase 17)
    APP_ENV: str = "development"  # "development", "staging", "production"
    AUTH_MODE: str = "mock"  # "mock", "production"
    JWT_SECRET_KEY: str = "dev-jwt-secret-key-change-in-production-1234567890"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    ENCRYPTION_KEY: str = ""  # Base64 Fernet key or auto-derived from JWT_SECRET_KEY
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 120
    RATE_LIMIT_AUTH_PER_MINUTE: int = 15
    RATE_LIMIT_WEBHOOK_PER_MINUTE: int = 300
    DATA_RETENTION_DAYS: int = 90
    WORKER_ENABLED: bool = True
    WORKER_CONCURRENCY: int = 4

    def is_production(self) -> bool:
        return self.APP_ENV.lower() in ("production", "prod")

    def is_production_auth(self) -> bool:
        return self.AUTH_MODE.lower() == "production" or self.is_production()

    def validate_production_config(self) -> List[str]:
        """
        Validates configuration integrity. Returns a list of error descriptions.
        If empty, configuration is valid.
        """
        errors: List[str] = []
        if self.is_production():
            if self.DEBUG:
                errors.append("DEBUG must be False in production environment.")
            if "dev-jwt-secret" in self.JWT_SECRET_KEY or len(self.JWT_SECRET_KEY) < 32:
                errors.append("JWT_SECRET_KEY must be a secure high-entropy string (>= 32 characters) in production.")
            if self.AUTH_MODE.lower() != "production":
                errors.append("AUTH_MODE must be set to 'production' when APP_ENV is production.")
            if self.DATABASE_URL.startswith("sqlite") and ":memory:" in self.DATABASE_URL:
                errors.append("In-memory SQLite cannot be used as persistent storage in production.")
        return errors


settings = Settings()

