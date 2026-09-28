from functools import lru_cache
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        # Some hosts (Heroku-style, some Neon/Render strings) hand out
        # postgres:// URLs; SQLAlchemy 2.0 only recognizes postgresql://.
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        return v
    JWT_SECRET: str = "change-me"
    JWT_ALG: str = "HS256"
    JWT_TTL_HOURS: int = 24    # a day, then the PIN is asked for again
    OWNER_PIN: str = "1234"

    # No SUPABASE_* settings: nothing uploads files any more. Spreadsheets are
    # parsed in memory and discarded, so the only Supabase service in use is
    # Postgres itself, reached through DATABASE_URL.

    CORS_ORIGINS: str = "http://localhost:3000"
    DEFAULT_SYP_PER_USD: float = 15000.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
