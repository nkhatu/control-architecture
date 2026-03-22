from pathlib import Path

from fastapi.testclient import TestClient

from memory_service.config import AppSettings
from memory_service.main import create_app


def build_test_client(tmp_path: Path) -> TestClient:
    database_path = tmp_path / "memory-service.db"
    settings = AppSettings(
        auto_create_schema=True,
        database_url=f"sqlite+pysqlite:///{database_path}",
        control_plane_config_path="config/control-plane/default.yaml",
    )
    return TestClient(create_app(settings))


def test_health_endpoint_uses_control_plane_mode(tmp_path: Path) -> None:
    with build_test_client(tmp_path) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["mode"] == "dry_run"


def test_create_update_and_fetch_task(tmp_path: Path) -> None:
    with build_test_client(tmp_path) as client:
        create_response = client.post(
            "/tasks",
            json={
                "customer_id": "cust_123",
                "rail": "ach",
                "amount_usd": 85000,
                "provenance": {
                    "initiated_by": "user.neil",
                    "trace_id": "tr_test_001",
                },
            },
        )

        assert create_response.status_code == 201
        created_task = create_response.json()
        task_id = created_task["task_id"]
        assert created_task["status"] == "received"
        assert created_task["state_history"][0]["to_status"] == "received"

        patch_response = client.patch(
            f"/tasks/{task_id}/state",
            json={
                "status": "awaiting_approval",
                "approval_status": "pending",
                "changed_by": "agent.payment_orchestrator",
                "reason": "validation complete",
            },
        )

        assert patch_response.status_code == 200
        patched_task = patch_response.json()
        assert patched_task["status"] == "awaiting_approval"
        assert patched_task["approval_status"] == "pending"

        artifact_response = client.post(
            f"/tasks/{task_id}/artifacts",
            json={
                "artifact_type": "beneficiary_validation_result",
                "content": {"status": "validated"},
                "created_by": "agent.compliance_screening",
            },
        )

        assert artifact_response.status_code == 201

        delegation_response = client.post(
            f"/tasks/{task_id}/delegations",
            json={
                "workflow_id": f"wf_{task_id}",
                "parent_agent_id": "agent.payment_orchestrator",
                "delegated_agent_id": "agent.compliance_screening",
                "delegated_action": "beneficiary_validation",
                "capability_id": "domestic_payment.validate_beneficiary_account",
                "status": "queued",
                "request_envelope": {
                    "message_type": "delegation.request.validate_beneficiary",
                    "task_id": task_id,
                },
            },
        )

        assert delegation_response.status_code == 201
        delegation_id = delegation_response.json()["delegation_id"]

        delegation_patch_response = client.patch(
            f"/delegations/{delegation_id}",
            json={
                "status": "completed",
                "updated_by": "agent.compliance_screening",
                "response_envelope": {
                    "message_type": "delegation.result.validate_beneficiary",
                    "payload": {"status": "validated"},
                },
            },
        )

        assert delegation_patch_response.status_code == 200

        get_response = client.get(f"/tasks/{task_id}")

        assert get_response.status_code == 200
        fetched_task = get_response.json()
        assert len(fetched_task["state_history"]) == 2
        assert len(fetched_task["artifacts"]) == 1
        assert len(fetched_task["delegations"]) == 1
        assert fetched_task["delegations"][0]["status"] == "completed"


def test_rejects_no_op_state_patch(tmp_path: Path) -> None:
    with build_test_client(tmp_path) as client:
        create_response = client.post(
            "/tasks",
            json={
                "customer_id": "cust_002",
                "rail": "ach",
                "amount_usd": 1500,
                "provenance": {
                    "initiated_by": "user.neil",
                },
            },
        )

        task_id = create_response.json()["task_id"]

        patch_response = client.patch(
            f"/tasks/{task_id}/state",
            json={
                "status": "received",
                "changed_by": "agent.payment_orchestrator",
                "reason": "no-op attempt",
            },
        )

        assert patch_response.status_code == 409
        assert "already reflects the requested state" in patch_response.json()["detail"]
