from __future__ import annotations

from typing import Any, Protocol

import httpx


class WorkflowWorkerError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502, error_class: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_class = error_class


class WorkflowWorkerClient(Protocol):
    def start_workflow(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def resume_workflow(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def close(self) -> None:
        ...


class WorkflowWorkerHttpClient:
    def __init__(self, base_url: str, timeout_seconds: float = 10.0):
        self._client = httpx.Client(base_url=base_url, timeout=timeout_seconds)

    def start_workflow(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "post",
            "/workflows/domestic-payments/start",
            json=payload,
            failure_message="Failed to start domestic payment workflow in workflow-worker.",
        )

    def resume_workflow(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "post",
            f"/workflows/domestic-payments/{task_id}/resume",
            json=payload,
            failure_message=f"Failed to resume domestic payment workflow for task {task_id}.",
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
            raise WorkflowWorkerError(failure_message) from exc

        if response.is_error:
            message, error_class = self._detail_from_response(response, failure_message)
            raise WorkflowWorkerError(message, status_code=response.status_code, error_class=error_class)

        return response.json()

    def _detail_from_response(self, response: httpx.Response, fallback: str) -> tuple[str, str | None]:
        try:
            payload = response.json()
        except ValueError:
            return fallback, None

        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str):
                return detail, None
            if isinstance(detail, dict):
                message = detail.get("message")
                error_class = detail.get("error_class")
                if isinstance(message, str):
                    return message, error_class if isinstance(error_class, str) else None

        return fallback, None
