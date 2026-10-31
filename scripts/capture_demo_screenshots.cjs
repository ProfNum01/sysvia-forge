const { chromium } = require("../frontend/node_modules/playwright");
const fs = require("node:fs");
const path = require("node:path");

async function capture() {
  const envContent = fs.readFileSync(path.resolve(__dirname, "../.env"), "utf-8");
  const token = envContent.match(/OPERATOR_TOKEN=['"]?([^'"\r\n]+)/)[1].trim();
  const outDir = path.resolve(__dirname, "../submission/demo-assets");

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // Authorize session
  await page.goto("http://127.0.0.1:5173/settings");
  await page.fill("#operator-token", token);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(500);

  // 1. Dashboard / Overview
  console.log("Capturing 01_dashboard.png...");
  await page.goto("http://127.0.0.1:5173/");
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: path.join(outDir, "01_dashboard.png"), fullPage: false });

  // 2. Demo Workspace
  console.log("Capturing 02_demo_workspace.png...");
  await page.goto("http://127.0.0.1:5173/demo");
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: path.join(outDir, "02_demo_workspace.png"), fullPage: false });

  // 3. Inspection Evidence & Discrepancies
  console.log("Capturing 03_visual_inspection.png...");
  await page.goto("http://127.0.0.1:5173/inspection?id=101d04b7-9d6d-48db-bcd8-570215e0b7c6");
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: path.join(outDir, "03_visual_inspection.png"), fullPage: false });

  // 4. Before & After Reinspection
  console.log("Capturing 04_before_after_reinspection.png...");
  await page.goto("http://127.0.0.1:5173/inspection?id=3dbdd268-af2c-4beb-bef1-edaf1c17c962");
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: path.join(outDir, "04_before_after_reinspection.png"), fullPage: false });

  // 5. AI Operations & Tool Traces
  console.log("Capturing 05_ai_operations.png...");
  await page.goto("http://127.0.0.1:5173/operations");
  await page.waitForLoadState("networkidle");
  const trace = page.locator(".investigation-trace summary").first();
  if (await trace.isVisible()) {
    await trace.click();
    await page.waitForTimeout(400);
  }
  await page.screenshot({ path: path.join(outDir, "05_ai_operations.png"), fullPage: false });

  await browser.close();
  console.log("Screenshots captured successfully.");
}

capture().catch((err) => {
  console.error("Screenshot capture failed:", err);
  process.exit(1);
});
