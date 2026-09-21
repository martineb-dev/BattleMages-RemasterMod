#requires -Version 5.1
[CmdletBinding()]
param([string]$ZipPath, [switch]$NoLaunch)
. (Join-Path $PSScriptRoot 'Common.ps1')
$repo = Split-Path $PSScriptRoot -Parent
$config = Get-Content -LiteralPath (Join-Path $repo 'config/local.json') -Raw | ConvertFrom-Json
$work = Get-BMFullPath $config.workRoot
$test = Get-BMFullPath $config.testGamePath
foreach ($path in @($work, $test)) {
    Assert-BMNoReparsePath $path
    Assert-BMSeparatePaths $config.sourceGamePath $path
}
if (-not (Test-BMContained $test $work) -or $test -eq $work) { throw 'Invalid test workspace.' }
Assert-BMGameRoot $test
if (@(Get-Process -Name mages -ErrorAction SilentlyContinue).Count) { throw 'Close Battle Mages first.' }

if (-not $ZipPath) {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Title = 'Select BM_Paladin_Realism_GameTest_01.zip (NEW game package)'
    $dialog.Filter = 'Realism game test ZIP|BM_Paladin_Realism_GameTest_01*.zip|ZIP archives|*.zip'
    $dialog.FileName = 'BM_Paladin_Realism_GameTest_01.zip'
    try {
        if ($dialog.ShowDialog() -ne 'OK') { Write-Host 'Cancelled. No installation changes.'; return }
        $ZipPath = $dialog.FileName
    } finally { $dialog.Dispose() }
}
$ZipPath = Get-BMFullPath $ZipPath
Assert-BMNoReparsePath $ZipPath
$actualHash = (Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash
$expectedHash = 'a560ed8fa19fb548f9c652022f146deb1adc8d5044940f80f596cabeb202dda4'
Write-Host "Selected archive: $ZipPath"
if ($actualHash -eq '57e94d2a9bae27447dd6790063872a5b2d98d1cf5bbf1a636219df6d5adeb757') {
    throw 'This is the old Blender study. Download BM_Paladin_Realism_GameTest_01.zip from the new reply and select it.'
}
if ($actualHash -ne $expectedHash) {
    throw "Archive checksum mismatch. Expected the new BM_Paladin_Realism_GameTest_01.zip. Selected SHA256: $actualHash"
}
& (Join-Path $PSScriptRoot 'Test-SourceBaseline.ps1')
$builds = Join-Path $work 'builds'
Assert-BMNoReparsePath $builds
Assert-BMSeparatePaths $config.sourceGamePath $builds
Assert-BMSeparatePaths $test $builds
$package = Join-Path $builds ('paladin-realism-game-01-' + [guid]::NewGuid().ToString('N'))
Expand-Archive -LiteralPath $ZipPath -DestinationPath $package
$manifest = Get-Content -LiteralPath (Join-Path $package 'manifest.json') -Raw | ConvertFrom-Json
if ($manifest.build -ne 'cm1-comparison-paladin-realism-game-01') { throw 'Unexpected build identifier.' }
Write-Host 'Installing the Realism Study game adaptation with planar soles.' -ForegroundColor Cyan
Write-Host 'Start a NEW Part I / Chapter 1: Final Examination. Compare movement and combat.'
& (Join-Path $PSScriptRoot 'Switch-ComparisonBuild.ps1') -PackagePath $package -Launch:(-not $NoLaunch)
