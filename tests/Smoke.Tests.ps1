#requires -Version 5.1
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$projectRoot = Split-Path $PSScriptRoot -Parent
$sandbox = Join-Path ([IO.Path]::GetTempPath()) ('bm-mod-smoke-' + [guid]::NewGuid().ToString('N'))
$caseRepo = Join-Path $sandbox 'repo'
$source = Join-Path $sandbox 'source game [fixture]'
$work = Join-Path $sandbox 'workspace'
$junction = $null
function Assert-True { param([bool]$Value,[string]$Message) if (-not $Value) { throw $Message } }
function Assert-Throws {
    param([scriptblock]$Action,[string]$Message)
    $threw = $false
    try { & $Action | Out-Null } catch { $threw = $true }
    Assert-True $threw $Message
}
try {
    [void][IO.Directory]::CreateDirectory($caseRepo)
    [void][IO.Directory]::CreateDirectory($source)
    Copy-Item -LiteralPath (Join-Path $projectRoot 'scripts') -Destination $caseRepo -Recurse
    [IO.File]::WriteAllText((Join-Path $source 'Pack3.gdp'),'Synthetic test data, not a game archive.')
    [IO.File]::WriteAllText((Join-Path $source 'testgame.exe'),'Synthetic test data. Never execute.')
    [IO.File]::WriteAllText((Join-Path $source 'datasources.txt'),'Fixture data source')
    [IO.File]::WriteAllText((Join-Path $source 'config.cfg'),'fixture=1')
    [void][IO.Directory]::CreateDirectory((Join-Path $source 'profiles'))
    [IO.File]::WriteAllText((Join-Path $source 'profiles/private-save.sav'),'SAVE CONTENT MUST NOT APPEAR IN REPORT ZIP')
    . (Join-Path $caseRepo 'scripts/Common.ps1')
    $before = @(Get-BMInventory $source)

    Assert-Throws { & (Join-Path $caseRepo 'scripts/Initialize-Workspace.ps1') -GamePath $source -WorkRoot (Join-Path $source 'unsafe') } 'Nested source workspace must be refused.'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $source 'unsafe'))) 'Rejected setup created a source directory.'
    Assert-Throws { & (Join-Path $caseRepo 'scripts/Get-GameReport.ps1') -GamePath $source -OutputDirectory $source } 'Report must not write into the source.'

    $config = & (Join-Path $caseRepo 'scripts/Initialize-Workspace.ps1') -GamePath $source -WorkRoot $work
    Assert-True ($config.modInstalled -eq $false) 'Setup must not claim a mod is installed.'
    Assert-True ($config.loaderStatus -eq 'unverified') 'Setup must not claim a verified loader.'
    Assert-True (@(Compare-BMInventory $before @(Get-BMInventory $source)).Count -eq 0) 'Original files changed during setup.'
    Assert-True (@(Compare-BMInventory $before @(Get-BMInventory $config.testGamePath)).Count -eq 0) 'Test copy is not byte-identical.'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $work 'INITIALIZATION_INCOMPLETE.txt'))) 'Successful copy still has incomplete marker.'
    $zip = [IO.Compression.ZipFile]::OpenRead($config.lastDiagnosticZip)
    try {
        $names = @($zip.Entries | ForEach-Object { $_.FullName })
        Assert-True ($names -contains 'inventory.json') 'Inventory missing from ZIP.'
        Assert-True ($names -contains 'datasources.txt') 'Datasource config missing.'
        Assert-True (@($names | Where-Object { $_ -match '\.(exe|gdp|sav|dds|sam)$' }).Count -eq 0) 'Diagnostics leaked game binary/save files.'
    } finally { $zip.Dispose() }
    Assert-Throws { & (Join-Path $caseRepo 'scripts/Initialize-Workspace.ps1') -GamePath $source -WorkRoot $work } 'Second setup should refuse to overwrite.'
    & (Join-Path $caseRepo 'scripts/Test-SourceBaseline.ps1')

    # Editing the test copy must not change the source: detects accidental hardlinks.
    [IO.File]::WriteAllText((Join-Path $config.testGamePath 'Pack3.gdp'),'MODIFIED TEST COPY')
    Assert-True (@(Compare-BMInventory $before @(Get-BMInventory $source)).Count -eq 0) 'Test copy shares mutable file data with original.'
    [IO.File]::WriteAllText((Join-Path $source 'Pack3.gdp'),'CHANGED SOURCE FIXTURE')
    Assert-Throws { & (Join-Path $caseRepo 'scripts/Test-SourceBaseline.ps1') } 'Baseline check must detect a changed source.'

    if ($env:OS -eq 'Windows_NT') {
        $junction = Join-Path $sandbox 'junction-to-source'
        New-Item -ItemType Junction -Path $junction -Target $source | Out-Null
        Assert-Throws { Get-BMSafeFiles $junction } 'Junction root must be refused.'
        Assert-Throws { Assert-BMNoReparsePath (Join-Path $junction 'nonexistent') } 'Junction ancestor must be refused.'
        [IO.Directory]::Delete($junction)
        $junction = $null
    }
    Write-Host 'PASS: copy isolation, baseline checks, report contents, path guards and repeat-run refusal.' -ForegroundColor Green
} finally {
    if ($junction -and (Test-Path -LiteralPath $junction)) { [IO.Directory]::Delete($junction) }
    if (Test-Path -LiteralPath $sandbox) { Remove-Item -LiteralPath $sandbox -Recurse -Force }
}

