from __future__ import annotations

from typing import Any, Protocol

import httpx
from shared_contracts.tasks import (
    ArtifactView,
    DelegatedWorkView,
    TaskContextView,
    TaskDetailView,
    TaskRecordsView,
    empty_task_records,
    merge_task_detail,
)


class MemoryServiceError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class MemoryServiceClient(Protocol):
    def create_task(self, payload: dict[str, Any]) -> TaskDetailView:
        ...

    def get_task(self, task_id: str) -> TaskDetailView:
        ...

    def patch_task_state(self, task_id: str, payload: dict[str, Any]) -> TaskDetailView:
        ...

    def create_artifact(self, task_id: str, payload: dict[str, Any]) -> ArtifactView:
        ...

    def create_delegation(self, task_id: str, payload: dict[str, Any]) -> DelegatedWorkView:
        ...

    def update_delegation(self, delegation_id: str, payload: dict[str, Any]) -> DelegatedWorkView:
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

    def create_task(self, payload: dict[str, Any]) -> TaskDetailView:
        context_task = self._context_request(
            "post",
            "/tasks",
            json=payload,
            failure_message="Failed to create task in context-memory-service.",
        )
        self._dispatch_consistency()
        return self.get_task(context_task.task_id)

    def get_task(self, task_id: str) -> TaskDetailView:
        context_task = self._context_request(
            "get",
            f"/tasks/{task_id}",
            failure_message=f"Failed to load task {task_id} from context-memory-service.",
        )
        records = self._provenance_request_allow_missing(
            "get",
            f"/tasks/{task_id}/records",
            failure_message=f"Failed to load provenance for task {task_id}.",
        )
        return merge_task_detail(context_task, records)

    def patch_task_state(self, task_id: str, payload: dict[str, Any]) -> TaskDetailView:
        self._context_request(
            "patch",
            f"/tasks/{task_id}/state",
            json=payload,
            failure_message=f"Failed to update task {task_id} state in context-memory-service.",
        )
        self._dispatch_consistency()
        return self.get_task(task_id)

    def create_artifact(self, task_id: str, payload: dict[str, Any]) -> ArtifactView:
        response = self._provenance_request(
            "post",
            f"/tasks/{task_id}/artifacts",
            json=payload,
            failure_message=f"Failed to create artifact for task {task_id} in provenance-service.",
        )
        return ArtifactView.model_validate(response)

    def create_delegation(self, task_id: str, payload: dict[str, Any]) -> DelegatedWorkView:
        response = self._provenance_request(
            "post",
            f"/tasks/{task_id}/delegations",
            json=payload,
            failure_message=f"Failed to create delegation for task {task_id} in provenance-service.",
        )
        return DelegatedWorkView.model_validate(response)

    def update_delegation(self, delegation_id: str, payload: dict[str, Any]) -> DelegatedWorkView:
        response = self._provenance_request(
            "patch",
            f"/delegations/{delegation_id}",
            json=payload,
            failure_message=f"Failed to update delegation {delegation_id} in provenance-service.",
        )
        return DelegatedWorkView.model_validate(response)

    def close(self) -> None:
        self._context_client.close()
        self._provenance_client.close()
        self._event_consumer_client.close()

    def _context_request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        failure_message: str,
    ) -> TaskContextView:
        try:
            response = self._context_client.request(method, path, json=json)
        except httpx.HTTPError as exc:
            raise MemoryServiceError(failure_message) from exc

        if response.is_error:
            raise MemoryServiceError(self._detail_from_response(response, failure_message), status_code=response.status_code)

        return TaskContextView.model_validate(response.json())

    def _provenance_request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        failure_message: str,
    ) -> dict[str, Any]:
        try:
            response = self._provenance_client.request(method, path, json=json)
        except httpx.HTTPError as exc:
            raise MemoryServiceError(failure_message) from exc

        if response.is_error:
            raise MemoryServiceError(self._detail_from_response(response, failure_message), status_code=response.status_code)

        return response.json()

    def _provenance_request_allow_missing(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        failure_message: str,
    ) -> TaskRecordsView:
        try:
            response = self._provenance_client.request(method, path, json=json)
        except httpx.HTTPError as exc:
            raise MemoryServiceError(failure_message) from exc

        if response.status_code == 404:
            return empty_task_records(path.split("/")[2])

        if response.is_error:
            raise MemoryServiceError(self._detail_from_response(response, failure_message), status_code=response.status_code)

        return TaskRecordsView.model_validate(response.json())

    def _dispatch_consistency(self) -> None:
        try:
            response = self._event_consumer_client.post("/dispatch/run-once", json={"limit": 100, "lease_seconds": 30})
        except httpx.HTTPError as exc:
            raise MemoryServiceError("Failed to dispatch context outbox events through event-consumer.") from exc

        if response.is_error:
            raise MemoryServiceError(self._detail_from_response(response, "Failed to dispatch context outbox events through event-consumer."), status_code=response.status_code)

    def _detail_from_response(self, response: httpx.Response, fallback: str) -> str:
        try:
            payload = response.json()
        except ValueError:
            return fallback

        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str):
                return detail
            if isinstance(detail, dict):
                message = detail.get("message")
                if isinstance(message, str):
                    return message
        return fallback
