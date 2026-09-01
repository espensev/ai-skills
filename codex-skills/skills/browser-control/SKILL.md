---
name: browser-control
description: "Use when a task needs a live browser: navigating pages, reading DOM or page text, screenshots, form fills, console/network inspection, or web app testing. Routes browser automation through DevHome Opera Developer CDP: isolated devbrowser ports 9000/9001 by default, or the explicitly selected signed-in providerbrowser lane. Never use harness-bundled browser tooling (browser/chrome plugins, browser-harness, playwright) - it is disabled on purpose."
---

# Browser Control - DevHome CDP Routing

Browser automation on this machine goes through **Opera Developer** instances
managed by DevHome.Profile. Use the isolated `devbrowser` lane by default. Use
the signed-in `providerbrowser` lane only when the user explicitly names or
selects a persistent provider profile. The harness-bundled browser stacks are
deliberately disabled and must not be re-enabled or worked around - they
pop windows into the user's real session.

**Banned:** the bundled `browser` and `chrome` plugins, `chrome:control-chrome`,
browser-harness, playwright, and launching your own Chrome/Chromium instance
by hand.

**Allowed:** the CDP endpoints below, driven by chrome-devtools-mcp or direct
CDP calls (helper script included).

## Endpoints

| Port | Instance | Profile |
|------|----------|---------|
| 9000 | visible  | isolated `opera-visible` state dir |
| 9001 | headless | isolated `opera-headless` state dir |
| returned `Port` | headless by default; visible opt-in | catalog-selected persistent provider profile; not isolated |

All endpoints are loopback-only. Ports 9000 and 9001 use isolated profiles, so
they do not touch persistent provider sessions. The signed-in persistent
provider profile must not be described as isolated. Do not infer a provider
profile from a site, task, URL, or apparent account need.
More isolated instances on other ports are fine when a task needs a clean
profile - each `devbrowser -Port` gets its own state dir.

## Launch / status: devbrowser

`devbrowser` is a PowerShell function from the DevHome profile (available in
any profile-loaded pwsh session; from bash run it via `pwsh -Command`).

```powershell
devbrowser                                  # status of port 9000 (default)
devbrowser -Mode Headless -Port 9001        # launch/ensure headless instance
devbrowser -Mode Visible                    # launch/ensure visible instance
devbrowser -Mode Open -Port 9000 -Url 'https://example.com/'   # open a tab
```

If an endpoint probe fails, run `devbrowser` first - do not start Opera or
Chrome yourself.

## Explicit signed-in provider lane: providerbrowser

Use `providerbrowser <provider>` only after the user explicitly names or selects
that persistent provider profile. DevHome maintains one shared browser process
and endpoint per provider on its deterministic, catalog-assigned loopback port.
The lane runs headless by default. Use `-Mode Visible` only for login, CAPTCHA,
consent, or attended work.

Concurrent agents call the same command. If that provider endpoint is already
healthy and owned by the exact selected profile and configured executable, the
command must reuse it and open a new tab; it must never start another browser
merely to change its mode. If the port, profile, executable, endpoint health,
or owner cannot be proved, fail closed and report the conflict. Preserve the
loopback and machine-identity guards; do not bypass them with a manual launch.
The command succeeds only after its result reports
`ProfileOwnerVerified = True`. The signed-in persistent provider profile must
not be described as isolated. Do not infer a provider profile from a site,
task, URL, or apparent account need.

```powershell
$browser = providerbrowser <provider> -Url 'https://example.com/'
$port = $browser.Port
Invoke-RestMethod "http://127.0.0.1:$port/json/version"
node <skill-dir>/cdp.mjs --port $port tabs

# Visible is an explicit attended exception:
providerbrowser <provider> -Mode Visible -Url 'https://example.com/'
```

Do not kill or restart a provider profile to gain access. Do not close user
tabs. Close only disposable tabs the agent opened, and only when safe.

## Driving the browser

**Option A - chrome-devtools-mcp (rich toolset).** Preferred for
interactive work: click, fill, snapshots, console, network, performance
tracing. The MCP server must attach to a DevHome CDP endpoint, for example
`--browser-url http://127.0.0.1:9000` (use `9001` for the headless instance).
Do not start it bare: a bare server launches a separate Chrome instance and
violates this skill's browser-routing and profile-isolation contract. If the
MCP configuration cannot pass `--browser-url`, use Option B instead.

For the provider lane, direct `cdp.mjs --port $port` with the command-returned
`Port` is the default. Use chrome-devtools-mcp only when its effective
`--browser-url` is proven to target exactly the command-returned `Endpoint`.
Never call `list_pages` before that proof.

### MCP attachment preflight (required)

Before calling any chrome-devtools-mcp browser tool, verify the **effective MCP
launch arguments**. Tool availability, an enabled plugin, or a successful MCP
server startup is not proof that the server is attached to DevHome Opera.

For Codex, inspect `codex mcp get chrome-devtools --json` or `codex mcp list`.
The effective arguments must contain `--browser-url` targeting the intended
DevHome endpoint. Read [CODEX-INTEGRATION.md](CODEX-INTEGRATION.md) before
changing the Codex MCP or plugin registration.

Do not call `list_pages` or another browser MCP tool to test a bare or
unverified registration: the first browser operation can launch the wrong
Chrome/profile. If the argument is absent or cannot be proved, use `cdp.mjs`.

**Option B - direct CDP via `cdp.mjs`.** Zero-dependency Node script
next to this SKILL.md (Node 22+, no npm install). Works on any port:

```bash
node <skill-dir>/cdp.mjs                          # status + tab list (port 9000)
node <skill-dir>/cdp.mjs --port 9001 tabs         # list headless tabs
node <skill-dir>/cdp.mjs --port $port tabs        # selected provider's returned Port
node <skill-dir>/cdp.mjs new https://example.com/ # open tab, prints id
node <skill-dir>/cdp.mjs goto 3 https://foo/      # navigate tab (index or id prefix)
node <skill-dir>/cdp.mjs eval 3 "document.title"  # run JS, print result
node <skill-dir>/cdp.mjs text 3                   # page innerText (read a page)
node <skill-dir>/cdp.mjs screenshot 3 out.png     # capture PNG
node <skill-dir>/cdp.mjs close 3                  # close tab
```

Tab argument is a `tabs` index or an id prefix. Exit code 1 with a clear
message on any failure (endpoint down, bad tab, page exception).

**Option C - raw HTTP for quick checks.**

```bash
curl -s http://127.0.0.1:9000/json/version   # is it up, what build
curl -s http://127.0.0.1:9000/json/list      # all targets, ws URLs
```

## Rules of engagement

- Navigation and read-only assistance are scoped to the user's request.
  Do not submit, send, post, purchase, delete, change account settings, or
  disclose data without explicit instruction for that action.
- Reuse the running instances; don't kill or restart ones you didn't start.
  The user often has work open in the visible instance.
- Need isolation (clean cookies, parallel task)? Launch a new port via
  `devbrowser -Mode Headless -Port <n>`, and close your tabs when done.
- Headless-first for scraping/testing; use the visible instance when the user
  should see what's happening or has already staged state there.
- `devbrowser` mutations are identity-gated to this machine (snd-desk); if it
  refuses, stop and report - do not bypass via manual process launch.
- `providerbrowser` is also identity-gated. Bail on any command error or
  unhealthy endpoint; never weaken its loopback or identity checks.
