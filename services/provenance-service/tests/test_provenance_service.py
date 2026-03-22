from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from shared_contracts.tasks import (
    ApprovalRequestArtifactContent,
    ApprovalRoutingRequestEnvelope,
    ApprovalRoutingResultEnvelope,
    DelegationContext,
    MessageSource,
    MessageTarget,
    TrustContext,
    TraceContext,
)

from provenance_service.config import AppSettings
from provenance_service.main import create_app


def test_provenance_service_records_history_artifacts_and_delegations(tmp_path) -> None:
    database_path = tmp_path / "provenance.db"
    settings = AppSettings(
        auto_create_schema=True,
        database_url=f"sqlite+pysqlite:///{database_path}",
        control_plane_config_path="config/control-plane/default.yaml",
    )
    now = datetime.now(timezone.utc)
    request_envelope = ApprovalRoutingRequestEnvelope(
        message_id="msg_001",
        correlation_id="corr_001",
        task_id="task_001",
        workflow_id="wf_task_001",
        timestamp=now,
        source=MessageSource(principal_type="agent", principal_id="agent.payment_orchestrator"),
        delegation=DelegationContext(
            delegated_by="agent.payment_orchestrator",
            delegation_chain=["agent.payment_orchestrator", "agent.approval_router"],
            scope=["payment.submit_for_approval"],
            expires_at=now + timedelta(minutes=15),
        ),
        target=MessageTarget(target_type="agent", target_id="agent.approval_router", version="v1"),
        trust=TrustContext(classification="bounded_delegation", human_approval_required=True),
        payload={
            "delegated_action": "approval_routing",
            "approval_profile": "single_approval",
            "task_summary": {
                "task_id": "task_001",
                "payment_id": "pay_001",
                "customer_id": "cust_001",
                "amount_usd": 2500,
                "rail": "ach",
            },
        },
        trace=TraceContext(trace_id="tr_001", span_id="span_001"),
    )
    response_envelope = ApprovalRoutingResultEnvelope(
        message_id="msg_002",
        correlation_id="corr_001",
        task_id="task_001",
        workflow_id="wf_task_001",
        timestamp=now,
        source=MessageSource(principal_type="agent", principal_id="agent.approval_router"),
        delegation=request_envelope.delegation,
        target=MessageTarget(target_type="agent", target_id="agent.payment_orchestrator", version="v1"),
        trust=request_envelope.trust,
        payload=ApprovalRequestArtifactContent(
            approval_request_id="apr_001",
            approval_status="pending",
            approval_profile="single_approval",
            required_approvals=1,
            route="human_approval_queue",
        ),
        trace=TraceContext(trace_id="tr_001", span_id="span_002"),
    )

    with TestClient(create_app(settings)) as client:
        provenance_response = client.post(
            "/tasks/task_001/provenance",
            json={
                "initiated_by": "user.neil",
                "trace_id": "tr_001",
            },
        )
        assert provenance_response.status_code == 201

        transition_response = client.post(
            "/tasks/task_001/state-transitions",
            json={
                "source_event_id": "evt_001",
                "from_status": None,
                "to_status": "received",
                "changed_by": "user.neil",
                "reason": "task created",
            },
        )
        assert transition_response.status_code == 201

        duplicate_transition = client.post(
            "/tasks/task_001/state-transitions",
            json={
                "source_event_id": "evt_001",
                "from_status": None,
                "to_status": "received",
                "changed_by": "user.neil",
                "reason": "task created",
            },
        )
        assert duplicate_transition.status_code == 201

        artifact_response = client.post(
            "/tasks/task_001/artifacts",
            json={
                "artifact_type": "beneficiary_validation_result",
                "content": {
                    "beneficiary_id": "ben_001",
                    "status": "validated",
                    "validated_at": now.isoformat(),
                },
                "created_by": "agent.compliance_screening",
            },
        )
        assert artifact_response.status_code == 201

        delegation_response = client.post(
            "/tasks/task_001/delegations",
            json={
                "workflow_id": "wf_task_001",
                "parent_agent_id": "agent.payment_orchestrator",
                "delegated_agent_id": "agent.approval_router",
                "delegated_action": "approval_routing",
                "status": "pending",
                "request_envelope": request_envelope.model_dump(mode="json"),
            },
        )
        assert delegation_response.status_code == 201
        delegation_id = delegation_response.json()["delegation_id"]

        update_response = client.patch(
            f"/delegations/{delegation_id}",
            json={
                "status": "completed",
                "updated_by": "agent.approval_router",
                "response_envelope": response_envelope.model_dump(mode="json"),
            },
        )
        assert update_response.status_code == 200

        records_response = client.get("/tasks/task_001/records")
        assert records_response.status_code == 200
        body = records_response.json()
        assert body["provenance"]["trace_id"] == "tr_001"
        assert len(body["state_history"]) == 1
        assert len(body["artifacts"]) == 1
        assert len(body["delegations"]) == 1
        assert body["delegations"][0]["status"] == "completed"
