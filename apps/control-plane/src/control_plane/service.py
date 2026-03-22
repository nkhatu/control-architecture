from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any

from .schemas import (
    AgentDescriptor,
    CapabilityDescriptor,
    ControlSummaryResponse,
    ControlPlaneSnapshotResponse,
    DocumentVersionResponse,
    MetadataResponse,
    VersionSnapshotResponse,
)


@dataclass(frozen=True)
class SourceDocument:
    name: str
    path: Path
    content: dict[str, Any]


class ControlPlaneService:
    def __init__(
        self,
        *,
        control_plane_document: dict[str, Any],
        capability_registry_document: dict[str, Any],
        agent_registry_document: dict[str, Any],
        control_plane_path: Path,
        capability_registry_path: Path,
        agent_registry_path: Path,
        app_name: str = "control-plane",
    ) -> None:
        self._app_name = app_name
        self._control_plane_document = control_plane_document
        self._capabilities = [
            CapabilityDescriptor.model_validate(item)
            for item in capability_registry_document.get("capabilities", [])
        ]
        self._agents = [
            AgentDescriptor.model_validate(item)
            for item in agent_registry_document.get("agents", [])
        ]
        self._source_documents = [
            SourceDocument("control-plane", control_plane_path, control_plane_document),
            SourceDocument("capability-registry", capability_registry_path, capability_registry_document),
            SourceDocument("agent-registry", agent_registry_path, agent_registry_document),
        ]
        self._versions = self._compute_versions(self._source_documents)

    def metadata(self, app_env: str) -> MetadataResponse:
        environment = self._control_plane_document.get("environment", {})
        return MetadataResponse(
            service=self._app_name,
            environment=app_env,
            control_plane_environment=environment.get("name"),
            capability_count=len(self._capabilities),
            agent_count=len(self._agents),
            snapshot_sha256=self._versions.snapshot_sha256,
            source_documents=self._versions.documents,
        )

    def control_plane_document(self) -> dict[str, Any]:
        return self._control_plane_document

    def capabilities(self) -> list[CapabilityDescriptor]:
        return self._capabilities

    def agents(self) -> list[AgentDescriptor]:
        return self._agents

    def versions(self) -> VersionSnapshotResponse:
        return self._versions

    def control_summary(self) -> ControlSummaryResponse:
        environment = self._control_plane_document.get("environment", {})
        control_plane = self._control_plane_document.get("control_plane", {})
        release_capability = self._control_plane_document.get("capabilities", {}).get("release_approved_payment", {})
        return ControlSummaryResponse(
            environment_name=environment.get("name", "unknown"),
            region=environment.get("region"),
            default_mode=environment.get("default_mode", "unknown"),
            rail_scope=list(environment.get("rail_scope", [])),
            policy_engine=control_plane.get("policy_engine", "unknown"),
            kill_switch_enabled=bool(control_plane.get("kill_switch_enabled", False)),
            dual_approval_threshold_usd=float(control_plane.get("dual_approval_threshold_usd", 0)),
            high_risk_escalation_threshold_usd=float(control_plane.get("high_risk_escalation_threshold_usd", 0)),
            ambiguous_response_action=control_plane.get("ambiguous_response_action", "unknown"),
            release_scope=release_capability.get("requires_scope"),
            release_requires_human_approval=bool(release_capability.get("approval_required", False)),
            release_idempotency_required=bool(release_capability.get("idempotency_key_required", False)),
            release_dry_run_supported=bool(release_capability.get("dry_run_supported", False)),
        )

    def snapshot(self) -> ControlPlaneSnapshotResponse:
        return ControlPlaneSnapshotResponse(
            control_plane=self._control_plane_document,
            capabilities=self._capabilities,
            agents=self._agents,
            versions=self._versions,
        )

    def _compute_versions(self, documents: list[SourceDocument]) -> VersionSnapshotResponse:
        version_documents: list[DocumentVersionResponse] = []
        digest = hashlib.sha256()
        for item in documents:
            raw_bytes = item.path.read_bytes()
            file_digest = hashlib.sha256(raw_bytes).hexdigest()
            digest.update(item.name.encode("utf-8"))
            digest.update(file_digest.encode("utf-8"))
            version_documents.append(
                DocumentVersionResponse(
                    name=item.name,
                    source_path=str(item.path),
                    sha256=file_digest,
                    last_modified_at=datetime.fromtimestamp(item.path.stat().st_mtime, tz=timezone.utc),
                )
            )
        return VersionSnapshotResponse(snapshot_sha256=digest.hexdigest(), documents=version_documents)
