"""Render actual SAM comparison geometry with a simple offline diffuse light.
Not an engine capture: no team-color shader, PBR or animation evaluation.
Requires NumPy and Pillow. Private package directories are CLI inputs.
"""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from build_paladin_geometry import parse

def render(parts,eye,center,scale,W=650,H=650,neutral=False,texture=None):
 tex=texture
 im=np.full((H,W,3),38,dtype=np.uint8);zb=np.full((H,W),-np.inf);center=np.array(center);z=np.array(eye)-center;z=z/np.linalg.norm(z);x=np.cross([0,0,1],z);x/=np.linalg.norm(x);y=np.cross(z,x)
 light=np.array([.3,-.6,.74]);light/=np.linalg.norm(light)
 for m in parts:
  verts=np.array(m['v']);v=verts[:,:3];uv=verts[:,6:8];normals=verts[:,3:6];pos=np.stack([(v-center)@x,(v-center)@y,(v-center)@z],axis=-1);pos[:,0]=W/2+scale*pos[:,0];pos[:,1]=H/2-scale*pos[:,1]
  for f in m['f']:
   f=list(f)
   if np.dot(np.cross(v[f[1]]-v[f[0]],v[f[2]]-v[f[0]]),z)<=0:continue
   t=pos[f];u=uv[f];ns=normals[f];lo=np.maximum(np.floor(t[:,:2].min(0)).astype(int),0);hi=np.minimum(np.ceil(t[:,:2].max(0)).astype(int),[W-1,H-1])
   if np.any(hi<lo):continue
   xx,yy=np.meshgrid(np.arange(lo[0],hi[0]+1)+.5,np.arange(lo[1],hi[1]+1)+.5);a,b,c=t;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
   if abs(den)<1e-8:continue
   w1=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den;w2=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den;w3=1-w1-w2;zz=w1*a[2]+w2*b[2]+w3*c[2];sl=np.s_[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
   uvp=w1[...,None]*u[0]+w2[...,None]*u[1]+w3[...,None]*u[2];tc=np.clip((uvp*(tex.shape[0]-1)).astype(int),0,tex.shape[0]-1);col=tex[tc[...,1],tc[...,0]]
   mask=(w1>=0)&(w2>=0)&(w3>=0)&(zz>zb[sl])&(col[...,3]>=128)
   n=w1[...,None]*ns[0]+w2[...,None]*ns[1]+w3[...,None]*ns[2];n/=np.maximum(np.linalg.norm(n,axis=-1)[...,None],1e-8);shade=.6+.4*np.maximum(n@light,0)
   rgb=np.full(col[...,:3].shape,185) if neutral else col[...,:3]
   im[sl][mask]=np.clip(rgb*shade[...,None],0,255).astype(np.uint8)[mask];zb[sl][mask]=zz[mask]
 return Image.fromarray(im)
def framing(groups,direction,width,height):
    points=np.concatenate([np.array(p['v'])[:,:3] for parts in groups for p in parts])
    z=np.array(direction,dtype=float);z/=np.linalg.norm(z)
    x=np.cross([0,0,1],z);x/=np.linalg.norm(x);y=np.cross(z,x)
    basis=np.stack((x,y,z));projected=points@basis.T
    lo,hi=projected.min(0),projected.max(0);center=((lo+hi)*.5)@basis
    scale=min((width-90)/(hi[0]-lo[0]),(height-100)/(hi[1]-lo[1]))
    return center+z*60,center,scale

def sheet(groups,textures,labels,views,path,font):
    width,height=800,750
    image=Image.new('RGB',(width*2,height*len(views)+120),(38,38,38))
    draw=ImageDraw.Draw(image)
    for i,label in enumerate(labels):draw.text((35+i*width,20),label,font=font,fill='white')
    for row,direction in enumerate(views):
        eye,center,scale=framing(groups,direction,width,height)
        for col,parts in enumerate(groups):
            image.paste(render(parts,eye,center,scale,W=width,H=height,texture=textures[col]),(width*col,65+height*row))
    ImageDraw.Draw(image).text((35,image.height-35),'Actual SAM meshes | same camera, pose and light | offline preview',font=font,fill=(190,190,190))
    image.save(path)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('package',type=Path);ap.add_argument('previous',type=Path);ap.add_argument('--font',type=Path);a=ap.parse_args()
    assets=a.package/'payload/data/models/units/humans'
    original=parse((assets/'bmbefor.sam').read_bytes());after=parse((assets/'bmafter.sam').read_bytes())
    previous=parse((a.previous/'payload/data/models/units/humans/bmafter.sam').read_bytes())
    originaltex=np.array(Image.open(assets/'bmbefor.dds').convert('RGBA'));aftertex=np.array(Image.open(assets/'bmafter.dds').convert('RGBA'))
    font=ImageFont.truetype(str(a.font),22) if a.font else ImageFont.load_default()
    views=[[-32,-42,24],[28,38,24]]
    sheet([original,after],[originaltex,aftertex],['BEFORE: original game','AFTER: Master Candidate 01'],views,a.package/'before-after-model.png',font)
    sheet([previous,after],[aftertex,aftertex],['BEFORE: approved v6 geometry','AFTER: Master Candidate 01'],views,a.package/'v6-to-master-model.png',font)
    swords=[[p for p in group if p['name']=='mech'] for group in (previous,after)]
    sheet(swords,[aftertex,aftertex],['BEFORE: v6 sword','AFTER: rebuilt sword'],[[13,28,30]],a.package/'before-after-sword.png',font)
    legs=[[dict(p,f=[f for f in p['f'] if all(p['w'][j] and {b for b,_ in p['w'][j]}<={30,31,35,36} for j in f)]) for p in group if p['kind']==2] for group in (previous,after)]
    # Frame only referenced vertices for the isolated detail.
    for group in legs:
        for p in group:
            used=sorted({i for f in p['f'] for i in f});lookup={i:j for j,i in enumerate(used)}
            p['v']=[p['v'][i] for i in used];p['f']=[tuple(lookup[i] for i in f) for f in p['f']]
    sheet(legs,[aftertex,aftertex],['BEFORE: v6 boots','AFTER: articulated sabatons'],[[-28,-38,17]],a.package/'before-after-boots.png',font)

if __name__=='__main__':main()
