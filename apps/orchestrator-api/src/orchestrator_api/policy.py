from __future__ import annotations

from .schemas import DomesticPaymentIntakeRequest, PolicyDecisionResponse


def evaluate_intake_policy(
    request: DomesticPaymentIntakeRequest,
    control_plane_config: dict,
) -> PolicyDecisionResponse:
    environment = control_plane_config.get("environment", {})
    control_plane = control_plane_config.get("control_plane", {})

    allowed_rails = set(environment.get("rail_scope", []))
    default_mode = environment.get("default_mode", "dry_run")
    dual_approval_threshold = control_plane.get("dual_approval_threshold_usd", 0)
    high_risk_threshold = control_plane.get("high_risk_escalation_threshold_usd", 0)

    if request.rail not in allowed_rails:
        return PolicyDecisionResponse(
            decision="deny",
            reason=f"Rail {request.rail} is outside the configured PoC rail scope.",
            approval_profile="unsupported",
            execution_mode=default_mode,
            recommended_next_capability="",
            requires_manual_escalation=False,
        )

    approval_profile = "dual_approval" if request.amount_usd >= dual_approval_threshold else "single_approval"

    if default_mode == "read_only":
        return PolicyDecisionResponse(
            decision="simulate",
            reason="The environment is running in read-only mode, so intake is simulated only.",
            approval_profile=approval_profile,
            execution_mode=default_mode,
            recommended_next_capability="domestic_payment.validate_beneficiary_account",
            requires_manual_escalation=False,
        )

    if request.amount_usd >= high_risk_threshold:
        return PolicyDecisionResponse(
            decision="escalate",
            reason="The payment amount exceeds the high-risk escalation threshold.",
            approval_profile=approval_profile,
            execution_mode=default_mode,
            recommended_next_capability="domestic_payment.validate_beneficiary_account",
            requires_manual_escalation=True,
        )

    return PolicyDecisionResponse(
        decision="allow",
        reason="The payment is within the configured intake thresholds.",
        approval_profile=approval_profile,
        execution_mode=default_mode,
        recommended_next_capability="domestic_payment.validate_beneficiary_account",
        requires_manual_escalation=False,
    )
