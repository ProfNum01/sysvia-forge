import { describe, expect, it } from "vitest";
import {
  buildInspectionUpload,
  canAnalyzeInspection,
  canReinspectInspection,
  inspectionHref,
  UploadIdempotency,
} from "./workflow";

describe("inspection backend contract", () => {
  it("reuses an upload idempotency key only for the same file, order, and parent", () => {
    let sequence = 0;
    const identity = new UploadIdempotency(() => `request-${++sequence}`);
    const file = new File(["image"], "evidence.png", { type: "image/png" });
    expect(identity.keyFor(file, "order-1", null)).toBe("request-1");
    expect(identity.keyFor(file, "order-1", null)).toBe("request-1");
    expect(identity.keyFor(file, "order-2", null)).toBe("request-2");
    expect(identity.keyFor(file, "order-2", "parent-1")).toBe("request-3");
    expect(
      identity.keyFor(
        new File(["image"], "evidence.png"),
        "order-2",
        "parent-1",
      ),
    ).toBe("request-4");
    identity.reset();
    expect(identity.keyFor(file, "order-2", "parent-1")).toBe("request-5");
  });
  it("includes rights confirmation and order for initial upload", () => {
    const body = buildInspectionUpload(
      new File(["image"], "evidence.png", { type: "image/png" }),
      "order-1",
    );
    expect(body.get("rights_confirmed")).toBe("true");
    expect(body.get("order_id")).toBe("order-1");
    expect(body.get("image")).toBeInstanceOf(File);
  });
  it("includes rights confirmation without an order for reinspection", () => {
    const body = buildInspectionUpload(
      new File(["new image"], "new.png", { type: "image/png" }),
    );
    expect(body.get("rights_confirmed")).toBe("true");
    expect(body.has("order_id")).toBe(false);
  });
  it("opens existing inspection chains instead of creating another initial inspection", () => {
    expect(inspectionHref({ id: "o-1", latest_inspection_id: "i-1" })).toBe(
      "/inspection?id=i-1",
    );
    expect(inspectionHref({ id: "o-2", latest_inspection_id: null })).toBe(
      "/inspection?order=o-2",
    );
  });
  it("blocks analysis while preparing, for stale evidence, and after an analysis result", () => {
    expect(
      canAnalyzeInspection(
        { id: "i-1", status: "UPLOADED" },
        { latest_inspection_id: "i-1", preparation_status: "PREPARING" },
      ),
    ).toBe(false);
    expect(
      canAnalyzeInspection(
        { id: "i-1", status: "PROVIDER_ERROR" },
        { latest_inspection_id: "i-2", preparation_status: "READY" },
      ),
    ).toBe(false);
    expect(
      canAnalyzeInspection(
        { id: "i-1", status: "NEEDS_REVIEW" },
        { latest_inspection_id: "i-1", preparation_status: "READY" },
      ),
    ).toBe(false);
    expect(
      canAnalyzeInspection(
        { id: "i-1", status: "UPLOADED" },
        { latest_inspection_id: "i-1", preparation_status: "READY" },
      ),
    ).toBe(true);
  });
  it("requires the latest analyzed image before reinspection", () => {
    expect(
      canReinspectInspection({ id: "i-1", status: "UPLOADED" }, "i-1"),
    ).toBe(false);
    expect(
      canReinspectInspection({ id: "i-1", status: "ANALYZING" }, "i-1"),
    ).toBe(false);
    expect(
      canReinspectInspection({ id: "i-1", status: "NEEDS_REVIEW" }, "i-2"),
    ).toBe(false);
    expect(
      canReinspectInspection({ id: "i-1", status: "PROVIDER_ERROR" }, "i-1"),
    ).toBe(true);
  });
});
