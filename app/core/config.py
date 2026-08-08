"""Application settings, loaded from environment. Never hard-code secrets."""
from functools import lru_cache
from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "Mandi Ledger API"
    ENV: str = Field(default="development")  # development | staging | production
    DEBUG: bool = False

    # --- Database ---
    DATABASE_URL: PostgresDsn
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # --- Auth / JWT ---
    # Generate with: openssl rand -hex 32   (store in secret manager, never commit)
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15          # short-lived access token
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7             # rotating refresh token
    PASSWORD_MIN_LENGTH: int = 12

    # --- CORS: explicit allow-list only, never "*" with credentials ---
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # --- Rate limiting ---
    RATE_LIMIT_LOGIN: str = "5/minute"             # brute-force protection
    RATE_LIMIT_DEFAULT: str = "120/minute"

    # --- Cookies (refresh token is httpOnly, Secure, SameSite) ---
    COOKIE_SECURE: bool = True                     # True in prod (HTTPS only)
    COOKIE_SAMESITE: str = "strict"
    COOKIE_DOMAIN: str | None = None

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_prod(self) -> bool:
        return self.ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
