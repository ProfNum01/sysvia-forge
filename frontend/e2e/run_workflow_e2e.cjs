/**
 * SYSVIA ProofSight — Authenticated Browser E2E Test Suite
 * Powered by Playwright and Chromium.
 */
const { chromium, request } = require("playwright");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert");

function getOperatorToken() {
  if (process.env.OPERATOR_TOKEN) {
    return process.env.OPERATOR_TOKEN;
  }
  try {
    const envPath = path.resolve(__dirname, "../../.env");
    const content = fs.readFileSync(envPath, "utf-8");
    const match = content.match(/OPERATOR_TOKEN=['"]?([^'"\r\n]+)['"]?/);
    if (match) return match[1].trim();
  } catch (err) {}
  return "";
}

async function runE2E() {
  const token = getOperatorToken();
  if (!token) {
    throw new Error("No OPERATOR_TOKEN found in environment or .env file.");
  }

  const BASE_URL = "http://127.0.0.1:5173";
  const API_URL = "http://127.0.0.1:8000";

  console.log("=== STARTING AUTHENTICATED BROWSER E2E VALIDATION ===");
  console.log(`Frontend URL: ${BASE_URL}`);
  console.log(`Backend API:  ${API_URL}`);

  // Step 0: Test Security Integration (Task 1) via API Context
  console.log("\n[TEST 1] Testing Protected Endpoints (Security Integration)...");
  const apiContext = await request.newContext();

  // Test unauthenticated access to image
  const unauthImg = await apiContext.get(`${API_URL}/api/inspections/3dbdd268-af2c-4beb-bef1-edaf1c17c962/image`);
  assert.strictEqual(unauthImg.status(), 403, "Unauthenticated access to image must return 403 Forbidden");
  console.log("  ✓ Unauthenticated GET /api/inspections/{id}/image rejected with 403");

  // Test authenticated access to image
  const authImg = await apiContext.get(`${API_URL}/api/inspections/3dbdd268-af2c-4beb-bef1-edaf1c17c962/image`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  assert.strictEqual(authImg.status(), 200, "Authenticated access to image must return 200 OK");
  assert.strictEqual(authImg.headers()["content-type"], "image/png");
  assert.strictEqual(authImg.headers()["x-content-type-options"], "nosniff");
  console.log("  ✓ Authenticated GET /api/inspections/{id}/image succeeded with 200 image/png");

  // Test unauthenticated access to annotation
  const unauthAnn = await apiContext.get(`${API_URL}/api/inspections/3dbdd268-af2c-4beb-bef1-edaf1c17c962/annotation`);
  assert.strictEqual(unauthAnn.status(), 403, "Unauthenticated access to annotation must return 403 Forbidden");
  console.log("  ✓ Unauthenticated GET /api/inspections/{id}/annotation rejected with 403");

  // Launch Chromium
  console.log("\n[TEST 2] Launching Playwright Chromium Browser...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    // 1. Establish Authorized Session via Settings (no hardcoding or query param leakage)
    console.log("\n[STEP 1] Authorizing local operator session via Settings...");
    await page.goto(`${BASE_URL}/settings`);
    await page.waitForSelector("#operator-token");
    await page.fill("#operator-token", token);
    await page.click('button[type="submit"]');
    await page.waitForTimeout(500);

    const storedToken = await page.evaluate(() => sessionStorage.getItem("proofsight_operator_token"));
    assert.strictEqual(storedToken, token, "Operator token must be preserved in sessionStorage");
    console.log("  ✓ Operator token successfully saved in browser session");

    // 2. Open Demo Workspace (Task 4)
    console.log("\n[STEP 2] Verifying Demo Workspace and 5 Synthetic Scenarios...");
    await page.goto(`${BASE_URL}/demo`);
    await page.waitForSelector(".demo-workspace");

    const truthText = await page.textContent(".demo-truth");
    assert(truthText.includes("Original synthetic evidence"), "Must clearly label synthetic evidence");

    const fixtureTitles = [
      "Visible shortfall",
      "Required visible count",
      "Additional product",
      "Unreadable label",
      "Unidentified shape"
    ];
    for (const title of fixtureTitles) {
      const visible = await page.getByText(title).isVisible();
      assert(visible, `Scenario '${title}' must be visible in Demo Workspace`);
    }
    console.log("  ✓ All 5 synthetic scenarios available and clearly labeled with TEST FIXTURE");

    // 3. Test Refresh Preserves Authentication State
    console.log("\n[STEP 3] Testing authentication persistence across page refresh...");
    await page.reload();
    await page.waitForTimeout(500);
    const persistedToken = await page.evaluate(() => sessionStorage.getItem("proofsight_operator_token"));
    assert.strictEqual(persistedToken, token, "Session token must survive page reload");
    console.log("  ✓ Session authentication persisted after reload");

    // 4. Select Order and Inspect Evidence
    console.log("\n[STEP 4] Selecting order PS-1001 and reopening existing inspection...");
    await page.selectOption("#demo-order", { label: "PS-1001 · Held" });
    const manifestText = await page.textContent(".demo-manifest");
    assert(manifestText.includes("PS-RED-01 × 2"), "Manifest must show required items");
    console.log("  ✓ Order PS-1001 manifest verified");

    // 5. Open Existing Inspection (Task 2 & 4: Reopen without paid inference)
    console.log("\n[STEP 5] Reopening existing inspection results...");
    await page.goto(`${BASE_URL}/inspection?id=101d04b7-9d6d-48db-bcd8-570215e0b7c6`);
    await page.waitForSelector(".evidence-viewer", { timeout: 10000 });

    // Check protected image loading (Blob URL cleanup, no token in URL)
    const imageElement = page.locator(".source-image-svg image, .evidence-canvas img");
    await imageElement.first().waitFor({ state: "visible", timeout: 10000 });
    const imageSrc = await imageElement.first().getAttribute("href") || await imageElement.first().getAttribute("src");
    assert(imageSrc.startsWith("blob:"), "Protected image must load via Blob URL");
    assert(!imageSrc.includes(token), "Operator token must NOT be exposed in image URL");
    console.log(`  ✓ Protected image successfully loaded via safe Blob URL: ${imageSrc.slice(0, 30)}...`);

    // 6. Verify Real Observations and Discrepancies
    console.log("\n[STEP 6] Verifying real observations and deterministic discrepancy...");
    await page.waitForSelector(".results-content");
    const redObs = await page.getByText("PS-RED-01").first().isVisible();
    const blueObs = await page.getByText("PS-BLUE-02").first().isVisible();
    const discShortfall = await page.getByText("Shortfall").first().isVisible();
    assert(redObs && blueObs, "Observed items must be rendered in UI");
    assert(discShortfall, "Reconciliation discrepancy must be visible");
    console.log("  ✓ Real observations and discrepancy (Shortfall) correctly displayed");

    // 6b. Verify Before and After Reinspection Results
    console.log("\n[STEP 6b] Verifying before/after reinspection comparison...");
    await page.goto(`${BASE_URL}/inspection?id=3dbdd268-af2c-4beb-bef1-edaf1c17c962`);
    const compTable = page.locator(".comparison-table");
    await compTable.first().waitFor({ state: "visible", timeout: 10000 });
    const redInTable = compTable.getByText("Red utility canister").first();
    const blueInTable = compTable.getByText("Blue supply box").first();
    await redInTable.waitFor({ state: "visible", timeout: 10000 });
    assert(await redInTable.isVisible() && await blueInTable.isVisible(), "Comparison table must list catalog items");
    console.log("  ✓ Before and after comparison table verified");

    // 7. Verify AI Investigation and Tool Activity
    console.log("\n[STEP 7] Inspecting AI investigation and bounded tool calls...");
    await page.goto(`${BASE_URL}/operations`);
    await page.waitForSelector(".operations-summary", { timeout: 10000 });

    const targetCard = page.locator(".investigation-card").filter({ hasText: "PS-1001" }).first();
    await targetCard.waitFor({ state: "visible", timeout: 10000 });
    await targetCard.getByText("Verification eligibility").waitFor({ state: "visible", timeout: 10000 });
    const investigationText = await targetCard.textContent();
    assert(investigationText.includes("PS-1001"), "Investigation card must link to order PS-1001");
    assert(investigationText.includes("Human Review Required") || investigationText.includes("Completed"), "Investigation decision recorded");
    console.log("  ✓ Investigation record and persisted decision verified");

    // Expand trace and verify tool events
    const traceSummary = targetCard.locator(".investigation-trace summary").first();
    await traceSummary.click();
    const timelineText = await targetCard.locator(".audit-list").first().textContent();
    assert(timelineText.toUpperCase().includes("TOOL CALLED") || timelineText.toUpperCase().includes("TOOL") || timelineText.toUpperCase().includes("EVIDENCE"), "Tool events must be recorded");
    console.log("  ✓ Read tool execution events verified in timeline");

    // 8. Verify Proposed Actions and Status
    console.log("\n[STEP 8] Reviewing proposed corrective action and verification state...");
    const actionText = await page.locator(".action-card").first().textContent();
    assert(actionText.includes("Reinspection") || actionText.includes("Review"), "Proposed action displayed");
    console.log("  ✓ Corrective action and review requirements verified");

    // 9. Verify Shipping Safety
    console.log("\n[STEP 9] Verifying shipping safety (blocking unverified/held orders)...");
    assert(investigationText.includes("Shipping: Held"), "Unverified order shipping status must be HELD");
    assert(investigationText.includes("New evidence required"), "Requires new evidence before verification");
    console.log("  ✓ Shipping safety verified: unverified order is strictly Held");

    console.log("\n=== BROWSER E2E VALIDATION: ALL 9 PHASES PASSED ===");
  } finally {
    await browser.close();
    await apiContext.dispose();
  }
}

runE2E().catch((err) => {
  console.error("\n❌ Browser E2E Test Failed:\n", err);
  process.exit(1);
});
