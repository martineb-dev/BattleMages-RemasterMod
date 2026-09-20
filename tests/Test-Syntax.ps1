#requires -Version 5.1
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
foreach ($file in @(Get-ChildItem -LiteralPath $root -Filter '*.ps1' -Recurse -File)) {
    $tokens = $null; $parseErrors = $null
    [void][Management.Automation.Language.Parser]::ParseFile($file.FullName,[ref]$tokens,[ref]$parseErrors)
    if (@($parseErrors).Count -gt 0) { throw "$($file.FullName): $($parseErrors -join '; ')" }
}
$catalog = Get-Content -LiteralPath (Join-Path $root 'catalog/assets.json') -Raw | ConvertFrom-Json
if ($catalog.schemaVersion -ne 1) { throw 'Unexpected catalog version.' }
if (@($catalog.assets | Where-Object { $_.enabledInBuild }).Count -gt 0) { throw 'No game assets are integration-approved in this bootstrap milestone.' }
Write-Host 'PASS: PowerShell parser and bootstrap catalog.' -ForegroundColor Green

