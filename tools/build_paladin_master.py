"""Paladin Master Candidate 01: source-pinned full geometry pass.
Private SAM/DDS inputs are required. Outputs preserve source skeleton/animations.
Requires NumPy. No image generation or texture regeneration occurs in this build.
"""
import argparse, copy, hashlib, json, math, struct
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
from build_paladin_geometry import parse
from probe_sam_topology import sections, SOURCE_SHA

V6_SHA='cc0cdf96c9606f2d4f78e139156edd73b66f319a08598b9db143b24feeda7318'

def unit(v):
    v=np.asarray(v,dtype=float);return v/max(np.linalg.norm(v),1e-12)

def blendweights(a,b):
    d=defaultdict(float)
    for w in (a,b):
        for k,x in w:d[k]+=x*.5
    kept=sorted(d.items(),key=lambda x:(-x[1],x[0]))[:4];s=sum(x for _,x in kept)
    return [(k,x/s) for k,x in kept] if s else []

def recalc(p):
    pos=np.array(p['v'])[:,:3];acc=np.zeros_like(pos)
    for a,b,c in p['f']:
        n=np.cross(pos[b]-pos[a],pos[c]-pos[a])
        for i in (a,b,c):acc[i]+=n
    for i,n in enumerate(acc):
        if np.linalg.norm(n)>1e-10:p['v'][i][3:6]=unit(n).tolist()

def finish_normals(p):
    # Split only hard/re-entrant corners where averaging would turn a vertex
    # normal against its face. Preserve position, UV and skinning at each split.
    recalc(p);original=np.array(p['v']);faces=[];splits={}
    for face in p['f']:
        a,b,c=original[list(face),:3];normal=unit(np.cross(b-a,c-a));fixed=[]
        for i in face:
            if np.dot(original[i,3:6],normal)<.15:
                key=(i,*np.round(normal,6))
                if key not in splits:
                    vv=original[i].copy();vv[3:6]=normal
                    splits[key]=len(p['v']);p['v'].append(vv.tolist());p['w'].append(list(p['w'][i]))
                fixed.append(splits[key])
            else:fixed.append(i)
        faces.append(tuple(fixed))
    # Remove vertices belonging only to deleted/replaced surfaces.
    used=sorted({i for f in faces for i in f});lookup={i:j for j,i in enumerate(used)}
    p['v']=[p['v'][i] for i in used];p['w']=[p['w'][i] for i in used]
    p['f']=[tuple(lookup[i] for i in f) for f in faces]

def subdivide(p,curvature=.8):
    v=p['v'];weights=p['w'];faces=[];cache={}
    # Share geometric curvature at coincident UV seams without welding UVs.
    normals=defaultdict(lambda:np.zeros(3))
    for a in v:normals[tuple(np.round(a[:3],5))]+=unit(a[3:6])
    normals={k:unit(n) for k,n in normals.items()}
    def edge(a,b):
        key=tuple(sorted((a,b)))
        if key in cache:return cache[key]
        va,vb=np.array(v[a]),np.array(v[b]);mid=(va+vb)*.5;d=np.zeros(3)
        ns=[normals[tuple(np.round(x[:3],5))] for x in (va,vb)]
        if np.dot(*ns)>.12:
            for vv,nn in zip((va,vb),ns):d-=.5*np.dot(mid[:3]-vv[:3],nn)*nn
            cap=np.linalg.norm(va[:3]-vb[:3])*.18
            if np.linalg.norm(d)>cap:d=unit(d)*cap
            mid[:3]+=d*curvature
        mid[3:6]=unit(va[3:6]+vb[3:6]);mid[2]=max(.03,mid[2])
        idx=len(v);v.append(mid.tolist());weights.append(blendweights(weights[a],weights[b]));cache[key]=idx
        return idx
    for a,b,c in p['f']:
        ab,bc,ca=edge(a,b),edge(b,c),edge(c,a)
        faces.extend(((a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca)))
    p['f']=faces

def fresh(p):
    return dict(p,v=[],w=[],f=[])

def vertex(p,pos,uv,w=None):
    p['v'].append([*map(float,pos),0.,0.,1.,*map(float,uv)]);p['w'].append(w or []);return len(p['v'])-1

