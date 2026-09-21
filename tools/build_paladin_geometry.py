"""Pinned paladin refinement: rigid armor plus weighted lower-leg subdivision.
Not a general SAM exporter. New skinning requires in-game validation.
"""
import argparse, hashlib, json, math, struct
from pathlib import Path
from probe_sam_topology import SOURCE_SHA, sections

def parse(b):
    entry=next(e for e in sections(b) if e[0]==3)
    o=entry[2];parts=[]
    while o<entry[2]+entry[1]:
        start=o;header=b[o:o+40];nv,nf,mat,kind=struct.unpack_from('<4H',b,o+40);o+=48
        v=[];weights=[]
        for _ in range(nv):
            v.append(list(struct.unpack_from('<8f',b,o)));o+=32;w=[]
            if kind==2:
                n=struct.unpack_from('<H',b,o)[0];o+=2
                w=[struct.unpack_from('<Hf',b,o+6*j) for j in range(n)];o+=6*n
            weights.append(w)
        faces=[struct.unpack_from('<3H',b,o+6*j) for j in range(nf)];o+=6*nf
        parts.append(dict(name=header.split(b'\0')[0].decode(),header=header,kind=kind,mat=mat,v=v,w=weights,f=faces,raw=b[start:o]))
    assert o==entry[2]+entry[1]
    return parts

def norm(v):
    length=math.sqrt(sum(x*x for x in v))
    return [x/length for x in v] if length>1e-10 else [0,0,1]

def refine(p, curved):
    v=p['v'];w=p['w'];cache={};faces=[]
    # Same-position seam vertices share curvature normals, but retain their UVs.
    normals={}
    for a in v:
        key=tuple(round(x,5) for x in a[:3]);old=normals.setdefault(key,[0,0,0])
        for k in range(3):old[k]+=a[k+3]
    normals={k:norm(n) for k,n in normals.items()}
    def edge(a,b):
        key=tuple(sorted((a,b)))
        if key in cache:return cache[key]
        va,vb=v[a],v[b];pos=[(va[k]+vb[k])/2 for k in range(3)]
        if curved(a) and curved(b):
            na=normals[tuple(round(x,5) for x in va[:3])];nb=normals[tuple(round(x,5) for x in vb[:3])]
            # Preserve sharp junctions; only interpolate compatible surface normals.
            if sum(x*y for x,y in zip(na,nb))>0.15:
                delta=[0,0,0]
                for vv,nn in ((va,na),(vb,nb)):
                    d=sum((pos[k]-vv[k])*nn[k] for k in range(3))
                    for k in range(3):delta[k]-=0.5*d*nn[k]
                size=math.sqrt(sum((va[k]-vb[k])**2 for k in range(3)))
                length=math.sqrt(sum(x*x for x in delta));limit=0.18*size
                if length>limit:delta=[x*limit/length for x in delta]
                pos=[pos[k]+delta[k] for k in range(3)]
                if p['kind']==2:pos[2]=max(0.03,pos[2])
        n=norm([va[k]+vb[k] for k in range(3,6)])
        ww={}
        for idx in (a,b):
            for bone,weight in w[idx]:ww[bone]=ww.get(bone,0)+weight*.5
        assert len(ww)<=4,'New edge exceeds observed four-weight limit'
        total=sum(ww.values())
        neww=[(bone,weight/total) for bone,weight in sorted(ww.items())] if ww else []
        cache[key]=len(v);v.append([*pos,*n,(va[6]+vb[6])/2,(va[7]+vb[7])/2]);w.append(neww)
        return cache[key]
    # Split whole rigid parts; lower-leg faces only for body. Shared boundary
    # edges split neighbors too, avoiding T-junctions at the transition.
    selected=set()
    for face in p['f']:
        if all(curved(i) for i in face):
            for a,b in zip(face,face[1:]+face[:1]):selected.add(tuple(sorted((a,b))))
    for a,b,c in p['f']:
        edges=[(a,b),(b,c),(c,a)];m=[edge(x,y) if tuple(sorted((x,y))) in selected else None for x,y in edges]
        count=sum(x is not None for x in m)
        if count==0:faces.append((a,b,c))
        elif count==3:
            ab,bc,ca=m;faces.extend(((a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca)))
        elif count==1:
            j=next(i for i,x in enumerate(m) if x is not None);x,y,z=(a,b,c)[j:]+(a,b,c)[:j];mid=m[j];faces.extend(((x,mid,z),(mid,y,z)))
        else:
            j=next(i for i,x in enumerate(m) if x is None);x,y,z=(a,b,c)[j:]+(a,b,c)[:j];yz=m[(j+1)%3];zx=m[(j+2)%3];faces.extend(((z,zx,yz),(x,y,yz),(x,yz,zx)))
    p['f']=faces

def build(b):
    assert hashlib.sha256(b).hexdigest()==SOURCE_SHA
    parts=parse(b);report=[];lower={30,31,35,36}
    for p in parts:
        nv,nf=len(p['v']),len(p['f'])
        if p['name'] in ('naplechnik1','naplechnik2','shlem'):
            for _ in range(2):refine(p,lambda i:True)
        elif p['name']=='object03':
            def eligible(i):return bool(p['w'][i]) and {j for j,_ in p['w'][i]}<=lower
            for _ in range(2):refine(p,eligible)
        else:continue
        report.append(dict(part=p['name'],beforeVertices=nv,afterVertices=len(p['v']),beforeTriangles=nf,afterTriangles=len(p['f'])))
    chunks=[]
    for p in parts:
        if p['name'] in ('shit','mech'):chunks.append(p['raw']);continue
        v,w,f=p['v'],p['w'],p['f'];assert len(v)<65536 and len(f)<65536
        chunk=p['header']+struct.pack('<4H',len(v),len(f),p['mat'],p['kind'])
        for vv,ww in zip(v,w):
            assert all(math.isfinite(x) for x in vv)
            chunk+=struct.pack('<8f',*vv)
            if p['kind']==2:
                assert 1<=len(ww)<=4 and abs(sum(x for _,x in ww)-1)<1e-5
                chunk+=struct.pack('<H',len(ww))+b''.join(struct.pack('<Hf',*x) for x in ww)
        assert all(max(t)<len(v) for t in f)
        chunk+=b''.join(struct.pack('<3H',*t) for t in f);chunks.append(chunk)
    entries=sections(b);gi=next(i for i,e in enumerate(entries) if e[0]==3);_,size,start,_=entries[gi];geo=b''.join(chunks);delta=len(geo)-size
    out=bytearray(b[:start]+geo+b[start+size:]);struct.pack_into('<I',out,16+16*gi,len(geo))
    for i in range(gi+1,len(entries)):struct.pack_into('<I',out,20+16*i,entries[i][2]+delta)
    newentries=sections(out)
    for i,(old,new) in enumerate(zip(entries,newentries)):
        if i!=gi:assert b[old[2]:old[2]+old[1]]==out[new[2]:new[2]+new[1]]
    reread=parse(out);assert len(reread)==6
    for old,new in zip(parse(b),reread):
        if old['name'] in ('shit','mech'):assert old['raw']==new['raw']
        # Existing records retain exact vertex attributes and weights.
        assert old['v']==new['v'][:len(old['v'])]
        assert old['w']==new['w'][:len(old['w'])]
    return bytes(out),dict(parts=report,sourceSha256=SOURCE_SHA,outputSha256=hashlib.sha256(out).hexdigest(),runtimeStatus='unverified',animationBytesUnchanged=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    out,report=build(a.source.read_bytes());a.output.write_bytes(out);a.report.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
