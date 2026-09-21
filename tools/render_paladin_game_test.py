"""Render the actual exported SAM candidate with diffuse materials in a fixed studio.
This is not an in-game screenshot and does not assert PBR engine support.
"""
import argparse
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from build_paladin_geometry import parse

ap=argparse.ArgumentParser();ap.add_argument('study',type=Path);ap.add_argument('package',type=Path)
ap.add_argument('previous',type=Path);ap.add_argument('--only',choices=['before-studio','after-studio','feet-before-studio','feet-after-studio']);a=ap.parse_args();root=a.package.resolve()
bpy.ops.wm.open_mainfile(filepath=str(a.study.resolve()),use_scripts=False)
scene=bpy.context.scene;scene.cycles.samples=32;scene.render.threads_mode='FIXED';scene.render.threads=12
scene.render.resolution_x=1100;scene.render.resolution_y=1100
for obj in bpy.data.objects:
    if obj.type=='MESH':obj.hide_render=True
floor=bpy.data.objects['Studio floor'];floor.hide_render=False;floor.location.z=.003
team=bpy.data.images.load(str(root/'textures/team-mask.png'))
def load(stem,sam,texture):
    tex=bpy.data.images.load(str(texture));m=bpy.data.materials.new(stem+' diffuse only');m.use_nodes=True
    nd=m.node_tree.nodes;ln=m.node_tree.links;bs=nd.get('Principled BSDF')
    bs.inputs['Roughness'].default_value=.9;bs.inputs['Specular IOR Level'].default_value=.08
    t=nd.new('ShaderNodeTexImage');t.image=tex;ln.new(t.outputs['Alpha'],bs.inputs['Alpha'])
    tm=nd.new('ShaderNodeTexImage');tm.image=team
    inv=nd.new('ShaderNodeMath');inv.operation='SUBTRACT';inv.inputs[0].default_value=1;ln.new(tm.outputs['Color'],inv.inputs[1])
    mix=nd.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';ln.new(inv.outputs[0],mix.inputs[0]);ln.new(t.outputs['Color'],mix.inputs[1]);mix.inputs[2].default_value=(.035,.42,.07,1)
    ln.new(mix.outputs[0],bs.inputs['Base Color']);objects=[]
    for p in parse(sam.read_bytes()):
        v=np.array(p['v']);mesh=bpy.data.meshes.new(stem+' '+p['name']);mesh.from_pydata((v[:,:3]*.1).tolist(),[],p['f']);mesh.update()
        obj=bpy.data.objects.new(mesh.name,mesh);bpy.context.collection.objects.link(obj);mesh.materials.append(m)
        uv=mesh.uv_layers.new()
        for poly in mesh.polygons:
            poly.use_smooth=True
            for li in poly.loop_indices:
                i=mesh.loops[li].vertex_index;uv.data[li].uv=(float(v[i,6]),float(1-v[i,7]))
        mesh.normals_split_custom_set_from_vertices(v[:,3:6].tolist());obj.hide_render=True;objects.append(obj)
    tex.pack();return objects
assets=root/'payload/data/models/units/humans'
original=load('Original',assets/'bmbefor.sam',root/'textures/before.png')
after=load('GameTest',assets/'bmafter.sam',root/'textures/after.png')
previous=load('Study geometry base',a.previous/'payload/data/models/units/humans/bmafter.sam',root/'textures/approved-previous.png')
for name,group in [('before-studio',original),('after-studio',after)]:
    if a.only and name!=a.only:continue
    for o in group:o.hide_render=False
    scene.render.filepath=str(root/(name+'.png'));bpy.ops.render.render(write_still=True)
    for o in group:o.hide_render=True
cam=scene.camera;cam.location=(-1.65,-2.15,.93);target=Vector((-.065,-.04,.07));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.18
for name,group in [('feet-before-studio',previous),('feet-after-studio',after)]:
    if a.only and name!=a.only:continue
    for o in group:o.hide_render=False
    scene.render.filepath=str(root/(name+'.png'));bpy.ops.render.render(write_still=True)
    for o in group:o.hide_render=True
print('Exported SAM studio previews complete.')
