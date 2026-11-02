import type { ProductComparisonRow } from "../types";
import { checklistState } from "../lib/product-checklist";

export function ProductChecklist({ rows, title }: { rows: ProductComparisonRow[]; title: string }) {
  return <section className="product-checklist" aria-label={title}>
    <strong>{title}</strong>
    <ul>{rows.map((row) => {
      const state = checklistState(row);
      return <li key={row.product_id}>
        <span className={state.checked ? "checklist-mark confirmed" : "checklist-mark unresolved"} aria-hidden="true">{state.checked ? "✓" : "X"}</span>
        <span><b>{row.name}</b> <small>{state.text}</small></span>
      </li>;
    })}</ul>
    <p>X means the evidence is unresolved; it does not prove the item is absent.</p>
  </section>;
}
