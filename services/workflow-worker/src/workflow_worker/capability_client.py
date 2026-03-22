from __future__ import annotations

from typing import Any, Protocol

import httpx


class CapabilityGatewayError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502, error_class: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_class = error_class


class CapabilityGatewayClient(Protocol):
    def create_instruction(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def validate_beneficiary(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def release_payment(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def close(self) -> None:
        ...


class CapabilityGatewayHttpClient:
    def __init__(self, base_url: str, timeout_seconds: float = 5.0):
        self._client = httpx.Client(base_url=base_url, timeout=timeout_seconds)

    def create_instruction(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "post",
            "/domestic-payments/instructions",
            json=payload,
            failure_message="Failed to create a domestic payment instruction in capability-gateway.",
        )

    def validate_beneficiary(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "post",
            "/domestic-payments/beneficiaries/validate",
            json=payload,
            failure_message="Failed to validate beneficiary details in capability-gateway.",
        )

    def release_payment(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "post",
            "/domestic-payments/release",
            json=payload,
            failure_message="Failed to release payment through capability-gateway.",
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
            raise CapabilityGatewayError(failure_message) from exc

        if response.is_error:
            message, error_class = self._detail_from_response(response, failure_message)
            raise CapabilityGatewayError(message, status_code=response.status_code, error_class=error_class)

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
