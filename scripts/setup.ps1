[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvRoot = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvRoot "Scripts\python.exe"
$KFlow = Join-Path $VenvRoot "Scripts\kflow.exe"
$ModelingSkillUpstream = "https://github.com/skillforCUMCM/math-modeling-skill-pro.git"
$ModelingSkillCommit = "88e97054bddc789239b66b38485469d5d1b6e09e"
$SkillsRoot = Join-Path $RepoRoot ".agents\skills"
$ModelingSkillRoot = Join-Path $SkillsRoot "math-modeling-skill"
$ModelingSkillMarker = Join-Path $ModelingSkillRoot ".cumcm-source-commit"

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Description
    )

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

function Find-CompatiblePython {
    $Commands = @(Get-Command python -CommandType Application -All -ErrorAction SilentlyContinue)
    foreach ($Command in $Commands) {
        $Candidate = $Command.Source
        $Probe = & $Candidate -c "import json,sys; print(json.dumps({'major':sys.version_info.major,'minor':sys.version_info.minor,'version':sys.version.split()[0]}))" 2>$null | Select-Object -Last 1
        if ($LASTEXITCODE -ne 0 -or -not $Probe) {
            continue
        }
        try {
            $Version = $Probe | ConvertFrom-Json
        }
        catch {
            continue
        }
        if (($Version.major -gt 3) -or (($Version.major -eq 3) -and ($Version.minor -ge 11))) {
            Write-Host "Python $($Version.version): $Candidate"
            return $Candidate
        }
    }
    throw "Python 3.11 or newer is required. Install it and ensure a working 'python' command is on PATH; the setup script will not modify system Python."
}

function Install-MathModelingSkill {
    $SkillFile = Join-Path $ModelingSkillRoot "SKILL.md"
    if ((Test-Path -LiteralPath $SkillFile -PathType Leaf) -and (Test-Path -LiteralPath $ModelingSkillMarker -PathType Leaf)) {
        $InstalledCommit = (Get-Content -Raw -LiteralPath $ModelingSkillMarker).Trim()
        if ($InstalledCommit -eq $ModelingSkillCommit) {
            Write-Host "Reusing Math Modeling Skill at pinned commit $ModelingSkillCommit."
            return
        }
        Write-Host "Math Modeling Skill commit mismatch ($InstalledCommit); safely replacing it with pinned commit $ModelingSkillCommit."
    }
    elseif (Test-Path -LiteralPath $ModelingSkillRoot) {
        Write-Host "Math Modeling Skill is incomplete or lacks a source marker; safely replacing it with the pinned version."
    }
    else {
        Write-Host "Provisioning Math Modeling Skill at pinned commit $ModelingSkillCommit."
    }

    $InstallId = [guid]::NewGuid().ToString("N")
    $InstallRoot = Join-Path $SkillsRoot ".math-modeling-skill-install-$InstallId"
    $BackupRoot = Join-Path $SkillsRoot ".math-modeling-skill-backup-$InstallId"
    $ExistingMoved = $false

    try {
        Invoke-NativeChecked "git" @("clone", "--filter=blob:none", "--no-checkout", $ModelingSkillUpstream, $InstallRoot) "Math Modeling Skill download (authorization may be required by the upstream license)"
        Invoke-NativeChecked "git" @("-C", $InstallRoot, "checkout", "--detach", $ModelingSkillCommit) "Math Modeling Skill pinned checkout"

        $ResolvedCommit = (& git -C $InstallRoot rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0 -or $ResolvedCommit -ne $ModelingSkillCommit) {
            throw "Math Modeling Skill checkout resolved to '$ResolvedCommit', expected '$ModelingSkillCommit'."
        }

        $NestedGit = Join-Path $InstallRoot ".git"
        if (-not (Test-Path -LiteralPath $NestedGit)) {
            throw "Downloaded Math Modeling Skill does not contain expected Git metadata."
        }
        Remove-Item -LiteralPath $NestedGit -Recurse -Force
        Set-Content -LiteralPath (Join-Path $InstallRoot ".cumcm-source-commit") -Value $ModelingSkillCommit -NoNewline

        foreach ($RequiredPath in @("SKILL.md", "LICENSE", "THIRD-PARTY-NOTICE.md", "cases", "knowledge", "templates", "scripts", "code", "references", "agents")) {
            if (-not (Test-Path -LiteralPath (Join-Path $InstallRoot $RequiredPath))) {
                throw "Downloaded Math Modeling Skill is missing required content: $RequiredPath"
            }
        }

        Invoke-NativeChecked $VenvPython @("-B", (Join-Path $InstallRoot "scripts\validate_skill_content.py")) "Downloaded Math Modeling Skill content validation"
        Invoke-NativeChecked $VenvPython @("-B", (Join-Path $InstallRoot "scripts\validate_repository.py")) "Downloaded Math Modeling Skill repository validation"

        if (Test-Path -LiteralPath $ModelingSkillRoot) {
            Move-Item -LiteralPath $ModelingSkillRoot -Destination $BackupRoot
            $ExistingMoved = $true
        }
        try {
            Move-Item -LiteralPath $InstallRoot -Destination $ModelingSkillRoot
        }
        catch {
            if ($ExistingMoved -and -not (Test-Path -LiteralPath $ModelingSkillRoot)) {
                Move-Item -LiteralPath $BackupRoot -Destination $ModelingSkillRoot
                $ExistingMoved = $false
            }
            throw
        }

        if ($ExistingMoved -and (Test-Path -LiteralPath $BackupRoot)) {
            Remove-Item -LiteralPath $BackupRoot -Recurse -Force
            $ExistingMoved = $false
        }
        Write-Host "Math Modeling Skill ready at $ModelingSkillRoot."
    }
    finally {
        if (Test-Path -LiteralPath $InstallRoot) {
            Remove-Item -LiteralPath $InstallRoot -Recurse -Force
        }
        if ($ExistingMoved -and (Test-Path -LiteralPath $BackupRoot) -and -not (Test-Path -LiteralPath $ModelingSkillRoot)) {
            Move-Item -LiteralPath $BackupRoot -Destination $ModelingSkillRoot
        }
    }
}

