"""Export the pinned private Realism Study 01 shells to the established SAM layout.

Run with Blender 4.5 Python. This is a legacy-renderer adaptation, not a PBR
renderer upgrade. Study chain links are baked separately, never exported as
half a million triangles. Existing skeleton/clip sections remain byte-identical.
"""
import argparse
import copy
import hashlib
import json
import math
import struct
from collections import defaultdict
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from build_paladin_geometry import parse
from build_paladin_master import fresh, vertex, tri, unit, finish_normals, serialize
from probe_sam_topology import sections, SOURCE_SHA

BLEND_SHA = 'bd7d2f4462d2bd910879fe073642fe5af18b6bdc57a376c5265de43173abdfe3'
MASTER_SHA = '3996dbc6c56a4a038d6bc72859ccc0c70faac0ed878ee652f4ee9db307fc6eab'


def checked(path, digest):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Unsupported source bytes: ' + str(path))
    return data


def skin_transfer(source):
    points = np.asarray(source['v'])[:, :3]
    bvh = BVHTree.FromPolygons(points.tolist(), source['f'], all_triangles=True)
    errors = []

    def sample(pos):
        hit, _, index, distance = bvh.find_nearest(Vector(pos))
        if hit is None:
            raise ValueError('No source surface for skin transfer')
        errors.append(float(distance))
        ids = source['f'][index]
        abc = points[list(ids)]
        st = np.linalg.lstsq(np.stack((abc[1]-abc[0], abc[2]-abc[0]), axis=1), np.array(hit)-abc[0], rcond=None)[0]
        bary = np.maximum([1-st.sum(), *st], 0)
        bary /= bary.sum()
        weights = defaultdict(float)
        for i, fac in zip(ids, bary):
            for bone, weight in source['w'][i]:
                weights[bone] += float(fac)*weight
        kept = sorted(((b,w) for b,w in weights.items() if w > 1e-7), key=lambda x: (-x[1], x[0]))[:4]
        total = sum(w for _,w in kept)
        return [(b,w/total) for b,w in kept]
    return sample, errors


