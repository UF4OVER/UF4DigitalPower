$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot

try {
    uv run python -m cx_Freeze build
    if ($LASTEXITCODE -ne 0) {
        throw "cx_Freeze build failed with exit code $LASTEXITCODE"
    }

#    $legacyDir = Join-Path $repoRoot "build\exe\PyQt5.uic.widget-plugins"
#    $targetDir = Join-Path $repoRoot "build\exe\lib\PyQt5\uic\widget-plugins"
#    $targetParent = Split-Path -Parent $targetDir
#
#    if (-not (Test-Path -LiteralPath $legacyDir)) {
#        Write-Host "No legacy widget-plugins directory found. Build output already normalized."
#        exit 0
#    }
#
#    if (-not (Test-Path -LiteralPath $targetParent)) {
#        New-Item -ItemType Directory -Path $targetParent -Force | Out-Null
#    }
#
#    if (Test-Path -LiteralPath $targetDir) {
#        Remove-Item -LiteralPath $targetDir -Recurse -Force
#    }

#    Move-Item -LiteralPath $legacyDir -Destination $targetDir
#    Write-Host "Moved PyQt5 widget-plugins to $targetDir"
}
finally {
    Pop-Location
}
