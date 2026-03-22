export type TaskStatus =
  | "received"
  | "validated"
  | "awaiting_approval"
  | "approved"
  | "released"
  | "settlement_pending"
  | "settled"
  | "failed"
  | "cancelled"
  | "pending_reconcile"
  | "exception";

export type ApprovalStatus = "not_required" | "pending" | "approved" | "denied" | "expired";
export type BeneficiaryStatus = "unknown" | "approved" | "rejected" | "needs_review";

export interface ControlSummary {
  environment_name: string;
  region: string | null;
  default_mode: string;
  rail_scope: string[];
  policy_engine: string;
  kill_switch_enabled: boolean;
  dual_approval_threshold_usd: number;
  high_risk_escalation_threshold_usd: number;
  ambiguous_response_action: string;
  release_scope: string | null;
  release_requires_human_approval: boolean;
  release_idempotency_required: boolean;
  release_dry_run_supported: boolean;
}

export interface VersionDocument {
  name: string;
  source_path: string;
  sha256: string;
  last_modified_at: string;
}

export interface VersionSnapshot {
  snapshot_sha256: string;
  documents: VersionDocument[];
}

export interface TaskProvenance {
  task_id: string;
  initiated_by: string | null;
  last_updated_by: string | null;
  policy_context_id: string | null;
  trace_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface TaskStateHistoryEntry {
  id: number;
  source_event_id?: string | null;
  from_status?: string | null;
  to_status: string;
  changed_by: string;
  reason?: string | null;
  created_at: string;
}

export interface ArtifactView {
  id: number;
  artifact_type: string;
  artifact_ref?: string | null;
  content: Record<string, unknown>;
  trust_level: string;
  created_by: string;
  created_at: string;
}

export interface DelegatedWorkView {
  delegation_id: string;
  workflow_id: string;
  parent_agent_id: string;
  delegated_agent_id: string;
  delegated_action: string;
  capability_id?: string | null;
  status: string;
  request_envelope: Record<string, unknown>;
  response_envelope?: Record<string, unknown> | null;
  created_at: string;
  updated_at?: string | null;
}

export interface TaskDetailView {
  task_id: string;
  payment_id: string;
  customer_id: string;
  rail: string;
  amount_usd: number;
  status: TaskStatus;
  beneficiary_status: BeneficiaryStatus;
  approval_status: ApprovalStatus;
  task_metadata: Record<string, unknown>;
  created_at: string;
  updated_at?: string | null;
  provenance: TaskProvenance;
  state_history: TaskStateHistoryEntry[];
  artifacts: ArtifactView[];
  delegations: DelegatedWorkView[];
}

export interface PolicyDecision {
  decision: "allow" | "deny" | "escalate" | "simulate";
  reason: string;
  approval_profile: string;
  execution_mode: string;
  recommended_next_capability: string;
  requires_manual_escalation: boolean;
}

export interface WorkflowProgress {
  workflow_id: string;
  workflow_state: string;
  next_action: string;
  last_capability?: string | null;
}

export interface DomesticPaymentIntakeResponse {
  task: TaskDetailView;
  policy_decision: PolicyDecision;
  available_capabilities: string[];
  selected_agents: string[];
  workflow: WorkflowProgress;
}

export interface DomesticPaymentResumeResponse {
  task: TaskDetailView;
  workflow: WorkflowProgress;
  release_result?: Record<string, unknown> | null;
}

export interface RecentTaskRecord {
  taskId: string;
  paymentId: string;
  customerId: string;
  amountUsd: number;
  rail: string;
  status: TaskStatus;
  updatedAt: string;
}
