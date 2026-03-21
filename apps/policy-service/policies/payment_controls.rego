package payment.controls

default allow := false
default requires_escalation := false

allow if input.action == "validate_beneficiary_account"

allow if input.action == "request_payment_approval"

allow if {
  input.action == "release_approved_payment"
  input.payment.status == "approved"
  input.payment.beneficiary_status == "approved"
  input.request.idempotency_key != ""
  "release:domestic_payment" in input.principal.scopes
}

requires_escalation if {
  input.action == "release_approved_payment"
  input.payment.amount_usd >= data.control_plane.high_risk_escalation_threshold_usd
}
