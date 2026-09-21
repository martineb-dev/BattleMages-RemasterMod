# Status — 2026-09-21

Current work: docs/ROADMAP.md. Earlier sections below are chronological history;
the latest runtime/topology entries supersede their pending statements.

## Implemented in this scaffold

- Windows PowerShell 5.1 / PowerShell 7 source inventory with SHA-256.
- Supports executable-at-root with GDP/config files either at root or under data. The user's Steam layout has mages.exe at root and Pack*.gdp/config.cfg/datasources.txt in data.
- Diagnostic ZIP containing inventory, executable versions, GDP header samples and the small datasource/config files, preserving relative paths. It contains no game executables, full archives, textures or save contents.
- A separately copied test installation, verified against the original by file hash. Original source is never written to by these scripts.
- Read-only verification against the recorded source baseline.
- Local config and all original/binary/work files excluded from version control.
- Windows CI parser and smoke-test workflow, plus an explicitly named **tooling** build artifact.

## Not implemented / not verified yet

- User confirmed the menu TGA checkerboard appeared on 2026-09-21. Loose TGA overrides the archived logo with unchanged datasources order. Model DDS loading remains unverified.
- GDP archive creation: no supported tool established.
- DDS conversion and mod payload building: not implemented.
- Patch deployment, per-file backups and rollback: planned, not implemented.
- Test-copy launch confirmed by user on 2026-09-21: main menu and cm1 loaded successfully, normal quit recorded, original file baseline unchanged. Exit code 1 accompanied normal shutdown; do not use it alone to classify a crash. Registry/external save isolation is not established.
- Automated in-game testing: not implemented. No local Windows game is accessible from the cloud chat.

## Next input

Diagnostics received and inspected. datasources.txt lists data, then Pack_Loc, pack1, pack2, pack3. Menu TGA override is now confirmed by user observation. Test-LooseTexture.ps1 creates a synthetic 512x256 BGRA TGA at the menu logo path referenced by extracted mainmenuwnd.xml. Run mode launches the test copy and removes the fixture on exit; Remove mode recovers an interrupted run. Existing loose textures are refused, never overwritten. Next: -Texture Paladin probes the original 512x512 DXT5 format with 10 mip levels. A visible paladin is required; menu-only observation cannot validate this test.

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

## Chapter 1 comparison build

User requested two extra starting troops in Part I / Chapter 1, Final Examination. Prepared a private cm1-comparison-paladin-v1 package from supplied extracted Pack3. The one-shot trigger follows the existing mission CreateNewObject and player:AddChild pattern. Before/After clone troop, unit and animated-model definitions; same-length SAM texture-name edits isolate their textures without changing geometry or animations. Before uses original DDS; After converts approved Paladin v6 PNG to 1024 DXT5 with mipmaps. Two six-unit troops spawn near the initial swordsmen at (4620,4640) and (4850,4640). Actual placement, XML overrides and game behavior are NOT runtime verified.

Use-ComparisonBuild.ps1 installs only into the configured test copy, refuses existing loose files, records a manifest receipt, and removes only unchanged installed files. Original GDP files serve as untouched originals; there are no overwritten loose files to back up. Close the game before removal. Start a NEW chapter; existing saves do not rerun the startup trigger. Saves created with custom model IDs may require this package to remain installed.

The Python builder accepts --unit, --troop and --stem for future units; current binary texture-name substitution requires a seven-character stem and one DDS reference. Additional asset formats require implementation and validation, not blind substitution. Payloads contain private derived game files and must not enter the public repository.

## Runtime feedback and alpha fix

2026-09-21: user confirmed both comparison troops spawn; screenshot shows the After group on the right. Chapter XML/model overrides now have runtime evidence. User reports little remaster impact, angular legs, visible opaque weapon/shield planes and palette differences. Inspection confirmed v1 After DDS alpha was uniformly 255; original DDS has cutouts. v2 restores original BC3 alpha endpoints/indices at every mip; level 0 doubles original pixels exactly, subsequent levels copy original mip alpha. RGB blocks, geometry, animation, mission and Before payload remain byte-identical to v1. Local decoded-alpha comparison passed. In-game verification of v2 is pending.

Texture-only work cannot change the angular silhouette. A geometry pass on feet/legs, pauldrons, helmet and equipment is the next proposed visual milestone. SAM export with valid skinning/animation and engine compatibility must be established before claiming a modern mesh can run. Screenshot green regions appear consistent with team colors; copied MRK is unchanged, exact shader interpretation needs validation.

## Geometry probe v3

User authorized first geometry experiment. Source-pinned probe_sam_geometry.py modifies XYZ of 32 vertices across the two pauldrons by uniform 1.30 scale about each part center. Source has 423 vertices and 414 triangles in six parts; counts are unchanged. Every byte outside selected position fields, including normals (unchanged under uniform scale), UVs, skin weights, skeleton/animation and trailing data remains identical. This is not a general SAM exporter or new-topology support. Package v3 retains alpha-fixed v2 textures and changes only After SAM. A diagnostic same-camera geometry preview is bundled. Runtime walking/attack/death tests remain pending.

## v3 feedback and v4 topology test

User confirmed v3 shoulders follow the body. Screenshot supports attached geometry;
full attack/death validation remains pending. Agreed roadmap saved in ROADMAP.md.

SAM section-table interpretation checked against all 127 supplied SAM files:
uint32 count at byte 8, then 16-byte (id,size,offset,reserved) entries with contiguous
payloads ending at EOF. Source-pinned v4 rebuilds only naplechnik1, interpolates UVs
and normals, projects edge midpoints to endpoint tangent planes, and replaces 16
triangles with 64 (16 -> 46 vertices). Updates geometry size and later section offsets.
Other meshes and all non-geometry section payloads are byte-identical, including
animation. This validates file construction locally, not the game's parser.

v4 uses v2 geometry as base, removes v3 enlargement, keeps v2 alpha-fixed DDS bytes.
Private package includes same-camera actual shoulder geometry and texture previews.
Runtime loading, walking, attack and death require the user's Windows test.
