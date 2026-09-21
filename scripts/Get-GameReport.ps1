#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$GamePath = 'C:\Program Files (x86)\Steam\steamapps\common\Battle Mages',
    [string]$OutputDirectory = (Join-Path $env:USERPROFILE 'BattleMages-RemasterWorkspace\reports')
)
. (Join-Path $PSScriptRoot 'Common.ps1')
$GamePath = Get-BMFullPath $GamePath
$OutputDirectory = Get-BMFullPath $OutputDirectory
$layout = Get-BMGameLayout $GamePath
Assert-BMSeparatePaths $GamePath $OutputDirectory
Assert-BMNoReparsePath $OutputDirectory
$inventory = @(Get-BMInventory $GamePath)
$name = 'BM-Diagnostics-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$reportPath = Join-Path $OutputDirectory $name
[void][IO.Directory]::CreateDirectory($reportPath)

$packs = @()
foreach ($file in @(Get-ChildItem -LiteralPath $layout.dataRoot -Filter '*.gdp' -File)) {
    $stream = [IO.File]::OpenRead($file.FullName)
    try {
        $buffer = New-Object byte[] 64
        $count = $stream.Read($buffer,0,$buffer.Length)
        $hex = if ($count -gt 0) { [BitConverter]::ToString($buffer,0,$count).Replace('-','') } else { '' }
    } finally { $stream.Dispose() }
    $packs += [pscustomobject]@{name=$file.Name; path=(Get-BMRelativePath $GamePath $file.FullName); bytes=$file.Length; first64BytesHex=$hex}
}
$executables = @()
foreach ($file in @(Get-ChildItem -LiteralPath $GamePath -Filter '*.exe' -File)) {
    $executables += [pscustomobject]@{name=$file.Name; fileVersion=$file.VersionInfo.FileVersion; productVersion=$file.VersionInfo.ProductVersion}
}
$report = [ordered]@{
    schemaVersion=1; createdUtc=[DateTime]::UtcNow.ToString('o')
    edition='steam-candidate'; sourcePath=$GamePath
    dataRelativePath=$layout.dataRelativePath
    powershell=$PSVersionTable.PSVersion.ToString()
    files=$inventory; archives=$packs; executables=$executables
    note='Read-only inventory. No executables or game archives included; no game was launched.'
}
Write-BMJson $report (Join-Path $reportPath 'inventory.json')
foreach ($directory in @(@($GamePath,$layout.dataRoot) | Select-Object -Unique)) {
    foreach ($filename in @('datasources','datasources.txt','config.cfg')) {
        $source = Join-Path $directory $filename
        if (Test-Path -LiteralPath $source -PathType Leaf) {
            Assert-BMNoReparsePath $source
            if ((Get-Item -LiteralPath $source).Length -gt 1MB) { throw "Unexpectedly large config: $filename" }
            $target = Join-Path $reportPath (Get-BMRelativePath $GamePath $source)
            [void][IO.Directory]::CreateDirectory((Split-Path $target -Parent))
            Copy-Item -LiteralPath $source -Destination $target
        }
    }
}
$zipPath = $reportPath + '.zip'
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::CreateFromDirectory($reportPath,$zipPath)
Write-Host "Diagnostic report: $zipPath" -ForegroundColor Green
return $zipPath
