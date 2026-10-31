import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import ReactDOM from "react-dom/client";
import {
  BrowserRouter,
  NavLink,
  Route,
  Routes,
  Link,
  useSearchParams,
} from "react-router-dom";
import {
  QueryClient,
  QueryClientProvider,
  useMutation,
  useIsMutating,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  Box,
  Check,
  CheckCheck,
  ChevronRight,
  CircleAlert,
  CircleCheck,
  Camera,
  Clock3,
  Database,
  Presentation,
  FileSearch,
  Fingerprint,
  GitBranch,
  ImagePlus,
  LayoutDashboard,
  LoaderCircle,
  LockKeyhole,
  Menu,
  Package,
  RefreshCw,
  ScanLine,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Button } from "./components/ui/button";
import {
  CorrectiveActionCard,
  InvestigationCard,
  OperationsWorkspace,
} from "./components/operations-workspace";
import {
  EvidenceViewer,
  InspectionProgress,
  ProductComparison,
} from "./components/inspection-evidence";
import { DemoWorkspace } from "./components/demo-workspace";
import { api, formatTime, label } from "./lib/api";
import { validateImage } from "./lib/validation";
import {
  buildInspectionUpload,
  canAnalyzeInspection,
  canReinspectInspection,
  inspectionHref,
  UploadIdempotency,
} from "./lib/workflow";
import type {
  Action,
  Audit,
  Inspection,
  MetaStatus,
  Order,
  Product,
  Summary,
} from "./types";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 15000 },
  },
});
const TokenContext = createContext({
  token: "",
  setToken: (_value: string) => {},
});
function TokenProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState("");
  return (
    <TokenContext.Provider value={{ token, setToken }}>
      {children}
    </TokenContext.Provider>
  );
}
const nav = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/orders", label: "Orders", icon: Package },
  { to: "/inspection", label: "Visual Inspection", icon: ScanLine },
  { to: "/operations", label: "AI Operations", icon: Sparkles },
  { to: "/history", label: "Verification History", icon: FileSearch },
  { to: "/demo", label: "Demo Workspace", icon: Presentation },
  { to: "/settings", label: "Settings", icon: Settings2 },
];
function Status({ value }: { value: string }) {
  return (
    <span
      className={`status status-${value.toLowerCase().replaceAll("_", "-")}`}
    >
      <span />
      {value === "MISMATCH_DETECTED" ? "MISMATCH DETECTED" : label(value)}
    </span>
  );
}
function Empty({
  icon: Icon = ScanLine,
  title,
  children,
}: {
  icon?: typeof ScanLine;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Icon aria-hidden="true" size={25} />
      </div>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
function ErrorState({ error, retry }: { error: Error; retry?: () => void }) {
  return (
    <div role="alert" className="error-state">
      <CircleAlert aria-hidden="true" size={20} />
      <div>
        <strong>Couldn’t load this workspace</strong>
        <p>{error.message}</p>
      </div>
      {retry && (
        <Button variant="outline" size="sm" onClick={retry}>
          <RefreshCw size={14} aria-hidden="true" />
          Retry
        </Button>
      )}
    </div>
  );
}
function Loading() {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={20} aria-hidden="true" />
      Loading workspace data…
    </div>
  );
}
function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
function Panel({
  title,
  subtitle,
  action,
  children,
  className = "",
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
function Shell() {
  const [open, setOpen] = useState(false);
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api<{ status: string; database: string }>("/health"),
    refetchInterval: 30000,
  });
  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      {open && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
        />
      )}
      <aside className={`sidebar ${open ? "is-open" : ""}`}>
        <Link className="brand" to="/" onClick={() => setOpen(false)}>
          <div className="brand-mark">
            <ScanLine size={25} aria-hidden="true" />
          </div>
          <div>
            <span>
              SYSVIA<span className="brand-dot">.</span>
            </span>
            <strong>ProofSight</strong>
          </div>
        </Link>
        <div className="workspace-label">
          WORKSPACE <span>LOCAL</span>
        </div>
        <nav aria-label="Main navigation">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                `nav-link ${isActive ? "active" : ""}`
              }
            >
              <n.icon size={19} aria-hidden="true" />
              {n.label}
              {n.to === "/inspection" && <span className="nav-dot" />}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="trust-card">
            <ShieldCheck size={21} aria-hidden="true" />
            <strong>Evidence before confidence.</strong>
            <p>Every decision starts with what can actually be observed.</p>
          </div>
          <div className="workspace-user">
            <div className="avatar">S</div>
            <div>
              <strong>Local workspace</strong>
              <span>Startup Track · 2026</span>
            </div>
            <LockKeyhole size={15} aria-hidden="true" />
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="topbar-left">
            <Button
              variant="ghost"
              size="icon"
              className="mobile-menu"
              onClick={() => setOpen(!open)}
              aria-label="Open navigation"
              aria-expanded={open}
            >
              <Menu size={21} />
            </Button>
            <span className="breadcrumb">
              Workspace <ChevronRight size={14} aria-hidden="true" />{" "}
              <strong>Operations console</strong>
            </span>
          </div>
          <div className="topbar-right">
            <span className="environment">
              <span
                className={
                  health.isSuccess ? "connection-dot" : "connection-dot offline"
                }
              />
              {health.isSuccess
                ? "Local API connected"
                : health.isPending
                  ? "Connecting to local API"
                  : "Local API offline"}
            </span>
            <span className="topbar-divider" />
            <span className="local-badge">
              <LockKeyhole size={12} aria-hidden="true" />
              Local-first
            </span>
            <div className="avatar small">S</div>
          </div>
        </header>
        <main id="main" tabIndex={-1}>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/orders" element={<Orders />} />
            <Route path="/inspection" element={<InspectionPage />} />
            <Route path="/operations" element={<Operations />} />
            <Route path="/history" element={<History />} />
            <Route path="/demo" element={<Demo />} />
            <Route path="/settings" element={<Settings />} />
            <Route
              path="*"
              element={
                <Empty title="Page not found">
                  Return to <Link to="/">the overview</Link>.
                </Empty>
              }
            />
          </Routes>
          <footer>
            <span>
              SYSVIA ProofSight <span className="footer-separator">/</span> The
              AI That Verifies Reality
            </span>
            <span>Evidence-backed. Human-approved.</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