def tri(p,a,b,c,normal=None):
    if normal is not None:
        vv=np.array(p['v']);n=np.cross(vv[b,:3]-vv[a,:3],vv[c,:3]-vv[a,:3])
        if np.dot(n,normal)<0:b,c=c,b
    p['f'].append((a,b,c))

def joinrings(p,rings,center=None):
    n=len(rings[0])
    for ra,rb in zip(rings,rings[1:]):
        for j in range(n):
            k=(j+1)%n
            for f in ((ra[j],rb[j],rb[k]),(ra[j],rb[k],ra[k])):
                norm=None
                if center is not None:norm=np.mean([p['v'][i][:3] for i in f],axis=0)-center
                tri(p,*f,normal=norm)

def uv_project(pos,source,face_ids):
    best=(float('inf'),None,None)
    for idx in face_ids:
        f=source['f'][idx];vv=np.array([source['v'][i] for i in f]);mat=np.stack((vv[1,:3]-vv[0,:3],vv[2,:3]-vv[0,:3]),axis=1)
        st=np.linalg.lstsq(mat,pos-vv[0,:3],rcond=None)[0];w=np.array([1-st.sum(),*st]);err=np.linalg.norm(w@vv[:,:3]-pos)+max(0,-w.min())*20
        if err<best[0]:best=(err,w@vv[:,6:8],w@vv[:,:3])
    return best[1]

def boundary_loop(p,faces):
    cnt=Counter(tuple(sorted(e)) for f in faces for e in zip(f,f[1:]+f[:1]));edges=[e for e,n in cnt.items() if n==1];adj=defaultdict(list)
    for a,b in edges:adj[a].append(b);adj[b].append(a)
    assert all(len(a)==2 for a in adj.values())
    unseen=set(adj);loops=[]
    while unseen:
        start=min(unseen);prev=None;cur=start;loop=[]
        while True:
            loop.append(cur);unseen.discard(cur);nxt=next(i for i in adj[cur] if i!=prev)
            prev,cur=cur,nxt
            if cur==start:break
        loops.append(loop)
    return max(loops,key=lambda ids:sum(np.linalg.norm(np.array(p['v'][a][:3])-p['v'][b][:3]) for a,b in zip(ids,ids[1:]+ids[:1])))

def resample_closed(points,n):
    pts=np.array(points);d=np.linalg.norm(np.roll(pts,-1,axis=0)-pts,axis=1);s=np.r_[0,np.cumsum(d)];q=np.vstack((pts,pts[0]));return np.array([[np.interp(t,s,q[:,k]) for k in range(3)] for t in np.linspace(0,s[-1],n,endpoint=False)])

def shield(original,v6):
    out=fresh(original);loop=boundary_loop(v6,v6['f'][:2118]);outline=resample_closed([v6['v'][i][:3] for i in loop],56)
    # A gentle geometric fairing removes pixel-sized notches from alpha tracing.
    outline=.72*outline+.14*np.roll(outline,1,axis=0)+.14*np.roll(outline,-1,axis=0)
    n=unit(np.mean(np.array(original['v'])[:7,3:6],axis=0));outline-=n*.11
    center=np.array(original['v'][2][:3]);outline=center+(outline-center)*.985;rings=[]
    for side in (1,-1):
        part_rings=[]
        for r in (.08,.27,.50,.73,.90,.96,1.):
            ring=[]
            for edge in outline:
                pos=center+(edge-center)*r;uv=uv_project(pos,original,range(6) if side==1 else range(6,12))
                raised=0.
                if side==1:
                    raised=.09*math.exp(-((uv[0]-.815)/.016)**2)+.065*math.exp(-((uv[1]-.832)/.012)**2)
                bulge=.16*(1-r*r) if side==1 else 0
                offset=side*.095+raised+bulge+(.035 if r>.95 and side==1 else 0)
                ring.append(vertex(out,pos+n*offset,uv))
            part_rings.append(ring)
        # Source-facing winding explicitly set for front and rear surfaces.
        for ra,rb in zip(part_rings,part_rings[1:]):
            for j in range(56):
                k=(j+1)%56
                tri(out,ra[j],rb[j],rb[k],n*side);tri(out,ra[j],rb[k],ra[k],n*side)
        ci=vertex(out,center+n*(side*.095+(.16 if side==1 else 0)),uv_project(center,original,range(6) if side==1 else range(6,12)))
        for j in range(56):tri(out,ci,part_rings[0][j],part_rings[0][(j+1)%56],n*side)
        rings.append(part_rings[-1])
    # Independent rim vertices give a crisp edge and a narrow bevel.
    front,back=rings
    for j in range(56):
        k=(j+1)%56;pos=[out['v'][i][:3] for i in (front[j],front[k],back[k],back[j])];ids=[vertex(out,x,(.30,.96)) for x in pos];outward=unit((outline[j]+outline[k])*.5-center)
        tri(out,ids[0],ids[1],ids[2],outward);tri(out,ids[0],ids[2],ids[3],outward)
    recalc(out);return out

