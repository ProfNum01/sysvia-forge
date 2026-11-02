import { describe, expect, it } from "vitest";
import { actionButtonLabel, investigationNextStep, sortOperationalRecords } from "./operations-presentation";

describe("operations presentation", () => {
  it("orders actionable current records before old history", () => {
    const rows = [
      { id: "old", created_at: "2026-11-01T00:00:00Z", current: false, actionable: false },
      { id: "current", created_at: "2026-11-01T00:00:00Z", current: true, actionable: false },
      { id: "review", created_at: "2026-10-30T00:00:00Z", current: true, actionable: true },
    ];
    expect(sortOperationalRecords(rows).map((row) => row.id)).toEqual(["review", "current", "old"]);
  });

  it("gives different labels only for actions the server can authorize", () => {
    expect(actionButtonLabel("CREATE_PICKING_TASK", "approve")).toBe("Approve picking task");
    expect(actionButtonLabel("CREATE_REMOVAL_TASK", "execute")).toBe("Create removal task");
    expect(actionButtonLabel("HOLD_SHIPMENT", "execute")).toBe("Place shipping hold");
    expect(actionButtonLabel("REQUEST_REINSPECTION", "approve")).toBe("Approve new photo request");
  });

  it("distinguishes verified, uncertain, correction, and follow-up outcomes", () => {
    expect(investigationNextStep("HUMAN_REVIEW_REQUIRED", "HELD").label).toBe("Review uncertain evidence");
    expect(investigationNextStep("CORRECTIVE_ACTION_REQUIRED", "HELD").label).toBe("Review proposed action");
    expect(investigationNextStep("EXISTING_ACTION_IN_PROGRESS", "HELD").label).toBe("Track operator task");
    expect(investigationNextStep("NO_ACTION_REQUIRED", "VERIFIED").label).toBe("View verified evidence");
  });
});
