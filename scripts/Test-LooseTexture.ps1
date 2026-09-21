#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet('Run','Prepare','Remove')][string]$Mode = 'Run',
    [ValidateSet('Menu','Paladin')][string]$Texture = 'Menu'
)
. (Join-Path $PSScriptRoot 'Common.ps1')
$repo = Get-BMFullPath (Split-Path $PSScriptRoot -Parent)
$configPath = Join-Path $repo 'config/local.json'
Assert-BMNoReparsePath $configPath
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$test = Get-BMFullPath $config.testGamePath
$work = Get-BMFullPath $config.workRoot
Assert-BMSeparatePaths $config.sourceGamePath $test
Assert-BMSeparatePaths $config.sourceGamePath $work
Assert-BMSeparatePaths $repo $work
if (-not (Test-BMContained $test $work) -or $test -eq $work) { throw 'Test copy must be inside the workspace.' }
Assert-BMNoReparsePath $test
Assert-BMNoReparsePath $work
Assert-BMGameRoot $test
$relative = if ($Texture -eq 'Menu') { 'data/if/ico/Mainmenu/Symbol.tga' } else { 'data/models/units/humans/paladin.dds' }
$target = Join-Path $test $relative
$marker = Join-Path $work 'loose-texture-probe.json'
Assert-BMNoReparsePath $target
Assert-BMNoReparsePath $marker
if (@(Get-Process -Name mages -ErrorAction SilentlyContinue).Count -gt 0) { throw 'Close Battle Mages before running this script.' }

if ($Texture -eq 'Menu') {
# Synthetic diagnostic fixture, not a replacement art asset. Same size/type/origin
# as extracted Pack3 data/if/ico/mainmenu/symbol.tga (512x256, type 2, BGRA).
$bytes = New-Object byte[] (18 + 512*256*4)
$bytes[2]=2; $bytes[13]=2; $bytes[15]=1; $bytes[16]=32; $bytes[17]=32
for ($y=0; $y -lt 256; $y++) {
    for ($x=0; $x -lt 512; $x++) {
        $i=18+4*($y*512+$x)
        $pink=(([int][Math]::Floor($x/32)+[int][Math]::Floor($y/32)) % 2 -eq 0)
        if ($pink) { $bytes[$i]=255; $bytes[$i+2]=255 } else { $bytes[$i+1]=255 }
        $bytes[$i+3]=255
    }
}

} else {
    # Synthetic DXT5 fixture: original paladin dimensions and complete mip chain.
    $memory = New-Object IO.MemoryStream
    $writer = New-Object IO.BinaryWriter($memory)
    try {
        $writer.Write([Text.Encoding]::ASCII.GetBytes('DDS '))
        $header = New-Object uint32[] 31
        $header[0]=124; $header[1]=659463; $header[2]=512; $header[3]=512
        $header[4]=262144; $header[6]=10; $header[18]=32; $header[19]=4
        $header[20]=894720068; $header[26]=4198408
        foreach ($word in $header) { $writer.Write([uint32]$word) }
        for ($level=0; $level -lt 10; $level++) {
            $size=[int][Math]::Max(1,512/[Math]::Pow(2,$level))
            $blocks=[int][Math]::Ceiling($size/4)
            for ($y=0; $y -lt $blocks; $y++) {
                for ($x=0; $x -lt $blocks; $x++) {
                    # BC3 alpha index 0 everywhere; BC1 color index 0 everywhere.
                    $pink=(([int][Math]::Floor($x*4*8/$size)+[int][Math]::Floor($y*4*8/$size)) % 2 -eq 0)
                    $writer.Write([byte]255); $writer.Write([byte]0)
                    $writer.Write((New-Object byte[] 6))
                    $color=if ($pink) { 63519 } else { 2016 }
                    $writer.Write([uint16]$color); $writer.Write([uint16]0)
                    $writer.Write([uint32]0)
                }
            }
        }
        $bytes=$memory.ToArray()
    } finally { $writer.Dispose(); $memory.Dispose() }
}
$hasher=[Security.Cryptography.SHA256]::Create()
try { $expectedHash=[BitConverter]::ToString($hasher.ComputeHash($bytes)).Replace('-','').ToLowerInvariant() }
finally { $hasher.Dispose() }
function Remove-Probe {
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) { throw 'No probe marker found; no file was removed.' }
    Assert-BMNoReparsePath $target
    Assert-BMNoReparsePath $marker
    $record=Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
    if ($record.sha256 -ne $expectedHash -or $record.target -ne $target) { throw 'Unexpected probe marker; no file was removed.' }
    if (Test-Path -LiteralPath $target) {
        if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $expectedHash) { throw 'Probe file changed; preserving it for inspection.' }
        Remove-Item -LiteralPath $target
    }
    Remove-Item -LiteralPath $marker
    Write-Host 'Probe removed. Original texture will load from the archive.' -ForegroundColor Green
}
if ($Mode -eq 'Remove') {
    Remove-Probe
    & (Join-Path $PSScriptRoot 'Test-SourceBaseline.ps1')
    return
}
& (Join-Path $PSScriptRoot 'Test-SourceBaseline.ps1')
if ((Test-Path -LiteralPath $target) -or (Test-Path -LiteralPath $marker)) {
    throw 'Probe or loose texture already exists. Nothing overwritten. Use -Mode Remove to recover an interrupted probe.'
}
$exe=Join-Path $test 'mages.exe'
Assert-BMNoReparsePath $exe
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'mages.exe missing from test copy.' }
[void][IO.Directory]::CreateDirectory((Split-Path $target -Parent))
Write-BMJson ([ordered]@{target=$target;sha256=$expectedHash;purpose='temporary texture probe';texture=$Texture}) $marker
$stream=[IO.File]::Open($target,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
try { $stream.Write($bytes,0,$bytes.Length) } finally { $stream.Dispose() }
if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $expectedHash) { throw 'Probe verification failed.' }
Write-Host "Look for a bright pink/green checkerboard on: $Texture" -ForegroundColor Cyan
if ($Mode -eq 'Prepare') { return }
try {
    $process=Start-Process -FilePath $exe -WorkingDirectory $test -PassThru -Wait
    Write-Host "Process exit code: $($process.ExitCode) (not a standalone pass/fail result)."
}
finally {
    # Do not remove a live process's probe if execution was interrupted.
    if (@(Get-Process -Name mages -ErrorAction SilentlyContinue).Count -eq 0) { Remove-Probe }
    else { Write-Warning 'Game is still running. Close it, then run this script with -Mode Remove and the same -Texture option.' }
    & (Join-Path $PSScriptRoot 'Test-SourceBaseline.ps1')
}
