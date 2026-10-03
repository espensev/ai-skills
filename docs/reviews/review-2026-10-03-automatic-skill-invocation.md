# Review: automatic skill invocation

Date: 2026-10-03. Baseline: `1e01c95`, branch
`fix/ai-skills-online-followups-20260825`. The initial tree was clean.
Scope: improve skills using observed data, with the clarified goal that agents
choose and run relevant skills from ordinary task requests.

## Findings and changes

1. **Installed discovery settings hid useful development skills.** Codex had
   `enabled = false` for the canonical `diagnosing-bugs`, `docs-sync`,
   `skill-authoring`, and `smart-test` paths. Claude overrides set
   `diagnosing-bugs`, `docs-sync`, and `smart-test` to `off`. Those seven
   settings are now enabled. Parsed before/after comparison confirmed all
   unrelated settings, including duplicate-copy disables, were preserved.
2. **Claude source metadata blocked automatic invocation.** Removed the
   `disable-model-invocation` restriction from those four skills and
   `usage-stats`. Removed their broad `allowed-tools` grants so automatic
   loading uses ordinary provider permissions. Existing local-model delegation
   settings were preserved. Documentation checks remain read-only; a question
   about which tests to run selects a map without executing tests.
3. **Frequently read usage instructions were large.** `usage-stats` was read
   repeatedly in the measured sample. Its Codex entry decreased from 35,840
   to 7,616 characters (856 to 116 lines, 78.8% smaller). Claude decreased
   from 34,877 to 7,232 characters (79.3%). All 15 command routes remain;
   detailed analytics and collection methods load from shared references.
   This is measured text reduction, not a measured latency or billing saving.
4. **Evaluation scores could hide bad results.** Two 3/5 cases previously
   produced priority -8 and disappeared from the actionable report. Priority
   now uses the average; the same cases produce 16. Both provider scorers
   also let `reject` pass at 4/5; rejection, missing labels, and unknown labels
   now fail. Empty feedback no longer claims all skills are healthy.

Independent review found and corrected a cross-provider counting error during
this change: Claude native input, cache-read, and cache-write lanes must be
added before reporting total input. Codex native input already includes cache.
The final read-only review returned PASS, including reference paths and anchors.

## Data used

Fixed window: 2026-09-26 00:57:56 UTC through 2026-10-03 00:57:56 UTC.
Local Codex sample: 109 interactive sessions, classified from the first
`session_meta`; event timestamps were bounded to the window. Windows path
matching accepted escaped separators. There were no repeated tool-call IDs
across sessions in this sample.

| Skill | Calls mentioning its path | Distinct sessions |
|---|---:|---:|
| usage-stats | 228 | 89 |
| handoff | 87 | 68 |
| repo-conventions | 66 | 48 |
| ship | 61 | 40 |
| review | 40 | 31 |
| qa | 35 | 23 |

For `usage-stats`, 222 calls resembled reads; 160 contained partial-read
markers, and 71 of 89 sessions read it at least twice. These are command-shape
and path-mention measurements, not proof of successful skill execution.
Claude's bounded sample had 30 CLI and 8 SDK sessions, with no explicit
invocations of the five skills enabled by this change.

The original `scripts/measure_hook_cost.py` could not supply this baseline
unmodified: its path regex missed escaped Windows separators and `--days`
filtered file modification time rather than individual event timestamps.
The baseline above was collected separately; the subsequent collector repair
is described below. Sanitized aggregate inputs were retained in the local
system temp directory under `aiskills-20261003-*-7d-sanitized.json`.

## Installation and verification

- Verified controller: `snd-desk`, instance
  `ca96d510-7d87-4cec-8e1a-bd8fc3866903`, using both declared local verifiers.
- Selected installs: five skills in each provider's canonical root under
  `%MACHINE_CODE_ROOT%DevHome/state/{codex,claude}/skills`. Before copying,
  all ten installed entry files matched the previous committed source.
- Selected installer `-Check`: both providers PASS. Generated package
  `-Check`: 51 files across 16 shared skills PASS.
- `codex-budget`: active skills 39 to 43; active duplicate names remain 0.
  Eligible description characters rose from 12,026 to 13,044.
- `scripts/Test-ReleaseReadiness.ps1`: PASS, including export/install smoke,
  provider parity, package contracts, lifecycle, and environment contracts.
- Final focused unittest run: 64 tests PASS, covering docs, both scorers,
  feedback, and the native usage collector. The final cache-accounting
  correction was rechecked through docs tests and generation/installation.
- Independent review: PASS. `git diff --check`: PASS.

### Initial fresh-session probes

The prompts did not name the expected skill. CLI sessions used disposable
fixtures in the system temp directory. Codex used read-only mode; Claude had
only Read, Glob, Grep, and Skill tools. The fixture's four files remained
unchanged in all four fixture directories (16 content comparisons). Provider
startup hooks created separate `.remember` metadata in temporary fixtures;
that metadata was removed after the probe processes exited.

| Provider | Prompt/task | Observed behavior | Result |
|---|---|---|---|
| Codex | Check README against project metadata; change no files | Loaded `docs-sync`; reported version 1.0.0 versus 2.0.0 | PASS |
| Claude | Same documentation check | Called Skill `docs-sync`; reported the same mismatch | PASS |
| Codex | Measured token usage over the last hour; use an existing collector | Loaded `usage-stats`; ran its bundled `codex_usage_window.py --hours 1` | PASS |
| Codex | 17 plus 25, just the number, no tools needed | Returned 42; no tool or skill calls | PASS |
| Claude | Same arithmetic control | Returned 42; no tool or skill calls | PASS |
| Claude | Which existing tests cover calculator.py; do not run tests | Called Skill `smart-test`; selected `tests/test_calculator.py` without running it, using the no-config fallback | PASS |
| Codex | Which existing tests cover calculator.py; do not run tests | Probe exceeded 180 seconds; driver hung during subprocess cleanup and was stopped by verified PID | INCONCLUSIVE |

