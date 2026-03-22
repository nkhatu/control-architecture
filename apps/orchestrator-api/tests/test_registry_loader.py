import httpx

from orchestrator_api.config import AppSettings
from orchestrator_api.registry import load_registry_snapshot


def test_registry_snapshot_prefers_control_plane() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "control_plane": {
                    "environment": {
                        "name": "remote-test",
                        "default_mode": "execute",
                    },
                    "control_plane": {
                        "policy_engine": "opa",
                    },
                },
                "capabilities": [
                    {
                        "id": "domestic_payment.release_approved_payment",
                        "version": "1.0.0",
                        "owner": "capability-gateway",
                        "category": "payments",
                        "side_effect_class": "funds_movement",
                        "required_scopes": ["release:domestic_payment"],
                    }
                ],
                "agents": [
                    {
                        "agent_id": "agent.payment_orchestrator",
                        "name": "Payment Orchestrator",
                        "purpose": "Coordinate domestic payment workflows",
                        "trust_tier": "tier-1",
                    }
                ],
                "versions": {
                    "snapshot_sha256": "0" * 64,
                    "documents": [],
                },
            },
        )
    )
    settings = AppSettings(
        control_plane_base_url="http://control-plane.test",
        control_plane_timeout_seconds=0.1,
        control_plane_config_path="config/control-plane/missing.yaml",
        capability_registry_path="config/registry/missing-capabilities.yaml",
        agent_registry_path="config/registry/missing-agents.yaml",
    )

    snapshot = load_registry_snapshot(settings, transport=transport)

    assert snapshot.control_plane["environment"]["name"] == "remote-test"
    assert snapshot.capabilities[0].id == "domestic_payment.release_approved_payment"
    assert snapshot.agents[0].agent_id == "agent.payment_orchestrator"


def test_registry_snapshot_falls_back_to_files_when_service_unavailable() -> None:
    transport = httpx.MockTransport(
        lambda request: (_ for _ in ()).throw(httpx.ConnectError("service unavailable", request=request))
    )
    settings = AppSettings(
        control_plane_base_url="http://control-plane.test",
        control_plane_timeout_seconds=0.1,
        control_plane_config_path="config/control-plane/default.yaml",
        capability_registry_path="config/registry/capabilities.yaml",
        agent_registry_path="config/registry/agents.yaml",
    )

    snapshot = load_registry_snapshot(settings, transport=transport)

    assert snapshot.control_plane["environment"]["name"] == "poc-local"
    assert len(snapshot.capabilities) >= 5
    assert len(snapshot.agents) >= 3
