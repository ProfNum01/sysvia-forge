import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  CircleAlert,
  FileSearch,
  Image,
  LoaderCircle,
  LockKeyhole,
  Package,
  ScanLine,
  Settings2,
  ShieldCheck,
  Sparkles,
  GitBranch,
  ClipboardCheck,
} from "lucide-react";
import { Button } from "./ui/button";
import { api, label } from "../lib/api";
import type { DemoAsset, Inspection, MetaStatus, Order, Summary } from "../types";

const journey = [
  { title: "1. Order manifest", detail: "The required SKUs and quantities define the expected order.", to: "/orders", icon: Package },
  { title: "2. Visual evidence", detail: "A new photo is uploaded, then Muse Spark and SAM examine visible products.", to: "/inspection", icon: ScanLine },
  { title: "3. Reconciliation", detail: "Server rules compare supported observations with the manifest. Uncertainty stays under review.", to: "/history", icon: ShieldCheck },
  { title: "4. Investigation", detail: "The AI agent reads order, inventory and inspection records before proposing a next step.", to: "/operations", icon: Sparkles },
  { title: "5. Approved action", detail: "Consequential changes require supervisor approval and leave an audit trail.", to: "/operations", icon: ClipboardCheck },
  { title: "6. New evidence", detail: "A corrected order needs a new photo and linked reinspection before verification.", to: "/history", icon: GitBranch },
];

