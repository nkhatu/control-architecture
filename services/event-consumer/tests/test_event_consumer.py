from contextlib import ExitStack

from fastapi.testclient import TestClient
from shared_contracts.events import TaskLifecycleTransition, parse_task_lifecycle_outbox_event

from context_memory_service.config import AppSettings as ContextMemorySettings
from context_memory_service.main import create_app as create_context_memory_app
from event_consumer.config import AppSettings as EventConsumerSettings
from event_consumer.main import create_app as create_event_consumer_app
from event_consumer.context_client import ContextOutboxClient
from event_consumer.provenance_client import ProvenanceProjectionClient
from provenance_service.config import AppSettings as ProvenanceSettings
from provenance_service.main import create_app as create_provenance_app


class InProcessContextOutboxClient:
    def __init__(self, client: TestClient):
        self._client = client

    def claim_events(self, *, limit: int, lease_seconds: int) -> list:
        response = self._client.post("/outbox/claim", json={"limit": limit, "lease_seconds": lease_seconds})
        response.raise_for_status()
        return [parse_task_lifecycle_outbox_event(item) for item in response.json()["events"]]

    def complete_event(self, event_id: str):
        response = self._client.post(f"/outbox/{event_id}/complete")
        response.raise_for_status()
        return parse_task_lifecycle_outbox_event(response.json())

    def fail_event(self, event_id: str, *, error_message: str):
        response = self._client.post(f"/outbox/{event_id}/fail", json={"error_message": error_message})
        response.raise_for_status()
        return parse_task_lifecycle_outbox_event(response.json())

    def close(self) -> None:
        return None


class InProcessProvenanceClient:
    def __init__(self, client: TestClient):
        self._client = client

    def ensure_task_provenance(self, task_id: str, payload) -> dict:
        response = self._client.post(f"/tasks/{task_id}/provenance", json=payload.model_dump(mode="json"))
        response.raise_for_status()
        return response.json()

    def append_state_transition(self, task_id: str, payload: TaskLifecycleTransition, *, source_event_id: str) -> dict:
        response = self._client.post(
            f"/tasks/{task_id}/state-transitions",
            json={
                **payload.model_dump(mode="json"),
                "source_event_id": source_event_id,
            },
        )
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        return None


def test_event_consumer_projects_outbox_events_into_provenance(tmp_path) -> None:
    context_settings = ContextMemorySettings(
        auto_create_schema=True,
        database_url=f"sqlite+pysqlite:///{tmp_path / 'context.db'}",
        control_plane_config_path="config/control-plane/default.yaml",
    )
    provenance_settings = ProvenanceSettings(
        auto_create_schema=True,
        database_url=f"sqlite+pysqlite:///{tmp_path / 'provenance.db'}",
        control_plane_config_path="config/control-plane/default.yaml",
    )
    event_settings = EventConsumerSettings(control_plane_config_path="config/control-plane/default.yaml")

    with ExitStack() as stack:
        context_client = stack.enter_context(TestClient(create_context_memory_app(context_settings)))
        provenance_client = stack.enter_context(TestClient(create_provenance_app(provenance_settings)))
        event_consumer_client = stack.enter_context(
            TestClient(
                create_event_consumer_app(
                    event_settings,
                    context_outbox_client=InProcessContextOutboxClient(context_client),
                    provenance_client=InProcessProvenanceClient(provenance_client),
                )
            )
        )

        create_response = context_client.post(
            "/tasks",
            json={
                "customer_id": "cust_001",
                "rail": "ach",
                "amount_usd": 2500,
                "task_metadata": {"workflow_id": "wf_task_001"},
                "provenance": {
                    "initiated_by": "user.neil",
                    "trace_id": "tr_001",
                },
            },
        )
        assert create_response.status_code == 201
        task_id = create_response.json()["task_id"]

        initial_records = provenance_client.get(f"/tasks/{task_id}/records")
        assert initial_records.status_code == 404

        dispatch_response = event_consumer_client.post("/dispatch/run-once", json={"limit": 10, "lease_seconds": 30})
        assert dispatch_response.status_code == 200
        assert dispatch_response.json()["processed_count"] == 1

        records = provenance_client.get(f"/tasks/{task_id}/records")
        assert records.status_code == 200
        assert records.json()["provenance"]["initiated_by"] == "user.neil"
        assert len(records.json()["state_history"]) == 1

        patch_response = context_client.patch(
            f"/tasks/{task_id}/state",
            json={
                "status": "awaiting_approval",
                "approval_status": "pending",
                "beneficiary_status": "approved",
                "changed_by": "workflow-worker",
                "reason": "Validation completed.",
            },
        )
        assert patch_response.status_code == 200

        second_dispatch = event_consumer_client.post("/dispatch/run-once", json={"limit": 10, "lease_seconds": 30})
        assert second_dispatch.status_code == 200
        assert second_dispatch.json()["processed_count"] == 1

        updated_records = provenance_client.get(f"/tasks/{task_id}/records")
        assert updated_records.status_code == 200
        assert len(updated_records.json()["state_history"]) == 2
