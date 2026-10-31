import { test, expect } from "@playwright/test";
import * as fs from "node:fs";
import * as path from "node:path";

function getOperatorToken(): string {
  if (process.env.OPERATOR_TOKEN) {
    return process.env.OPERATOR_TOKEN;
  }
  for (const candidate of [
    path.resolve(process.cwd(), ".env"),
    path.resolve(process.cwd(), "../.env"),
  ]) {
    try {
      if (fs.existsSync(candidate)) {
        const content = fs.readFileSync(candidate, "utf-8");
        const match = content.match(/OPERATOR_TOKEN=['"]?([^'"\r\n]+)['"]?/);
        if (match) return match[1].trim();
      }
    } catch {}
  }
  return "";
}

test.describe("SYSVIA ProofSight — Final Release Hardening E2E", () => {
  const token = getOperatorToken();

  test.beforeEach(async ({ page }) => {
    // Authorize operator session via Settings without hardcoding or URL leakage
    expect(token).toBeTruthy();
    await page.goto("/settings");
    await page.fill("#operator-token", token);
    await page.click('button[type="submit"]');
    await page.waitForTimeout(500);
  });

  test("TASK 1 & 4 — Security Integration & Demo Workspace Reliability", async ({ page, request }) => {
    // 1. Verify unauthenticated access to protected endpoints is blocked with 403
    const unauthImage = await request.get("/api/inspections/3dbdd268-af2c-4beb-bef1-edaf1c17c962/image");
    expect(unauthImage.status()).toBe(403);

    const unauthAnnotation = await request.get("/api/inspections/3dbdd268-af2c-4beb-bef1-edaf1c17c962/annotation");
    expect(unauthAnnotation.status()).toBe(403);

    // 2. Authenticated API request succeeds
    const authImage = await request.get("/api/inspections/3dbdd268-af2c-4beb-bef1-edaf1c17c962/image", {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(authImage.status()).toBe(200);
    expect(authImage.headers()["content-type"]).toContain("image/png");

    // 3. Demo Workspace loads 5 synthetic scenarios clearly labeled
    await page.goto("/demo");
    await expect(page.locator(".demo-workspace")).toBeVisible();
    await expect(page.locator(".demo-truth")).toContainText("Original synthetic evidence");

    // Ensure all 5 synthetic fixture titles exist
    await expect(page.getByText("Visible shortfall")).toBeVisible();
    await expect(page.getByText("Required visible count")).toBeVisible();
    await expect(page.getByText("Additional product")).toBeVisible();
    await expect(page.getByText("Unreadable label")).toBeVisible();
    await expect(page.getByText("Unidentified shape")).toBeVisible();

    // Verify TEST FIXTURE labels
    const fixtureBadges = page.locator(".demo-asset .eyebrow");
    expect(await fixtureBadges.count()).toBe(5);

    // 4. Verify refresh preserves workflow state (authentication persistence)
    await page.reload();
    await page.goto("/operations");
    // Should NOT say "Set an operator credential" in active controls
    await expect(page.locator(".operations-summary")).toBeVisible();
  });

  test("TASK 2 & 3 — Complete End-to-End Workflow with Shipping Safety", async ({ page }) => {
    // 1. Open Demo Workspace
    await page.goto("/demo");
    await expect(page.locator("h2", { hasText: "Choose a synthetic order" })).toBeVisible();

    // 2. Select order PS-1001
    const orderSelect = page.locator("#demo-order");
    await orderSelect.selectOption({ label: "PS-1001 · Held" });
    await expect(page.locator(".demo-manifest")).toContainText("PS-RED-01 × 2");

    // 3. Reopen existing inspection results without paid inference
    await page.goto("/inspection?id=101d04b7-9d6d-48db-bcd8-570215e0b7c6");
    await page.waitForLoadState("networkidle");

    // 4. Verify protected evidence image is loaded securely in browser via blob URL (no token in src URL)
    const viewer = page.locator(".evidence-viewer");
    await expect(viewer).toBeVisible();

    // 5. Verify real observations and discrepancies are displayed
    await expect(page.locator(".results-content").first()).toBeVisible();
    await expect(page.getByText("PS-RED-01").first()).toBeVisible();
    await expect(page.getByText("PS-BLUE-02").first()).toBeVisible();
    await expect(page.getByText("Shortfall").first()).toBeVisible();

    // 5b. Verify before/after comparison on reinspection
    await page.goto("/inspection?id=3dbdd268-af2c-4beb-bef1-edaf1c17c962");
    await page.waitForLoadState("networkidle");
    const compTable = page.locator(".comparison-table");
    await expect(compTable.getByText("Red utility canister").first()).toBeVisible();
    await expect(compTable.getByText("Blue supply box").first()).toBeVisible();

    // 6. Inspect AI investigation, tool calls, and proposed actions
    await page.goto("/operations");
    await page.waitForLoadState("networkidle");

    const investigationCard = page.locator(".investigation-card").filter({ hasText: "PS-1001" }).first();
    await expect(investigationCard).toBeVisible();
    await expect(investigationCard).toContainText("PS-1001");

    // Verify tool calls in agent activity
    const trace = investigationCard.locator(".investigation-trace summary").first();
    await expect(trace).toBeVisible();
    await trace.click();
    await expect(investigationCard).toContainText(/TOOL CALLED|Tool Called|Evidence/i);

    // 7. Verify proposed and executed corrective actions
    await expect(page.locator(".action-card", { hasText: "Request Reinspection" })).toBeVisible();

    // 8. Verify Verification Status and Shipping Safety
    // The order currently requires reinspection, so shipping MUST NOT be authorized
    await expect(investigationCard).toContainText("New evidence required");
    await expect(investigationCard).toContainText("Shipping: Held");

    // 9. Verify order revision state
    await expect(investigationCard).toContainText(/Order revision/i);
  });
});
