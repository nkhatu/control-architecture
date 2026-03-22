from __future__ import annotations

from typing import Any, Protocol

import httpx


class MemoryServiceError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class MemoryServiceClient(Protocol):
    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def get_task(self, task_id: str) -> dict[str, Any]:
        ...

    def patch_task_state(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def create_artifact(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def create_delegation(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def update_delegation(self, delegation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def close(self) -> None:
        ...


class MemoryServiceHttpClient:
    def __init__(self, base_url: str, timeout_seconds: float = 5.0):
        self._client = httpx.Client(base_url=base_url, timeout=timeout_seconds)

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("post", "/tasks", json=payload, failure_message="Failed to create task in memory-service.")

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self._request(
            "get",
            f"/tasks/{task_id}",
            failure_message=f"Failed to load task {task_id} from memory-service.",
        )

    def patch_task_state(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "patch",
            f"/tasks/{task_id}/state",
            json=payload,
            failure_message=f"Failed to update task {task_id} state in memory-service.",
        )

    def create_artifact(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "post",
            f"/tasks/{task_id}/artifacts",
            json=payload,
            failure_message=f"Failed to create artifact for task {task_id} in memory-service.",
        )

    def create_delegation(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "post",
            f"/tasks/{task_id}/delegations",
            json=payload,
            failure_message=f"Failed to create delegation for task {task_id} in memory-service.",
        )

    def update_delegation(self, delegation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "patch",
            f"/delegations/{delegation_id}",
            json=payload,
            failure_message=f"Failed to update delegation {delegation_id} in memory-service.",
        )

    def close(self) -> None:
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        failure_message: str,
    ) -> dict[str, Any]:
        try:
            response = self._client.request(method, path, json=json)
        except httpx.HTTPError as exc:
            raise MemoryServiceError(failure_message) from exc

        if response.is_error:
            raise MemoryServiceError(self._detail_from_response(response, failure_message), status_code=response.status_code)

        return response.json()

    def _detail_from_response(self, response: httpx.Response, fallback: str) -> str:
        try:
            payload = response.json()
        except ValueError:
            return fallback

        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str):
                return detail
        return fallback
