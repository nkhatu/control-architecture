from contextlib import ExitStack, contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from capability_gateway.config import AppSettings as CapabilityGatewaySettings
from capability_gateway.main import create_app as create_capability_gateway_app
from context_memory_service.config import AppSettings as ContextMemorySettings
from context_memory_service.main import create_app as create_context_memory_app
from event_consumer.config import AppSettings as EventConsumerSettings
from event_consumer.main import create_app as create_event_consumer_app
from orchestrator_api.config import AppSettings as OrchestratorSettings
from orchestrator_api.main import create_app as create_orchestrator_app
from policy_service.config import AppSettings as PolicyServiceSettings
from policy_service.main import create_app as create_policy_service_app
from provenance_service.config import AppSettings as ProvenanceSettings
from provenance_service.main import create_app as create_provenance_app
from workflow_worker.config import AppSettings as WorkflowWorkerSettings
from workflow_worker.main import create_app as create_workflow_worker_app


class InProcessMemoryServiceClient:
    def __init__(self, context_client: TestClient, provenance_client: TestClient, event_consumer_client: TestClient):
        self._context_client = context_client
        self._provenance_client = provenance_client
        self._event_consumer_client = event_consumer_client

    def create_task(self, payload: dict) -> dict:
        context_response = self._context_client.post(
            "/tasks",
            json=payload,
        )
        context_response.raise_for_status()
        context_task = context_response.json()
        dispatch_response = self._event_consumer_client.post("/dispatch/run-once", json={"limit": 100, "lease_seconds": 30})
        dispatch_response.raise_for_status()
        return self.get_task(context_task["task_id"])

    def get_task(self, task_id: str) -> dict:
        context_response = self._context_client.get(f"/tasks/{task_id}")
        context_response.raise_for_status()
        context_task = context_response.json()
        records_response = self._provenance_client.get(f"/tasks/{task_id}/records")
        if records_response.status_code == 404:
            records = {
                "provenance": {
                    "task_id": task_id,
                    "initiated_by": "",
                    "last_updated_by": "",
                    "policy_context_id": None,
                    "trace_id": None,
                    "created_at": None,
                    "updated_at": None,
                },
                "state_history": [],
                "artifacts": [],
                "delegations": [],
            }
        else:
            records_response.raise_for_status()
            records = records_response.json()
        return {
            **context_task,
            "provenance": records["provenance"],
            "state_history": records["state_history"],
            "artifacts": records["artifacts"],
            "delegations": records["delegations"],
        }

    def patch_task_state(self, task_id: str, payload: dict) -> dict:
        response = self._context_client.patch(
            f"/tasks/{task_id}/state",
            json=payload,
        )
        response.raise_for_status()
        dispatch_response = self._event_consumer_client.post("/dispatch/run-once", json={"limit": 100, "lease_seconds": 30})
        dispatch_response.raise_for_status()
        return self.get_task(task_id)

    def create_artifact(self, task_id: str, payload: dict) -> dict:
        response = self._provenance_client.post(f"/tasks/{task_id}/artifacts", json=payload)
        response.raise_for_status()
        return response.json()

    def create_delegation(self, task_id: str, payload: dict) -> dict:
        response = self._provenance_client.post(f"/tasks/{task_id}/delegations", json=payload)
        response.raise_for_status()
        return response.json()

    def update_delegation(self, delegation_id: str, payload: dict) -> dict:
        response = self._provenance_client.patch(f"/delegations/{delegation_id}", json=payload)
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


class InProcessWorkflowWorkerClient:
    def __init__(self, client: TestClient):
        self._client = client

    def start_workflow(self, payload: dict) -> dict:
        response = self._client.post("/workflows/domestic-payments/start", json=payload)
        response.raise_for_status()
        return response.json()

    def resume_workflow(self, task_id: str, payload: dict) -> dict:
        response = self._client.post(f"/workflows/domestic-payments/{task_id}/resume", json=payload)
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        return None


class InProcessPolicyServiceClient:
    def __init__(self, client: TestClient):
        self._client = client

    def evaluate_intake(self, payload: dict) -> dict:
        response = self._client.post("/decisions/intake", json=payload)
        response.raise_for_status()
        return response.json()

    def evaluate_release(self, payload: dict) -> dict:
        response = self._client.post("/decisions/release", json=payload)
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        return None


