"""Create a static Blender/Cycles material study from private parsed SAM assets.
This is NOT a Battle Mages deployable build or an implemented engine shader.
Run under Blender Python (bpy 4.5), input folder supplies geometry.json and textures.
"""
import argparse,json,math,os
from pathlib import Path
import bpy,bmesh
import numpy as np
from mathutils import Vector

ap=argparse.ArgumentParser();ap.add_argument('folder',type=Path);ap.add_argument('--samples',type=int,default=48);ap.add_argument('--size',type=int,default=1200)
a=ap.parse_args();root=a.folder.resolve();parts=json.loads((root/'geometry.json').read_text())
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=a.samples;scene.cycles.use_denoising=True
scene.render.resolution_x=a.size;scene.render.resolution_y=a.size;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.view_settings.view_transform='AgX'
scene.view_settings.exposure=-.5
scene.render.threads_mode='FIXED';scene.render.threads=12
tex=bpy.data.images.load(str(root/'textures/approved-basecolor.png'));regions=bpy.data.images.load(str(root/'textures/material-regions.png'));regions.colorspace_settings.name='Non-Color'
team=bpy.data.images.load(str(root/'textures/original-team-mask.png'));team.colorspace_settings.name='Non-Color'
raw=np.array(regions.pixels[:]).reshape(regions.size[1],regions.size[0],4)

def region(uv):
 u,v=uv;h,w=raw.shape[:2];return int(round(float(raw[min(h-1,max(0,int((1-v)*(h-1)))),min(w-1,max(0,int(u*(w-1)))),0])*3))

def material(name,kind):
 m=bpy.data.materials.new(name);m.use_nodes=True;nodes=m.node_tree.nodes;links=m.node_tree.links;bs=nodes.get('Principled BSDF')
 t=nodes.new('ShaderNodeTexImage');t.image=tex;links.new(t.outputs['Alpha'],bs.inputs['Alpha'])
 tm=nodes.new('ShaderNodeTexImage');tm.image=team
 inverse=nodes.new('ShaderNodeMath');inverse.operation='SUBTRACT';inverse.inputs[0].default_value=1.;links.new(tm.outputs['Color'],inverse.inputs[1])
 tint=nodes.new('ShaderNodeMixRGB');tint.blend_type='MULTIPLY';links.new(inverse.outputs[0],tint.inputs[0]);links.new(t.outputs['Color'],tint.inputs[1]);tint.inputs[2].default_value=(.035,.42,.07,1)
 basecolor=tint.outputs[0]
 if kind=='before':
  links.new(basecolor,bs.inputs['Base Color']);bs.inputs['Roughness'].default_value=1.;bs.inputs['Specular IOR Level'].default_value=.12
  return m
 color=(.43,.46,.49,1);amount=1.;rough=.40;metal=1.;strength=.075;distance=.00028
 if kind=='cloth':color=(.77,.75,.82,1);amount=1.;rough=.84;metal=0.;strength=.12;distance=.00022;bs.inputs['Sheen Weight'].default_value=.20
 if kind=='leather':color=(.075,.054,.045,1);amount=1.;rough=.59;metal=0.;strength=.20;distance=.00065
 if kind=='chain':color=(.028,.035,.041,1);amount=.06;rough=.72;metal=.60;strength=.04;distance=.0001
 mix=nodes.new('ShaderNodeMixRGB');mix.blend_type='MIX';mix.inputs[0].default_value=amount;mix.inputs[1].default_value=color;links.new(basecolor,mix.inputs[2]);links.new(mix.outputs[0],bs.inputs['Base Color'])
 bs.inputs['Metallic'].default_value=metal;bs.inputs['Roughness'].default_value=rough
 if kind=='metal':bs.inputs['Anisotropic'].default_value=.18
 bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=strength;bump.inputs['Distance'].default_value=distance
 if kind=='cloth':
  noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=800;noise.inputs['Detail'].default_value=2;links.new(noise.outputs['Fac'],bump.inputs['Height'])
 else:links.new(t.outputs['Color'],bump.inputs['Height'])
 links.new(bump.outputs['Normal'],bs.inputs['Normal'])
 return m

