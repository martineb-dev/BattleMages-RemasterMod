Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-BMFullPath {
    param([Parameter(Mandatory=$true)][string]$Path)
    $full = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetPathRoot($full)
    if ($full.Length -gt $root.Length) { $full = $full.TrimEnd([char[]]'\/') }
    return $full
}

function Test-BMContained {
    param([string]$Child, [string]$Parent)
    $c = Get-BMFullPath $Child
    $p = Get-BMFullPath $Parent
    if ($c.Equals($p, [StringComparison]::OrdinalIgnoreCase)) { return $true }
    $prefix = $p.TrimEnd([char[]]'\/') + [IO.Path]::DirectorySeparatorChar
    return $c.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)
}

function Assert-BMSeparatePaths {
    param([string]$First, [string]$Second)
    if ((Test-BMContained $First $Second) -or (Test-BMContained $Second $First)) {
        throw "Paths must not overlap: '$First' and '$Second'."
    }
}

function Assert-BMNoReparsePath {
    param([string]$Path)
    $cursor = Get-BMFullPath $Path
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Reparse points (junctions/symlinks) are not supported: $cursor"
            }
        }
        $parent = [IO.Directory]::GetParent($cursor)
        if ($null -eq $parent) { break }
        $cursor = $parent.FullName
    }
}

function Get-BMSafeFiles {
    param([string]$Root)
    Assert-BMNoReparsePath $Root
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) { throw "Folder missing: $Root" }
    $pending = New-Object 'System.Collections.Generic.Stack[string]'
    $files = New-Object 'System.Collections.Generic.List[object]'
    $pending.Push((Get-BMFullPath $Root))
    while ($pending.Count -gt 0) {
        $current = $pending.Pop()
        foreach ($item in @(Get-ChildItem -LiteralPath $current -Force)) {
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Reparse point in tree: $($item.FullName)"
            }
            if ($item.PSIsContainer) { $pending.Push($item.FullName) }
            else { $files.Add($item) }
        }
    }
    return $files.ToArray() | Sort-Object FullName
}

function Get-BMRelativePath {
    param([string]$Root, [string]$Path)
    if (-not (Test-BMContained $Path $Root)) { throw 'Path is outside the selected root.' }
    $prefix = (Get-BMFullPath $Root).TrimEnd([char[]]'\/') + [IO.Path]::DirectorySeparatorChar
    return (Get-BMFullPath $Path).Substring($prefix.Length).Replace('\','/')
}

function Write-BMJson {
    param([object]$Value, [string]$Path)
    $text = ConvertTo-Json -InputObject $Value -Depth 20
    [IO.File]::WriteAllText($Path, $text + [Environment]::NewLine, (New-Object Text.UTF8Encoding($false)))
}

function Get-BMGameLayout {
    param([string]$GamePath)
    $GamePath = Get-BMFullPath $GamePath
    Assert-BMNoReparsePath $GamePath
    $executables = @(Get-ChildItem -LiteralPath $GamePath -Filter '*.exe' -File)
    if ($executables.Count -eq 0) { throw 'Select the installation root containing the executable, not its data subfolder.' }
    $locations = @(
        foreach ($directory in @($GamePath, (Join-Path $GamePath 'data'))) {
            Assert-BMNoReparsePath $directory
            if (Test-Path -LiteralPath (Join-Path $directory 'Pack3.gdp') -PathType Leaf) {
                Assert-BMNoReparsePath (Join-Path $directory 'Pack3.gdp')
                $directory
            }
        }
    )
    if ($locations.Count -ne 1) {
        throw "Expected one archive location (root or data), found $($locations.Count): $GamePath"
    }
    $relative = if ($locations[0] -eq $GamePath) { '.' } else { 'data' }
    return [pscustomobject]@{ gameRoot=$GamePath; dataRoot=$locations[0]; dataRelativePath=$relative }
}

function Assert-BMGameRoot {
    param([string]$GamePath)
    [void](Get-BMGameLayout $GamePath)
}

function Get-BMInventory {
    param([string]$Root)
    $result = New-Object 'System.Collections.Generic.List[object]'
    foreach ($file in @(Get-BMSafeFiles $Root)) {
        $result.Add([pscustomobject][ordered]@{
            path = Get-BMRelativePath $Root $file.FullName
            bytes = $file.Length
            sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        })
    }
    return $result.ToArray()
}

function Compare-BMInventory {
    param([object[]]$Expected, [object[]]$Actual)
    $left = @{}; $right = @{}
    foreach ($item in $Expected) { $left[$item.path] = $item }
    foreach ($item in $Actual) { $right[$item.path] = $item }
    foreach ($name in $left.Keys) {
        if (-not $right.ContainsKey($name)) { "Missing: $name" }
        elseif ($left[$name].sha256 -ne $right[$name].sha256) { "Changed: $name" }
    }
    foreach ($name in $right.Keys) {
        if (-not $left.ContainsKey($name)) { "Added: $name" }
    }
}