def flat_boots(body, original):
    """Beveled, planar soles and articulated steel uppers in the original foot frames."""
    reports = []
    # A broad toe and squared heel, with small chamfers at their corners.
    outline = np.array([(2.22,-.43),(2.22,.43),(2.07,.62),(1.40,.73),(.20,.73),(-.92,.58),
                        (-1.12,.39),(-1.12,-.39),(-.92,-.58),(.20,-.73),(1.40,-.73),(2.07,-.62)])
    for foot, shin in ((31,30),(36,35)):
        ids = [i for i,w in enumerate(original['w']) if {b for b,_ in w}<={foot,shin} and original['v'][i][2]<2.2]
        source = np.asarray([original['v'][i][:3] for i in ids])
        ankle = source[source[:,2]>1.2].mean(0); ankle[2]=0
        _, eigen = np.linalg.eigh(np.cov(source[:,:2].T))
        forward = np.r_[eigen[:,-1],0.]
        if np.dot(forward[:2],source[:,:2].mean(0)-ankle[:2])<0: forward=-forward
        side = np.cross([0,0,1], forward)
        start = len(body['v'])
        def place(x,y,z): return ankle+forward*x+side*y+np.array([0,0,z])
        def weight(z):
            t=float(np.clip((z-.85)/.92,0,1))*.48
            return [(foot,1-t),(shin,t)] if t else [(foot,1.)]
        # The lower and upper sole rims are duplicated so the sole stays visually crisp.
        for low, high, shrink0, shrink1 in ((.03,.09,.94,1.),(.09,.21,1.,1.),(.21,.27,1.,.95)):
            for j in range(len(outline)):
                k=(j+1)%len(outline)
                points=[place(*(outline[j]*shrink0),low),place(*(outline[k]*shrink0),low),
                        place(*(outline[k]*shrink1),high),place(*(outline[j]*shrink1),high)]
                # Small existing dark leather swatch; no new alpha or team-color region.
                uv=(.075,.060)
                q=[vertex(body,p,uv,[(foot,1.)]) for p in points]
                outward=(points[0]+points[1])*.5-place(.5,0,low)
                tri(body,q[0],q[1],q[2],outward);tri(body,q[0],q[2],q[3],outward)
        # Entire contact face is planar, with rigid foot influence only.
        center=vertex(body,place(.5,0,.03),(.075,.060),[(foot,1.)])
        sole=[vertex(body,place(*(p*.94),.03),(.075,.060),[(foot,1.)]) for p in outline]
        for j in range(len(sole)):tri(body,center,sole[j],sole[(j+1)%len(sole)],[0,0,-1])
        # Separate armor shell: low, broad toe tapering into an ankle collar.
        rings=[];armorstart=len(body['f'])
        levels=[(.27,1.,0.),(.46,.98,0.),(.70,.81,.03),(1.02,.53,.05),(1.42,.43,.02),(1.78,.46,0.)]
        for z, longitudinal, shift in levels:
            r=[]
            widthscale=1. if z<.7 else (1.+.08*(z-.7)/1.08)
            for x,y in outline:
                # Upper cross-sections are centered on the ankle, not the forefoot.
                xx=(x-.55)*longitudinal+(max(0,1-(z-.27)/.8)*.55)+shift
                yy=y*widthscale
                pos=place(xx,yy,z)
                uv=(.023+.155*(y/.73+1)*.5,.66+.12*(1-z/1.9))
                r.append(vertex(body,pos,uv,weight(z)))
            rings.append(r)
        for ra,rb in zip(rings,rings[1:]):
            for j in range(len(outline)):
                k=(j+1)%len(outline)
                outward=np.mean([body['v'][i][:3] for i in (ra[j],ra[k],rb[k],rb[j])],axis=0)-place(.1,0,1.)
                tri(body,ra[j],ra[k],rb[k],outward);tri(body,ra[j],rb[k],rb[j],outward)
        shelltree=BVHTree.FromPolygons([v[:3] for v in body['v']],body['f'][armorstart:],all_triangles=True)
        # Broad overlapping sabaton plates, covering the upper rather than narrow straps.
        for row in range(4):
            rows=[]
            for k in range(3):
                along=.84+row*.30+k*.20
                width=.64 if along<1.9 else .64-(along-1.9)*.9
                ids=[]
                for j in range(13):
                    t=-1+2*j/12
                    pos=place(along,width*t,3.)
                    hit,_,_,_=shelltree.ray_cast(Vector(pos),Vector((0,0,-1)))
                    if hit is None:raise ValueError('Armor plate misses boot shell: '+str((foot,along,width*t)))
                    pos=np.array(hit)+np.array([0,0,.04+(.025 if k==2 else 0)])
                    ids.append(vertex(body,pos,(.055+.09*j/12,.715+.019*k/2),[(foot,1.)]))
                rows.append(ids)
            for ra,rb in zip(rows,rows[1:]):
                for j in range(12):
                    tri(body,ra[j],rb[j],rb[j+1],[0,0,1]);tri(body,ra[j],rb[j+1],ra[j+1],[0,0,1])
        contact=[body['v'][i][2] for i in sole]
        assert max(contact)-min(contact)<1e-10 and min(contact)==.03
        reports.append(dict(footBone=foot,shinBone=shin,soleZ=.03,contactVertices=len(sole),
                            contactPlanarityError=max(contact)-min(contact),newVertices=len(body['v'])-start))
    return reports


