from __future__ import annotations

from typing import Any, Protocol

import httpx


class MemoryServiceError(RuntimeError):
    """Raised when the orchestrator cannot complete a memory-service call."""


class MemoryServiceClient(Protocol):
    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def get_task(self, task_id: str) -> dict[str, Any]:
        ...

    def create_artifact(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def close(self) -> None:
        ...


class MemoryServiceHttpClient:
    def __init__(
        self,
        context_base_url: str,
        provenance_base_url: str,
        event_consumer_base_url: str,
        timeout_seconds: float = 5.0,
    ):
        self._context_client = httpx.Client(base_url=context_base_url, timeout=timeout_seconds)
        self._provenance_client = httpx.Client(base_url=provenance_base_url, timeout=timeout_seconds)
        self._event_consumer_client = httpx.Client(base_url=event_consumer_base_url, timeout=timeout_seconds)

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            context_response = self._context_client.post(
                "/tasks",
                json=payload,
            )
            context_response.raise_for_status()
        except httpx.HTTPError as exc:
            raise MemoryServiceError("Failed to create task in context-memory-service.") from exc

        context_task = context_response.json()
        self._dispatch_consistency()
        return self.get_task(context_task["task_id"])

    def get_task(self, task_id: str) -> dict[str, Any]:
        try:
            context_response = self._context_client.get(f"/tasks/{task_id}")
            context_response.raise_for_status()
        except httpx.HTTPError as exc:
            raise MemoryServiceError(f"Failed to load task {task_id} from context-memory-service or provenance-service.") from exc

        context_task = context_response.json()
        records = self._provenance_records(task_id)
        return {
            **context_task,
            "provenance": records["provenance"],
            "state_history": records["state_history"],
            "artifacts": records["artifacts"],
            "delegations": records["delegations"],
        }

    def create_artifact(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._provenance_client.post(f"/tasks/{task_id}/artifacts", json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise MemoryServiceError(f"Failed to create artifact for task {task_id} in provenance-service.") from exc

        return response.json()

    def close(self) -> None:
        self._context_client.close()
        self._provenance_client.close()
        self._event_consumer_client.close()

    def _provenance_records(self, task_id: str) -> dict[str, Any]:
        try:
            response = self._provenance_client.get(f"/tasks/{task_id}/records")
        except httpx.HTTPError as exc:
            raise MemoryServiceError(f"Failed to load task {task_id} from context-memory-service or provenance-service.") from exc

        if response.status_code == 404:
            return {
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

        if response.is_error:
            raise MemoryServiceError(f"Failed to load task {task_id} from context-memory-service or provenance-service.")

        return response.json()

    def _dispatch_consistency(self) -> None:
        try:
            response = self._event_consumer_client.post("/dispatch/run-once", json={"limit": 100, "lease_seconds": 30})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise MemoryServiceError("Failed to dispatch context outbox events through event-consumer.") from exc
