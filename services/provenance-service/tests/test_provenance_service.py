from fastapi.testclient import TestClient

from provenance_service.config import AppSettings
from provenance_service.main import create_app


def test_provenance_service_records_history_artifacts_and_delegations(tmp_path) -> None:
    database_path = tmp_path / "provenance.db"
    settings = AppSettings(
        auto_create_schema=True,
        database_url=f"sqlite+pysqlite:///{database_path}",
        control_plane_config_path="config/control-plane/default.yaml",
    )

    with TestClient(create_app(settings)) as client:
        provenance_response = client.post(
            "/tasks/task_001/provenance",
            json={
                "initiated_by": "user.neil",
                "trace_id": "tr_001",
            },
        )
        assert provenance_response.status_code == 201

        transition_response = client.post(
            "/tasks/task_001/state-transitions",
            json={
                "from_status": None,
                "to_status": "received",
                "changed_by": "user.neil",
                "reason": "task created",
            },
        )
        assert transition_response.status_code == 201

        artifact_response = client.post(
            "/tasks/task_001/artifacts",
            json={
                "artifact_type": "beneficiary_validation_result",
                "content": {"status": "validated"},
                "created_by": "agent.compliance_screening",
            },
        )
        assert artifact_response.status_code == 201

        delegation_response = client.post(
            "/tasks/task_001/delegations",
            json={
                "workflow_id": "wf_task_001",
                "parent_agent_id": "agent.payment_orchestrator",
                "delegated_agent_id": "agent.approval_router",
                "delegated_action": "approval_routing",
                "status": "pending",
                "request_envelope": {"message_type": "delegation.request.approval_routing"},
            },
        )
        assert delegation_response.status_code == 201
        delegation_id = delegation_response.json()["delegation_id"]

        update_response = client.patch(
            f"/delegations/{delegation_id}",
            json={
                "status": "completed",
                "updated_by": "agent.approval_router",
                "response_envelope": {"message_type": "delegation.result.approval_routing"},
            },
        )
        assert update_response.status_code == 200

        records_response = client.get("/tasks/task_001/records")
        assert records_response.status_code == 200
        body = records_response.json()
        assert body["provenance"]["trace_id"] == "tr_001"
        assert len(body["state_history"]) == 1
        assert len(body["artifacts"]) == 1
        assert len(body["delegations"]) == 1
        assert body["delegations"][0]["status"] == "completed"