Push-Location $RepoRoot
try {
    $SystemPython = Find-CompatiblePython

    if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
        if (Test-Path -LiteralPath $VenvRoot) {
            throw ".venv exists but does not contain Scripts\python.exe. Move or repair it before retrying; setup will not overwrite it."
        }
        Write-Host "Creating repository virtual environment..."
        Invoke-NativeChecked $SystemPython @("-m", "venv", $VenvRoot) "Virtual environment creation"
    }
    else {
        Write-Host "Reusing existing .venv."
    }

    Invoke-NativeChecked $VenvPython @("-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel") "Base packaging-tool installation"
    Invoke-NativeChecked $VenvPython @("-m", "pip", "install", "-r", (Join-Path $RepoRoot "requirements.txt")) "Modeling dependency installation"

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Git is required to install the commit-pinned KFlow dependency and Math Modeling Skill."
    }
    Invoke-NativeChecked $VenvPython @("-m", "pip", "install", "-r", (Join-Path $RepoRoot "requirements-tools.txt")) "Tool dependency installation"

    Install-MathModelingSkill

    $RequiredSkills = @(
        (Join-Path $RepoRoot ".agents\skills\kflow\SKILL.md"),
        (Join-Path $ModelingSkillRoot "SKILL.md")
    )
    foreach ($Skill in $RequiredSkills) {
        if (-not (Test-Path -LiteralPath $Skill -PathType Leaf)) {
            throw "Required repository-local Skill is missing: $Skill"
        }
    }

    $KFlowProject = Join-Path $RepoRoot ".kflow\project.json"
    if (Test-Path -LiteralPath $KFlowProject -PathType Leaf) {
        Write-Host "Preserving existing KFlow project metadata."
        foreach ($Directory in @("nodes", "derivations", "confirmations", "runtime")) {
            New-Item -ItemType Directory -Path (Join-Path $RepoRoot ".kflow\$Directory") -Force | Out-Null
        }
    }
    else {
        $KFlowRoot = Join-Path $RepoRoot ".kflow"
        if (Test-Path -LiteralPath $KFlowRoot) {
            throw ".kflow exists without project.json. Setup will not overwrite or replace ambiguous KFlow state."
        }
        Write-Host "Initializing KFlow project metadata..."
        Invoke-NativeChecked $KFlow @("init", ".") "KFlow initialization"
    }

    & (Join-Path $PSScriptRoot "verify-environment.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "Environment verification failed with exit code $LASTEXITCODE."
    }

    Write-Host "Environment ready"
}
finally {
    Pop-Location
}
