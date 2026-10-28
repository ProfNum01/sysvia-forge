import { describe, expect, it } from "vitest";
import {
  comparisonValue,
  maskTransform,
  regionLabel,
  sourceBox,
  modelEventStatus,
} from "./evidence";

describe("source-coordinate evidence rendering", () => {
  it("reports provider progress only from real events and respects a newer retry", () => {
    expect(modelEventStatus([], "MUSE", false)).toBe("Not recorded");
    expect(
      modelEventStatus(
        [
          { event_type: "MUSE_ANALYSIS_STARTED" },
          { event_type: "MUSE_ANALYSIS_COMPLETED" },
        ],
        "MUSE",
        false,
      ),
    ).toBe("Completed");
    expect(
      modelEventStatus(
        [
          { event_type: "MUSE_ANALYSIS_COMPLETED" },
          { event_type: "MUSE_ANALYSIS_STARTED" },
        ],
        "MUSE",
        false,
      ),
    ).toBe("Started");
    expect(
      modelEventStatus(
        [{ event_type: "SAM_SEGMENTATION_STARTED" }],
        "SAM",
        true,
      ),
    ).toBe("Incomplete");
  });
  it("keeps SAM boxes in original image pixel coordinates", () => {
    expect(sourceBox({ left: 120, top: 90, right: 360, bottom: 450 })).toEqual({
      x: 120,
      y: 90,
      width: 240,
      height: 360,
    });
  });
  it("maps local mask coordinates to the exact backend source bounds", () => {
    expect(
      maskTransform({
        width: 120,
        height: 180,
        bounds: { left: 120, top: 90, right: 360, bottom: 450 },
      }),
    ).toBe("translate(120 90) scale(2 2)");
  });
  it("rejects impossible geometry without substituting a box or mask", () => {
    expect(sourceBox({ left: 50, top: 10, right: 20, bottom: 40 })).toBeNull();
    expect(
      maskTransform({
        width: 0,
        height: 10,
        bounds: { left: 0, top: 0, right: 10, bottom: 10 },
      }),
    ).toBeNull();
    expect(
      sourceBox({ left: NaN, top: 0, right: 100, bottom: 100 }),
    ).toBeNull();
  });
  it("labels geometry unidentified unless a supported product association maps to the catalog", () => {
    const catalog = [{ id: "red", sku: "RED-001" }];
    expect(
      regionLabel({ product_id: null, candidate_product_id: "red" }, catalog),
    ).toBe("UNIDENTIFIED");
    expect(regionLabel({ product_id: "unknown" }, catalog)).toBe(
      "UNIDENTIFIED",
    );
    expect(regionLabel({ product_id: "red" }, catalog)).toBe("RED-001");
  });
  it("preserves unknown observed quantities and differences without turning them into zero", () => {
    expect(comparisonValue(null)).toBe("Not established");
    expect(comparisonValue(undefined)).toBe("Not established");
    expect(comparisonValue(0)).toBe("0");
    expect(comparisonValue(-1)).toBe("-1");
  });
});
