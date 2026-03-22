from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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


class DocumentVersionResponse(BaseModel):
    name: str
    source_path: str
    sha256: str
    last_modified_at: datetime


class VersionSnapshotResponse(BaseModel):
    snapshot_sha256: str
    documents: list[DocumentVersionResponse] = Field(default_factory=list)


class ControlSummaryResponse(BaseModel):
    environment_name: str
    region: str | None = None
    default_mode: str
    rail_scope: list[str] = Field(default_factory=list)
    policy_engine: str
    kill_switch_enabled: bool
    dual_approval_threshold_usd: float
    high_risk_escalation_threshold_usd: float
    ambiguous_response_action: str
    release_scope: str | None = None
    release_requires_human_approval: bool = False
    release_idempotency_required: bool = False
    release_dry_run_supported: bool = False


class ControlPlaneDocumentResponse(BaseModel):
    document: dict[str, Any]


class CapabilityRegistryResponse(BaseModel):
    capabilities: list[CapabilityDescriptor] = Field(default_factory=list)


class AgentRegistryResponse(BaseModel):
    agents: list[AgentDescriptor] = Field(default_factory=list)


class ControlPlaneSnapshotResponse(BaseModel):
    control_plane: dict[str, Any]
    capabilities: list[CapabilityDescriptor] = Field(default_factory=list)
    agents: list[AgentDescriptor] = Field(default_factory=list)
    versions: VersionSnapshotResponse


class MetadataResponse(BaseModel):
    service: str
    environment: str
    control_plane_environment: str | None = None
    capability_count: int
    agent_count: int
    snapshot_sha256: str
    source_documents: list[DocumentVersionResponse] = Field(default_factory=list)
