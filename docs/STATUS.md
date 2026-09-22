# Status — 2026-09-22

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

## v4 feedback and v5 geometry pass

User reports normal movement after v4 and supplied in-game screenshot. This supports
loading and movement, not independently measured runtime triangle count or all animations.
v5 refines both rigid shoulders and helmet with two subdivision rounds, and weighted
lower legs (bone subsets 30/31 and 35/36). Boundary neighbors split to avoid T-junctions
inside indexed mesh; coincident seam positions use shared curvature normals. Existing
vertex records and bone weights stay exact. New weights interpolate endpoints, normalize,
and must not exceed the four influences already observed in the source. New joints are
not added. Animation and other non-geometry sections remain byte-identical.

Total triangles: 414 -> 2646. Original body upper parts, shield/sword and approved DDS
remain unchanged; this is a first rounded silhouette pass, not a complete new model.
Local structural and preservation assertions pass. v5 loading/skinning, including walking,
attack and death, remain UNVERIFIED in game. Private package includes actual same-camera
Before/After geometry preview with the same After texture on both sides, plus textures.

## v5 accepted; v6 equipment batch

User accepted v5 with in-game screenshot (2026-09-21) and requested larger steps.
v6 batches shield solidification/rim, alpha-contour guard extrusion and blade ridge
thickening. Source pinned to v5; source DDS pinned and unchanged. Alpha clipped
surface is tessellated, reverse UVs interpolated from source reverse faces, and
boundary walls use an existing opaque metal swatch. Original shield/sword attachment
names, materials, body meshes and all non-geometry chunks remain unchanged.
Local checks: valid indices/counts, finite records, positive winding-to-normal dot
for equipment faces, exact preservation of other meshes/sections and all other
payload files. Total 9278 triangles; development topology, not army-scale optimized.
Preview culls reverse normals to avoid coplanar front/back artifacts on original
shield. No texture smoothing or recoloring was applied. Runtime loading, attack,
reverse UV appearance and performance require Windows verification.

## v6 loaded; full-model Master Candidate 01

2026-09-21: user supplied a close in-game v6 screenshot and requested a full model
overhaul, particularly proper sword geometry, instead of more isolated probes.
v6 loading and visible equipment are confirmed; exhaustive animations are not.

`tools/build_paladin_master.py` requires the pinned v2 SAM and pinned v6 SAM.
It changes all six mesh parts and outputs 11826 triangles. New blade, bevels and
fullers, rounded grip and pommel; original wing-shaped guard gets added depth.
Shield is rebuilt from the established outline with a curved surface and narrow
edge. New boots use four overlapping geometric toe plates per foot, attached to
original foot/shin bones. Torso, hands, arms, cloth, helmet and shoulders receive
curved refinement. Some existing surfaces are refined rather than authored anew.
Approved DDS bytes, MRK, Before assets and all mission files are unchanged.

Source skeleton/animation and all non-geometry sections are byte-identical.
New/interpolated skinning uses existing bones, normalized weights and at most four
influences. These properties do not independently prove deformation quality.
Local geometry checks cover finite values, valid indices, section layout, binary
roundtrip, unit normals, positive face/normal orientation, nonzero triangle areas
and preservation of the other payload files. No PBR shader, new rig, new animation
or LOD chain has been introduced. Runtime status is UNVERIFIED until the user tests.

Private package includes actual SAM before/after previews, v6-to-candidate details,
original/After texture PNGs, deployable SAM/DDS and static OBJ/MTL inspection exports.
Offline previews use the same pose/camera/light within each pair, but do not simulate
the engine's player-color shader or lighting. OBJ exports are static, not a rigged
interchange format; the game SAM retains its original rig/clip sections.

`Switch-ComparisonBuild.ps1` validates the complete incoming package, installed
checksums, exact prior manifest and source baseline before removing an existing
comparison. Finds previous package under workspace/builds (or accepts an explicit
path). Retains both packages for rollback. Modified/unmanaged loose files are
refused. A copy failure can leave a partial new receipt; recover with the existing
Remove command for that exact package, then reinstall the prior package. This is
not an atomic switch or automatic rollback. PowerShell parser and Linux pwsh smoke
checks passed, including invalid incoming data, preserving local edits, switching
forward/back and source-byte preservation. Windows game testing remains separate.

## Reference correction and Realism Study 01

User says Master Candidate 01 does not achieve the expected photographic fantasy
look; latest reference is ead528fa-e273-4f22-8d04-cd78efd19d2b.png. Keep this as the
visual goal, not a claim about the original renderer. Master Candidate 01 remains
an integration candidate, not visually accepted as the remaster master.

Built a separate static Blender 4.5.3 / Cycles study through
`tools/build_paladin_material_study.py`. Inputs/outputs are private and external.
Derived geometry uses the existing master, replacing intersecting shoulder/tabard
inner/outer layers with single outer shells plus physical thickness. Added 4178
actual steel chain links for the modern master view. These are high-detail study
geometry; no direct SAM export or game-performance claim is made. Source skinning
metadata is retained in private JSON, but the Blender scene has NO animation rig.

Separate steel/cloth/leather material responses; approximate green team tint uses
the original MRK. The approved atlas RGB/alpha is retained as source and still
contains painted lighting. This is a material study, not finished PBR texture
production. Camera/lighting are fixed across: original mesh with diffuse atlas,
modern shell geometry with diffuse atlas, and PBR+physical-mail view. Studio results
must not be presented as in-game results. Packed Blender scene, maps and actual
rendered comparisons are delivered in a private archive; game-test is untouched.