function Overview() {
  const q = useQuery({
    queryKey: ["summary"],
    queryFn: () => api<Summary>("/dashboard/summary"),
  });
  const data = q.data;
  return (
    <>
      <PageHeading
        eyebrow="OPERATIONAL INTELLIGENCE"
        title="See the order. Verify the reality."
        description="One workspace to connect physical evidence, AI reasoning, and accountable action."
        action={
          <Button asChild>
            <Link to="/inspection">
              <ScanLine size={17} aria-hidden="true" />
              New inspection
              <ArrowRight size={16} aria-hidden="true" />
            </Link>
          </Button>
        }
      />
      <div className="notice">
        <Database size={15} aria-hidden="true" />
        <span>
          <strong>Development workspace</strong> · Seeded orders are synthetic.
          Inspection outcomes appear only after real analysis.
        </span>
        <span className="notice-tag">SANDBOX DATA</span>
      </div>
      {q.isPending ? (
        <Loading />
      ) : q.isError ? (
        <ErrorState error={q.error} retry={() => q.refetch()} />
      ) : (
        data && (
          <>
            <div className="metric-grid">
              {[
                {
                  label: "Total orders",
                  value: data.total_orders,
                  icon: Package,
                  note: "Synthetic order workspace",
                  color: "blue",
                },
                {
                  label: "Awaiting inspection",
                  value: data.pending_inspections,
                  icon: ScanLine,
                  note: "Evidence still required",
                  color: "violet",
                },
                {
                  label: "Verified orders",
                  value: data.verified_orders,
                  icon: ShieldCheck,
                  note: "Evidence-backed reconciliation",
                  color: "green",
                },
                {
                  label: "Active discrepancies",
                  value: data.active_discrepancies,
                  icon: CircleAlert,
                  note: "Require attention or review",
                  color: "amber",
                },
                {
                  label: "Orders on hold",
                  value: data.orders_on_hold,
                  icon: LockKeyhole,
                  note: "Shipping gate is active",
                  color: "amber",
                },
                {
                  label: "Human reviews",
                  value: data.pending_human_reviews,
                  icon: FileSearch,
                  note: "Uncertain evidence or escalation",
                  color: "violet",
                },
              ].map((m) => (
                <div className="metric" key={m.label}>
                  <div className="metric-top">
                    <span>{m.label}</span>
                    <div className={`metric-icon ${m.color}`}>
                      <m.icon size={18} aria-hidden="true" />
                    </div>
                  </div>
                  <div className="metric-value">
                    {m.value.toLocaleString()}
                    <span className={`metric-trace ${m.color}`}>—</span>
                  </div>
                  <div className="metric-note">
                    <span className={`tiny-dot ${m.color}`} />
                    {m.note}
                  </div>
                </div>
              ))}
            </div>
            <Panel title="Attention required" subtitle="Current orders with unresolved evidence or an active hold."
              action={<span className="count-badge">{data.attention_required.length}</span>}>
              {data.attention_required.length ? <div className="attention-list">
                {data.attention_required.map((item) => <Link className="attention-row"
                  key={item.order_id} to={`/inspection?id=${encodeURIComponent(item.inspection_id)}`}>
                  <span><strong>{item.order_reference}</strong><small>{item.issue_types.length ?
                    item.issue_types.map(label).join(", ") : "Order hold or reinspection required"}</small></span>
                  <span className="attention-meta"><Status value={item.inspection_status} />
                    {item.human_review_required && <span>Human review</span>}</span>
                  <ArrowRight size={16} aria-hidden="true" />
                </Link>)}
              </div> : <Empty icon={ShieldCheck} title="No active issues">
                Orders requiring action will appear here from current inspection records.
              </Empty>}
            </Panel>
            <div className="overview-grid">
              <Panel
                title="Verification pipeline"
                subtitle="From intent to evidence. Every step accounted for."
                action={
                  <span className="subtle-label">THE PROOFSIGHT LOOP</span>
                }
                className="pipeline-panel"
              >
                <div className="pipeline">
                  {[
                    {
                      icon: Package,
                      name: "Order",
                      detail: "Define the expected",
                    },
                    {
                      icon: ScanLine,
                      name: "Observe",
                      detail: "Inspect actual evidence",
                    },
                    {
                      icon: Sparkles,
                      name: "Investigate",
                      detail: "Propose a resolution",
                    },
                    {
                      icon: CheckCheck,
                      name: "Reverify",
                      detail: "Confirm with new evidence",
                    },
                  ].map((s, i) => (
                    <div className="pipeline-step" key={s.name}>
                      <div
                        className={`step-symbol ${i === 1 ? "highlight" : ""}`}
                      >
                        <s.icon size={22} aria-hidden="true" />
                        {i < 3 && <span className="step-connector" />}
                      </div>
                      <strong>{s.name}</strong>
                      <span>{s.detail}</span>
                    </div>
                  ))}
                </div>
                <div className="pipeline-note">
                  <Fingerprint size={16} aria-hidden="true" />A completed task
                  is never proof of correction. A new image closes the loop.
                </div>
              </Panel>
              <Panel title="Order status" subtitle="Current database snapshot">
                <div
                  className="chart-frame"
                  role="img"
                  aria-label={data.order_status_distribution
                    .map((x) => `${label(x.status)}: ${x.count}`)
                    .join(", ")}
                >
                  {data.order_status_distribution.length ? (
                    <ResponsiveContainer width="100%" height={180}>
                      <BarChart
                        data={data.order_status_distribution}
                        layout="vertical"
                        margin={{ left: 0, right: 20, top: 12, bottom: 0 }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 5"
                          stroke="#253145"
                          horizontal={false}
                        />
                        <XAxis
                          type="number"
                          allowDecimals={false}
                          tick={{ fill: "#96a4bc", fontSize: 11 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          type="category"
                          dataKey="status"
                          width={100}
                          tickFormatter={label}
                          tick={{ fill: "#b6c2d7", fontSize: 11 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip
                          cursor={{ fill: "#192337" }}
                          contentStyle={{
                            background: "#111b2b",
                            border: "1px solid #2b3b54",
                            borderRadius: 8,
                            color: "#eaf0fc",
                          }}
                          labelFormatter={(v) => label(String(v))}
                        />
                        <Bar
                          dataKey="count"
                          name="Orders"
                          fill="#5683ff"
                          radius={[0, 4, 4, 0]}
                          barSize={17}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <Empty title="No order data">
                      Order status appears once orders exist.
                    </Empty>
                  )}
                </div>
              </Panel>
            </div>
            <div className="overview-grid lower-grid">
              <Panel
                title="Recent inspections"
                subtitle="A traceable record of what was actually observed."
                action={
                  <Link className="text-link" to="/history">
                    View history
                    <ArrowRight size={14} aria-hidden="true" />
                  </Link>
                }
              >
                {data.recent_inspections.length ? (
                  <InspectionTable
                    inspections={data.recent_inspections.slice(0, 5)}
                  />
                ) : (
                  <Empty title="Your first verification starts here">
                    Upload a rights-cleared image to inspect an order against
                    physical evidence.
                    <Button asChild variant="outline" size="sm">
                      <Link to="/inspection">
                        <ImagePlus size={15} aria-hidden="true" />
                        Start an inspection
                      </Link>
                    </Button>
                  </Empty>
                )}
              </Panel>
              <Panel
                title="Operations activity"
                subtitle="Recorded events, never simulated thoughts."
                action={
                  <Activity size={17} className="muted" aria-hidden="true" />
                }
              >
                {data.agent_activity.length ? (
                  <AuditList events={data.agent_activity.slice(0, 4)} />
                ) : (
                  <Empty icon={Activity} title="No activity yet">
                    Investigation, approval, and execution events will appear
                    here after they occur.
                  </Empty>
                )}
              </Panel>
            </div>
          </>
        )
      )}
      <div className="principle-strip">
        <ShieldCheck size={23} aria-hidden="true" />
        <div>
          <strong>Confidence has to be earned.</strong>
          <p>
            Not observed does not mean absent. Uncertain evidence stays in
            review.
          </p>
        </div>
        <span>BUILT FOR ACCOUNTABILITY</span>
      </div>
    </>
  );
}
function Orders() {
  const [orderParams] = useSearchParams();
  const q = useQuery({
    queryKey: ["orders"],
    queryFn: () => api<Order[]>("/orders"),
  });
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string | null>(
    orderParams.get("order"),
  );
  const rows =
    q.data?.filter((o) =>
      `${o.reference} ${o.customer} ${o.status}`
        .toLowerCase()
        .includes(search.toLowerCase()),
    ) ?? [];
  const order = q.data?.find((o) => o.id === selected);
  return (
    <>
      <PageHeading
        eyebrow="EXPECTED REALITY"
        title="Orders"
        description="Define what should be there before checking what actually is."
        action={
          <span className="synthetic-label">
            <Database size={14} aria-hidden="true" />
            Synthetic seed data
          </span>
        }
      />
      <Panel
        title="Order workspace"
        subtitle="Select an order to inspect its expected items."
        action={
          <div className="search-field">
            <Search size={16} aria-hidden="true" />
            <input
              aria-label="Search orders"
              placeholder="Search orders…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        }
      >
        {q.isPending ? (
          <Loading />
        ) : q.isError ? (
          <ErrorState error={q.error} retry={() => q.refetch()} />
        ) : rows.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Customer</th>
                  <th>Items / units</th>
                  <th>Verification</th>
                  <th>Preparation</th>
                  <th>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((o) => (
                  <tr key={o.id}>
                    <td>
                      <button
                        className="table-link"
                        onClick={() => setSelected(o.id)}
                      >
                        {o.reference}
                      </button>
                      <span className="cell-subtitle">
                        {formatTime(o.created_at)}
                      </span>
                    </td>
                    <td>{o.customer}</td>
                    <td>
                      {o.items.length} /{" "}
                      {o.items.reduce((n, i) => n + i.quantity, 0)}
                    </td>
                    <td>
                      <Status value={o.status} />
                    </td>
                    <td className="muted">{label(o.preparation_status)}</td>
                    <td>
                      <Button asChild variant="ghost" size="sm">
                        <Link to={inspectionHref(o)}>
                          {o.latest_inspection_id
                            ? "View inspection"
                            : "Inspect"}
                          <ArrowRight size={14} aria-hidden="true" />
                        </Link>
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            icon={Package}
            title={search ? "No matching orders" : "No orders available"}
          >
            {search
              ? "Try a different search."
              : "Load synthetic seed orders through the backend to begin."}
          </Empty>
        )}
      </Panel>
      {order && (
        <Panel
          title={order.reference}
          subtitle={`${order.customer} · Expected items`}
          action={
            <Button
              variant="ghost"
              size="icon"
              aria-label="Close order details"
              onClick={() => setSelected(null)}
            >
              <X size={17} />
            </Button>
          }
        >
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Product</th>
                  <th>SKU</th>
                  <th>Color</th>
                  <th>Expected quantity</th>
                </tr>
              </thead>
              <tbody>
                {order.items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.product.name}</td>
                    <td className="mono">{item.product.sku}</td>
                    <td>{item.product.color ?? "Not specified"}</td>
                    <td>{item.quantity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </>
  );
}
function InspectionTable({ inspections }: { inspections: Inspection[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Inspection / order</th>
            <th>Result</th>
            <th>Recorded</th>
            <th>
              <span className="sr-only">View</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {inspections.map((i) => (
            <tr key={i.id}>
              <td>
                <Link
                  className="table-link"
                  to={`/inspection?id=${encodeURIComponent(i.id)}`}
                >
                  {i.id.slice(0, 12)}
                </Link>
                <span className="cell-subtitle">
                  Order {i.order_id.slice(0, 12)}
                </span>
              </td>
              <td>
                <Status value={i.status} />
              </td>
              <td className="muted">{formatTime(i.created_at)}</td>
              <td>
                <Link
                  className="icon-link"
                  aria-label={`View inspection ${i.id}`}
                  to={`/inspection?id=${encodeURIComponent(i.id)}`}
                >
                  <ChevronRight size={17} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function InspectionPage() {
  const [params, setParams] = useSearchParams();
  const id = params.get("id");
  const demoAsset = params.get("demo");
  const { token } = useContext(TokenContext);
  const initialOrder = params.get("order") ?? "";
  const [orderId, setOrderId] = useState(initialOrder);
  const [file, setFile] = useState<File | null>(null);
  const [rights, setRights] = useState(false);
  const [preview, setPreview] = useState("");
  const [formError, setFormError] = useState("");
  const [reinspect, setReinspect] = useState(false);
  const [analysisRequested, setAnalysisRequested] = useState(false);
  const [selectedRegionIds, setSelectedRegionIds] = useState<string[]>([]);
  const fileInput = useRef<HTMLInputElement>(null);
  const cameraInput = useRef<HTMLInputElement>(null);
  const uploadIdentity = useRef(new UploadIdempotency());
  useEffect(() => {
    uploadIdentity.current.reset();
  }, [file, orderId, id, reinspect]);
  const qc = useQueryClient();
  const orders = useQuery({
    queryKey: ["orders"],
    queryFn: () => api<Order[]>("/orders"),
  });
  const investigationPending =
    useIsMutating({ mutationKey: ["investigate", id] }) > 0;
  const inspection = useQuery({
    queryKey: ["inspection", id],
    queryFn: () => api<Inspection>(`/inspections/${id}`),
    enabled: !!id,
    refetchInterval: (query) =>
      analysisRequested ||
      investigationPending ||
      query.state.data?.status === "ANALYZING" ||
      query.state.data?.investigation_status === "RUNNING"
        ? 1000
        : false,
  });
  const catalog = useQuery({
    queryKey: ["products"],
    queryFn: () => api<Product[]>("/products"),
  });
  useEffect(() => {
    if (!file) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  useEffect(() => {
    setReinspect(false);
    setFormError("");
    setSelectedRegionIds(params.get("region") ? [params.get("region")!] : []);
  }, [id, params]);
  useEffect(() => {
    if (!demoAsset) return;
    const controller = new AbortController();
    setReinspect(!!id);
    setFormError("");
    fetch(`/api/demo/assets/${encodeURIComponent(demoAsset)}`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("The selected synthetic asset is unavailable on the backend.");
        const blob = await response.blob();
        if (blob.type !== "image/png") throw new Error("The demo asset was not a PNG image.");
        setFile(new File([blob], `proofsight-demo-${demoAsset}.png`, { type: "image/png" }));
        setRights(true);
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setFormError(error instanceof Error ? error.message : "Demo asset could not be loaded.");
      });
    return () => controller.abort();
  }, [demoAsset, id]);
  const upload = useMutation({
    mutationFn: async () => {
      const error = validateImage(file, rights);
      if (error) throw new Error(error);
      if (!reinspect && !orderId)
        throw new Error("Select an order before uploading.");
      const body = buildInspectionUpload(
        file!,
        reinspect ? undefined : orderId,
      );
      return api<Inspection>(
        reinspect ? `/inspections/${id}/reinspect` : "/inspections",
        {
          method: "POST",
          body,
          headers: {
            Authorization: `Bearer ${token}`,
            "Idempotency-Key": uploadIdentity.current.keyFor(
              file!,
              reinspect ? (inspection.data?.order_id ?? orderId) : orderId,
              reinspect ? id : null,
            ),
          },
        },
      );
    },
    onSuccess: (data) => {
      qc.setQueryData(["inspection", data.id], data);
      setParams({ id: data.id });
      setFile(null);
      setRights(false);
      qc.invalidateQueries({ queryKey: ["inspections"] });
      qc.invalidateQueries({ queryKey: ["summary"] });
      qc.invalidateQueries({ queryKey: ["orders"] });
    },
  });
  const analyze = useMutation({
    onMutate: () => setAnalysisRequested(true),
    mutationFn: () =>
      api<Inspection>(`/inspections/${id}/analyze`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      }),
    onSuccess: (data) => {
      qc.setQueryData(["inspection", id], data);
      qc.invalidateQueries({ queryKey: ["summary"] });
      qc.invalidateQueries({ queryKey: ["inspections"] });
      qc.invalidateQueries({ queryKey: ["orders"] });
    },
    onSettled: () => {
      setAnalysisRequested(false);
      qc.invalidateQueries({ queryKey: ["inspection", id] });
      qc.invalidateQueries({ queryKey: ["audit"] });
    },
  });
  const current = inspection.data;
  const selected = orders.data?.find(
    (o) => o.id === (current?.order_id ?? orderId),
  );
  useEffect(() => {
    if (!id && selected?.latest_inspection_id) {
      setParams({ id: selected.latest_inspection_id });
      setFile(null);
      setRights(false);
    }
  }, [id, selected?.latest_inspection_id, setParams]);
  return (
    <>
      <PageHeading
        eyebrow="PHYSICAL EVIDENCE"
        title="Visual Inspection"
        description="Compare the expected order with a real image. Let evidence set the confidence."
        action={
          id && (
            <Button
              variant="outline"
              onClick={() => {
                setParams({});
                setOrderId("");
                setFile(null);
                setRights(false);
                setReinspect(false);
              }}
            >
              <ImagePlus size={16} aria-hidden="true" />
              New inspection
            </Button>
          )
        }
      />
      <div className="inspection-layout">
        <div>
          <Panel
            title={
              reinspect
                ? "Upload correction evidence"
                : id
                  ? "Captured evidence"
                  : "Create an inspection"
            }
            subtitle={
              reinspect
                ? "A new image creates a separate inspection and preserves the original."
                : "Only synthetic or rights-cleared imagery. PNG, JPEG, or WebP · up to 15 MiB."
            }
          >
            {!id || reinspect ? (
              <form
                className="upload-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  setFormError("");
                  const error = validateImage(file, rights);
                  if (error) {
                    setFormError(error);
                    return;
                  }
                  upload.mutate();
                }}
              >
                {!reinspect && (
                  <div className="field">
                    <label htmlFor="order-select">Order to inspect</label>
                    <select
                      id="order-select"
                      value={orderId}
                      onChange={(e) => setOrderId(e.target.value)}
                      required
                      disabled={orders.isPending || orders.isError}
                    >
                      <option value="">
                        {orders.isPending
                          ? "Loading orders…"
                          : "Select an order"}
                      </option>
                      {orders.data?.map((o) => (
                        <option key={o.id} value={o.id}>
                          {o.reference} · {o.customer}
                        </option>
                      ))}
                    </select>
                    {orders.isError && (
                      <p className="field-error">{orders.error.message}</p>
                    )}
                  </div>
                )}
                <input
                  ref={fileInput}
                  id="inspection-image"
                  className="sr-only"
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(e) => {
                    setFile(e.target.files?.[0] ?? null);
                    setFormError("");
                  }}
                />
                <input
                  ref={cameraInput}
                  id="inspection-camera"
                  className="sr-only"
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  capture="environment"
                  onChange={(event) => {
                    setFile(event.target.files?.[0] ?? null);
                    setFormError("");
                  }}
                />
                <button
                  type="button"
                  className={`upload-zone ${preview ? "has-preview" : ""}`}
                  onClick={() => fileInput.current?.click()}
                >
                  {preview ? (
                    <>
                      <img
                        src={preview}
                        alt="Selected image preview for inspection"
                      />
                      <span className="preview-caption">
                        <ImagePlus size={15} aria-hidden="true" />
                        {file?.name} · Change image
                      </span>
                    </>
                  ) : (
                    <>
                      <div className="upload-target">
                        <ScanLine size={34} aria-hidden="true" />
                        <span className="scan-corner c1" />
                        <span className="scan-corner c2" />
                        <span className="scan-corner c3" />
                        <span className="scan-corner c4" />
                      </div>
                      <strong>Bring reality into focus</strong>
                      <span>Choose an image of the prepared order</span>
                      <span className="upload-file-hint">
                        <Upload size={14} aria-hidden="true" />
                        Browse files
                      </span>
                    </>
                  )}
                </button>
                <div className="camera-capture-control">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => cameraInput.current?.click()}
                  >
                    <Camera size={16} aria-hidden="true" />
                    Capture with device camera
                  </Button>
                  <p className="form-hint">
                    Opens your device’s capture chooser. Camera access is
                    controlled by your browser; supported images follow the same
                    validation.
                  </p>
                </div>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={rights}
                    onChange={(e) => setRights(e.target.checked)}
                  />
                  <span>
                    I confirm this image is synthetic or I have the rights to
                    use it, and it contains no private customer information.
                  </span>
                </label>
                {(formError || upload.error) && (
                  <p role="alert" className="field-error">
                    {formError || upload.error?.message}
                  </p>
                )}
                <Button
                  type="submit"
                  disabled={
                    !token || upload.isPending || (!reinspect && orders.isError)
                  }
                >
                  {upload.isPending ? (
                    <LoaderCircle
                      className="spin"
                      size={16}
                      aria-hidden="true"
                    />
                  ) : (
                    <ArrowDownToLine size={16} aria-hidden="true" />
                  )}
                  {upload.isPending
                    ? "Uploading evidence…"
                    : "Save inspection image"}
                </Button>
                <p className="form-hint">
                  Saving an image does not analyze or verify it. Analysis is a
                  separate, explicit step.
                </p>
                {!token && (
                  <p className="form-hint">
                    An operator credential is required to upload evidence.{" "}
                    <Link className="text-link" to="/settings">
                      Set session token in Settings
                    </Link>
                    .
                  </p>
                )}
              </form>
            ) : inspection.isPending ? (
              <Loading />
            ) : inspection.isError ? (
              <ErrorState
                error={inspection.error}
                retry={() => inspection.refetch()}
              />
            ) : (
              current && (
                <div className="captured-evidence">
                  <EvidenceViewer
                    key={current.id}
                    inspection={current}
                    products={
                      catalog.data ??
                      selected?.items.map((item) => item.product) ??
                      []
                    }
                    selectedRegionIds={selectedRegionIds}
                    onSelectRegion={setSelectedRegionIds}
                  />
                  <div className="evidence-meta">
                    <Status value={current.status} />
                    {current.reconciliation_status && (
                      <Status value={current.reconciliation_status} />
                    )}
                    <span>{formatTime(current.created_at)}</span>
                  </div>
                  <dl className="metadata">
                    <div>
                      <dt>Inspection ID</dt>
                      <dd>{current.id}</dd>
                    </div>
                    <div>
                      <dt>Photo ID</dt>
                      <dd>{current.photo_id}</dd>
                    </div>
                    {current.previous_inspection_id && (
                      <div>
                        <dt>Previous inspection</dt>
                        <dd>
                          <Link
                            to={`/inspection?id=${encodeURIComponent(current.previous_inspection_id)}`}
                          >
                            {current.previous_inspection_id}
                          </Link>
                        </dd>
                      </div>
                    )}
                  </dl>
                  <InspectionProgress inspection={current} />
                  {current.provider_error && (
                    <div className="error-state" role="alert">
                      <CircleAlert size={19} aria-hidden="true" />
                      <div>
                        <strong>Provider analysis unavailable</strong>
                        <p>{current.provider_error}</p>
                        <p>
                          No fallback or simulated result has been substituted.
                        </p>
                      </div>
                    </div>
                  )}
                  <div className="button-row">
                    <Button
                      onClick={() => analyze.mutate()}
                      disabled={
                        !token ||
                        analyze.isPending ||
                        !canAnalyzeInspection(current, selected)
                      }
                    >
                      {analyze.isPending ? (
                        <LoaderCircle
                          className="spin"
                          size={16}
                          aria-hidden="true"
                        />
                      ) : (
                        <ScanLine size={16} aria-hidden="true" />
                      )}
                      {analyze.isPending
                        ? "Analyzing real evidence…"
                        : "Start AI Inspection"}
                    </Button>
                    <Button
                      variant="outline"
                      disabled={
                        !canReinspectInspection(
                          current,
                          selected?.latest_inspection_id,
                        ) || analyze.isPending
                      }
                      onClick={() => {
                        setReinspect(true);
                        setRights(false);
                        setFile(null);
                      }}
                    >
                      <ImagePlus size={16} aria-hidden="true" />
                      Upload new evidence
                    </Button>
                  </div>
                  <p className="form-hint">
                    Explicitly starts paid Meta inference: Muse visual analysis
                    and SAM segmentation limited to visible catalog types.
                  </p>
                  {current.status === "PROVIDER_ERROR" && (
                    <p className="form-hint">
                      Review the provider error and correct configuration if
                      needed, then use Start AI Inspection for an explicit
                      retry.
                    </p>
                  )}
                  {selected?.preparation_status === "PREPARING" && (
                    <p className="form-hint">
                      Preparation is still in progress. Analysis becomes
                      available after the order is ready.
                    </p>
                  )}
                  {["UPLOADED", "ANALYZING"].includes(current.status) && (
                    <p className="form-hint">
                      Analyze the current image before uploading correction
                      evidence.
                    </p>
                  )}
                  {selected?.latest_inspection_id &&
                    selected.latest_inspection_id !== current.id && (
                      <p className="form-hint">
                        This evidence has been superseded.{" "}
                        <Link
                          className="text-link"
                          to={inspectionHref(selected)}
                        >
                          Open the latest inspection
                        </Link>
                        .
                      </p>
                    )}
                  {!token && (
                    <p className="form-hint">
                      Analysis requires an operator credential.{" "}
                      <Link className="text-link" to="/settings">
                        Set session token in Settings
                      </Link>
                      .
                    </p>
                  )}
                  {analyze.isError && (
                    <p role="alert" className="field-error">
                      {analyze.error.message}
                    </p>
                  )}
                </div>
              )
            )}
          </Panel>
          {current && !reinspect && (
            <>
              <VerificationComparison inspection={current} />
              <InspectionResults
                inspection={current}
                selectedRegionIds={selectedRegionIds}
                onSelectRegions={setSelectedRegionIds}
              />
              <Investigation
                inspection={current}
                isCurrent={selected?.latest_inspection_id === current.id}
              />
            </>
          )}
        </div>
        <div className="inspection-aside">
          <Panel
            title="Expected order"
            subtitle={
              selected?.reference ?? "Select an order to see the manifest"
            }
          >
            {selected ? (
              <div className="manifest">
                {selected.items.map((item) => (
                  <div className="manifest-item" key={item.id}>
                    {item.product.reference_image_url ? (
                      <img
                        className="product-reference"
                        src={item.product.reference_image_url}
                        alt={`Synthetic catalog reference for ${item.product.sku}`}
                        loading="lazy"
                      />
                    ) : (
                      <div className="product-cube">
                        <Box size={20} aria-hidden="true" />
                      </div>
                    )}
                    <div>
                      <strong>{item.product.name}</strong>
                      <span>
                        {item.product.sku}
                        {item.product.color ? ` · ${item.product.color}` : ""}
                      </span>
                      {item.product.reference_source ===
                        "original_synthetic_reference" && (
                        <span className="reference-source-badge">
                          Synthetic catalog reference
                        </span>
                      )}
                    </div>
                    <span className="quantity">×{item.quantity}</span>
                  </div>
                ))}
                <div className="manifest-total">
                  <span>Expected units</span>
                  <strong>
                    {selected.items.reduce((n, i) => n + i.quantity, 0)}
                  </strong>
                </div>
              </div>
            ) : (
              <Empty icon={Package} title="The manifest comes first">
                Choose an order to establish the expected items.
              </Empty>
            )}
          </Panel>
          <div className="guidance-card">
            <div className="eyebrow">
              <ShieldCheck size={15} aria-hidden="true" />
              EVIDENCE STANDARD
            </div>
            <h3>Give certainty a clear view.</h3>
            <ul>
              <li>
                <Check size={14} aria-hidden="true" />
                Show all items and readable labels.
              </li>
              <li>
                <Check size={14} aria-hidden="true" />
                Use good lighting without overlap.
              </li>
              <li>
                <Check size={14} aria-hidden="true" />
                Uncertain counts remain in review.
              </li>
            </ul>
            <p>
              “Not observed” never proves “absent.” No exact identity is
              asserted from ambiguous evidence.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
function InspectionResults({
  inspection: i,
  selectedRegionIds,
  onSelectRegions,
}: {
  inspection: Inspection;
  selectedRegionIds: string[];
  onSelectRegions: (ids: string[]) => void;
}) {
  return (
    <>
      {!!i.comparison?.length && (
        <Panel
          title="Product comparison"
          subtitle="Server-calculated quantities and differences, linked to actual evidence."
        >
          <ProductComparison
            rows={i.comparison}
            selectedRegionIds={selectedRegionIds}
            onSelectRegions={onSelectRegions}
          />
        </Panel>
      )}
      {i.annotation_url && !i.regions?.length && (
        <Panel
          title="Stored segmentation annotation"
          subtitle="Historical annotation; expand only when needed."
        >
          <details className="stored-annotation">
            <summary>View recorded SAM annotation</summary>
            <figure className="captured-evidence segmentation-figure">
              <img
                src={i.annotation_url}
                alt={`SAM segmentation annotation for inspection ${i.id}`}
                loading="lazy"
              />
              <figcaption className="form-hint">
                Geometry highlights visual regions. Segmentation does not
                independently establish product SKU or verify the order.
                Identity and quantities require separate evidence-backed
                reconciliation.
              </figcaption>
            </figure>
          </details>
        </Panel>
      )}
      <Panel
        title="Evidence & reconciliation"
        subtitle="Provider observations and deterministic policy outcomes."
      >
        {!i.observations.length && !i.discrepancies.length ? (
          <Empty icon={Search} title="No analysis results recorded">
            Run analysis to produce evidence-backed observations. Empty results
            do not verify an order.
          </Empty>
        ) : (
          <div className="results-content">
            {i.observations.length > 0 && (
              <>
                <h3>Observed evidence</h3>
                {i.observations.map((o) => (
                  <div className="observation" key={o.id}>
                    <div>
                      <strong>
                        {o.label_text || o.product_id || "Unidentified item"}
                      </strong>
                      <p>{o.evidence}</p>
                    </div>
                    <span className="observation-count">
                      {o.count_certain && o.quantity != null
                        ? `× ${o.quantity}`
                        : "Count uncertain"}
                    </span>
                    <div className="evidence-flags">
                      {o.identification_status && (
                        <span>{label(o.identification_status)}</span>
                      )}
                      <span>
                        {o.identity_certain
                          ? "Identity supported"
                          : "Identity uncertain"}
                      </span>
                      <span>
                        {o.count_certain
                          ? "Count supported"
                          : "Count uncertain"}
                      </span>
                    </div>
                  </div>
                ))}
              </>
            )}
            {!!i.unidentified_objects?.length && (
              <>
                <h3 className="result-subheading">Unidentified objects</h3>
                {i.unidentified_objects.map((object, index) => (
                  <div key={object.id ?? index} className="observation">
                    <div>
                      <strong>UNIDENTIFIED</strong>
                      <p>{object.evidence}</p>
                      <p>{object.label_text}</p>
                    </div>
                    <span className="observation-count">
                      {object.count_certain && object.quantity != null
                        ? `Observed ${object.quantity}`
                        : "Quantity not established"}
                    </span>
                  </div>
                ))}
              </>
            )}
            {i.discrepancies.length > 0 && (
              <>
                <h3 className="result-subheading">Discrepancies</h3>
                {i.discrepancies.map((d) => (
                  <div className="discrepancy" key={d.id}>
                    <CircleAlert size={18} aria-hidden="true" />
                    <div>
                      <strong>{label(d.type)}</strong>
                      <p>{d.description}</p>
                      <span>
                        Expected: {d.required_quantity ?? "Unknown"} · Observed:{" "}
                        {d.observed_quantity ?? "Not established"}
                      </span>
                    </div>
                    <Status value={d.status} />
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </Panel>
      {i.actions.length > 0 && (
        <Panel
          title="Proposed actions"
          subtitle="Consequential actions require supervisor authorization."
        >
          <div className="results-content">
            {i.actions.map((a) => (
              <ActionCard key={a.id} action={a} inspection={i} />
            ))}
          </div>
        </Panel>
      )}
    </>
  );
}
function VerificationComparison({ inspection }: { inspection: Inspection }) {
  const { token } = useContext(TokenContext);
  const previous = useQuery({
    queryKey: ["inspection", inspection.previous_inspection_id],
    queryFn: () => api<Inspection>(`/inspections/${inspection.previous_inspection_id}`),
    enabled: !!inspection.previous_inspection_id,
  });
  const status = useQuery({
    queryKey: ["verification-status", inspection.order_id, inspection.id],
    queryFn: () => api<{verification_status: string; revision_current: boolean;
      order_version: number; inspection_order_version: number | null;
      picking_tasks: {id: string; product_id: string; quantity: number; status: string}[];
      removal_tasks: {id: string; product_id: string; quantity: number; status: string}[]}>(
      `/orders/${inspection.order_id}/verification-status`,
      {headers: {Authorization: `Bearer ${token}`}}),
    enabled: !!token,
  });
  if (!inspection.previous_inspection_id) return null;
  return (
    <Panel title="Before and after" subtitle="Saved visual evidence and server-calculated quantities.">
      {previous.isPending ? <Loading /> : previous.isError ?
        <ErrorState error={previous.error} retry={() => previous.refetch()} /> : previous.data && (
          <>
            <div className="verification-summary">
              <p><strong>Final decision:</strong> {status.data ? label(status.data.verification_status) : label(inspection.status)}</p>
              <p><strong>Order revision:</strong> {status.data ?
                `${status.data.revision_current ? "Current" : "Changed"} (order ${status.data.order_version}, evidence ${status.data.inspection_order_version ?? "unknown"})` :
                "Sign in to check the current order revision."}</p>
              <p><strong>Original discrepancies:</strong> {previous.data.discrepancies.length ?
                previous.data.discrepancies.map((item) => label(item.type)).join(", ") : "None recorded"}</p>
              <p><strong>Current discrepancies:</strong> {inspection.discrepancies.length ?
                inspection.discrepancies.map((item) => label(item.type)).join(", ") : "None recorded"}</p>
              <p><strong>Corrective actions:</strong> {previous.data.actions.length ?
                previous.data.actions.map((item) => `${label(item.type)}: ${label(item.status)}`).join(", ") : "None recorded"}</p>
              <p><strong>Picking tasks:</strong> {status.data ?
                status.data.picking_tasks.length ? status.data.picking_tasks.map((item) =>
                  `${item.product_id} × ${item.quantity}: ${label(item.status)}`).join(", ") : "None" : "Sign in to view"}</p>
              <p><strong>Removal tasks:</strong> {status.data ?
                status.data.removal_tasks.length ? status.data.removal_tasks.map((item) =>
                  `${item.product_id} × ${item.quantity}: ${label(item.status)}`).join(", ") : "None" : "Sign in to view"}</p>
            </div>
            <div className="verification-images">
              {[previous.data, inspection].map((item, index) => (
                <figure key={item.id}>
                  <figcaption>{index === 0 ? "BEFORE CORRECTION" : "AFTER CORRECTION"} · {formatTime(item.created_at)} · {label(item.status)}</figcaption>
                  <a href={item.image_url} target="_blank" rel="noreferrer" aria-label={`Open ${index === 0 ? "before" : "after"} evidence image`}>
                    <img src={item.annotation_url ?? item.image_url} alt={`${index === 0 ? "Original" : "New"} inspection evidence`} />
                  </a>
                  <small>Photo ID: {item.photo_id}</small>
                </figure>
              ))}
            </div>
            <table className="comparison-table"><thead><tr><th>Product</th><th>Required</th><th>Before</th><th>After</th><th>Result</th></tr></thead>
              <tbody>{inspection.comparison?.map((row) => {
                const before = previous.data?.comparison?.find((item) => item.product_id === row.product_id);
                return <tr key={row.product_id}><td>{row.name}</td><td>{row.required_quantity}</td>
                  <td>{before?.observed_quantity ?? "Unknown"}</td><td>{row.observed_quantity ?? "Unknown"}</td>
                  <td>{label(row.status)}</td></tr>;
              })}</tbody>
            </table>
          </>
        )}
    </Panel>
  );
}
function Investigation({
  inspection: i,
  isCurrent,
}: {
  inspection: Inspection;
  isCurrent: boolean;
}) {
  const { token } = useContext(TokenContext);
  return (
    <Panel
      title="AI investigation"
      subtitle="Persisted evidence-based findings and actual read-tool activity."
    >
      <div className="results-content">
        <InvestigationCard inspection={i} token={token} isCurrent={isCurrent} />
      </div>
    </Panel>
  );
}
function ActionCard({
  action,
  inspection,
}: {
  action: Action;
  inspection?: Inspection;
}) {
  const { token } = useContext(TokenContext);
  const orders = useQuery({
    queryKey: ["orders"],
    queryFn: () => api<Order[]>("/orders"),
  });
  return (
    <CorrectiveActionCard
      action={action}
      inspection={inspection}
      order={orders.data?.find(
        (order) => order.id === (inspection?.order_id ?? action.order_id),
      )}
      token={token}
    />
  );
}
function Operations() {
  const { token } = useContext(TokenContext);
  return (
    <>
      <PageHeading
        eyebrow="CONTROLLED AUTONOMY"
        title="AI Operations"
        description="Investigate real evidence, review validated proposals, and authorize accountable actions."
      />
      <div className="notice">
        <ShieldCheck size={16} aria-hidden="true" />
        <span>
          Model tools are read-only. Every corrective action requires server
          validation and recorded supervisor approval.
        </span>
      </div>
      <OperationsWorkspace token={token} />
    </>
  );
}
function AuditList({ events }: { events: Audit[] }) {
  return (
    <ol className="audit-list">
      {events.map((event) => (
        <li key={event.id}>
          <div className="audit-symbol">
            <Activity size={15} aria-hidden="true" />
          </div>
          <div>
            <strong>{label(event.event_type)}</strong>
            <p>
              {event.actor} · {event.entity_id?.slice(0, 16) || "Workspace"}
            </p>
            <time dateTime={event.created_at}>
              {formatTime(event.created_at)}
            </time>
            <details>
              <summary>Event details</summary>
              <pre>{JSON.stringify(event.details, null, 2)}</pre>
            </details>
          </div>
        </li>
      ))}
    </ol>
  );
}
function History() {
  const q = useQuery({
    queryKey: ["inspections"],
    queryFn: () => api<Inspection[]>("/inspections"),
  });
  const [status, setStatus] = useState("ALL");
  const rows =
    q.data?.filter((i) => status === "ALL" || i.status === status) ?? [];
  return (
    <>
      <PageHeading
        eyebrow="PROOF, PRESERVED"
        title="Verification History"
        description="Follow each inspection, its original photo, and every subsequent reinspection."
      />
      <Panel
        title="Inspection ledger"
        subtitle="Historical evidence stays linked and reviewable."
        action={
          <select
            aria-label="Filter inspection status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="ALL">All statuses</option>
            {Array.from(new Set(q.data?.map((i) => i.status))).map((s) => (
              <option key={s} value={s}>
                {label(s)}
              </option>
            ))}
          </select>
        }
      >
        {q.isPending ? (
          <Loading />
        ) : q.isError ? (
          <ErrorState error={q.error} retry={() => q.refetch()} />
        ) : rows.length ? (
          <InspectionTable inspections={rows} />
        ) : (
          <Empty icon={FileSearch} title="No inspections in this view">
            {status === "ALL"
              ? "Your first real inspection will start the evidence ledger."
              : "Try another status filter."}
          </Empty>
        )}
      </Panel>
      <div className="principle-strip">
        <GitBranch size={22} aria-hidden="true" />
        <div>
          <strong>A correction needs its own evidence.</strong>
          <p>
            New photos create linked inspections, preserving the original
            evidence and outcome.
          </p>
        </div>
      </div>
    </>
  );
}
function Demo() {
  return <>
    <PageHeading eyebrow="CONTROLLED PRESENTATION" title="Demo Workspace"
      description="Run the real ProofSight workflow with rights-cleared synthetic scenes and isolated seed orders." />
    <DemoWorkspace />
  </>;
}
function Settings() {
  const q = useQuery({
    queryKey: ["meta-status"],
    queryFn: () => api<MetaStatus>("/integrations/meta/status"),
  });
  const { token, setToken } = useContext(TokenContext);
  const [draft, setDraft] = useState("");
  const [saved, setSaved] = useState(false);
  return (
    <>
      <PageHeading
        eyebrow="WORKSPACE CONFIGURATION"
        title="Settings"
        description="Inspect integration readiness and authorize this browser session."
      />
      <div className="settings-grid">
        <Panel
          title="Meta integration"
          subtitle="Configuration reported by the local backend."
          action={
            <Button
              variant="ghost"
              size="icon"
              aria-label="Refresh integration status"
              onClick={() => q.refetch()}
            >
              <RefreshCw size={16} />
            </Button>
          }
        >
          {q.isPending ? (
            <Loading />
          ) : q.isError ? (
            <ErrorState error={q.error} retry={() => q.refetch()} />
          ) : (
            <div className="settings-content">
              <div className="integration-heading">
                <div className="integration-symbol">
                  <Sparkles size={25} aria-hidden="true" />
                </div>
                <div>
                  <h3>Meta AI</h3>
                  <p>Perception & evidence investigation</p>
                </div>
                <Status
                  value={q.data.configured ? "CONFIGURED" : "NOT_CONFIGURED"}
                />
              </div>
              <dl className="settings-list">
                <div>
                  <dt>API endpoint</dt>
                  <dd>{q.data.base_url}</dd>
                </div>
                <div>
                  <dt>Reasoning model</dt>
                  <dd>{q.data.muse_model}</dd>
                </div>
                <div>
                  <dt>Segmentation model</dt>
                  <dd>{q.data.sam_model}</dd>
                </div>
                <div>
                  <dt>Last live check</dt>
                  <dd>{formatTime(q.data.last_live_check)}</dd>
                </div>
                <div>
                  <dt>Operator authorization</dt>
                  <dd>
                    {q.data.operator_auth_configured
                      ? "Configured on server"
                      : "Not configured on server"}
                  </dd>
                </div>
              </dl>
              <div className="inline-note">
                <CircleAlert size={16} aria-hidden="true" />
                <p>
                  Configured does not mean a live request has succeeded. Model
                  credentials stay in the backend environment.
                </p>
              </div>
            </div>
          )}
        </Panel>
        <Panel
          title="Operator authorization"
          subtitle="Required for evidence uploads, analysis, investigation, approvals, and execution."
        >
          <form
            className="settings-content"
            onSubmit={(e) => {
              e.preventDefault();
              setToken(draft.trim());
              setDraft("");
              setSaved(true);
            }}
          >
            <div className="field">
              <label htmlFor="operator-token">Operator session token</label>
              <input
                id="operator-token"
                type="password"
                autoComplete="off"
                spellCheck={false}
                value={draft}
                onChange={(e) => {
                  setDraft(e.target.value);
                  setSaved(false);
                }}
                placeholder="Enter the server-issued operator token"
                aria-describedby="token-hint"
              />
              <p id="token-hint" className="form-hint">
                Find the operator token in your local backend .env file
                (OPERATOR_TOKEN). Kept in browser memory only; refreshing clears
                it. The server determines your authorization.
              </p>
            </div>
            <div className="button-row">
              <Button type="submit" disabled={!draft.trim()}>
                <LockKeyhole size={15} aria-hidden="true" />
                Set session token
              </Button>
              {token && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setToken("");
                    setSaved(false);
                  }}
                >
                  Clear token
                </Button>
              )}
            </div>
            <div className="session-status" role="status">
              {token ? (
                <>
                  <CircleCheck size={16} aria-hidden="true" />
                  {saved
                    ? "Token saved for this session."
                    : "Session token is present."}{" "}
                  Authorization is checked on each server request.
                </>
              ) : (
                <>
                  <Clock3 size={16} aria-hidden="true" />
                  No operator token in this session.
                </>
              )}
            </div>
            <div className="inline-note">
              <ShieldCheck size={17} aria-hidden="true" />
              <p>
                This token is separate from the model API key. Never enter a
                model API key into the browser.
              </p>
            </div>
          </form>
        </Panel>
      </div>
    </>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <TokenProvider>
        <BrowserRouter>
          <Shell />
        </BrowserRouter>
      </TokenProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
