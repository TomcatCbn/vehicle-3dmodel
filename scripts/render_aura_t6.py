"""Render the actual articulated mesh with Cycles; never uses a car image billboard."""
import bpy
import math
import sys
from pathlib import Path
from mathutils import Vector, Matrix

ROOT=Path(__file__).resolve().parents[1]
preview='--preview' in sys.argv
detail_view=next((arg.split('=',1)[1] for arg in sys.argv if arg.startswith('--view=')),None)
if detail_view not in {None,'front','front-photo','front-quarter','handle','mirror','mirror-rear','sensor','roof-sensor','tire','roof-close','rear','rear-photo','rear-quarter','side','wheel','lamp','badge','hood','hood-quarter','trunk','sunroof'}:raise ValueError('unknown detail view')
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'models/aura-t6.blend'))
scene=bpy.context.scene
if detail_view=='mirror-rear':
    for obj in bpy.data.objects:
        if obj.get('part') and obj.get('label')!='右后视镜':
            for child in [obj,*obj.children_recursive]:child.hide_render=True
if detail_view=='trunk':
    for obj in bpy.data.objects:
        if obj.get('motion')=='tailgate':obj.rotation_euler.y=-1.45
        if obj.get('motion')=='tailgate_strut':
            m=obj['moving'];h=obj['hinge'];hinge=Vector((h[0],-h[2],h[1]));moving=Vector((m[0],-m[2],m[1]))
            moving=hinge+Matrix.Rotation(-1.45,3,'Y')@(moving-hinge);length=(moving-obj.location).length
            obj.rotation_euler=(moving-obj.location).to_track_quat('Z','Y').to_euler()
            for child in obj.children:
                tag=child.get('strut_component')
                if tag:child.location.z=obj.location.z+length-(obj['piston_length']/2 if tag=='piston' else 0)
if detail_view=='sunroof':
    for obj in bpy.data.objects:
        if obj.get('motion')=='sunroof':
            obj.location.x+=.78;obj.location.z+=.065;obj.rotation_euler.y=-.045*.35
if detail_view in {'hood','hood-quarter'}:
    hinge=Vector((-1.045,0,1.095));rotation=Matrix.Rotation(1.12,3,'Y')
    for obj in bpy.data.objects:
        if obj.get('motion')=='hood':obj.rotation_euler.y=1.12
        if obj.get('motion')=='hood_strut':
            # Metadata is exported in glTF axes; Blender keeps Z upright.
            m=obj['moving'];moving=Vector((m[0],-m[2],m[1]))
            moving=hinge+rotation@(moving-hinge);length=(moving-obj.location).length
            obj.rotation_euler=(moving-obj.location).to_track_quat('Z','Y').to_euler()
            for child in obj.children:
                tag=child.get('strut_component')
                if tag:child.location.z=obj.location.z+length-(obj['piston_length']/2 if tag=='piston' else 0)
# Model metadata determines the assembled, unpowered presentation pose.
for obj in bpy.data.objects:
    if obj.get('effect'):
        for child in [obj,*obj.children_recursive]:child.hide_render=True
for material in bpy.data.materials:
    if '--white' in sys.argv and material.name.startswith('Paint'):
        material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.72,.77,.78,1)
    if material.name.startswith('Glazing'):
        bsdf=material.node_tree.nodes.get('Principled BSDF')
        privacy='rear privacy' in material.name
        bsdf.inputs['Base Color'].default_value=(.025,.040,.045,1) if privacy else (.065,.10,.12,1)
        bsdf.inputs['Metallic'].default_value=0
        bsdf.inputs['Roughness'].default_value=.075
        bsdf.inputs['Transmission Weight'].default_value=.42 if privacy else .7
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
    camera.location={'front':(-8,0,.84),'front-photo':(-8.8,0,1.8),'front-quarter':(-6.3,-8.5,1.65),'mirror':(-1.45,-2.2,1.38),'mirror-rear':(-.30,-.20,1.42),'sensor':(-1.4,-2.5,1.28),'roof-sensor':(-1.4,-1.2,2.4),'tire':(-1.34,-2.5,.66),'roof-close':(-1.6,-2.2,3.3),'handle':(-.46,-2.4,1.24),'rear':(8,0,.84),'rear-photo':(8.8,0,1.7),'rear-quarter':(6.3,-8.5,1.65),'side':(0,-8,.84),'wheel':(-1.418,-3,.37),'lamp':(-3.5,-1.3,.83),'badge':(-3.5,0,1.12),'hood':(-5,0,2.7),'hood-quarter':(-5,-3.5,2.5),'trunk':(6.4,-4.4,2.45),'sunroof':(-2.5,-3.5,5.2)}[detail_view]
    targets={'mirror':(-.865,-1.06,1.16),'mirror-rear':(-.835,-1.025,1.16),'sensor':(-1.157,-.96,1.022),'roof-sensor':(-.345,0,1.64),'tire':(-1.418,-.935,.37),'roof-close':(.5,0,1.60)}
    target=targets.get(detail_view) or ((-.026,-.91,.984) if detail_view=='handle' else (1.5,0,1.3) if detail_view=='trunk' else (.55,0,1.50) if detail_view=='sunroof' else (-1.6,0,1.40) if detail_view=='hood' else (-1.25,0,1.22) if detail_view=='hood-quarter' else (-2.35,0,.944) if detail_view=='badge' else (-2.24,-.75,.741) if detail_view=='lamp' else (-1.418,-.9,.37) if detail_view=='wheel' else (0,0,.84))
    camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='PERSP' if detail_view in {'front-quarter','rear-quarter','hood-quarter','front-photo','rear-photo','trunk'} else 'ORTHO'
    if detail_view in {'front-photo','rear-photo'}:camera.data.lens=68
    if detail_view=='sunroof':camera.data.ortho_scale=3.6
    camera.data.ortho_scale=5.5 if detail_view=='side' else 3.6 if detail_view=='sunroof' else .45 if detail_view in {'mirror','mirror-rear'} else .38 if detail_view=='sensor' else .39 if detail_view=='roof-sensor' else .82 if detail_view=='tire' else 2.8 if detail_view=='roof-close' else .31 if detail_view=='handle' else .25 if detail_view=='badge' else .48 if detail_view=='lamp' else .90 if detail_view=='wheel' else 2.5
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
if detail_view in {'front-photo','rear-photo'}:scene.render.resolution_y=900
if detail_view in {'front','rear','wheel','lamp','badge','handle','mirror','mirror-rear','sensor','roof-sensor','tire'}:scene.render.resolution_x=900;scene.render.resolution_y=900
scene.view_settings.view_transform='AgX';scene.view_settings.exposure=-.25
scene.render.image_settings.file_format='PNG'
filename=f'aura-t6-detail-{detail_view}.png' if detail_view else ('aura-t6-cycles-preview.png' if preview else 'aura-t6-cycles.png')
output=ROOT/'output/playwright'/filename;scene.render.filepath=str(output)
if not detail_view:bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'models/aura-t6-studio.blend'))
print('RENDER_START',scene.cycles.device,flush=True)
bpy.ops.render.render(write_still=True)
print('RENDER_SAVED',output)
