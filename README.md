# BattleMages-RemasterMod

A texture-first mod project for the original **Battle Mages**. Current milestone: reproducible Windows tooling and a separate test installation. No texture mod is installed by this initial scaffold.

## First run — Windows PowerShell

Requires Git and Windows PowerShell 5.1 or PowerShell 7. Run as your normal Windows user; Administrator is not needed. Close the game and wait for Steam downloads/updates to finish.

```powershell
$ErrorActionPreference = 'Stop'
$repoPath = Join-Path $env:USERPROFILE 'BattleMages-RemasterMod'
if (Test-Path -LiteralPath $repoPath) { throw "Folder already exists: $repoPath. Open that checkout instead of cloning over it." }
git clone https://github.com/martineb-dev/BattleMages-RemasterMod.git $repoPath
if ($LASTEXITCODE -ne 0) { throw 'Git clone failed.' }
Set-Location -LiteralPath $repoPath
& powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\Initialize-Workspace.ps1
if ($LASTEXITCODE -ne 0) { throw 'Setup failed; review the preceding error. Do not use an incomplete workspace.' }
```

The command sets RemoteSigned only for the child PowerShell process; it does not change the machine's saved policy and cannot override a managed policy.

Default source: `C:\Program Files (x86)\Steam\steamapps\common\Battle Mages`.

Default work area: `%USERPROFILE%\BattleMages-RemasterWorkspace`. It must not already exist at the first initialization. Setup makes `game-test`, `assets`, `backups`, `builds`, `reports`, and `source-baseline.json` there. The source installation is read-only. Copying needs roughly the size of the installed game in extra free disk space.

The final output gives a diagnostic ZIP path. Upload that ZIP to the shared project's `04_Diagnostics` Drive folder. You do not need to upload the whole Steam installation or non-Steam installer yet.

## Local Codex

Start `codex` from this checkout after setup. It will read `AGENTS.md`. Ask it to read `config/local.json`, `docs/STATUS.md`, and the diagnostic output, then investigate the loader using the copied game. Install Codex separately through its official Windows instructions if not already installed; this repository does not install global tools.

## Recheck the original files

```powershell
.\scripts\Test-SourceBaseline.ps1
```

To collect another report without reinitializing:

```powershell
.\scripts\Get-GameReport.ps1
```

## Versioning and builds

Git tracks tooling, documentation, and the asset catalog. Original game bytes, working copies, diagnostic archives and art binaries are external. CI tests both supported PowerShell hosts on Windows and produces a tooling ZIP; it is not a runnable game or a texture mod release. `docs/STATUS.md` lists the remaining integration work.

Future mod builds will pin approved texture hashes and converter versions, validate DDS/alpha/mipmaps, and produce a payload manifest. Applying a payload will target only the copied test installation, record a separate backup, and support rollback. These features are deliberately pending the verified loader route.

## Review format

Every art delivery includes the original and new texture on the same real mesh, with matching camera, pose, scale and lighting, plus texture comparisons. Preserve the original visual identity; see `AGENTS.md` for the current art decisions.
