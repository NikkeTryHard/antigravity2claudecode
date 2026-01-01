import { test, expect } from "./fixtures";

test.describe("Routing Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/routing");
    await page.waitForLoadState("networkidle");
  });

  test("should display page header", async ({ page }) => {
    await expect(page.locator("h1", { hasText: "Routing" })).toBeVisible();
    await expect(
      page.getByText("Configure request routing rules"),
    ).toBeVisible();
  });

  test("should display Add Rule button", async ({ page }) => {
    const addButton = page.getByRole("button", { name: /add rule/i });
    await expect(addButton).toBeVisible();
    await expect(addButton).toBeEnabled();
  });

  test("should display Default Settings card", async ({ page }) => {
    await expect(page.getByText("Default Settings")).toBeVisible();
    await expect(page.getByText("Default Provider")).toBeVisible();
    await expect(page.getByText("Long Context Threshold")).toBeVisible();
    await expect(page.getByText("Active Rules")).toBeVisible();
  });

  test("should display default provider value", async ({ page }) => {
    // Check for provider name (anthropic is the default)
    await expect(page.getByText("anthropic").first()).toBeVisible();
  });

  test("should display long context threshold", async ({ page }) => {
    // Check for token count - the text might be formatted differently
    await expect(page.getByText(/100,?000/).first()).toBeVisible();
  });

  test("should display Routing Flow visualization", async ({ page }) => {
    await expect(page.getByText("Routing Flow")).toBeVisible();
    await expect(page.getByText("Request", { exact: true })).toBeVisible();
    await expect(page.getByText("Rules Engine")).toBeVisible();
  });

  test("should display provider options in flow", async ({ page }) => {
    // Check for provider names in the flow visualization
    await expect(page.getByText("anthropic").first()).toBeVisible();
    await expect(page.getByText("antigravity").first()).toBeVisible();
    await expect(page.getByText("gemini").first()).toBeVisible();
    await expect(page.getByText("openai").first()).toBeVisible();
  });

  test("should display Routing Rules card", async ({ page }) => {
    await expect(
      page.getByText("Routing Rules", { exact: true }),
    ).toBeVisible();
  });

  test("should display routing rules with priority badges", async ({
    page,
  }) => {
    await page.waitForTimeout(500);

    // Check for priority badges (numbers like 100, 90, 80)
    const priorityBadges = page.locator('[class*="outline"]');
    expect(await priorityBadges.count()).toBeGreaterThan(0);
  });

  test("should display rule names", async ({ page }) => {
    await page.waitForTimeout(500);

    // Check for rule names
    await expect(page.getByText("background_agents")).toBeVisible();
    await expect(page.getByText("extended_thinking")).toBeVisible();
    await expect(page.getByText("long_context")).toBeVisible();
  });

  test("should display rule conditions", async ({ page }) => {
    await page.waitForTimeout(500);

    // Check for condition expressions
    await expect(page.getByText("agent_type == 'background'")).toBeVisible();
    await expect(page.getByText("thinking == true")).toBeVisible();
    await expect(page.getByText("tokens > 100000")).toBeVisible();
  });

  test("should display Edit buttons for rules", async ({ page }) => {
    await page.waitForTimeout(500);

    const editButtons = page.getByRole("button", { name: "Edit" });
    expect(await editButtons.count()).toBeGreaterThan(0);
  });

  test("should be responsive on tablet", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });

    await expect(page.locator("h1", { hasText: "Routing" })).toBeVisible();
    await expect(page.getByText("Default Settings")).toBeVisible();
    await expect(
      page.getByText("Routing Rules", { exact: true }),
    ).toBeVisible();
  });

  test("should be responsive on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });

    await expect(page.locator("h1", { hasText: "Routing" })).toBeVisible();
    await expect(page.getByText("Default Provider")).toBeVisible();
  });
});

test.describe("Routing Page Visual", () => {
  test("full page screenshot", async ({ page }) => {
    await page.goto("/routing");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    await expect(page).toHaveScreenshot("routing-full.png", {
      fullPage: true,
      animations: "disabled",
    });
  });
});
