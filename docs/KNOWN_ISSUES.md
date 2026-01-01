# Known Issues and Technical Debt

This document tracks known issues, limitations, and areas for improvement in the a2c project. Items are categorized by severity and component.

## Table of Contents

- [Critical Issues](#critical-issues)
- [High Priority](#high-priority)
- [Medium Priority](#medium-priority)
- [Low Priority](#low-priority)
- [Technical Debt](#technical-debt)
- [Future Enhancements](#future-enhancements)

---

## Critical Issues

_No critical issues at this time._

---

## High Priority

### 1. E2E Tests Use API Mocking - May Hide Real Integration Issues

**Component:** UI / Testing
**File:** `ui/e2e/fixtures.ts`
**Status:** Open

**Description:**
The Playwright E2E tests mock all API responses via the `fixtures.ts` file. While this allows tests to run without a backend, it means:

- Tests won't catch actual API integration issues
- Mock data structure might drift from the real API over time
- Changes to API response format won't be caught by E2E tests

**Impact:**
Integration bugs between frontend and backend may go undetected until manual testing or production.

**Recommended Fix:**

1. Create a separate test suite that runs against a real backend (integration tests)
2. Add API contract tests using tools like Pact or OpenAPI validation
3. Consider running E2E tests in CI with a real backend in a Docker container

**Workaround:**
Manually test UI against running backend before releases.

---

### 2. Unused Error State Removed Instead of Displayed

**Component:** UI
**Files:** `ui/src/pages/Providers.tsx`, `ui/src/pages/Dashboard.tsx`
**Status:** Open

**Description:**
The error state was removed from these components to fix ESLint warnings, but the error should be displayed to users when API calls fail. Currently, if an API call fails:

- `Providers.tsx`: Logs error to console but shows no UI feedback
- `Dashboard.tsx`: Shows toast notification but no persistent error state

**Impact:**
Users may not understand why data isn't loading or why the page appears empty.

**Recommended Fix:**

```tsx
// Add error state back and display it
const [error, setError] = useState<string | null>(null);

// In the JSX:
{
  error && (
    <Alert variant="destructive">
      <AlertTitle>Error</AlertTitle>
      <AlertDescription>{error}</AlertDescription>
    </Alert>
  );
}
```

---

### 3. WebSocket Mock Missing in E2E Tests

**Component:** UI / Testing
**File:** `ui/e2e/fixtures.ts`
**Status:** Open

**Description:**
The E2E test fixtures mock HTTP requests but not WebSocket connections. The Logs page and real-time updates rely on WebSocket connections that are not tested.

**Impact:**

- Real-time update functionality is not tested
- WebSocket connection/reconnection logic is not verified
- Logs page streaming behavior is untested

**Recommended Fix:**
Add WebSocket mocking to the fixtures:

```typescript
// In fixtures.ts
await page.route("**/ws/**", async (route) => {
  // Mock WebSocket upgrade or use playwright's WebSocket interception
});
```

Or use a library like `playwright-websocket-mock`.

---

## Medium Priority

### 4. Visual Regression Tests Are Fragile

**Component:** UI / Testing
**Files:** `ui/e2e/*.spec.ts` (visual tests)
**Status:** Open

**Description:**
Screenshot-based visual regression tests will fail on:

- Different OS/font rendering
- Any UI change (even intentional ones)
- CI environments with different screen configurations

**Impact:**
False positives in CI, requiring frequent snapshot updates.

**Recommended Fix:**

1. Add `threshold` option to `toHaveScreenshot()` calls:
   ```typescript
   await expect(page).toHaveScreenshot("page.png", {
     maxDiffPixels: 100,
     threshold: 0.2,
   });
   ```
2. Move visual tests to a separate CI job that can be manually approved
3. Consider using a visual testing service like Percy or Chromatic

---

### 5. Tooltip Test Always Passes (No-Op Test)

**Component:** UI / Testing
**File:** `ui/e2e/dashboard.spec.ts:196-208`
**Status:** Open

**Description:**
The tooltip test doesn't actually verify tooltip functionality:

```typescript
test("should have tooltips on capability badges", async ({ page }) => {
  const streamingBadge = page.getByText("Streaming").first();
  await streamingBadge.hover();
  await page.waitForTimeout(500);

  const tooltip = page.getByRole("tooltip");
  const tooltipCount = await tooltip.count();
  // This always passes - even if tooltips don't exist!
  expect(tooltipCount).toBeGreaterThanOrEqual(0);
});
```

**Impact:**
Test provides false confidence - tooltip functionality is not actually verified.

**Recommended Fix:**
Either implement proper tooltip testing or remove the test:

```typescript
// Option 1: Actually test tooltips
test("should have tooltips on capability badges", async ({ page }) => {
  const streamingBadge = page.getByText("Streaming").first();
  await streamingBadge.hover();
  await expect(page.getByRole("tooltip")).toBeVisible({ timeout: 1000 });
  await expect(page.getByRole("tooltip")).toContainText("Streaming");
});

// Option 2: Skip if tooltips not implemented
test.skip("should have tooltips on capability badges", async ({ page }) => {
  // TODO: Implement tooltips first
});
```

---

### 6. `waitForTimeout` Usage in Tests

**Component:** UI / Testing
**Files:** Multiple E2E test files
**Status:** Open

**Description:**
Several tests use `waitForTimeout` which is discouraged by Playwright:

```typescript
await page.waitForTimeout(500); // Arbitrary wait - fragile
```

**Impact:**

- Tests are slower than necessary
- Tests may be flaky (race conditions)
- Tests may fail on slower CI machines

**Recommended Fix:**
Replace with proper wait conditions:

```typescript
// Instead of:
await page.waitForTimeout(500);

// Use:
await expect(page.getByText("Expected Text")).toBeVisible();
// or
await page.waitForSelector('[data-testid="loaded"]');
// or
await page.waitForLoadState("networkidle");
```

---

### 7. No Test for Request Replay Functionality

**Component:** UI / Testing
**File:** `ui/e2e/debug.spec.ts`
**Status:** Open

**Description:**
The Debug page has a replay button for re-sending stored requests, but there's no E2E test verifying this functionality works.

**Impact:**
Replay functionality could break without detection.

**Recommended Fix:**
Add a test that:

1. Navigates to Debug page
2. Selects a request
3. Clicks replay button
4. Verifies replay was triggered (check for loading state, success message, or network request)

---

## Low Priority

### 8. Badge and Button Variants in Separate Files

**Component:** UI
**Files:** `ui/src/components/ui/badge-variants.ts`, `ui/src/components/ui/button-variants.ts`
**Status:** Resolved (Intentional)

**Description:**
The `badgeVariants` and `buttonVariants` were moved to separate files to fix ESLint react-refresh warnings. This is a deviation from standard shadcn/ui patterns.

**Impact:**
Minor - imports need to come from separate files if variants are needed directly.

**Note:**
This is intentional and not a bug. The separation was done to satisfy ESLint rules.

---

### 9. Coverage Directory Lint Warnings

**Component:** UI / Tooling
**Status:** Open

**Description:**
Running `npm run lint` shows warnings from files in the `coverage/` directory.

**Recommended Fix:**
Add `coverage/` to `.eslintignore`:

```
coverage/
```

---

## Technical Debt

### TD-1: Inconsistent Error Handling Across Pages

**Description:**
Different pages handle errors differently:

- Some use toast notifications
- Some log to console
- Some have error state (removed)
- Some show nothing

**Recommendation:**
Create a consistent error handling pattern:

1. Create an `ErrorBoundary` component (already exists)
2. Create a `useApiError` hook for consistent error handling
3. Standardize on toast + error state for all pages

---

### TD-2: API Client Could Use React Query

**Description:**
The current API client (`ui/src/lib/api.ts`) is a simple fetch wrapper. Pages manually manage loading/error/data states.

**Recommendation:**
Consider adopting React Query (TanStack Query) for:

- Automatic caching
- Background refetching
- Optimistic updates
- Consistent loading/error states
- Devtools for debugging

---

### TD-3: WebSocket Hook Complexity

**File:** `ui/src/hooks/useWebSocket.ts`
**Description:**
The WebSocket hook has complex reconnection logic with refs to avoid circular dependencies. This could be simplified.

**Recommendation:**
Consider using a library like `react-use-websocket` or refactoring to use a state machine pattern.

---

## Future Enhancements

### FE-1: Add Integration Test Suite

Run E2E tests against a real backend in Docker for true integration testing.

### FE-2: Add API Contract Tests

Use OpenAPI spec validation or Pact for contract testing between frontend and backend.

### FE-3: Add Accessibility Testing

Add axe-core accessibility testing to E2E tests:

```typescript
import { injectAxe, checkA11y } from "axe-playwright";

test("should have no accessibility violations", async ({ page }) => {
  await page.goto("/");
  await injectAxe(page);
  await checkA11y(page);
});
```

### FE-4: Add Performance Testing

Add Lighthouse CI or Web Vitals monitoring to track performance regressions.

### FE-5: Implement Request Replay UI

The backend supports request replay (`POST /debug/requests/{id}/replay`), but the UI doesn't have a button to trigger it.

### FE-6: Add Dark Mode Persistence

Dark mode toggle exists but doesn't persist across page reloads. Add localStorage persistence.

---

## Contributing

When fixing issues from this list:

1. Create a branch named `fix/issue-number-short-description`
2. Reference this document in your PR
3. Update this document to mark the issue as resolved
4. Add tests to prevent regression

## Issue Template

When adding new issues to this document, use this template:

```markdown
### N. Issue Title

**Component:** [UI/Backend/Testing/etc.]
**File(s):** `path/to/file.ts`
**Status:** [Open/In Progress/Resolved]

**Description:**
Clear description of the issue.

**Impact:**
What problems does this cause?

**Recommended Fix:**
How should this be fixed?

**Workaround:**
Any temporary workarounds?
```
