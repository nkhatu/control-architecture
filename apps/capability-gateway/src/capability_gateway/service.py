from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import secrets
from typing import Any

from .mock_rail import MockRailAdapter
from .schemas import (
    BeneficiaryTaskStatus,
    BeneficiaryValidationRequest,
    BeneficiaryValidationResponse,
    DomesticPaymentInstructionRequest,
    DomesticPaymentInstructionResponse,
    DomesticPaymentTask,
    PaymentStatusEnvelope,
    PaymentStatusResponse,
    ReleaseApprovedPaymentRequest,
    ReleaseApprovedPaymentResponse,
    TaskProvenance,
)


CAPABILITY_CREATE_INSTRUCTION = "domestic_payment.create_instruction"
CAPABILITY_VALIDATE_BENEFICIARY = "domestic_payment.validate_beneficiary_account"
CAPABILITY_RELEASE_PAYMENT = "domestic_payment.release_approved_payment"
CAPABILITY_CHECK_STATUS = "domestic_payment.check_payment_status"
EXPECTED_CAPABILITY_IDS = {
    CAPABILITY_CREATE_INSTRUCTION,
    CAPABILITY_VALIDATE_BENEFICIARY,
    CAPABILITY_RELEASE_PAYMENT,
    CAPABILITY_CHECK_STATUS,
}