oldmat=material('Before | approved atlas, diffuse response','before')
materials=[material('Steel | physically reflective, fine relief','metal'),material('White cloth | lavender shade, woven surface','cloth'),material('Leather | restrained reflection','leather'),material('Mail backing | dark cloth under real links','chain')]
ringmat=bpy.data.materials.new('Chain links | solid steel');ringmat.use_nodes=True
bs=ringmat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.38,.42,.46,1);bs.inputs['Metallic'].default_value=1.;bs.inputs['Roughness'].default_value=.34
# Legacy armor/tabards have near-coincident inner/outer surfaces. Build a
# physical shell from the outward layer so ray-traced self-shadowing is valid.
prepared=[]
for source in parts:
 p=dict(source)
 if p['name'].startswith('naplechnik'):
  p['f']=p['f'][:128];p['shell']=.004
 elif p['name']=='object03':
  origins=json.loads((root/'body-face-origins.json').read_text());outer=set(range(69,73))|set(range(198,202))|set(range(258,262))|set(range(266,270))
  both=outer|set(range(73,77))|set(range(202,206))|set(range(262,266))|set(range(270,274))
  retained=[];cloth=[]
  for i,f in enumerate(p['f']):
   parent=origins[i] if i<len(origins) else -1
   if parent in outer:cloth.append(f)
   if parent not in both:retained.append(f)
  p['f']=retained
  clothpart=dict(source,name='Tabard | physical cloth shell',f=cloth,shell=.0018)
  prepared.append(clothpart)
 prepared.append(p)
objects=[]
for p in prepared:
 verts=np.array(p['v']);mesh=bpy.data.meshes.new(p['name']);mesh.from_pydata((verts[:,:3]*.1).tolist(),[],p['f']);mesh.update()
 obj=bpy.data.objects.new(p['name'],mesh);bpy.context.collection.objects.link(obj);objects.append(obj)
 for m in materials:mesh.materials.append(m)
 uv=mesh.uv_layers.new(name='Original UV')
 for face in mesh.polygons:
  for li in face.loop_indices:
   vi=mesh.loops[li].vertex_index;u,v=verts[vi,6:8];uv.data[li].uv=(float(u),float(1-v))
  center=verts[list(face.vertices),6:8].mean(0);r=region(center)
  # Helm/pauldron/weapon part identity takes precedence over atlas heuristics.
  if p['name'] in ('naplechnik1','naplechnik2','mech'):r=0
  if p['name']=='shlem' and r!=3:r=0
  face.material_index=r;face.use_smooth=True
 mesh.normals_split_custom_set_from_vertices(verts[:,3:6].tolist())
 if 'shell' in p:
  bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000005);bm.to_mesh(mesh);bm.free();mesh.update()
  # Smooth and thicken a single connected outer surface, not two intersecting skins.
  smooth=obj.modifiers.new('Surface fairing','SMOOTH');smooth.factor=.25;smooth.iterations=3
  sub=obj.modifiers.new('Rounded physical surface','SUBSURF');sub.levels=1;sub.render_levels=1;sub.uv_smooth='NONE'
  shell=obj.modifiers.new('Physical thickness','SOLIDIFY');shell.thickness=p['shell'];shell.offset=-1

 obj['source_part']=p['name'];obj['game_deployment']='Preview only. No SAM/PBR engine export implemented.'
 obj['rig_status']='Static material study mesh. Original weights retained in geometry.json; no Blender animation rig imported.'

