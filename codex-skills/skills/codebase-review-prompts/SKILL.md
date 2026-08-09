---
name: codebase-review-prompts
description: Provide short, ready-to-run prompts for reviewing whole codebases or subsystems. Use when the user asks for a codebase review prompt, audit prompt, reusable review brief, or concise review modes. Do not replace PR/diff review or specialist audits.
---

# Codebase Review Prompts

Replace `[scope]` with a repository, folder, or subsystem. If omitted, use
`this repository`.

Rules:

- Return only the requested prompt in a code block; default to `general`.
- Show the full set only when the user asks for options.
- If asked to run a prompt, use it as the read-only review brief.
- Route diffs to `review`, known failures to `diagnosing-bugs`, deep performance
  work to `deep-audit`, and full security assessments to a security workflow.

## General

Review [scope] for concrete correctness, reliability, maintainability, and test
risks. Read repo instructions first. Do not edit. Report actionable findings
only, highest severity first, with file:line evidence, impact, and the smallest
sensible fix. State what you inspected and skipped.

## Correctness

Review [scope] for logic errors, invalid assumptions, edge cases, lifecycle
bugs, and unsafe failure handling. Follow callers and tests. Do not edit. Rank
actionable findings by severity with file:line evidence, impact, and a minimal
fix.

## Architecture

Trace the main runtime paths in [scope]. Find boundary leaks, cycles, hidden
coupling, unclear ownership, and fragile state flow. Do not edit. Report only
evidenced risks with file:line citations and one practical remedy each. State
coverage gaps.

## Tests

Review tests for [scope]. Find important behavior that is untested, falsely
tested, flaky, over-mocked, or costly. Do not edit. Prioritize regression risk;
cite production and test lines and propose the smallest valuable tests.

## Maintainability

Review [scope] for duplicated logic, misleading abstractions, high coupling,
unclear ownership, dead paths, and change amplification. Do not edit. Report
only issues that materially raise defect or change cost, with file:line evidence
and focused remedies.

## Dependencies

Review manifests and real imports in [scope] for unused, duplicated, overlapping,
or unnecessarily broad dependencies. Verify usage before judging. Do not edit.
Report actionable findings with file:line evidence, impact, and a safe removal
or consolidation check.

## Security

Review [scope] for trust-boundary, authorization, secret, injection, unsafe
deserialization, and file/path risks. Do not edit or exploit. Report only
plausible findings with file:line evidence, preconditions, impact, mitigation,
and clearly labeled uncertainty.

## Performance

Trace real hot paths in [scope] for redundant I/O, repeated work or allocation,
blocking operations, unbounded queues, retry amplification, and lifecycle
leaks. Do not edit. Report evidenced issues with file:line citations, expected
impact, and how to measure before fixing.

## API Contracts

Review public APIs and data contracts in [scope] for inconsistent validation,
error semantics, ambiguity, compatibility risk, and leaky internals. Do not
edit. Cite definitions and consumers; rank findings by user impact and give
minimal corrections.
