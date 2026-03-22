from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


Rail = Literal["ach", "same_day_ach", "internal_transfer", "rtp"]
PolicyDecisionType = Literal["allow", "deny", "escalate", "simulate"]
ReleaseMode = Literal["dry_run", "execute"]


class DomesticPaymentIntakePayload(BaseModel):
    customer_id: str
    source_account_id: str
    beneficiary_id: str
    amount_usd: float = Field(gt=0)
    rail: Rail
    requested_execution_date: date
    initiated_by: str
    memo: str | None = None
    trace_id: str | None = None
    principal_scopes: list[str] = Field(default_factory=list)


class PolicyDecision(BaseModel):
    decision: PolicyDecisionType
    reason: str
    approval_profile: str
    execution_mode: str
    recommended_next_capability: str
    requires_manual_escalation: bool = False


class WorkflowStartRequest(BaseModel):
    request: DomesticPaymentIntakePayload
    policy_decision: PolicyDecision
    selected_agents: list[str] = Field(default_factory=list)
    available_capabilities: list[str] = Field(default_factory=list)


class WorkflowResumeRequest(BaseModel):
    approved_by: str
    approval_note: str | None = None
    idempotency_key: str | None = None
    release_mode: ReleaseMode = "execute"


class WorkflowProgress(BaseModel):
    workflow_id: str
    workflow_state: str
    next_action: str
    last_capability: str | None = None


class WorkflowExecutionResponse(BaseModel):
    task: dict[str, Any]
    workflow: WorkflowProgress
    artifacts_created: list[str] = Field(default_factory=list)
    release_result: dict[str, Any] | None = None
