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

    app_name: str = "capability-gateway"
    app_env: str = "local"
    host: str = "0.0.0.0"
    port: int = Field(default=8001, validation_alias="CAPABILITY_GATEWAY_PORT")
    mock_rail_name: str = Field(default="mock-domestic-rail", validation_alias="CAPABILITY_GATEWAY_MOCK_RAIL_NAME")
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
    capability_registry_path: str = Field(
        default="config/registry/capabilities.yaml",
        validation_alias="CAPABILITY_REGISTRY_PATH",
    )

    def resolve_path(self, raw_path: str) -> Path:
        path = Path(raw_path)
        if path.is_absolute():
            return path
        return REPO_ROOT / path

    @property
    def resolved_control_plane_config_path(self) -> Path:
        return self.resolve_path(self.control_plane_config_path)

    @property
    def resolved_capability_registry_path(self) -> Path:
        return self.resolve_path(self.capability_registry_path)


def load_yaml_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_gateway_documents(
    settings: AppSettings,
    *,
    transport: httpx.BaseTransport | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    service_documents = _load_gateway_documents_from_control_plane(settings, transport=transport)
    if service_documents is not None:
        return service_documents
    return (
        load_yaml_file(settings.resolved_control_plane_config_path),
        load_yaml_file(settings.resolved_capability_registry_path),
    )


def _load_gateway_documents_from_control_plane(
    settings: AppSettings,
    *,
    transport: httpx.BaseTransport | None = None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    if not settings.control_plane_base_url:
        return None

    try:
        with httpx.Client(
            base_url=settings.control_plane_base_url,
            timeout=settings.control_plane_timeout_seconds,
            transport=transport,
        ) as client:
            response = client.get("/snapshot")
            response.raise_for_status()
        payload = response.json()
        control_plane = payload.get("control_plane")
        capabilities = payload.get("capabilities")
        if not isinstance(control_plane, dict):
            raise ValueError("control-plane returned an invalid control-plane document")
        if not isinstance(capabilities, list):
            raise ValueError("control-plane returned an invalid capability registry")
        return control_plane, {"capabilities": capabilities}
    except (httpx.HTTPError, ValueError):
        return None


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