def sword(original,previous):
    out=fresh(original);v=np.array(original['v']);base=v[[2,3,5],:3].mean(0);tip=v[12,:3];axis=unit(tip-base);length=np.linalg.norm(tip-base);normal=unit(v[0,3:6]);normal=unit(normal-axis*np.dot(normal,axis));width=unit(np.cross(normal,axis))
    # Actual cross-section with bevels and a recessed central fuller, both sides.
    fractions=np.array([-1.,-.77,-.26,-.14,.14,.26,.77,1.]);heights=np.array([.008,.075,.145,.097,.097,.145,.075,.008])
    stations=[(0.,.61),(.06,.62),(.30,.59),(.63,.52),(.85,.41),(.94,.24),(.995,.025)]
    sides=[]
    for sign in (1,-1):
        strips=[]
        for t,half in stations:
            row=[]
            for q,h in zip(fractions,heights):
                pos=base+axis*(length*t)+width*q*half+normal*h*sign*(1-.65*t)
                uv=(.201+(.597-.201)*t,.961+q*.019)
                row.append(vertex(out,pos,uv))
            strips.append(row)
        for ra,rb in zip(strips,strips[1:]):
            for j in range(7):
                tri(out,ra[j],rb[j],rb[j+1],normal*sign);tri(out,ra[j],rb[j+1],ra[j+1],normal*sign)
        ti=vertex(out,tip,(.597,.961))
        for j in range(7):tri(out,strips[-1][j],ti,strips[-1][j+1],normal*sign)
        sides.append(strips)
    # Seal blade edges including root. Upper and lower tip vertices coincide.
    for j in (0,7):
        for k in range(len(stations)-1):
            a,b=sides[0][k][j],sides[0][k+1][j];c,d=sides[1][k+1][j],sides[1][k][j];tri(out,a,b,c,width*(-1 if j==0 else 1));tri(out,a,c,d,width*(-1 if j==0 else 1))
    for j in (0,7):
        tipid=vertex(out,tip,(.597,.961))
        tri(out,sides[0][-1][j],tipid,sides[1][-1][j],width*(-1 if j==0 else 1))
    for j in range(7):
        a,b=sides[0][0][j],sides[0][0][j+1];c,d=sides[1][0][j+1],sides[1][0][j];tri(out,a,c,b,-axis);tri(out,a,d,c,-axis)
    # Retain the distinctive wing-shaped guard and its original ornament layout.
    # The verified v6 alpha contour supplies the silhouette; add real cambered
    # metal depth, retaining independent front/back/rim vertices and their UVs.
    guardfaces=previous['f'][22:]
    assert len(guardfaces)==1508 and min(min(f) for f in guardfaces)==46
    ids=sorted({i for f in guardfaces for i in f});sourcev=np.array(previous['v'])
    frontfaces=previous['f'][22:22+547]
    counts=Counter(tuple(sorted(e)) for f in frontfaces for e in zip(f,f[1:]+f[:1]))
    boundary=sorted({i for e,c in counts.items() if c==1 for i in e})
    gn=unit(sourcev[46,3:6]);plane=sourcev[46,:3]-gn*.08
    edgepos=sourcev[boundary,:3];edgepos-=np.outer((edgepos-plane)@gn,gn)
    remap={}
    for i in ids:
        vv=sourcev[i].copy();signed=np.dot(vv[:3]-plane,gn);flat=vv[:3]-gn*signed
        distance=np.min(np.linalg.norm(edgepos-flat,axis=1))
        relief=.035+.085*min(distance/.28,1.)
        vv[:3]+=gn*(1 if signed>=0 else -1)*relief
        remap[i]=vertex(out,vv[:3],vv[6:8])
    out['f'].extend(tuple(remap[i] for i in f) for f in guardfaces)
    # Rounded decorated grip with raised winding.
    rings=[];griplen=2.65
    for k in range(31):
        t=k/30;r=.235*(1-.12*math.sin(math.pi*t));ring=[]
        for j in range(16):
            a=2*math.pi*j/16;rr=r+.016*math.cos(2*math.pi*(t*8-j/16));pos=base-axis*(.25+griplen*t)+width*rr*math.cos(a)+normal*rr*math.sin(a)
            ring.append(vertex(out,pos,(.585+.044*j/16,.671-.218*t)))
        rings.append(ring)
    joinrings(out,rings,base-axis*1.5)
    # Pommel: closed flattened oval, adding a physical end to the grip.
    pc=base-axis*3.;rings=[]
    for t in np.linspace(-.96,.96,11):
        ring=[];rr=math.sqrt(1-t*t)
        for j in range(16):
            a=2*math.pi*j/16;pos=pc+axis*.40*t+width*.32*rr*math.cos(a)+normal*.24*rr*math.sin(a);ring.append(vertex(out,pos,(.607+.012*math.cos(a),.55+.015*t)))
        rings.append(ring)
    joinrings(out,rings,pc)
    for ring,sign in ((rings[0],-1),(rings[-1],1)):
        ci=vertex(out,pc+axis*.40*sign,(.606,.55))
        for j in range(16):tri(out,ci,ring[j],ring[(j+1)%16],axis*sign)
    recalc(out);return out

