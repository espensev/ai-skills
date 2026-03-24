---
name: frontend-patterns
description: "Apply practical React and Next.js UI patterns that respect existing design systems, accessibility, and the repo's React or compiler guidance. Use when building components, forms, state flows, or client-side data loading."
---

# Frontend Patterns

Build intentional UI that fits the existing product instead of dropping in
generic component patterns.

## Workflow

1. Inspect the current UI stack:
   - design system or component library
   - routing and data-fetching model
   - state management choices
   - styling conventions
   - accessibility patterns
2. Reuse existing primitives before inventing new ones.
3. Keep state as local as possible, then lift or centralize only when multiple
   surfaces truly share it.
4. Model the user-facing states explicitly:
   - loading
   - empty
   - error
   - success
5. Build responsive and keyboard-accessible behavior into the first pass.

## Design Rules

- Prefer composition over over-abstracted component trees.
- Respect existing typography, spacing, and motion conventions.
- Do not add `useMemo` or `useCallback` by default; follow the repo's React
  compiler or performance guidance.
- Prefer existing form and validation patterns.
- Use stable test selectors only where tests genuinely need them.
- Avoid animation that obscures state transitions or slows interaction.

## Performance Rules

- Optimize after identifying a real render or bundle problem.
- Prefer code-splitting for heavy surfaces.
- Use virtualization for genuinely long lists.
- Avoid unnecessary client-side state when server rendering or loader data is a
  better fit.

## Accessibility Rules

- Ensure focus order and keyboard access.
- Use semantic elements first.
- Label inputs and interactive controls.
- Keep visual-only status changes accessible to assistive technology.

## Deliverable

When implementing or reviewing frontend work, provide:

1. component structure
2. state and data-flow choice
3. loading or error-state handling
4. accessibility notes
5. verification steps
