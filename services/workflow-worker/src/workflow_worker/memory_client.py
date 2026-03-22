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
    def __init__(self, context_base_url: str, provenance_base_url: str, timeout_seconds: float = 5.0):
        self._context_client = httpx.Client(base_url=context_base_url, timeout=timeout_seconds)
        self._provenance_client = httpx.Client(base_url=provenance_base_url, timeout=timeout_seconds)

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        context_task = self._context_request(
            "post",
            "/tasks",
            json={key: value for key, value in payload.items() if key != "provenance"},
            failure_message="Failed to create task in context-memory-service.",
        )
        provenance = payload.get("provenance", {})
        task_id = context_task["task_id"]
        self._provenance_request(
            "post",
            f"/tasks/{task_id}/provenance",
            json=provenance,
            failure_message=f"Failed to create provenance record for task {task_id}.",
        )
        self._provenance_request(
            "post",
            f"/tasks/{task_id}/state-transitions",
            json={
                "from_status": None,
                "to_status": context_task["status"],
                "changed_by": provenance.get("initiated_by", "system"),
                "reason": "task created",
            },
            failure_message=f"Failed to create initial state transition for task {task_id}.",
        )
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> dict[str, Any]:
        context_task = self._context_request(
            "get",
            f"/tasks/{task_id}",
            failure_message=f"Failed to load task {task_id} from context-memory-service.",
        )
        records = self._provenance_request(
            "get",
            f"/tasks/{task_id}/records",
            failure_message=f"Failed to load provenance for task {task_id}.",
        )
        return self._merge_task_detail(context_task, records)

    def patch_task_state(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        current_task = self._context_request(
            "get",
            f"/tasks/{task_id}",
            failure_message=f"Failed to load task {task_id} from context-memory-service.",
        )
        self._context_request(
            "patch",
            f"/tasks/{task_id}/state",
            json={
                "status": payload["status"],
                "approval_status": payload.get("approval_status"),
                "beneficiary_status": payload.get("beneficiary_status"),
            },
            failure_message=f"Failed to update task {task_id} state in context-memory-service.",
        )
        self._provenance_request(
            "post",
            f"/tasks/{task_id}/state-transitions",
            json={
                "from_status": current_task["status"],
                "to_status": payload["status"],
                "changed_by": payload["changed_by"],
                "reason": payload.get("reason"),
            },
            failure_message=f"Failed to record state transition for task {task_id}.",
        )
        return self.get_task(task_id)

    def create_artifact(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._provenance_request(
            "post",
            f"/tasks/{task_id}/artifacts",
            json=payload,
            failure_message=f"Failed to create artifact for task {task_id} in provenance-service.",
        )

    def create_delegation(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._provenance_request(
            "post",
            f"/tasks/{task_id}/delegations",
            json=payload,
            failure_message=f"Failed to create delegation for task {task_id} in provenance-service.",
        )

    def update_delegation(self, delegation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._provenance_request(
            "patch",
            f"/delegations/{delegation_id}",
            json=payload,
            failure_message=f"Failed to update delegation {delegation_id} in provenance-service.",
        )

    def close(self) -> None:
        self._context_client.close()
        self._provenance_client.close()

    def _context_request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        failure_message: str,
    ) -> dict[str, Any]:
        try:
            response = self._context_client.request(method, path, json=json)
        except httpx.HTTPError as exc:
            raise MemoryServiceError(failure_message) from exc

        if response.is_error:
            raise MemoryServiceError(self._detail_from_response(response, failure_message), status_code=response.status_code)

        return response.json()

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

    def _merge_task_detail(self, context_task: dict[str, Any], records: dict[str, Any]) -> dict[str, Any]:
        return {
            **context_task,
            "provenance": records["provenance"],
            "state_history": records["state_history"],
            "artifacts": records["artifacts"],
            "delegations": records["delegations"],
        }

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
