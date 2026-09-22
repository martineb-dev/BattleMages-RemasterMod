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

Active: geometry/topology experiments under docs/ROADMAP.md. Test-copy launch,
loose overrides and comparison troops are user-confirmed. v3 edited shoulders
follow the body (user confirmed 2026-09-21). Full attack/death checks remain open.
v4 user reports normal movement. v5 refines rigid armor and adds weighted lower-leg
vertices; user accepted v5 in-game on 2026-09-21, exhaustive animations not verified.
v6 equipment loaded in-game (user screenshot, 2026-09-21). User prefers larger coherent batches
(e.g. shield and sword together), not repeated single-part probes. User authorized a full model overhaul. Master Candidate 01 changes all six parts;
its Windows runtime, attack/death and performance checks are pending. The user does
not accept its appearance as the target remaster: use the latest photorealistic
reference ead528fa-e273-4f22-8d04-cd78efd19d2b.png. No general
SAM exporter or final art master has been validated.

## Art decisions to preserve

- Every future model delivery includes BEFORE / AFTER using the actual original and candidate meshes, matching camera, scale, pose and lighting, plus textures.
- Preserve original design and approved texture/UV islands. Full geometry overhaul is authorized on After, including new sword and boots; keep Before unchanged. New geometry may remap within existing opaque texture islands.
- Dark fantasy, worn materials, original character identity and palette. Paladin cloth is white with a slight lavender shadow. Paladin texture v6 is visually accepted and integrated through the alpha-fixed DDS. Geometry build v6 is a separate checkpoint. Swordsman v1 awaits review and integration.
- No distinctive asymmetric damage on mirrored UV regions. Preserve the approved material texture/grain; avoid the rejected overly smooth appearance.
- Player spirit is in scope. Process race units first, then other units, then environment and buildings.
- Implement clear feedback directly; do not repeatedly ask the user to say 'next'.

## Engineering

- Read docs/STATUS.md before continuing. Keep completed work separate from planned functionality.
- Pin approved art bytes by SHA-256; never regenerate imagery during a build.
- Future deployment must record changed paths, back up existing targets separately, validate the baseline and support rollback.
- Meaningful tests: source remains byte-identical, dangerous/overlapping paths are rejected, junctions are refused, diagnostics exclude game binaries, incomplete initialization cannot be mistaken for success.
- Run tests/Smoke.Tests.ps1 and the PowerShell parser gate. Do not claim an in-game test without running the game.


## Realism target (latest user correction)

Do not treat more triangles or a subdivided legacy silhouette as a finished modern
character. Work toward convincingly constructed armor, shaped cloth, physical
material response and original character identity. A studio PBR preview is not
proof that the old engine can reproduce it. Label studio renders, static unrigged
assets and in-game evidence separately. Current Realism Study 01 is a Blender/Cycles
prototype derived from Master Candidate 01, with physical shoulder/tabard shells,
real chain links and material separation. It is neither a replacement SAM build nor
an approved final master. Existing diffuse atlas still contains painted lighting;
proper PBR albedo/normal/roughness authoring and legacy-renderer integration remain.

## Realism game adaptation

Realism GameTest 01 now has a private SAM/DDS comparison package. It is a legacy
adaptation of the study, not the full Cycles look. Study shoulder/tabard shells
were evaluated and exported; original body weights were transferred by nearest
triangle barycentrics. Original skeleton/animation sections remain unchanged.
User requested flatter planted feet: new planar soles and broader overlapping
sabaton plates, with contact faces at the source's z=0.03 bind-pose height.
16,544 triangles, no new IK or animation clips. Real chain links are NOT exported;
a normal bake supplies a restrained diffuse detail contribution in mail regions.
All mip alpha blocks and the team MRK remain exact. GameTest 01 FAILED on the user's
Windows machine with a VB LOCK assertion on 2026-09-22; Retry then caused an
unhandled exception 0x80000003. Do not treat it as a working runtime checkpoint.
The historical installer is Install-RealismGameTest.ps1 with the private
BM_Paladin_Realism_GameTest_01.zip, never the static Paladin_RealismStudy_01.zip.
Do not send the user back to MasterCandidate when they ask to test RealismStudy.

## VB LOCK investigation (current)

Realism GameTest 02 is a geometry-only conservative test: 5,328 vertices / 5,952
triangles, weighted body 1,985 vertices (01 had 11,169 / 16,544, body 5,179).
Original foot triangles/positions/UV/weights are retained exactly. Other surfaces
are simplified with interpolated skin groups. DDS/MRK, Before, mission, skeleton
and clips stay byte-identical to 01. The 2,048 body-vertex test budget is NOT a
discovered engine limit. Exact assertion cause remains unknown; runtime is pending.
Use Install-RealismGameTest02.ps1 and BM_Paladin_Realism_GameTest_02.zip. This saves
pre-launch mages.log and installed hashes, then after-run evidence, into one private
diagnostic ZIP. On assertion choose Abort, not Retry/Ignore. Do not advise driver
changes solely from the assertion's generic text. v6 is still the latest build
with user-confirmed runtime loading. Do not claim a fix until a Windows retest.
