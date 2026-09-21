#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PackagePath,
    [string]$PreviousPackagePath,
    [switch]$Launch
)
. (Join-Path $PSScriptRoot 'Common.ps1')
$repo = Get-BMFullPath (Split-Path $PSScriptRoot -Parent)
$config = Get-Content -LiteralPath (Join-Path $repo 'config/local.json') -Raw | ConvertFrom-Json
$work = Get-BMFullPath $config.workRoot
$test = Get-BMFullPath $config.testGamePath
$PackagePath = Get-BMFullPath $PackagePath
foreach ($path in @($work,$test,$PackagePath)) {
    Assert-BMNoReparsePath $path
    Assert-BMSeparatePaths $config.sourceGamePath $path
}
Assert-BMSeparatePaths $test $PackagePath
if (-not (Test-BMContained $test $work) -or $test -eq $work) { throw 'Invalid test workspace.' }
Assert-BMGameRoot $test
if (@(Get-Process -Name mages -ErrorAction SilentlyContinue).Count) { throw 'Close Battle Mages first.' }
$receipt = Join-Path $work 'comparison-installed.json'
Assert-BMNoReparsePath $receipt
$installer = Join-Path $PSScriptRoot 'Use-ComparisonBuild.ps1'

function Read-CheckedPackage {
    param([string]$Directory)
    $Directory = Get-BMFullPath $Directory
    Assert-BMNoReparsePath $Directory
    Assert-BMSeparatePaths $config.sourceGamePath $Directory
    Assert-BMSeparatePaths $test $Directory
    $mp = Join-Path $Directory 'manifest.json'
    Assert-BMNoReparsePath $mp
    $m = Get-Content -LiteralPath $mp -Raw | ConvertFrom-Json
    if (@($m.files).Count -eq 0) { throw 'Empty comparison manifest.' }
    $seen = @{}
    foreach ($entry in $m.files) {
        if ($entry.path -notmatch '^data/[a-zA-Z0-9_./-]+$' -or $entry.path -match '(^|/)\.\.(/|$)' -or $seen.ContainsKey($entry.path)) { throw 'Invalid or repeated package path.' }
        if ($entry.sha256 -notmatch '^[a-fA-F0-9]{64}$') { throw 'Invalid payload checksum.' }
        $seen[$entry.path] = $true
        $source = Join-Path (Join-Path $Directory 'payload') $entry.path
        Assert-BMNoReparsePath $source
        if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $entry.sha256) { throw "Package checksum mismatch: $source" }
    }
    if ($m.PSObject.Properties.Name -contains 'expectedPack3Sha256') {
        $pack = Join-Path $test 'data/Pack3.gdp'
        Assert-BMNoReparsePath $pack
        if ((Get-FileHash -LiteralPath $pack -Algorithm SHA256).Hash -ne $m.expectedPack3Sha256) { throw 'Package does not match the test Pack3 archive.' }
    }
    return [pscustomobject]@{ directory=$Directory; manifest=$m; hash=(Get-FileHash -LiteralPath $mp -Algorithm SHA256).Hash }
}

# Check the complete incoming build before removing a working build.
$new = Read-CheckedPackage $PackagePath
& (Join-Path $PSScriptRoot 'Test-SourceBaseline.ps1')
if (Test-Path -LiteralPath (Join-Path $work 'loose-texture-probe.json')) { throw 'Remove the texture probe before switching builds.' }
$old = $null
$owned = @{}
if (Test-Path -LiteralPath $receipt) {
    $r = Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json
    if ($r.testPath -ne $test) { throw 'Comparison receipt belongs to a different test copy.' }
    if (-not $PreviousPackagePath) {
        $builds = Join-Path $work 'builds'
        foreach ($file in @(Get-BMSafeFiles $builds)) {
            if ($file.Name -eq 'manifest.json' -and (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -eq $r.manifestHash) {
                $PreviousPackagePath = $file.DirectoryName
                break
            }
        }
    }
    if (-not $PreviousPackagePath) { throw 'Previous package not found in workspace/builds. Supply -PreviousPackagePath; no installed files were removed.' }
    $old = Read-CheckedPackage $PreviousPackagePath
    if ($old.hash -ne $r.manifestHash) { throw 'Previous package does not match the installed receipt.' }
    foreach ($entry in $old.manifest.files) {
        $target = Join-Path $test $entry.path
        Assert-BMNoReparsePath $target
        if ((Test-Path -LiteralPath $target) -and (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $entry.sha256) { throw "Modified installed file preserved: $target" }
        $owned[$entry.path] = $true
    }
}
foreach ($entry in $new.manifest.files) {
    $target = Join-Path $test $entry.path
    Assert-BMNoReparsePath $target
    if ((Test-Path -LiteralPath $target) -and -not $owned.ContainsKey($entry.path)) { throw "Unmanaged loose file preserved: $target" }
}
# Packages remain in builds as exact, checksum-verified rollback inputs.
# The existing installer records a partial receipt if a copy fails. It never
# overwrites existing loose files; recover using Remove with that exact package.
if ($old) { & $installer -PackagePath $old.directory -Mode Remove }
try {
    & $installer -PackagePath $new.directory -Mode Install
} catch {
    Write-Warning "Switch incomplete. Keep both package folders. Recover with Use-ComparisonBuild.ps1 -PackagePath '$($new.directory)' -Mode Remove if a new receipt exists, then reinstall the previous package."
    throw
}
if ($Launch) {
    $exe = Join-Path $test 'mages.exe'
    Assert-BMNoReparsePath $exe
    try {
        $process = Start-Process -FilePath $exe -WorkingDirectory $test -PassThru -Wait
        Write-Host "Process exit code: $($process.ExitCode) (not a standalone visual pass/fail result)."
    } finally { & (Join-Path $PSScriptRoot 'Test-SourceBaseline.ps1') }
}
