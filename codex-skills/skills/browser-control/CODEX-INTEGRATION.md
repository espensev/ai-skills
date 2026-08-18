# Codex Integration - DevHome Browser Control

This reference governs the Codex-side attachment of `chrome-devtools-mcp` to
the DevHome-managed Opera Developer instances. Read it when installing,
changing, troubleshooting, or accepting the rich MCP path. Normal browser work
should follow `SKILL.md` and use direct `cdp.mjs` whenever this attachment is
not proven.

## Required end state

The effective MCP launch command must include exactly one DevHome endpoint:

```text
npx chrome-devtools-mcp@<approved-version> --browser-url=http://127.0.0.1:9000
```

Use port `9001` instead for the managed headless instance. Both ports are
loopback-only and use isolated Opera profiles. A bare
`npx chrome-devtools-mcp@<version>` registration is non-compliant because its
first browser operation can launch a separate Chrome/profile.

## Read-only preflight

Run these before invoking any Chrome DevTools MCP browser tool:

```powershell
codex mcp get chrome-devtools --json
codex mcp list
Invoke-RestMethod http://127.0.0.1:9000/json/version
```

Pass only when the effective MCP arguments contain either
`--browser-url=http://127.0.0.1:9000` or the equivalent two-argument form
`--browser-url http://127.0.0.1:9000`, and the endpoint probe succeeds. An
enabled plugin and visible MCP tools do not prove attachment. Do not use
`list_pages` as the preflight for a bare or unverified registration.

If any check is missing or ambiguous, stop the MCP path and use the installed
direct-CDP helper:

```powershell
node D:\DevHome\state\codex\skills\browser-control\cdp.mjs tabs
```

## Registration changes

Codex plugin cache directories are generated, versioned material. Never patch
the cached `.claude-plugin/plugin.json` or another cache file to add arguments;
an upgrade or reconciliation can overwrite it.

With explicit authority for a machine-local Codex configuration change, use
one of these supported ownership models:

1. Configure the installed plugin through a supported plugin override that is
   visible in `codex mcp get`.
2. Disable or remove the plugin-provided registration, then add one standalone
   Codex MCP registration with the attached endpoint:

   ```powershell
   codex mcp add chrome-devtools -- npx chrome-devtools-mcp@<approved-version> --browser-url=http://127.0.0.1:9000
   ```

Do not leave plugin-provided and standalone servers publishing the same
`chrome-devtools` registration. Do not make either change merely because a
browser task was requested; direct CDP is the safe fallback.

## Acceptance after a change

1. Verify the local machine identity before changing DevHome browser or Codex
   state.
2. Ensure the selected endpoint is running through `devbrowser`.
3. Re-run `codex mcp get chrome-devtools --json` and `codex mcp list`; capture
   the effective attached arguments.
4. Start a fresh Codex session so the MCP process is reconstructed.
5. Compare `list_pages` with `cdp.mjs tabs`; they must identify the same known
   DevHome Opera target.
6. Open, inspect, and close one disposable tab. Confirm no separate Chrome
   profile or unmanaged browser process was created.

Only then may the rich MCP path be described as accepted. Source-package tests
and direct-CDP smoke tests do not substitute for this attended integration
check.
