from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, Field

from .config import AppSettings, load_yaml_file


class CapabilityDescriptor(BaseModel):
    id: str
    version: str
    owner: str
    category: str
    side_effect_class: str
    required_scopes: list[str] = Field(default_factory=list)
    input_schema: str | None = None
    output_schema: str | None = None
    timeout_ms: int | None = None
    retry_policy: str | None = None
    requires_human_approval: bool | None = None
    idempotency: str | None = None
    compensation_action: str | None = None


class AgentDescriptor(BaseModel):
    agent_id: str
    name: str
    purpose: str
    supported_tasks: list[str] = Field(default_factory=list)
    accepts_scopes: list[str] = Field(default_factory=list)
    trust_tier: str
    supported_transports: list[str] = Field(default_factory=list)
    callback_mode: str | None = None
    max_task_ttl_seconds: int | None = None
    requires_provenance: bool = False
    execution_authority: str | None = None


class RegistrySnapshot(BaseModel):
    control_plane: dict[str, Any]
    capabilities: list[CapabilityDescriptor]
    agents: list[AgentDescriptor]

    def get_capability(self, capability_id: str) -> CapabilityDescriptor | None:
        return next((item for item in self.capabilities if item.id == capability_id), None)

    def get_agent(self, agent_id: str) -> AgentDescriptor | None:
        return next((item for item in self.agents if item.agent_id == agent_id), None)


def load_registry_snapshot(
    settings: AppSettings,
    *,
    transport: httpx.BaseTransport | None = None,
) -> RegistrySnapshot:
    service_snapshot = _load_registry_snapshot_from_control_plane(settings, transport=transport)
    if service_snapshot is not None:
        return service_snapshot
    return _load_registry_snapshot_from_files(settings)


def _load_registry_snapshot_from_control_plane(
    settings: AppSettings,
    *,
    transport: httpx.BaseTransport | None = None,
) -> RegistrySnapshot | None:
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
        return RegistrySnapshot.model_validate(response.json())
    except (httpx.HTTPError, ValueError):
        return None


def _load_registry_snapshot_from_files(settings: AppSettings) -> RegistrySnapshot:
    control_plane = load_yaml_file(settings.resolved_control_plane_config_path)
    capabilities_data = load_yaml_file(settings.resolved_capability_registry_path)
    agents_data = load_yaml_file(settings.resolved_agent_registry_path)

    return RegistrySnapshot(
        control_plane=control_plane,
        capabilities=[CapabilityDescriptor.model_validate(item) for item in capabilities_data.get("capabilities", [])],
        agents=[AgentDescriptor.model_validate(item) for item in agents_data.get("agents", [])],
    )
