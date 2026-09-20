#requires -Version 5.1
[CmdletBinding()]
param([string]$ConfigPath = (Join-Path (Split-Path $PSScriptRoot -Parent) 'config\local.json'))
. (Join-Path $PSScriptRoot 'Common.ps1')
$config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$baseline = Get-Content -LiteralPath $config.sourceBaseline -Raw | ConvertFrom-Json
if ((Get-BMFullPath $config.sourceGamePath) -ne (Get-BMFullPath $baseline.sourcePath)) { throw 'Baseline source does not match local configuration.' }
$actual = @(Get-BMInventory $config.sourceGamePath)
$diff = @(Compare-BMInventory @($baseline.files) $actual)
if ($diff.Count -gt 0) { throw ('Original installation differs from the saved baseline: ' + ($diff -join '; ')) }
Write-Host 'PASS: original installation matches the recorded SHA-256 baseline.' -ForegroundColor Green

