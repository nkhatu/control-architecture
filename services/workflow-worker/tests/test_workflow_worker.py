from pathlib import Path

from fastapi.testclient import TestClient

from capability_gateway.config import AppSettings as CapabilityGatewaySettings
from capability_gateway.main import create_app as create_capability_gateway_app
from memory_service.config import AppSettings as MemorySettings
from memory_service.main import create_app as create_memory_app
from workflow_worker.config import AppSettings as WorkflowWorkerSettings
from workflow_worker.main import create_app as create_workflow_worker_app


class InProcessMemoryServiceClient:
    def __init__(self, client: TestClient):
        self._client = client

    def create_task(self, payload: dict) -> dict:
        response = self._client.post("/tasks", json=payload)
        response.raise_for_status()
        return response.json()

    def get_task(self, task_id: str) -> dict:
        response = self._client.get(f"/tasks/{task_id}")
        response.raise_for_status()
        return response.json()

    def patch_task_state(self, task_id: str, payload: dict) -> dict:
        response = self._client.patch(f"/tasks/{task_id}/state", json=payload)
        response.raise_for_status()
        return response.json()

    def create_artifact(self, task_id: str, payload: dict) -> dict:
        response = self._client.post(f"/tasks/{task_id}/artifacts", json=payload)
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        return None


class InProcessCapabilityGatewayClient:
    def __init__(self, client: TestClient):
        self._client = client

    def create_instruction(self, payload: dict) -> dict:
        response = self._client.post("/domestic-payments/instructions", json=payload)
        response.raise_for_status()
        return response.json()

    def validate_beneficiary(self, payload: dict) -> dict:
        response = self._client.post("/domestic-payments/beneficiaries/validate", json=payload)
        response.raise_for_status()
        return response.json()

    def release_payment(self, payload: dict) -> dict:
        response = self._client.post("/domestic-payments/release", json=payload)
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        return None


def build_test_client(tmp_path: Path) -> TestClient:
    database_path = tmp_path / "workflow-memory-service.db"
    memory_settings = MemorySettings(
        auto_create_schema=True,
        database_url=f"sqlite+pysqlite:///{database_path}",
        control_plane_config_path="config/control-plane/default.yaml",
    )
    memory_app = create_memory_app(memory_settings)
    memory_client = TestClient(memory_app)

    gateway_settings = CapabilityGatewaySettings(
        control_plane_config_path="config/control-plane/default.yaml",
        capability_registry_path="config/registry/capabilities.yaml",
    )
    gateway_app = create_capability_gateway_app(gateway_settings)
    gateway_client = TestClient(gateway_app)

    worker_settings = WorkflowWorkerSettings(
        control_plane_config_path="config/control-plane/default.yaml",
    )
    worker_app = create_workflow_worker_app(
        worker_settings,
        memory_service_client=InProcessMemoryServiceClient(memory_client),
        capability_gateway_client=InProcessCapabilityGatewayClient(gateway_client),
    )

    return TestClient(worker_app)


def start_payload(beneficiary_id: str = "ben_001") -> dict:
    return {
        "request": {
            "customer_id": "cust_123",
            "source_account_id": "acct_001",
            "beneficiary_id": beneficiary_id,
            "amount_usd": 2500,
            "rail": "ach",
            "requested_execution_date": "2026-03-24",
            "initiated_by": "user.neil",
            "trace_id": "tr_workflow_001",
            "principal_scopes": ["payment.validate", "payment.release"],
        },
        "policy_decision": {
            "decision": "allow",
            "reason": "The payment is within the configured intake thresholds.",
            "approval_profile": "single_approval",
            "execution_mode": "dry_run",
            "recommended_next_capability": "domestic_payment.validate_beneficiary_account",
            "requires_manual_escalation": False,
        },
        "selected_agents": ["agent.payment_orchestrator"],
        "available_capabilities": [
            "domestic_payment.create_instruction",
            "domestic_payment.validate_beneficiary_account",
            "domestic_payment.release_approved_payment",
        ],
    }


def test_start_workflow_moves_task_to_awaiting_approval(tmp_path: Path) -> None:
    with build_test_client(tmp_path) as client:
        response = client.post("/workflows/domestic-payments/start", json=start_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["task"]["status"] == "awaiting_approval"
    assert body["task"]["beneficiary_status"] == "approved"
    assert body["workflow"]["workflow_state"] == "waiting_for_approval"
    assert body["artifacts_created"] == ["beneficiary_validation_result"]


def test_resume_workflow_reaches_settlement_pending(tmp_path: Path) -> None:
    with build_test_client(tmp_path) as client:
        start_response = client.post("/workflows/domestic-payments/start", json=start_payload())
        task_id = start_response.json()["task"]["task_id"]

        resume_response = client.post(
            f"/workflows/domestic-payments/{task_id}/resume",
            json={
                "approved_by": "user.ops_approver",
                "approval_note": "Approved for release.",
                "release_mode": "execute",
            },
        )

    assert resume_response.status_code == 200
    body = resume_response.json()
    assert body["task"]["status"] == "settlement_pending"
    assert body["task"]["approval_status"] == "approved"
    assert body["workflow"]["workflow_state"] == "release_submitted"
    assert body["release_result"]["mock_rail_outcome"] == "success"
    assert body["artifacts_created"] == ["payment_release_result"]


def test_resume_workflow_surfaces_ambiguous_release(tmp_path: Path) -> None:
    with build_test_client(tmp_path) as client:
        start_response = client.post("/workflows/domestic-payments/start", json=start_payload())
        task_id = start_response.json()["task"]["task_id"]

        resume_response = client.post(
            f"/workflows/domestic-payments/{task_id}/resume",
            json={
                "approved_by": "user.ops_approver",
                "idempotency_key": "resume-ambiguous-4477",
                "release_mode": "execute",
            },
        )

    assert resume_response.status_code == 200
    body = resume_response.json()
    assert body["task"]["status"] == "pending_reconcile"
    assert body["workflow"]["workflow_state"] == "pending_reconcile"
    assert body["release_result"]["mock_rail_outcome"] == "ambiguous"
