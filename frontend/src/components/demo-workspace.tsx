import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CircleAlert, Image, LoaderCircle, LockKeyhole, Package, Settings2 } from "lucide-react";
import { Button } from "./ui/button";
import { api, label } from "../lib/api";
import type { DemoAsset, MetaStatus, Order } from "../types";

export function DemoWorkspace({ token }: { token: string }) {
  const [selectedId, setSelectedId] = useState("");
  const orders = useQuery({
    queryKey: ["orders"],
    queryFn: () => api<Order[]>("/orders"),
    enabled: !!token,
  });
  const assets = useQuery({ queryKey: ["demo-assets"], queryFn: () => api<DemoAsset[]>("/demo/assets") });
  const meta = useQuery({ queryKey: ["meta-status"], queryFn: () => api<MetaStatus>("/integrations/meta/status") });
  const demoOrders = (orders.data ?? []).filter((order) => ["synthetic_seed", "synthetic_claude", "physical_capture"].includes(order.data_source))
    .sort((a, b) => Number(b.data_source === "synthetic_seed") - Number(a.data_source === "synthetic_seed"));
  const selected = demoOrders.find((order) => order.id === selectedId) ?? demoOrders.find((order) => order.reference === "PS-1001") ?? demoOrders[0];
  const blocked = selected?.shipping_status === "SHIPPED";

  return <div className="demo-workspace">
    <div className="demo-truth"><CircleAlert size={20} aria-hidden="true" />
      <div><strong>Synthetic evidence only</strong><p>Original fixtures, unlabeled packing scenes, and Claude AI generated labeled scenes do not document a physical warehouse correction. Analyze and Investigate can make paid Meta requests; open an inspection to see saved model evidence.</p></div>
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
        <div className="panel-heading"><div><h2>Choose a synthetic order</h2><p>Synthetic seeds and explicitly registered physical orders appear here with separate provenance.</p></div><Package size={20} aria-hidden="true" /></div>
        {orders.isPending ? <p className="demo-message"><LoaderCircle className="spin" size={16} aria-hidden="true" /> Loading orders...</p> :
          orders.isError ? <p className="demo-message" role="alert">{orders.error.message} <button onClick={() => orders.refetch()}>Retry</button></p> :
          demoOrders.length ? <div className="demo-order-select"><label htmlFor="demo-order">Demonstration order</label>
            <select id="demo-order" value={selected?.id ?? ""} onChange={(event) => setSelectedId(event.target.value)}>
              {demoOrders.map((order) => <option key={order.id} value={order.id}>{order.reference} · {label(order.status)}{order.data_source === "physical_capture" ? " · PHYSICAL_CAPTURE" : ""}</option>)}
            </select>
            {selected && <div className="demo-manifest"><strong>Authoritative manifest · {selected.data_source === "physical_capture" ? "PHYSICAL_CAPTURE" : "SYNTHETIC"}</strong><span>{selected.items.map((item) => `${item.product.sku} × ${item.quantity}`).join(" · ")}</span><span>Shipping: {label(selected.shipping_status ?? "NOT_READY")}</span></div>}
            {selected && (selected.data_source === "physical_capture" || selected.latest_inspection_id) && <Button asChild size="sm" variant="outline"><Link to={selected.latest_inspection_id ? `/inspection?id=${selected.latest_inspection_id}` : `/inspection?order=${selected.id}`}>Open inspection evidence <ArrowRight size={14} aria-hidden="true" /></Link></Button>}
          </div> : <p className="demo-message">No synthetic orders are available in this database.</p>}
      </section>
    )}

    <section className="panel">
      <div className="panel-heading"><div><h2>Rights-cleared scenes</h2><p>Images served from the local backend. Choose one to load it into Visual Inspection.</p></div><Image size={20} aria-hidden="true" /></div>
      {assets.isPending ? <p className="demo-message"><LoaderCircle className="spin" size={16} aria-hidden="true" /> Loading assets...</p> :
        assets.isError ? <p className="demo-message" role="alert">{assets.error.message} <button onClick={() => assets.refetch()}>Retry</button></p> :
        selected?.data_source === "physical_capture" ? <p className="demo-message">Upload physical photos through the authorized inspection page. Synthetic assets are never substituted.</p> :
        assets.data?.length ? <div className="demo-assets">{assets.data.filter((asset) =>
          asset.provenance === "synthetic_claude" ? selected?.data_source === "synthetic_claude" :
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
            <div><span className="eyebrow">{asset.provenance === "synthetic_claude" ? "CLAUDE AI · SYNTHETIC" : asset.provenance === "synthetic_packing" ? "SYNTHETIC PACKING" : "TEST FIXTURE"}</span><h3>{asset.title}</h3><p>{asset.description}</p>
              {canUse ? (
                <Button asChild size="sm" variant="outline"><Link to={`/inspection?${query}`}>
                  Use in inspection <ArrowRight size={14} aria-hidden="true" /></Link></Button>
              ) : asset.provenance === "synthetic_packing" && !!token ? (
                <span className="demo-message">{asset.name.endsWith("after") ? "Inspect the before image and complete any required approval first." : "This order already has evidence; follow its inspection chain."}</span>
              ) : (
                <Button asChild size="sm" variant="outline"><Link to="/settings">
                  <LockKeyhole size={13} aria-hidden="true" /> Set token to use <ArrowRight size={14} aria-hidden="true" /></Link></Button>
              )}
            </div>
          </article>;
        })}</div> : <p className="demo-message">No approved synthetic assets are installed.</p>}
      {blocked && <p className="demo-message" role="status">This order is shipped and cannot accept new evidence.</p>}
    </section>
  </div>;
}
