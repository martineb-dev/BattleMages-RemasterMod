"""Pinned v5 -> v6 equipment pass. Requires numpy and Pillow. Private inputs only."""
import argparse, hashlib, json, struct
from collections import Counter
from pathlib import Path
import numpy as np
from PIL import Image
from build_paladin_geometry import parse
from probe_sam_topology import sections
SOURCE='bbbdbe412d9dfb61ebfd4860137dd2cfbb6a63d4b2098d5cc98ee2d7d220353b'
TEXTURE='83fee9e629420e85881237c21422c3c5ebb6b9eb1e73ff4adbcc3cde206019cc'

def unit(x):
    return x/max(np.linalg.norm(x),1e-10)

def solid_surface(p, ids, tex, thickness, rim):
    old=np.array(p['v']);verts=[];faces=[];lookup={}
    def alpha(v):
        uv=np.clip(v[6:8],0,1)*(tex.shape[0]-1);xy=np.floor(uv).astype(int);hi=np.minimum(xy+1,tex.shape[0]-1);t=uv-xy
        return float((1-t[0])*(1-t[1])*tex[xy[1],xy[0]]+t[0]*(1-t[1])*tex[xy[1],hi[0]]+(1-t[0])*t[1]*tex[hi[1],xy[0]]+t[0]*t[1]*tex[hi[1],hi[0]])-128
    def add(v):
        key=tuple(np.round(v[:3],5))
        if key not in lookup:lookup[key]=len(verts);verts.append(v)
        return lookup[key]
    def clip(tri):
        out=[]
        for a,b in zip(tri,tri[1:]+tri[:1]):
            aa,bb=alpha(a),alpha(b)
            if aa>=0:out.append(a)
            if (aa>=0)!=(bb>=0):
                # Bisection samples actual alpha rather than assuming linear pixels.
                lo,hi=0.,1.
                for _ in range(14):
                    mid=(lo+hi)/2
                    if (alpha(a+(b-a)*mid)>=0)==(aa>=0):lo=mid
                    else:hi=mid
                out.append(a+(b-a)*((lo+hi)/2))
        if len(out)>=3:
            q=[add(v) for v in out]
            for j in range(1,len(q)-1):
                f=(q[0],q[j],q[j+1]);vv=[verts[k][:3] for k in f]
                if np.linalg.norm(np.cross(vv[1]-vv[0],vv[2]-vv[0]))>1e-8:faces.append(f)
    n=20
    for idx in ids:
        a,b,c=old[list(p['f'][idx])]
        def point(i,j):return a+(b-a)*(i/n)+(c-a)*(j/n)
        for i in range(n):
            for j in range(n-i):
                clip([point(i,j),point(i+1,j),point(i,j+1)])
                if i+j<n-1:clip([point(i+1,j),point(i+1,j+1),point(i,j+1)])
    assert faces
    # Source front/back can share a geometric seam; preserve source-facing orientation.
    counts=Counter(tuple(sorted((a,b))) for f in faces for a,b in zip(f,f[1:]+f[:1]))
    assert max(counts.values())<=2
    boundary=[(a,b) for f in faces for a,b in zip(f,f[1:]+f[:1]) if counts[tuple(sorted((a,b)))]==1]
    base=np.array(verts);direction=unit(np.mean(base[:,3:6],axis=0));center=base[:,:3].mean(axis=0)
    front=base.copy();back=base.copy();front[:,:3]+=direction*thickness*.5;back[:,:3]-=direction*thickness*.5
    # Reuse original reverse-side UV through barycentric interpolation.
    back_ids=range(6,12) if p['name']=='shit' else (12,13)
    for i,v in enumerate(base):
        best=None
        for idx in back_ids:
            vv=old[list(p['f'][idx])];mat=np.stack((vv[1,:3]-vv[0,:3],vv[2,:3]-vv[0,:3]),axis=1)
            st=np.linalg.lstsq(mat,v[:3]-vv[0,:3],rcond=None)[0];weights=np.array([1-st.sum(),*st]);err=np.linalg.norm(weights@vv[:,:3]-v[:3])+max(0,-weights.min())*100
            if best is None or err<best[0]:best=(err,weights@vv[:,6:8])
        back[i,6:8]=best[1];back[i,3:6]=-front[i,3:6]
    result=list(front)+list(back);nv=len(front);output=list(faces)+[(c+nv,b+nv,a+nv) for a,b,c in faces]
    def quad(points,normal,uv):
        start=len(result)
        result.extend(np.array([*pos,*normal,*uv]) for pos in points)
        output.extend(((start,start+1,start+2),(start,start+2,start+3)))
    for a,b in boundary:
        outward=unit(np.cross(front[b,:3]-front[a,:3],direction))
        quad([front[b,:3],front[a,:3],back[a,:3],back[b,:3]],outward,(.3,.96))
        if rim:
            oa,ob=front[a,:3]+direction*.035,front[b,:3]+direction*.035
            # Narrow raised band towards shield center, keeping original outline.
            ia=oa+(center-base[a,:3])*.025+direction*.045
            ib=ob+(center-base[b,:3])*.025+direction*.045
            quad([oa,ob,ib,ia],direction,(.3,.96))
    return result,output,dict(surfaceTriangles=len(faces),boundaryEdges=len(boundary),thickness=thickness)