def boots(body,source):
    # Replace the old foot wedges; retain the upper shin and existing bone IDs.
    for foot,shin in ((31,30),(36,35)):
        ids=[i for i,w in enumerate(source['w']) if {b for b,_ in w}<={foot,shin} and source['v'][i][2]<2.2]
        vv=np.array([source['v'][i][:3] for i in ids]);ankle=vv[vv[:,2]>1.2].mean(0);ankle[2]=0
        xy=vv[:,:2];cov=np.cov(xy.T);eigenvalues,eigenvectors=np.linalg.eigh(cov);forward=np.r_[eigenvectors[:,-1],0.]
        if np.dot(forward[:2],xy.mean(0)-ankle[:2])<0:forward=-forward
        side=np.cross([0,0,1],forward);rings=[]
        params=[(.055,.62,1.83,.82),(.17,.62,1.85,.84),(.38,.68,1.79,.84),(.64,.50,1.48,.81),(1.02,.16,1.0,.73),(1.45,0.,.70,.64),(1.77,0.,.64,.62)]
        for z,offset,rl,rw in params:
            ring=[]
            for j in range(24):
                a=2*math.pi*j/24;pos=ankle+forward*(offset+rl*math.cos(a))+side*rw*math.sin(a)+np.array([0,0,z]);t=max(0,min(1,(z-.85)/1.0))*.48;ww=[(foot,1-t),(shin,t)] if t>0 else [(foot,1.)]
                # Existing steel boot island; longitudinal mapping reads as sabatons.
                uv=(.02+.16*(.5+.5*math.sin(a)),.66+.12*(1-z/1.9))
                ring.append(vertex(body,pos,uv,ww))
            rings.append(ring)
        center=ankle+forward*.62+np.array([0,0,.7]);joinrings(body,rings,center)
        ci=vertex(body,ankle+forward*.62+np.array([0,0,.055]),(.10,.75),[(foot,1.)])
        for j in range(24):tri(body,ci,rings[0][j],rings[0][(j+1)%24],[0,0,-1])
        # Four real overlapping sabaton plates follow the upper boot surface.
        # Solve the elliptical shell for height, then lift the plate above it.
        profile=np.array(params)
        def shellheight(along,across):
            lo,hi=.17,1.77
            for _ in range(25):
                z=(lo+hi)*.5
                off,rl,rw=[np.interp(z,profile[:,0],profile[:,i]) for i in (1,2,3)]
                if ((along-off)/rl)**2+(across/rw)**2<1:lo=z
                else:hi=z
            return (lo+hi)*.5
        for row in range(4):
            start=.62+row*.43;rows=[]
            for k in range(4):
                along=start+k*.13
                width=.74*math.sqrt(max(.08,1-((along-.55)/2.05)**2))
                curve=[]
                for j in range(17):
                    t=-1+2*j/16;across=width*t
                    lift=(.04 if k<3 else .075)*(1-.25*t*t)
                    z=shellheight(along,across)+lift
                    pos=ankle+forward*along+side*across+np.array([0,0,z])
                    uv=(.026+.017*j/16,.554+.031*k/3)
                    curve.append(vertex(body,pos,uv,[(foot,1.)]))
                rows.append(curve)
            for ra,rb in zip(rows,rows[1:]):
                for j in range(16):
                    tri(body,ra[j],rb[j],rb[j+1],[0,0,1]);tri(body,ra[j],rb[j+1],ra[j+1],[0,0,1])
            # Fold the leading lip down to the shell, leaving a crisp joint.
            edge=rows[-1]
            for j in range(16):
                a,b=[np.array(body['v'][i][:3]) for i in edge[j:j+2]]
                q=[vertex(body,x,(.3,.96),[(foot,1.)]) for x in (a,b,b-np.array([0,0,.06]),a-np.array([0,0,.06]))]
                tri(body,q[0],q[1],q[2],forward);tri(body,q[0],q[2],q[3],forward)

