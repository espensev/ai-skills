---
name: verify
description: "Use when a DevHome shell/powershell profile or module change needs tests and evidence from interactive pwsh and Windows PowerShell 5.1 consoles. Do not use for handoff claims, deployments, general test results, or work outside the DevHome PowerShell profile; use the workflow that owns that work (review, qa, ship)."
---

# Verifying DevHome shell changes

Automated tests are the default gate. Live consoles establish final runtime
acceptance for profile presentation and other behavior that requires a console.
Resolve the source from the authoritative environment variable:

```powershell
if ([string]::IsNullOrWhiteSpace($env:MACHINE_CODE_ROOT)) {
    throw 'MACHINE_CODE_ROOT is required.'
}
$devhome = Join-Path $env:MACHINE_CODE_ROOT 'DevHome'
$tests = Join-Path $devhome 'shell/powershell/tests/Invoke-Tests.ps1'
```

## Source tests and installed runtime

Read `AGENTS.md` and `docs/devhome-shell-runtime.md` in DevHome before choosing
the relevant tests. Run focused source tests first; use the aggregate gates
when the change requires them:

```powershell
pwsh.exe -NoProfile -File $tests
```

A fresh shell runs the installed implementation on the tools volume selected
by `MACHINE_TOOLS_ROOT`. The Windows profile entry files forward to that
implementation. Editing the checkout does not update the installed runtime.
Source test results and installed console results are separate evidence.
Publication follows the DevHome runtime contract and requires authorization;
this skill does not authorize deployment. Record the installed generation and
loaded function `ScriptBlock.File` paths before attributing a result to a change.

The tool session can carry a pwsh-built `PSModulePath` that breaks the 5.1
gate. Reset it from known folders for that child, then restore it:

```powershell
$previousModulePath = $env:PSModulePath
try {
    $env:PSModulePath = @(
        (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'WindowsPowerShell/Modules')
        (Join-Path ${env:ProgramFiles} 'WindowsPowerShell/Modules')
        (Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/Modules')
    ) -join ';'
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File $tests
} finally {
    $env:PSModulePath = $previousModulePath
}
```

## Live console evidence

`Enable-DevHomeInlinePrediction` returns early when
`[Console]::IsOutputRedirected` is true. Piped and winpty sessions do not prove
presentation behavior. Write a capture script to an approved scratch directory
and have it write results to a file, keeping stdout attached to the console.
Define `$capture` as that script and `$sp` as its output directory, then launch:

```powershell
Start-Process -FilePath 'powershell' -UseNewEnvironment -Wait -WindowStyle Hidden `
  -ArgumentList '-NoLogo','-ExecutionPolicy','Bypass','-File',"`"$capture`"","`"$sp/out-ps5.txt`""
Start-Process -FilePath 'pwsh' -UseNewEnvironment -Wait -WindowStyle Hidden `
  -ArgumentList '-NoLogo','-File',"`"$capture`"","`"$sp/out-pwsh.txt`""
```

`-UseNewEnvironment` refreshes the child environment from persisted settings.
Capture the engine version, `Console.IsOutputRedirected`, PSReadLine version
and module base, the options and key handlers under test, and actual loaded
implementation paths. Confirm the child completed and the output file is fresh.
Test redirected-output guards separately through a pipe.

Use a script with `-File` for probes; nested shell quotes can silently change
PowerShell expressions. Do not launch `shell/tests/Invoke-Verification.ps1`
through Git Bash: it rejects that parent, and an inherited backup privilege
can invalidate Deny-ACE fixtures. Run it from PowerShell; for a hidden child,
catch errors inside the script and redirect all streams to its log. A reported
`SKIP` means the fixture was not exercised, not that it passed.

## Ownership

This machine-specific recipe is generated for both providers from
`skills-src/verify/SKILL.src.md` in Ai-Skills. It remains source-only for portable
exports. Use the explicit selected-skill install and check commands in
`docs/local-agent-skill-access.md` to maintain its existing local roots.
