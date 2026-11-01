export const taskViews = [
  "ALL", "PENDING", "ASSIGNED", "IN_PROGRESS", "AWAITING_EVIDENCE",
  "AWAITING_APPROVAL", "COMPLETED", "ESCALATED",
] as const;

export type TaskView = (typeof taskViews)[number];

export function taskView(status: string): TaskView {
  if (["PENDING_APPROVAL", "APPROVED"].includes(status)) return "AWAITING_APPROVAL";
  if (status === "OPEN") return "PENDING";
  if (["ASSIGNED", "ACKNOWLEDGED"].includes(status)) return "ASSIGNED";
  if (status === "IN_PROGRESS") return "IN_PROGRESS";
  if (["EVIDENCE_REQUIRED", "EVIDENCE_SUBMITTED"].includes(status)) return "AWAITING_EVIDENCE";
  if (status === "COMPLETED") return "COMPLETED";
  if (status === "ESCALATED") return "ESCALATED";
  return "PENDING";
}