export function DemoWorkspace({ token }: { token: string }) {
  const [selectedId, setSelectedId] = useState("");
  const orders = useQuery({
    queryKey: ["orders"],
    queryFn: () => api<Order[]>("/orders"),
    enabled: !!token,
  });
  const assets = useQuery({ queryKey: ["demo-assets"], queryFn: () => api<DemoAsset[]>("/demo/assets") });
  const meta = useQuery({ queryKey: ["meta-status"], queryFn: () => api<MetaStatus>("/integrations/meta/status") });
  const summary = useQuery({ queryKey: ["dashboard-summary"], queryFn: () => api<Summary>("/dashboard/summary"), enabled: !!token });
  const demoOrders = (orders.data ?? []).filter((order) => ["synthetic_seed", "synthetic_claude", "physical_capture"].includes(order.data_source))
    .sort((a, b) => Number(b.data_source === "synthetic_seed") - Number(a.data_source === "synthetic_seed"));
  const selected = demoOrders.find((order) => order.id === selectedId) ?? demoOrders.find((order) => order.reference === "PS-1001") ?? demoOrders[0];
  const inspection = useQuery({
    queryKey: ["inspection", selected?.latest_inspection_id],
    queryFn: () => api<Inspection>(`/inspections/${selected?.latest_inspection_id}`),
    enabled: !!token && !!selected?.latest_inspection_id,
  });
  const blocked = selected?.shipping_status === "SHIPPED";

  return <div className="demo-workspace">
    <section className="demo-intro" aria-labelledby="demo-story-title">
      <div><span className="eyebrow">PROOFSIGHT · SYSTEM TOUR</span><h2 id="demo-story-title">From order to evidence-backed decision</h2>
        <p>Follow one order through visual inspection, deterministic checks, AI investigation, human approval and reinspection. The records below come from this local workspace.</p>
        <div className="demo-intro-actions"><Button asChild variant="primary"><Link to="/orders">Explore orders <ArrowRight size={15} aria-hidden="true" /></Link></Button><Link className="text-link" to="/history">Open evidence ledger <ArrowRight size={15} aria-hidden="true" /></Link></div>
      </div>
      <div className="demo-intro-aside"><strong>Safety rule</strong><p>An unseen product is not proven absent. A completed task is not proof of correction. Verification requires enough visual evidence from a real inspection.</p></div>
    </section>
    <section className="demo-overview" aria-label="Current workspace summary">
      <div className="demo-section-heading"><div><span className="eyebrow">CURRENT WORKSPACE</span><h2>What the system knows now</h2></div><Link className="text-link" to="/">Full overview <ArrowRight size={15} aria-hidden="true" /></Link></div>
      {!token ? <p className="demo-overview-note">Set the operator token to show live workspace counts.</p> : summary.isPending ? <p className="demo-overview-note">Loading recorded counts…</p> : summary.isError ? <p className="demo-overview-note" role="alert">Workspace counts unavailable. <button onClick={() => summary.refetch()}>Retry</button></p> : summary.data &&
        <div className="demo-overview-grid">{[
          ["Orders in workspace", summary.data.total_orders], ["Awaiting inspection", summary.data.pending_inspections],
          ["Verified by evidence", summary.data.verified_orders], ["On shipping hold", summary.data.orders_on_hold],
        ].map(([name, value]) => <div className="demo-overview-card" key={name}><strong>{value}</strong><span>{name}</span></div>)}</div>}
    </section>
    <section className="demo-journey" aria-labelledby="demo-journey-title">
      <div className="demo-section-heading"><div><span className="eyebrow">THE CLOSED LOOP</span><h2 id="demo-journey-title">How ProofSight works</h2></div><p>Open any stage to see its real workspace.</p></div>
      <div className="demo-journey-grid">{journey.map(({ title, detail, to, icon: Icon }) =>
        <Link className="demo-journey-card" key={title} to={to}><Icon size={20} aria-hidden="true" /><strong>{title}</strong><p>{detail}</p><span>Explore stage <ArrowRight size={14} aria-hidden="true" /></span></Link>)}</div>
    </section>
    <div className="demo-truth"><CircleAlert size={20} aria-hidden="true" />
      <div><strong>Demonstration data and actual outcomes are separate</strong><p>The scene illustrations are synthetic. An order is only verified when its saved inspection has sufficient evidence. Analysis and investigation in their own workspaces can make paid Meta requests; this tour does not.</p></div>
    </div>

    {!token && (
      <div className="demo-token-prompt">
        <LockKeyhole size={18} aria-hidden="true" />
        <div>
          <strong>Token required to load orders</strong>
          <p>Set your operator session token in Settings to see synthetic orders and run the full demo workflow.</p>
        </div>
        <Button asChild size="sm">
          <Link to="/settings">
            <Settings2 size={14} aria-hidden="true" />
            Open Settings
          </Link>
        </Button>
      </div>
    )}

    <div className="demo-status-row">
      <span>Meta: <strong>{meta.isPending ? "Checking…" : meta.isError ? "Unavailable" :
        meta.data?.configured ? "Configured" : "Not configured"}</strong></span>
      <span>Token: <strong>{token ? "Session active" : "Not set"}</strong></span>
      <Link className="text-link" to="/settings"><LockKeyhole size={14} aria-hidden="true" /> Settings</Link>
    </div>

    {token && (
      <section className="panel">
        <div className="panel-heading"><div><h2>Follow a recorded order</h2><p>Select an order to show its manifest, current state and available evidence.</p></div><Package size={20} aria-hidden="true" /></div>
        {orders.isPending ? <p className="demo-message"><LoaderCircle className="spin" size={16} aria-hidden="true" /> Loading orders...</p> :
          orders.isError ? <p className="demo-message" role="alert">{orders.error.message} <button onClick={() => orders.refetch()}>Retry</button></p> :
          demoOrders.length ? <div className="demo-order-select"><label htmlFor="demo-order">Demonstration order</label>
            <select id="demo-order" value={selected?.id ?? ""} onChange={(event) => setSelectedId(event.target.value)}>
              {demoOrders.map((order) => <option key={order.id} value={order.id}>{order.reference} · {label(order.status)}{order.data_source === "physical_capture" ? " · PHYSICAL_CAPTURE" : ""}</option>)}
            </select>
            {selected && <div className="demo-manifest"><strong>Order manifest · {selected.data_source === "physical_capture" ? "PHYSICAL_CAPTURE" : "SYNTHETIC"}</strong><span>{selected.items.map((item) => `${item.product.sku} × ${item.quantity}`).join(" · ")}</span><span>Inspection: {selected.latest_inspection_id ? label(inspection.data?.status ?? "RECORDED") : "No inspection yet"}</span><span>Shipping: {label(selected.shipping_status ?? "NOT_READY")}</span></div>}
            {selected && (selected.data_source === "physical_capture" || selected.latest_inspection_id) && (
              <Button asChild size="sm" variant="primary">
                <Link to={selected.latest_inspection_id ? `/inspection?id=${selected.latest_inspection_id}` : `/inspection?order=${selected.id}`}>
                  <FileSearch size={14} aria-hidden="true" />
                  Open inspection evidence <ArrowRight size={14} aria-hidden="true" />
                </Link>
              </Button>
            )}
            {inspection.data && (
              <div className="demo-recorded-evidence">
                <strong>{inspection.data.execution_events?.some((event) => event.event_type === "MUSE_ANALYSIS_COMPLETED" || event.event_type === "SAM_SEGMENTATION_COMPLETED") ? "Recorded live inference" : "Saved inspection evidence"}</strong>
                <div className="demo-live-badges">
                  {inspection.data.execution_events?.some((event) => event.event_type === "MUSE_ANALYSIS_COMPLETED") && <span className="badge">Muse Spark 1.3</span>}
                  {inspection.data.execution_events?.some((event) => event.event_type === "SAM_SEGMENTATION_COMPLETED") && <span className="badge">SAM 3.1</span>}
                  {inspection.data.comparison?.some((c) => c.status === "NOT_OBSERVED") && (
                    <span className="badge">NOT OBSERVED is not confirmed missing</span>
                  )}
                  {inspection.data.execution_events?.some((e) => e.details && "tool" in e.details && e.details.tool === "check_inventory") && (
                    <span className="badge">check_inventory</span>
                  )}
                  {inspection.data.investigation_result?.decision && (
                    <span className="badge">{inspection.data.investigation_result.decision}</span>
                  )}
                  {selected?.shipping_status && (
                    <span className="badge">Shipping {selected.shipping_status}</span>
                  )}
                </div>
              </div>
            )}
          </div> : <p className="demo-message">No synthetic orders are available in this database.</p>}
      </section>
    )}

    <section className="panel">
        <div className="panel-heading"><div><h2>Scene for this order</h2><p>Synthetic illustration served from the local backend. Open Visual Inspection to submit it as evidence.</p></div><Image size={20} aria-hidden="true" /></div>
      {assets.isPending ? <p className="demo-message"><LoaderCircle className="spin" size={16} aria-hidden="true" /> Loading assets...</p> :
        assets.isError ? <p className="demo-message" role="alert">{assets.error.message} <button onClick={() => assets.refetch()}>Retry</button></p> :
        selected?.data_source === "physical_capture" ? <p className="demo-message">Upload physical photos through the authorized inspection page. Synthetic assets are never substituted.</p> :
        assets.data?.length ? <div className="demo-assets">{assets.data.filter((asset) =>
          asset.name.startsWith("ten-order-") ? asset.title.startsWith(selected?.reference ?? "~") :
          asset.provenance === "synthetic_claude" ? selected?.data_source === "synthetic_claude" && !selected?.reference.startsWith("TEN-ORDER-") :
          asset.provenance !== "synthetic_packing" ? selected?.data_source !== "synthetic_claude" :
          selected?.id === (asset.name.includes("missing") ? "order-packing-missing" : "order-packing-extra")
        ).map((asset) => {
          const query = new URLSearchParams(selected?.latest_inspection_id ?
            { id: selected.latest_inspection_id, demo: asset.name, reinspect: "1" } :
            { order: selected?.id ?? "", demo: asset.name });
          const canUse = !!token && !!selected && !blocked &&
            (asset.provenance === "synthetic_claude" ? !selected.latest_inspection_id : asset.provenance !== "synthetic_packing" ||
              (asset.name.endsWith("after") ? !!selected.latest_inspection_id : !selected.latest_inspection_id));
          return <article className="demo-asset" key={asset.name}>
            <img src={asset.url} alt={`${asset.title}, original synthetic test scene`} loading="lazy" />
            <div><span className="eyebrow">{asset.name.startsWith("ten-order-") ? "Synthetic illustration" : asset.provenance === "synthetic_claude" ? "CLAUDE AI · SYNTHETIC" : asset.provenance === "synthetic_packing" ? "SYNTHETIC PACKING" : "TEST FIXTURE"}</span><h3>{asset.title}</h3><p>{asset.description}</p>
              {canUse ? (
                <Button asChild size="sm" variant="inspect">
                  <Link to={`/inspection?${query}`}>
                    <ScanLine size={14} aria-hidden="true" />
                    Use in inspection <ArrowRight size={14} aria-hidden="true" />
                  </Link>
                </Button>
              ) : asset.provenance === "synthetic_packing" && !!token ? (
                <span className="demo-message">{asset.name.endsWith("after") ? "Inspect the before image and complete any required approval first." : "This order already has evidence; follow its inspection chain."}</span>
              ) : (
                <Button asChild size="sm" variant="warning">
                  <Link to="/settings">
                    <LockKeyhole size={13} aria-hidden="true" /> Set token to use <ArrowRight size={14} aria-hidden="true" />
                  </Link>
                </Button>
              )}
            </div>
          </article>;
        })}</div> : <p className="demo-message">No approved synthetic assets are installed.</p>}
      {blocked && <p className="demo-message" role="status">This order is shipped and cannot accept new evidence.</p>}
    </section>
  </div>;
}
