# Repeatable skill-selection checks

Use `scripts/run_skill_invocation_checks.py` to replay ordinary requests against
fresh Codex and Claude CLI sessions. The runner reads the
[saved controls](reviews/fixtures/invocation-controls-2026-10-03.json), records
actual tool attempts and results, and checks completion and file integrity.
It tests automatic selection without naming a skill in the prompt.

Live checks are opt-in and consume provider usage. The release gate runs only
the deterministic runner and telemetry tests; it never launches model CLIs.

## Run a small batch

Python 3.10+ and the relevant authenticated provider CLI must be available.
Supply the installed skill directory used by the provider you intend to test.
The runner requires the targeted `SKILL.md` entries to exist before launching.
These arguments identify the entries to hash; they do not change provider
configuration or select a different skill installation.

```powershell
python -B scripts/run_skill_invocation_checks.py --provider both `
  --codex-skill-root '<installed Codex skills directory>' `
  --claude-skill-root '<installed Claude skills directory>' `
  --case docs_summary --case token_concept
```

Omit `--case` to run all supported cases: five negative controls per provider
and one Claude usage case. Use `--provider codex` or `--provider claude` to
restrict the batch, `--repeat 2` to repeat it, and `--timeout 240` to set the
per-session deadline. Optional `--codex-cli` and `--claude-cli` arguments select
an executable path. Run `--help` for the complete interface.

The runner resolves executables directly, so PowerShell functions or aliases
that inject model or permission flags are bypassed. It leaves model selection
to the provider configuration. Codex uses a read-only sandbox and ephemeral
JSON output. Claude exposes only Read, Glob, Grep, and Skill, with `dontAsk`
permissions and no permission prompts. Existing global instructions, plugins,
and hooks remain active. This is a constrained selection check; it does not
certify the permissions or behavior of a normal unrestricted session.

## Read the evidence

Each batch creates a fresh artifact directory in system temp and prints its
location. Fixture directory leaves are UUIDs. Exact prompts, CLI versions and
commands, entry hashes, raw JSONL streams, stderr, final responses, and the
JSON report remain available for review. The runner retains artifacts and
does not install skills, change settings, or publish results.

- A routing PASS requires provider terminal success, process exit zero, and
  complete parseable evidence. Negative cases also require no forbidden skill
  attempt, including failed loads. Other selections remain in the report.
- Positive selection requires a correlated successful tool result. Narration,
  catalog entries, and quoted paths do not establish successful loading.
  Ambiguous Codex shell evidence remains inconclusive.
- Timeouts, missing completion, malformed evidence, fixture changes, unexpected
  source files, or targeted installed-entry drift cannot produce a routing PASS.
  Provider-created `.remember` metadata is reported separately.
- Exit zero means the automated routing checks passed. Task-result acceptance
  remains a manual review requirement; the runner does not infer correct
  answers from numbers appearing in a response.

For the positive usage case, review the successful fixture read and check
**5,000 total input**, with 3,000 cache reads and 800 cache writes as subsets,
250 output, and 5,250 overall. The answer must identify the synthetic source
and one-response coverage and omit estimated dollar cost. This fixture tests
interpretation of supplied Claude counters; it does not collect live usage.

Claude's startup catalog can establish whether a target was advertised when
the stream exposes it. Codex's public stream does not establish its effective
skill catalog or model identity. Installed-entry hashes alone do not prove
that either provider discovered those copies. Inherited configuration and
instructions are not fully captured, so compare runs only with those limits
in mind. A small fixed request set does not establish a general selection rate.

Keep raw evidence local: provider streams may include inherited machine
context. Commit reviewed summaries and case definitions rather than raw
session output.

## Observed live checks, 2026-10-03

Three sessions used the saved prompts, UUID fixture directories, Codex
`0.160.0`, and Claude Code `2.1.288`, with the tools and permissions above.

| Provider | Case | Seconds | Observed selection |
|---|---|---:|---|
| Claude | `usage-positive` | 22.280 | Successfully loaded `usage-stats` and read the counter fixture |
| Codex | `token_concept` | 18.021 | No skill attempts or tool calls |
| Claude | `token_concept` | 11.343 | No skill attempts or tool calls |

Manual review confirmed the positive case's arithmetic, synthetic source,
one-response coverage, and absence of a dollar estimate. Both negative runs
left `usage-stats` idle. Claude added a third sentence about pricing to the
conceptual answer, so its routing result does not establish format compliance.
Claude advertised the target in both startup catalogs; Codex's catalog was
not exposed.

All 15 original source files retained their hashes; provider-created
`.remember` files were reported separately and retained. CLI versions and
binary hashes remained stable, as did the two targeted entry hashes. The
entries matched `f3f7d38`: Codex `8f9aaf7d6c6b`, Claude `f7db67cab507`.
Raw evidence remains locally under `%TEMP%/skill-invocation-oygk3prc`.
After the three parser corrections, all three saved streams were regraded
with the final parser (`8a4154da2d69`); they still passed. The independent
review reproduced the original false passes and verified their rejection.
These three samples verify the runner's integration with the installed CLIs;
they do not establish broader routing reliability.

The Claude conceptual run's Remember session-end hook logged exit `127` from
`save-session.sh --force`. Its hook-error log changed after CLI exit; the 15
source files stayed unchanged. The raw provider streams and regrade evidence
were retained independently of that hook. This check does not verify Remember
session capture, and no installed hook repair was attempted.

## Offline verification

```powershell
python -B -m unittest discover -s scripts/tests -p 'test_*.py'
.\scripts\Test-ReleaseReadiness.ps1
```

The release gate enforces the first command under its existing unit-test
switch. Fixture subprocesses are synthetic and require no provider access.
Broader trigger sets and remaining installation work are tracked in the
[refinement review](reviews/review-2026-10-03-model-invocation-refinement.md#follow-ups).
