# Status — 2026-09-20

## Implemented in this scaffold

- Windows PowerShell 5.1 / PowerShell 7 source inventory with SHA-256.
- Diagnostic ZIP containing inventory, executable versions, GDP header samples and the small root datasource/config files. It contains no game executables, full archives, textures or save contents.
- A separately copied test installation, verified against the original by file hash. Original source is never written to by these scripts.
- Read-only verification against the recorded source baseline.
- Local config and all original/binary/work files excluded from version control.
- Windows CI parser and smoke-test workflow, plus an explicitly named **tooling** build artifact.

## Not implemented / not verified yet

- Loading modified assets in the Steam build: unverified.
- GDP archive creation: no supported tool established.
- DDS conversion and mod payload building: not implemented.
- Patch deployment, per-file backups and rollback: planned, not implemented.
- Launch behavior of the copied Steam executable: untested. It could depend on Steam or select a shared save/config path; do not assume full runtime isolation from a file copy alone.
- Automated in-game testing: not implemented. No local Windows game is accessible from the cloud chat.

## Next input

Run Initialize-Workspace.ps1 locally and upload its BM-Diagnostics-*.zip into the shared Drive diagnostics folder. This identifies the executable/version, archive format signatures and datasource configuration without requesting the full installation initially.

Keep Steam closed to game updates and keep the game closed during setup. The original directory may still be changed independently by Steam or the game; source-baseline checks will detect that. Setup copies profiles locally, but diagnostics only include their filenames/hashes, not save bytes.

If source game files are required after diagnostics, request the original Steam GDP archives first. Keep non-Steam installation media separate and use only if a concrete compatibility comparison requires it. Never mix files from different editions into the same baseline.

## Art checkpoint

Models paused at Paladin v6 (visually accepted) and Swordsman v1 (review). Both are external art checkpoints, not game-ready DDS packages. The player spirit remains in scope.

## Loader investigation

1. Inspect datasources and executable/version metadata.
2. Check whether the build supports a data directory/override without altering source files.
3. Confirm unchanged assets can load in the test copy.
4. Convert and test one accepted paladin texture.
5. Only then implement payload builds and backup/rollback against the test copy.

The published README for jTommy ExMachina GDP v2.0 explicitly excludes Battle Mages archive creation. It supports extraction. A different implementation requires its own validation.

Source: https://www.playground.ru/ex_machina/file/exmachina_gdp_archives_unpacker_packer_v2_0_by_jtommy-864544

