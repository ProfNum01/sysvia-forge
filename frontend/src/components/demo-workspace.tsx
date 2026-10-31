import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CircleAlert, Image, LoaderCircle, LockKeyhole, Package } from "lucide-react";
import { Button } from "./ui/button";
import { api, label } from "../lib/api";
import type { DemoAsset, MetaStatus, Order } from "../types";

export function DemoWorkspace() {
  const [selectedId, setSelectedId] = useState("");
  const orders = useQuery({ queryKey: ["orders"], queryFn: () => api<Order[]>("/orders") });
  const assets = useQuery({ queryKey: ["demo-assets"], queryFn: () => api<DemoAsset[]>("/demo/assets") });
  const meta = useQuery({ queryKey: ["meta-status"], queryFn: () => api<MetaStatus>("/integrations/meta/status") });
  const syntheticOrders = (orders.data ?? []).filter((order) => order.data_source === "synthetic_seed");
  const selected = syntheticOrders.find((order) => order.id === selectedId) ?? syntheticOrders[0];
  const blocked = selected?.shipping_status === "SHIPPED";
  return <div className="demo-workspace">
    <div className="demo-truth"><CircleAlert size={20} aria-hidden="true" />
      <div><strong>Original synthetic evidence</strong><p>These are locally drawn test scenes. They do not document a physical warehouse correction. Upload and Analyze use the actual backend; Analyze and Investigate can make paid Meta requests.</p></div>
    </div>
    <div className="demo-status-row">
      <span>Meta configuration: <strong>{meta.isPending ? "Checking" : meta.isError ? "Unavailable" :
        meta.data?.configured ? "Configured, connection untested here" : "Not configured"}</strong></span>
      <span>Approval: <strong>Operator credential required</strong></span>
      <Link className="text-link" to="/settings"><LockKeyhole size={14} aria-hidden="true" /> Open settings</Link>
    </div>
    <section className="panel">
      <div className="panel-heading"><div><h2>Choose a synthetic order</h2><p>Only database records marked as synthetic seed data appear here.</p></div><Package size={20} aria-hidden="true" /></div>
      {orders.isPending ? <p className="demo-message"><LoaderCircle className="spin" size={16} aria-hidden="true" /> Loading orders...</p> :
        orders.isError ? <p className="demo-message" role="alert">{orders.error.message} <button onClick={() => orders.refetch()}>Retry</button></p> :
        syntheticOrders.length ? <div className="demo-order-select"><label htmlFor="demo-order">Demonstration order</label>
          <select id="demo-order" value={selected?.id ?? ""} onChange={(event) => setSelectedId(event.target.value)}>
            {syntheticOrders.map((order) => <option key={order.id} value={order.id}>{order.reference} · {label(order.status)}</option>)}
          </select>
          {selected && <div className="demo-manifest"><strong>Authoritative manifest</strong><span>{selected.items.map((item) => `${item.product.sku} × ${item.quantity}`).join(" · ")}</span><span>Shipping: {label(selected.shipping_status ?? "NOT_READY")}</span></div>}
        </div> : <p className="demo-message">No synthetic orders are available in this database.</p>}
    </section>
    <section className="panel">
      <div className="panel-heading"><div><h2>Rights-cleared scenes</h2><p>Images served from the local backend. Choose one to load it into Visual Inspection.</p></div><Image size={20} aria-hidden="true" /></div>
      {assets.isPending ? <p className="demo-message"><LoaderCircle className="spin" size={16} aria-hidden="true" /> Loading assets...</p> :
        assets.isError ? <p className="demo-message" role="alert">{assets.error.message} <button onClick={() => assets.refetch()}>Retry</button></p> :
        assets.data?.length ? <div className="demo-assets">{assets.data.map((asset) => {
          const query = new URLSearchParams(selected?.latest_inspection_id ?
            { id: selected.latest_inspection_id, demo: asset.name, reinspect: "1" } :
            { order: selected?.id ?? "", demo: asset.name });
          return <article className="demo-asset" key={asset.name}>
            <img src={asset.url} alt={`${asset.title}, original synthetic test scene`} loading="lazy" />
            <div><span className="eyebrow">TEST FIXTURE</span><h3>{asset.title}</h3><p>{asset.description}</p>
              <Button asChild size="sm" variant="outline"><Link to={`/inspection?${query}`} aria-disabled={!selected || blocked}
                onClick={(event) => { if (!selected || blocked) event.preventDefault(); }}>
                Use in inspection <ArrowRight size={14} aria-hidden="true" /></Link></Button></div>
          </article>;
        })}</div> : <p className="demo-message">No approved synthetic assets are installed.</p>}
      {blocked && <p className="demo-message" role="status">This order is shipped and cannot accept new evidence.</p>}
    </section>
  </div>;
}
