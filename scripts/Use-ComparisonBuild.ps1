#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PackagePath,
    [ValidateSet('Install','Remove')][string]$Mode='Install',
    [switch]$Launch
)
. (Join-Path $PSScriptRoot 'Common.ps1')
$repo=Get-BMFullPath (Split-Path $PSScriptRoot -Parent)
$config=Get-Content -LiteralPath (Join-Path $repo 'config/local.json') -Raw | ConvertFrom-Json
$test=Get-BMFullPath $config.testGamePath
$work=Get-BMFullPath $config.workRoot
$PackagePath=Get-BMFullPath $PackagePath
foreach ($path in @($test,$work,$PackagePath)) { Assert-BMNoReparsePath $path; Assert-BMSeparatePaths $config.sourceGamePath $path }
Assert-BMSeparatePaths $test $PackagePath
if (-not (Test-BMContained $test $work) -or $test -eq $work) { throw 'Invalid test workspace.' }
Assert-BMGameRoot $test
if (@(Get-Process -Name mages -ErrorAction SilentlyContinue).Count) { throw 'Close Battle Mages first.' }
$receipt=Join-Path $work 'comparison-installed.json'
Assert-BMNoReparsePath $receipt
$manifestPath=Join-Path $PackagePath 'manifest.json'
Assert-BMNoReparsePath $manifestPath
$manifest=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$manifestHash=(Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash
$seen=@{}
foreach ($entry in $manifest.files) {
    if ($entry.path -notmatch '^data/[a-zA-Z0-9_./-]+$' -or $entry.path -match '(^|/)\.\.(/|$)' -or $seen.ContainsKey($entry.path)) { throw 'Invalid or repeated package path.' }
    $seen[$entry.path]=$true
    $target=Join-Path $test $entry.path
    Assert-BMNoReparsePath $target
    if (-not (Test-BMContained $target $test)) { throw 'Package escapes test directory.' }
}
function Remove-Comparison {
    if (-not (Test-Path -LiteralPath $receipt)) { throw 'No installed comparison receipt.' }
    $r=Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json
    if ($r.manifestHash -ne $manifestHash -or $r.testPath -ne $test) { throw 'Use the same package that was installed.' }
    # Check all entries before deleting anything; preserve later user edits.
    foreach ($entry in $manifest.files) {
        $target=Join-Path $test $entry.path
        Assert-BMNoReparsePath $target
        if ((Test-Path -LiteralPath $target) -and (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $entry.sha256) { throw "Modified file preserved: $target" }
    }
    foreach ($entry in $manifest.files) {
        $target=Join-Path $test $entry.path
        if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target }
    }
    Remove-Item -LiteralPath $receipt
    Write-Host 'Comparison removed; archived mission files are active again.' -ForegroundColor Green
}
if ($Mode -eq 'Remove') { Remove-Comparison; & (Join-Path $PSScriptRoot 'Test-SourceBaseline.ps1'); return }
& (Join-Path $PSScriptRoot 'Test-SourceBaseline.ps1')
if ($manifest.PSObject.Properties.Name -contains 'expectedPack3Sha256') {
    $pack=Join-Path $test 'data/Pack3.gdp'
    if ((Get-FileHash -LiteralPath $pack -Algorithm SHA256).Hash -ne $manifest.expectedPack3Sha256) { throw 'This package does not match the test installation Pack3 archive.' }
}
if (Test-Path -LiteralPath $receipt) { throw 'Comparison already installed. Remove it with its original package before installing another.' }
if (Test-Path -LiteralPath (Join-Path $work 'loose-texture-probe.json')) { throw 'Remove the previous texture probe first.' }
foreach ($entry in $manifest.files) {
    $source=Join-Path (Join-Path $PackagePath 'payload') $entry.path
    Assert-BMNoReparsePath $source
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $entry.sha256) { throw "Package hash mismatch: $source" }
    $target=Join-Path $test $entry.path
    if (Test-Path -LiteralPath $target) { throw "Existing loose file preserved: $target" }
}
# The source files remain in untouched GDP archives. This installer creates only
# new loose files and records every path; no existing target needs overwriting.
Write-BMJson ([ordered]@{manifestHash=$manifestHash;testPath=$test;build=$manifest.build;status='installing'}) $receipt
try {
    foreach ($entry in $manifest.files) {
        $source=Join-Path (Join-Path $PackagePath 'payload') $entry.path
        $target=Join-Path $test $entry.path
        [void][IO.Directory]::CreateDirectory((Split-Path $target -Parent))
        [IO.File]::Copy($source,$target,$false)
        if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $entry.sha256) { throw 'Copy hash mismatch.' }
    }
    Write-BMJson ([ordered]@{manifestHash=$manifestHash;testPath=$test;build=$manifest.build;status='installed'}) $receipt
} catch { Write-Warning 'Installation incomplete. Use -Mode Remove with this same package to recover.'; throw }
Write-Host 'Comparison installed. Start a NEW Chapter 1 / Final Examination, not a saved game.' -ForegroundColor Cyan
if ($Launch) {
    $exe=Join-Path $test 'mages.exe'
    Assert-BMNoReparsePath $exe
    try { $process=Start-Process -FilePath $exe -WorkingDirectory $test -PassThru -Wait; Write-Host "Exit code: $($process.ExitCode)" }
    finally { & (Join-Path $PSScriptRoot 'Test-SourceBaseline.ps1') }
}
