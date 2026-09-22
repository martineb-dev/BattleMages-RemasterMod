"""Conservative geometry-only candidate after Realism GameTest 01's VB LOCK.

Requires Blender 4.5 Python and the pinned private SAM. Budgets here are TEST
budgets, not discovered engine limits. Keep GameTest 01 DDS/MRK and all other
payload files exact so this experiment changes geometry alone.
"""
import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

import bpy
import numpy as np
from mathutils.bvhtree import BVHTree
from mathutils import Vector

from build_paladin_geometry import parse
from build_paladin_master import fresh, vertex, finish_normals, serialize
from probe_sam_topology import sections

SOURCE_SHA = '7c060f603308327bef3a87e03c8e032307a3b0ab2b6cecff323764878561ae43'
RATIOS = dict(object03=.20, shlem=.65, shit=.50,
              naplechnik1=.35, mech=.38, naplechnik2=.35)


def is_foot(part, face):
    bones = {b for i in face for b, _ in part['w'][i]}
    return (part['name'] == 'object03' and
            (bones <= {30, 31} or bones <= {35, 36}) and
            max(part['v'][i][2] for i in face) < 2.2)


def foot_signature(part):
    """Exact foot topology/positions/UV/weights, ignoring recomputed normals."""
    def record(i):
        v = part['v'][i]
        return (*v[:3], *v[6:], tuple(part['w'][i]))
    return sorted(tuple(record(i) for i in f) for f in part['f'] if is_foot(part, f))


