# Visual overhaul roadmap — agreed 2026-09-21

Reference: user supplied 7162826e-29cd-4ca1-9d33-4fe70701b877.png.
Target its readable, rounded armor and dimensional equipment. Preserve original
character design, worn dark-fantasy materials and white cloth with lavender shade;
the reference's sunny pristine setting is not a replacement for that direction.

1. IN PROGRESS: prove additional vertices/triangles can load and animate in SAM.
   v3 position-only shoulders followed the body (user confirmed). v4 subdivides
   one rigid shoulder, 16 to 46 vertices and 16 to 64 triangles. User reports normal movement. Full animation coverage and installed-file verification remain open.
2. IN PROGRESS (v5 accepted; v6 equipment batch runtime pending): Refine complete paladin silhouette: shoulders, helmet, hands, boots, legs,
   shield thickness and sword profile. Remove v3 diagnostic enlargement.
3. Preserve original skeleton/animations where compatible; assign new body
   vertices appropriate weights. Verify idle, walk, attack and death.
4. Adapt approved v6 textures; preserve cutout alpha, team colors and mirrored UVs.
5. Investigate actual engine material/lighting support; do not assume PBR or normals.
6. Compare original and After troops in new cm1 at the same camera and normal
   gameplay distance. Deliver actual model Before/After and texture previews.
7. Repeat: race units, other units including player spirit, environment, buildings.

Original installation read-only. Private derived assets stay out of GitHub.
Each milestone needs observed evidence before being marked complete.

Workflow: user prefers larger coherent batches; keep before/after and rollback.
