import { FormEvent, useEffect, useState, type ReactNode } from "react";

import { createTask, getControlSummary, getControlVersions, getTask, resumeTask } from "./api";
import type {
  ControlSummary,
  RecentTaskRecord,
  TaskDetailView,
  TaskStatus,
  VersionSnapshot,
} from "./types";
import { loadRecentTasks, persistRecentTasks, upsertRecentTask } from "./storage";

interface CreateFormState {
  customer_id: string;
  source_account_id: string;
  beneficiary_id: string;
  amount_usd: string;
  rail: string;
  requested_execution_date: string;
  initiated_by: string;
  memo: string;
  trace_id: string;
}

interface ResumeFormState {
  approved_by: string;
  approval_note: string;
  release_mode: "dry_run" | "execute";
  idempotency_key: string;
}

type AppView = "overview" | "trust-graph" | "intake" | "approvals" | "explorer" | "exceptions";

interface TrustGraphMapping {
  id: string;
  label: string;
  targetView: AppView;
  targetLabel: string;
  top: string;
  left: string;
  description: string;
  detail: string;
}

const initialCreateForm: CreateFormState = {
  customer_id: "cust_123",
  source_account_id: "acct_001",
  beneficiary_id: "ben_001",
  amount_usd: "2500",
  rail: "ach",
  requested_execution_date: "2026-03-24",
  initiated_by: "user.ops_console",
  memo: "",
  trace_id: "",
};

const initialResumeForm: ResumeFormState = {
  approved_by: "user.ops_approver",
  approval_note: "Approved in ops console.",
  release_mode: "execute",
  idempotency_key: "",
};

const exceptionStatuses: TaskStatus[] = ["pending_reconcile", "exception", "failed"];

const trustGraphImage = `${import.meta.env.BASE_URL}trust-graph-agentic-domestic-money-movement.jpg`;

const trustGraphMappings: TrustGraphMapping[] = [
  {
    id: "human-initiator",
    label: "Human Initiator",
    targetView: "intake",
    targetLabel: "Create Payment",
    top: "23%",
    left: "10%",
    description: "Start the workflow where the trust graph starts: a human-initiated payment request.",
    detail: "Use the intake view to create a payment task before the controlled execution path begins.",
  },
  {
    id: "parent-agent",
    label: "Parent Agent",
    targetView: "approvals",
    targetLabel: "Approvals",
    top: "22%",
    left: "39%",
    description: "Review the parent-agent checkpoint where approval-backed release continues the workflow.",
    detail: "The approvals workbench is the closest operator-facing view to the parent-agent control handoff.",
  },
  {
    id: "context-memory",
    label: "Context Memory",
    targetView: "explorer",
    targetLabel: "Task Explorer",
    top: "50%",
    left: "25%",
    description: "Inspect the current task snapshot and operational state owned by the context boundary.",
    detail: "The task explorer is where the current merged state becomes visible to the operator.",
  },
  {
    id: "provenance-plane",
    label: "Provenance Plane",
    targetView: "explorer",
    targetLabel: "Task Explorer",
    top: "50%",
    left: "41%",
    description: "Move into the provenance-heavy view for artifacts, state transitions, and delegated records.",
    detail: "The explorer is where evidence, lineage, and approval traces are easiest to inspect.",
  },
  {
    id: "control-plane",
    label: "Control Plane",
    targetView: "overview",
    targetLabel: "Overview",
    top: "50%",
    left: "57%",
    description: "Jump to the control summary that anchors policy and runtime guardrails.",
    detail: "Overview is the operator-facing surface for the control-plane snapshot and queue posture.",
  },
  {
    id: "delegated-agents",
    label: "Delegated Agents",
    targetView: "exceptions",
    targetLabel: "Exceptions",
    top: "26%",
    left: "79%",
    description: "Review delegated or exception-heavy work where compliance and approval routing can branch.",
    detail: "Exception review is the cleanest place to inspect delegated work that did not remain routine.",
  },
  {
    id: "capability-surface",
    label: "Capability Surface",
    targetView: "approvals",
    targetLabel: "Approvals",
    top: "50%",
    left: "69%",
    description: "Navigate to the stage where approved work is released through the capability surface.",
    detail: "Approval-backed release is the closest operator action to a controlled capability invocation.",
  },
  {
    id: "banking-systems",
    label: "Banking Systems",
    targetView: "exceptions",
    targetLabel: "Exceptions",
    top: "50%",
    left: "91%",
    description: "Focus on downstream ambiguity, reconciliation, and failure handling after invocation.",
    detail: "The exceptions view is where downstream bank-facing outcomes are easiest to triage.",
  },
];

