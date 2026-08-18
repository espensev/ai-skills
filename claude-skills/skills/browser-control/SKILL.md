---
name: browser-control
description: "Use when a task needs a live browser: navigating pages, reading DOM or page text, screenshots, form fills, console/network inspection, or web app testing. Routes ALL browser automation through the DevHome Opera Developer CDP endpoints (devbrowser, ports 9000/9001) via chrome-devtools-mcp or direct CDP. Never use harness-bundled browser tooling (claude-in-chrome, browser-use, playwright) - it is disabled on purpose."
argument-hint: "[what to do in the browser]"
user-invocable: true
---

# Browser Control — DevHome CDP Routing

All browser automation on this machine goes through the **Opera Developer**
instances managed by `devbrowser` (DevHome.Profile). The harness-bundled
browser stacks are deliberately disabled and must not be re-enabled or worked
around — they pop windows into the user's real session.

**Banned:** claude-in-chrome (extension into the live browser), the
browser-use plugin/daemon, playwright, and launching your own Chrome/Chromium
instance by hand.

**Allowed:** the CDP endpoints below, driven by chrome-devtools-mcp or direct
CDP calls (helper script included).

## Endpoints

| Port | Instance | Profile |
|------|----------|---------|
| 9000 | visible  | isolated `opera-visible` state dir |
| 9001 | headless | isolated `opera-headless` state dir |

Loopback-only. Both use isolated profiles, so nothing here touches the user's
real browsing session. More instances on other ports are fine when a task
needs a clean profile — each `-Port` gets its own state dir.

## Launch / status: devbrowser

`devbrowser` is a PowerShell function from the DevHome profile (available in
any profile-loaded pwsh session; from bash run it via `pwsh -Command`).

```powershell
devbrowser                                  # status of port 9000 (default)
devbrowser -Mode Headless -Port 9001        # launch/ensure headless instance
devbrowser -Mode Visible                    # launch/ensure visible instance
devbrowser -Mode Open -Port 9000 -Url 'https://example.com/'   # open a tab
```

If an endpoint probe fails, run `devbrowser` first — do not start Opera or
Chrome yourself.

## Driving the browser

**Option A — chrome-devtools-mcp (rich toolset).** Preferred for
interactive work: click, fill, snapshots, console, network, performance
tracing. The MCP server must attach to a DevHome CDP endpoint, for example
`--browser-url http://127.0.0.1:9000` (use `9001` for the headless instance).
Do not start it bare: a bare server launches a separate Chrome instance and
violates this skill's browser-routing and profile-isolation contract. If the
MCP configuration cannot pass `--browser-url`, use Option B instead.

### MCP attachment preflight (required)

Before calling any chrome-devtools-mcp browser tool, verify the **effective MCP
launch arguments**. Tool availability, an enabled plugin, or a successful MCP
server startup is not proof that the server is attached to DevHome Opera.

Inspect the effective MCP command in the active Claude configuration. Its
arguments must contain `--browser-url` targeting the intended DevHome endpoint.

Do not call `list_pages` or another browser MCP tool to test a bare or
unverified registration: the first browser operation can launch the wrong
Chrome/profile. If the argument is absent or cannot be proved, use `cdp.mjs`.

**Option B — direct CDP via `cdp.mjs`.** Zero-dependency Node script
next to this SKILL.md (Node 22+, no npm install). Works on any port:

```bash
node <skill-dir>/cdp.mjs                          # status + tab list (port 9000)
node <skill-dir>/cdp.mjs --port 9001 tabs         # list headless tabs
node <skill-dir>/cdp.mjs new https://example.com/ # open tab, prints id
node <skill-dir>/cdp.mjs goto 3 https://foo/      # navigate tab (index or id prefix)
node <skill-dir>/cdp.mjs eval 3 "document.title"  # run JS, print result
node <skill-dir>/cdp.mjs text 3                   # page innerText (read a page)
node <skill-dir>/cdp.mjs screenshot 3 out.png     # capture PNG
node <skill-dir>/cdp.mjs close 3                  # close tab
```

Tab argument is a `tabs` index or an id prefix. Exit code 1 with a clear
message on any failure (endpoint down, bad tab, page exception).

**Option C — raw HTTP for quick checks.**

```bash
curl -s http://127.0.0.1:9000/json/version   # is it up, what build
curl -s http://127.0.0.1:9000/json/list      # all targets, ws URLs
```

## Rules of engagement

- Reuse the running instances; don't kill or restart ones you didn't start.
  The user often has work open in the visible instance.
- Need isolation (clean cookies, parallel task)? Launch a new port via
  `devbrowser -Mode Headless -Port <n>`, and close your tabs when done.
- Headless-first for scraping/testing; use the visible instance when the user
  should see what's happening or has already staged state there.
- `devbrowser` mutations are identity-gated to this machine (snd-desk); if it
  refuses, stop and report — do not bypass via manual process launch.
