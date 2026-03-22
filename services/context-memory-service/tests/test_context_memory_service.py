from fastapi.testclient import TestClient

from context_memory_service.config import AppSettings
from context_memory_service.main import create_app


def test_context_service_creates_and_updates_task(tmp_path) -> None:
    database_path = tmp_path / "context-memory.db"
    settings = AppSettings(
        auto_create_schema=True,
        database_url=f"sqlite+pysqlite:///{database_path}",
        control_plane_config_path="config/control-plane/default.yaml",
    )

    with TestClient(create_app(settings)) as client:
        create_response = client.post(
            "/tasks",
            json={
                "customer_id": "cust_001",
                "rail": "ach",
                "amount_usd": 2500,
                "task_metadata": {"workflow_id": "wf_task_001"},
            },
        )
        assert create_response.status_code == 201
        task_id = create_response.json()["task_id"]

        patch_response = client.patch(
            f"/tasks/{task_id}/state",
            json={
                "status": "awaiting_approval",
                "approval_status": "pending",
                "beneficiary_status": "approved",
            },
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["status"] == "awaiting_approval"
        assert patch_response.json()["beneficiary_status"] == "approved"

        get_response = client.get(f"/tasks/{task_id}")
        assert get_response.status_code == 200
        assert get_response.json()["task_id"] == task_id
