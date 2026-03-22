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
    def __init__(self, context_base_url: str, provenance_base_url: str, timeout_seconds: float = 5.0):
        self._context_client = httpx.Client(base_url=context_base_url, timeout=timeout_seconds)
        self._provenance_client = httpx.Client(base_url=provenance_base_url, timeout=timeout_seconds)

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            context_response = self._context_client.post(
                "/tasks",
                json={key: value for key, value in payload.items() if key != "provenance"},
            )
            context_response.raise_for_status()
        except httpx.HTTPError as exc:
            raise MemoryServiceError("Failed to create task in context-memory-service.") from exc

        context_task = context_response.json()
        task_id = context_task["task_id"]
        provenance = payload.get("provenance", {})

        try:
            provenance_response = self._provenance_client.post(f"/tasks/{task_id}/provenance", json=provenance)
            provenance_response.raise_for_status()
            transition_response = self._provenance_client.post(
                f"/tasks/{task_id}/state-transitions",
                json={
                    "from_status": None,
                    "to_status": context_task["status"],
                    "changed_by": provenance.get("initiated_by", "system"),
                    "reason": "task created",
                },
            )
            transition_response.raise_for_status()
        except httpx.HTTPError as exc:
            raise MemoryServiceError(f"Failed to create provenance for task {task_id}.") from exc

        return self.get_task(task_id)

    def get_task(self, task_id: str) -> dict[str, Any]:
        try:
            context_response = self._context_client.get(f"/tasks/{task_id}")
            context_response.raise_for_status()
            provenance_response = self._provenance_client.get(f"/tasks/{task_id}/records")
            provenance_response.raise_for_status()
        except httpx.HTTPError as exc:
            raise MemoryServiceError(f"Failed to load task {task_id} from context-memory-service or provenance-service.") from exc

        context_task = context_response.json()
        records = provenance_response.json()
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
