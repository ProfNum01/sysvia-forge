export function sortOperationalRecords<T extends { created_at: string; current: boolean; actionable: boolean }>(rows: T[]): T[] {
  return [...rows].sort((a, b) =>
    Number(b.actionable) - Number(a.actionable) ||
    Number(b.current) - Number(a.current) ||
    b.created_at.localeCompare(a.created_at));
}

export function actionButtonLabel(type: string, operation: "approve" | "execute"): string {
  const labels: Record<string, [string, string]> = {
    HOLD_SHIPMENT: ["Approve shipping hold", "Place shipping hold"],
    HOLD_ORDER: ["Approve shipping hold", "Place shipping hold"],
    CREATE_PICKING_TASK: ["Approve picking task", "Create picking task"],
    PROPOSE_CORRECTIVE_PICK: ["Approve picking task", "Create picking task"],
    CREATE_REMOVAL_TASK: ["Approve removal task", "Create removal task"],
    REQUEST_REINSPECTION: ["Approve new photo request", "Request new photo"],
    ESCALATE_TO_HUMAN: ["Approve human review", "Request human review"],
    REQUEST_HUMAN_REVIEW: ["Approve human review", "Request human review"],
    ESCALATE_TO_SUPERVISOR: ["Approve supervisor review", "Request supervisor review"],
  };
  return labels[type]?.[operation === "approve" ? 0 : 1] ?? (operation === "approve" ? "Approve action" : "Execute approved action");
}

export function investigationNextStep(decision: string | undefined, status: string): { label: string; explanation: string; target: "evidence" | "action" | "task" } {
  if (decision === "CORRECTIVE_ACTION_REQUIRED") return { label: "Review proposed action", explanation: "A supervisor must review the server-validated proposal before any execution.", target: "action" };
  if (decision === "EXISTING_ACTION_IN_PROGRESS") return { label: "Track operator task", explanation: "Follow the recorded task, then submit a new photo for reinspection.", target: "task" };
  if (decision === "NO_ACTION_REQUIRED" && status === "VERIFIED") return { label: "View verified evidence", explanation: "The current inspection supports this result. Shipping remains a separate controlled step.", target: "evidence" };
  if (decision === "HUMAN_REVIEW_REQUIRED") return { label: "Review uncertain evidence", explanation: "Identity or quantity is not established. Review the photo and request new evidence if needed.", target: "evidence" };
  return { label: "Review inspection evidence", explanation: "The result is unresolved. Inspect the recorded photo and findings before taking action.", target: "evidence" };
}
