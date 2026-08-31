"""
Phase 19 Application Configuration.

All settings are read from environment variables and .env files.
Helper methods support environment detection, PostgreSQL vs SQLite detection,
and production configuration validation.
"""
from typing import List, Union
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

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    DATABASE_URL: str = "sqlite+aiosqlite:///./obligations.db"
    # PostgreSQL connection pool (ignored for SQLite)
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800   # 30 min — forces connection refresh
    DB_ECHO: bool = False

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    FRONTEND_URL: Union[str, List[str]] = "http://localhost:3000"

    @property
    def cors_origins(self) -> List[str]:
        if isinstance(self.FRONTEND_URL, list):
            return self.FRONTEND_URL
        return [o.strip() for o in self.FRONTEND_URL.split(",") if o.strip()]

    # -------------------------------------------------------------------------
    # LLM (Phase 20 Natural-Language Intelligence Layer)
    # -------------------------------------------------------------------------
    LLM_ENABLED: bool = True
    LLM_PROVIDER: str = "mock"  # "mock" | "openai" | "local" | "anthropic"
    LLM_MODEL: str = "mock-intelligence-v1"
    LLM_MAX_REQUESTS_PER_MINUTE: int = 60
    LLM_MAX_TOKENS_PER_REQUEST: int = 2048
    LLM_MAX_DAILY_REQUESTS: int = 5000
    LLM_TIMEOUT_SECONDS: float = 5.0
    LLM_TEMPERATURE: float = 0.0
    LLM_FALLBACK_TO_DETERMINISTIC: bool = True
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # -------------------------------------------------------------------------
    # Slack Integration (Phase 8)
    # -------------------------------------------------------------------------
    SLACK_ENABLED: bool = False
    SLACK_SIGNING_SECRET: str = ""
    SLACK_BOT_TOKEN: str = ""
    SLACK_CLIENT_ID: str = ""
    SLACK_CLIENT_SECRET: str = ""
    SLACK_REDIRECT_URI: str = "http://localhost:8000/api/integrations/slack/callback"
    SLACK_SIGNATURE_TOLERANCE_SECONDS: int = 300

    # -------------------------------------------------------------------------
    # Gmail Integration (Phase 9)
    # -------------------------------------------------------------------------
    GMAIL_ENABLED: bool = False
    GMAIL_CLIENT_ID: str = ""
    GMAIL_CLIENT_SECRET: str = ""
    GMAIL_REDIRECT_URI: str = "http://localhost:8000/api/integrations/gmail/callback"
    GMAIL_PUBSUB_TOPIC: str = ""
    GMAIL_PUBSUB_VERIFICATION_TOKEN: str = ""

    # -------------------------------------------------------------------------
    # Google Calendar Integration (Phase 10)
    # -------------------------------------------------------------------------
    GOOGLE_CALENDAR_ENABLED: bool = False
    GOOGLE_CALENDAR_CLIENT_ID: str = ""
    GOOGLE_CALENDAR_CLIENT_SECRET: str = ""
    GOOGLE_CALENDAR_REDIRECT_URI: str = "http://localhost:8000/api/integrations/google_calendar/callback"
    GOOGLE_CALENDAR_WEBHOOK_SECRET: str = ""

    # -------------------------------------------------------------------------
    # Environment & Security (Phase 17)
    # -------------------------------------------------------------------------
    APP_ENV: str = "development"   # "development" | "staging" | "production"
    AUTH_MODE: str = "mock"        # "mock" | "production"
    JWT_SECRET_KEY: str = "dev-jwt-secret-key-change-in-production-1234567890"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24    # 24 hours
    ENCRYPTION_KEY: str = ""                      # Fernet key; auto-derived in dev

    # Rate limits (requests/minute)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 120
    RATE_LIMIT_AUTH_PER_MINUTE: int = 15
    RATE_LIMIT_WEBHOOK_PER_MINUTE: int = 300

    DATA_RETENTION_DAYS: int = 90

    # -------------------------------------------------------------------------
    # Background Worker (Phase 17 base, Phase 19 durable extension)
    # -------------------------------------------------------------------------
    WORKER_ENABLED: bool = True
    WORKER_CONCURRENCY: int = 4
    # Phase 19: durable DB-backed queue
    WORKER_DURABLE_QUEUE: bool = True
    WORKER_LEASE_TIMEOUT_SECONDS: int = 300   # crash recovery threshold
    WORKER_MAX_QUEUE_DEPTH: int = 10_000
    WORKER_POLL_INTERVAL_SECONDS: float = 1.0
    WORKER_JOB_MAX_AGE_HOURS: int = 24

    # -------------------------------------------------------------------------
    # Phase 19: Circuit Breaker / Provider Failure Isolation
    # -------------------------------------------------------------------------
    CB_FAILURE_THRESHOLD: int = 5    # consecutive failures before OPEN
    CB_RECOVERY_TIMEOUT: int = 60    # seconds before HALF_OPEN retry
    PROVIDER_TIMEOUT_SECONDS: int = 10

    # -------------------------------------------------------------------------
    # Phase 19: Resource Protection Hard Limits
    # -------------------------------------------------------------------------
    MAX_REQUEST_BODY_BYTES: int = 10 * 1024 * 1024     # 10 MB
    MAX_WEBHOOK_PAYLOAD_BYTES: int = 1 * 1024 * 1024   # 1 MB
    MAX_CSV_FILE_BYTES: int = 5 * 1024 * 1024           # 5 MB
    MAX_CSV_ROWS: int = 10_000
    MAX_SEARCH_RESULTS: int = 200
    MAX_GRAPH_DEPTH: int = 50
    MAX_GRAPH_NODES: int = 5_000
    MAX_SIMULATION_SCENARIOS: int = 100
    MAX_EVENT_BATCH_SIZE: int = 500

    # -------------------------------------------------------------------------
    # Phase 19: Endpoint-specific Rate Limits (per workspace, per minute)
    # -------------------------------------------------------------------------
    RATE_LIMIT_CSV_IMPORT_PER_MINUTE: int = 10
    RATE_LIMIT_SEARCH_PER_MINUTE: int = 30
    RATE_LIMIT_DECISION_GEN_PER_MINUTE: int = 20
    RATE_LIMIT_EXECUTION_DISPATCH_PER_MINUTE: int = 10

    # -------------------------------------------------------------------------
    # Phase 19: Backup & Disaster Recovery
    # -------------------------------------------------------------------------
    BACKUP_ENABLED: bool = True
    BACKUP_DIR: str = "./backups"
    BACKUP_RETENTION_COUNT: int = 7
    BACKUP_VERIFY_ON_CREATE: bool = True

    # -------------------------------------------------------------------------
    # Phase 19: Observability
    # -------------------------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "text"        # "json" (production) | "text" (development)
    METRICS_ENABLED: bool = True
    METRICS_WINDOW_SIZE: int = 1000  # rolling sample count for percentile calculation

    # =========================================================================
    # Environment Detection Helpers
    # =========================================================================

    def is_production(self) -> bool:
        return self.APP_ENV.lower() in ("production", "prod")

    def is_staging(self) -> bool:
        return self.APP_ENV.lower() == "staging"

    def is_development(self) -> bool:
        return self.APP_ENV.lower() in ("development", "dev", "test")

    def is_production_auth(self) -> bool:
        return self.AUTH_MODE.lower() == "production" or self.is_production()

    def is_postgres(self) -> bool:
        return "postgresql" in self.DATABASE_URL or "postgres" in self.DATABASE_URL

    def is_sqlite(self) -> bool:
        return "sqlite" in self.DATABASE_URL

    def validate_production_config(self) -> List[str]:
        """
        Validates configuration integrity for production deployment.
        Returns a list of error descriptions. Empty list means config is valid.
        """
        errors: List[str] = []
        if self.is_production():
            if self.DEBUG:
                errors.append("DEBUG must be False in production.")
            if "dev-jwt-secret" in self.JWT_SECRET_KEY or len(self.JWT_SECRET_KEY) < 32:
                errors.append(
                    "JWT_SECRET_KEY must be a secure high-entropy string "
                    "(>= 32 characters) in production."
                )
            if self.AUTH_MODE.lower() != "production":
                errors.append("AUTH_MODE must be 'production' when APP_ENV is production.")
            if self.is_sqlite():
                errors.append(
                    "SQLite is not supported in production. "
                    "Set DATABASE_URL to a PostgreSQL connection string."
                )
            if self.ENCRYPTION_KEY == "":
                errors.append("ENCRYPTION_KEY must be explicitly configured in production.")
        if self.is_staging():
            if self.is_sqlite():
                errors.append("SQLite is not recommended for staging; prefer PostgreSQL.")
        return errors


settings = Settings()
