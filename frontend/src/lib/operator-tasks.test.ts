import { describe, expect, it } from "vitest";
import { taskView } from "./operator-tasks";

describe("operator task queue", () => {
  it("puts saved recommendations at the approval gate", () => {
    expect(taskView("PENDING_APPROVAL")).toBe("AWAITING_APPROVAL");
    expect(taskView("APPROVED")).toBe("AWAITING_APPROVAL");
  });
  it("keeps submitted evidence separate from completed work", () => {
    expect(taskView("EVIDENCE_SUBMITTED")).toBe("AWAITING_EVIDENCE");
    expect(taskView("COMPLETED")).toBe("COMPLETED");
  });
});
