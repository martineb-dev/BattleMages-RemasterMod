"""Project real study links into the existing UVs; output is an authoring normal bake.

Requires Blender 4.5 Python. The legacy game is NOT assumed to support this map.
build_paladin_legacy_texture.py converts its small-scale relief to diffuse detail.
"""
import argparse
import hashlib
from pathlib import Path
import bpy

ap=argparse.ArgumentParser();ap.add_argument('study',type=Path);ap.add_argument('output',type=Path);args=ap.parse_args()
if hashlib.sha256(args.study.read_bytes()).hexdigest()!='bd7d2f4462d2bd910879fe073642fe5af18b6bdc57a376c5265de43173abdfe3':
    raise ValueError('Unsupported study file')
bpy.ops.wm.open_mainfile(filepath=str(args.study.resolve()),use_scripts=False)
scene=bpy.context.scene;scene.cycles.samples=16;scene.render.threads_mode='FIXED';scene.render.threads=12
for o in bpy.data.objects:o.select_set(False);o.hide_render=True
high=bpy.data.objects['Physical chainmail | static preview detail'];high.hide_render=False
objects=[]
for name in ('object03','shlem'):
    o=bpy.data.objects[name];o.hide_render=False;o.hide_set(False);o.select_set(True);objects.append(o)
bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();low=objects[0]
image=bpy.data.images.new('Mail tangent normal bake',width=2048,height=2048,alpha=False,float_buffer=False)
image.colorspace_settings.name='Non-Color';image.generated_color=(.5,.5,1,1)
for mat in low.data.materials:
    n=mat.node_tree.nodes.new('ShaderNodeTexImage');n.image=image;mat.node_tree.nodes.active=n
high.select_set(True);bpy.context.view_layer.objects.active=low
scene.render.bake.use_selected_to_active=True;scene.render.bake.cage_extrusion=.025;scene.render.bake.max_ray_distance=.05
scene.render.bake.margin=4
bpy.ops.object.bake(type='NORMAL',normal_space='TANGENT')
image.filepath_raw=str(args.output.resolve());image.file_format='PNG';image.save()
print('Physical mail normal bake saved; no game shader change.')
