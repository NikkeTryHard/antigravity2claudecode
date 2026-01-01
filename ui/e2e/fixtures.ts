import { test as base, expect } from "@playwright/test";

// Mock API responses
const mockResponses = {
  "/health/providers": {
    providers: {
      anthropic: {
        configured: true,
        enabled: true,
        health: { status: "healthy", latency_ms: 150 },
        capabilities: {
          streaming: true,
          thinking: true,
          tools: true,
          vision: true,
        },
      },
      google: {
        configured: true,
        enabled: true,
        health: { status: "healthy", latency_ms: 200 },
        capabilities: {
          streaming: true,
          thinking: false,
          tools: true,
          vision: true,
        },
      },
      openai: {
        configured: false,
        enabled: false,
        health: { status: "unknown" },
        capabilities: {
          streaming: true,
          thinking: false,
          tools: true,
          vision: true,
        },
      },
    },
    total: 3,
    healthy: 2,
    degraded: 0,
    unhealthy: 0,
  },
  "/admin/config": {
    server: {
      host: "127.0.0.1",
      port: 8080,
      log_level: "INFO",
      debug_enabled: true,
      metrics_enabled: true,
    },
    routing: {
      long_context_threshold: 100000,
      default_provider: "anthropic",
      background_provider: "antigravity",
      think_provider: "antigravity",
      long_context_provider: "gemini",
      websearch_provider: "gemini",
    },
    providers: {
      anthropic: { configured: true, base_url: "https://api.anthropic.com" },
      google: { configured: true },
      openai: { configured: false, base_url: "https://api.openai.com/v1" },
    },
  },
  "/admin/routing": {
    default_provider: "anthropic",
    long_context_threshold: 100000,
    rules: [
      {
        name: "background_agents",
        priority: 100,
        condition: "agent_type == 'background'",
        provider: "antigravity",
        enabled: true,
      },
      {
        name: "extended_thinking",
        priority: 90,
        condition: "thinking == true",
        provider: "antigravity",
        enabled: true,
      },
      {
        name: "long_context",
        priority: 80,
        condition: "tokens > 100000",
        provider: "gemini",
        enabled: true,
      },
    ],
  },
  "/debug/requests": {
    items: [],
    total: 0,
    limit: 50,
    offset: 0,
    has_more: false,
  },
  "/debug/stats": {
    period_hours: 24,
    total_requests: 0,
    total_errors: 0,
    error_rate: 0,
    avg_latency_ms: null,
    total_input_tokens: 0,
    total_output_tokens: 0,
    by_provider: {},
  },
};

// Extended test with API mocking
export const test = base.extend({
  page: async ({ page }, use) => {
    // Intercept API calls and return mock data
    await page.route("**/localhost:8080/**", async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname;

      // Find matching mock response
      const mockKey = Object.keys(mockResponses).find(
        (key) => path === key || path.endsWith(key),
      );

      if (mockKey) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(
            mockResponses[mockKey as keyof typeof mockResponses],
          ),
        });
      } else {
        // Return empty response for unmatched routes
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({}),
        });
      }
    });

    await use(page);
  },
});

export { expect };
