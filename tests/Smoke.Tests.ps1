#requires -Version 5.1
param([switch]$DataSubfolder)
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
    $dataRoot = if ($DataSubfolder) { Join-Path $source 'data' } else { $source }
    [void][IO.Directory]::CreateDirectory($dataRoot)
    $packRelative = if ($DataSubfolder) { 'data/Pack3.gdp' } else { 'Pack3.gdp' }
    $configRelative = if ($DataSubfolder) { 'data/datasources.txt' } else { 'datasources.txt' }
    Copy-Item -LiteralPath (Join-Path $projectRoot 'scripts') -Destination $caseRepo -Recurse
    [IO.File]::WriteAllText((Join-Path $dataRoot 'Pack3.gdp'),'Synthetic test data, not a game archive.')
    [IO.File]::WriteAllText((Join-Path $source 'mages.exe'),'Synthetic test data. Never execute.')
    [IO.File]::WriteAllText((Join-Path $dataRoot 'datasources.txt'),'Fixture data source')
    [IO.File]::WriteAllText((Join-Path $dataRoot 'config.cfg'),'fixture=1')
    [void][IO.Directory]::CreateDirectory((Join-Path $dataRoot 'profiles'))
    [IO.File]::WriteAllText((Join-Path $dataRoot 'profiles/private-save.sav'),'SAVE CONTENT MUST NOT APPEAR IN REPORT ZIP')
    . (Join-Path $caseRepo 'scripts/Common.ps1')
    $before = @(Get-BMInventory $source)
    if ($DataSubfolder) {
        Assert-Throws { Assert-BMGameRoot $dataRoot } 'Data folder alone must not count as a full installation.'
        [IO.File]::WriteAllText((Join-Path $source 'Pack3.gdp'),'Ambiguous archive fixture')
        Assert-Throws { Assert-BMGameRoot $source } 'Ambiguous archive locations must be refused.'
        Remove-Item -LiteralPath (Join-Path $source 'Pack3.gdp')
    }

    Assert-Throws { & (Join-Path $caseRepo 'scripts/Initialize-Workspace.ps1') -GamePath $source -WorkRoot (Join-Path $source 'unsafe') } 'Nested source workspace must be refused.'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $source 'unsafe'))) 'Rejected setup created a source directory.'
    Assert-Throws { & (Join-Path $caseRepo 'scripts/Get-GameReport.ps1') -GamePath $source -OutputDirectory $source } 'Report must not write into the source.'

    $config = & (Join-Path $caseRepo 'scripts/Initialize-Workspace.ps1') -GamePath $source -WorkRoot $work
    Assert-True ($config.modInstalled -eq $false) 'Setup must not claim a mod is installed.'
    Assert-True ($config.loaderStatus -eq 'unverified') 'Setup must not claim a verified loader.'
    Assert-True ($config.sourceDataPath -eq $dataRoot) 'Wrong source data directory.'
    Assert-True (Test-Path -LiteralPath (Join-Path $config.testGamePath 'mages.exe')) 'Executable omitted from test copy.'
    Assert-True (Test-Path -LiteralPath (Join-Path $config.testGamePath $packRelative)) 'Archive layout was not preserved.'
    Assert-True (@(Compare-BMInventory $before @(Get-BMInventory $source)).Count -eq 0) 'Original files changed during setup.'
    Assert-True (@(Compare-BMInventory $before @(Get-BMInventory $config.testGamePath)).Count -eq 0) 'Test copy is not byte-identical.'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $work 'INITIALIZATION_INCOMPLETE.txt'))) 'Successful copy still has incomplete marker.'
    $zip = [IO.Compression.ZipFile]::OpenRead($config.lastDiagnosticZip)
    try {
        $names = @($zip.Entries | ForEach-Object { $_.FullName.Replace('\','/') })
        Assert-True ($names -contains 'inventory.json') 'Inventory missing from ZIP.'
        Assert-True ($names -contains $configRelative) 'Datasource config missing or flattened.'
        $reader = New-Object IO.StreamReader($zip.GetEntry('inventory.json').Open())
        try { $report = $reader.ReadToEnd() | ConvertFrom-Json } finally { $reader.Dispose() }
        Assert-True (@($report.archives).Count -eq 1) 'GDP header inventory missed the archive.'
        Assert-True ($report.archives[0].path -eq $packRelative) 'Wrong GDP relative path.'
        Assert-True (@($names | Where-Object { $_ -match '\.(exe|gdp|sav|dds|sam)$' }).Count -eq 0) 'Diagnostics leaked game binary/save files.'
    } finally { $zip.Dispose() }
    Assert-Throws { & (Join-Path $caseRepo 'scripts/Initialize-Workspace.ps1') -GamePath $source -WorkRoot $work } 'Second setup should refuse to overwrite.'
    & (Join-Path $caseRepo 'scripts/Test-SourceBaseline.ps1')

    & (Join-Path $caseRepo 'scripts/Test-LooseTexture.ps1') -Mode Prepare
    $probe = Join-Path $config.testGamePath 'data/if/ico/Mainmenu/Symbol.tga'
    Assert-True ((Get-Item -LiteralPath $probe).Length -eq 524306) 'Wrong probe size.'
    Assert-Throws { & (Join-Path $caseRepo 'scripts/Test-LooseTexture.ps1') -Mode Prepare } 'Existing probe must not be overwritten.'
    & (Join-Path $caseRepo 'scripts/Test-LooseTexture.ps1') -Mode Remove
    Assert-True (-not (Test-Path -LiteralPath $probe)) 'Probe cleanup failed.'
    Assert-True (@(Compare-BMInventory $before @(Get-BMInventory $source)).Count -eq 0) 'Probe changed original source.'

    & (Join-Path $caseRepo 'scripts/Test-LooseTexture.ps1') -Mode Prepare -Texture Paladin
    $ddsPath = Join-Path $config.testGamePath 'data/models/units/humans/paladin.dds'
    $dds = [IO.File]::ReadAllBytes($ddsPath)
    Assert-True ($dds.Length -eq 349680) 'Wrong DDS mip chain size.'
    Assert-True ([Text.Encoding]::ASCII.GetString($dds,84,4) -eq 'DXT5') 'Wrong DDS format.'
    Assert-True ([BitConverter]::ToUInt32($dds,28) -eq 10) 'Missing DDS mip levels.'
    Assert-Throws { & (Join-Path $caseRepo 'scripts/Test-LooseTexture.ps1') -Mode Remove } 'Wrong texture mode must not delete the probe.'
    & (Join-Path $caseRepo 'scripts/Test-LooseTexture.ps1') -Mode Remove -Texture Paladin
    Assert-True (-not (Test-Path -LiteralPath $ddsPath)) 'DDS cleanup failed.'

    $package=Join-Path $sandbox 'comparison-package'
    [void][IO.Directory]::CreateDirectory((Join-Path $package 'payload/data'))
    $fixture=Join-Path $package 'payload/data/comparison-fixture.xml'
    [IO.File]::WriteAllText($fixture,'<fixture />')
    Write-BMJson ([ordered]@{build='fixture';files=@([ordered]@{path='data/comparison-fixture.xml';sha256=(Get-FileHash -LiteralPath $fixture -Algorithm SHA256).Hash})}) (Join-Path $package 'manifest.json')
    $installer=Join-Path $caseRepo 'scripts/Use-ComparisonBuild.ps1'
    & $installer -PackagePath $package
    $installed=Join-Path $config.testGamePath 'data/comparison-fixture.xml'
    Assert-True (Test-Path -LiteralPath $installed) 'Comparison not installed.'
    Assert-Throws { & $installer -PackagePath $package } 'Repeated install must refuse.'
    [IO.File]::WriteAllText($installed,'changed')
    Assert-Throws { & $installer -PackagePath $package -Mode Remove } 'Removal must preserve edited files.'
    [IO.File]::Copy($fixture,$installed,$true)
    & $installer -PackagePath $package -Mode Remove
    Assert-True (-not (Test-Path -LiteralPath $installed)) 'Comparison removal failed.'
    Assert-True (@(Compare-BMInventory $before @(Get-BMInventory $source)).Count -eq 0) 'Comparison changed source.'

    # Editing the test copy must not change the source: detects accidental hardlinks.
    [IO.File]::WriteAllText((Join-Path $config.testGamePath $packRelative),'MODIFIED TEST COPY')
    Assert-True (@(Compare-BMInventory $before @(Get-BMInventory $source)).Count -eq 0) 'Test copy shares mutable file data with original.'
    [IO.File]::WriteAllText((Join-Path $dataRoot 'Pack3.gdp'),'CHANGED SOURCE FIXTURE')
    Assert-Throws { & (Join-Path $caseRepo 'scripts/Test-SourceBaseline.ps1') } 'Baseline check must detect a changed source.'

    if ($env:OS -eq 'Windows_NT') {
        $junction = Join-Path $sandbox 'junction-to-source'
        # Windows PowerShell 5.1 treats brackets in -Target as wildcards.
        # Keep bracketed source coverage above and use a literal-safe link fixture here.
        $junctionTarget = Join-Path $sandbox 'junction-target'
        [void][IO.Directory]::CreateDirectory($junctionTarget)
        New-Item -ItemType Junction -Path $junction -Target $junctionTarget | Out-Null
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