def body_master(original):
    p=copy.deepcopy(original)
    # Remove feet under the new armor; ankle/upper-shin transitions remain.
    def footface(f):
        bones={b for i in f for b,_ in p['w'][i]}
        return (bones<={30,31} or bones<={35,36}) and max(p['v'][i][2] for i in f)<2.2
    p['f']=[f for f in p['f'] if not footface(f)]
    for i,(v,w) in enumerate(zip(p['v'],p['w'])):
        if {b for b,_ in w}<={2,3,4,6} and 10.2<v[2]<14:
            v[0]*=1.06;v[1]*=1.06
    for _ in range(2):subdivide(p,.9)
    # Sculpt folds, buckle and segmented forearm plates in their original UV islands.
    for v,w in zip(p['v'],p['w']):
        u,t=v[6:8];n=unit(v[3:6]);offset=0.
        if .50<u<.985 and .405<t<.635:
            fade=math.sin(math.pi*(t-.405)/.23)**2
            offset=.105*math.sin((u-.5)*math.pi*42)*fade
        if .695<u<.768 and .300<t<.369:
            r=((u-.731)/.037)**2+((t-.336)/.035)**2
            if r<1:offset+=.20*(1-r)**.6
        bones={b for b,_ in w}
        if bones & {11,12,21,22} and u<.36 and .14<t<.42:
            offset+=.055*(.5+.5*math.cos((t-.15)*math.pi*32))
        v[:3]=(np.array(v[:3])+n*offset).tolist()
    boots(p,original);recalc(p);return p

def rigid_master(original):
    p=copy.deepcopy(original)
    for _ in range(2):subdivide(p,1.0)
    # Remove residual pointed corners with a small, seam-shared fairing pass.
    pos=np.array(p['v'])[:,:3];groups=defaultdict(list)
    for i,x in enumerate(pos):groups[tuple(np.round(x,5))].append(i)
    adj=defaultdict(set)
    for f in p['f']:
        for a,b in zip(f,f[1:]+f[:1]):adj[a].add(b);adj[b].add(a)
    new=pos.copy()
    for ids in groups.values():
        neigh=set(j for i in ids for j in adj[i]);mean=pos[list(neigh)].mean(0);delta=mean-pos[ids[0]]
        maxmove=.05 if p['name']=='shlem' else .09
        if np.linalg.norm(delta)>maxmove:delta=unit(delta)*maxmove
        new[ids]=pos[ids]+delta*.65
    for i,x in enumerate(new):p['v'][i][:3]=x.tolist()
    # Raised original shoulder ornament border (UV elliptical island).
    if p['name'].startswith('naplechnik'):
        for v in p['v']:
            u,t=v[6:8];rr=((u-.402)/.047)**2+((t-.338)/.085)**2
            offset=.065*math.exp(-((math.sqrt(rr)-.83)/.08)**2)
            v[:3]=(np.array(v[:3])+unit(v[3:6])*offset).tolist()
    recalc(p);return p

