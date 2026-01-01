import { test, expect } from "./fixtures";

test.describe("Debug Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/debug");
    await page.waitForLoadState("networkidle");
  });

  test("should display page header", async ({ page }) => {
    await expect(page.locator("h1", { hasText: "Debug" })).toBeVisible();
    await expect(page.getByText("Inspect request/response data")).toBeVisible();
  });

  test("should display Refresh button", async ({ page }) => {
    const refreshButton = page.getByRole("button", { name: /refresh/i });
    await expect(refreshButton).toBeVisible();
    await expect(refreshButton).toBeEnabled();
  });

  test("should display stats cards", async ({ page }) => {
    await expect(page.getByText("Requests (24h)")).toBeVisible();
    await expect(page.getByText("Errors")).toBeVisible();
    await expect(page.getByText("Error Rate")).toBeVisible();
    await expect(page.getByText("Avg Latency")).toBeVisible();
  });

  test("should display stats values", async ({ page }) => {
    // Stats should show numeric values
    const statsCards = page.locator(".text-2xl.font-bold");
    expect(await statsCards.count()).toBeGreaterThanOrEqual(4);
  });

  test("should display Recent Requests card", async ({ page }) => {
    await expect(page.getByText("Recent Requests")).toBeVisible();
  });

  test("should display Request Inspector card", async ({ page }) => {
    await expect(page.getByText("Request Inspector")).toBeVisible();
  });

  test("should display empty inspector state", async ({ page }) => {
    // When no request is selected, should show prompt
    await expect(page.getByText("Select a request to inspect")).toBeVisible();
  });

  test("should have two-column layout on desktop", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });

    // Both cards should be visible side by side
    await expect(page.getByText("Recent Requests")).toBeVisible();
    await expect(page.getByText("Request Inspector")).toBeVisible();
  });

  test("should be responsive on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });

    await expect(page.locator("h1", { hasText: "Debug" })).toBeVisible();
    await expect(page.getByText("Requests (24h)")).toBeVisible();
  });

  test("should display scrollable request list", async ({ page }) => {
    // Check for scrollable container - the class might be different
    const requestList = page.locator(".overflow-auto").first();
    await expect(requestList).toBeVisible();
  });
});

test.describe("Debug Page Interactions", () => {
  test("should refresh data when clicking refresh button", async ({ page }) => {
    await page.goto("/debug");
    await page.waitForLoadState("networkidle");

    const refreshButton = page.getByRole("button", { name: /refresh/i });

    // Click refresh
    await refreshButton.click();

    // Page should still be functional after refresh
    await expect(page.getByText("Recent Requests")).toBeVisible();
  });
});

test.describe("Debug Page Visual", () => {
  test("full page screenshot", async ({ page }) => {
    await page.goto("/debug");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    await expect(page).toHaveScreenshot("debug-full.png", {
      fullPage: true,
      animations: "disabled",
    });
  });
});
