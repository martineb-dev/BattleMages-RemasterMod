"""Bake study mail relief into legacy diffuse DDS while preserving source BC3 alpha.

No generative texture editing. Only the semantic chainmail region changes; all
other level-zero RGB blocks remain byte-identical. The authoring normal map is
not installed or represented as a supported legacy game shader.
"""
import argparse,hashlib,io,json,struct
from pathlib import Path
import numpy as np
from PIL import Image,ImageFilter

SOURCE='83fee9e629420e85881237c21422c3c5ebb6b9eb1e73ff4adbcc3cde206019cc'
ap=argparse.ArgumentParser();ap.add_argument('source',type=Path);ap.add_argument('normal',type=Path)
ap.add_argument('regions',type=Path);ap.add_argument('output',type=Path);ap.add_argument('--preview',type=Path,required=True)
ap.add_argument('--report',type=Path,required=True);a=ap.parse_args()
source=a.source.read_bytes();assert hashlib.sha256(source).hexdigest()==SOURCE
size=1024;original=Image.open(io.BytesIO(source)).convert('RGBA');assert original.size==(size,size)
rgba=np.array(original);region=np.array(Image.open(a.regions).convert('L').resize((size,size),Image.Resampling.NEAREST))
# Inset the semantic mask to retain original seams and keep other materials intact.
mask=Image.fromarray(np.uint8(region>230)*255).filter(ImageFilter.MinFilter(3))
coverage=np.array(mask.filter(ImageFilter.GaussianBlur(5)),dtype=np.float32)/255
coverage*=np.array(mask)>0
n=np.array(Image.open(a.normal).convert('RGB').resize((size,size),Image.Resampling.LANCZOS),dtype=np.float32)/127.5-1
valid=np.linalg.norm(n[:,:,:2],axis=2)+np.maximum(0,1-n[:,:,2])
ring=np.clip((valid-.035)*9,0,1)
n/=np.maximum(np.linalg.norm(n,axis=2,keepdims=True),1e-6)
l1=np.array([-.35,.55,.76]);l1/=np.linalg.norm(l1)
l2=np.array([.55,-.3,.70]);l2/=np.linalg.norm(l2)
shade=.14+.50*np.maximum(n@l1,0)+.20*np.maximum(n@l2,0)
spec=.38*np.maximum(n@l1,0)**18
steel=np.clip(255*(shade+spec),0,245)
detail=27*(1-ring)+steel*ring
# Retain some approved worn texture; no blanket grain or lighting pass on the atlas.
color=rgba[:,:,:3].astype(float);baked=detail[:,:,None]*np.array([.95,.98,1.])
color=color*(1-.22*coverage[:,:,None])+baked*(.22*coverage[:,:,None])
rgba[:,:,:3]=np.uint8(np.clip(color,0,255));image=Image.fromarray(rgba)
blocks=[];off=128;changedblocks=0
for level in range(11):
    buf=io.BytesIO();image.save(buf,format='DDS',pixel_format='DXT5');encoded=bytearray(buf.getvalue()[128:])
    count=max(1,image.width//4);affected=np.array(mask.resize(image.size,Image.Resampling.BOX))>0
    for y in range(count):
        for x in range(count):
            j=16*(y*count+x);src=off+j
            encoded[j:j+8]=source[src:src+8]
            if not affected[y*4:min((y+1)*4,image.height),x*4:min((x+1)*4,image.width)].any():
                encoded[j+8:j+16]=source[src+8:src+16]
            elif level==0:changedblocks+=1
    blocks.append(bytes(encoded));off+=len(encoded)
    if image.width>1:image=image.resize((max(1,image.width//2),)*2,Image.Resampling.LANCZOS)
output=source[:128]+b''.join(blocks);assert len(output)==len(source)
# All alpha blocks, including every mip, are copied rather than recompressed.
for off in range(128,len(source),16):assert source[off:off+8]==output[off:off+8]
a.output.write_bytes(output);Image.open(io.BytesIO(output)).convert('RGBA').save(a.preview)
assert np.array_equal(np.array(Image.open(io.BytesIO(output)))[:,:,3],np.array(original)[:,:,3])
a.report.write_text(json.dumps(dict(sourceSha256=SOURCE,normalBakeSha256=hashlib.sha256(a.normal.read_bytes()).hexdigest(),
    outputSha256=hashlib.sha256(output).hexdigest(),changedLevelZeroBlocks=changedblocks,
    alphaBlocksAllMipsUnchanged=True,teamMaskUnchanged=True,scope='Chainmail relief converted to fixed diffuse detail; no PBR shader',runtimeStatus='UNVERIFIED'),indent=2))
print('Legacy DDS ready; all mip alpha bytes preserved.')
