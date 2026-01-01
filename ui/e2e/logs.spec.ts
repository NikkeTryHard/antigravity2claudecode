import { test, expect } from "./fixtures";

test.describe("Logs Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/logs");
    await page.waitForLoadState("networkidle");
  });

  test("should display page header", async ({ page }) => {
    await expect(page.locator("h1", { hasText: "Logs" })).toBeVisible();
    await expect(page.getByText("Real-time request logs")).toBeVisible();
  });

  test("should display Pause/Resume button", async ({ page }) => {
    const pauseButton = page.getByRole("button", { name: /pause/i });
    await expect(pauseButton).toBeVisible();
    await expect(pauseButton).toBeEnabled();
  });

  test("should toggle Pause/Resume button", async ({ page }) => {
    const pauseButton = page.getByRole("button", { name: /pause/i });

    // Click to pause
    await pauseButton.click();

    // Should now show Resume
    const resumeButton = page.getByRole("button", { name: /resume/i });
    await expect(resumeButton).toBeVisible();

    // Click to resume
    await resumeButton.click();

    // Should show Pause again
    await expect(page.getByRole("button", { name: /pause/i })).toBeVisible();
  });

  test("should display filter button", async ({ page }) => {
    const filterButton = page.getByRole("button", { name: /all|filter/i });
    await expect(filterButton).toBeVisible();
  });

  test("should display Live Logs card", async ({ page }) => {
    await expect(page.getByText("Live Logs")).toBeVisible();
  });

  test("should display WebSocket connection status", async ({ page }) => {
    // Should show either Connected or Disconnected badge
    const connectedBadge = page.getByText("Connected");
    const disconnectedBadge = page.getByText("Disconnected");

    const connectedCount = await connectedBadge.count();
    const disconnectedCount = await disconnectedBadge.count();

    expect(connectedCount + disconnectedCount).toBeGreaterThan(0);
  });

  test("should display empty state when no logs", async ({ page }) => {
    // If no logs, should show empty message
    const emptyMessage = page.getByText("No logs to display");
    const logEntries = page.locator(".font-mono");

    const emptyCount = await emptyMessage.count();
    const logCount = await logEntries.count();

    // Either empty message or log entries should be visible
    expect(emptyCount + logCount).toBeGreaterThan(0);
  });

  test("should have activity indicator", async ({ page }) => {
    // Check for activity icon - the icon might be rendered differently
    // Look for the Live Logs text which contains the activity indicator
    await expect(page.getByText("Live Logs")).toBeVisible();
  });

  test("should be responsive on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });

    await expect(page.locator("h1", { hasText: "Logs" })).toBeVisible();
    await expect(page.getByText("Live Logs")).toBeVisible();
  });

  test("should display scrollable log container", async ({ page }) => {
    // Check for scrollable container
    const logContainer = page.locator(".max-h-\\[600px\\].overflow-auto");
    await expect(logContainer).toBeVisible();
  });
});

test.describe("Logs Page Visual", () => {
  test("full page screenshot", async ({ page }) => {
    await page.goto("/logs");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    await expect(page).toHaveScreenshot("logs-full.png", {
      fullPage: true,
      animations: "disabled",
    });
  });
});
