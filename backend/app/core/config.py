from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Application
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-in-production"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://forgeboard:forgeboard@localhost:5432/forgeboard"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # JWT
    JWT_SECRET_KEY: str = "change-me-jwt-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # Encryption (Fernet) — NOTE: replace with a proper secrets vault before production
    FERNET_KEY: str = ""

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Google OAuth (for Calendar + Gmail connectors)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/connectors/oauth/google/callback"

    # Concurrency
    MAX_CONCURRENT_RUNS_PER_WORKSPACE: int = 5

    # ── Phase 8: Voice & Telephony ────────────────────────────────────────────
    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""          # E.164 e.g. +15551234567
    TWILIO_WEBHOOK_BASE_URL: str = ""      # Public URL Twilio posts to (ngrok in dev)

    # STT provider — "deepgram" (default) | pluggable via interface
    STT_PROVIDER: str = "deepgram"
    DEEPGRAM_API_KEY: str = ""

    # TTS provider — "elevenlabs" (default) | pluggable via interface
    TTS_PROVIDER: str = "elevenlabs"
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = "21m00Tcm4TlvDq8ikWAM"  # default "Rachel" voice

    # Max concurrent calls per workspace (separate from agent run cap)
    MAX_CONCURRENT_CALLS_PER_WORKSPACE: int = 3


settings = Settings()
