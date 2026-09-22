#requires -Version 5.1
[CmdletBinding()]
param([string]$ZipPath, [switch]$NoLaunch)
. (Join-Path $PSScriptRoot 'Common.ps1')
. (Join-Path $PSScriptRoot 'ComparisonDiagnostics.ps1')
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
if (@(Get-Process -Name mages -ErrorAction SilentlyContinue).Count) { throw 'Close Battle Mages and its error dialogs first.' }
if (-not $ZipPath) {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Title = 'Select BM_Paladin_Realism_GameTest_02.zip (reduced geometry)'
    $dialog.Filter = 'Realism GameTest 02|BM_Paladin_Realism_GameTest_02*.zip|ZIP archives|*.zip'
    $dialog.FileName = 'BM_Paladin_Realism_GameTest_02.zip'
    try {
        if ($dialog.ShowDialog() -ne 'OK') { Write-Host 'Cancelled. No installation changes.'; return }
        $ZipPath = $dialog.FileName
    } finally { $dialog.Dispose() }
}
$ZipPath = Get-BMFullPath $ZipPath
Assert-BMNoReparsePath $ZipPath
$actualHash = (Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash
$expectedHash = 'b2d9daabae5554cd1417caba22731317a6506f6b3d48cd08a35a16a50a54cc76'
if ($actualHash -ne $expectedHash) { throw "Select the NEW BM_Paladin_Realism_GameTest_02.zip. Selected SHA256: $actualHash" }
& (Join-Path $PSScriptRoot 'Test-SourceBaseline.ps1')
$run = Join-Path (Join-Path $work 'reports') ('realism-02-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N'))
Save-BMComparisonSnapshot -Config $config -Directory (Join-Path $run 'before')
Write-Host "Previous crash log and installed-build information saved: $run" -ForegroundColor Cyan
$phase = 'unpack'
$exitCode = $null
$failure = $null
try {
    $builds = Join-Path $work 'builds'
    Assert-BMNoReparsePath $builds
    Assert-BMSeparatePaths $config.sourceGamePath $builds
    Assert-BMSeparatePaths $test $builds
    $package = Join-Path $builds ('paladin-realism-game-02-' + [guid]::NewGuid().ToString('N'))
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $package
    $manifest = Get-Content -LiteralPath (Join-Path $package 'manifest.json') -Raw | ConvertFrom-Json
    if ($manifest.build -ne 'cm1-comparison-paladin-realism-game-02') { throw 'Unexpected build identifier.' }
    $phase = 'install'
    & (Join-Path $PSScriptRoot 'Switch-ComparisonBuild.ps1') -PackagePath $package
    if (-not $NoLaunch) {
        $exe = Join-Path $test 'mages.exe'
        Assert-BMNoReparsePath $exe
        $phase = 'launch'
        Write-Host 'Start a NEW Part I / Chapter 1: Final Examination. Compare Before / After.' -ForegroundColor Cyan
        Write-Host 'If an assertion appears, choose Abort. Retry opens the debugger; it does not retry the model.'
        $process = Start-Process -FilePath $exe -WorkingDirectory $test -PassThru -Wait
        $exitCode = $process.ExitCode
        $phase = 'game-exited'
        Write-Host "Process exit code: $exitCode (not a standalone visual pass/fail result)."
    } else { $phase = 'installed-without-launch' }
} catch {
    $failure = $_.ToString()
    throw
} finally {
    # Preserve the original failure evidence before any launch can replace it.
    Save-BMComparisonSnapshot -Config $config -Directory (Join-Path $run 'after')
    Write-BMJson ([ordered]@{ build='cm1-comparison-paladin-realism-game-02'; phase=$phase;
        processExitCode=$exitCode; scriptError=$failure;
        runtimeVerdict='Requires user observation and log review; exit code alone is not a verdict.' }) (Join-Path $run 'result.json')
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::CreateFromDirectory($run, ($run + '.zip'))
    Write-Host "Diagnostics ZIP (upload here if the test fails): $run.zip" -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot 'Test-SourceBaseline.ps1')
}