@contextmanager
def build_test_client(tmp_path: Path):
    context_database_path = tmp_path / "context-memory.db"
    provenance_database_path = tmp_path / "provenance.db"
    context_settings = ContextMemorySettings(
        auto_create_schema=True,
        database_url=f"sqlite+pysqlite:///{context_database_path}",
        control_plane_config_path="config/control-plane/default.yaml",
    )
    provenance_settings = ProvenanceSettings(
        auto_create_schema=True,
        database_url=f"sqlite+pysqlite:///{provenance_database_path}",
        control_plane_config_path="config/control-plane/default.yaml",
    )
    context_app = create_context_memory_app(context_settings)
    provenance_app = create_provenance_app(provenance_settings)

    gateway_settings = CapabilityGatewaySettings(
        control_plane_config_path="config/control-plane/default.yaml",
        capability_registry_path="config/registry/capabilities.yaml",
    )
    gateway_app = create_capability_gateway_app(gateway_settings)
    policy_settings = PolicyServiceSettings(control_plane_config_path="config/control-plane/default.yaml")
    policy_app = create_policy_service_app(policy_settings)
    event_settings = EventConsumerSettings(control_plane_config_path="config/control-plane/default.yaml")

    worker_settings = WorkflowWorkerSettings(
        control_plane_config_path="config/control-plane/default.yaml",
    )

    orchestrator_settings = OrchestratorSettings(
        control_plane_config_path="config/control-plane/default.yaml",
        capability_registry_path="config/registry/capabilities.yaml",
        agent_registry_path="config/registry/agents.yaml",
    )
    with ExitStack() as stack:
        context_client = stack.enter_context(TestClient(context_app))
        provenance_client = stack.enter_context(TestClient(provenance_app))
        event_consumer_app = create_event_consumer_app(
            event_settings,
            context_outbox_client=InProcessContextOutboxClient(context_client),
            provenance_client=InProcessProvenanceProjectionClient(provenance_client),
        )
        event_consumer_client = stack.enter_context(TestClient(event_consumer_app))
        gateway_client = stack.enter_context(TestClient(gateway_app))
        policy_client = stack.enter_context(TestClient(policy_app))
        workflow_worker_app = create_workflow_worker_app(
            worker_settings,
            memory_service_client=InProcessMemoryServiceClient(context_client, provenance_client, event_consumer_client),
            capability_gateway_client=InProcessCapabilityGatewayClient(gateway_client),
        )
        workflow_worker_client = stack.enter_context(TestClient(workflow_worker_app))
        orchestrator_app = create_orchestrator_app(
            orchestrator_settings,
            memory_service_client=InProcessMemoryServiceClient(context_client, provenance_client, event_consumer_client),
            policy_service_client=InProcessPolicyServiceClient(policy_client),
            workflow_worker_client=InProcessWorkflowWorkerClient(workflow_worker_client),
        )
        orchestrator_client = stack.enter_context(TestClient(orchestrator_app))
        yield orchestrator_client


class InProcessContextOutboxClient:
    def __init__(self, client: TestClient):
        self._client = client

    def claim_events(self, *, limit: int, lease_seconds: int) -> list[dict]:
        response = self._client.post("/outbox/claim", json={"limit": limit, "lease_seconds": lease_seconds})
        response.raise_for_status()
        return response.json()["events"]

    def complete_event(self, event_id: str) -> dict:
        response = self._client.post(f"/outbox/{event_id}/complete")
        response.raise_for_status()
        return response.json()

    def fail_event(self, event_id: str, *, error_message: str) -> dict:
        response = self._client.post(f"/outbox/{event_id}/fail", json={"error_message": error_message})
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        return None


class InProcessProvenanceProjectionClient:
    def __init__(self, client: TestClient):
        self._client = client

    def ensure_task_provenance(self, task_id: str, payload: dict) -> dict:
        response = self._client.post(f"/tasks/{task_id}/provenance", json=payload)
        response.raise_for_status()
        return response.json()

    def append_state_transition(self, task_id: str, payload: dict) -> dict:
        response = self._client.post(f"/tasks/{task_id}/state-transitions", json=payload)
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        return None


def test_health_reports_dry_run_mode(tmp_path: Path) -> None:
    with build_test_client(tmp_path) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["mode"] == "dry_run"


