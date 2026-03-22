from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


Rail = Literal["ach", "same_day_ach", "internal_transfer", "rtp"]
PolicyDecisionType = Literal["allow", "deny", "escalate", "simulate"]


class DomesticPaymentIntakeRequest(BaseModel):
    customer_id: str
    source_account_id: str
    beneficiary_id: str
    amount_usd: float = Field(gt=0)
    rail: Rail
    requested_execution_date: date
    initiated_by: str
    memo: str | None = None
    trace_id: str | None = None
    principal_scopes: list[str] = Field(
        default_factory=lambda: [
            "payment.validate",
            "payment.submit_for_approval",
        ]
    )


class PolicyDecisionResponse(BaseModel):
    decision: PolicyDecisionType
    reason: str
    approval_profile: str
    execution_mode: str
    recommended_next_capability: str
    requires_manual_escalation: bool = False


class DomesticPaymentIntakeResponse(BaseModel):
    task: dict[str, Any]
    policy_decision: PolicyDecisionResponse
    available_capabilities: list[str]
    selected_agents: list[str]
