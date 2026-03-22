from fastapi.testclient import TestClient

from control_plane.config import AppSettings
from control_plane.main import create_app


def build_test_client() -> TestClient:
    settings = AppSettings(
        control_plane_config_path="config/control-plane/default.yaml",
        capability_registry_path="config/registry/capabilities.yaml",
        agent_registry_path="config/registry/agents.yaml",
    )
    return TestClient(create_app(settings))


def test_snapshot_exposes_control_plane_and_registries() -> None:
    with build_test_client() as client:
        response = client.get("/snapshot")

    assert response.status_code == 200
    body = response.json()
    assert body["control_plane"]["control_plane"]["kill_switch_enabled"] is True
    assert len(body["capabilities"]) >= 5
    assert len(body["agents"]) >= 3
    assert len(body["versions"]["documents"]) == 3


def test_control_summary_surfaces_release_controls() -> None:
    with build_test_client() as client:
        response = client.get("/controls/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["environment_name"] == "poc-local"
    assert body["default_mode"] == "dry_run"
    assert body["kill_switch_enabled"] is True
    assert body["dual_approval_threshold_usd"] == 50000
    assert body["high_risk_escalation_threshold_usd"] == 100000
    assert body["release_scope"] == "release:domestic_payment"
    assert body["release_requires_human_approval"] is True
    assert body["release_idempotency_required"] is True


def test_versions_endpoint_returns_stable_document_metadata() -> None:
    with build_test_client() as client:
        response = client.get("/versions/current")

    assert response.status_code == 200
    body = response.json()
    assert len(body["snapshot_sha256"]) == 64
    document_names = {item["name"] for item in body["documents"]}
    assert document_names == {"control-plane", "capability-registry", "agent-registry"}


def test_metadata_reports_snapshot_and_counts() -> None:
    with build_test_client() as client:
        response = client.get("/metadata")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "control-plane"
    assert body["control_plane_environment"] == "poc-local"
    assert body["capability_count"] >= 5
    assert body["agent_count"] >= 3
    assert len(body["snapshot_sha256"]) == 64
