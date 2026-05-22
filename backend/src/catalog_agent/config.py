"""Application settings loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Look for .env in the project root (three levels above this file: src/catalog_agent/config.py
# → src/catalog_agent/ → src/ → backend/ → project root) and also in CWD as a fallback.
_PROJECT_ROOT = Path(__file__).parents[3]
_ENV_FILES = (str(_PROJECT_ROOT / ".env"), ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES, env_file_encoding="utf-8", extra="ignore"
    )

    gcp_project_id: str = "project-5c016d48-80d5-4534-b69"
    catalog_dataset: str = "catalog_registry"
    lineage_location: str = "us"
    lineage_fetch_concurrency: int = 4
    jobs_fallback_lookback_days: int = 90
    enable_jobs_column_inference: bool = False
    enable_llm_pii: bool = False
    google_application_credentials: str = ""
    api_key: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
