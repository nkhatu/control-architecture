from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


PolicyDecisionType = Literal["allow", "deny", "escalate", "simulate"]
ReleaseMode = Literal["dry_run", "execute"]


class PrincipalContext(BaseModel):
    actor_id: str | None = None
    scopes: list[str] = Field(default_factory=list)


class IntakeDecisionRequest(BaseModel):
    customer_id: str
    rail: str
    amount_usd: float = Field(gt=0)
    principal: PrincipalContext = Field(default_factory=PrincipalContext)
    trace_id: str | None = None


class PaymentContext(BaseModel):
    task_id: str
    payment_id: str
    amount_usd: float = Field(gt=0)
    rail: str
    status: str
    approval_status: str
    beneficiary_status: str
    task_metadata: dict[str, Any] = Field(default_factory=dict)


class ReleaseRequestContext(BaseModel):
    approved_by: str
    approval_note: str | None = None
    approval_outcome: Literal["approved"] = "approved"
    idempotency_key: str
    release_mode: ReleaseMode = "execute"


class ReleaseDecisionRequest(BaseModel):
    payment: PaymentContext
    principal: PrincipalContext = Field(default_factory=PrincipalContext)
    request: ReleaseRequestContext
    trace_id: str | None = None


class PolicyDecisionResponse(BaseModel):
    decision: PolicyDecisionType
    reason: str
    approval_profile: str
    execution_mode: str
    recommended_next_capability: str
    requires_manual_escalation: bool = False
