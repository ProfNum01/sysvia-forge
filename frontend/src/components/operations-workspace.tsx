import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  useIsMutating,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  Check,
  CircleAlert,
  Clock3,
  Database,
  FileSearch,
  GitBranch,
  LoaderCircle,
  LockKeyhole,
  Package,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Workflow,
  X,
} from "lucide-react";
import { Button } from "./ui/button";
import { api, formatTime, label } from "../lib/api";
import {
  actionControls,
  actionImpact,
  actionName,
  evidenceLink,
  operationEvents,
  operationKeys,
} from "../lib/operations";
import { comparisonValue } from "../lib/evidence";
import { useResultModal } from "./result-modal";
import type { Action, Audit, Inspection, Order, VerificationStatus } from "../types";

function Badge({ value }: { value: string }) {
  return (
    <span
      className={`status status-${value.toLowerCase().replaceAll("_", "-")}`}
    >
      <span />
      {label(value)}
    </span>
  );
}
function Pending() {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={18} aria-hidden="true" />
      Loading operational records...
    </div>
  );
}
function LoadError({ error, retry }: { error: Error; retry: () => void }) {
  return (
    <div className="error-state" role="alert">
      <CircleAlert size={19} aria-hidden="true" />
      <div>
        <strong>Operational records unavailable</strong>
        <p>{error.message}</p>
      </div>
      <Button variant="outline" size="sm" onClick={retry}>
        <RefreshCw size={14} aria-hidden="true" />
        Retry
      </Button>
    </div>
  );
}
function Surface({
  title,
  subtitle,
  children,
  action,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function EvidenceReferences({
  references,
  inspection,
  orderId,
}: {
  references: string[];
  inspection?: Inspection;
  orderId?: string;
}) {
  return (
    <div
      className="operation-evidence-refs"
      aria-label="Recorded evidence references"
    >
      {references.map((reference, index) => {
        const href = evidenceLink(reference, {
          inspection_id: inspection?.id ?? "",
          photo_id: inspection?.photo_id,
          order_id: orderId,
        });
        const [kind, ...rest] = reference.split(":");
        const rawId = rest.join(":");
        const shortId = rawId.length > 14 ? `${rawId.slice(0, 8)}…${rawId.slice(-4)}` : rawId;
        const displayLabel = rawId ? `${kind}: ${shortId}` : reference;

        return href && inspection ? (
          <Link key={`${reference}-${index}`} to={href} title={reference}>
            <span>{displayLabel}</span>
            <ArrowRight size={11} aria-hidden="true" />
          </Link>
        ) : (
          <span key={`${reference}-${index}`} title={reference}>{displayLabel}</span>
        );
      })}
    </div>
  );
}

export function RecordedTimeline({
  events,
  emptyMessage = "No operational events have been recorded.",
}: {
  events: {
    id: string;
    event_type: string;
    created_at: string;
    details: unknown;
    actor?: string;
  }[];
  emptyMessage?: string;
}) {
  const [filter, setFilter] = useState<"ALL" | "TOOL" | "LIFECYCLE" | "ACTION" | "EVIDENCE">("ALL");

  if (!events.length)
    return <p className="operations-empty-copy">{emptyMessage}</p>;

  const categorized = events.map((event) => {
    let cat: "TOOL" | "LIFECYCLE" | "ACTION" | "EVIDENCE" | "ERROR" = "EVIDENCE";
    let badge = "Evidence";
    let IconComponent = Activity;
    let className = "event-cat-evidence";

    if (
      event.actor === "meta-read-tool" ||
      event.event_type.startsWith("get_") ||
      event.event_type.startsWith("TOOL_")
    ) {
      cat = "TOOL";
      badge = "Agent Tool";
      IconComponent = Database;
      className = "event-cat-tool";
    } else if (
      event.event_type.includes("INVESTIGATION_") ||
      event.event_type.includes("ANALYSIS_")
    ) {
      cat = "LIFECYCLE";
      badge = "Lifecycle";
      IconComponent = Sparkles;
      className = "event-cat-lifecycle";
    } else if (
      event.event_type.includes("ACTION_") ||
      event.event_type.includes("APPROVAL_") ||
      event.event_type.includes("TASK_") ||
      event.event_type.includes("CONTROLLED_")
    ) {
      cat = "ACTION";
      badge = "Action Gate";
      IconComponent = ShieldCheck;
      className = "event-cat-action";
    } else if (
      event.event_type.includes("ERROR") ||
      event.event_type.includes("FAILED") ||
      event.event_type.includes("BLOCKED")
    ) {
      cat = "ERROR";
      badge = "Exception";
      IconComponent = CircleAlert;
      className = "event-cat-error";
    }

    return { event, cat, badge, IconComponent, className };
  });

  const toolCount = categorized.filter((c) => c.cat === "TOOL").length;
  const lifecycleCount = categorized.filter((c) => c.cat === "LIFECYCLE").length;
  const actionCount = categorized.filter((c) => c.cat === "ACTION").length;

  const filtered = filter === "ALL" ? categorized : categorized.filter((c) => c.cat === filter);

  return (
    <div className="recorded-timeline-container">
      {events.length > 3 && (
        <div className="timeline-filter-bar" role="toolbar" aria-label="Event category filter">
          <button
            type="button"
            data-category="ALL"
            className={`timeline-filter-pill ${filter === "ALL" ? "active is-active" : ""}`}
            onClick={() => setFilter("ALL")}
          >
            All ({events.length})
          </button>
          {toolCount > 0 && (
            <button
              type="button"
              data-category="TOOL"
              className={`timeline-filter-pill ${filter === "TOOL" ? "active is-active" : ""}`}
              onClick={() => setFilter("TOOL")}
            >
              Tools ({toolCount})
            </button>
          )}
          {lifecycleCount > 0 && (
            <button
              type="button"
              data-category="LIFECYCLE"
              className={`timeline-filter-pill ${filter === "LIFECYCLE" ? "active is-active" : ""}`}
              onClick={() => setFilter("LIFECYCLE")}
            >
              Lifecycle ({lifecycleCount})
            </button>
          )}
          {actionCount > 0 && (
            <button
              type="button"
              data-category="ACTION"
              className={`timeline-filter-pill ${filter === "ACTION" ? "active is-active" : ""}`}
              onClick={() => setFilter("ACTION")}
            >
              Actions ({actionCount})
            </button>
          )}
        </div>
      )}
      <ol className="audit-list operations-timeline">
        {filtered.map(({ event, badge, IconComponent, className }) => (
          <li key={event.id} id={`audit-${event.id}`} className={`timeline-entry ${className}`}>
            <div className={`audit-symbol ${className}`}>
              <IconComponent size={14} aria-hidden="true" />
            </div>
            <div className="timeline-content">
              <div className="timeline-header-row">
                <span className="timeline-cat-badge">{badge}</span>
                <strong>{label(event.event_type)}</strong>
                <time dateTime={event.created_at}>
                  {formatTime(event.created_at)}
                  {event.actor ? ` · ${event.actor}` : ""}
                </time>
              </div>
              <details className="timeline-details">
                <summary>Recorded details</summary>
                <pre>{JSON.stringify(event.details, null, 2)}</pre>
              </details>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function invalidateOperations(qc: ReturnType<typeof useQueryClient>) {
  for (const key of ["inspections", "inspection", "audit", "orders", "summary", "verification-status"])
    qc.invalidateQueries({ queryKey: [key] });
}

export function ActiveInvestigationProgress({
  orderRef,
  inspectionId,
}: {
  orderRef?: string;
  inspectionId?: string;
}) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setElapsed((prev) => Math.round((prev + 0.5) * 10) / 10);
    }, 500);
    return () => clearInterval(timer);
  }, []);

  const stages = [
    {
      id: "manifest",
      label: "Order Manifest",
      desc: "Target SKUs & lines",
      icon: Database,
    },
    {
      id: "muse",
      label: "Meta Muse Spark",
      desc: "Multimodal reasoning",
      icon: Sparkles,
    },
    {
      id: "tools",
      label: "Read-Tool Check",
      desc: "Stock & history audit",
      icon: FileSearch,
    },
    {
      id: "proposal",
      label: "Proposal Gate",
      desc: "Supervisor plan check",
      icon: ShieldCheck,
    },
  ];

  const currentStageIndex =
    elapsed < 2.5 ? 0 : elapsed < 6.0 ? 1 : elapsed < 10.0 ? 2 : 3;

  const currentStage = stages[currentStageIndex];

  const progressPercent = Math.min(
    95,
    Math.round(
      elapsed < 2.5
        ? (elapsed / 2.5) * 25
        : elapsed < 6.0
          ? 25 + ((elapsed - 2.5) / 3.5) * 25
          : elapsed < 10.0
            ? 50 + ((elapsed - 6.0) / 4.0) * 25
            : 75 + Math.min(20, ((elapsed - 10.0) / 4.0) * 20)
    )
  );

  return (
    <div className="active-investigation-container" role="status" aria-live="polite">
      <div className="active-investigation-header">
        <div className="investigation-header-main">
          <span className="investigation-radar-dot" aria-hidden="true" />
          <div className="investigation-title-group">
            <h4>Live AI Investigation in Progress</h4>
            <p>
              Autonomous reasoning via Meta Muse Spark 1.3
              {orderRef ? ` · Order ${orderRef}` : ""}
              {inspectionId ? ` · ${inspectionId.slice(0, 10)}` : ""}
            </p>
          </div>
        </div>
        <div className="investigation-timer">
          <Clock3 size={13} aria-hidden="true" />
          <span>{elapsed.toFixed(1)}s</span>
        </div>
      </div>

      <div
        className="progress-bar-track progress-bar-investigation"
        role="progressbar"
        aria-valuenow={progressPercent}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="progress-bar-fill progress-purple"
          style={{ width: `${progressPercent}%` }}
        >
          <div className="progress-bar-shimmer" />
        </div>
      </div>

      <div className="investigation-stepper-grid">
        {stages.map((stage, idx) => {
          const isDone = idx < currentStageIndex;
          const isCurrent = idx === currentStageIndex;
          const isPending = idx > currentStageIndex;
          const Icon = stage.icon;

          return (
            <div
              key={stage.id}
              className={`investigation-step-node ${isDone ? "is-done" : ""} ${isCurrent ? "is-current" : ""} ${isPending ? "is-pending" : ""}`}
            >
              <div className="investigation-node-icon">
                {isDone ? (
                  <Check size={14} aria-hidden="true" />
                ) : isCurrent ? (
                  <LoaderCircle className="spin" size={14} aria-hidden="true" />
                ) : (
                  <Icon size={14} aria-hidden="true" />
                )}
              </div>
              <div className="investigation-node-text">
                <strong>{stage.label}</strong>
                <span>{stage.desc}</span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="analysis-status-message">
        <Sparkles size={14} aria-hidden="true" />
        <p>
          <strong>Stage {currentStageIndex + 1}/4: {currentStage.label}.</strong>{" "}
          Model is executing read-only tools against local inventory and audit logs. No mutations are performed without supervisor approval.
        </p>
      </div>
    </div>
  );
}

export function InvestigationCard({
  inspection: i,
  order,
  token,
  isCurrent,
}: {
  inspection: Inspection;
  order?: Order;
  token: string;
  isCurrent: boolean;
}) {
  const qc = useQueryClient();
  const { showResult } = useResultModal();
  const inFlight = useIsMutating({ mutationKey: ["investigate", i.id] }) > 0;
  const mutation = useMutation({
    mutationKey: ["investigate", i.id],
    mutationFn: () =>
      api<Inspection>(`/inspections/${i.id}/investigate`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Idempotency-Key": operationKeys.get(i.id, "investigate"),
        },
      }),
    onSuccess: (data) => {
      qc.setQueryData(["inspection", i.id], data);
      invalidateOperations(qc);
      showResult({
        type: "INVESTIGATION",
        status: data.investigation_result?.decision ?? "COMPLETED",
        title: "اكتمل التحقيق الذكي · AI Investigation Completed",
        subtitle: `تم فحص الأدلة وتطبيق السياسة الحتمية (Order ${order?.reference ?? i.order_id})`,
        diagnosis:
          data.investigation_result?.summary ??
          data.investigation ??
          "تم استعلام أدوات القراءة وتسجيل النتائج وصياغة مقترحات الإجراءات التصحيحية المعتمدة.",
        orderReference: order?.reference,
        inspectionId: i.id,
        orderId: i.order_id,
        discrepancies: data.discrepancies,
      });
    },
    onSettled: () => invalidateOperations(qc),
  });
  const status =
    i.investigation_status ?? (i.investigation ? "COMPLETED" : "NOT_STARTED");
  const verification = useQuery({
    queryKey: ["verification-status", i.order_id, i.id],
    queryFn: () => api<VerificationStatus>(`/orders/${i.order_id}/verification-status`,
      { headers: { Authorization: `Bearer ${token}` } }),
    enabled: !!token && isCurrent,
  });
  const running = status === "RUNNING" || inFlight;
  const result = i.investigation_result;
  const summary = result?.summary ?? i.investigation;
  const events = operationEvents(i.execution_events ?? []);
  const eligible =
    isCurrent &&
    ["NEEDS_REVIEW", "HELD"].includes(i.status) &&
    i.discrepancies.length > 0;
  return (
    <article
      className="investigation-card"
      id={`investigation-${i.investigation_id ?? i.id}`}
    >
      <div className="investigation-card-top">
        <div className="investigation-symbol">
          <Sparkles size={18} aria-hidden="true" />
        </div>
        <div>
          <strong>{order?.reference ?? i.order_id}</strong>
          <span>Inspection {i.id.slice(0, 12)}</span>
          {order?.data_source === "synthetic_claude" && <span>CLAUDE AI SYNTHETIC · fictional inventory · no physical correction verified</span>}
        </div>
        <Badge value={status} />
      </div>
      <div className="investigation-context">
        <span>Inspection outcome</span>
        <Badge value={i.status} />
        {i.reconciliation_status && i.reconciliation_status !== i.status && (
          <Badge value={i.reconciliation_status} />
        )}
      </div>
      {!!i.discrepancies.length && (
        <div className="investigation-context">
          <span>Detected issues</span>
          <strong>{[...new Set(i.discrepancies.map((item) => label(item.type)))].join(", ")}</strong>
        </div>
      )}
      {verification.data && (
        <div className="investigation-verification-meta">
          <span className="verification-pill">
            <span className="pill-label">Eligibility</span>
            <Badge value={verification.data.verification_status} />
          </span>
          <span className="verification-pill">
            <span className="pill-label">Shipping</span>
            <strong>{label(verification.data.shipping_status)}</strong>
          </span>
          <span className="verification-pill">
            <span className="pill-label">Tasks</span>
            <strong>
              {[...verification.data.picking_tasks, ...verification.data.removal_tasks]
                .filter((task) => task.status !== "COMPLETED").length} open
            </strong>
          </span>
          <span className={`verification-pill ${verification.data.requires_reinspection ? "pill-flag-warning" : "pill-flag-ok"}`}>
            {verification.data.requires_reinspection ? "New evidence required" : "Evidence current"}
          </span>
          <span className="verification-pill">
            {verification.data.revision_current ? "Revision Current" : "Revision Changed"}
          </span>
        </div>
      )}
      {result?.decision && (
        <div className="investigation-decision">
          <span>Persisted decision</span>
          <strong>{label(result.decision)}</strong>
        </div>
      )}
      {running && (
        <ActiveInvestigationProgress
          orderRef={order?.reference}
          inspectionId={i.id}
        />
      )}
      {summary ? (
        <p className="investigation-summary">{summary}</p>
      ) : !running ? (
        <p className="operations-empty-copy">
          Unresolved evidence can be investigated through read-only order, inventory, inspection, pending-action, and history tools. Ambiguous visual evidence remains uncertain.
        </p>
      ) : null}
      {i.investigation_id && (
        <dl className="metadata investigation-metadata">
          <div>
            <dt>Investigation</dt>
            <dd>{i.investigation_id}</dd>
          </div>
          {i.investigation_started_at && (
            <div>
              <dt>Started</dt>
              <dd>{formatTime(i.investigation_started_at)}</dd>
            </div>
          )}
          {i.investigation_completed_at && (
            <div>
              <dt>Completed</dt>
              <dd>{formatTime(i.investigation_completed_at)}</dd>
            </div>
          )}
        </dl>
      )}
      {!!result?.findings?.length && (
        <div className="investigation-findings">
          <h3>Evidence-backed findings</h3>
          {result.findings.map((finding, index) => (
            <div key={index} className="finding">
              <strong>
                {finding.type ? label(finding.type) : "Recorded finding"}
              </strong>
              {finding.description && <p>{finding.description}</p>}
              {finding.evidence && <p>{finding.evidence}</p>}
              {finding.product_id && (
                <span className="finding-product">
                  Product {finding.product_id}
                </span>
              )}
              {"quantity" in finding && (
                <span className="finding-product">
                  Quantity: {comparisonValue(finding.quantity)}
                </span>
              )}
              {finding.evidence_references?.length ? (
                <EvidenceReferences
                  references={finding.evidence_references}
                  inspection={i}
                  orderId={i.order_id}
                />
              ) : null}
              <details>
                <summary>Structured finding</summary>
                <pre>{JSON.stringify(finding, null, 2)}</pre>
              </details>
            </div>
          ))}
        </div>
      )}
      {!!result?.evidence_references?.length && (
        <div className="investigation-evidence">
          <h3>Retrieved evidence</h3>
          <EvidenceReferences
            references={result.evidence_references}
            inspection={i}
            orderId={i.order_id}
          />
        </div>
      )}
      {result?.verification_required && (
        <div className="inline-note">
          <ShieldCheck size={16} aria-hidden="true" />
          <p>
            New physical evidence and reinspection are required. A proposal or
            completed task cannot verify this order.
          </p>
        </div>
      )}
      {(i.investigation_error || mutation.isError) && (
        <div className="error-state investigation-error" role="alert">
          <CircleAlert size={17} aria-hidden="true" />
          <div>
            <strong>Investigation did not complete</strong>
            <p>{mutation.error?.message ?? i.investigation_error?.message}</p>
            {i.investigation_error && (
              <p>
                {label(i.investigation_error.category)} ·{" "}
                {i.investigation_error.retryable
                  ? "Explicit retry is available."
                  : "Review the failure and configuration before retrying."}
              </p>
            )}
          </div>
        </div>
      )}
      <div className="button-row investigation-controls">
        {!["COMPLETED"].includes(status) && (
          <Button
            variant={status === "FAILED" ? "warning" : "agent"}
            disabled={!token || !eligible || running}
            size="sm"
            onClick={() => mutation.mutate()}
          >
            {running ? (
              <LoaderCircle className="spin" size={15} aria-hidden="true" />
            ) : (
              <Sparkles size={15} aria-hidden="true" />
            )}
            {running
              ? "Investigation in progress..."
              : status === "FAILED"
                ? "Retry AI investigation"
                : "Start AI investigation"}
          </Button>
        )}
        <Button asChild variant="outline" size="sm" className="btn-order-action action-view">
          <Link to={`/inspection?id=${encodeURIComponent(i.id)}`}>
            <FileSearch size={14} aria-hidden="true" />
            <span>View evidence</span>
            <ArrowRight size={13} aria-hidden="true" />
          </Link>
        </Button>
        {!token && status !== "COMPLETED" && (
          <Link className="text-link" to="/settings">
            <LockKeyhole size={13} aria-hidden="true" />
            Set operator credential
          </Link>
        )}
      </div>
      {!isCurrent && (
        <p className="form-hint">
          This inspection is historical. New investigations and actions require
          the latest order evidence.
        </p>
      )}
      {status !== "COMPLETED" && (
        <p className="form-hint">
          Starting an investigation makes a real Meta Muse Spark request. Only
          read tools are available to the model.
        </p>
      )}
      <details className="investigation-trace" open={running}>
        <summary>
          Agent tool activity <span>{events.length} recorded events</span>
        </summary>
        <RecordedTimeline events={events} />
      </details>
    </article>
  );
}

export function CorrectiveActionCard({
  action: a,
  inspection,
  order,
  token,
}: {
  action: Action;
  inspection?: Inspection;
  order?: Order;
  token: string;
}) {
  const qc = useQueryClient();
  const { showResult } = useResultModal();
  const [showReject, setShowReject] = useState(false);
  const [reason, setReason] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const audit = useQuery({
    queryKey: ["audit"],
    queryFn: () => api<Audit[]>("/audit-events"),
    enabled: showHistory,
    refetchInterval: a.lifecycle_state === "EXECUTING" ? 1000 : false,
  });
  const inFlight = useIsMutating({ mutationKey: ["action", a.id] }) > 0;
  const mutation = useMutation({
    mutationKey: ["action", a.id],
    mutationFn: (operation: "approve" | "reject" | "execute") =>
      api<Action>(`/actions/${a.id}/${operation}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          idempotency_key: operationKeys.get(a.id, operation),
          ...(operation === "reject" && reason.trim()
            ? { reason: reason.trim() }
            : {}),
        }),
      }),
    onSuccess: (_data, operation) => {
      setShowReject(false);
      invalidateOperations(qc);
      showResult({
        type: "ACTION",
        status: operation.toUpperCase(),
        title: `تم اعتماد الإجراء: ${label(a.type)}`,
        subtitle: `حالة الإجراء: ${label(operation === "approve" ? "APPROVED" : operation === "reject" ? "REJECTED" : "EXECUTED")}`,
        diagnosis:
          operation === "execute"
            ? "تم تنفيذ الإجراء الحتمي على الخادم بنجاح. تذكير أمني: إتمام المهمة الميدانية يتطلب صورة فوتوغرافية جديدة لإعادة الفحص والتوثيق البصري."
            : "تم تسجيل قرار المشرف البشري في سجل التدقيق بنجاح.",
        inspectionId: a.inspection_id,
        orderId: a.order_id,
      });
    },
    onSettled: () => invalidateOperations(qc),
  });
  const taskId = typeof a.execution_details?.task_id === "string" ? a.execution_details.task_id : null;
  const physicalKind = a.type === "CREATE_PICKING_TASK" ? "picking" :
    a.type === "CREATE_REMOVAL_TASK" ? "removal" : null;
  const physical = useQuery({
    queryKey: ["verification-status", order?.id, a.id],
    queryFn: () => api<VerificationStatus>(`/orders/${order?.id}/verification-status`,
      { headers: { Authorization: `Bearer ${token}` } }),
    enabled: !!token && !!order?.id && !!taskId && !!physicalKind,
  });
  const physicalTask = physicalKind === "picking" ?
    physical.data?.picking_tasks.find((task) => task.id === taskId) :
    physical.data?.removal_tasks.find((task) => task.id === taskId);
  const completePhysical = useMutation({
    mutationKey: ["physical-task", taskId],
    mutationFn: () => api<{ status: string }>(`/${physicalKind}-tasks/${taskId}/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ idempotency_key: operationKeys.get(taskId ?? "", "complete") }),
    }),
    onSettled: () => invalidateOperations(qc),
  });
  const controls = actionControls(a);
  const lifecycle = a.lifecycle_state ?? a.status;
  const stale =
    !!inspection && !!order && order.latest_inspection_id !== inspection.id;
  const history = (audit.data ?? []).filter(
    (event) =>
      event.entity_id === a.id ||
      (event.details != null &&
        typeof event.details === "object" &&
        (event.details as Record<string, unknown>).action_id === a.id),
  );
  const related =
    inspection?.discrepancies.filter(
      (d) => !a.product_id || d.product_id === a.product_id,
    ) ?? [];
  return (
    <article className="action-card corrective-action" id={`action-${a.id}`}>
      <div className="action-card-header">
        <span className="action-icon">
          <Workflow size={19} aria-hidden="true" />
        </span>
        <div>
          <strong>{actionName(a.type)}</strong>
          <span>
            {a.order_reference ??
              order?.reference ??
              a.order_id ??
              "Order linked through inspection"}{" "}
            · {a.id.slice(0, 10)}
          </span>
          {order?.data_source === "synthetic_claude" && <span>CLAUDE AI SYNTHETIC · approval pending</span>}
        </div>
        <Badge value={lifecycle} />
      </div>
      {lifecycle !== a.status && (
        <p className="action-record-status">
          Recorded action status: {label(a.status)}
        </p>
      )}
      <div className="action-problem">
        <span>Operational issue</span>
        {related.length ? (
          related.map((d) => <p key={d.id}>{d.description}</p>)
        ) : (
          <p>
            Review the linked inspection and proposal for the supporting
            evidence.
          </p>
        )}
      </div>
      <p className="action-proposal">
        {typeof a.proposal === "string"
          ? a.proposal
          : JSON.stringify(a.proposal)}
      </p>
      {a.quantity != null && (
        <p className="action-quantity">
          Required quantity: <strong>{a.quantity}</strong>
          {a.product_id && <span> · Product {a.product_id}</span>}
        </p>
      )}
      <div className="action-impact">
        <strong>Operational impact</strong>
        <p>{actionImpact(a.type)}</p>
      </div>
      {!!a.evidence_references?.length && (
        <EvidenceReferences
          references={a.evidence_references}
          inspection={inspection}
          orderId={a.order_id ?? order?.id}
        />
      )}
      <div className="button-row">
        {controls.approve && (
          <Button
            variant="success"
            size="sm"
            disabled={!token || inFlight || stale}
            onClick={() => mutation.mutate("approve")}
          >
            <ShieldCheck size={15} aria-hidden="true" />
            Approve
          </Button>
        )}
        {controls.reject && (
          <Button
            variant="destructive"
            size="sm"
            disabled={!token || inFlight || stale}
            onClick={() => setShowReject((value) => !value)}
          >
            <X size={14} aria-hidden="true" />
            Reject
          </Button>
        )}
        {controls.execute && (
          <Button
            variant="primary"
            size="sm"
            disabled={!token || inFlight || stale}
            onClick={() => mutation.mutate("execute")}
          >
            <Play size={14} aria-hidden="true" />
            Execute approved action
          </Button>
        )}
        {inFlight && (
          <LoaderCircle
            className="spin"
            size={16}
            aria-label="Server action pending"
          />
        )}
        <Button asChild variant="outline" size="sm" className="btn-order-action action-view">
          <Link to={`/inspection?id=${encodeURIComponent(a.inspection_id)}`}>
            <FileSearch size={14} aria-hidden="true" />
            <span>View evidence</span>
            <ArrowRight size={13} aria-hidden="true" />
          </Link>
        </Button>
      </div>
      {showReject && controls.reject && (
        <form
          className="rejection-form"
          onSubmit={(event) => {
            event.preventDefault();
            mutation.mutate("reject");
          }}
        >
          <label htmlFor={`reject-${a.id}`}>
            Reason for rejection <span>(optional)</span>
          </label>
          <textarea
            id={`reject-${a.id}`}
            maxLength={500}
            rows={3}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Record the reason for the audit trail"
          />
          <div className="button-row">
            <Button
              variant="destructive"
              size="sm"
              type="submit"
              disabled={!token || inFlight || stale}
            >
              Confirm rejection
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={inFlight}
              onClick={() => setShowReject(false)}
            >
              Cancel
            </Button>
          </div>
        </form>
      )}
      {!token && (controls.approve || controls.reject || controls.execute) && (
        <p className="form-hint">
          <Link className="text-link" to="/settings">
            <LockKeyhole size={13} aria-hidden="true" />
            Set an operator credential to approve, reject, or execute.
          </Link>
        </p>
      )}
      {stale && (
        <p className="form-hint">
          A newer inspection supersedes this proposal. Current server policy
          blocks historical actions.
        </p>
      )}
      {mutation.isError && (
        <p role="alert" className="field-error">
          {mutation.error.message}
        </p>
      )}
      {a.error_details && (
        <div className="provider-error-details">
          <strong>
            {a.error_details.category
              ? label(a.error_details.category)
              : "Action failure"}
          </strong>
          <span>
            {a.error_details.message ??
              "The server recorded an execution failure. Review the audit history."}
          </span>
        </div>
      )}
      {a.rejection_reason && (
        <div className="action-rejection-record">
          <strong>Recorded rejection reason</strong>
          <p>{a.rejection_reason}</p>
        </div>
      )}
      {a.execution_details && (
        <details className="action-execution-result" open>
          <summary>Recorded execution result</summary>
          <pre>{JSON.stringify(a.execution_details, null, 2)}</pre>
        </details>
      )}
      {physicalKind && taskId && (
        <div className={`warehouse-task-box ${physicalTask?.status === "OPEN" ? "is-open" : "is-completed"}`}>
          <div className="task-box-header">
            <div className="task-box-title">
              <Package size={16} aria-hidden="true" />
              <strong>Physical {physicalKind === "picking" ? "Picking" : "Removal"} Task</strong>
            </div>
            <span className={`task-tag ${physicalTask?.status === "OPEN" ? "tag-open" : "tag-completed"}`}>
              {physicalTask ? label(physicalTask.status) : "CHECKING…"}
            </span>
          </div>
          <p style={{ margin: "4px 0 8px 0", fontSize: "11px", color: "var(--foreground-muted)" }}>
            Physical task status: {physicalTask ? label(physicalTask.status) : "Loading"}.
            Reporting completion logs physical handling; <strong>a new photo is mandatory</strong> for visual verification.
          </p>
          {Array.isArray(a.execution_details?.required_product_review_ids) &&
            a.execution_details.required_product_review_ids.length > 0 && (
              <p style={{ fontSize: "11px", color: "#fbbf24", margin: "6px 0" }}>
                Review required products before replacement: {a.execution_details.required_product_review_ids.join(", ")}.
                Their absence was not established by the photo.
              </p>
            )}
          {physicalTask?.status === "OPEN" && (
            <Button
              variant="inspect"
              size="sm"
              disabled={!token || completePhysical.isPending}
              onClick={() => completePhysical.mutate()}
            >
              <Check size={14} aria-hidden="true" />
              {completePhysical.isPending ? "Reporting completion..." : "Report physical task completed"}
            </Button>
          )}
          {completePhysical.isError && (
            <p role="alert" className="field-error" style={{ marginTop: "6px" }}>
              {completePhysical.error.message}
            </p>
          )}
        </div>
      )}
      {["EXECUTED", "AWAITING_REINSPECTION"].includes(lifecycle) ||
        a.status === "EXECUTED" ? (
        <div className="action-reinspection">
          <ShieldCheck size={15} aria-hidden="true" />
          <div>
            <strong>Awaiting new physical evidence</strong>
            <p>
              Execution does not prove correction. Upload a new photo and
              reinspect the latest evidence.
            </p>
            <Link
              className="text-link"
              to={`/inspection?id=${encodeURIComponent(order?.latest_inspection_id ?? a.inspection_id)}`}
            >
              Open inspection
              <ArrowRight size={12} aria-hidden="true" />
            </Link>
          </div>
        </div>
      ) : null}
      <button
        type="button"
        className="action-history-toggle"
        aria-expanded={showHistory}
        onClick={() => setShowHistory((value) => !value)}
      >
        <GitBranch size={14} aria-hidden="true" />
        {showHistory ? "Hide execution history" : "View execution history"}
      </button>
      {showHistory &&
        (audit.isPending ? (
          <Pending />
        ) : audit.isError ? (
          <LoadError error={audit.error} retry={() => audit.refetch()} />
        ) : (
          <RecordedTimeline
            events={history}
            emptyMessage="No action-specific events appear in the retrieved audit records."
          />
        ))}
    </article>
  );
}

export function OperationsWorkspace({ token }: { token: string }) {
  const [params] = useSearchParams();
  const selectedAction = params.get("action");
  const [filter, setFilter] = useState("ALL");
  const activeRequests =
    useIsMutating({ mutationKey: ["investigate"] }) +
    useIsMutating({ mutationKey: ["action"] });
  const q = useQuery({
    queryKey: ["inspections"],
    queryFn: () => api<Inspection[]>("/inspections"),
    refetchInterval: (query) =>
      activeRequests > 0 ||
        query.state.data?.some(
          (i) =>
            i.investigation_status === "RUNNING" ||
            i.actions.some((a) => a.lifecycle_state === "EXECUTING"),
        )
        ? 1500
        : false,
  });
  const orders = useQuery({
    queryKey: ["orders"],
    queryFn: () => api<Order[]>("/orders"),
  });
  const running =
    q.data?.some((i) => i.investigation_status === "RUNNING") ?? false;
  const audit = useQuery({
    queryKey: ["audit"],
    queryFn: () => api<Audit[]>("/audit-events"),
    refetchInterval: running || activeRequests > 0 ? 1500 : false,
  });
  const inspections = q.data ?? [];
  const allActions = inspections.flatMap((i) =>
    i.actions.map((action) => ({ action, inspection: i })),
  );
  const actions = allActions.filter(
    ({ action }) =>
      (!selectedAction || action.id === selectedAction) &&
      (filter === "ALL" ||
        (filter === "REVIEW" && actionControls(action).approve) ||
        (filter === "APPROVED" && action.status === "APPROVED") ||
        (filter === "EXECUTED" && action.status === "EXECUTED") ||
        (filter === "REJECTED" && action.status === "REJECTED")),
  );
  const investigations = inspections.filter(
    (i) =>
      i.investigation_id ||
      i.investigation ||
      (i.investigation_status && i.investigation_status !== "NOT_STARTED") ||
      (["NEEDS_REVIEW", "HELD"].includes(i.status) &&
        i.discrepancies.length > 0 &&
        orders.data?.find((o) => o.id === i.order_id)?.latest_inspection_id ===
        i.id),
  );
  return (
    <>
      <div className="operations-summary">
        {[
          {
            label: "Active investigations",
            count: inspections.filter(
              (i) => i.investigation_status === "RUNNING",
            ).length,
          },
          {
            label: "Awaiting approval",
            count: allActions.filter(
              ({ action }) => actionControls(action).approve,
            ).length,
          },
          {
            label: "Approved actions",
            count: allActions.filter(
              ({ action }) => action.status === "APPROVED",
            ).length,
          },
          {
            label: "Awaiting reinspection",
            count: allActions.filter(
              ({ action }) =>
                action.lifecycle_state === "AWAITING_REINSPECTION",
            ).length,
          },
        ].map((metric) => (
          <div key={metric.label}>
            <span>{metric.label}</span>
            <strong>{q.isSuccess ? metric.count : "—"}</strong>
          </div>
        ))}
      </div>
      <Surface
        title="Investigations"
        subtitle="Persisted decisions and read-tool activity from actual inspection evidence."
        action={
          <span className="count-badge">
            {q.isSuccess ? investigations.length : "—"}
          </span>
        }
      >
        {q.isPending ? (
          <Pending />
        ) : q.isError ? (
          <LoadError error={q.error} retry={() => q.refetch()} />
        ) : investigations.length ? (
          <div className="investigation-grid">
            {investigations.map((i) => (
              <InvestigationCard
                key={i.id}
                inspection={i}
                token={token}
                order={orders.data?.find((o) => o.id === i.order_id)}
                isCurrent={
                  orders.data?.find((o) => o.id === i.order_id)
                    ?.latest_inspection_id === i.id
                }
              />
            ))}
          </div>
        ) : (
          <div className="empty">
            <div className="empty-icon">
              <Sparkles size={24} aria-hidden="true" />
            </div>
            <h3>No investigations recorded</h3>
            <p>
              Investigations become available when the latest inspection has
              unresolved evidence.
            </p>
            <Button asChild variant="outline" size="sm">
              <Link to="/inspection">
                Open visual inspection
                <ArrowRight size={14} aria-hidden="true" />
              </Link>
            </Button>
          </div>
        )}
      </Surface>
      {orders.isError && (
        <LoadError error={orders.error} retry={() => orders.refetch()} />
      )}
      <div className="operations-grid operations-workspace-grid">
        <Surface
          title="Corrective action queue"
          subtitle="Review proposals, authorize allowed actions, and inspect their recorded outcomes."
          action={
            <select
              aria-label="Filter corrective actions"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            >
              <option value="ALL">All actions</option>
              <option value="REVIEW">Awaiting approval</option>
              <option value="APPROVED">Approved</option>
              <option value="EXECUTED">Executed</option>
              <option value="REJECTED">Rejected</option>
            </select>
          }
        >
          {selectedAction && (
            <div className="action-filter-note">
              <span>Showing linked action</span>
              <Link className="text-link" to="/operations">
                Show all actions
              </Link>
            </div>
          )}
          {q.isPending ? (
            <Pending />
          ) : q.isError ? (
            <LoadError error={q.error} retry={() => q.refetch()} />
          ) : actions.length ? (
            <div className="results-content">
              {actions.map(({ action, inspection }) => (
                <CorrectiveActionCard
                  key={action.id}
                  action={action}
                  inspection={inspection}
                  order={orders.data?.find((o) => o.id === inspection.order_id)}
                  token={token}
                />
              ))}
            </div>
          ) : (
            <div className="empty">
              <div className="empty-icon">
                <Workflow size={24} aria-hidden="true" />
              </div>
              <h3>No actions in this view</h3>
              <p>
                Only server-validated proposals from recorded evidence appear
                here.
              </p>
            </div>
          )}
        </Surface>
        <Surface
          title="Agent activity & audit"
          subtitle="Actual persisted timestamps, tool results, decisions, and operator events."
          action={<Activity size={18} className="muted" aria-hidden="true" />}
        >
          {audit.isPending ? (
            <Pending />
          ) : audit.isError ? (
            <LoadError error={audit.error} retry={() => audit.refetch()} />
          ) : (
            <RecordedTimeline events={audit.data} />
          )}
        </Surface>
      </div>
    </>
  );
}
