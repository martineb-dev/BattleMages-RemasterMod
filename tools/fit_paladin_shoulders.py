"""Source-pinned shoulder clearance correction for Realism GameTest 02.

Change positions/local normals only. No extra vertices, skin weights, bones,
UV edits or animation changes. Requires Blender Python for nearest-surface BVH.
The static fit still requires in-game walking/attack verification.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from build_paladin_geometry import parse
from build_paladin_master import recalc, serialize
from probe_sam_topology import sections, SOURCE_SHA as ORIGINAL_SHA

SOURCE_SHA = 'afc2ef95d9a1b534e9b5294f990778b2bc6041f02972fc7dd807707fcdc5947b'


def checked(path, expected):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Unsupported source: ' + str(path))
    return data


def tree(part, faces=None):
    return BVHTree.FromPolygons([v[:3] for v in part['v']],
                               part['f'] if faces is None else faces, all_triangles=True)


def overlaps(parts):
    body = tree(parts[0])
    return {p['name']: len(body.overlap(tree(p))) for p in parts
            if p['name'].startswith('naplechnik')}


def build(source, original):
    before = parse(source)
    references = parse(original)
    parts = copy.deepcopy(before)
    body = parts[0]
    oldbody = references[0]
    positions = np.asarray(body['v'])[:, :3].copy()
    modified = set()
    fits = []
    for name, bones in [('naplechnik1', {9, 10}), ('naplechnik2', {19, 20})]:
        shell = next(p for p in parts if p['name'] == name)
        reference = next(p for p in references if p['name'] == name)
        v = np.asarray(shell['v'])
        rv = np.asarray(reference['v'])
        lo, hi = v[:, :3].min(0), v[:, :3].max(0)
        # Fairing/subdivision had pulled the rim inward. Restore the original
        # coverage with a small clearance margin while retaining the new shell.
        margin = np.array([.12, .12, .10])
        newlo, newhi = rv[:, :3].min(0)-margin, rv[:, :3].max(0)+margin
        scale = (newhi-newlo)/(hi-lo)
        v[:, :3] = (v[:, :3]-lo)*scale+newlo
        normals = v[:, 3:6]/scale  # inverse-transpose for a positive diagonal map
        v[:, 3:6] = normals/np.linalg.norm(normals, axis=1)[:, None]
        shell['v'] = v.tolist()

        faces = [f for f in oldbody['f']
                 if any(sum(w for b, w in oldbody['w'][i] if b in bones) > .05 for i in f)]
        original_surface = tree(oldbody, faces)
        armor_surface = tree(shell)
        changes = []
        for i, pos in enumerate(positions):
            influence = sum(w for b, w in body['w'][i] if b in bones)
            if influence < .08 or pos[2] < 11.6:
                continue
            distance = armor_surface.find_nearest(Vector(pos))[3]
            if distance > 1.25:
                continue
            fade = float(np.clip((pos[2]-11.6)/1.3, 0, 1))*float(np.clip((1.25-distance)/.6, 0, 1))
            if not fade:
                continue
            hit, normal, _, _ = original_surface.find_nearest(Vector(pos))
            target = np.asarray(hit)-np.asarray(normal)*.06
            new = pos+(target-pos)*(.85*fade)
            assert i not in modified, 'Left/right correction regions overlap'
            body['v'][i][:3] = new.tolist()
            modified.add(i)
            changes.append(float(np.linalg.norm(new-pos)))
        fits.append(dict(part=name, coverageScale=scale.tolist(),
                         movedSleeveVertices=len(changes), maxSleeveMoveGameUnits=max(changes)))

    # Only recalculate normals adjacent to moved sleeve points. All other body
    # records (especially the feet) remain byte-for-byte as in GameTest 02.
    affected_normals = {i for f in body['f'] if any(j in modified for j in f) for i in f}
    recalculated = copy.deepcopy(body)
    recalc(recalculated)
    for i in affected_normals:
        body['v'][i][3:6] = recalculated['v'][i][3:6]
    geometry = b''.join(serialize(p) for p in parts)
    entry = next(e for e in sections(source) if e[0] == 3)
    assert len(geometry) == entry[1]
    output = bytearray(source)
    output[entry[2]:entry[2]+entry[1]] = geometry
    after = parse(output)
    for old_section, new_section in zip(sections(source), sections(output)):
        assert old_section == new_section
        _, size, offset, _ = old_section
        if old_section[0] != 3:
            assert source[offset:offset+size] == output[offset:offset+size]
    for old, new in zip(before, after):
        assert (old['header'], old['mat'], old['kind'], old['f'], old['w']) == (
            new['header'], new['mat'], new['kind'], new['f'], new['w'])
        assert [v[6:8] for v in old['v']] == [v[6:8] for v in new['v']]
        assert len(old['v']) == len(new['v']) and serialize(new) == new['raw']
        if new['name'] in ('shlem', 'shit', 'mech'):
            assert old['raw'] == new['raw']
        if new['name'] == 'object03':
            for i, (a, b) in enumerate(zip(old['v'], new['v'])):
                if i not in modified:
                    assert a[:3] == b[:3]
                if i not in affected_normals:
                    assert a[3:6] == b[3:6]
                if a[2] < 2.2:
                    assert a == b, 'Foot/lower-leg record changed'
        v = np.asarray(new['v']); f = np.asarray(new['f'])
        cross = np.cross(v[f[:, 1], :3]-v[f[:, 0], :3], v[f[:, 2], :3]-v[f[:, 0], :3])
        assert np.isfinite(v).all() and np.all(np.linalg.norm(cross, axis=1) > 1e-9)
        assert np.allclose(np.linalg.norm(v[:, 3:6], axis=1), 1, atol=1e-5)
        assert np.all(np.einsum('ij,ij->i', cross, v[f, 3:6].mean(1)) > 0)
    before_overlap, after_overlap = overlaps(before), overlaps(after)
    assert all(after_overlap[k] < before_overlap[k] for k in before_overlap)
    report = dict(build='paladin-realism-game-03', sourceSha256=SOURCE_SHA,
                  originalSha256=ORIGINAL_SHA, outputSha256=hashlib.sha256(output).hexdigest(),
                  totalVertices=sum(len(p['v']) for p in after),
                  totalTriangles=sum(len(p['f']) for p in after),
                  fits=fits, changedBodyPositions=len(modified), changedBodyNormals=len(affected_normals),
                  topologyUVWeightsUnchanged=True, animationSectionsUnchanged=True,
                  feetHelmetSwordShieldExact=True,
                  staticBVHOverlapPairsBefore=before_overlap, staticBVHOverlapPairsAfter=after_overlap,
                  collisionCaveat='Static overlap diagnostic, not proof of clearance in all animation frames.',
                  runtimeStatus='UNVERIFIED: needs shoulder checks during movement and combat')
    return bytes(output), report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('source', type=Path)
    ap.add_argument('original', type=Path)
    ap.add_argument('output', type=Path)
    ap.add_argument('--report', type=Path, required=True)
    a = ap.parse_args()
    output, report = build(checked(a.source, SOURCE_SHA), checked(a.original, ORIGINAL_SHA))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_bytes(output)
    a.report.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