class CapabilityGatewayError(Exception):
    def __init__(self, message: str, *, status_code: int, error_class: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_class = error_class


@dataclass
class GatewayPaymentRecord:
    instruction_id: str
    task: DomesticPaymentTask
    payment_status: PaymentStatusResponse
    source_account_id: str
    beneficiary_id: str
    requested_execution_date: date
    memo: str | None


@dataclass
class IdempotencyRecord:
    fingerprint: str
    response: ReleaseApprovedPaymentResponse


class InMemoryGatewayStore:
    def __init__(self) -> None:
        self._records_by_payment_id: dict[str, GatewayPaymentRecord] = {}
        self._records_by_task_id: dict[str, GatewayPaymentRecord] = {}
        self._idempotency_records: dict[str, IdempotencyRecord] = {}

    def put(self, record: GatewayPaymentRecord) -> None:
        self._records_by_payment_id[record.task.payment_id] = record
        self._records_by_task_id[record.task.task_id] = record

    def get_by_payment_id(self, payment_id: str) -> GatewayPaymentRecord | None:
        return self._records_by_payment_id.get(payment_id)

    def get_by_task_id(self, task_id: str) -> GatewayPaymentRecord | None:
        return self._records_by_task_id.get(task_id)

    def get_idempotency_record(self, idempotency_key: str) -> IdempotencyRecord | None:
        return self._idempotency_records.get(idempotency_key)

    def put_idempotency_record(self, idempotency_key: str, record: IdempotencyRecord) -> None:
        self._idempotency_records[idempotency_key] = record


class CapabilityGatewayService:
    def __init__(
        self,
        *,
        control_plane_config: dict[str, Any],
        capability_registry: dict[str, Any],
        mock_rail_adapter: MockRailAdapter | None = None,
        store: InMemoryGatewayStore | None = None,
        app_name: str = "capability-gateway",
        mock_rail_name: str = "mock-domestic-rail",
    ) -> None:
        self._control_plane_config = control_plane_config
        self._app_name = app_name
        self._mock_rail_name = mock_rail_name
        self._capabilities = self._load_capabilities(capability_registry)
        self._mock_rail = mock_rail_adapter or MockRailAdapter(
            ambiguous_status=control_plane_config.get("control_plane", {}).get("ambiguous_response_action", "pending_reconcile")
        )
        self._store = store or InMemoryGatewayStore()

    def metadata(self) -> dict[str, Any]:
        environment = self._control_plane_config.get("environment", {})
        capabilities = [
            {
                "id": capability_id,
                "category": capability.get("category", "unknown"),
                "side_effect_class": capability.get("side_effect_class", "unknown"),
            }
            for capability_id, capability in sorted(self._capabilities.items())
        ]
        return {
            "service": self._app_name,
            "environment": environment.get("name", "unknown"),
            "mode": environment.get("default_mode", "unknown"),
            "rail_scope": environment.get("rail_scope", []),
            "mock_rail": {
                "name": self._mock_rail_name,
                "deterministic_outcomes": {
                    "success": "default path",
                    "reject": "payment_id or idempotency key contains 'reject' or key ends with '99'",
                    "ambiguous": "payment_id or idempotency key contains 'ambiguous' or key ends with '77'",
                },
            },
            "capabilities": capabilities,
        }

    def create_instruction(self, payload: DomesticPaymentInstructionRequest) -> DomesticPaymentInstructionResponse:
        self._ensure_supported_rail(payload.rail)

        timestamp = self._utcnow()
        task_id = self._new_identifier("task")
        payment_id = self._new_identifier("pay")
        instruction_id = self._new_identifier("instr")
        task = DomesticPaymentTask(
            task_id=task_id,
            payment_id=payment_id,
            customer_id=payload.customer_id,
            rail=payload.rail,
            amount_usd=payload.amount_usd,
            status="received",
            beneficiary_status="unknown",
            approval_status="pending",
            provenance=TaskProvenance(
                initiated_by=payload.initiated_by,
                last_updated_by=self._app_name,
                trace_id=payload.trace_id,
            ),
        )
        payment_status = PaymentStatusResponse(
            payment_id=payment_id,
            status="received",
            rail=payload.rail,
            updated_at=timestamp,
            explanation="The mock capability gateway accepted the payment instruction.",
        )
        self._store.put(
            GatewayPaymentRecord(
                instruction_id=instruction_id,
                task=task,
                payment_status=payment_status,
                source_account_id=payload.source_account_id,
                beneficiary_id=payload.beneficiary_id,
                requested_execution_date=payload.requested_execution_date,
                memo=payload.memo,
            )
        )
        return DomesticPaymentInstructionResponse(
            capability_id=CAPABILITY_CREATE_INSTRUCTION,
            side_effect_class=self._capabilities[CAPABILITY_CREATE_INSTRUCTION]["side_effect_class"],
            instruction_id=instruction_id,
            task=task,
            payment_status=payment_status,
        )

    def validate_beneficiary(self, payload: BeneficiaryValidationRequest) -> BeneficiaryValidationResponse:
        record = self._store.get_by_payment_id(payload.payment_id)
        if record is None or record.task.task_id != payload.task_id:
            raise CapabilityGatewayError(
                "No gateway payment record matched the supplied task and payment identifiers.",
                status_code=404,
                error_class="state_conflict",
            )

        validated_at = self._utcnow()
        result = self._mock_rail.validate_beneficiary(payload.beneficiary_id, validated_at)
        beneficiary_status = self._beneficiary_task_status(result.status)
        payment_status_value = "validated" if result.status == "validated" else "exception"
        explanation = result.reason
        updated_task = self._copy_task(
            record.task,
            status=payment_status_value,
            beneficiary_status=beneficiary_status,
            last_updated_by=self._app_name,
            trace_id=payload.trace_id,
        )
        updated_payment_status = PaymentStatusResponse(
            payment_id=record.task.payment_id,
            status=payment_status_value,
            rail=record.task.rail,
            updated_at=validated_at,
            error_class=None if result.status == "validated" else "state_conflict",
            explanation=explanation,
        )
        self._store.put(
            GatewayPaymentRecord(
                instruction_id=record.instruction_id,
                task=updated_task,
                payment_status=updated_payment_status,
                source_account_id=record.source_account_id,
                beneficiary_id=record.beneficiary_id,
                requested_execution_date=record.requested_execution_date,
                memo=record.memo,
            )
        )
        return BeneficiaryValidationResponse(
            capability_id=CAPABILITY_VALIDATE_BENEFICIARY,
            side_effect_class=self._capabilities[CAPABILITY_VALIDATE_BENEFICIARY]["side_effect_class"],
            result=result,
            task=updated_task,
        )

    def release_approved_payment(self, payload: ReleaseApprovedPaymentRequest) -> ReleaseApprovedPaymentResponse:
        record = self._store.get_by_payment_id(payload.payment_id)
        if record is None or record.task.task_id != payload.task_id:
            raise CapabilityGatewayError(
                "No gateway payment record matched the supplied task and payment identifiers.",
                status_code=404,
                error_class="state_conflict",
            )

        release_capability = self._capabilities[CAPABILITY_RELEASE_PAYMENT]
        if payload.release_mode == "dry_run" and not release_capability.get("dry_run_supported", False):
            raise CapabilityGatewayError(
                "The release capability does not support dry_run mode in this PoC configuration.",
                status_code=409,
                error_class="state_conflict",
            )

        fingerprint = self._release_request_fingerprint(payload)
        prior_record = self._store.get_idempotency_record(payload.idempotency_key)
        if prior_record is not None:
            if prior_record.fingerprint != fingerprint:
                raise CapabilityGatewayError(
                    "The idempotency key has already been used for a different release request.",
                    status_code=409,
                    error_class="duplicate_request",
                )
            return prior_record.response.model_copy(update={"idempotency_replayed": True})

        outcome, payment_status = self._mock_rail.release_payment(
            payment_id=payload.payment_id,
            rail=record.task.rail,
            idempotency_key=payload.idempotency_key,
            updated_at=self._utcnow(),
        )
        updated_task = self._copy_task(
            record.task,
            status=payment_status.status,
            approval_status="approved",
            last_updated_by=payload.released_by,
        )
        self._store.put(
            GatewayPaymentRecord(
                instruction_id=record.instruction_id,
                task=updated_task,
                payment_status=payment_status,
                source_account_id=record.source_account_id,
                beneficiary_id=record.beneficiary_id,
                requested_execution_date=record.requested_execution_date,
                memo=record.memo,
            )
        )
        response = ReleaseApprovedPaymentResponse(
            capability_id=CAPABILITY_RELEASE_PAYMENT,
            side_effect_class=release_capability["side_effect_class"],
            idempotency_key=payload.idempotency_key,
            idempotency_replayed=False,
            mock_rail_outcome=outcome,
            result=payment_status,
            task=updated_task,
        )
        self._store.put_idempotency_record(
            payload.idempotency_key,
            IdempotencyRecord(fingerprint=fingerprint, response=response),
        )
        return response

    def get_payment_status(self, payment_id: str) -> PaymentStatusEnvelope:
        record = self._store.get_by_payment_id(payment_id)
        if record is None:
            raise CapabilityGatewayError(
                "No gateway payment record matched the supplied payment identifier.",
                status_code=404,
                error_class="state_conflict",
            )

        return PaymentStatusEnvelope(
            capability_id=CAPABILITY_CHECK_STATUS,
            side_effect_class=self._capabilities[CAPABILITY_CHECK_STATUS]["side_effect_class"],
            payment_status=record.payment_status,
        )

    def _ensure_supported_rail(self, rail: str) -> None:
        rail_scope = set(self._control_plane_config.get("environment", {}).get("rail_scope", []))
        if rail not in rail_scope:
            raise CapabilityGatewayError(
                f"Rail {rail} is outside the configured PoC rail scope.",
                status_code=403,
                error_class="policy_denied",
            )

    def _load_capabilities(self, capability_registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
        capabilities = {
            entry["id"]: entry
            for entry in capability_registry.get("capabilities", [])
            if entry.get("owner") == self._app_name
        }
        missing_capabilities = EXPECTED_CAPABILITY_IDS - set(capabilities)
        if missing_capabilities:
            missing = ", ".join(sorted(missing_capabilities))
            raise ValueError(f"Capability registry is missing expected gateway capabilities: {missing}")
        return capabilities

    def _beneficiary_task_status(self, result_status: str) -> BeneficiaryTaskStatus:
        mapping: dict[str, BeneficiaryTaskStatus] = {
            "validated": "approved",
            "rejected": "rejected",
            "needs_review": "needs_review",
        }
        return mapping[result_status]

    def _copy_task(
        self,
        task: DomesticPaymentTask,
        *,
        status: str | None = None,
        beneficiary_status: str | None = None,
        approval_status: str | None = None,
        last_updated_by: str,
        trace_id: str | None = None,
    ) -> DomesticPaymentTask:
        provenance = task.provenance.model_copy(
            update={
                "last_updated_by": last_updated_by,
                "trace_id": trace_id if trace_id is not None else task.provenance.trace_id,
            }
        )
        return task.model_copy(
            update={
                "status": status or task.status,
                "beneficiary_status": beneficiary_status or task.beneficiary_status,
                "approval_status": approval_status or task.approval_status,
                "provenance": provenance,
            }
        )

    def _release_request_fingerprint(self, payload: ReleaseApprovedPaymentRequest) -> str:
        canonical_payload = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

    def _utcnow(self) -> datetime:
        return datetime.now(timezone.utc)

    def _new_identifier(self, prefix: str) -> str:
        return f"{prefix}_{secrets.token_hex(6)}"
