from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


Rail = Literal["ach", "same_day_ach", "internal_transfer", "rtp"]
PaymentStatus = Literal[
    "received",
    "validated",
    "awaiting_approval",
    "approved",
    "released",
    "settlement_pending",
    "settled",
    "failed",
    "cancelled",
    "pending_reconcile",
    "exception",
]
BeneficiaryTaskStatus = Literal["unknown", "approved", "rejected", "needs_review"]
ApprovalStatus = Literal["not_required", "pending", "approved", "denied", "expired"]
BeneficiaryValidationStatus = Literal["validated", "rejected", "needs_review"]
MockRailOutcome = Literal["success", "reject", "ambiguous"]


class TaskProvenance(BaseModel):
    initiated_by: str
    last_updated_by: str
    policy_context_id: str | None = None
    trace_id: str | None = None


class DomesticPaymentTask(BaseModel):
    task_id: str
    payment_id: str
    customer_id: str
    rail: Rail
    amount_usd: float = Field(gt=0)
    status: PaymentStatus
    beneficiary_status: BeneficiaryTaskStatus
    approval_status: ApprovalStatus
    provenance: TaskProvenance


class DomesticPaymentInstructionRequest(BaseModel):
    customer_id: str
    source_account_id: str
    beneficiary_id: str
    amount_usd: float = Field(gt=0)
    rail: Rail
    requested_execution_date: date
    memo: str | None = None
    initiated_by: str = "orchestrator-api"
    trace_id: str | None = None


class BeneficiaryValidationRequest(BaseModel):
    task_id: str
    payment_id: str
    customer_id: str
    beneficiary_id: str
    amount_usd: float = Field(gt=0)
    rail: Rail
    trace_id: str | None = None


class ReleaseApprovedPaymentRequest(BaseModel):
    payment_id: str
    task_id: str
    idempotency_key: str = Field(min_length=8)
    released_by: str
    release_mode: Literal["dry_run", "execute"] = "execute"


class BeneficiaryValidationResult(BaseModel):
    beneficiary_id: str
    status: BeneficiaryValidationStatus
    reason: str | None = None
    validated_at: datetime


class PaymentStatusResponse(BaseModel):
    payment_id: str
    status: PaymentStatus
    rail: Rail | None = None
    updated_at: datetime
    error_class: str | None = None
    explanation: str | None = None


class GatewayResponseBase(BaseModel):
    capability_id: str
    side_effect_class: str


class DomesticPaymentInstructionResponse(GatewayResponseBase):
    instruction_id: str
    task: DomesticPaymentTask
    payment_status: PaymentStatusResponse


class BeneficiaryValidationResponse(GatewayResponseBase):
    result: BeneficiaryValidationResult
    task: DomesticPaymentTask


class ReleaseApprovedPaymentResponse(GatewayResponseBase):
    idempotency_key: str
    idempotency_replayed: bool = False
    mock_rail_outcome: MockRailOutcome
    result: PaymentStatusResponse
    task: DomesticPaymentTask


class PaymentStatusEnvelope(GatewayResponseBase):
    payment_status: PaymentStatusResponse