def main():
    ap=argparse.ArgumentParser();ap.add_argument('study',type=Path);ap.add_argument('master',type=Path)
    ap.add_argument('original',type=Path);ap.add_argument('output',type=Path);ap.add_argument('--report',type=Path,required=True)
    args=ap.parse_args()
    checked(args.study,BLEND_SHA);master=checked(args.master,MASTER_SHA);original=checked(args.original,SOURCE_SHA)
    sourceparts=parse(master);oldparts=parse(original)
    bpy.ops.wm.open_mainfile(filepath=str(args.study.resolve()),use_scripts=False)
    deps=bpy.context.evaluated_depsgraph_get();result=[];distances=[];bootreport=[]
    for source in sourceparts:
        out=fresh(source)
        names=[source['name']]
        if source['name']=='object03':names.append('Tabard | physical cloth shell')
        transfer,errors=skin_transfer(source) if source['kind']==2 else (None,[])
        for name in names:
            obj=bpy.data.objects[name];evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh()
            mesh.calc_loop_triangles();uv=mesh.uv_layers.active.data;cache={}
            try:
                for face in mesh.loop_triangles:
                    ps=[np.array(mesh.vertices[i].co)*10 for i in face.vertices]
                    if np.linalg.norm(np.cross(ps[1]-ps[0],ps[2]-ps[0]))<1e-9:continue
                    weights=[transfer(p) if transfer else [] for p in ps]
                    if name=='object03':
                        bones={b for w in weights for b,_ in w}
                        if (bones<={30,31} or bones<={35,36}) and max(p[2] for p in ps)<2.2:continue
                    newface=[]
                    for vi,li,pos,w in zip(face.vertices,face.loops,ps,weights):
                        u,v=uv[li].uv;key=(vi,round(float(u),8),round(float(v),8))
                        if key not in cache:cache[key]=vertex(out,pos,(u,1-v),w)
                        newface.append(cache[key])
                    out['f'].append(tuple(newface))
            finally:evaluated.to_mesh_clear()
        if source['name']=='object03':bootreport=flat_boots(out,next(p for p in oldparts if p['name']=='object03'))
        finish_normals(out)
        distances.extend(errors);result.append(out)
    geo=b''.join(serialize(p) for p in result);entries=sections(master);gi=next(i for i,e in enumerate(entries) if e[0]==3)
    _,size,start,_=entries[gi];delta=len(geo)-size
    output=bytearray(master[:start]+geo+master[start+size:]);struct.pack_into('<I',output,16+16*gi,len(geo))
    for i in range(gi+1,len(entries)):struct.pack_into('<I',output,20+16*i,entries[i][2]+delta)
    for i,(old,new) in enumerate(zip(entries,sections(output))):
        if i!=gi:assert master[old[2]:old[2]+old[1]]==output[new[2]:new[2]+new[1]]
    parsed=parse(output);validbones={b for p in sourceparts for w in p['w'] for b,_ in w}
    report=[]
    for old,p in zip(sourceparts,parsed):
        assert (p['name'],p['kind'],p['mat'])==(old['name'],old['kind'],old['mat'])
        assert serialize(p)==p['raw']
        vv=np.asarray(p['v']);ff=np.asarray(p['f']);cross=np.cross(vv[ff[:,1],:3]-vv[ff[:,0],:3],vv[ff[:,2],:3]-vv[ff[:,0],:3])
        assert np.isfinite(vv).all() and np.all(np.linalg.norm(cross,axis=1)>1e-9)
        assert np.allclose(np.linalg.norm(vv[:,3:6],axis=1),1,atol=1e-5)
        assert np.all(np.einsum('ij,ij->i',cross,vv[ff,3:6].mean(1))>0)
        for w in p['w']:
            if p['kind']==2:assert 1<=len(w)<=4 and abs(sum(x for _,x in w)-1)<1e-5 and {b for b,_ in w}<=validbones
        report.append(dict(part=p['name'],vertices=len(p['v']),triangles=len(p['f'])))
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(output)
    record=dict(build='paladin-realism-game-01',sourceStudySha256=BLEND_SHA,sourceMasterSha256=MASTER_SHA,
                outputSha256=hashlib.sha256(output).hexdigest(),parts=report,totalTriangles=sum(p['triangles'] for p in report),
                animationSectionsUnchanged=True,rig='Original SAM skeleton and clips; barycentric skin transfer for study shells',
                boots=bootreport,skinTransferMaxDistanceGameUnits=max(distances),
                renderer='Legacy game materials, not Cycles/PBR',physicalMailInSAM=False,runtimeStatus='UNVERIFIED')
    args.report.write_text(json.dumps(record,indent=2));print(json.dumps(record,indent=2))


if __name__=='__main__':main()
