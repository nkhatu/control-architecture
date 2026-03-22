from __future__ import annotations

from typing import Any, Protocol

import httpx
from shared_contracts.events import TaskLifecycleOutboxEvent, parse_task_lifecycle_outbox_event


class ContextOutboxError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class ContextOutboxClient(Protocol):
    def claim_events(self, *, limit: int, lease_seconds: int) -> list[TaskLifecycleOutboxEvent]:
        ...

    def complete_event(self, event_id: str) -> TaskLifecycleOutboxEvent:
        ...

    def fail_event(self, event_id: str, *, error_message: str) -> TaskLifecycleOutboxEvent:
        ...

    def close(self) -> None:
        ...


class ContextOutboxHttpClient:
    def __init__(self, base_url: str, timeout_seconds: float = 5.0):
        self._client = httpx.Client(base_url=base_url, timeout=timeout_seconds)

    def claim_events(self, *, limit: int, lease_seconds: int) -> list[TaskLifecycleOutboxEvent]:
        payload = self._request(
            "post",
            "/outbox/claim",
            json={"limit": limit, "lease_seconds": lease_seconds},
            failure_message="Failed to claim context outbox events.",
        )
        return [parse_task_lifecycle_outbox_event(item) for item in payload.get("events", [])]

    def complete_event(self, event_id: str) -> TaskLifecycleOutboxEvent:
        payload = self._request(
            "post",
            f"/outbox/{event_id}/complete",
            failure_message=f"Failed to complete outbox event {event_id}.",
        )
        return parse_task_lifecycle_outbox_event(payload)

    def fail_event(self, event_id: str, *, error_message: str) -> TaskLifecycleOutboxEvent:
        payload = self._request(
            "post",
            f"/outbox/{event_id}/fail",
            json={"error_message": error_message},
            failure_message=f"Failed to mark outbox event {event_id} as failed.",
        )
        return parse_task_lifecycle_outbox_event(payload)

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
            raise ContextOutboxError(failure_message) from exc

        if response.is_error:
            raise ContextOutboxError(self._detail_from_response(response, failure_message), status_code=response.status_code)
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