def build(b,dds):
    assert hashlib.sha256(b).hexdigest()==SOURCE
    assert hashlib.sha256(dds).hexdigest()==TEXTURE
    import io
    tex=np.asarray(Image.open(io.BytesIO(dds)).convert('RGBA'))[:,:,3].astype(float)
    parts=parse(b);report=[]
    for p in parts:
        if p['name']=='shit':
            v,f,info=solid_surface(p,range(6),tex,.22,True)
        elif p['name']=='mech':
            old=np.array(p['v']);v=list(old.copy());f=list(p['f'])
            # Increase blade central ridge separation; keep edge and tip positions.
            for a,c in ((0,6),(3,9)):
                midpoint=(old[a,:3]+old[c,:3])/2;normal=unit(old[a,3:6]);half=max(np.linalg.norm(old[a,:3]-old[c,:3])/2,.10)
                v[a][:3]=midpoint+normal*half;v[c][:3]=midpoint-normal*half
            guard_v,guard_f,info=solid_surface(p,(14,15),tex,.16,False)
            f=[face for i,face in enumerate(f) if i not in (12,13,14,15)]
            offset=len(v);v+=guard_v;f += [tuple(i+offset for i in face) for face in guard_f]
        else:continue
        report.append(dict(part=p['name'],beforeTriangles=len(p['f']),afterTriangles=len(f),**info))
        p['v']=[list(x) for x in v];p['f']=f;p['w']=[[] for _ in v]
    geo=b''
    for p in parts:
        if p['name'] not in ('shit','mech'):geo+=p['raw'];continue
        assert len(p['v'])<65536 and len(p['f'])<65536
        assert all(np.isfinite(v).all() for v in p['v'])
        assert all(max(f)<len(p['v']) for f in p['f'])
        geo+=p['header']+struct.pack('<4H',len(p['v']),len(p['f']),p['mat'],1)
        geo+=b''.join(struct.pack('<8f',*v) for v in p['v'])+b''.join(struct.pack('<3H',*f) for f in p['f'])
    entries=sections(b);gi=next(i for i,e in enumerate(entries) if e[0]==3);_,size,start,_=entries[gi];delta=len(geo)-size
    out=bytearray(b[:start]+geo+b[start+size:]);struct.pack_into('<I',out,16+16*gi,len(geo))
    for i in range(gi+1,len(entries)):struct.pack_into('<I',out,20+16*i,entries[i][2]+delta)
    for i,(a,c) in enumerate(zip(entries,sections(out))):
        if i!=gi:assert b[a[2]:a[2]+a[1]]==out[c[2]:c[2]+c[1]]
    for a,c in zip(parse(b),parse(out)):
        if a['name'] not in ('shit','mech'):assert a['raw']==c['raw']
    return bytes(out),dict(parts=report,totalTriangles=sum(len(p['f']) for p in parts),sourceSha256=SOURCE,outputSha256=hashlib.sha256(out).hexdigest(),runtimeStatus='unverified')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('texture',type=Path);p.add_argument('output',type=Path);p.add_argument('--report',required=True,type=Path);a=p.parse_args()
    out,report=build(a.source.read_bytes(),a.texture.read_bytes());a.output.write_bytes(out);a.report.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