# Actual steel rings on mail surfaces, sampled through existing UV triangles.
# These are modern master detail geometry, not claimed to work in the old engine.
rv=[];rf=[];seen=set();stepu,stepv=.008,.0055
for p in parts:
 if p['name'] not in ('object03','shlem'):continue
 vv=np.array(p['v'])
 for face in p['f']:
  f=list(face);uv=vv[f,6:8];pos=vv[f,:3]*.1
  if not any(region(q)==3 for q in [*uv,uv.mean(0)]):continue
  mat=np.stack((uv[1]-uv[0],uv[2]-uv[0]),axis=1)
  if abs(np.linalg.det(mat))<1e-10:continue
  inv=np.linalg.inv(mat);derivative=np.stack((pos[1]-pos[0],pos[2]-pos[0]),axis=1)@inv
  normal=np.cross(pos[1]-pos[0],pos[2]-pos[0]);nl=np.linalg.norm(normal)
  if nl<1e-10:continue
  normal/=nl;du=derivative[:,0];du/=np.linalg.norm(du);dv=np.cross(normal,du)
  physical_u=np.linalg.norm(derivative[:,0])*stepu;physical_v=np.linalg.norm(derivative[:,1])*stepv
  # Derivative[:,0] was normalized above: derive spacing from the full matrix again.
  actual=np.stack((pos[1]-pos[0],pos[2]-pos[0]),axis=1)@inv
  radius=float(np.clip(np.linalg.norm(actual[:,0])*stepu*.68,.002,.012))
  for j in range(math.floor(uv[:,1].min()/stepv),math.ceil(uv[:,1].max()/stepv)+1):
   y=j*stepv
   for i in range(math.floor(uv[:,0].min()/stepu)-1,math.ceil(uv[:,0].max()/stepu)+1):
    x=(i+.5*(j%2))*stepu;st=inv@(np.array([x,y])-uv[0]);w=np.array([1-st.sum(),*st])
    if w.min()<1e-6 or region((x,y))!=3:continue
    center=w@pos+normal*radius*.44;key=tuple(np.round(center,4))
    if key in seen:continue
    seen.add(key);tilt=math.radians(34 if j%2 else -34);ax=dv*math.cos(tilt)+normal*math.sin(tilt);bn=np.cross(du,ax);tube=radius*.155;start=len(rv)
    for k in range(12):
     theta=k*2*math.pi/12;rad=du*math.cos(theta)+ax*math.sin(theta)
     for l in range(5):
      phi=l*2*math.pi/5;rv.append((center+radius*rad+tube*(rad*math.cos(phi)+bn*math.sin(phi))).tolist())
    for k in range(12):
     for l in range(5):
      aa=start+k*5+l;bb=start+((k+1)%12)*5+l;cc=start+((k+1)%12)*5+(l+1)%5;dd=start+k*5+(l+1)%5;rf.append((aa,bb,cc,dd))
mesh=bpy.data.meshes.new('Physical chainmail');mesh.from_pydata(rv,[],rf);mesh.update();links=bpy.data.objects.new('Physical chainmail | static preview detail',mesh);bpy.context.collection.objects.link(links);mesh.materials.append(ringmat)
for poly in mesh.polygons:poly.use_smooth=True
print('PHYSICAL LINKS',len(seen),'LINK VERTICES',len(rv),flush=True)

# Controlled studio conditions; no composited reference background or fake game UI.
world=bpy.data.worlds.new('Neutral studio');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.23,.26,.31,1);world.node_tree.nodes['Background'].inputs[1].default_value=.45;scene.world=world
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.025));floor=bpy.context.object;floor.name='Studio floor'
ground=bpy.data.materials.new('Matte charcoal floor');ground.use_nodes=True;gb=ground.node_tree.nodes.get('Principled BSDF');gb.inputs['Base Color'].default_value=(.065,.074,.085,1);gb.inputs['Roughness'].default_value=.83;floor.data.materials.append(ground)
def point(obj,target):obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
def area(name,location,power,size,color):
 light=bpy.data.lights.new(name,'AREA');light.energy=power;light.shape='DISK';light.size=size;light.color=color;o=bpy.data.objects.new(name,light);bpy.context.collection.objects.link(o);o.location=location;point(o,(0,0,1))
