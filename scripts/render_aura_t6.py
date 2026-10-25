"""Render the actual articulated mesh with Cycles; never uses a car image billboard."""
import bpy
import math
import sys
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
preview='--preview' in sys.argv
detail_view=next((arg.split('=',1)[1] for arg in sys.argv if arg.startswith('--view=')),None)
if detail_view not in {None,'front','rear','side','wheel'}:raise ValueError('view must be front, rear, side or wheel')
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'models/aura-t6.blend'))
scene=bpy.context.scene
# Model metadata determines the assembled, unpowered presentation pose.
for obj in bpy.data.objects:
    if obj.get('effect'):
        for child in [obj,*obj.children_recursive]:child.hide_render=True
for material in bpy.data.materials:
    if material.name.startswith('Glazing'):
        bsdf=material.node_tree.nodes.get('Principled BSDF')
        bsdf.inputs['Base Color'].default_value=(.065,.10,.12,1)
        bsdf.inputs['Metallic'].default_value=0
        bsdf.inputs['Roughness'].default_value=.075
        bsdf.inputs['Transmission Weight'].default_value=.7
        bsdf.inputs['IOR'].default_value=1.48

studio=bpy.data.collections.new('Photography studio')
scene.collection.children.link(studio)
def in_studio(obj):
    for collection in list(obj.users_collection):collection.objects.unlink(obj)
    studio.objects.link(obj)

world=bpy.data.worlds.new('Dusk HDR lighting')
world.use_nodes=True;scene.world=world
nodes=world.node_tree.nodes;nodes.clear();links=world.node_tree.links
out=nodes.new('ShaderNodeOutputWorld')
env=nodes.new('ShaderNodeTexEnvironment');env.image=bpy.data.images.load(str(ROOT/'public/environments/studio-small-09.hdr'));env.image.pack()
background=nodes.new('ShaderNodeBackground');background.inputs['Strength'].default_value=.65;links.new(env.outputs['Color'],background.inputs['Color'])
coordinates=nodes.new('ShaderNodeTexCoord');separate=nodes.new('ShaderNodeSeparateXYZ');links.new(coordinates.outputs['Normal'],separate.inputs['Vector'])
maprange=nodes.new('ShaderNodeMapRange');maprange.inputs['From Min'].default_value=-.1;maprange.inputs['From Max'].default_value=.35;links.new(separate.outputs['Z'],maprange.inputs['Value'])
ramp=nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(.64,.45,.32,1);ramp.color_ramp.elements[1].color=(.18,.26,.4,1);links.new(maprange.outputs['Result'],ramp.inputs['Fac'])
sky=nodes.new('ShaderNodeBackground');sky.inputs['Strength'].default_value=.8;links.new(ramp.outputs['Color'],sky.inputs['Color'])
lightpath=nodes.new('ShaderNodeLightPath');mix=nodes.new('ShaderNodeMixShader');links.new(lightpath.outputs['Is Camera Ray'],mix.inputs[0]);links.new(background.outputs[0],mix.inputs[1]);links.new(sky.outputs[0],mix.inputs[2]);links.new(mix.outputs[0],out.inputs[0])

floor_material=bpy.data.materials.new('Satin graphite floor');floor_material.use_nodes=True
p=floor_material.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(.105,.115,.13,1);p.inputs['Metallic'].default_value=.2;p.inputs['Roughness'].default_value=.2
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.004));floor=bpy.context.object;floor.name='Reflective floor';floor.data.materials.append(floor_material);in_studio(floor)

def area(name,location,power,color,size,size_y):
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.color=color;data.shape='RECTANGLE';data.size=size;data.size_y=size_y
    obj=bpy.data.objects.new(name,data);studio.objects.link(obj);obj.location=location;obj.rotation_euler=(Vector((0,0,.65))-obj.location).to_track_quat('-Z','Y').to_euler()
area('Large overhead softbox',(-.4,-1,5.5),1200,(.82,.9,1),6,2.2)
area('Warm rim',(3,2,3.4),850,(1,.69,.43),4,2.0)
area('Front fill',(-5,-3,3.5),750,(.91,.95,1),4,3.0)

bpy.ops.object.camera_add(location=(-6.3,-8.5,2.35))
camera=bpy.context.object;camera.name='Advertising view';in_studio(camera)
camera.rotation_euler=(Vector((0,0,.76))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.lens=60;scene.camera=camera
if detail_view:
    camera.location={'front':(-8,0,.84),'rear':(8,0,.84),'side':(0,-8,.84),'wheel':(-1.418,-3,.37)}[detail_view]
    target=(-1.418,-.9,.37) if detail_view=='wheel' else (0,0,.84)
    camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO';camera.data.ortho_scale=5.5 if detail_view=='side' else .90 if detail_view=='wheel' else 2.5
scene.render.engine='CYCLES';scene.cycles.samples=96;scene.cycles.use_denoising=True;scene.cycles.max_bounces=8;scene.cycles.transparent_max_bounces=8
try:
    preferences=bpy.context.preferences.addons['cycles'].preferences
    preferences.compute_device_type='METAL';preferences.get_devices()
    gpu=False
    for device in preferences.devices:
        device.use=device.type!='CPU';gpu=gpu or device.use
    scene.cycles.device='CPU' if preview else ('GPU' if gpu else 'CPU')
except Exception:
    scene.cycles.device='CPU'
scene.render.resolution_x=1800;scene.render.resolution_y=1125;scene.render.resolution_percentage=100
if preview:
    scene.render.resolution_x=1200;scene.render.resolution_y=750;scene.cycles.samples=24
if detail_view in {'front','rear','wheel'}:scene.render.resolution_x=900;scene.render.resolution_y=900
scene.view_settings.view_transform='AgX';scene.view_settings.exposure=-.25
scene.render.image_settings.file_format='PNG'
filename=f'aura-t6-detail-{detail_view}.png' if detail_view else ('aura-t6-cycles-preview.png' if preview else 'aura-t6-cycles.png')
output=ROOT/'output/playwright'/filename;scene.render.filepath=str(output)
if not detail_view:bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'models/aura-t6-studio.blend'))
print('RENDER_START',scene.cycles.device,flush=True)
bpy.ops.render.render(write_still=True)
print('RENDER_SAVED',output)
