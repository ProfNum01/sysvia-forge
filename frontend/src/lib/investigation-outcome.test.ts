import { describe, expect, it } from "vitest";
import { investigationOutcome } from "./investigation-outcome";

describe("investigationOutcome", () => {
  it("distinguishes human review from corrective action and verified evidence", () => {
    expect(investigationOutcome("HUMAN_REVIEW_REQUIRED", "HELD").title).toBe("مطلوب تدخل بشري");
    expect(investigationOutcome("CORRECTIVE_ACTION_REQUIRED", "HELD").title).toBe("مطلوب إجراء تصحيحي");
    expect(investigationOutcome("NO_ACTION_REQUIRED", "VERIFIED").title).toBe("الفحص يؤيد الطلب");
  });

  it("does not claim a match from an investigation decision alone", () => {
    expect(investigationOutcome("NO_ACTION_REQUIRED", "HELD").title).not.toBe("الفحص يؤيد الطلب");
    expect(investigationOutcome("UNKNOWN", "HELD").title).toBe("نتيجة التحقيق تحتاج مراجعة");
  });
});