The extracted .shader examples examined describe animated texture sequences.
They do not establish PBR/normal-map support for units. Next: author a genuinely
modern asset and unlit material maps, then assess what geometry and baked detail
can be transferred to the legacy engine. Renderer modifications are a separate
investigation; a GPU's capabilities alone do not establish engine support.

## Realism GameTest 01: deployable legacy adaptation, awaiting Windows test

User explicitly requested integrating RealismStudy and flattening the rounded
feet. Created an actual SAM/DDS package from that study, rather than offering the
older MasterCandidate installer again. The previous download error was the user
selecting the valid static Study ZIP, not a damaged download.

`export_paladin_realism_game.py` evaluates the pinned study's shoulder and tabard
shells, merges cloth into the original weighted body part, transfers weights by
closest-triangle barycentrics, and rebuilds the six-part SAM geometry section.
Skeleton, animation and all other sections are byte-identical to MasterCandidate.
Largest transfer distance is 0.09275 game units, about 9.3 mm in the study scale.
New boot soles have 12 boundary contact positions per foot, one plane at z=0.03
in the source pose, heel/toe chamfers and broad overlapping metal plates.
This does not guarantee planted feet in every animation frame or on slopes.

The candidate has 16,544 triangles. The 501,360 study mail triangles are omitted.
`bake_paladin_mail.py` projects the physical links into a tangent-space authoring
map; `build_paladin_legacy_texture.py` adds a restrained 22% local diffuse-detail
contribution through the existing mail mask. All other material regions retain
the approved design; unchanged BC3 color blocks are copied. All BC3 alpha blocks
at every mip level are byte-identical, as is the original MRK. The normal map is
included for authoring only, not deployed as an unsupported game shader.

Only bmafter.sam and bmafter.dds differ from the prior comparison payload. Before
files, troop definitions and Chapter 1 spawn configuration remain unchanged.
`Install-RealismGameTest.ps1` checks a pinned NEW ZIP and identifies the old static
study explicitly before extraction. It validates workspace/source separation and
uses the existing verified-file switcher; prior build folders remain available.
No claim of atomic switching or automatic rollback is made.

Local checks: SAM roundtrip, finite geometry, unit normals, positive winding,
bone IDs/normalized weights, non-geometry section identity, planar contact
vertices, DDS decode/alpha preservation, and exact preservation of other payloads.
PowerShell parser and smoke suite passed on Linux pwsh. Previews are renders of
the delivered SAM/DDS under matched diffuse studio conditions, NOT engine captures.
Windows load/movement/attack/death, foot placement and performance remain pending.

## 2026-09-22 — Realism GameTest 01 assertion; GameTest 02 candidate

User reports the Windows C++ assertion `WE HAVE A PROBLEM WITH VB LOCK!!! LET'S
TRY USE NEW VIDEO DRIVERS`. Choosing Retry then displayed unhandled exception
0x80000003. This is a FAILED runtime checkpoint, not a normal exit-code-1 case.
No crash log or HRESULT has yet been received. Retry invokes the debugger:
https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/assert-macro-assert-wassert
The message alone does not establish a driver problem or a particular engine limit.

Comparison of actual SAM records:

| Build | Vertices | Triangles | Weighted body vertices | Runtime evidence |
| --- | ---: | ---: | ---: | --- |
| v6 equipment | 7395 | 9278 | 726 | User confirmed loading |
| Realism GameTest 01 | 11169 | 16544 | 5179 | VB LOCK assertion |
| Realism GameTest 02 | 5328 | 5952 | 1985 | Not yet tested in Windows |

`tools/optimize_paladin_runtime.py` consumes only the pinned GameTest 01 SAM.
It simplifies six parts using Blender's collapse modifier and interpolated
original skin groups. Retains at most four normalized influences on existing
bones. All 792 original foot triangles, their positions, UVs and skin weights
are retained exactly; sole height remains z=0.03 in the static source pose.
No new animations or IK. Other surfaces change topology and some positions/UVs;
this is a conservative test candidate, not the final art master or an LOD chain.
Maximum new-body vertex distance to the old surface is 0.11636 game units.

Only bmafter.sam changes in the deployed payload relative to GameTest 01.
DDS, all alpha/mips, MRK, Before, troop/mission definitions and non-geometry SAM
sections remain byte-identical. Output SAM SHA256:
`afc2ef95d9a1b534e9b5294f990778b2bc6041f02972fc7dd807707fcdc5947b`.
The limits enforced by this exporter are experimental budgets, NOT documented
engine capacities. A successful retest would support the geometry-complexity
hypothesis but would not by itself identify the exact failing allocation.

`Install-RealismGameTest02.ps1` pins the new ZIP, saves the previous crash log
and receipt before replacing a build, switches through the existing checked
installer, and preserves after-run logs plus hashes in one diagnostic ZIP.
It never copies executable, asset or save bytes into diagnostics. Prior package
folders remain available as rollback inputs. Original source baseline checked
before and after. Normal exit code alone does not decide runtime success.
If an assertion recurs, Abort and upload the printed diagnostic ZIP.

Local checks: SAM binary roundtrip, finite/indexed geometry, nonzero triangle
areas, winding/normals, valid bone influences, exact foot preservation, unchanged
non-geometry chunks and all other payload files. PowerShell parser and smoke
suite passed, including wrong-ZIP refusal, preserving existing crash evidence,
checked build switching and byte-identical source installation. Studio previews
render the actual SAM under fixed lighting; they are not in-game proof.
