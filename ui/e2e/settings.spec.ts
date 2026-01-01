import { test, expect } from "./fixtures";

test.describe("Settings Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");
  });

  test("should display page header", async ({ page }) => {
    await expect(page.locator("h1", { hasText: "Settings" })).toBeVisible();
    await expect(page.getByText("Configure your a2c instance")).toBeVisible();
  });

  test("should display Save Changes button", async ({ page }) => {
    const saveButton = page.getByRole("button", { name: /save changes/i });
    await expect(saveButton).toBeVisible();
    await expect(saveButton).toBeEnabled();
  });

  test("should display Appearance card", async ({ page }) => {
    await expect(page.getByText("Appearance")).toBeVisible();
    await expect(page.getByText("Dark Mode")).toBeVisible();
    await expect(page.getByText("Toggle dark theme")).toBeVisible();
  });

  test("should toggle dark mode", async ({ page }) => {
    const toggle = page.locator('[role="switch"]').first();
    const html = page.locator("html");

    // Get initial state
    const initialDark = await html.evaluate((el) =>
      el.classList.contains("dark"),
    );

    // Click toggle
    await toggle.click();

    // State should change
    const afterToggle = await html.evaluate((el) =>
      el.classList.contains("dark"),
    );
    expect(afterToggle).toBe(!initialDark);

    // Toggle back
    await toggle.click();
    const afterSecondToggle = await html.evaluate((el) =>
      el.classList.contains("dark"),
    );
    expect(afterSecondToggle).toBe(initialDark);
  });

  test("should display Server Configuration card", async ({ page }) => {
    await expect(page.getByText("Server Configuration")).toBeVisible();
    await expect(page.getByText("Host")).toBeVisible();
    await expect(page.getByText("Port")).toBeVisible();
    await expect(page.getByText("Log Level")).toBeVisible();
    await expect(page.getByText("Debug Mode")).toBeVisible();
    await expect(page.getByText("Metrics")).toBeVisible();
  });

  test("should display server host and port", async ({ page }) => {
    // Check for host value
    await expect(page.getByText("127.0.0.1")).toBeVisible();
    // Check for port value
    await expect(page.getByText("8080")).toBeVisible();
  });

  test("should display log level badge", async ({ page }) => {
    // Check for log level badge (INFO is default)
    await expect(page.getByText("INFO")).toBeVisible();
  });

  test("should display Routing Configuration card", async ({ page }) => {
    await expect(page.getByText("Routing Configuration")).toBeVisible();
    await expect(page.getByText("Default Provider")).toBeVisible();
    await expect(page.getByText("Background Provider")).toBeVisible();
    await expect(page.getByText("Think Provider")).toBeVisible();
    await expect(page.getByText("Long Context Provider")).toBeVisible();
    await expect(page.getByText("Long Context Threshold")).toBeVisible();
  });

  test("should display provider badges in routing config", async ({ page }) => {
    // Check for provider badges
    await expect(page.getByText("anthropic").first()).toBeVisible();
    await expect(page.getByText("antigravity").first()).toBeVisible();
    await expect(page.getByText("gemini").first()).toBeVisible();
  });

  test("should display Provider Credentials card", async ({ page }) => {
    await expect(
      page.getByText("Provider Credentials", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("Provider credentials are managed via environment"),
    ).toBeVisible();
  });

  test("should display provider configuration status", async ({ page }) => {
    // Check for configured/not configured badges
    const configuredBadge = page.getByText("Configured").first();
    const notConfiguredBadge = page.getByText("Not Configured").first();

    const configuredCount = await configuredBadge.count();
    const notConfiguredCount = await notConfiguredBadge.count();

    expect(configuredCount + notConfiguredCount).toBeGreaterThan(0);
  });

  test("should display provider status indicators", async ({ page }) => {
    // Check for status indicator dots
    const greenDots = page.locator(".bg-green-500.rounded-full");
    const grayDots = page.locator(".bg-gray-300.rounded-full");

    const greenCount = await greenDots.count();
    const grayCount = await grayDots.count();

    expect(greenCount + grayCount).toBeGreaterThan(0);
  });

  test("should be responsive on tablet", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });

    await expect(page.locator("h1", { hasText: "Settings" })).toBeVisible();
    await expect(page.getByText("Appearance")).toBeVisible();
    await expect(page.getByText("Server Configuration")).toBeVisible();
  });

  test("should be responsive on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });

    await expect(page.locator("h1", { hasText: "Settings" })).toBeVisible();
    await expect(page.getByText("Dark Mode")).toBeVisible();
  });

  test("should animate cards on load", async ({ page }) => {
    // Cards should be visible after animation
    await expect(page.getByText("Appearance")).toBeVisible();
    await expect(page.getByText("Server Configuration")).toBeVisible();
    await expect(page.getByText("Routing Configuration")).toBeVisible();
    await expect(
      page.getByText("Provider Credentials", { exact: true }),
    ).toBeVisible();
  });
});

test.describe("Settings Page Visual", () => {
  test("full page screenshot", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    await expect(page).toHaveScreenshot("settings-full.png", {
      fullPage: true,
      animations: "disabled",
    });
  });

  test("dark mode screenshot", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Enable dark mode
    const toggle = page.locator('[role="switch"]').first();
    await toggle.click();

    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot("settings-dark.png", {
      fullPage: true,
      animations: "disabled",
    });
  });
});
