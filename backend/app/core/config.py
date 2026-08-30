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

    PROJECT_NAME: str = "Continuity Guardian API"
    VERSION: str = "0.1.0"
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


settings = Settings()