def test_intake_creates_task_through_memory_service(tmp_path: Path) -> None:
    with build_test_client(tmp_path) as client:
        response = client.post(
            "/tasks/domestic-payments",
            json={
                "customer_id": "cust_123",
                "source_account_id": "acct_001",
                "beneficiary_id": "ben_001",
                "amount_usd": 2500,
                "rail": "ach",
                "requested_execution_date": "2026-03-23",
                "initiated_by": "user.neil",
                "trace_id": "tr_orch_001",
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["policy_decision"]["decision"] == "allow"
    assert body["policy_decision"]["approval_profile"] == "single_approval"
    assert body["task"]["status"] == "awaiting_approval"
    assert body["task"]["task_metadata"]["beneficiary_id"] == "ben_001"
    assert "domestic_payment.validate_beneficiary_account" in body["available_capabilities"]
    assert "agent.payment_orchestrator" in body["selected_agents"]
    assert "agent.approval_router" in body["selected_agents"]
    assert body["workflow"]["workflow_state"] == "waiting_for_approval"
    assert any(item["delegated_action"] == "approval_routing" for item in body["task"]["delegations"])


def test_intake_rejects_unsupported_rail(tmp_path: Path) -> None:
    with build_test_client(tmp_path) as client:
        response = client.post(
            "/tasks/domestic-payments",
            json={
                "customer_id": "cust_123",
                "source_account_id": "acct_001",
                "beneficiary_id": "ben_001",
                "amount_usd": 2500,
                "rail": "rtp",
                "requested_execution_date": "2026-03-23",
                "initiated_by": "user.neil",
            },
        )

    assert response.status_code == 403
    assert "outside the configured PoC rail scope" in response.json()["detail"]["message"]


def test_get_task_proxies_to_memory_service(tmp_path: Path) -> None:
    with build_test_client(tmp_path) as client:
        create_response = client.post(
            "/tasks/domestic-payments",
            json={
                "customer_id": "cust_456",
                "source_account_id": "acct_009",
                "beneficiary_id": "ben_008",
                "amount_usd": 125000,
                "rail": "ach",
                "requested_execution_date": "2026-03-24",
                "initiated_by": "user.neil",
            },
        )
        task_id = create_response.json()["task"]["task_id"]

        get_response = client.get(f"/tasks/{task_id}")

    assert get_response.status_code == 200
    assert get_response.json()["task_id"] == task_id
    assert get_response.json()["task_metadata"]["policy_decision"]["decision"] == "escalate"
    assert get_response.json()["status"] == "awaiting_approval"
    assert len(get_response.json()["delegations"]) == 2


def test_resume_endpoint_releases_payment_after_approval(tmp_path: Path) -> None:
    with build_test_client(tmp_path) as client:
        create_response = client.post(
            "/tasks/domestic-payments",
            json={
                "customer_id": "cust_456",
                "source_account_id": "acct_009",
                "beneficiary_id": "ben_008",
                "amount_usd": 2500,
                "rail": "ach",
                "requested_execution_date": "2026-03-24",
                "initiated_by": "user.neil",
            },
        )
        task_id = create_response.json()["task"]["task_id"]

        resume_response = client.post(
            f"/tasks/{task_id}/resume",
            json={
                "approved_by": "user.ops_approver",
                "approval_note": "Approved to release.",
                "release_mode": "execute",
            },
        )

    assert resume_response.status_code == 200
    assert resume_response.json()["task"]["status"] == "settlement_pending"
    assert resume_response.json()["task"]["approval_status"] == "approved"
    assert resume_response.json()["workflow"]["workflow_state"] == "release_submitted"
    assert resume_response.json()["release_result"]["mock_rail_outcome"] == "success"
    assert any(item["artifact_type"] == "release_policy_decision" for item in resume_response.json()["task"]["artifacts"])
    assert any(item["delegated_action"] == "approval_routing" and item["status"] == "completed" for item in resume_response.json()["task"]["delegations"])


def test_resume_endpoint_denies_release_without_scope(tmp_path: Path) -> None:
    with build_test_client(tmp_path) as client:
        create_response = client.post(
            "/tasks/domestic-payments",
            json={
                "customer_id": "cust_456",
                "source_account_id": "acct_009",
                "beneficiary_id": "ben_008",
                "amount_usd": 2500,
                "rail": "ach",
                "requested_execution_date": "2026-03-24",
                "initiated_by": "user.neil",
            },
        )
        task_id = create_response.json()["task"]["task_id"]

        resume_response = client.post(
            f"/tasks/{task_id}/resume",
            json={
                "approved_by": "user.ops_approver",
                "approval_note": "Approved to release.",
                "release_mode": "execute",
                "principal_scopes": [],
            },
        )

    assert resume_response.status_code == 403
    assert resume_response.json()["detail"]["error_class"] == "policy_denied"
    assert "missing required scope" in resume_response.json()["detail"]["message"]
