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
