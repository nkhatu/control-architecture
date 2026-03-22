import type { RecentTaskRecord, TaskDetailView } from "./types";

const RECENT_TASKS_KEY = "ops-console.recent-tasks";
const MAX_RECENT_TASKS = 18;

function isRecentTaskRecord(value: unknown): value is RecentTaskRecord {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const record = value as Record<string, unknown>;
  return (
    typeof record.taskId === "string" &&
    typeof record.paymentId === "string" &&
    typeof record.customerId === "string" &&
    typeof record.amountUsd === "number" &&
    typeof record.rail === "string" &&
    typeof record.status === "string" &&
    typeof record.updatedAt === "string"
  );
}

export function loadRecentTasks(): RecentTaskRecord[] {
  if (typeof window === "undefined") {
    return [];
  }

  const raw = window.localStorage.getItem(RECENT_TASKS_KEY);
  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw) as unknown[];
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter(isRecentTaskRecord);
  } catch {
    return [];
  }
}

export function persistRecentTasks(tasks: RecentTaskRecord[]): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(RECENT_TASKS_KEY, JSON.stringify(tasks.slice(0, MAX_RECENT_TASKS)));
}

export function upsertRecentTask(tasks: RecentTaskRecord[], task: TaskDetailView): RecentTaskRecord[] {
  const nextRecord: RecentTaskRecord = {
    taskId: task.task_id,
    paymentId: task.payment_id,
    customerId: task.customer_id,
    amountUsd: task.amount_usd,
    rail: task.rail,
    status: task.status,
    updatedAt: task.updated_at ?? task.created_at,
  };

  const remaining = tasks.filter((item) => item.taskId !== task.task_id);
  return [nextRecord, ...remaining].slice(0, MAX_RECENT_TASKS);
}