def reduce_part(part):
    out = fresh(part)
    fixed = [f for f in part['f'] if is_foot(part, f)]
    selected = [f for f in part['f'] if not is_foot(part, f)]
    used = sorted({i for f in selected for i in f})
    lookup = {i: j for j, i in enumerate(used)}
    mesh = bpy.data.meshes.new(part['name'])
    mesh.from_pydata([part['v'][i][:3] for i in used], [],
                     [tuple(lookup[i] for i in f) for f in selected])
    mesh.update()
    uv = mesh.uv_layers.new()
    for loop in mesh.loops:
        uv.data[loop.index].uv = part['v'][used[loop.vertex_index]][6:8]
    obj = bpy.data.objects.new(part['name'], mesh)
    bpy.context.collection.objects.link(obj)
    # Let the simplifier interpolate the original vertex groups. Do not transfer
    # from a nearest but unrelated overlapping cloth/armor surface.
    bones = sorted({b for i in used for b, _ in part['w'][i]})
    groups = {b: obj.vertex_groups.new(name=str(b)) for b in bones}
    for j, i in enumerate(used):
        for b, w in part['w'][i]:
            groups[b].add([j], w, 'REPLACE')
    mod = obj.modifiers.new('Runtime geometry budget', 'DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = RATIOS[part['name']]
    mod.use_collapse_triangulate = True
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    reduced = evaluated.to_mesh()
    reduced.calc_loop_triangles()
    cache = {}
    try:
        for face in reduced.loop_triangles:
            pos = [np.array(reduced.vertices[i].co) for i in face.vertices]
            if np.linalg.norm(np.cross(pos[1]-pos[0], pos[2]-pos[0])) < 1e-9:
                continue
            indices = []
            for i, li, p in zip(face.vertices, face.loops, pos):
                tex = tuple(float(x) for x in reduced.uv_layers.active.data[li].uv)
                key = (i, *tex)
                if key not in cache:
                    weights = sorted(((bones[g.group], float(g.weight))
                                      for g in reduced.vertices[i].groups if g.weight > 1e-7),
                                     key=lambda x: (-x[1], x[0]))[:4]
                    total = sum(w for _, w in weights)
                    weights = [(b, w/total) for b, w in weights] if total else []
                    if part['kind'] == 2 and not weights:
                        raise ValueError('Missing interpolated skin weights')
                    cache[key] = vertex(out, p, tex, weights)
                indices.append(cache[key])
            out['f'].append(tuple(indices))
    finally:
        evaluated.to_mesh_clear()
        bpy.data.objects.remove(obj, do_unlink=True)
    # Feet are copied without simplification: sole plane, bevels and sabaton
    # plates keep exactly their positions, UVs, skin weights and triangles.
    fixed_lookup = {}
    for face in fixed:
        new = []
        for i in face:
            if i not in fixed_lookup:
                fixed_lookup[i] = vertex(out, part['v'][i][:3], part['v'][i][6:8], part['w'][i])
            new.append(fixed_lookup[i])
        out['f'].append(tuple(new))
    finish_normals(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('source', type=Path)
    ap.add_argument('output', type=Path)
    ap.add_argument('--report', type=Path, required=True)
    args = ap.parse_args()
    source = args.source.read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Expected the unchanged Realism GameTest 01 SAM')
    before = parse(source)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    parts = [reduce_part(p) for p in before]
    geo = b''.join(serialize(p) for p in parts)
    entries = sections(source)
    gi = next(i for i, e in enumerate(entries) if e[0] == 3)
    _, size, start, _ = entries[gi]
    delta = len(geo)-size
    output = bytearray(source[:start]+geo+source[start+size:])
    struct.pack_into('<I', output, 16+16*gi, len(geo))
    for i in range(gi+1, len(entries)):
        struct.pack_into('<I', output, 20+16*i, entries[i][2]+delta)
    for old, new in zip(entries, sections(output)):
        if old[0] != 3:
            assert source[old[2]:old[2]+old[1]] == output[new[2]:new[2]+new[1]]
    after = parse(output)
    report = []
    for old, new in zip(before, after):
        assert (old['name'], old['mat'], old['kind']) == (new['name'], new['mat'], new['kind'])
        assert serialize(new) == new['raw']
        v = np.asarray(new['v']); f = np.asarray(new['f'])
        cross = np.cross(v[f[:, 1], :3]-v[f[:, 0], :3], v[f[:, 2], :3]-v[f[:, 0], :3])
        assert np.isfinite(v).all() and np.all(np.linalg.norm(cross, axis=1) > 1e-9)
        assert np.allclose(np.linalg.norm(v[:, 3:6], axis=1), 1, atol=1e-5)
        assert np.all(np.einsum('ij,ij->i', cross, v[f, 3:6].mean(1)) > 0)
        allowed = {b for w in old['w'] for b, _ in w}
        for weights in new['w']:
            if new['kind'] == 2:
                assert 1 <= len(weights) <= 4 and abs(sum(w for _, w in weights)-1) < 1e-5
                assert {b for b, _ in weights} <= allowed
        if new['name'] == 'object03':
            # A simplified lower-shin triangle can newly satisfy the z<2.2
            # selector. Require every protected foot triangle exactly once,
            # rather than misclassifying that new shin triangle as a foot edit.
            oldfeet, newfeet = Counter(foot_signature(old)), Counter(foot_signature(new))
            assert all(newfeet[f] == count for f, count in oldfeet.items()), 'Changed protected foot geometry'
        tree = BVHTree.FromPolygons([x[:3] for x in old['v']], old['f'], all_triangles=True)
        errors = [float(tree.find_nearest(Vector(x[:3]))[3]) for x in new['v']]
        report.append(dict(part=new['name'], beforeVertices=len(old['v']), vertices=len(new['v']),
                           beforeTriangles=len(old['f']), triangles=len(new['f']),
                           maxSurfaceDistanceGameUnits=max(errors)))
    # Conservative experiment budgets, deliberately below the 7,395 total
    # vertices / 9,278 triangles of the runtime-confirmed v6 equipment build.
    assert sum(len(p['v']) for p in after) <= 6500, 'Total vertex budget exceeded'
    assert sum(len(p['f']) for p in after) <= 8500, 'Total triangle budget exceeded'
    assert len(after[0]['v']) <= 2048, 'Weighted body experiment budget exceeded'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output)
    result = dict(build='paladin-realism-game-02', sourceSha256=SOURCE_SHA,
                  outputSha256=hashlib.sha256(output).hexdigest(), parts=report,
                  totalVertices=sum(len(p['v']) for p in after),
                  totalTriangles=sum(len(p['f']) for p in after),
                  footGeometryUVWeightsExact=True, animationSectionsUnchanged=True,
                  diagnosis='Reduced geometry to test a VB LOCK regression; exact engine limit/cause unknown',
                  runtimeStatus='UNVERIFIED')
    args.report.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