area('Large key',(-3,-4,5),1300,3,(1,.92,.83));area('Cool fill',(3,-1,3),950,2.5,(.73,.83,1));area('Rim',(1,4,4),1800,2,(1,.95,.84))
camera=bpy.data.cameras.new('Comparison camera');cam=bpy.data.objects.new('Comparison camera',camera);bpy.context.collection.objects.link(cam);scene.camera=cam
cam.location=(-3.4,-5.3,2.65);target=(-.25,0,1.02);point(cam,target);camera.type='ORTHO';camera.ortho_scale=3.05;camera.lens=55
# Save the after scene with packed source maps, then render matched material states.
for im in (tex,regions,team):im.pack()
scene['study_scope']='Derived Master Candidate 01 mesh with physical shoulder/tabard shells, real mail and Cycles materials; NOT an in-game build.'
scene['rig_status']='Static look development scene. Source skin weights are in geometry.json; no Blender armature or clips imported.'
scene['source_reference']='ead528fa-e273-4f22-8d04-cd78efd19d2b.png; original identity/white-lavender cloth retained.'
bpy.ops.wm.save_as_mainfile(filepath=str(root/'Paladin_RealismStudy_01.blend'))
scene.render.filepath=str(root/'after-pbr.png');bpy.ops.render.render(write_still=True)
links.hide_render=True
saved=[]
for obj in objects:
 saved.append(list(obj.data.materials))
 for i in range(len(obj.data.materials)):obj.data.materials[i]=oldmat
scene.render.filepath=str(root/'before-diffuse.png');bpy.ops.render.render(write_still=True)
for obj,mats in zip(objects,saved):
 for i,m in enumerate(mats):obj.data.materials[i]=m
links.hide_render=False
(root/'study-report.json').write_text(json.dumps({'renderer':bpy.app.version_string+' Cycles CPU','sourceMesh':'Master Candidate 01; shoulder and tabard shells repaired for ray tracing','newPhysicalChainLinks':len(seen),'newDetailVertices':len(rv),'newDetailQuads':len(rf),'materialState':'Before: diffuse atlas. After: steel/cloth/leather materials plus physical chain links. Same camera and lights.','gameBuild':False,'animatedBlenderRig':False},indent=2))
print('STUDY COMPLETE',flush=True)

# Also preserve and render the real original game mesh, in the SAME studio.
# This comparison is explicitly not a screenshot of the old game renderer.
originalparts=json.loads((root/'original-geometry.json').read_text())
originaltex=bpy.data.images.load(str(root/'textures/original-basecolor.png'));originaltex.pack()
originalmat=oldmat.copy();originalmat.name='Original game atlas | diffuse studio baseline'
for node in originalmat.node_tree.nodes:
 if node.type=='TEX_IMAGE' and node.image==tex:node.image=originaltex
originalobjects=[]
for p in originalparts:
 v=np.array(p['v']);m=bpy.data.meshes.new('Original '+p['name']);m.from_pydata((v[:,:3]*.1).tolist(),[],p['f']);m.update()
 o=bpy.data.objects.new('Original '+p['name'],m);bpy.context.collection.objects.link(o);originalobjects.append(o);m.materials.append(originalmat)
 uv=m.uv_layers.new(name='Original UV')
 for face in m.polygons:
  face.use_smooth=True
  for li in face.loop_indices:
   i=m.loops[li].vertex_index;uv.data[li].uv=(float(v[i,6]),float(1-v[i,7]))
 nn=v[:,3:6];nn/=np.maximum(np.linalg.norm(nn,axis=1)[:,None],1e-10);m.normals_split_custom_set_from_vertices(nn.tolist())
for o in objects:o.hide_render=True
links.hide_render=True
scene.render.filepath=str(root/'before-original.png');bpy.ops.render.render(write_still=True)
for o in originalobjects:o.hide_render=True;o.hide_set(True)
for o in objects:o.hide_render=False
links.hide_render=False
scene.render.filepath=str(root/'after-pbr.png')
bpy.ops.wm.save_as_mainfile(filepath=str(root/'Paladin_RealismStudy_01.blend'))
print('ORIGINAL COMPARISON COMPLETE',flush=True)
