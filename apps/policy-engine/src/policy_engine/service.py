from __future__ import annotations

from typing import Any

from .schemas import IntakeDecisionRequest, PolicyDecisionResponse, ReleaseDecisionRequest


INTAKE_CAPABILITY_ID = "domestic_payment.validate_beneficiary_account"
RELEASE_CAPABILITY_ID = "domestic_payment.release_approved_payment"


class PolicyEngine:
    def __init__(self, control_plane_config: dict[str, Any], app_name: str = "policy-engine") -> None:
        self._control_plane_config = control_plane_config
        self._app_name = app_name

    def metadata(self, app_env: str) -> dict[str, object]:
        control_plane = self._control_plane_config.get("control_plane", {})
        return {
            "service": self._app_name,
            "environment": app_env,
            "policy_engine": control_plane.get("policy_engine", "unknown"),
            "supported_actions": [
                "domestic_payment.intake",
                "domestic_payment.release_approved_payment",
            ],
        }

    def evaluate_intake(self, payload: IntakeDecisionRequest) -> PolicyDecisionResponse:
        environment = self._control_plane_config.get("environment", {})
        control_plane = self._control_plane_config.get("control_plane", {})

        allowed_rails = set(environment.get("rail_scope", []))
        default_mode = environment.get("default_mode", "dry_run")
        dual_approval_threshold = control_plane.get("dual_approval_threshold_usd", 0)
        high_risk_threshold = control_plane.get("high_risk_escalation_threshold_usd", 0)
        approval_profile = "dual_approval" if payload.amount_usd >= dual_approval_threshold else "single_approval"

        if payload.rail not in allowed_rails:
            return PolicyDecisionResponse(
                decision="deny",
                reason=f"Rail {payload.rail} is outside the configured PoC rail scope.",
                approval_profile="unsupported",
                execution_mode=default_mode,
                recommended_next_capability="",
            )

        if default_mode == "read_only":
            return PolicyDecisionResponse(
                decision="simulate",
                reason="The environment is running in read-only mode, so intake is simulated only.",
                approval_profile=approval_profile,
                execution_mode=default_mode,
                recommended_next_capability=INTAKE_CAPABILITY_ID,
            )

        if payload.amount_usd >= high_risk_threshold:
            return PolicyDecisionResponse(
                decision="escalate",
                reason="The payment amount exceeds the high-risk escalation threshold.",
                approval_profile=approval_profile,
                execution_mode=default_mode,
                recommended_next_capability=INTAKE_CAPABILITY_ID,
                requires_manual_escalation=True,
            )

        return PolicyDecisionResponse(
            decision="allow",
            reason="The payment is within the configured intake thresholds.",
            approval_profile=approval_profile,
            execution_mode=default_mode,
            recommended_next_capability=INTAKE_CAPABILITY_ID,
        )

    def evaluate_release(self, payload: ReleaseDecisionRequest) -> PolicyDecisionResponse:
        environment = self._control_plane_config.get("environment", {})
        control_plane = self._control_plane_config.get("control_plane", {})
        capability_config = self._control_plane_config.get("capabilities", {}).get("release_approved_payment", {})

        allowed_rails = set(environment.get("rail_scope", []))
        default_mode = environment.get("default_mode", "dry_run")
        dual_approval_threshold = control_plane.get("dual_approval_threshold_usd", 0)
        high_risk_threshold = control_plane.get("high_risk_escalation_threshold_usd", 0)
        approval_profile = (
            payload.payment.task_metadata.get("policy_decision", {}).get("approval_profile")
            or ("dual_approval" if payload.payment.amount_usd >= dual_approval_threshold else "single_approval")
        )
        required_scope = capability_config.get("requires_scope", "release:domestic_payment")

        if payload.payment.rail not in allowed_rails:
            return PolicyDecisionResponse(
                decision="deny",
                reason=f"Rail {payload.payment.rail} is outside the configured PoC rail scope.",
                approval_profile=approval_profile,
                execution_mode=default_mode,
                recommended_next_capability=RELEASE_CAPABILITY_ID,
            )

        if default_mode == "read_only":
            return PolicyDecisionResponse(
                decision="simulate",
                reason="The environment is running in read-only mode, so release is simulated only.",
                approval_profile=approval_profile,
                execution_mode=default_mode,
                recommended_next_capability=RELEASE_CAPABILITY_ID,
            )

        if payload.request.release_mode == "dry_run" and not capability_config.get("dry_run_supported", False):
            return PolicyDecisionResponse(
                decision="deny",
                reason="The release capability does not support dry_run mode in this PoC configuration.",
                approval_profile=approval_profile,
                execution_mode=default_mode,
                recommended_next_capability=RELEASE_CAPABILITY_ID,
            )

        if payload.payment.status != "awaiting_approval":
            return PolicyDecisionResponse(
                decision="deny",
                reason=f"Task {payload.payment.task_id} is in state {payload.payment.status} and cannot be released.",
                approval_profile=approval_profile,
                execution_mode=default_mode,
                recommended_next_capability=RELEASE_CAPABILITY_ID,
            )

        if payload.payment.beneficiary_status != "approved":
            return PolicyDecisionResponse(
                decision="deny",
                reason="Beneficiary validation is not approved, so release is blocked.",
                approval_profile=approval_profile,
                execution_mode=default_mode,
                recommended_next_capability=RELEASE_CAPABILITY_ID,
            )

        if payload.request.approval_outcome != "approved":
            return PolicyDecisionResponse(
                decision="deny",
                reason="Release can only proceed after an approved human decision.",
                approval_profile=approval_profile,
                execution_mode=default_mode,
                recommended_next_capability=RELEASE_CAPABILITY_ID,
            )

        if not payload.request.idempotency_key:
            return PolicyDecisionResponse(
                decision="deny",
                reason="Release requires an idempotency key.",
                approval_profile=approval_profile,
                execution_mode=default_mode,
                recommended_next_capability=RELEASE_CAPABILITY_ID,
            )

        if required_scope not in payload.principal.scopes:
            return PolicyDecisionResponse(
                decision="deny",
                reason=f"Principal is missing required scope {required_scope}.",
                approval_profile=approval_profile,
                execution_mode=default_mode,
                recommended_next_capability=RELEASE_CAPABILITY_ID,
            )

        if payload.payment.amount_usd >= high_risk_threshold:
            return PolicyDecisionResponse(
                decision="escalate",
                reason="The payment amount exceeds the high-risk release escalation threshold.",
                approval_profile=approval_profile,
                execution_mode=default_mode,
                recommended_next_capability=RELEASE_CAPABILITY_ID,
                requires_manual_escalation=True,
            )

        return PolicyDecisionResponse(
            decision="allow",
            reason="Release satisfies the configured policy checks.",
            approval_profile=approval_profile,
            execution_mode=default_mode,
            recommended_next_capability=RELEASE_CAPABILITY_ID,
        )
