export function checklistState(row: { required_quantity: number; observed_quantity: number | null; status: string }) {
  const checked = row.status === "MATCHED" && row.observed_quantity === row.required_quantity;
  return {
    checked,
    text: checked ? `${row.observed_quantity} / ${row.required_quantity} confirmed` : "Not established · needs review",
  };
}
