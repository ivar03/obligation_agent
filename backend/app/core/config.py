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


settings = Settings()
