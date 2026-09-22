# Functions only. The caller loads Common.ps1 first.
function Save-BMComparisonSnapshot {
    param(
        [Parameter(Mandatory=$true)][object]$Config,
        [Parameter(Mandatory=$true)][string]$Directory
    )
    $workRoot = Get-BMFullPath $Config.workRoot
    $testRoot = Get-BMFullPath $Config.testGamePath
    $reportsRoot = Join-Path $workRoot 'reports'
    $Directory = Get-BMFullPath $Directory
    if (-not (Test-BMContained $Directory $reportsRoot) -or $Directory -eq $reportsRoot) {
        throw 'Comparison diagnostics must be in a new subfolder of workspace/reports.'
    }
    foreach ($path in @($Directory, $testRoot, $workRoot)) {
        Assert-BMNoReparsePath $path
        Assert-BMSeparatePaths $Config.sourceGamePath $path
    }
    Assert-BMSeparatePaths $testRoot $Directory
    if (Test-Path -LiteralPath $Directory) { throw 'Diagnostic snapshot already exists; preserved.' }
    if (@(Get-Process -Name mages -ErrorAction SilentlyContinue).Count) { throw 'Close Battle Mages before capturing diagnostics.' }
    $log = Join-Path $testRoot 'mages.log'
    $receipt = Join-Path $workRoot 'comparison-installed.json'
    foreach ($path in @($log, $receipt)) { Assert-BMNoReparsePath $path }
    [void][IO.Directory]::CreateDirectory($Directory)
    # Allowlist: no profiles, saves, executables or game assets are copied.
    foreach ($path in @($log, $receipt)) {
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            Copy-Item -LiteralPath $path -Destination $Directory
        }
    }
    $files = @(
        foreach ($relative in @('mages.exe', 'mages.log',
                'data/models/units/humans/bmafter.sam',
                'data/models/units/humans/bmafter.dds',
                'data/models/units/humans/bmafter.mrk',
                'data/models/units/humans/bmbefor.sam')) {
            $path = Join-Path $testRoot $relative
            Assert-BMNoReparsePath $path
            if (Test-Path -LiteralPath $path -PathType Leaf) {
                $item = Get-Item -LiteralPath $path
                [ordered]@{ path=$relative; bytes=$item.Length;
                    modifiedUtc=$item.LastWriteTimeUtc.ToString('o');
                    sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash }
            } else { [ordered]@{ path=$relative; missing=$true } }
        }
    )
    Write-BMJson ([ordered]@{ capturedUtc=[DateTime]::UtcNow.ToString('o'); files=$files }) (Join-Path $Directory 'state.json')
}
