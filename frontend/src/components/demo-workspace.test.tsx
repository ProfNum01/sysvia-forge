import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { DemoWorkspace } from "./demo-workspace";

describe("DemoWorkspace", () => {
  it("shows a recorded Claude judge path only from persisted inspection evidence", () => {
    const client = new QueryClient();
    const inspectionId = "saved-inspection";
    client.setQueryData(["orders"], [{ id: "claude-order", reference: "CLAUDE-MISSING-001", data_source: "synthetic_claude", status: "NEEDS_REVIEW", shipping_status: "HELD", latest_inspection_id: inspectionId, items: [
      { product: { sku: "BLUE-BOX" }, quantity: 2 }, { product: { sku: "YELLOW-POUCH" }, quantity: 1 },
    ] }]);
    client.setQueryData(["demo-assets"], [{ name: "claude-missing-before", title: "Claude before", url: "/api/demo/assets/claude-missing-before", provenance: "synthetic_claude" }]);
    client.setQueryData(["meta-status"], { configured: true });
    client.setQueryData(["inspection", inspectionId], { id: inspectionId, status: "NEEDS_REVIEW", photo_id: "saved-photo", regions: [
      { id: "region-blue", product_id: "claude-blue-box", source: "sam-3.1" },
    ], comparison: [
      { sku: "BLUE-BOX", required_quantity: 2, observed_quantity: 2, status: "MATCHED", evidence_region_ids: ["region-blue"] },
      { sku: "YELLOW-POUCH", required_quantity: 1, observed_quantity: null, status: "NOT_OBSERVED", evidence_region_ids: [] },
    ], execution_events: [
      { id: "one", event_type: "MUSE_ANALYSIS_COMPLETED", details: {} },
      { id: "two", event_type: "SAM_SEGMENTATION_COMPLETED", details: {} },
      { id: "three", event_type: "TOOL_COMPLETED", details: { tool: "check_inventory" } },
    ], investigation_result: { decision: "HUMAN_REVIEW_REQUIRED" }, actions: [{ type: "REQUEST_REINSPECTION", status: "PENDING_APPROVAL" }] });
    const html = renderToStaticMarkup(<QueryClientProvider client={client}><MemoryRouter><DemoWorkspace token="test-token" /></MemoryRouter></QueryClientProvider>);
    expect(html).toContain("Recorded live inference");
    expect(html).toContain("Muse Spark 1.3");
    expect(html).toContain("SAM 3.1");
    expect(html).toContain("NOT OBSERVED is not confirmed missing");
    expect(html).toContain("check_inventory");
    expect(html).toContain("HUMAN_REVIEW_REQUIRED");
    expect(html).toContain("Shipping HELD");
  });
  it("renders only backend supplied synthetic orders and assets with an explicit workflow link", () => {
    const client = new QueryClient();
    client.setQueryData(["orders"], [
      { id: "ord-1", reference: "DEMO-1", data_source: "synthetic_seed", status: "PENDING", shipping_status: "NOT_READY", items: [{ product: { sku: "BOX-A" }, quantity: 2 }] },
      { id: "ord-2", reference: "PRIVATE-2", data_source: "production", status: "PENDING", items: [] },
    ]);
    client.setQueryData(["demo-assets"], [{ name: "missing", title: "Missing item scene", description: "Original fixture", url: "/api/demo/assets/missing", provenance: "original_synthetic_fixture" }]);
    client.setQueryData(["meta-status"], { configured: false });
    // With token: orders section visible, use-in-inspection link present
    const htmlWithToken = renderToStaticMarkup(<QueryClientProvider client={client}><MemoryRouter><DemoWorkspace token="test-token" /></MemoryRouter></QueryClientProvider>);
    expect(htmlWithToken).toContain("DEMO-1");
    expect(htmlWithToken).not.toContain("PRIVATE-2");
    expect(htmlWithToken).toContain("Missing item scene");
    expect(htmlWithToken).toContain("TEST FIXTURE");
    expect(htmlWithToken).toContain("/inspection?order=ord-1&amp;demo=missing");
    expect(htmlWithToken).toContain("Not configured");
    // Without token: orders section hidden, assets still shown, set-token CTA present
    const htmlNoToken = renderToStaticMarkup(<QueryClientProvider client={client}><MemoryRouter><DemoWorkspace token="" /></MemoryRouter></QueryClientProvider>);
    expect(htmlNoToken).not.toContain("DEMO-1");
    expect(htmlNoToken).toContain("Missing item scene");
    expect(htmlNoToken).toContain("Set token to use");
  });
});
