"""Source-pinned rigid shoulder subdivision experiment, NOT a general exporter."""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

SOURCE_SHA = 'ca83ad6d860d3d0768eab0e681c9975bfcdfe0c07fcf5c47d0a536e312f29b38'

def sections(b):
    n = struct.unpack_from('<I', b, 8)[0]
    entries = [struct.unpack_from('<4I', b, 12+16*i) for i in range(n)]
    assert entries[0][2] == 12+16*n
    for i, (_, size, offset, _) in enumerate(entries):
        assert offset+size == (entries[i+1][2] if i+1<n else len(b))
    return entries

def meshes(b, start, end):
    result = []
    o = start
    while o < end:
        begin = o
        name = b[o:o+40].split(b'\0')[0].decode('ascii')
        nv, nf, mat, kind = struct.unpack_from('<4H', b, o+40)
        assert kind in (1, 2)
        o += 48
        vertices = []
        for _ in range(nv):
            vertices.append(struct.unpack_from('<8f', b, o))
            o += 32
            if kind == 2:
                weights = struct.unpack_from('<H', b, o)[0]
                o += 2+6*weights
        faces = [struct.unpack_from('<3H', b, o+6*i) for i in range(nf)]
        o += 6*nf
        assert all(max(f)<nv for f in faces)
        result.append(dict(name=name, start=begin, end=o, vertices=vertices,
                           faces=faces, material=mat, kind=kind))
    assert o == end
    return result

def build(source):
    assert hashlib.sha256(source).hexdigest() == SOURCE_SHA, 'Unsupported source SAM'
    entries = sections(source)
    gi = next(i for i, e in enumerate(entries) if e[0] == 3)
    _, old_size, start, _ = entries[gi]
    parts = meshes(source, start, start+old_size)
    part = next(p for p in parts if p['name'] == 'naplechnik1')
    assert part['kind'] == 1
    vertices = list(part['vertices'])
    cache = {}
    def midpoint(a, b):
        key = tuple(sorted((a, b)))
        if key in cache:
            return cache[key]
        va, vb = vertices[a], vertices[b]
        pos = [(va[k]+vb[k])/2 for k in range(3)]
        # Project midpoint to endpoint tangent planes; average projections
        # for a mild curvature correction. Original vertices remain fixed.
        projected = []
        for v in (va, vb):
            n = v[3:6]
            n2 = sum(x*x for x in n)
            d = sum((pos[k]-v[k])*n[k] for k in range(3))/n2 if n2 else 0
            projected.append([pos[k]-d*n[k] for k in range(3)])
        pos = [(projected[0][k]+projected[1][k])/2 for k in range(3)]
        normal = [va[k]+vb[k] for k in range(3,6)]
        length = math.sqrt(sum(x*x for x in normal))
        normal = [x/length for x in normal] if length>1e-8 else list(va[3:6])
        value = (*pos, *normal, (va[6]+vb[6])/2, (va[7]+vb[7])/2)
        assert all(math.isfinite(x) for x in value)
        cache[key] = len(vertices)
        vertices.append(value)
        return cache[key]
    faces = []
    for a,b,c in part['faces']:
        ab,bc,ca = midpoint(a,b),midpoint(b,c),midpoint(c,a)
        faces.extend(((a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca)))
    assert len(vertices)<65536 and len(faces)<65536
    replacement = source[part['start']:part['start']+40]
    replacement += struct.pack('<4H',len(vertices),len(faces),part['material'],1)
    replacement += b''.join(struct.pack('<8f',*v) for v in vertices)
    replacement += b''.join(struct.pack('<3H',*f) for f in faces)
    delta = len(replacement)-(part['end']-part['start'])
    out = bytearray(source[:part['start']]+replacement+source[part['end']:])
    struct.pack_into('<I',out,12+gi*16+4,old_size+delta)
    for i in range(gi+1,len(entries)):
        struct.pack_into('<I',out,12+i*16+8,entries[i][2]+delta)
    updated = sections(out)
    parsed = meshes(out,start,start+old_size+delta)
    for old,new in zip(parts,parsed):
        if old['name'] != part['name']:
            assert source[old['start']:old['end']] == out[new['start']:new['end']]
    for i,(old,new) in enumerate(zip(entries,updated)):
        if i != gi:
            assert source[old[2]:old[2]+old[1]] == out[new[2]:new[2]+new[1]]
    report = dict(sourceSha256=SOURCE_SHA,outputSha256=hashlib.sha256(out).hexdigest(),
                  part=part['name'],beforeVertices=len(part['vertices']),afterVertices=len(vertices),
                  beforeTriangles=len(part['faces']),afterTriangles=len(faces),sizeDelta=delta,
                  unchanged='Other five meshes; all non-geometry section payloads including animation',
                  runtimeStatus='UNVERIFIED: requires Windows game test')
    return bytes(out),report

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();out,report=build(a.source.read_bytes())
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_bytes(out);a.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
