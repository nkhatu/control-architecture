from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
import yaml
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[4]


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "policy-engine"
    app_env: str = "local"
    host: str = "0.0.0.0"
    port: int = Field(default=8005, validation_alias=AliasChoices("POLICY_ENGINE_PORT", "POLICY_SERVICE_PORT"))
    control_plane_base_url: str | None = Field(
        default="http://localhost:8008",
        validation_alias=AliasChoices("CONTROL_PLANE_BASE_URL", "CONTROL_PLANE_SERVICE_BASE_URL"),
    )
    control_plane_timeout_seconds: float = Field(
        default=0.5,
        validation_alias=AliasChoices("CONTROL_PLANE_TIMEOUT_SECONDS", "CONTROL_PLANE_SERVICE_TIMEOUT_SECONDS"),
    )
    control_plane_config_path: str = Field(
        default="config/control-plane/default.yaml",
        validation_alias="CONTROL_PLANE_CONFIG_PATH",
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


def load_control_plane_document(
    settings: AppSettings,
    *,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    service_document = _load_control_plane_document_from_service(settings, transport=transport)
    if service_document is not None:
        return service_document
    return load_yaml_file(settings.resolved_control_plane_config_path)


def _load_control_plane_document_from_service(
    settings: AppSettings,
    *,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any] | None:
    if not settings.control_plane_base_url:
        return None

    try:
        with httpx.Client(
            base_url=settings.control_plane_base_url,
            timeout=settings.control_plane_timeout_seconds,
            transport=transport,
        ) as client:
            response = client.get("/control-plane")
            response.raise_for_status()
        payload = response.json()
        document = payload.get("document")
        if not isinstance(document, dict):
            raise ValueError("control-plane returned an invalid document payload")
        return document
    except (httpx.HTTPError, ValueError):
        return None


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
