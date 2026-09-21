"""Build private cm1 comparison payload from extracted Pack3; never commit output."""
import argparse, copy, hashlib, io, json, struct
from pathlib import Path
from lxml import etree as E
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--after',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
p.add_argument('--unit',default='ManPaladin');p.add_argument('--troop',default='ManTroop_Paladin');p.add_argument('--stem',default='paladin');a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=False)
root=a.out/'payload';root.mkdir()
def put(path,data):
 f=root/path;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(data)
def readxml(path): return E.parse(str(a.source/path),E.XMLParser(remove_blank_text=False))
def unique(tree,xpath):
 nodes=tree.xpath(xpath);assert len(nodes)==1,(xpath,len(nodes));return nodes[0]
def write(path,tree): put(path,E.tostring(tree,encoding='windows-1251',xml_declaration=True))
gamepath='data/gamedata/gameobjects.xml';animpath='data/models/animmodels.xml';serverpath='data/maps/cm1/servers.xml';triggerpath='data/maps/cm1/triggers.xml';icopath='data/if/ico/ico.xml'
game=readxml(gamepath);anim=readxml(animpath);servers=readxml(serverpath);triggers=readxml(triggerpath);icons=readxml(icopath)
unit=unique(game,f'//model[@ModelName="{a.unit}"]');troop=unique(game,f'//model[@ModelName="{a.troop}"]');model=unique(anim,f'//model[@id="{unit.get("ModelFile")}"]')
modelpath=model.get('file').replace('\\','/');folder=str(Path(modelpath).parent)
sam=(a.source/modelpath).read_bytes();needle=(a.stem+'.dds').encode();start=sam.lower().find(needle.lower());assert start>=0 and sam.lower().count(needle.lower())==1
assert len(needle)==11,'Current SAM patch requires a seven-letter source stem.'
# Convert the accepted image only; no art generation. Power-of-two 1024, BC3 mip chain.
im=Image.open(a.after).convert('RGBA').resize((1024,1024),Image.Resampling.LANCZOS)
parts=[];header=None
while True:
 buf=io.BytesIO();im.save(buf,format='DDS',pixel_format='DXT5');b=buf.getvalue();assert b[84:88]==b'DXT5'
 if header is None: header=bytearray(b[:128])
 parts.append(b[128:])
 if im.width==1: break
 im=im.resize((max(1,im.width//2),max(1,im.height//2)),Image.Resampling.LANCZOS)
struct.pack_into('<I',header,8,0xA1007);struct.pack_into('<I',header,28,len(parts));struct.pack_into('<I',header,108,0x401008)
afterdds=bytearray(bytes(header)+b''.join(parts))
# Preserve original BC3 alpha endpoints/indices rather than recompressing the
# cutout mask. New level 0 doubles its pixels; subsequent levels copy original mips.
originaldds=(a.source/(folder+'/'+a.stem+'.dds')).read_bytes()
assert originaldds[84:88]==b'DXT5' and struct.unpack_from('<II',originaldds,12)==(512,512)
assert struct.unpack_from('<I',originaldds,28)[0]==10
src_offsets=[];off=128
for level in range(10):
 src_offsets.append(off);n=max(1,128>>level);off+=n*n*16
assert off==len(originaldds)
off=128
for level in range(11):
 n=max(1,256>>level)
 for y in range(n):
  for x in range(n):
   dest=off+16*(y*n+x)
   if level:
    src=src_offsets[level-1]+16*(y*n+x)
    afterdds[dest:dest+8]=originaldds[src:src+8]
   else:
    src=128+16*((y//2)*128+x//2)
    indices=int.from_bytes(originaldds[src+2:src+8],'little');expanded=0
    for py in range(4):
     for px in range(4):
      oldpixel=((y%2)*2+py//2)*4+(x%2)*2+px//2
      expanded|=((indices>>(3*oldpixel))&7)<<(3*(py*4+px))
    afterdds[dest:dest+2]=originaldds[src:src+2]
    afterdds[dest+2:dest+8]=expanded.to_bytes(6,'little')
 off+=n*n*16
afterdds=bytes(afterdds)
for label,stem in [('Before','bmbefor'),('After','bmafter')]:
 modelid='BM'+label+'Model';unitid='BM'+label+'Unit';troopid='BM'+label+'Troop'
 u=copy.deepcopy(unit);u.set('ModelName',unitid);u.set('ModelFile',modelid);unit.getparent().append(u)
 t=copy.deepcopy(troop);t.set('ModelName',troopid);t.find('Properties').set('ChildModel',unitid);troop.getparent().append(t)
 m=copy.deepcopy(model);m.set('id',modelid);m.set('file',folder.replace('/','\\')+'\\'+stem+'.sam');model.getparent().append(m)
 E.SubElement(servers.getroot().find('AnimatedModelsServer'),'Item',id=modelid,file='data\\models\\AnimModels.xml')
 icon=copy.deepcopy(unique(icons,f'//Item[@id="{a.troop}"]'));icon.set('id',troopid);icons.getroot().append(icon)
 # Same-length replacement preserves all geometry/animation offsets.
 patched=sam[:start]+(stem+'.dds').encode()+sam[start+11:];assert len(patched)==len(sam)
 put(folder+'/'+stem+'.sam',patched)
 mrk=a.source/(str(Path(modelpath).with_suffix('.mrk')))
 if mrk.exists(): put(folder+'/'+stem+'.mrk',mrk.read_bytes())
 put(folder+'/'+stem+'.dds',(a.source/(folder+'/'+a.stem+'.dds')).read_bytes() if label=='Before' else afterdds)
# One-shot timer uses the mission's own CreateNewObject/player:AddChild pattern.
tr=E.SubElement(triggers.getroot(),'trigger',name='BMComparisonStart',active='1')
E.SubElement(tr,'event',timeout='1.5',eventid='GE_TIME_PERIOD')
script=E.SubElement(tr,'script');script.text='\n local player = GetPlayer(1001)\n'
for label,x,y in [('Before',4620,4640),('After',4850,4640)]:
 script.text+=f''' local id{label} = CreateNewObject{{
 modelName = "BM{label}Troop", objName = "BM_{label.upper()}",
 pos = CVector({x}.000,{y}.000,0.000), angle = "-143", belong = "1001"
 }}
 player:AddChild(GetEntityByID(id{label}))
'''
script.text+=' trigger:Deactivate()\n'
for path,tree in [(gamepath,game),(animpath,anim),(serverpath,servers),(triggerpath,triggers),(icopath,icons)]: write(path,tree)
# Validate references and uniqueness, and decode the delivered DDS.
for tree,attr,tag in [(game,'ModelName','model'),(anim,'id','model')]:
 ids=[n.get(attr) for n in tree.findall('.//'+tag) if (n.get(attr) or '').startswith('BM')];assert len(ids)==len(set(ids))
Image.open(io.BytesIO(afterdds)).load()
files=[dict(path=f.relative_to(root).as_posix(),sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(root.rglob('*')) if f.is_file()]
manifest=dict(build='cm1-comparison-paladin-v2-alpha',map='cm1',unit=a.unit,troop=a.troop,afterSourceSha256=hashlib.sha256(a.after.read_bytes()).hexdigest(),runtimeStatus='unverified',files=files)
(a.out/'manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(dict(files=len(files),afterDDSBytes=len(afterdds),output=str(a.out))))
