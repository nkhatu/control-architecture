import httpx

from workflow_worker.config import AppSettings, load_control_plane_document


def test_control_plane_document_prefers_control_plane() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "document": {
                    "environment": {
                        "name": "remote-test",
                        "default_mode": "execute",
                        "rail_scope": ["ach"],
                    },
                    "control_plane": {
                        "policy_engine": "opa",
                    },
                },
            },
        )
    )
    settings = AppSettings(
        control_plane_base_url="http://control-plane.test",
        control_plane_timeout_seconds=0.1,
        control_plane_config_path="config/control-plane/missing.yaml",
    )

    document = load_control_plane_document(settings, transport=transport)

    assert document["environment"]["name"] == "remote-test"
    assert document["environment"]["default_mode"] == "execute"


def test_control_plane_document_falls_back_to_file_when_service_unavailable() -> None:
    transport = httpx.MockTransport(
        lambda request: (_ for _ in ()).throw(httpx.ConnectError("service unavailable", request=request))
    )
    settings = AppSettings(
        control_plane_base_url="http://control-plane.test",
        control_plane_timeout_seconds=0.1,
        control_plane_config_path="config/control-plane/default.yaml",
    )

    document = load_control_plane_document(settings, transport=transport)

    assert document["environment"]["name"] == "poc-local"
    assert document["control_plane"]["kill_switch_enabled"] is True
