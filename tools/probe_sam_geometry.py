"""Conservative, source-pinned paladin vertex-position probe; not a SAM exporter."""
import argparse,hashlib,json,struct,math
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
b=a.source.read_bytes()
assert hashlib.sha256(b).hexdigest()=='ca83ad6d860d3d0768eab0e681c9975bfcdfe0c07fcf5c47d0a536e312f29b38','Unsupported source SAM'
out=bytearray(b);o=3832;allowed=set();summary=[]
while o<23236:
 start=o;name=b[o:o+40].split(b'\0')[0].decode();nv,nf,mat,kind=struct.unpack_from('<4H',b,o+40);o+=48
 offsets=[];vertices=[]
 for i in range(nv):
  offsets.append(o);vertices.append(struct.unpack_from('<3f',b,o));o+=32
  if kind==2:
   n=struct.unpack_from('<H',b,o)[0];o+=2+6*n
 faces=[struct.unpack_from('<3H',b,o+6*i) for i in range(nf)];o+=6*nf
 assert all(max(f)<nv for f in faces)
 if name in ('naplechnik1','naplechnik2'):
  center=[(min(v[k] for v in vertices)+max(v[k] for v in vertices))/2 for k in range(3)]
  for offset,v in zip(offsets,vertices):
   new=[center[k]+1.30*(v[k]-center[k]) for k in range(3)]
   assert all(math.isfinite(x) for x in new)
   struct.pack_into('<3f',out,offset,*new);allowed.update(range(offset,offset+12))
  summary.append(dict(part=name,vertices=nv,scale=1.3,center=center))
assert o==23236 and len(summary)==2 and len(out)==len(b)
changed={i for i,(x,y) in enumerate(zip(b,out)) if x!=y};assert changed and changed<=allowed
assert b[:3832]==out[:3832] and b[23236:]==out[23236:]
# Normals do not change under uniform scaling. UV, weights, faces, skeleton,
# animation and all other bytes remain exactly unchanged.
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(out)
a.report.write_text(json.dumps(dict(sourceSha256=hashlib.sha256(b).hexdigest(),outputSha256=hashlib.sha256(out).hexdigest(),parts=summary,changedBytes=len(changed),changedFields='vertex positions only',runtimeStatus='unverified'),indent=2))
print('PASS: 32 shoulder vertices transformed; all bytes outside their XYZ fields unchanged.')
