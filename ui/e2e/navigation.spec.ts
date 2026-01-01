import { test, expect } from "./fixtures";

test.describe("Navigation", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
  });

  test("should display sidebar with all navigation items", async ({ page }) => {
    const sidebar = page.locator("nav");
    await expect(sidebar).toBeVisible();

    // Check app title
    await expect(sidebar.getByRole("heading", { name: "a2c" })).toBeVisible();
    await expect(sidebar.getByText("AI API Router")).toBeVisible();

    // Check all nav items
    await expect(
      sidebar.getByRole("link", { name: "Dashboard" }),
    ).toBeVisible();
    await expect(
      sidebar.getByRole("link", { name: "Providers" }),
    ).toBeVisible();
    await expect(sidebar.getByRole("link", { name: "Routing" })).toBeVisible();
    await expect(sidebar.getByRole("link", { name: "Logs" })).toBeVisible();
    await expect(sidebar.getByRole("link", { name: "Debug" })).toBeVisible();
    await expect(sidebar.getByRole("link", { name: "Settings" })).toBeVisible();
  });

  test("should navigate to Providers page", async ({ page }) => {
    await page.getByRole("link", { name: "Providers" }).click();
    await expect(page).toHaveURL("/providers");
    // Wait for content to load (either from API or mock data)
    await expect(page.locator("h1", { hasText: "Providers" })).toBeVisible({
      timeout: 10000,
    });
  });

  test("should navigate to Routing page", async ({ page }) => {
    await page.getByRole("link", { name: "Routing" }).click();
    await expect(page).toHaveURL("/routing");
    await expect(page.locator("h1", { hasText: "Routing" })).toBeVisible({
      timeout: 10000,
    });
  });

  test("should navigate to Logs page", async ({ page }) => {
    await page.getByRole("link", { name: "Logs" }).click();
    await expect(page).toHaveURL("/logs");
    await expect(page.locator("h1", { hasText: "Logs" })).toBeVisible({
      timeout: 10000,
    });
  });

  test("should navigate to Debug page", async ({ page }) => {
    await page.getByRole("link", { name: "Debug" }).click();
    await expect(page).toHaveURL("/debug");
    await expect(page.locator("h1", { hasText: "Debug" })).toBeVisible({
      timeout: 10000,
    });
  });

  test("should navigate to Settings page", async ({ page }) => {
    await page.getByRole("link", { name: "Settings" }).click();
    await expect(page).toHaveURL("/settings");
    await expect(page.locator("h1", { hasText: "Settings" })).toBeVisible({
      timeout: 10000,
    });
  });

  test("should highlight active navigation item", async ({ page }) => {
    // Dashboard should be active initially
    const dashboardLink = page.getByRole("link", { name: "Dashboard" });
    await expect(dashboardLink).toHaveClass(/bg-primary/);

    // Navigate to Providers
    await page.getByRole("link", { name: "Providers" }).click();
    await page.waitForURL("/providers");

    // Providers should now be active
    const providersLink = page.getByRole("link", { name: "Providers" });
    await expect(providersLink).toHaveClass(/bg-primary/);

    // Dashboard should no longer be active
    await expect(dashboardLink).not.toHaveClass(/bg-primary/);
  });

  test("should display version in sidebar footer", async ({ page }) => {
    await expect(page.getByText("v0.1.0")).toBeVisible();
  });

  test("should navigate back to Dashboard from other pages", async ({
    page,
  }) => {
    // Go to Settings
    await page.getByRole("link", { name: "Settings" }).click();
    await expect(page).toHaveURL("/settings");

    // Go back to Dashboard
    await page.getByRole("link", { name: "Dashboard" }).click();
    await expect(page).toHaveURL("/");
    await page.waitForLoadState("networkidle");
    await expect(
      page.locator("h1", { hasText: "A2C Dashboard" }),
    ).toBeVisible();
  });
});
