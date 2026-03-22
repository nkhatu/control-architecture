from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DispatchRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)
    lease_seconds: int = Field(default=30, ge=1, le=3600)


class DispatchFailure(BaseModel):
    event_id: str
    event_type: str
    error_message: str


class DispatchResponse(BaseModel):
    claimed_count: int
    processed_count: int
    failed_count: int
    failures: list[DispatchFailure] = Field(default_factory=list)


class OutboxEvent(BaseModel):
    event_id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload: dict[str, Any]
    status: str
    attempt_count: int
