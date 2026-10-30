import { describe, expect, it } from "vitest";
import {
  actionControls,
  actionImpact,
  actionName,
  evidenceLink,
  operationEvents,
  SessionOperationKeys,
} from "./operations";

describe("controlled operations interface", () => {
  it("exposes review controls only before a decision and execution only after approval", () => {
    expect(
      actionControls({
        type: "HOLD_SHIPMENT",
        status: "APPROVED",
        lifecycle_state: "EXECUTED",
      }),
    ).toEqual({ approve: false, reject: false, execute: false });
    expect(
      actionControls({
        type: "HOLD_SHIPMENT",
        status: "PROPOSED",
        lifecycle_state: "AWAITING_REINSPECTION",
      }),
    ).toEqual({ approve: false, reject: false, execute: false });
    expect(
      actionControls({
        type: "CREATE_PICKING_TASK",
        status: "PENDING_APPROVAL",
      }),
    ).toEqual({ approve: true, reject: true, execute: false });
    expect(
      actionControls({ type: "HOLD_SHIPMENT", status: "APPROVED" }),
    ).toEqual({ approve: false, reject: false, execute: true });
    expect(
      actionControls({
        type: "HOLD_SHIPMENT",
        status: "EXECUTED",
        lifecycle_state: "AWAITING_REINSPECTION",
      }),
    ).toEqual({ approve: false, reject: false, execute: false });
    expect(
      actionControls({ type: "UNRESTRICTED_SQL", status: "APPROVED" }),
    ).toEqual({ approve: false, reject: false, execute: false });
  });
  it("supports legacy holds and all four policy action types without implying a physical correction", () => {
    expect(actionName("HOLD_ORDER")).toBe("Hold Shipment");
    for (const type of [
      "HOLD_SHIPMENT",
      "CREATE_PICKING_TASK",
      "REQUEST_REINSPECTION",
      "ESCALATE_TO_HUMAN",
    ])
      expect(actionControls({ type, status: "PROPOSED" }).approve).toBe(true);
    expect(actionImpact("CREATE_PICKING_TASK")).toMatch(
      /Inventory is not deducted/,
    );
  });
  it("links only recognized evidence to its supported workspace target", () => {
    const context = {
      inspection_id: "ins-1",
      order_id: "order-1",
      photo_id: "photo-1",
    };
    expect(evidenceLink("region:region-2", context)).toBe(
      "/inspection?id=ins-1&region=region-2",
    );
    expect(evidenceLink("photo:photo-1", context)).toBe("/inspection?id=ins-1");
    expect(evidenceLink("photo:other-photo", context)).toBeNull();
    expect(evidenceLink("https://unknown.example", context)).toBeNull();
  });
  it("filters the actual recorded operations events without synthesizing a timeline", () => {
    const rows = [
      { id: "one", event_type: "MUSE_ANALYSIS_STARTED" },
      { id: "two", event_type: "TOOL_CALLED" },
      { id: "three", event_type: "INVESTIGATION_STARTED" },
      { id: "four", event_type: "AGENT_MODEL_COMPLETED" },
    ];
    expect(operationEvents(rows).map((event) => event.id)).toEqual([
      "two",
      "three",
      "four",
    ]);
    expect(operationEvents([])).toEqual([]);
  });
  it("keeps request keys stable per entity and operation across component remounts", () => {
    let count = 0;
    const keys = new SessionOperationKeys(() => `key-${++count}`);
    expect(keys.get("action-1", "approve")).toBe(
      keys.get("action-1", "approve"),
    );
    expect(keys.get("action-1", "reject")).not.toBe(
      keys.get("action-1", "approve"),
    );
    expect(keys.get("action-2", "approve")).not.toBe(
      keys.get("action-1", "approve"),
    );
  });
});
