[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$KFlow = Join-Path $RepoRoot ".venv\Scripts\kflow.exe"
$ModelingSkillCommit = "88e97054bddc789239b66b38485469d5d1b6e09e"

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

function Assert-SkillFrontmatter {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ExpectedName
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Skill file is missing: $Path"
    }
    $Text = Get-Content -Raw -LiteralPath $Path
    $Parts = [regex]::Split($Text, "(?m)^---\s*$")
    if ($Parts.Count -lt 3) {
        throw "Skill frontmatter is missing or malformed: $Path"
    }
    $NamePattern = "(?m)^name:\s*" + [regex]::Escape($ExpectedName) + "\s*$"
    if ($Parts[1] -notmatch $NamePattern) {
        throw "Skill frontmatter name is not '$ExpectedName': $Path"
    }
    Write-Host "Skill OK: $ExpectedName"
}

Push-Location $RepoRoot
try {
    if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
        throw "Virtual-environment Python is missing. Run .\scripts\setup.ps1 first."
    }

    Invoke-NativeChecked $VenvPython @("-c", "import sys; assert sys.version_info >= (3,11); print('Python version:', sys.version.split()[0]); print('venv Python:', sys.executable)") "Python version check"
    Invoke-NativeChecked $VenvPython @("-c", "import numpy,pandas,scipy,matplotlib,sklearn,networkx,openpyxl,yaml; print('Python imports: OK')") "Python package import check"

    if (-not (Test-Path -LiteralPath $KFlow -PathType Leaf)) {
        throw "KFlow entry point is missing: $KFlow"
    }
    $KFlowHelp = & $KFlow --help
    if ($LASTEXITCODE -ne 0) {
        throw "KFlow --help failed with exit code $LASTEXITCODE."
    }
    $KFlowHelp | Select-Object -First 8
    Invoke-NativeChecked $VenvPython @("-c", "import importlib.metadata as m; d=m.distribution('kflow'); print('KFlow version:',d.version); print('KFlow source:',(d.read_text('direct_url.json') or 'not recorded').strip())") "KFlow installation metadata check"

    $KFlowProject = Join-Path $RepoRoot ".kflow\project.json"
    if (-not (Test-Path -LiteralPath $KFlowProject -PathType Leaf)) {
        throw "KFlow project metadata is missing: $KFlowProject"
    }
    Invoke-NativeChecked $KFlow @("overview", "--status", "-p") "KFlow read-only overview"
    Invoke-NativeChecked $KFlow @("validate") "KFlow project validation"

    $KFlowSkill = Join-Path $RepoRoot ".agents\skills\kflow\SKILL.md"
    $ModelingSkill = Join-Path $RepoRoot ".agents\skills\math-modeling-skill\SKILL.md"
    Assert-SkillFrontmatter $KFlowSkill "kflow"
    if (-not (Test-Path -LiteralPath $ModelingSkill -PathType Leaf)) {
        throw "Math Modeling Skill is not provisioned. Run .\scripts\setup.ps1 first."
    }
    Assert-SkillFrontmatter $ModelingSkill "math-modeling-skill"

    $ModelingSkillRoot = Split-Path -Parent $ModelingSkill
    $ModelingSkillMarker = Join-Path $ModelingSkillRoot ".cumcm-source-commit"
    if (-not (Test-Path -LiteralPath $ModelingSkillMarker -PathType Leaf)) {
        throw "Math Modeling Skill source marker is missing. Run .\scripts\setup.ps1 to install the pinned version."
    }
    $InstalledModelingSkillCommit = (Get-Content -Raw -LiteralPath $ModelingSkillMarker).Trim()
    if ($InstalledModelingSkillCommit -ne $ModelingSkillCommit) {
        throw "Math Modeling Skill commit is '$InstalledModelingSkillCommit', expected '$ModelingSkillCommit'. Run .\scripts\setup.ps1."
    }
    foreach ($RequiredPath in @("cases", "knowledge", "templates", "scripts", "code", "references", "agents", "LICENSE", "THIRD-PARTY-NOTICE.md")) {
        if (-not (Test-Path -LiteralPath (Join-Path $ModelingSkillRoot $RequiredPath))) {
            throw "Math Modeling Skill is missing required content: $RequiredPath"
        }
    }
    Write-Host "Math Modeling Skill commit: $InstalledModelingSkillCommit"

    Push-Location $ModelingSkillRoot
    try {
        $ContentValidator = Join-Path $ModelingSkillRoot "scripts\validate_skill_content.py"
        $RepositoryValidator = Join-Path $ModelingSkillRoot "scripts\validate_repository.py"
        if (Test-Path -LiteralPath $ContentValidator -PathType Leaf) {
            Invoke-NativeChecked $VenvPython @("-B", $ContentValidator) "Math Modeling Skill content validation"
        }
        if (Test-Path -LiteralPath $RepositoryValidator -PathType Leaf) {
            Invoke-NativeChecked $VenvPython @("-B", $RepositoryValidator) "Math Modeling Skill repository validation"
        }
    }
    finally {
        Pop-Location
    }

    Write-Host "Environment verification passed"
}
finally {
    Pop-Location
}