def serialize(p):
    assert len(p['v'])<65536 and len(p['f'])<65536
    b=p['header']+struct.pack('<4H',len(p['v']),len(p['f']),p['mat'],p['kind'])
    for v,w in zip(p['v'],p['w']):
        assert all(math.isfinite(x) for x in v)
        b+=struct.pack('<8f',*v)
        if p['kind']==2:
            assert 1<=len(w)<=4 and abs(sum(x for _,x in w)-1)<1e-5
            b+=struct.pack('<H',len(w))+b''.join(struct.pack('<Hf',*x) for x in w)
    for f in p['f']:assert min(f)>=0 and max(f)<len(p['v'])
    return b+b''.join(struct.pack('<3H',*f) for f in p['f'])

def build(original,v6):
    assert hashlib.sha256(original).hexdigest()==SOURCE_SHA
    assert hashlib.sha256(v6).hexdigest()==V6_SHA
    old=parse(original);previous=parse(v6);result=[]
    for p in old:
        if p['name']=='object03':out=body_master(p)
        elif p['name']=='mech':out=sword(p,next(x for x in previous if x['name']=='mech'))
        elif p['name']=='shit':out=shield(p,next(x for x in previous if x['name']=='shit'))
        else:out=rigid_master(p)
        finish_normals(out)
        result.append(out)
    geo=b''.join(serialize(p) for p in result);entries=sections(original);gi=next(i for i,e in enumerate(entries) if e[0]==3);_,size,start,_=entries[gi];delta=len(geo)-size
    out=bytearray(original[:start]+geo+original[start+size:]);struct.pack_into('<I',out,16+16*gi,len(geo))
    for i in range(gi+1,len(entries)):struct.pack_into('<I',out,20+16*i,entries[i][2]+delta)
    for i,(a,c) in enumerate(zip(entries,sections(out))):
        if i!=gi:assert original[a[2]:a[2]+a[1]]==out[c[2]:c[2]+c[1]]
    parsed=parse(out);report=[]
    for a,b in zip(old,parsed):
        vv=np.array(b['v']);ff=np.array(b['f'])
        cross=np.cross(vv[ff[:,1],:3]-vv[ff[:,0],:3],vv[ff[:,2],:3]-vv[ff[:,0],:3])
        assert np.all(np.linalg.norm(cross,axis=1)>1e-9), 'Degenerate triangle'
        assert np.all(np.einsum('ij,ij->i',cross,np.mean(vv[ff,3:6],axis=1))>0), 'Normal opposes face'
        assert np.allclose(np.linalg.norm(vv[:,3:6],axis=1),1,atol=1e-5)
        assert serialize(b)==b['raw'], 'SAM geometry roundtrip mismatch'
        assert b['name']==a['name'] and b['mat']==a['mat'] and b['kind']==a['kind']
        report.append(dict(part=b['name'],vertices=len(b['v']),triangles=len(b['f']),originalTriangles=len(a['f'])))
    assert {k for p in parsed for w in p['w'] for k,_ in w}<={k for p in old for w in p['w'] for k,_ in w}
    return bytes(out),dict(build='paladin-master-candidate-01',parts=report,totalTriangles=sum(len(p['f']) for p in parsed),sourceSha256=SOURCE_SHA,previousSha256=V6_SHA,outputSha256=hashlib.sha256(out).hexdigest(),animationSectionsUnchanged=True,runtimeStatus='UNVERIFIED',scope='All six mesh parts changed; original rig, clips, material IDs, texture names preserved.')

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('original',type=Path);a.add_argument('v6',type=Path);a.add_argument('output',type=Path);a.add_argument('--report',type=Path,required=True);args=a.parse_args()
    b,r=build(args.original.read_bytes(),args.v6.read_bytes());args.output.write_bytes(b);args.report.write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
