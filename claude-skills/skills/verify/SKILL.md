---
name: verify
description: "Use when a DevHome shell/powershell profile or module change needs evidence captured at its real surface: interactive pwsh and Windows PowerShell 5.1 console sessions with the profile loaded, plus the DevHome shell test gates. Do not use to verify handoff claims, test results, deployments, or any work outside the DevHome PowerShell profile; ordinary verification belongs to the workflow that owns the work (review, qa, ship)."
---

# Verifying DevHome shell changes

The surface for `shell/powershell` changes is a live console session of each
engine (pwsh and Windows PowerShell 5.1) with the profile loaded. The profile
stubs in `Documents\PowerShell` / `Documents\WindowsPowerShell` dot-source the
repo's `shell/powershell/bootstrap/Initialize-DevHomeProfile.ps1` directly, so
a fresh shell always runs the working tree — no install step needed to test.

Resolve the repo from the authoritative code root; never hardcode the drive:

```powershell
$devhome = Join-Path $env:MACHINE_CODE_ROOT 'DevHome'
```

## Gotchas that invalidate naive probes

- `Enable-DevHomeInlinePrediction` guards on `[Console]::IsOutputRedirected`
  and returns before doing anything. Any piped session (Bash/PowerShell tool,
  `winpty -Xallow-non-tty`) silently skips ALL profile presentation config —
  you'll observe defaults and wrongly conclude the change is broken.
- winpty fails here: plain winpty refuses ("stdin is not a tty");
  `-Xallow-non-tty` asserts on zero console dimensions.
- The tool session inherits a pwsh-constructed `PSModulePath` (telltale `;;`
  in it). Children inherit it too — a 5.1 child then resolves modules from
  *pwsh's* user dir (`Documents\PowerShell\Modules`), not its own, and
  `Start-Process -WindowStyle Hidden` does NOT drop the inherited value.
  Machine/user registry values are default/empty; the pollution is in-process.

## Working recipe

Write a capture script that dumps state to a file (stdout must stay a real
console or the guard trips), then launch each engine with a registry-fresh
environment:

```powershell
Start-Process -FilePath 'powershell' -UseNewEnvironment -Wait -WindowStyle Hidden `
  -ArgumentList '-NoLogo','-ExecutionPolicy','Bypass','-File',$capture,"$sp\out-ps5.txt"
Start-Process -FilePath 'pwsh' -UseNewEnvironment -Wait -WindowStyle Hidden `
  -ArgumentList '-NoLogo','-File',$capture,"$sp\out-pwsh.txt"
```

`-UseNewEnvironment` rebuilds env from the registry — the only way found to
simulate a real Explorer/Terminal launch (5.1 then builds its own default
`PSModulePath` starting with `Documents\WindowsPowerShell\Modules`).

Capture at minimum: `$PSVersionTable.PSVersion`, `[Console]::IsOutputRedirected`,
`(Get-Module PSReadLine).Version` + `.ModuleBase` (which dir actually fed the
session), `Get-PSReadLineOption` fields under test, and
`Get-PSReadLineKeyHandler | Where-Object Key -eq '<key>'`.

The guard path itself is verified the opposite way: run the same statements as
`pwsh -NoLogo -File probe.ps1` through a pipe and confirm defaults remain and
nothing leaks to output.

## Repo validation gate (separate from verification)

```powershell
$tests = Join-Path $devhome 'shell\powershell\tests\Invoke-Tests.ps1'
pwsh.exe -NoProfile -File $tests
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $tests
```

The 5.1 gate FAILS under the tool session's inherited `PSModulePath`
(`Get-FileHash` not recognized — 5.1 resolves Microsoft.PowerShell.Utility from
PS7's Core-only module dir). Reset the path from known folders first when
running it from a tool:

```powershell
$env:PSModulePath = @(
    (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'WindowsPowerShell\Modules')
    (Join-Path ${env:ProgramFiles} 'WindowsPowerShell\Modules')
    (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\Modules')
) -join ';'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $tests
```

## Hazard writing probes from the Bash tool

Nested `''` inside a bash single-quoted `pwsh -Command '...'` does NOT produce
a quote — it toggles quoting and strips them (`-eq ''Tab''` reaches pwsh as
`-eq Tab`). pwsh then dies on a parse error with no visible stderr, which looks
exactly like "the change broke the shell". Use `-File` with a written script
for anything non-trivial.

## Gate launch trap (2026-10-07)

Do not launch `Invoke-Verification.ps1` from the Bash tool: its header
refuses a Git Bash parent, and the Git Bash/Cygwin parent enables
`SeBackupPrivilege` on the inherited token, so a Deny-ACE case cannot observe
the denial. Since 2026-10-07 `AiProviderStateReport.Tests.ps1` and
`CompatJunctionGuard.Tests.ps1` probe their denied fixture with
`Test-DevHomeListDenyEnforced` (TestSupport.ps1) and print
`SKIP: ... needs a token without an enabled backup privilege` under that
token; a SKIP line means the case was not exercised, not that it passed.
Run the gate as a hidden child from the PowerShell tool:
`Start-Process pwsh -WindowStyle Hidden -Wait -PassThru -ArgumentList
'-NoProfile','-File',<inner>` where the inner script wraps the gate call in
try/catch and redirects `*>>` to a log (a terminating error otherwise escapes
the redirect and vanishes with no console). `-UseNewEnvironment` is not
needed for the gate.
