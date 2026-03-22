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

    app_name: str = "workflow-worker"
    app_env: str = "local"
    host: str = "0.0.0.0"
    port: int = Field(default=8004, validation_alias="WORKFLOW_WORKER_PORT")
    control_plane_config_path: str = Field(
        default="config/control-plane/default.yaml",
        validation_alias="CONTROL_PLANE_CONFIG_PATH",
    )
    context_memory_service_base_url: str = Field(
        default="http://localhost:8002",
        validation_alias="CONTEXT_MEMORY_SERVICE_BASE_URL",
    )
    provenance_service_base_url: str = Field(
        default="http://localhost:8006",
        validation_alias="PROVENANCE_SERVICE_BASE_URL",
    )
    capability_gateway_base_url: str = Field(
        default="http://localhost:8001",
        validation_alias="CAPABILITY_GATEWAY_BASE_URL",
    )

    def resolve_path(self, raw_path: str) -> Path:
        path = Path(raw_path)
        if path.is_absolute():
            return path
        return REPO_ROOT / path

    @property
    def resolved_control_plane_config_path(self) -> Path:
        return self.resolve_path(self.control_plane_config_path)


def load_yaml_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
