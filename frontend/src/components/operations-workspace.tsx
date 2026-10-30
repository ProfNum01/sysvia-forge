import { useState } from "react";
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
  CircleAlert,
  FileSearch,
  GitBranch,
  LoaderCircle,
  LockKeyhole,
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
import type { Action, Audit, Inspection, Order } from "../types";

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
        return href && inspection ? (
          <Link key={`${reference}-${index}`} to={href}>
            {reference}
            <ArrowRight size={11} aria-hidden="true" />
          </Link>
        ) : (
          <span key={`${reference}-${index}`}>{reference}</span>
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
  if (!events.length)
    return <p className="operations-empty-copy">{emptyMessage}</p>;
  return (
    <ol className="audit-list operations-timeline">
      {events.map((event) => (
        <li key={event.id} id={`audit-${event.id}`}>
          <div className="audit-symbol">
            <Activity size={14} aria-hidden="true" />
          </div>
          <div>
            <strong>{label(event.event_type)}</strong>
            <time dateTime={event.created_at}>
              {formatTime(event.created_at)}
              {event.actor ? ` · ${event.actor}` : ""}
            </time>
            <details>
              <summary>Recorded details</summary>
              <pre>{JSON.stringify(event.details, null, 2)}</pre>
            </details>
          </div>
        </li>
      ))}
    </ol>
  );
}

function invalidateOperations(qc: ReturnType<typeof useQueryClient>) {
  for (const key of ["inspections", "inspection", "audit", "orders", "summary"])
    qc.invalidateQueries({ queryKey: [key] });
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
    },
    onSettled: () => invalidateOperations(qc),
  });
  const status =
    i.investigation_status ?? (i.investigation ? "COMPLETED" : "NOT_STARTED");
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
        </div>
        <Badge value={status} />
      </div>
      <div className="investigation-context">
        <span>Inspection outcome</span>
        <Badge value={i.status} />
        {i.reconciliation_status && <Badge value={i.reconciliation_status} />}
      </div>
      {result?.decision && (
        <div className="investigation-decision">
          <span>Persisted decision</span>
          <strong>{label(result.decision)}</strong>
        </div>
      )}
      {summary ? (
        <p className="investigation-summary">{summary}</p>
      ) : (
        <p className="operations-empty-copy">
          {running
            ? "Investigation is active. Tool activity appears only after the backend records it."
            : "Unresolved evidence can be investigated through read-only order, inventory, inspection, pending-action, and history tools. Ambiguous visual evidence remains uncertain."}
        </p>
      )}
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
        <Button asChild variant="outline" size="sm">
          <Link to={`/inspection?id=${encodeURIComponent(i.id)}`}>
            <FileSearch size={14} aria-hidden="true" />
            View evidence
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
    onSuccess: () => {
      setShowReject(false);
      invalidateOperations(qc);
    },
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
            variant="outline"
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
        <Button asChild variant="ghost" size="sm">
          <Link to={`/inspection?id=${encodeURIComponent(a.inspection_id)}`}>
            View evidence
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
