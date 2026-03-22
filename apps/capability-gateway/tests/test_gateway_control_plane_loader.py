import httpx

from capability_gateway.config import AppSettings, load_gateway_documents


def test_gateway_documents_prefer_control_plane() -> None:
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
                "agents": [],
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
    )

    control_plane, capability_registry = load_gateway_documents(settings, transport=transport)

    assert control_plane["environment"]["name"] == "remote-test"
    assert capability_registry["capabilities"][0]["id"] == "domestic_payment.release_approved_payment"


def test_gateway_documents_fall_back_to_files_when_service_unavailable() -> None:
    transport = httpx.MockTransport(
        lambda request: (_ for _ in ()).throw(httpx.ConnectError("service unavailable", request=request))
    )
    settings = AppSettings(
        control_plane_base_url="http://control-plane.test",
        control_plane_timeout_seconds=0.1,
        control_plane_config_path="config/control-plane/default.yaml",
        capability_registry_path="config/registry/capabilities.yaml",
    )

    control_plane, capability_registry = load_gateway_documents(settings, transport=transport)

    assert control_plane["environment"]["name"] == "poc-local"
    assert len(capability_registry["capabilities"]) >= 5
