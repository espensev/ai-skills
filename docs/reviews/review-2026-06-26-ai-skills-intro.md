# Review - AI Skills Package Surface

**Date:** 2026-06-26
**Scope:** root README positioning, package manifests, ready-package boundaries, and high-signal upgrade candidates.
**Verdict:** PASS with one low-risk packaging hygiene follow-up.

## Current Update

This review was superseded later on 2026-06-26 by the Antigravity split:
`antigravity-skills` is now the active Google-facing ready package, and
`gemini-skills` is retained as legacy source material.

## What's Good

- The useful product surface is clear and shippable: `release-manifest.json` marks `claude-skills`, `codex-skills`, and the current Google-facing package as ready packages, while `wt-cli` remains source-only tooling.
- The README skill counts match the ready package manifests for 81 total install-ready skills.
- Manifest-listed skill files and provider entrypoints are present on disk. No missing `SKILL.md` files were found for the ready packages.
- The strongest reusable workflows are the campaign core (`discover`, `planner`, `manager`, `qa`, `ship`), the portable `review` and `diagnosing-bugs` skills, the ops/analytics suite, and telemetry-aware delegation/evaluation.
- The repo already documents the right promotion model: imported skills are reference material until adapted to the provider surface, added to manifests, and export-validated.

## Improvements Made

- Rewrote the root README intro to explain the manifest-driven shipping boundary before the package table.
- Clarified that imported or source-only skills are reference material unless listed in the install manifests.
- Promoted `diagnosing-bugs` as a portable optional skill across Claude, Codex, and Gemini.

## Suggested Follow-Ups

- Reconcile the three extra Gemini command wrappers only if the legacy Gemini package is reactivated for release.
- Keep using the root ready-package validation script so manifest counts, missing files, provider entrypoint drift, source-only exclusions, and export smoke checks can be run with one command.
- Promote future skills one at a time. `tdd` and merge-conflict resolution remain useful candidates, but both need provider adaptation before shipping.

## Checks Run

- Manifest count comparison for Claude, Codex, and Gemini packages.
- Missing manifest-listed skill/runtime/wrapper check.
- Conflict-marker scan narrowed to real marker forms.
- README path and command spot-check against `scripts/export-ready-skill-packages.ps1`, `gemini-skills/scripts/bootstrap.ps1`, `docs/ollama-telemetry-integration.md`, and `LICENSE`.
