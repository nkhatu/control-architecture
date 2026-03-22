from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[4]


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "provenance-service"
    app_env: str = "local"
    host: str = "0.0.0.0"
    port: int = Field(default=8006, validation_alias="PROVENANCE_SERVICE_PORT")
    auto_create_schema: bool = Field(default=False, validation_alias="PROVENANCE_AUTO_CREATE_SCHEMA")

    database_url: str | None = Field(default=None, validation_alias="PROVENANCE_DATABASE_URL")
    postgres_host: str = Field(default="localhost", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    postgres_db: str = Field(default="agentic_money_provenance", validation_alias="PROVENANCE_POSTGRES_DB")
    postgres_user: str = Field(default="postgres", validation_alias="POSTGRES_USER")
    postgres_password: str = Field(default="postgres", validation_alias="POSTGRES_PASSWORD")

    control_plane_config_path: str = Field(
        default="config/control-plane/default.yaml",
        validation_alias="CONTROL_PLANE_CONFIG_PATH",
    )

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url

        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def resolved_control_plane_config_path(self) -> Path:
        path = Path(self.control_plane_config_path)
        if path.is_absolute():
            return path
        return REPO_ROOT / path


def load_control_plane_config(settings: AppSettings) -> dict[str, Any]:
    with settings.resolved_control_plane_config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
