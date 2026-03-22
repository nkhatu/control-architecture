import type {
  ControlSummary,
  DomesticPaymentIntakeResponse,
  DomesticPaymentResumeResponse,
  TaskDetailView,
  VersionSnapshot,
} from "./types";

interface ApiErrorPayload {
  detail?: string | { message?: string; error_class?: string };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const fallback = `${response.status} ${response.statusText}`;

    try {
      const payload = (await response.json()) as ApiErrorPayload;
      if (typeof payload.detail === "string") {
        throw new Error(payload.detail);
      }
      if (payload.detail?.message) {
        throw new Error(payload.detail.message);
      }
    } catch (error) {
      if (error instanceof Error && error.message !== "") {
        throw error;
      }
    }

    throw new Error(fallback);
  }

  return (await response.json()) as T;
}

export interface CreateTaskInput {
  customer_id: string;
  source_account_id: string;
  beneficiary_id: string;
  amount_usd: number;
  rail: string;
  requested_execution_date: string;
  initiated_by: string;
  memo?: string;
  trace_id?: string;
}

export interface ResumeTaskInput {
  approved_by: string;
  approval_note?: string;
  release_mode: "dry_run" | "execute";
  idempotency_key?: string;
}

export function getControlSummary(): Promise<ControlSummary> {
  return request<ControlSummary>("/api/control-plane/controls/summary");
}

export function getControlVersions(): Promise<VersionSnapshot> {
  return request<VersionSnapshot>("/api/control-plane/versions/current");
}

export function createTask(payload: CreateTaskInput): Promise<DomesticPaymentIntakeResponse> {
  return request<DomesticPaymentIntakeResponse>("/api/orchestrator/tasks/domestic-payments", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getTask(taskId: string): Promise<TaskDetailView> {
  return request<TaskDetailView>(`/api/orchestrator/tasks/${taskId}`);
}

export function resumeTask(taskId: string, payload: ResumeTaskInput): Promise<DomesticPaymentResumeResponse> {
  return request<DomesticPaymentResumeResponse>(`/api/orchestrator/tasks/${taskId}/resume`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
