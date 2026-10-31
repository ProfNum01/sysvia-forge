import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { DemoWorkspace } from "./demo-workspace";

describe("DemoWorkspace", () => {
  it("renders only backend supplied synthetic orders and assets with an explicit workflow link", () => {
    const client = new QueryClient();
    client.setQueryData(["orders"], [
      { id: "ord-1", reference: "DEMO-1", data_source: "synthetic_seed", status: "PENDING", shipping_status: "NOT_READY", items: [{ product: { sku: "BOX-A" }, quantity: 2 }] },
      { id: "ord-2", reference: "PRIVATE-2", data_source: "production", status: "PENDING", items: [] },
    ]);
    client.setQueryData(["demo-assets"], [{ name: "missing", title: "Missing item scene", description: "Original fixture", url: "/api/demo/assets/missing", provenance: "original_synthetic_fixture" }]);
    client.setQueryData(["meta-status"], { configured: false });
    const html = renderToStaticMarkup(<QueryClientProvider client={client}><MemoryRouter><DemoWorkspace /></MemoryRouter></QueryClientProvider>);
    expect(html).toContain("DEMO-1");
    expect(html).not.toContain("PRIVATE-2");
    expect(html).toContain("Missing item scene");
    expect(html).toContain("TEST FIXTURE");
    expect(html).toContain("/inspection?order=ord-1&amp;demo=missing");
    expect(html).toContain("Not configured");
  });
});
