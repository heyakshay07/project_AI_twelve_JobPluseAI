from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_name: str = "JobPulse AI"
    database_url: str = "sqlite:///./jobpulse.db"
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    cors_origins: str = "http://localhost:5173"

    # Job sources. Keyless sources work out of the box; keyed ones are skipped if empty.
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    adzuna_countries: str = "in,gb,us"
    adzuna_queries: str = (
        "python developer,machine learning engineer,generative ai engineer,full stack developer"
    )
    adzuna_max_days_old: int = 7

    http_user_agent: str = "JobPulseAI/0.1"
    http_timeout_seconds: float = 20.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
