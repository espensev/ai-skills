# Review: automatic invocation controls

Date: 2026-10-03. Repository baseline: `888ca2f`. This round adds the missing
Claude usage selection check and five negative prompts per provider. The
[fixture and prompt specification](fixtures/invocation-controls-2026-10-03.json)
contains six distinct prompts and their expectations; four negative runs were
then repeated in directories with opaque names.

## Outcome

All fifteen runs completed successfully: one positive usage case and fourteen
negative controls. Claude automatically selected `usage-stats`, read the supplied
counter fixture, and produced the correct totals. Neither provider loaded or
attempted to read any skill in the negative runs. This provides positive
selection and negative-control evidence for the tested requests; it does not
establish a general routing success rate.

## Tested environment and versions

- Controller: verified `snd-desk`, instance
  `ca96d510-7d87-4cec-8e1a-bd8fc3866903`.
- CLI versions: Codex `0.160.0`, Claude Code `2.1.288`; configured models were
  used without overrides.
- Codex used `exec --sandbox read-only --skip-git-repo-check --ephemeral --json`.
- Claude used print mode, streaming JSON, no session persistence, and only
  Read, Glob, Grep, and Skill tools. Prompts were passed through stdin.
- Each run used a disposable fixture copy and a 240-second timeout. Output
  streamed to regular files; at most two negative CLI runs executed concurrently.
- Existing provider settings, startup hooks, and global routing instructions
  remained active. All five targeted skills appeared in every initial Claude
  negative session's startup skill listing. Codex's four explicit canonical
  overrides were enabled; its actual startup catalog was not captured.

The installed entries matched the concurrent generated working files when
checked. Codex `skill-authoring` and all five Claude entries differed from
`888ca2f`; the other four Codex entries matched that commit. The following
SHA-256 prefixes identify the installed entries exercised in this round.
Full hashes were compared before and after each batch and matched.

| Skill | Codex SHA-256 prefix | Claude SHA-256 prefix |
|---|---|---|
| diagnosing-bugs | `0833a4116543` | `1eb5028fe823` |
| docs-sync | `eb5897607502` | `9d80c6544e1e` |
| skill-authoring | `d35f4427f26b` | `1bd4ab9cdb1f` |
| smart-test | `91e689f46ae2` | `bf37d008d8bb` |
| usage-stats | `8f9aaf7d6c6b` | `f7db67cab507` |

At probe startup, six installed entries reflected concurrent uncommitted
refinement. That work was subsequently committed as `f3f7d38`; all ten tested
entry hashes match that commit. These results cover the listed snapshots and
do not validate every other skill or package change in that commit.

## Positive Claude usage case

The prompt requested a summary of synthetic Claude native counters without
naming a skill. The supplied counters were 1,200 uncached input, 3,000 cache
reads, 800 cache writes, and 250 output tokens. Claude called Skill
`usage-stats`, read `usage-snapshot.json`, and reported:

- Total input: **5,000**, with cache reads and writes shown as subsets.
- Output: **250**; overall total: **5,250**.
- Source: synthetic fixture; coverage: one completed response.
- No estimated dollar cost.

The run completed in 26.9 seconds with Skill, Glob, and Read calls. Independent
trace review confirmed successful loading and correct arithmetic. This tests
selection and interpretation of supplied counters, not collection of live
Claude usage.

## Negative controls

The prompts in the specification request ordinary nearby tasks: summarize a
README, rewrite a sentence containing the word "test", explain correct code,
rewrite a checklist as prose, and explain token concepts without measurements.
Each case forbids one inappropriate skill; every other selected skill would
still be retained in the evidence. All ten initial runs selected no skills.

| Case | Skill expected to stay idle | Codex seconds | Claude seconds | Routing result |
|---|---|---:|---:|---|
| docs_summary | docs-sync | 44.568 | 24.591 | PASS / PASS |
| tests_wording | smart-test | 17.426 | 15.782 | PASS / PASS |
| code_explanation | diagnosing-bugs | 37.739 | 21.205 | PASS / PASS |
| checklist_prose | skill-authoring | 40.093 | 35.593 | PASS / PASS |
| token_concept | usage-stats | 20.889 | 21.596 | PASS / PASS |

The initial fixture directory names included control labels. To check that cue,
the README summary and token concept prompts were repeated with identical tools
and prompts in UUID-only fixture directories. All four repeats again selected
no skills and completed successfully.

| Repeat | Codex seconds | Claude seconds | Routing result |
|---|---:|---:|---|
| docs_summary, opaque directory | 24.886 | 16.874 | PASS / PASS |
| token_concept, opaque directory | 18.155 | 12.195 | PASS / PASS |

Independent raw-trace review found no skill-load attempts, failed skill reads,
mutation tools, or test execution in any negative run. Only the requested
README and checklist reads used tools. Routing PASS does not imply perfect
output quality: Claude added a prefatory paragraph to its checklist rewrite
and an unrequested pricing aside to its initial token explanation.

## Evidence and limits

- All 75 source files across fifteen probe fixture copies matched their original
  hashes and file sets. Provider-created `.remember` metadata was accounted for
  separately and removed after process exit checks.
- The committed specification was parsed and checked against actual fixture
  contents and saved prompts. None of its prompts names the tested skill.
- Raw streams, summaries, installed hashes, and independent verification files
  remain local under `aiskills-routing-next-ihl_kts5` in system temp. They are
  not committed. The original negative results were preserved during repeats.
- The specification is a replayable case definition, not an automatic CI runner
  or part of the existing saved-output scorer.
- Each request has only one initial sample per provider; only two negative
  prompts have repeats. Some prompts explicitly limit actions. Inherited global
  routing, constrained tools, synthetic data, and installed-version differences
  limit any broader effectiveness claim.

Prior positive and arithmetic-control results remain in the
[earlier review](review-2026-10-03-automatic-skill-invocation.md). Across the
three rounds there are 26 passing smoke runs and one original timed-out run;
the runs span different installed snapshots and are not a single benchmark.

## Follow-up

For broader evidence, collect varied natural requests per skill using opaque
directories, consistent versions, and an explicit instruction/configuration
snapshot. Live Claude usage collection remains untested in this fixture round.
