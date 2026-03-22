from __future__ import annotations

from .context_client import ContextOutboxClient
from .provenance_client import ProvenanceProjectionClient
from .schemas import DispatchFailure, DispatchResponse, OutboxEvent


EVENT_TYPE_TASK_CREATED = "task.lifecycle.created.v1"
EVENT_TYPE_TASK_STATE_CHANGED = "task.lifecycle.state_changed.v1"


class EventConsumerService:
    def __init__(
        self,
        *,
        context_outbox_client: ContextOutboxClient,
        provenance_client: ProvenanceProjectionClient,
        app_name: str = "event-consumer",
    ) -> None:
        self._context_outbox_client = context_outbox_client
        self._provenance_client = provenance_client
        self._app_name = app_name

    def metadata(self, context_memory_service_base_url: str, provenance_service_base_url: str, app_env: str) -> dict[str, object]:
        return {
            "service": self._app_name,
            "environment": app_env,
            "context_memory_service_base_url": context_memory_service_base_url,
            "provenance_service_base_url": provenance_service_base_url,
            "supported_event_types": [EVENT_TYPE_TASK_CREATED, EVENT_TYPE_TASK_STATE_CHANGED],
        }

    def process_once(self, *, limit: int, lease_seconds: int) -> DispatchResponse:
        claimed = [
            OutboxEvent.model_validate(item)
            for item in self._context_outbox_client.claim_events(limit=limit, lease_seconds=lease_seconds)
        ]

        processed_count = 0
        failures: list[DispatchFailure] = []

        for event in claimed:
            try:
                self._project_event(event)
                self._context_outbox_client.complete_event(event.event_id)
                processed_count += 1
            except Exception as exc:
                message = str(exc)
                self._context_outbox_client.fail_event(event.event_id, error_message=message)
                failures.append(
                    DispatchFailure(
                        event_id=event.event_id,
                        event_type=event.event_type,
                        error_message=message,
                    )
                )

        return DispatchResponse(
            claimed_count=len(claimed),
            processed_count=processed_count,
            failed_count=len(failures),
            failures=failures,
        )

    def _project_event(self, event: OutboxEvent) -> None:
        payload = event.payload
        task_id = payload["task_id"]

        if event.event_type == EVENT_TYPE_TASK_CREATED:
            self._provenance_client.ensure_task_provenance(task_id, payload["provenance"])
            self._provenance_client.append_state_transition(
                task_id,
                {
                    **payload["transition"],
                    "source_event_id": event.event_id,
                },
            )
            return

        if event.event_type == EVENT_TYPE_TASK_STATE_CHANGED:
            self._provenance_client.append_state_transition(
                task_id,
                {
                    **payload["transition"],
                    "source_event_id": event.event_id,
                },
            )
            return

        raise RuntimeError(f"Unsupported outbox event type: {event.event_type}")
