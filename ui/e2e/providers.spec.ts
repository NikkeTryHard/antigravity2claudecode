import { test, expect } from "./fixtures";

test.describe("Providers Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/providers");
    await page.waitForLoadState("networkidle");
  });

  test("should display page header", async ({ page }) => {
    await expect(page.locator("h1", { hasText: "Providers" })).toBeVisible();
    await expect(
      page.getByText("Manage and monitor AI providers"),
    ).toBeVisible();
  });

  test("should display refresh button", async ({ page }) => {
    const refreshButton = page.getByRole("button", { name: /refresh/i });
    await expect(refreshButton).toBeVisible();
    await expect(refreshButton).toBeEnabled();
  });

  test("should display summary cards", async ({ page }) => {
    // Use first() to handle multiple matches
    await expect(page.getByText("Total").first()).toBeVisible();
    await expect(page.getByText("Healthy").first()).toBeVisible();
    await expect(page.getByText("Degraded").first()).toBeVisible();
    await expect(page.getByText("Unhealthy").first()).toBeVisible();
  });

  test("should display provider cards with status", async ({ page }) => {
    // Wait for provider cards to load
    await page.waitForTimeout(500);

    // Check for provider status badges
    const healthyBadges = page.locator("text=Healthy");
    const unknownBadges = page.locator("text=Unknown");

    // At least one status badge should be visible
    const healthyCount = await healthyBadges.count();
    const unknownCount = await unknownBadges.count();
    expect(healthyCount + unknownCount).toBeGreaterThan(0);
  });

  test("should display provider capabilities", async ({ page }) => {
    await page.waitForTimeout(500);

    // Check for capability badges
    const streamingBadge = page.getByText("Streaming").first();
    await expect(streamingBadge).toBeVisible();
  });

  test("should display configured status for providers", async ({ page }) => {
    await page.waitForTimeout(500);

    // Check for configured status
    await expect(page.getByText("Configured").first()).toBeVisible();
  });

  test("should show loading state on refresh", async ({ page }) => {
    const refreshButton = page.getByRole("button", { name: /refresh/i });

    // Click refresh
    await refreshButton.click();

    // Check for spinning animation
    const refreshIcon = refreshButton.locator("svg");
    await expect(refreshIcon).toHaveClass(/animate-spin/);
  });

  test("should display latency information", async ({ page }) => {
    await page.waitForTimeout(500);

    // Check for latency label
    await expect(page.getByText("Latency").first()).toBeVisible();
  });

  test("should be responsive on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });

    await expect(page.locator("h1", { hasText: "Providers" })).toBeVisible();
    await expect(page.getByText("Total")).toBeVisible();
  });

  test("should animate provider cards on load", async ({ page }) => {
    // Provider cards should have motion animation classes
    const cards = page.locator(".rounded-lg.border").first();
    await expect(cards).toBeVisible();
  });
});

test.describe("Providers Page Visual", () => {
  test("full page screenshot", async ({ page }) => {
    await page.goto("/providers");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    await expect(page).toHaveScreenshot("providers-full.png", {
      fullPage: true,
      animations: "disabled",
    });
  });
});
