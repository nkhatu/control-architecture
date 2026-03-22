from fastapi.testclient import TestClient

from policy_service.config import AppSettings
from policy_service.main import create_app


def build_test_client() -> TestClient:
    settings = AppSettings(control_plane_config_path="config/control-plane/default.yaml")
    return TestClient(create_app(settings))


def test_intake_decision_allows_supported_rail() -> None:
    with build_test_client() as client:
        response = client.post(
            "/decisions/intake",
            json={
                "customer_id": "cust_001",
                "rail": "ach",
                "amount_usd": 2500,
                "principal": {"actor_id": "user.neil", "scopes": ["payment.validate"]},
            },
        )

    assert response.status_code == 200
    assert response.json()["decision"] == "allow"
    assert response.json()["recommended_next_capability"] == "domestic_payment.validate_beneficiary_account"


def test_release_decision_denies_missing_scope() -> None:
    with build_test_client() as client:
        response = client.post(
            "/decisions/release",
            json={
                "payment": {
                    "task_id": "task_001",
                    "payment_id": "pay_001",
                    "amount_usd": 2500,
                    "rail": "ach",
                    "status": "awaiting_approval",
                    "approval_status": "pending",
                    "beneficiary_status": "approved",
                    "task_metadata": {},
                },
                "principal": {"actor_id": "user.ops_approver", "scopes": []},
                "request": {
                    "approved_by": "user.ops_approver",
                    "approval_outcome": "approved",
                    "idempotency_key": "release-test-001",
                    "release_mode": "execute",
                },
            },
        )

    assert response.status_code == 200
    assert response.json()["decision"] == "deny"
    assert "missing required scope" in response.json()["reason"]