const navigation: Array<{ view: AppView; label: string }> = [
  { view: "overview", label: "Overview" },
  { view: "trust-graph", label: "Trust Graph" },
  { view: "intake", label: "Create Payment" },
  { view: "approvals", label: "Approvals" },
  { view: "explorer", label: "Task Explorer" },
  { view: "exceptions", label: "Exceptions" },
];

export function App() {
  const [activeView, setActiveView] = useState<AppView>(() => getInitialView());
  const [controlSummary, setControlSummary] = useState<ControlSummary | null>(null);
  const [controlVersions, setControlVersions] = useState<VersionSnapshot | null>(null);
  const [controlError, setControlError] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState<CreateFormState>(initialCreateForm);
  const [resumeForm, setResumeForm] = useState<ResumeFormState>(initialResumeForm);
  const [createError, setCreateError] = useState<string | null>(null);
  const [resumeError, setResumeError] = useState<string | null>(null);
  const [taskError, setTaskError] = useState<string | null>(null);
  const [taskLookup, setTaskLookup] = useState<string>("");
  const [recentTasks, setRecentTasks] = useState<RecentTaskRecord[]>(() => loadRecentTasks());
  const [selectedTask, setSelectedTask] = useState<TaskDetailView | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string>("");
  const [isLoadingControl, setIsLoadingControl] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [isFetchingTask, setIsFetchingTask] = useState(false);
  const [isResuming, setIsResuming] = useState(false);

  useEffect(() => {
    persistRecentTasks(recentTasks);
  }, [recentTasks]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    const syncFromHash = () => {
      const next = parseView(window.location.hash.replace("#", ""));
      if (next) {
        setActiveView(next);
      }
    };

    window.addEventListener("hashchange", syncFromHash);
    return () => window.removeEventListener("hashchange", syncFromHash);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const nextHash = `#${activeView}`;
    if (window.location.hash !== nextHash) {
      window.history.replaceState(null, "", nextHash);
    }
  }, [activeView]);

  useEffect(() => {
    async function loadControlPlane() {
      setIsLoadingControl(true);
      setControlError(null);

      try {
        const [summary, versions] = await Promise.all([getControlSummary(), getControlVersions()]);
        setControlSummary(summary);
        setControlVersions(versions);
      } catch (error) {
        setControlError(toMessage(error));
      } finally {
        setIsLoadingControl(false);
      }
    }

    void loadControlPlane();
  }, []);

  useEffect(() => {
    if (selectedTaskId === "") {
      return;
    }

    void loadTask(selectedTaskId);
  }, [selectedTaskId]);

  async function loadTask(taskId: string) {
    setIsFetchingTask(true);
    setTaskError(null);

    try {
      const task = await getTask(taskId);
      setSelectedTask(task);
      setTaskLookup(task.task_id);
      setRecentTasks((current) => upsertRecentTask(current, task));
      setResumeForm((current) => ({
        ...current,
        idempotency_key: current.idempotency_key || buildIdempotencyKey(task.task_id),
      }));
    } catch (error) {
      setTaskError(toMessage(error));
    } finally {
      setIsFetchingTask(false);
    }
  }

  async function handleCreateTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsCreating(true);
    setCreateError(null);
    setResumeError(null);
    setTaskError(null);

    try {
      const response = await createTask({
        customer_id: createForm.customer_id,
        source_account_id: createForm.source_account_id,
        beneficiary_id: createForm.beneficiary_id,
        amount_usd: Number(createForm.amount_usd),
        rail: createForm.rail,
        requested_execution_date: createForm.requested_execution_date,
        initiated_by: createForm.initiated_by,
        memo: createForm.memo || undefined,
        trace_id: createForm.trace_id || undefined,
      });

      setSelectedTask(response.task);
      setSelectedTaskId(response.task.task_id);
      setTaskLookup(response.task.task_id);
      setRecentTasks((current) => upsertRecentTask(current, response.task));
      setResumeForm((current) => ({
        ...current,
        idempotency_key: buildIdempotencyKey(response.task.task_id),
      }));
      setActiveView(viewForTask(response.task.status));
    } catch (error) {
      setCreateError(toMessage(error));
    } finally {
      setIsCreating(false);
    }
  }

  async function handleLoadTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = taskLookup.trim();
    if (trimmed === "") {
      return;
    }
    setActiveView("explorer");
    setSelectedTaskId(trimmed);
  }

  async function handleResumeTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedTask === null) {
      return;
    }

    setIsResuming(true);
    setResumeError(null);

    try {
      const response = await resumeTask(selectedTask.task_id, {
        approved_by: resumeForm.approved_by,
        approval_note: resumeForm.approval_note || undefined,
        release_mode: resumeForm.release_mode,
        idempotency_key: resumeForm.idempotency_key || buildIdempotencyKey(selectedTask.task_id),
      });

      setSelectedTask(response.task);
      setRecentTasks((current) => upsertRecentTask(current, response.task));
      setResumeForm((current) => ({
        ...current,
        idempotency_key: buildIdempotencyKey(response.task.task_id),
      }));
      setActiveView(viewForTask(response.task.status));
    } catch (error) {
      setResumeError(toMessage(error));
    } finally {
      setIsResuming(false);
    }
  }

  function updateCreateForm<K extends keyof CreateFormState>(field: K, value: CreateFormState[K]) {
    setCreateForm((current) => ({ ...current, [field]: value }));
  }

  function updateResumeForm<K extends keyof ResumeFormState>(field: K, value: ResumeFormState[K]) {
    setResumeForm((current) => ({ ...current, [field]: value }));
  }

  function selectTask(taskId: string, view: AppView) {
    setActiveView(view);
    setSelectedTaskId(taskId);
  }

  const approvalQueue = recentTasks.filter((task) => task.status === "awaiting_approval");
  const exceptionQueue = recentTasks.filter((task) => exceptionStatuses.includes(task.status));
  const latestTask = recentTasks[0] ?? null;

  return (
    <div className="page-shell">
      <div className="page-noise" />

      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Ops Console</p>
          <h1>Approvals stay human. Control stays visible.</h1>
          <p className="hero-text">
            The console now uses a top-menu flow instead of one long workspace. Move between the trust graph,
            control overview, intake, approvals, task inspection, and exception review without losing the current
            operator context.
          </p>
        </div>

        <div className="hero-card">
          <div className="hero-card-header">
            <span className="chip chip-quiet">Control Snapshot</span>
            {controlVersions ? <span className="hash-tag">{shortHash(controlVersions.snapshot_sha256)}</span> : null}
          </div>

          {isLoadingControl ? <p className="muted">Loading control-plane summary…</p> : null}
          {controlError ? <p className="error-text">{controlError}</p> : null}

          {controlSummary ? (
            <div className="summary-grid">
              <SummaryItem label="Environment" value={controlSummary.environment_name} />
              <SummaryItem label="Mode" value={controlSummary.default_mode} />
              <SummaryItem label="Kill Switch" value={controlSummary.kill_switch_enabled ? "Enabled" : "Disabled"} />
              <SummaryItem label="Approval Threshold" value={formatCurrency(controlSummary.dual_approval_threshold_usd)} />
              <SummaryItem label="High-Risk Threshold" value={formatCurrency(controlSummary.high_risk_escalation_threshold_usd)} />
              <SummaryItem label="Ambiguous Action" value={controlSummary.ambiguous_response_action} />
            </div>
          ) : null}

          <div className="subtle-note">
            `workflow-worker`, `capability-gateway`, `policy-engine`, and `orchestrator-api` all read from this control
            source before falling back locally.
          </div>
        </div>
      </header>

      <nav className="top-nav" aria-label="Ops console navigation">
        {navigation.map((item) => (
          <button
            key={item.view}
            className={`nav-button ${activeView === item.view ? "nav-button-active" : ""}`.trim()}
            type="button"
            onClick={() => setActiveView(item.view)}
          >
            <span className="nav-label">{item.label}</span>
            <span className="nav-meta">{viewMeta(item.view, approvalQueue.length, exceptionQueue.length, latestTask)}</span>
          </button>
        ))}
      </nav>

      <main className="view-shell">
        {activeView === "overview" ? (
          <div className="view-grid">
            <SectionCard title="Operator Snapshot" subtitle="The current operator-visible state of the PoC stack.">
              <div className="summary-grid">
                <SummaryItem label="Awaiting Approval" value={String(approvalQueue.length)} />
                <SummaryItem label="Exceptions" value={String(exceptionQueue.length)} />
                <SummaryItem label="Recent Tasks" value={String(recentTasks.length)} />
                <SummaryItem label="Latest Task" value={latestTask ? latestTask.taskId : "None"} />
              </div>
            </SectionCard>

            <SectionCard title="Approval Queue" subtitle="Recent tasks waiting for approval." count={approvalQueue.length}>
              <TaskList
                tasks={approvalQueue}
                activeTaskId={selectedTask?.task_id ?? null}
                emptyMessage="No recent tasks are waiting for approval."
                onSelect={(taskId) => selectTask(taskId, "approvals")}
              />
            </SectionCard>

            <SectionCard title="Exception Queue" subtitle="Recent tasks that need operator attention." count={exceptionQueue.length}>
              <TaskList
                tasks={exceptionQueue}
                activeTaskId={selectedTask?.task_id ?? null}
                emptyMessage="No recent exception tasks in this browser."
                onSelect={(taskId) => selectTask(taskId, "exceptions")}
              />
            </SectionCard>

            <SectionCard title="Recent Tasks" subtitle="Local browser queue until a server-side listing endpoint exists." count={recentTasks.length}>
              <TaskList
                tasks={recentTasks}
                activeTaskId={selectedTask?.task_id ?? null}
                emptyMessage="No tasks captured in this browser yet."
                onSelect={(taskId) => selectTask(taskId, "explorer")}
              />
            </SectionCard>

            <SectionCard title="Control Source Documents" subtitle="Snapshot documents currently backing the stack.">
              {controlVersions ? (
                <div className="document-list">
                  {controlVersions.documents.map((document) => (
                    <article className="document-item" key={document.name}>
                      <div className="record-header">
                        <strong>{document.name}</strong>
                        <span className="hash-tag">{shortHash(document.sha256)}</span>
                      </div>
                      <p className="record-meta">{document.source_path}</p>
                      <p className="record-meta">{formatDate(document.last_modified_at)}</p>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="muted">Control snapshot metadata is not available yet.</p>
              )}
            </SectionCard>
          </div>
        ) : null}

        {activeView === "trust-graph" ? (
          <TrustGraphNavigator
            approvalCount={approvalQueue.length}
            exceptionCount={exceptionQueue.length}
            latestTask={latestTask}
            onNavigate={setActiveView}
          />
        ) : null}

        {activeView === "intake" ? (
          <div className="view-grid view-grid-split">
            <SectionCard title="Create Test Payment" subtitle="Send a real intake request through orchestrator-api.">
              <form className="form-grid" onSubmit={handleCreateTask}>
                <LabeledInput label="Customer" value={createForm.customer_id} onChange={(value) => updateCreateForm("customer_id", value)} />
                <LabeledInput
                  label="Source Account"
                  value={createForm.source_account_id}
                  onChange={(value) => updateCreateForm("source_account_id", value)}
                />
                <LabeledInput
                  label="Beneficiary"
                  value={createForm.beneficiary_id}
                  onChange={(value) => updateCreateForm("beneficiary_id", value)}
                />
                <LabeledInput
                  label="Amount (USD)"
                  inputMode="decimal"
                  value={createForm.amount_usd}
                  onChange={(value) => updateCreateForm("amount_usd", value)}
                />
                <LabeledSelect
                  label="Rail"
                  value={createForm.rail}
                  options={[
                    { label: "ACH", value: "ach" },
                    { label: "Same Day ACH", value: "same_day_ach" },
                    { label: "Internal Transfer", value: "internal_transfer" },
                  ]}
                  onChange={(value) => updateCreateForm("rail", value)}
                />
                <LabeledInput
                  label="Requested Date"
                  type="date"
                  value={createForm.requested_execution_date}
                  onChange={(value) => updateCreateForm("requested_execution_date", value)}
                />
                <LabeledInput
                  label="Initiated By"
                  value={createForm.initiated_by}
                  onChange={(value) => updateCreateForm("initiated_by", value)}
                />
                <LabeledInput label="Trace Id" value={createForm.trace_id} onChange={(value) => updateCreateForm("trace_id", value)} />
                <LabeledInput className="full-span" label="Memo" value={createForm.memo} onChange={(value) => updateCreateForm("memo", value)} />

                {createError ? <p className="error-text full-span">{createError}</p> : null}

                <div className="form-actions full-span">
                  <button className="primary-button" type="submit" disabled={isCreating}>
                    {isCreating ? "Submitting…" : "Create Task"}
                  </button>
                </div>
              </form>
            </SectionCard>

            <SectionCard title="Recent Tasks" subtitle="Use this to jump back into the latest operator work." count={recentTasks.length}>
              <TaskList
                tasks={recentTasks}
                activeTaskId={selectedTask?.task_id ?? null}
                emptyMessage="No recent tasks in this browser yet."
                onSelect={(taskId) => selectTask(taskId, "explorer")}
              />
            </SectionCard>
          </div>
        ) : null}

        {activeView === "approvals" ? (
          <div className="view-grid view-grid-split">
            <SectionCard title="Approval Queue" subtitle="Tasks in browser history that still need approval." count={approvalQueue.length}>
              <TaskList
                tasks={approvalQueue}
                activeTaskId={selectedTask?.task_id ?? null}
                emptyMessage="No recent tasks are waiting for approval."
                onSelect={(taskId) => selectTask(taskId, "approvals")}
              />
            </SectionCard>

            <TaskWorkbenchPanel
              title="Approval Workbench"
              subtitle="Review a selected task and send it back through orchestrator-api for approval-backed release."
              taskLookup={taskLookup}
              onTaskLookupChange={setTaskLookup}
              onLoadTask={handleLoadTask}
              onRefreshTask={() => selectedTask && setSelectedTaskId(selectedTask.task_id)}
              isFetchingTask={isFetchingTask}
              taskError={taskError}
              selectedTask={selectedTask}
              showResumeAction={selectedTask?.status === "awaiting_approval"}
              resumeForm={resumeForm}
              onResumeFormChange={updateResumeForm}
              onResumeTask={handleResumeTask}
              isResuming={isResuming}
              resumeError={resumeError}
            />
          </div>
        ) : null}

        {activeView === "explorer" ? (
          <div className="view-grid view-grid-split">
            <SectionCard title="Recent Tasks" subtitle="Load a recent task or paste a `task_id` into the explorer." count={recentTasks.length}>
              <TaskList
                tasks={recentTasks}
                activeTaskId={selectedTask?.task_id ?? null}
                emptyMessage="No recent tasks in this browser yet."
                onSelect={(taskId) => selectTask(taskId, "explorer")}
              />
            </SectionCard>

            <TaskWorkbenchPanel
              title="Task Explorer"
              subtitle="Inspect the full merged task view, including provenance, artifacts, and delegated work."
              taskLookup={taskLookup}
              onTaskLookupChange={setTaskLookup}
              onLoadTask={handleLoadTask}
              onRefreshTask={() => selectedTask && setSelectedTaskId(selectedTask.task_id)}
              isFetchingTask={isFetchingTask}
              taskError={taskError}
              selectedTask={selectedTask}
              showResumeAction={selectedTask?.status === "awaiting_approval"}
              resumeForm={resumeForm}
              onResumeFormChange={updateResumeForm}
              onResumeTask={handleResumeTask}
              isResuming={isResuming}
              resumeError={resumeError}
            />
          </div>
        ) : null}

        {activeView === "exceptions" ? (
          <div className="view-grid view-grid-split">
            <SectionCard title="Exception Queue" subtitle="Tasks in recent history that need extra operator attention." count={exceptionQueue.length}>
              <TaskList
                tasks={exceptionQueue}
                activeTaskId={selectedTask?.task_id ?? null}
                emptyMessage="No recent exception tasks in this browser."
                onSelect={(taskId) => selectTask(taskId, "exceptions")}
              />
            </SectionCard>

            <TaskWorkbenchPanel
              title="Exception Review"
              subtitle="Inspect ambiguous, failed, or manual-review tasks without mixing them into approval work."
              taskLookup={taskLookup}
              onTaskLookupChange={setTaskLookup}
              onLoadTask={handleLoadTask}
              onRefreshTask={() => selectedTask && setSelectedTaskId(selectedTask.task_id)}
              isFetchingTask={isFetchingTask}
              taskError={taskError}
              selectedTask={selectedTask}
              showResumeAction={false}
              resumeForm={resumeForm}
              onResumeFormChange={updateResumeForm}
              onResumeTask={handleResumeTask}
              isResuming={isResuming}
              resumeError={resumeError}
            />
          </div>
        ) : null}
      </main>
    </div>
  );
}

function TaskWorkbenchPanel(props: {
  title: string;
  subtitle: string;
  taskLookup: string;
  onTaskLookupChange: (value: string) => void;
  onLoadTask: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onRefreshTask: () => void;
  isFetchingTask: boolean;
  taskError: string | null;
  selectedTask: TaskDetailView | null;
  showResumeAction: boolean;
  resumeForm: ResumeFormState;
  onResumeFormChange: <K extends keyof ResumeFormState>(field: K, value: ResumeFormState[K]) => void;
  onResumeTask: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  isResuming: boolean;
  resumeError: string | null;
}) {
  const policyDecision = asRecord(props.selectedTask?.task_metadata.policy_decision);
  const selectedArtifacts = props.selectedTask?.artifacts ?? [];
  const selectedDelegations = props.selectedTask?.delegations ?? [];
  const selectedHistory = props.selectedTask?.state_history ?? [];

  return (
    <SectionCard title={props.title} subtitle={props.subtitle}>
      <form className="task-lookup" onSubmit={props.onLoadTask}>
        <input
          aria-label="Task id"
          className="lookup-input"
          placeholder="task_..."
          value={props.taskLookup}
          onChange={(event) => props.onTaskLookupChange(event.target.value)}
        />
        <button className="secondary-button" type="submit" disabled={props.isFetchingTask}>
          {props.isFetchingTask ? "Loading…" : "Load Task"}
        </button>
        <button
          className="secondary-button"
          type="button"
          disabled={props.selectedTask === null || props.isFetchingTask}
          onClick={props.onRefreshTask}
        >
          Refresh
        </button>
      </form>

      {props.taskError ? <p className="error-text">{props.taskError}</p> : null}

      {props.selectedTask ? (
        <div className="task-layout">
          <div className="task-summary-card">
            <div className="task-summary-header">
              <div>
                <p className="task-title">{props.selectedTask.task_id}</p>
                <p className="task-subtitle">
                  {props.selectedTask.customer_id} · {formatCurrency(props.selectedTask.amount_usd)} · {props.selectedTask.rail}
                </p>
              </div>
              <StatusBadge status={props.selectedTask.status} />
            </div>

            <div className="summary-grid">
              <SummaryItem label="Approval" value={props.selectedTask.approval_status} />
              <SummaryItem label="Beneficiary" value={props.selectedTask.beneficiary_status} />
              <SummaryItem label="Updated" value={formatDate(props.selectedTask.updated_at ?? props.selectedTask.created_at)} />
              <SummaryItem label="Workflow Id" value={stringValue(props.selectedTask.task_metadata.workflow_id)} />
              <SummaryItem label="Source Account" value={maskValue(stringValue(props.selectedTask.task_metadata.source_account_id))} />
              <SummaryItem label="Beneficiary Id" value={maskValue(stringValue(props.selectedTask.task_metadata.beneficiary_id))} />
            </div>

            {policyDecision ? (
              <div className="policy-callout">
                <span className="chip">{stringValue(policyDecision.decision)}</span>
                <p>{stringValue(policyDecision.reason)}</p>
              </div>
            ) : null}
          </div>

          {props.showResumeAction ? (
            <SectionCard title="Approve And Release" subtitle="This action goes back through orchestrator-api and policy-engine.">
              <form className="form-grid" onSubmit={props.onResumeTask}>
                <LabeledInput
                  label="Approved By"
                  value={props.resumeForm.approved_by}
                  onChange={(value) => props.onResumeFormChange("approved_by", value)}
                />
                <LabeledSelect
                  label="Release Mode"
                  value={props.resumeForm.release_mode}
                  options={[
                    { label: "Execute", value: "execute" },
                    { label: "Dry Run", value: "dry_run" },
                  ]}
                  onChange={(value) => props.onResumeFormChange("release_mode", value as "dry_run" | "execute")}
                />
                <LabeledInput
                  className="full-span"
                  label="Idempotency Key"
                  value={props.resumeForm.idempotency_key}
                  onChange={(value) => props.onResumeFormChange("idempotency_key", value)}
                />
                <LabeledInput
                  className="full-span"
                  label="Approval Note"
                  value={props.resumeForm.approval_note}
                  onChange={(value) => props.onResumeFormChange("approval_note", value)}
                />

                {props.resumeError ? <p className="error-text full-span">{props.resumeError}</p> : null}

                <div className="form-actions full-span">
                  <button className="primary-button" type="submit" disabled={props.isResuming}>
                    {props.isResuming ? "Submitting approval…" : "Approve And Resume"}
                  </button>
                </div>
              </form>
            </SectionCard>
          ) : null}

          <div className="detail-grid">
            <SectionCard title="State History" subtitle="Operational state transitions in order.">
              <div className="timeline">
                {selectedHistory.length > 0 ? (
                  selectedHistory.map((entry) => (
                    <div className="timeline-item" key={entry.id}>
                      <div className="timeline-marker" />
                      <div>
                        <p className="timeline-title">
                          {entry.from_status ?? "start"} → {entry.to_status}
                        </p>
                        <p className="timeline-subtitle">
                          {entry.changed_by} · {formatDate(entry.created_at)}
                        </p>
                        {entry.reason ? <p className="timeline-reason">{entry.reason}</p> : null}
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="muted">No state transitions recorded yet.</p>
                )}
              </div>
            </SectionCard>

            <SectionCard title="Delegations" subtitle="Bounded work issued by the parent agent.">
              {selectedDelegations.length > 0 ? (
                <div className="record-list">
                  {selectedDelegations.map((delegation) => (
                    <article className="record-card" key={delegation.delegation_id}>
                      <div className="record-header">
                        <strong>{delegation.delegated_action}</strong>
                        <StatusBadge status={delegation.status} kind="delegation" />
                      </div>
                      <p className="record-meta">
                        {delegation.parent_agent_id} → {delegation.delegated_agent_id}
                      </p>
                      <p className="record-meta">
                        {delegation.capability_id ?? "no capability"} · {formatDate(delegation.created_at)}
                      </p>
                      <details>
                        <summary>Envelope</summary>
                        <pre>{toJson(delegation.response_envelope ?? delegation.request_envelope)}</pre>
                      </details>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="muted">No delegations available.</p>
              )}
            </SectionCard>

            <SectionCard title="Artifacts" subtitle="Evidence and policy traces attached to the task.">
              {selectedArtifacts.length > 0 ? (
                <div className="record-list">
                  {selectedArtifacts.map((artifact) => (
                    <article className="record-card" key={artifact.id}>
                      <div className="record-header">
                        <strong>{artifact.artifact_type}</strong>
                        <span className="chip chip-quiet">{artifact.trust_level}</span>
                      </div>
                      <p className="record-meta">
                        {artifact.created_by} · {formatDate(artifact.created_at)}
                      </p>
                      <details>
                        <summary>Content</summary>
                        <pre>{toJson(artifact.content)}</pre>
                      </details>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="muted">No artifacts attached yet.</p>
              )}
            </SectionCard>

            <SectionCard title="Raw Task JSON" subtitle="Merged context + provenance view returned by orchestrator-api.">
              <pre>{toJson(props.selectedTask)}</pre>
            </SectionCard>
          </div>
        </div>
      ) : (
        <div className="empty-state">
          <p className="empty-title">No task selected yet.</p>
          <p className="muted">
            Load a known `task_id` or choose a task from one of the queues to inspect approval state, provenance,
            artifacts, and delegated work.
          </p>
        </div>
      )}
    </SectionCard>
  );
}

function TrustGraphNavigator(props: {
  approvalCount: number;
  exceptionCount: number;
  latestTask: RecentTaskRecord | null;
  onNavigate: (view: AppView) => void;
}) {
  return (
    <div className="view-grid view-grid-trust-graph">
      <SectionCard
        title="Trust Graph Navigator"
        subtitle="Use the trust graph itself to move through the console surfaces that correspond to each architectural checkpoint."
      >
        <div className="graph-stage">
          <figure className="graph-figure">
            <img
              alt="Trust Graph: Agentic Domestic Money Movement"
              className="graph-image"
              src={trustGraphImage}
            />
            <div className="graph-overlay" aria-hidden="true">
              {trustGraphMappings.map((mapping) => (
                <button
                  key={mapping.id}
                  aria-label={`${mapping.label}: open ${mapping.targetLabel}`}
                  className="graph-hotspot"
                  style={{ top: mapping.top, left: mapping.left }}
                  type="button"
                  onClick={() => props.onNavigate(mapping.targetView)}
                >
                  <span className="graph-hotspot-dot" />
                  <span className="graph-hotspot-label">{mapping.label}</span>
                </button>
              ))}
            </div>
          </figure>

          <p className="subtle-note">
            Click any hotspot to jump from the architecture diagram into the closest operator-facing console view.
          </p>
        </div>
      </SectionCard>

      <SectionCard
        title="Graph To Console Mapping"
        subtitle="Each graph component below maps to the view that best supports the operator task at that checkpoint."
      >
        <div className="summary-grid trust-graph-summary">
          <SummaryItem label="Awaiting Approval" value={String(props.approvalCount)} />
          <SummaryItem label="Exceptions" value={String(props.exceptionCount)} />
          <SummaryItem label="Latest Task" value={props.latestTask ? shortHash(props.latestTask.taskId) : "None"} />
          <SummaryItem label="Navigation Mode" value="Image-Driven" />
        </div>

        <div className="graph-mapping-grid">
          {trustGraphMappings.map((mapping) => (
            <article className="graph-mapping-card" key={mapping.id}>
              <div className="graph-mapping-header">
                <div>
                  <strong>{mapping.label}</strong>
                  <p className="record-meta">{mapping.description}</p>
                </div>
                <span className="chip chip-quiet">{mapping.targetLabel}</span>
              </div>
              <p className="graph-mapping-detail">{mapping.detail}</p>
              <div className="graph-mapping-actions">
                <button className="secondary-button" type="button" onClick={() => props.onNavigate(mapping.targetView)}>
                  Open {mapping.targetLabel}
                </button>
              </div>
            </article>
          ))}
        </div>
      </SectionCard>
    </div>
  );
}

function SectionCard(props: {
  title: string;
  subtitle: string;
  count?: number;
  children: ReactNode;
}) {
  return (
    <section className="section-card">
      <div className="section-header">
        <div>
          <h2>{props.title}</h2>
          <p>{props.subtitle}</p>
        </div>
        {props.count !== undefined ? <span className="count-pill">{props.count}</span> : null}
      </div>
      {props.children}
    </section>
  );
}

function SummaryItem(props: { label: string; value: string }) {
  return (
    <div className="summary-item">
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </div>
  );
}

function LabeledInput(props: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"];
  className?: string;
}) {
  return (
    <label className={`field ${props.className ?? ""}`.trim()}>
      <span>{props.label}</span>
      <input
        type={props.type ?? "text"}
        inputMode={props.inputMode}
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
      />
    </label>
  );
}

function LabeledSelect(props: {
  label: string;
  value: string;
  options: Array<{ label: string; value: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <label className="field">
      <span>{props.label}</span>
      <select value={props.value} onChange={(event) => props.onChange(event.target.value)}>
        {props.options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function TaskList(props: {
  tasks: RecentTaskRecord[];
  activeTaskId: string | null;
  emptyMessage: string;
  onSelect: (taskId: string) => void;
}) {
  if (props.tasks.length === 0) {
    return <p className="muted">{props.emptyMessage}</p>;
  }

  return (
    <div className="queue-list">
      {props.tasks.map((task) => (
        <button
          key={task.taskId}
          className={`queue-item ${props.activeTaskId === task.taskId ? "queue-item-active" : ""}`.trim()}
          type="button"
          onClick={() => props.onSelect(task.taskId)}
        >
          <div className="queue-item-header">
            <strong>{task.customerId}</strong>
            <StatusBadge status={task.status} />
          </div>
          <div className="queue-item-body">
            <span>{task.taskId}</span>
            <span>
              {formatCurrency(task.amountUsd)} · {task.rail}
            </span>
          </div>
        </button>
      ))}
    </div>
  );
}

function StatusBadge(props: { status: string; kind?: "task" | "delegation" }) {
  const className = statusTone(props.status, props.kind ?? "task");
  return <span className={`status-badge ${className}`}>{props.status.replaceAll("_", " ")}</span>;
}

function statusTone(status: string, kind: "task" | "delegation") {
  if (kind === "delegation") {
    if (status === "completed") return "status-good";
    if (status === "pending" || status === "queued") return "status-warn";
    return "status-bad";
  }

  if (status === "settlement_pending" || status === "validated") return "status-good";
  if (status === "awaiting_approval" || status === "pending_reconcile") return "status-warn";
  if (status === "exception" || status === "failed" || status === "cancelled") return "status-bad";
  return "status-neutral";
}

function toMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }
  return "An unexpected error occurred.";
}

function buildIdempotencyKey(taskId: string) {
  const suffix = Math.random().toString(36).slice(2, 8);
  return `ops-${taskId.slice(-6)}-${suffix}`;
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function shortHash(value: string) {
  return value.slice(0, 10);
}

function toJson(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function stringValue(value: unknown) {
  return typeof value === "string" && value !== "" ? value : "Unavailable";
}

function maskValue(value: string) {
  if (value === "Unavailable") {
    return value;
  }
  if (value.length <= 4) {
    return "••••";
  }
  return `${"•".repeat(Math.max(4, value.length - 4))}${value.slice(-4)}`;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

function parseView(value: string): AppView | null {
  return navigation.some((item) => item.view === value) ? (value as AppView) : null;
}

function getInitialView(): AppView {
  if (typeof window === "undefined") {
    return "overview";
  }

  return parseView(window.location.hash.replace("#", "")) ?? "overview";
}

function viewForTask(status: TaskStatus): AppView {
  if (status === "awaiting_approval") {
    return "approvals";
  }
  if (exceptionStatuses.includes(status)) {
    return "exceptions";
  }
  return "explorer";
}

function viewMeta(view: AppView, approvalCount: number, exceptionCount: number, latestTask: RecentTaskRecord | null) {
  switch (view) {
    case "overview":
      return "control + queues";
    case "trust-graph":
      return "image navigation";
    case "intake":
      return "new payment";
    case "approvals":
      return `${approvalCount} waiting`;
    case "explorer":
      return latestTask ? shortHash(latestTask.taskId) : "load by id";
    case "exceptions":
      return `${exceptionCount} flagged`;
  }
}
