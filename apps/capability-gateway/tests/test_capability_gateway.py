from fastapi.testclient import TestClient

from capability_gateway.config import AppSettings
from capability_gateway.main import create_app


def build_test_client() -> TestClient:
    settings = AppSettings(
        control_plane_config_path="config/control-plane/default.yaml",
        capability_registry_path="config/registry/capabilities.yaml",
    )
    return TestClient(create_app(settings))


def create_instruction(client: TestClient, beneficiary_id: str = "ben_001") -> dict:
    response = client.post(
        "/domestic-payments/instructions",
        json={
            "customer_id": "cust_123",
            "source_account_id": "acct_001",
            "beneficiary_id": beneficiary_id,
            "amount_usd": 2500,
            "rail": "ach",
            "requested_execution_date": "2026-03-24",
            "initiated_by": "agent.payment_orchestrator",
            "trace_id": "tr_gateway_001",
        },
    )
    response.raise_for_status()
    return response.json()


def test_health_and_metadata_expose_gateway_shape() -> None:
    with build_test_client() as client:
        health_response = client.get("/health")
        metadata_response = client.get("/metadata")

    assert health_response.status_code == 200
    assert health_response.json()["service"] == "capability-gateway"
    assert metadata_response.status_code == 200
    assert metadata_response.json()["mode"] == "dry_run"
    assert any(
        item["id"] == "domestic_payment.release_approved_payment"
        for item in metadata_response.json()["capabilities"]
    )


def test_instruction_and_beneficiary_validation_update_task_state() -> None:
    with build_test_client() as client:
        instruction = create_instruction(client)
        validation_response = client.post(
            "/domestic-payments/beneficiaries/validate",
            json={
                "task_id": instruction["task"]["task_id"],
                "payment_id": instruction["task"]["payment_id"],
                "customer_id": instruction["task"]["customer_id"],
                "beneficiary_id": "ben_001",
                "amount_usd": instruction["task"]["amount_usd"],
                "rail": instruction["task"]["rail"],
                "trace_id": "tr_gateway_validate_001",
            },
        )
        status_response = client.get(f"/domestic-payments/{instruction['task']['payment_id']}/status")

    assert validation_response.status_code == 200
    validation_body = validation_response.json()
    assert validation_body["result"]["status"] == "validated"
    assert validation_body["task"]["status"] == "validated"
    assert validation_body["task"]["beneficiary_status"] == "approved"
    assert status_response.status_code == 200
    assert status_response.json()["payment_status"]["status"] == "validated"


def test_release_returns_success_and_replays_idempotently() -> None:
    with build_test_client() as client:
        instruction = create_instruction(client)
        release_payload = {
            "task_id": instruction["task"]["task_id"],
            "payment_id": instruction["task"]["payment_id"],
            "idempotency_key": "idem-success-1234",
            "released_by": "user.ops_approver",
            "release_mode": "execute",
        }

        first_release = client.post("/domestic-payments/release", json=release_payload)
        second_release = client.post("/domestic-payments/release", json=release_payload)

    assert first_release.status_code == 200
    first_body = first_release.json()
    assert first_body["mock_rail_outcome"] == "success"
    assert first_body["result"]["status"] == "settlement_pending"
    assert first_body["idempotency_replayed"] is False

    assert second_release.status_code == 200
    second_body = second_release.json()
    assert second_body["mock_rail_outcome"] == "success"
    assert second_body["idempotency_replayed"] is True


def test_release_surfaces_ambiguous_outcome_in_status() -> None:
    with build_test_client() as client:
        instruction = create_instruction(client)
        release_response = client.post(
            "/domestic-payments/release",
            json={
                "task_id": instruction["task"]["task_id"],
                "payment_id": instruction["task"]["payment_id"],
                "idempotency_key": "idem-ambiguous-4477",
                "released_by": "user.ops_approver",
                "release_mode": "execute",
            },
        )
        status_response = client.get(f"/domestic-payments/{instruction['task']['payment_id']}/status")

    assert release_response.status_code == 200
    assert release_response.json()["mock_rail_outcome"] == "ambiguous"
    assert release_response.json()["result"]["status"] == "pending_reconcile"
    assert status_response.status_code == 200
    assert status_response.json()["payment_status"]["status"] == "pending_reconcile"


def test_reused_idempotency_key_with_different_payload_conflicts() -> None:
    with build_test_client() as client:
        first_instruction = create_instruction(client)
        second_instruction = create_instruction(client, beneficiary_id="ben_777")

        first_release = client.post(
            "/domestic-payments/release",
            json={
                "task_id": first_instruction["task"]["task_id"],
                "payment_id": first_instruction["task"]["payment_id"],
                "idempotency_key": "idem-shared-1234",
                "released_by": "user.ops_approver",
                "release_mode": "execute",
            },
        )
        conflicting_release = client.post(
            "/domestic-payments/release",
            json={
                "task_id": second_instruction["task"]["task_id"],
                "payment_id": second_instruction["task"]["payment_id"],
                "idempotency_key": "idem-shared-1234",
                "released_by": "user.ops_approver",
                "release_mode": "execute",
            },
        )

    assert first_release.status_code == 200
    assert conflicting_release.status_code == 409
    assert conflicting_release.json()["detail"]["error_class"] == "duplicate_request"


def test_instruction_rejects_unsupported_rail() -> None:
    with build_test_client() as client:
        response = client.post(
            "/domestic-payments/instructions",
            json={
                "customer_id": "cust_123",
                "source_account_id": "acct_001",
                "beneficiary_id": "ben_001",
                "amount_usd": 2500,
                "rail": "rtp",
                "requested_execution_date": "2026-03-24",
            },
        )

    assert response.status_code == 403
    assert response.json()["detail"]["error_class"] == "policy_denied"
