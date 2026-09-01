# Codex Integration - DevHome Browser Control

This reference governs the Codex-side attachment of `chrome-devtools-mcp` to
the DevHome-managed Opera Developer instances. Read it when installing,
changing, troubleshooting, or accepting the rich MCP path. Normal browser work
should follow `SKILL.md` and use direct `cdp.mjs` whenever this attachment is
not proven.

The isolated `devbrowser` ports `9000`/`9001` remain the default automation
lane. The signed-in provider lane is allowed only when the user explicitly
names or selects a persistent profile with `providerbrowser <provider>`. Do not
infer a provider from the site, task, URL, or apparent account need. DevHome
maintains one shared browser process and endpoint per provider on its
deterministic, catalog-assigned loopback port. The provider lane runs headless
by default; use `-Mode Visible` only for login, CAPTCHA, consent, or attended
work. The persistent provider profile must not be described as isolated.

## Required end state

The effective MCP launch command must include exactly one DevHome endpoint:

```text
npx chrome-devtools-mcp@<approved-version> --browser-url=http://127.0.0.1:9000
```

Use port `9001` instead for the managed headless instance. Both ports are
loopback-only and use isolated Opera profiles. A bare
`npx chrome-devtools-mcp@<version>` registration is non-compliant because its
first browser operation can launch a separate Chrome/profile.

For `providerbrowser <provider>`, use direct CDP by default:

```powershell
$browser = providerbrowser <provider> -Url 'https://example.com/'
$port = $browser.Port
node D:\DevHome\state\codex\skills\browser-control\cdp.mjs --port $port tabs
```

Concurrent agents use the same provider command. A healthy endpoint owned by
the exact selected profile and configured executable must be reused to open a
new tab; never start another browser merely to change its mode. The command
must fail closed on an occupied or unhealthy port, mismatched or ambiguous
ownership, or any unproved state. Preserve the command's loopback and identity
guards. Require
the result to report `ProfileOwnerVerified = True`; missing or false ownership
proof is a failure. Do not kill or restart the profile, and do not close user
tabs.

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

For the provider lane, the only acceptable MCP target is the exact `Endpoint`
returned by `providerbrowser`. Do not call `list_pages` or any other browser MCP
tool until the effective `--browser-url` proves that exact target. Otherwise
use direct `cdp.mjs` with the command-returned `Port`.

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

## Account-action boundary

Navigation and read-only assistance are scoped to the user's request. Do not
submit, send, post, purchase, delete, change account settings, or disclose data
without explicit instruction for that action. Close only disposable tabs the
agent opened, and only when safe.
