import { test, expect } from "@playwright/test";
import * as fs from "node:fs";
import * as path from "node:path";

function localToken(): string {
  if (process.env.OPERATOR_TOKEN) return process.env.OPERATOR_TOKEN;
  const file = path.resolve(process.cwd(), "../.env");
  const content = fs.readFileSync(file, "utf-8");
  return content.match(/^OPERATOR_TOKEN=['"]?([^'"\r\n]+)['"]?/m)?.[1]?.trim() ?? "";
}

test("saved reinspection requests appear in the existing operator queue across reloads", async ({ page, request }) => {
  const token = localToken();
  expect(token).toBeTruthy();
  expect((await request.get("/api/operational-tasks")).status()).toBe(403);
  const budget = await request.get("/api/integrations/meta/budget", { headers: { Authorization: `Bearer ${token}` } });
  expect(budget.status()).toBe(200);
  expect((await budget.json()).remaining_requests).toBe(0);
  await page.goto("/settings");
  await page.fill("#operator-token", token);
  await page.click('button[type="submit"]');
  await page.goto("/operations");
  await expect(page.getByText("Operator task queue")).toBeVisible();
  await expect(page.locator(".operator-task-card").filter({ hasText: "Request Reinspection" }).first()).toBeVisible();
  await expect(page.locator(".operator-task-card").filter({ hasText: "CLAUDE-MISSING-001" })).toContainText("No registered Claude synthetic after-image");
  await page.getByRole("button", { name: /Awaiting Approval/ }).click();
  await expect(page.locator(".operator-task-card").first()).toContainText("Supervisor approval");
  await page.reload();
  await expect(page.locator(".operator-task-card").first()).toBeVisible();
  await page.locator(".operator-task-card").first().getByRole("button", { name: "View timeline" }).click();
  await expect(page.locator(".operator-task-card").first()).toContainText("Operational Task");
});
