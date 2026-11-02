import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import type { Order } from "../types";

type Line = { sku: string; name: string; color: string; quantity: number; visible_label: boolean; file: File | null };
const blank = (): Line => ({ sku: "", name: "", color: "", quantity: 1, visible_label: false, file: null });

export function CreateTestOrder({ onCreated }: { onCreated: (order: Order) => void }) {
  const [reference, setReference] = useState("");
  const [customer, setCustomer] = useState("Local test");
  const [lines, setLines] = useState<Line[]>([blank()]);
  const [rights, setRights] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState<Order | null>(null);
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID());
  const update = (index: number, values: Partial<Line>) =>
    setLines((current) => current.map((line, at) => at === index ? { ...line, ...values } : line));

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (lines.some((line) => !line.file)) {
      setError("Add one reference image for every product.");
      return;
    }
    const body = new FormData();
    body.append("manifest", JSON.stringify({ reference: reference.trim(), customer: customer.trim(),
      items: lines.map(({ sku, name, color, quantity, visible_label }) => ({
        sku: sku.trim(), name: name.trim(), color: color.trim(), quantity, visible_label,
      })) }));
    body.append("rights_confirmed", String(rights));
    lines.forEach((line) => body.append("references", line.file!));
    setPending(true);
    try {
      const order = await api<Order>("/orders/test", { method: "POST", body,
        headers: { "Idempotency-Key": requestKey } });
      setCreated(order);
      onCreated(order);
      setRequestKey(crypto.randomUUID());
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not create the test order.");
    } finally {
      setPending(false);
    }
  }

  return <form className="test-order-form" onSubmit={submit}>
    <p className="test-order-note">Create a local test manifest. Product references guide visual analysis; the scene photo is uploaded during inspection. Unreadable or missing labels may still require review.</p>
    <div className="test-order-fields">
      <label>Order reference<input required maxLength={60} pattern="[A-Za-z0-9_-]{3,60}" value={reference} onChange={(e) => setReference(e.target.value)} placeholder="TEST-ORDER-001" /></label>
      <label>Customer / scenario<input required maxLength={100} value={customer} onChange={(e) => setCustomer(e.target.value)} /></label>
    </div>
    <div className="test-order-lines">
      {lines.map((line, index) => <fieldset className="test-order-line" key={index}>
        <legend>Product {index + 1}</legend>
        <div className="test-order-fields">
          <label>SKU<input required maxLength={60} pattern="[A-Za-z0-9_-]{2,60}" value={line.sku} onChange={(e) => update(index, { sku: e.target.value })} placeholder="TEST-BLUE-CUBE" /></label>
          <label>Product name<input required maxLength={100} value={line.name} onChange={(e) => update(index, { name: e.target.value })} placeholder="Blue cube" /></label>
          <label>Color / visual description<input required maxLength={40} value={line.color} onChange={(e) => update(index, { color: e.target.value })} placeholder="Blue" /></label>
          <label>Expected quantity<input required min={1} max={100} type="number" value={line.quantity} onChange={(e) => update(index, { quantity: Number(e.target.value) })} /></label>
          <label>Product reference image<input required type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => update(index, { file: e.target.files?.[0] ?? null })} /></label>
        </div>
        <label className="test-order-check"><input type="checkbox" checked={line.visible_label} onChange={(e) => update(index, { visible_label: e.target.checked })} />Exact SKU is visibly printed on the product</label>
        {lines.length > 1 && <button type="button" className="test-order-secondary" onClick={() => setLines((current) => current.filter((_, at) => at !== index))}>Remove product</button>}
      </fieldset>)}
    </div>
    {lines.length < 4 && <button type="button" className="test-order-secondary" onClick={() => setLines((current) => [...current, blank()])}>+ Add product</button>}
    <label className="test-order-check"><input required type="checkbox" checked={rights} onChange={(e) => setRights(e.target.checked)} />These reference images are synthetic or I have rights to use them.</label>
    {error && <p className="test-order-error" role="alert">{error}</p>}
    <div className="test-order-actions"><button type="submit" disabled={pending}>{pending ? "Creating order…" : "Create test order"}</button>
      {created && <Link to={`/inspection?order=${encodeURIComponent(created.id)}`}>Open {created.reference} for inspection →</Link>}
    </div>
  </form>;
}
