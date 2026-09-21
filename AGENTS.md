# Battle Mages Remaster Mod

Target the FIRST Battle Mages. All user-facing commands must work in Windows PowerShell 5.1 and PowerShell 7. Use one complete copy-paste block for setup instructions. Do not require Administrator privileges.

## Source installation boundary

- Treat the configured original installation as READ ONLY. Never patch, repack, rename, delete, or launch files there as part of setup.
- Work on a separate, fully copied test installation. No hardlinks, junctions, symlinks, or reverse synchronization to the source.
- Keep original game files, extracted files, executables, diagnostics, backups and large art checkpoints outside this public repository. Do not commit credentials or local paths from config/local.json.
- A GitHub connection cannot access the user's Windows disk. Local execution must occur through local Codex or PowerShell in this checkout.
- Never deploy into a game installation until its data-loading route has been verified. jTommy GDP v2.0 supports Battle Mages extraction but its documented packer does not support Battle Mages archive creation.
- Do not implement bypasses for Steam, activation, or DRM. Establish normal launch behavior in the copied installation first.

## Current milestone

Models are PAUSED. Steam diagnostics are received and the user confirmed a successful test-copy menu/map launch with the original SHA-256 baseline unchanged. Next: controlled loose-texture loader probe, then asset integration. Test-LooseTexture.ps1 is a temporary synthetic diagnostic fixture, not a mod deployment. User confirmed menu TGA override on 2026-09-21. Model DDS override remains unverified.

## Art decisions to preserve

- Every future model delivery includes BEFORE / AFTER on the actual same mesh, same camera, same scale, same pose and lighting, plus textures.
- Preserve original geometry/UVs/design for the current texture-only scope.
- Dark fantasy, worn materials, original character identity and palette. Paladin cloth is white with a slight lavender shadow. Paladin v6 is visually accepted; Swordsman v1 is awaiting review. Neither is game-integration tested.
- No distinctive asymmetric damage on mirrored UV regions. Preserve the approved material texture/grain; avoid the rejected overly smooth appearance.
- Player spirit is in scope. Process race units first, then other units, then environment and buildings.
- Implement clear feedback directly; do not repeatedly ask the user to say 'next'.

## Engineering

- Read docs/STATUS.md before continuing. Keep completed work separate from planned functionality.
- Pin approved art bytes by SHA-256; never regenerate imagery during a build.
- Future deployment must record changed paths, back up existing targets separately, validate the baseline and support rollback.
- Meaningful tests: source remains byte-identical, dangerous/overlapping paths are rejected, junctions are refused, diagnostics exclude game binaries, incomplete initialization cannot be mistaken for success.
- Run tests/Smoke.Tests.ps1 and the PowerShell parser gate. Do not claim an in-game test without running the game.

