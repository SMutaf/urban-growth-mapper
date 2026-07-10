from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Urban Growth Mapper API"
    database_url: str = "postgresql://postgres:postgres@localhost:5433/urban_growth_mapper"
    cors_origins: List[str] = ["http://localhost:5173"]
    google_geocoding_api_key: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
