"""Read-only authenticated Chromium walkthrough; never prints the operator token."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.app.core.config import Settings

SCRIPT = r'''
import { chromium } from "playwright";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on("pageerror", e => errors.push(e.message));
page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
const routes = ["/", "/orders", "/inspection", "/operations", "/history", "/demo", "/settings"];
const titles = {};
for (const route of routes) {
  await page.goto(`http://127.0.0.1:5173${route}`, { waitUntil: "networkidle" });
  titles[route] = await page.locator("h1").first().textContent();
}
await page.locator("#operator-token").fill(process.env.PROOFSIGHT_BROWSER_TEST_TOKEN);
await page.getByRole("button", { name: "Set session token" }).click();
const auth = await page.evaluate(async token => {
  const response = await fetch("/api/orders/order-1001/verification-status", { headers: { Authorization: `Bearer ${token}` } });
  return response.status;
}, process.env.PROOFSIGHT_BROWSER_TEST_TOKEN);
await page.goto("http://127.0.0.1:5173/demo", { waitUntil: "networkidle" });
const assets = await page.locator(".demo-asset").count();
await page.screenshot({ path: process.env.PROOFSIGHT_BROWSER_SCREENSHOT, fullPage: true });
await page.setViewportSize({ width: 390, height: 844 });
await page.goto("http://127.0.0.1:5173/demo", { waitUntil: "networkidle" });
const mobileOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
console.log(JSON.stringify({ routes: titles, authenticated_read_status: auth, demo_assets: assets,
  mobile_horizontal_overflow: mobileOverflow, console_error_count: errors.length }));
await browser.close();
'''


def main():
    token = Settings.from_env().operator_token
    if not token:
        print("BLOCKED: OPERATOR_TOKEN is not configured")
        return 2
    screenshot = ROOT / "data/evaluation-results/authenticated-browser.png"
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PROOFSIGHT_BROWSER_TEST_TOKEN": token,
           "PROOFSIGHT_BROWSER_SCREENSHOT": str(screenshot)}
    result = subprocess.run(["node", "--input-type=module", "--eval", SCRIPT],
                            cwd=ROOT / "frontend", env=env, capture_output=True, text=True, timeout=90)
    if result.returncode:
        print("BLOCKED: Chromium walkthrough failed; inspect local browser installation and running servers")
        return 2
    report = json.loads(result.stdout.strip())
    if report["authenticated_read_status"] != 200 or report["mobile_horizontal_overflow"] or report["console_error_count"]:
        print(json.dumps(report))
        return 1
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
