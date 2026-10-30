import { label } from "./api";
const supportedTypes = new Set([
  "HOLD_SHIPMENT",
  "HOLD_ORDER",
  "CREATE_PICKING_TASK",
  "REQUEST_REINSPECTION",
  "ESCALATE_TO_HUMAN",
]);
export function actionControls(action: {
  type: string;
  status: string;
  lifecycle_state?: string;
}) {
  const supported = supportedTypes.has(action.type);
  const state = action.lifecycle_state ?? action.status;
  const pending =
    supported &&
    ["PROPOSED", "PENDING_APPROVAL"].includes(action.status) &&
    ["PROPOSED", "PENDING_APPROVAL"].includes(state);
  return {
    approve: pending,
    reject: pending,
    execute: supported && action.status === "APPROVED" && state === "APPROVED",
  };
}
export function actionName(type: string) {
  return label(type === "HOLD_ORDER" ? "HOLD_SHIPMENT" : type);
}
export function actionImpact(type: string): string {
  switch (type) {
    case "HOLD_ORDER":
    case "HOLD_SHIPMENT":
      return "Prevents this order from advancing to shipping through ProofSight.";
    case "CREATE_PICKING_TASK":
      return "Creates a local picking task. Inventory is not deducted, and physical completion is not assumed.";
    case "REQUEST_REINSPECTION":
      return "Requires new visual evidence. The request does not verify the order.";
    case "ESCALATE_TO_HUMAN":
      return "Routes unresolved evidence to human review. The order remains unverified.";
    default:
      return "This action type is not supported by the current interface. Server policy remains authoritative.";
  }
}
export function evidenceLink(
  reference: string,
  context: { inspection_id: string; order_id?: string; photo_id?: string },
): string | null {
  const split = reference.indexOf(":");
  if (split < 1) return null;
  const type = reference.slice(0, split),
    id = reference.slice(split + 1);
  if (!id) return null;
  const inspection = `/inspection?id=${encodeURIComponent(context.inspection_id)}`;
  if (type === "inspection") return `/inspection?id=${encodeURIComponent(id)}`;
  if (type === "region")
    return `${inspection}&region=${encodeURIComponent(id)}`;
  if (type === "photo") return id === context.photo_id ? inspection : null;
  if (type === "order") return `/orders?order=${encodeURIComponent(id)}`;
  if (type === "discrepancy") return inspection;
  if (type === "action")
    return `/operations?action=${encodeURIComponent(id)}#action-${encodeURIComponent(id)}`;
  if (type === "history")
    return `/operations?event=${encodeURIComponent(id)}#audit-${encodeURIComponent(id)}`;
  return null;
}
export function operationEvents<T extends { event_type: string }>(
  events: T[],
): T[] {
  return events.filter((event) =>
    /^(INVESTIGATION_|AGENT_MODEL_|TOOL_|EVIDENCE_|ACTION_|VALIDATION_|APPROVAL_|EXECUTION_|REINSPECTION_|CONTROLLED_ACTION_)/.test(
      event.event_type,
    ),
  );
}
export class SessionOperationKeys {
  private values = new Map<string, string>();
  private makeKey: () => string;
  constructor(makeKey: () => string = () => crypto.randomUUID()) {
    this.makeKey = makeKey;
  }
  get(entity: string, operation: string): string {
    const id = `${entity}:${operation}`;
    let value = this.values.get(id);
    if (!value) {
      value = this.makeKey();
      this.values.set(id, value);
    }
    return value;
  }
}
export const operationKeys = new SessionOperationKeys();
