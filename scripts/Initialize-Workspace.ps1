#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$GamePath = 'C:\Program Files (x86)\Steam\steamapps\common\Battle Mages',
    [string]$WorkRoot = (Join-Path $env:USERPROFILE 'BattleMages-RemasterWorkspace')
)
. (Join-Path $PSScriptRoot 'Common.ps1')
$repo = Get-BMFullPath (Split-Path $PSScriptRoot -Parent)
$GamePath = Get-BMFullPath $GamePath
$WorkRoot = Get-BMFullPath $WorkRoot
$configPath = Join-Path $repo 'config\local.json'
$layout = Get-BMGameLayout $GamePath
Assert-BMSeparatePaths $GamePath $repo
Assert-BMSeparatePaths $GamePath $WorkRoot
Assert-BMSeparatePaths $repo $WorkRoot
Assert-BMNoReparsePath $WorkRoot
Assert-BMNoReparsePath $configPath
if (Test-Path -LiteralPath $configPath) { throw 'Already configured. Use Get-GameReport.ps1 or Test-SourceBaseline.ps1; setup will not overwrite local.json.' }
if (Test-Path -LiteralPath $WorkRoot) { throw 'WorkRoot already exists. Select a new, empty workspace path. Existing files will not be overwritten.' }
$inventory = @(Get-BMInventory $GamePath)
$totalBytes = ($inventory | Measure-Object -Property bytes -Sum).Sum
Write-Host ('Copying {0} files ({1:N1} MB). Original installation stays read-only.' -f $inventory.Count,($totalBytes/1MB))
$testPath = Join-Path $WorkRoot 'game-test'
foreach ($dir in @($WorkRoot,$testPath,(Join-Path $WorkRoot 'reports'),(Join-Path $WorkRoot 'backups'),(Join-Path $WorkRoot 'builds'),(Join-Path $WorkRoot 'assets'))) {
    [void][IO.Directory]::CreateDirectory($dir)
}
$incomplete = Join-Path $WorkRoot 'INITIALIZATION_INCOMPLETE.txt'
[IO.File]::WriteAllText($incomplete,'Copy or verification has not completed. Do not use this test installation.')
# Copy each regular file, never links. Create directories explicitly, including empty ones.
foreach ($dir in @(Get-ChildItem -LiteralPath $GamePath -Directory -Recurse -Force)) {
    $relative = Get-BMRelativePath $GamePath $dir.FullName
    [void][IO.Directory]::CreateDirectory((Join-Path $testPath $relative))
}
foreach ($item in $inventory) {
    $source = Join-Path $GamePath $item.path
    $target = Join-Path $testPath $item.path
    Assert-BMNoReparsePath $source
    [void][IO.Directory]::CreateDirectory((Split-Path $target -Parent))
    [IO.File]::Copy($source,$target,$false)
}
$copied = @(Get-BMInventory $testPath)
$copyDiff = @(Compare-BMInventory $inventory $copied)
if ($copyDiff.Count -gt 0) { throw ('Copy verification failed: ' + ($copyDiff -join '; ')) }
$currentSource = @(Get-BMInventory $GamePath)
$sourceDiff = @(Compare-BMInventory $inventory $currentSource)
if ($sourceDiff.Count -gt 0) { throw ('Source changed during setup. Close Steam updates/game and use a new workspace: ' + ($sourceDiff -join '; ')) }
$baselinePath = Join-Path $WorkRoot 'source-baseline.json'
Write-BMJson ([ordered]@{schemaVersion=1;createdUtc=[DateTime]::UtcNow.ToString('o');sourcePath=$GamePath;files=$inventory}) $baselinePath
$reportZip = & (Join-Path $PSScriptRoot 'Get-GameReport.ps1') -GamePath $GamePath -OutputDirectory (Join-Path $WorkRoot 'reports')
$config = [ordered]@{
    schemaVersion=1; sourceGamePath=$GamePath; workRoot=$WorkRoot; testGamePath=$testPath
    sourceDataPath=$layout.dataRoot; dataRelativePath=$layout.dataRelativePath
    testDataPath=(Join-Path $testPath $layout.dataRelativePath)
    sourceBaseline=$baselinePath; lastDiagnosticZip=$reportZip
    loaderStatus='unverified'; launchStatus='not-tested'; modInstalled=$false
}
[void][IO.Directory]::CreateDirectory((Split-Path $configPath -Parent))
Write-BMJson $config $configPath
Remove-Item -LiteralPath $incomplete
Write-Host "Workspace ready: $WorkRoot" -ForegroundColor Green
Write-Host "Test installation: $testPath"
Write-Host "Upload this ZIP to Drive / 04_Diagnostics: $reportZip" -ForegroundColor Cyan
Write-Host 'No mod was applied and the game was not launched.'
return [pscustomobject]$config
