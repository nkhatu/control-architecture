from __future__ import annotations

from typing import Any, Protocol

import httpx


class ProvenanceProjectionError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class ProvenanceProjectionClient(Protocol):
    def ensure_task_provenance(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def append_state_transition(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def close(self) -> None:
        ...


class ProvenanceProjectionHttpClient:
    def __init__(self, base_url: str, timeout_seconds: float = 5.0):
        self._client = httpx.Client(base_url=base_url, timeout=timeout_seconds)

    def ensure_task_provenance(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "post",
            f"/tasks/{task_id}/provenance",
            json=payload,
            failure_message=f"Failed to project provenance for task {task_id}.",
        )

    def append_state_transition(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "post",
            f"/tasks/{task_id}/state-transitions",
            json=payload,
            failure_message=f"Failed to project state transition for task {task_id}.",
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
            raise ProvenanceProjectionError(failure_message) from exc

        if response.is_error:
            raise ProvenanceProjectionError(self._detail_from_response(response, failure_message), status_code=response.status_code)
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
