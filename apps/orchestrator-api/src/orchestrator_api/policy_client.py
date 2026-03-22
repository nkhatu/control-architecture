from __future__ import annotations

from typing import Any, Protocol

import httpx


class PolicyEngineError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502, error_class: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_class = error_class


class PolicyEngineClient(Protocol):
    def evaluate_intake(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def evaluate_release(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def close(self) -> None:
        ...


class PolicyEngineHttpClient:
    def __init__(self, base_url: str, timeout_seconds: float = 5.0):
        self._client = httpx.Client(base_url=base_url, timeout=timeout_seconds)

    def evaluate_intake(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "/decisions/intake",
            payload,
            failure_message="Failed to evaluate intake policy in policy-engine.",
        )

    def evaluate_release(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "/decisions/release",
            payload,
            failure_message="Failed to evaluate release policy in policy-engine.",
        )

    def close(self) -> None:
        self._client.close()

    def _request(self, path: str, payload: dict[str, Any], *, failure_message: str) -> dict[str, Any]:
        try:
            response = self._client.post(path, json=payload)
        except httpx.HTTPError as exc:
            raise PolicyEngineError(failure_message) from exc

        if response.is_error:
            raise PolicyEngineError(failure_message, status_code=response.status_code)

        return response.json()
