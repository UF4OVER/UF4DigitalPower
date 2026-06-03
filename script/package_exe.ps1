$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot

try {
    $buildExeDir = Join-Path $repoRoot "build\exe"
    if (Test-Path -LiteralPath $buildExeDir) {
        Remove-Item -LiteralPath $buildExeDir -Recurse -Force
    }

    uv run python -m cx_Freeze build
    if ($LASTEXITCODE -ne 0) {
        throw "cx_Freeze build failed with exit code $LASTEXITCODE"
    }

}
finally {
    Pop-Location
}
