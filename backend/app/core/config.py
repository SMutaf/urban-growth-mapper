from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Urban Growth Mapper API"
    database_url: str = "postgresql://postgres:postgres@localhost:5433/urban_growth_mapper"
    cors_origins: List[str] = ["http://localhost:5173"]
    google_geocoding_api_key: Optional[str] = None

    # Advisory chat (see app/domain/interpretation/advisory_interfaces.py) -
    # a local Ollama server by default, but every field is env-overridable
    # so switching to a different model or a remote API later is a config
    # change, not a code change.
    advisory_llm_enabled: bool = True
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:12b"
    advisory_llm_temperature: float = 0.3
    # A dense downtown point can put 80+ nearby features in the context,
    # pushing the prompt to Ollama's context-window limit - measured at
    # ~140s for gemma3:12b on local hardware for such a prompt, so this
    # needs real headroom above that, not the 60s a chat reply would
    # normally need.
    advisory_llm_timeout_seconds: int = 300

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
