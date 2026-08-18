# Review - Browser-control shipping lane

**Date:** 2026-08-18
**Surface:** Current browser-control architecture, provider packages, installed
roots, and live DevHome CDP smoke; the `main...origin/main` branch diff was
empty at review start.
**Spec source:** Current user request, plus `docs/release-readiness.md`
**Standards sources:** `AGENTS.md`, `CLAUDE.md`,
`skills-src/browser-control/SKILL.src.md`
**Verdict:** PASS WITH NOTES

## Findings

### High

No findings.

### Medium

- [regression, resolved] `skills-src/browser-control/SKILL.src.md:62-68` - The
  MCP guidance previously allowed a bare MCP server to launch a separate Chrome
  even though the skill requires all browser work to use DevHome-managed Opera
  endpoints. That could silently select the wrong browser profile. The source
  now requires `--browser-url` and directs agents to direct CDP when MCP cannot
  attach.

- [regression, resolved] Installed-root verification initially found Codex
  missing `handoff`, seven retired skill directories, and six stale skills;
  after the verified installer run, `Compare-AgentSkillRoots.ps1
  -Provider Both -FailOnMissingOrStale` passed. The Claude user-profile root
  was also synchronized after it was confirmed to be a regular directory.

### Low

- [regression, resolved] There was no package contract protecting the browser
  routing rule or the helper command surface. Both provider contract suites now
  assert the attached-CDP wording, reject the old bare-MCP wording, and check
  all eight helper commands at
  `codex-skills/tests/test_skill_docs_contract.py:255-264` and
  `claude-skills/tests/test_skill_docs_contract.py:200-209`.

## Verification

- `node --check` on source and both generated `cdp.mjs` files - pass.
- `python -m unittest ...test_browser_control_requires_devhome_cdp_attachment` - 2/2 pass.
- `Build-ProviderSkillPackages.ps1 -Check` - pass, 44 files across 16 skills.
- `Compare-ProviderSkillParity.ps1 -FailOnUndeclaredFork` - pass.
- Installed Codex-root CDP smoke on headless port 9001 (`new`, `eval`, `text`,
  `screenshot`, `close`) - pass; screenshot was 2,736 bytes and the temporary
  artifact was removed.
- `Test-ReleaseReadiness.ps1 -IncludeLiveRootCompare` - pass; lifecycle tests
  39/39, installer tests 3/3, root comparison pass.
- Post-ship preflight contract tests - pass for both Codex and Claude.
- `Install-AgentSkills.ps1 -Provider Both -Force` refreshed the verified live
  roots, including the new Codex integration reference;
  `Compare-AgentSkillRoots.ps1 -Provider Both -FailOnMissingOrStale` - pass.

## Coverage Notes

- Deep-reviewed canonical browser skill, CDP helper, generated provider copies,
  manifests, installer/comparator paths, contract tests, and live root state.
- The helper was exercised against the real headless DevHome endpoint. MCP
  server attachment itself was not exercised because the current lane used the
  direct-CDP path.

## Post-ship Codex integration status

- On verified controller `snd-desk`, `codex mcp list` currently resolves the
  enabled `chrome-devtools` registration to `npx
  chrome-devtools-mcp@1.7.0` with no `--browser-url` argument.
- The plugin cache manifest contains the same bare argument list. That cache is
  managed material and is not an edit authority.
- Therefore the rich MCP path is not accepted on this host yet. Its tools must
  not be invoked as a probe because the first browser operation can create the
  separate Chrome/profile that this routing contract forbids.
- The installed direct-CDP path remains the safe, verified browser-control
  route. This does not invalidate the source/package ship verdict.

## Required follow-up

- The canonical skill now requires an effective-argument preflight before any
  rich MCP browser call. Codex-specific setup and acceptance are documented in
  `codex-skills/skills/browser-control/CODEX-INTEGRATION.md`.
- With explicit authority for a machine-local Codex configuration change,
  replace the bare registration with one attached to
  `http://127.0.0.1:9000`, start a fresh Codex session, compare `list_pages`
  against `cdp.mjs tabs`, and confirm no unmanaged Chrome/profile appears.
