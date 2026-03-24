---
name: e2e-testing
description: "Build and debug Playwright end-to-end tests with stable selectors, app-aware setup, useful artifacts, and flake-resistant waiting. Use when creating, reviewing, or stabilizing browser-based tests."
---

# E2E Testing

Write Playwright tests that fail for product regressions, not for timing noise.

## Dependencies

- Required: Playwright test runner in the target repo
- Optional: Playwright MCP for interactive debugging
- Fallback: standard Playwright CLI, saved traces, screenshots, and videos

## Workflow

1. Inspect the repo before writing tests:
   - existing Playwright config
   - current test layout
   - app start command
   - seeded test data or auth helpers
2. Reuse the existing layout and fixtures.
3. Prefer stable selectors and visible user behavior over implementation detail.
4. Wait on specific states:
   - locator visibility
   - network responses
   - URL changes
   - semantic success indicators
5. Capture artifacts that help debug failures:
   - traces
   - screenshots
   - video when configured

## Anti-Flake Rules

- Do not rely on arbitrary sleeps when a real condition exists.
- Do not overuse global retries to hide deterministic bugs.
- Keep tests isolated from shared mutable data when possible.
- Use focused page objects or helpers only when they reduce duplication.
- Keep assertions close to the user-visible effect.

## Review Checklist

- Does the test use the repo's existing conventions?
- Is the server startup command correct for this app?
- Are selectors stable and intention-revealing?
- Are waits tied to real system behavior?
- Does the failure output leave enough evidence to debug quickly?

## Deliverable

When adding or fixing E2E coverage, provide:

1. tests added or updated
2. app startup assumptions
3. selectors and wait strategy
4. artifacts or debug hooks
5. command used to verify
