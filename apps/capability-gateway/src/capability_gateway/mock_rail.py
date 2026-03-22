from __future__ import annotations

from datetime import datetime

from .schemas import BeneficiaryValidationResult, MockRailOutcome, PaymentStatusResponse


class MockRailAdapter:
    def __init__(self, ambiguous_status: str = "pending_reconcile") -> None:
        self._ambiguous_status = ambiguous_status

    def validate_beneficiary(self, beneficiary_id: str, validated_at: datetime) -> BeneficiaryValidationResult:
        normalized = beneficiary_id.lower()

        if "review" in normalized or normalized.endswith("7"):
            return BeneficiaryValidationResult(
                beneficiary_id=beneficiary_id,
                status="needs_review",
                reason="The mock rail flagged this beneficiary for manual review.",
                validated_at=validated_at,
            )

        if "reject" in normalized or normalized.endswith("9"):
            return BeneficiaryValidationResult(
                beneficiary_id=beneficiary_id,
                status="rejected",
                reason="The mock rail rejected the beneficiary details.",
                validated_at=validated_at,
            )

        return BeneficiaryValidationResult(
            beneficiary_id=beneficiary_id,
            status="validated",
            reason="The mock rail validated the beneficiary account.",
            validated_at=validated_at,
        )

    def release_payment(
        self,
        *,
        payment_id: str,
        rail: str,
        idempotency_key: str,
        updated_at: datetime,
    ) -> tuple[MockRailOutcome, PaymentStatusResponse]:
        outcome_token = f"{payment_id}:{idempotency_key}".lower()

        if "ambiguous" in outcome_token or idempotency_key.endswith("77"):
            return (
                "ambiguous",
                PaymentStatusResponse(
                    payment_id=payment_id,
                    status=self._ambiguous_status,
                    rail=rail,  # type: ignore[arg-type]
                    updated_at=updated_at,
                    error_class="ambiguous_result",
                    explanation="The mock rail returned an ambiguous release outcome that needs reconciliation.",
                ),
            )

        if "reject" in outcome_token or idempotency_key.endswith("99"):
            return (
                "reject",
                PaymentStatusResponse(
                    payment_id=payment_id,
                    status="failed",
                    rail=rail,  # type: ignore[arg-type]
                    updated_at=updated_at,
                    error_class="state_conflict",
                    explanation="The mock rail rejected the release request.",
                ),
            )

        return (
            "success",
            PaymentStatusResponse(
                payment_id=payment_id,
                status="settlement_pending",
                rail=rail,  # type: ignore[arg-type]
                updated_at=updated_at,
                explanation="The mock rail accepted the release request.",
            ),
        )
