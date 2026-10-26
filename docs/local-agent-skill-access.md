# Local Agent Skill Access

Use the root sync script when the curated Codex and Claude package skills should
be available from the local agent skill roots, not just from this repo.

## Default Roots

The script targets the local roots that exist on this workstation:

| Provider | Default roots |
|---|---|
| Codex | `C:\Users\Sev\.codex\skills`, `D:\DevHome\state\codex\skills` |
| Claude | `C:\Users\Sev\.claude\skills`, `D:\DevHome\state\claude\skills` |

On enrolled `snd-desk`, the profile paths are junctions to the matching
`D:\DevHome\state` roots. The installer resolves those link identities and
de-duplicates them; the table shows both discovery paths, not two physical
copies.

If `CODEX_HOME` or `CLAUDE_HOME` is set, the script also uses
`$env:CODEX_HOME\skills` or `$env:CLAUDE_HOME\skills`.

## Commands

### Automatic selection

Every packaged development skill except `delegate` supports selection from
ordinary task requests; `delegate` keeps an explicit-only boundary. Users can
still invoke any skill by name. Skill selection uses the task description and
preserves the task's action limits: documentation checks stay read-only,
test-selection questions do not run tests, and closeouts do not write history
or memory. A selected skill with subcommands maps the request to the command
that does the work: `ship` commits and normally pushes without a second
confirmation, and `manager` runs `go` or `plan` rather than `status`.

No model-selectable skill carries an `allowed-tools` grant. In Claude Code
that field pre-approves tools for the invoking turn, so a skill the model can
select on its own would let it grant itself access; pre-approve tools through
provider permission settings when a workflow needs it.

After installing those skills, check the effective provider settings:

- Codex: an `enabled = false` entry in `[[skills.config]]` hides that exact
  `SKILL.md` path. Enable the canonical installed copy, preserving disables
  for duplicate copies. `agents/openai.yaml` must not set
  `policy.allow_implicit_invocation: false` for an automatic skill.
- Claude: `skillOverrides` must allow the skill (`on` or no override; the
  `name-only`, `user-invocable-only`, and `off` states hide the description
  from Claude), and its frontmatter must not set
  `disable-model-invocation: true`. The skill listing shares a budget of about
  one percent of the context window; above it Claude Code drops the
  descriptions of the least-used skills, so keep descriptions short and turn
  off skills that are not in use. `/doctor` reports the listing cost.

Restart Codex after changing its config. Test a fresh session with a request
that omits the skill name, then inspect whether it loads the intended skill
and completes the requested action. Include nearby requests that should not
select it. An installer or fixture pass proves file integrity, not model
selection. Local-model `delegate` retains its separate invocation boundary.

Provider contracts: [Codex skills](https://learn.chatgpt.com/docs/build-skills)
and [Claude skills](https://code.claude.com/docs/en/skills).

### Install and compare

Preview what would be copied:

```powershell
.\scripts\Install-AgentSkills.ps1 -Provider Both -DryRun
```

Copy only missing manifest-listed package entries. An existing skill or runtime
directory that lost files (for example an emptied skill) is repaired by copying
back only the missing files; files already present are never overwritten
without `-Force`. Every real run then verifies that each selected source file,
including each `SKILL.md`, exists in the target:

```powershell
.\scripts\Install-AgentSkills.ps1 -Provider Both
```

Check installed state read-only; exits non-zero on a missing file or content
drift (CRLF-only differences are not drift):

```powershell
.\scripts\Install-AgentSkills.ps1 -Provider Both -Check
```

Refresh existing manifest-listed entries as well:

```powershell
.\scripts\Install-AgentSkills.ps1 -Provider Both -Force
```

Compare installed files against the package manifests:

```powershell
.\scripts\Compare-AgentSkillRoots.ps1 -Provider Both -FailOnMissingOrStale
```

Pass `-IncludeExtra` only when auditing unrelated local skills in the same
roots; extras are intentionally ignored by the default compare.

The script copies only the skills, support files, runtime files, and runtime
directories listed in each provider's `package/install-manifest.json`. It does
not delete unrelated local skills, and it does not copy source-only package
material such as `telemetry-live-ops`.

## Local Codex plugin choice

Machine-local components remain outside those portable manifests. Register the
repository marketplace separately when `devhome-lifecycle` should appear as an
AI Skills plugin choice:

```powershell
.\scripts\Install-AgentSkills.ps1 -Provider Codex -CodexLocalPlugin DevHomeLifecycle
```

Use `-Provider Both` instead when the Claude roots should be refreshed in the
same invocation. Add `-DryRun` for a read-only package preview plus plugin
convergence report; add `-Force` only for an explicit package refresh and plugin
reinstall.

The plugin contributes one operator skill and one startup reconciliation hook.
It does not duplicate the installed DevHome behavior hooks. Re-run the command
after updating this checkout: it hashes the closed source/cache payload and
refreshes stale plugin material explicitly. A restart alone is not treated as a
cache-update mechanism. The trusted cached reconciler delegates to the canonical
Ai-Skills source, then updates the verified runtime projection if needed; until
that SessionStart hook is trusted, automatic reconciliation is skipped.
Unlike portable skill-copy targets, this machine-specific plugin's registration,
cache, and three runtime files are pinned to `D:\DevHome\state\codex`;
`CODEX_HOME` cannot redirect those surfaces into AppData. The adapter-state
exception is called out separately below.

The three lifecycle surfaces are intentionally distinct:

| Surface | Location | Authority |
|---|---|---|
| Source | `%MACHINE_CODE_ROOT%AI4000\skills\Ai-Skills\codex-skills\local-hooks\devhome-lifecycle` | Canonical; update Git separately. |
| Plugin cache | `D:\DevHome\state\codex\plugins\cache\ai-skills\devhome-lifecycle\` | Materialized copy refreshed by the command above. |
| Codex runtime hooks | `D:\DevHome\state\codex\hooks.json` and two owned files under `hooks\` | Installed projection reconciled from source. |
| Claude Handoff Relay | `D:\DevHome\state\claude\settings.json` and `hooks\Invoke-HandoffRelay.ps1` | Dedicated installer preserves unrelated settings/hooks and owns only its exact Stop command and script. |
| Handoff Relay state | `D:\DevHome\state\remember\projects\<project>\tmp\handoff-relay\` and `D:\DevHome\state\remember\handoff-relay\latest-status.json` | Session drafts, hash/lock state, preserved failures/conflicts, and one redacted health record; canonical output remains `<project>\remember.md`. |

The former `%MACHINE_CODE_ROOT%Development\AI-related\Ai-Skills` source path
remains a compatibility junction to the same checkout. Plugin-cache and runtime
paths remain installer-owned; the source relocation does not migrate them.

Read-only checks:

```powershell
.\codex-skills\local-hooks\devhome-lifecycle\Sync-DevHomeLifecyclePlugin.ps1 -Check
.\codex-skills\local-hooks\devhome-lifecycle\Sync-DevHomeCodexHooks.ps1 -Check
.\codex-skills\local-hooks\devhome-lifecycle\Install-DevHomeClaudeHandoffRelay.ps1 -Check
```

The plugin check passes only with `Status = CURRENT` and exit code `0`; the
other two throw on drift.

Installation does not prove activation. Plugin enablement and hook trust are
Codex-managed user choices; after first installation or a hook command change,
restart Codex, confirm `devhome-lifecycle@ai-skills` is enabled, and review the
SessionStart reconciler in `/hooks`.
