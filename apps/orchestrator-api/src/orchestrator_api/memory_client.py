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

    def close(self) -> None:
        ...


class MemoryServiceHttpClient:
    def __init__(self, base_url: str, timeout_seconds: float = 5.0):
        self._client = httpx.Client(base_url=base_url, timeout=timeout_seconds)

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post("/tasks", json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise MemoryServiceError("Failed to create task in memory-service.") from exc

        return response.json()

    def get_task(self, task_id: str) -> dict[str, Any]:
        try:
            response = self._client.get(f"/tasks/{task_id}")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise MemoryServiceError(f"Failed to load task {task_id} from memory-service.") from exc

        return response.json()

    def close(self) -> None:
        self._client.close()