Raw local probe files are under `aiskills-invocation-097lu1u0` in system temp.
No raw provider transcripts or local settings backups are committed.
This small smoke sample demonstrates selection and helper execution; it does
not establish a general routing success rate or end-to-end quality improvement.

### Follow-up verification

The probes exercised the skill implementation in `1e0b5cb`, installed before
the follow-up. Five further fresh sessions completed without timeouts. The
temporary driver wrote output directly to files while each CLI ran and bounded
process cleanup.
The successful retry resolves the missing Codex test-selection result; it does
not establish why the original CLI exceeded its timeout.

| Provider | Prompt/task | Observed behavior | Seconds | Result |
|---|---|---|---:|---|
| Codex | Which existing tests cover calculator.py; do not run tests | Loaded `smart-test`; selected `TestCalculator.test_add` without executing tests; disclosed unavailable Git metadata | 65.1 | PASS |
| Codex | Reproduce incorrect subtraction; diagnose only | Loaded `diagnosing-bugs`; ran `python -B reproduce.py`, observed the expected assertion failure, and identified addition at `calculator.py:2` | 116.1 | PASS |
| Claude | Same diagnosis request | Called Skill `diagnosing-bugs`; ran the reproduction, observed the expected failure, and identified the same cause | 27.9 | PASS |
| Codex | Turn a review checklist into a reusable Agent Skill design; planning only | Loaded `skill-authoring`; proposed discovery metadata, instructions, and positive/negative trigger examples without creating files | 90.5 | PASS |
| Claude | Same authoring request | Called Skill `skill-authoring`; proposed the design and trigger examples, and flagged overlap with the installed `review` skill | 69.5 | PASS |

These prompts did not name the selected skills. Codex again used read-only
mode. Claude retained Read, Glob, Grep, and Skill; its diagnosis probe also
exposed Bash with `Bash(python -B *)` in `--allowedTools`. The observed Bash
commands included read-only shell inspection alongside the reproduction;
the pattern is not evidence of a Python-only execution boundary. No persistent
provider permissions or settings changed during this follow-up.

All ten source files across the five follow-up fixture directories matched
their original contents. File enumeration found no additional source files or
Python bytecode; provider-created `.remember` metadata was excluded from that
comparison and removed separately after process exit. Raw traces and summaries
remain local as `*-v2.jsonl` and `*-v2.summary.json` under the same temp root.

Across both rounds, eleven probes passed, including two arithmetic controls;
the original timed-out run remains recorded above. All five changed skills
were selected in Codex, and four in Claude; Claude `usage-stats` was not probed.
Selection was inferred from completed skill-file reads in Codex and explicit
Skill calls in Claude, then checked against the observed task actions.
The authoring examples were proposed designs, not newly installed skills or
validated triggers. This remains a small smoke sample with constrained tools.

### Collector correction and live check

`scripts/measure_hook_cost.py` now recognizes escaped Windows skill paths and
applies the date cutoff to event timestamps, independently of file modification
time. The first Codex session metadata and first Claude entrypoint still
classify eligible events even when that metadata predates the cutoff.
Missing, malformed, and timezone-free timestamps are excluded explicitly.
Continuations crossing the cutoff are excluded rather than charging their
entire duration to the window.

Token costs require valid cumulative counters before and after the hook.
Empty counters, missing snapshots, and counter resets leave token costs
unmeasured. JSON and text output expose `token_measured_n` and
`token_unmeasured_n`, distinguishing missing coverage from a measured zero.

Verification: `python -B -m unittest scripts.tests.test_measure_hook_cost`
passed all 37 tests, including a real CLI check for both providers with old
file modification times and current events. Independent diff review passed;
`git diff --check` passed for the changed collector, tests, and this report.

A live scan with cutoff `2026-09-26T02:16:57.727296+00:00` completed at
`2026-10-03T02:17:05.469726+00:00` in 7.74 seconds. It included 371 Codex
sessions (108 interactive, 259 subagent, 4 exec) and 39 Claude sessions
(31 CLI, 8 SDK). Of 37 Codex hook continuations, 24 had usable token counters
and 13 did not. The sanitized aggregate is local at
`aiskills-invocation-097lu1u0/collector-followup-live-sanitized.json` under
system temp; no raw transcript content is committed.

The live scan reads active files and has a different cutoff and session scope
from the initial baseline. These counts verify collector operation; they are
not a before/after effectiveness comparison. Path mentions still do not prove
successful skill execution. Ignoring file modification times also means the
collector scans more historical files.

## Follow-up

- [Additional invocation controls](review-2026-10-03-invocation-controls.md)
  cover Claude `usage-stats` with synthetic counters and negative requests.
  More natural task samples are needed before claiming broad routing reliability
  or an effectiveness improvement.
- Use the corrected collector with a consistent window and session scope for
  future comparisons, retaining its token-coverage counts.

Provider contracts checked during this review:
[Codex skill selection and configuration](https://learn.chatgpt.com/docs/build-skills),
[Claude invocation and visibility](https://code.claude.com/docs/en/skills), and
[evaluating implicit and negative triggers](https://developers.openai.com/blog/eval-skills).
