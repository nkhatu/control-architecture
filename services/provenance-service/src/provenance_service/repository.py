from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import Artifact, DelegatedWorkItem, TaskProvenance, TaskStateTransition
from .schemas import (
    ArtifactCreateRequest,
    DelegatedWorkCreateRequest,
    DelegatedWorkUpdateRequest,
    ProvenanceRecordCreateRequest,
    TaskStateTransitionCreateRequest,
)


class ProvenanceRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_task_provenance(self, task_id: str, payload: ProvenanceRecordCreateRequest) -> TaskProvenance:
        record = TaskProvenance(
            task_id=task_id,
            initiated_by=payload.initiated_by,
            last_updated_by=payload.last_updated_by or payload.initiated_by,
            policy_context_id=payload.policy_context_id,
            trace_id=payload.trace_id,
        )
        self.session.add(record)
        self.session.commit()
        return self.get_task_provenance(task_id)

    def get_task_provenance(self, task_id: str) -> TaskProvenance | None:
        statement = (
            select(TaskProvenance)
            .options(
                selectinload(TaskProvenance.state_history),
                selectinload(TaskProvenance.artifacts),
                selectinload(TaskProvenance.delegations),
            )
            .where(TaskProvenance.task_id == task_id)
        )
        return self.session.scalars(statement).unique().one_or_none()

    def add_state_transition(self, task_id: str, payload: TaskStateTransitionCreateRequest) -> TaskStateTransition | None:
        task = self.get_task_provenance(task_id)
        if task is None:
            return None

        transition = TaskStateTransition(
            task_id=task_id,
            from_status=payload.from_status,
            to_status=payload.to_status,
            changed_by=payload.changed_by,
            reason=payload.reason,
        )
        task.last_updated_by = payload.changed_by

        self.session.add(task)
        self.session.add(transition)
        self.session.commit()
        self.session.refresh(transition)
        return transition

    def add_artifact(self, task_id: str, payload: ArtifactCreateRequest) -> Artifact | None:
        task = self.get_task_provenance(task_id)
        if task is None:
            return None

        artifact = Artifact(
            task_id=task_id,
            artifact_type=payload.artifact_type,
            artifact_ref=payload.artifact_ref,
            content=payload.content,
            trust_level=payload.trust_level,
            created_by=payload.created_by,
        )
        task.last_updated_by = payload.created_by

        self.session.add(task)
        self.session.add(artifact)
        self.session.commit()
        self.session.refresh(artifact)
        return artifact

    def create_delegation(self, task_id: str, payload: DelegatedWorkCreateRequest) -> DelegatedWorkItem | None:
        task = self.get_task_provenance(task_id)
        if task is None:
            return None

        delegation = DelegatedWorkItem(
            delegation_id=f"dlg_{uuid4().hex[:12]}",
            task_id=task_id,
            workflow_id=payload.workflow_id,
            parent_agent_id=payload.parent_agent_id,
            delegated_agent_id=payload.delegated_agent_id,
            delegated_action=payload.delegated_action,
            capability_id=payload.capability_id,
            status=payload.status,
            request_envelope=payload.request_envelope,
            response_envelope=payload.response_envelope,
        )
        task.last_updated_by = payload.parent_agent_id

        self.session.add(task)
        self.session.add(delegation)
        self.session.commit()
        self.session.refresh(delegation)
        return delegation

    def get_delegation(self, delegation_id: str) -> DelegatedWorkItem | None:
        statement = select(DelegatedWorkItem).where(DelegatedWorkItem.delegation_id == delegation_id)
        return self.session.scalars(statement).one_or_none()

    def update_delegation(self, delegation_id: str, payload: DelegatedWorkUpdateRequest) -> DelegatedWorkItem | None:
        delegation = self.get_delegation(delegation_id)
        if delegation is None:
            return None

        delegation.status = payload.status
        if payload.response_envelope is not None:
            delegation.response_envelope = payload.response_envelope

        task = self.get_task_provenance(delegation.task_id)
        if task is not None:
            task.last_updated_by = payload.updated_by
            self.session.add(task)

        self.session.add(delegation)
        self.session.commit()
        return self.get_delegation(delegation_id)
