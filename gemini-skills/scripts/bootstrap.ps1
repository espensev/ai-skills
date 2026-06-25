param (
    [Parameter(Mandatory=$false)]
    [string]$TargetDir = "."
)

# Resolve full paths
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $SourceDir
$TargetDir = Resolve-Path $TargetDir | Select-Object -ExpandProperty Path

Write-Host "Starting gemini-skills adapter bootstrap..."
Write-Host "Source: $ProjectRoot"
Write-Host "Target: $TargetDir"

if (-Not (Test-Path $TargetDir)) {
    Write-Error "Target directory does not exist: $TargetDir"
    exit 1
}

$ManifestPath = Join-Path $ProjectRoot "package\install-manifest.json"
if (-Not (Test-Path $ManifestPath)) {
    Write-Error "Missing install manifest: $ManifestPath"
    exit 1
}

$InstallManifest = Get-Content -Path $ManifestPath -Raw | ConvertFrom-Json

# 1. Setup target Gemini runtime directories
$TargetGeminiDir = Join-Path $TargetDir ".gemini"
$TargetSkillsDir = Join-Path $TargetGeminiDir "skills"
$TargetCommandsDir = Join-Path $TargetGeminiDir "commands"

foreach ($Dir in @($TargetGeminiDir, $TargetSkillsDir, $TargetCommandsDir)) {
    if (-Not (Test-Path $Dir)) {
        Write-Host "Creating $Dir..."
        New-Item -ItemType Directory -Force -Path $Dir | Out-Null
    }
}

# 2. Copy skills wrappers
$SourceSkillsDir = Join-Path $ProjectRoot "skills"
Write-Host "Copying skills from $SourceSkillsDir..."
if (Test-Path $SourceSkillsDir) {
    foreach ($SkillName in $InstallManifest.skills) {
        $SourceSkillPath = Join-Path $SourceSkillsDir $SkillName
        $TargetSkillPath = Join-Path $TargetSkillsDir $SkillName

        if (-Not (Test-Path $SourceSkillPath)) {
            Write-Error "Manifest references missing skill: $SourceSkillPath"
            exit 1
        }

        if (-Not (Test-Path $TargetSkillPath)) {
            Write-Host "  Copying skill: $SkillName"
            Copy-Item -Path $SourceSkillPath -Destination $TargetSkillsDir -Recurse
        } else {
            Write-Host "  Skipping existing skill: $SkillName"
        }
    }
} else {
    Write-Warning "Source skills directory not found: $SourceSkillsDir"
}

# 3. Copy Gemini command wrappers
$SourceCommandsDir = Join-Path $ProjectRoot ".gemini\commands"
Write-Host "Copying command wrappers from $SourceCommandsDir..."
if (Test-Path $SourceCommandsDir) {
    foreach ($CommandWrapper in $InstallManifest.command_wrappers) {
        $SourceCommandPath = Join-Path $SourceCommandsDir $CommandWrapper
        $TargetCommandPath = Join-Path $TargetCommandsDir $CommandWrapper

        if (-Not (Test-Path $SourceCommandPath)) {
            Write-Error "Manifest references missing command wrapper: $SourceCommandPath"
            exit 1
        }

        if (-Not (Test-Path $TargetCommandPath)) {
            Write-Host "  Copying command wrapper: $CommandWrapper"
            Copy-Item -Path $SourceCommandPath -Destination $TargetCommandPath -Force
        } else {
            Write-Host "  Skipping existing command wrapper: $CommandWrapper"
        }
    }
} else {
    Write-Warning "Source commands directory not found: $SourceCommandsDir"
}

# 4. Append guardrails to target GEMINI.md
$SourceGeminiMd = Join-Path $ProjectRoot "GEMINI.md"
$TargetGeminiMd = Join-Path $TargetDir "GEMINI.md"

if (Test-Path $SourceGeminiMd) {
    # Read only the global guardrails section to append, skipping the local package guidance
    $Content = Get-Content -Path $SourceGeminiMd -Raw
    $GuardrailsMarker = "## Global Multi-Agent Guardrails"
    
    if ($Content -match "$GuardrailsMarker.*") {
        $GuardrailsContent = $Matches[0]
        
        Write-Host "Injecting Global Guardrails into Target GEMINI.md..."
        if (-Not (Test-Path $TargetGeminiMd)) {
            Write-Host "  Creating new GEMINI.md"
            Set-Content -Path $TargetGeminiMd -Value $GuardrailsContent
        } else {
            $TargetContent = Get-Content -Path $TargetGeminiMd -Raw
            if ($TargetContent -match $GuardrailsMarker) {
                Write-Host "  Guardrails already present in target GEMINI.md. Skipping."
            } else {
                Write-Host "  Appending to existing GEMINI.md"
                Add-Content -Path $TargetGeminiMd -Value "`n`n$GuardrailsContent"
            }
        }
    } else {
         Write-Warning "Could not find 'Global Multi-Agent Guardrails' in source GEMINI.md"
    }
}

Write-Host "Bootstrap complete! You may need to run '/skills reload' in Gemini CLI to see the new skills and commands."
