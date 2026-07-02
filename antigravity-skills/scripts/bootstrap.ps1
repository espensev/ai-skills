param (
    [Parameter(Mandatory=$false)]
    [string]$TargetDir = "."
)

$ErrorActionPreference = "Stop"

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $SourceDir
$TargetDir = Resolve-Path $TargetDir | Select-Object -ExpandProperty Path

Write-Host "Starting antigravity-skills adapter bootstrap..."
Write-Host "Source: $ProjectRoot"
Write-Host "Target: $TargetDir"

if (-not (Test-Path $TargetDir)) {
    Write-Error "Target directory does not exist: $TargetDir"
    exit 1
}

$ManifestPath = Join-Path $ProjectRoot "package\install-manifest.json"
if (-not (Test-Path $ManifestPath)) {
    Write-Error "Missing install manifest: $ManifestPath"
    exit 1
}

$InstallManifest = Get-Content -Path $ManifestPath -Raw | ConvertFrom-Json

$TargetAgentsDir = Join-Path $TargetDir ".agents"
$TargetSkillsDir = Join-Path $TargetAgentsDir "skills"
$TargetAgentDir = Join-Path $TargetDir ".agent"
$TargetWorkflowsDir = Join-Path $TargetAgentDir "workflows"

foreach ($Dir in @($TargetAgentsDir, $TargetSkillsDir, $TargetAgentDir, $TargetWorkflowsDir)) {
    if (-not (Test-Path $Dir)) {
        Write-Host "Creating $Dir..."
        New-Item -ItemType Directory -Force -Path $Dir | Out-Null
    }
}

$SourceSkillsDir = Join-Path $ProjectRoot "skills"
Write-Host "Copying skills from $SourceSkillsDir..."
foreach ($SkillName in $InstallManifest.skills) {
    $SourceSkillPath = Join-Path $SourceSkillsDir $SkillName
    $TargetSkillPath = Join-Path $TargetSkillsDir $SkillName

    if (-not (Test-Path $SourceSkillPath)) {
        Write-Error "Manifest references missing skill: $SourceSkillPath"
        exit 1
    }

    if (-not (Test-Path $TargetSkillPath)) {
        Write-Host "  Copying skill: $SkillName"
        Copy-Item -Path $SourceSkillPath -Destination $TargetSkillsDir -Recurse
    } else {
        Write-Host "  Skipping existing skill: $SkillName"
    }
}

$SourceWorkflowsDir = Join-Path $ProjectRoot ".agent\workflows"
Write-Host "Copying workflows from $SourceWorkflowsDir..."
foreach ($Workflow in $InstallManifest.workflows) {
    $SourceWorkflowPath = Join-Path $SourceWorkflowsDir $Workflow
    $TargetWorkflowPath = Join-Path $TargetWorkflowsDir $Workflow

    if (-not (Test-Path $SourceWorkflowPath)) {
        Write-Error "Manifest references missing workflow: $SourceWorkflowPath"
        exit 1
    }

    if (-not (Test-Path $TargetWorkflowPath)) {
        Write-Host "  Installing workflow: $Workflow"
        Copy-Item -Path $SourceWorkflowPath -Destination $TargetWorkflowPath
    } else {
        Write-Host "  Skipping existing workflow: $Workflow"
    }
}

$SourceAgentsMd = Join-Path $ProjectRoot "AGENTS.md"
$TargetAgentsMd = Join-Path $TargetDir "AGENTS.md"

if (Test-Path $SourceAgentsMd) {
    $Content = Get-Content -Path $SourceAgentsMd -Raw
    $GuardrailsMarker = "## Global Multi-Agent Guardrails"

    if ($Content -match "$GuardrailsMarker.*") {
        $GuardrailsContent = $Matches[0]

        Write-Host "Injecting Global Guardrails into target AGENTS.md..."
        if (-not (Test-Path $TargetAgentsMd)) {
            Write-Host "  Creating new AGENTS.md"
            Set-Content -Path $TargetAgentsMd -Value $GuardrailsContent
        } else {
            $TargetContent = Get-Content -Path $TargetAgentsMd -Raw
            if ($TargetContent -match $GuardrailsMarker) {
                Write-Host "  Guardrails already present in target AGENTS.md. Skipping."
            } else {
                Write-Host "  Appending to existing AGENTS.md"
                Add-Content -Path $TargetAgentsMd -Value "`n`n$GuardrailsContent"
            }
        }
    } else {
        Write-Warning "Could not find 'Global Multi-Agent Guardrails' in source AGENTS.md"
    }
}

Write-Host "Bootstrap complete. Antigravity should discover workflows from .agent/workflows and skills from .agents/skills."
