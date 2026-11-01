"""Render the actual articulated mesh with Cycles; never uses a car image billboard."""
import bpy
import math
import sys
from pathlib import Path
from mathutils import Vector, Matrix

ROOT=Path(__file__).resolve().parents[1]
preview='--preview' in sys.argv
detail_view=next((arg.split('=',1)[1] for arg in sys.argv if arg.startswith('--view=')),None)
if detail_view not in {None,'front','front-photo','front-quarter','handle','charge','underbody','mirror','mirror-rear','sensor','roof-sensor','windscreen-sensor','key','tire','roof-close','rear','rear-photo','rear-quarter','rear-lamp','rear-wiper','rear-camera','side','wheel','lamp','badge','hood','hood-quarter','trunk','sunroof','door-interior','interior','seats'}:raise ValueError('unknown detail view')
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'models/aura-t6.blend'))
scene=bpy.context.scene
if detail_view=='charge':
    for obj in bpy.data.objects:
        if obj.get('motion')=='charge_flap':obj.rotation_euler.z=1.35
if detail_view=='door-interior':
    for obj in bpy.data.objects:
        if obj.get('part') and obj.get('label')!='右后门':
            for child in [obj,*obj.children_recursive]:child.hide_render=True
        if obj.get('label')=='右后门':obj.rotation_euler.z=-.95
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
    if obj.get('effect') or obj.get('detail')=='chargeInner' or obj.get('detailOnly'):
        for child in [obj,*obj.children_recursive]:child.hide_render=True
    if detail_view=='charge' and obj.get('detail')=='chargeInner':obj.hide_render=False
if detail_view in {'key','windscreen-sensor'}:
    label='遥控钥匙' if detail_view=='key' else '前挡双目感知'
    for obj in bpy.data.objects:
        if obj.get('part'):
            visible=obj.get('label')==label
            for child in [obj,*obj.children_recursive]:child.hide_render=not visible
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
# Inspect the optical geometry with the lamps switched off; do not alter the saved asset.
if detail_view in {'lamp','rear-lamp'}:
    for obj in bpy.data.objects:
        if obj.get('lightRole') and obj.type=='MESH':
            for material in obj.data.materials:
                if material and material.use_nodes:
                    bsdf=material.node_tree.nodes.get('Principled BSDF')
                    if bsdf:bsdf.inputs['Emission Strength'].default_value=0

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
if detail_view=='underbody':floor.hide_render=True

def area(name,location,power,color,size,size_y):
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.color=color;data.shape='RECTANGLE';data.size=size;data.size_y=size_y
    obj=bpy.data.objects.new(name,data);studio.objects.link(obj);obj.location=location;obj.rotation_euler=(Vector((0,0,.65))-obj.location).to_track_quat('-Z','Y').to_euler()
area('Large overhead softbox',(-.4,-1,5.5),1200,(.82,.9,1),6,2.2)
area('Warm rim',(3,2,3.4),850,(1,.69,.43),4,2.0)
area('Front fill',(-5,-3,3.5),750,(.91,.95,1),4,3.0)

if detail_view in {'interior','seats'}:area('Cabin soft fill',(.20,0,1.48),35,(.88,.93,1),.9,.7)
if detail_view in {'hood','hood-quarter'}:area('Front storage soft fill',(-1.65,0,2.5),55,(.88,.94,1),.9,.7)
bpy.ops.object.camera_add(location=(-6.3,-8.5,2.35))
camera=bpy.context.object;camera.name='Advertising view';in_studio(camera)
camera.rotation_euler=(Vector((0,0,.76))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.lens=60;scene.camera=camera
if detail_view:
    camera.location={'front':(-8,0,.84),'front-photo':(-8.8,0,1.8),'front-quarter':(-6.3,-8.5,1.65),'mirror':(-1.45,-2.2,1.38),'mirror-rear':(-.30,-.20,1.42),'sensor':(-1.4,-2.5,1.28),'roof-sensor':(-1.4,-1.2,2.4),'windscreen-sensor':(-1.8,-.25,1.52),'key':(.14,.22,1.04),'tire':(-1.34,-2.5,.66),'roof-close':(-1.6,-2.2,3.3),'handle':(-.46,-2.4,1.24),'charge':(3.3,3.0,1.35),'underbody':(4,-5,-2.4),'rear-lamp':(3.55,-1.40,1.20),'rear-wiper':(3.5,-.28,1.45),'rear-camera':(3.1,-.28,1.76),'rear':(8,0,.84),'rear-photo':(8.8,0,1.7),'rear-quarter':(6.3,-8.5,1.65),'side':(0,-8,.84),'wheel':(-1.418,-3,.37),'lamp':(-3.5,-1.3,.83),'badge':(-3.5,0,1.12),'hood':(-5,0,2.7),'hood-quarter':(-5,-3.5,2.5),'trunk':(6.4,-4.4,2.45),'sunroof':(-2.5,-3.5,5.2),'door-interior':(1.5,.8,1.5),'interior':(.20,0,1.39),'seats':(-.42,0,1.40)}[detail_view]
    targets={'rear-lamp':(2.18,-.65,1.065),'rear-wiper':(2.15,-.12,1.205),'rear-camera':(1.94,0,1.55),'mirror':(-.865,-1.06,1.16),'mirror-rear':(-.835,-1.025,1.16),'sensor':(-1.157,-.96,1.022),'roof-sensor':(-.345,0,1.64),'windscreen-sensor':(-.52,0,1.41),'key':(0,0,.84),'tire':(-1.418,-.935,.37),'roof-close':(.5,0,1.60),'door-interior':(.5,-1.3,.75),'interior':(-.73,0,1.04),'seats':(.42,0,.91),'charge':(1.74,.94,.910),'underbody':(0,0,.25)}
    target=targets.get(detail_view) or ((-.026,-.91,.984) if detail_view=='handle' else (1.5,0,1.3) if detail_view=='trunk' else (.55,0,1.50) if detail_view=='sunroof' else (-1.6,0,1.40) if detail_view=='hood' else (-1.25,0,1.22) if detail_view=='hood-quarter' else (-2.35,0,.944) if detail_view=='badge' else (-2.24,-.75,.741) if detail_view=='lamp' else (-1.418,-.9,.37) if detail_view=='wheel' else (0,0,.84))
    camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='PERSP' if detail_view in {'front-quarter','rear-quarter','hood-quarter','front-photo','rear-photo','trunk','interior','seats'} else 'ORTHO'
    if detail_view in {'front-photo','rear-photo'}:camera.data.lens=68
    if detail_view=='interior':camera.data.lens=16.5
    if detail_view=='seats':camera.data.lens=14
    if detail_view=='sunroof':camera.data.ortho_scale=3.6
    camera.data.ortho_scale=.85 if detail_view=='rear-lamp' else .68 if detail_view=='rear-wiper' else .28 if detail_view=='rear-camera' else 5.5 if detail_view in {'side','underbody'} else 3.6 if detail_view=='sunroof' else .56 if detail_view=='charge' else .45 if detail_view in {'mirror','mirror-rear'} else .38 if detail_view=='sensor' else .39 if detail_view=='roof-sensor' else .56 if detail_view=='windscreen-sensor' else .14 if detail_view=='key' else .82 if detail_view=='tire' else 2.8 if detail_view=='roof-close' else 1.9 if detail_view=='door-interior' else .31 if detail_view=='handle' else .25 if detail_view=='badge' else .48 if detail_view=='lamp' else .90 if detail_view=='wheel' else 2.5
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
if detail_view in {'rear-lamp','rear-wiper','rear-camera','front','rear','wheel','lamp','badge','handle','mirror','mirror-rear','sensor','roof-sensor','windscreen-sensor','key','tire'}:scene.render.resolution_x=900;scene.render.resolution_y=900
scene.view_settings.view_transform='AgX';scene.view_settings.exposure=-.25

# ── Animation mode (--animation): replay the welcome-page entrance flow ──
# Reads per-frame poses exported from src/render/entrance.js (single source of
# truth) and drives the vehicle root, camera and wheels in Blender, then muxes
# the PNG sequence to mp4 with ffmpeg. Coordinate transform three(Y-up)→blender
# (Z-up): (x,y,z)→(x,-z,y) — three's Y(height) maps to blender Z, three's Z
# (depth) maps to blender -Y. Yaw around three Y → rotation around blender Z
# (negated to match the handedness flip on the depth axis).
animate='--animation' in sys.argv
if animate:
    import math as _m, json as _json, subprocess, shlex
    fps=int(next((a.split('=',1)[1] for a in sys.argv if a.startswith('--fps=')),24))
    poses_path=ROOT/'public/models/entrance-poses.json'
    poses=_json.loads(poses_path.read_text())
    maxf=int(next((a.split('=',1)[1] for a in sys.argv if a.startswith('--max-frames=')),0))
    if maxf: poses=poses[:maxf]
    total=len(poses)
    scene.render.fps=fps;scene.frame_start=1;scene.frame_end=total
    engine='BLENDER_EEVEE'
    try: scene.render.engine=engine
    except Exception:
        scene.render.engine='CYCLES';scene.cycles.samples=64 if preview else 96
    if scene.render.engine.startswith('BLENDER_EEVEE'):
        scene.eevee.taa_render_samples=32 if preview else 128
    # Parent every non-studio object under a fresh vehicle root so the whole
    # car (body + wheels + lamps + interior) translates/rotates as one rig.
    # Use parent_set semantics: set parent WITHOUT matrix_parent_inverse so the
    # child keeps its world transform and follows car_root's animation faithfully.
    car_root=bpy.data.objects.new('Entrance car root',None)
    studio.objects.link(car_root)
    car_root.location=(0,0,0); car_root.rotation_euler=(0,0,0)
    bpy.context.view_layer.update()
    studio_objs=set(studio.objects)
    parent_targets=[]
    for o in list(bpy.data.objects):
        if o is car_root or o in studio_objs or o.type in {'CAMERA','LIGHT'}: continue
        # Skip the marketing/user empties parked at x≈8 (decor), keep real parts.
        if abs(o.location.x)>5 and o.type=='EMPTY': continue
        parent_targets.append(o)
    for o in parent_targets:
        # Preserve world transform: compute the inverse so children stay put,
        # then they follow car_root as it animates. Using world matrix at bind
        # time (car_root at origin) gives identity inverse → children keep
        # local = world, and animate correctly with car_root.
        o.parent=car_root
    bpy.context.view_layer.update()
    # Wheel rigs: rim/tire/brake per corner. Names: rim_<side>_<z>, tire_<side>_<z>,
    # brake_<side>_<z> where side=-1 is left, +1 right; x<0 is front (-X nose).
    corners={
        'fl':('rim_-1_-1.418','tire_-1_-1.418','brake_-1_-1.418'),
        'fr':('rim_-1_1.418','tire_-1_1.418','brake_-1_1.418'),
        'rl':('rim_1_-1.418','tire_1_-1.418','brake_1_-1.418'),
        'rr':('rim_1_1.418','tire_1_1.418','brake_1_1.418'),
    }
    axle=Vector((1,0,0)); up_axis=Vector((0,0,1))
    # Save each wheel's local base rotation so rolling/steering compound cleanly.
    wheel_base={}; wheel_loc={}
    for cid,(rim,tire,brake) in corners.items():
        for n in (rim,tire,brake):
            o=bpy.data.objects.get(n)
            if o:
                wheel_base[n]=o.rotation_euler.copy(); wheel_loc[n]=o.location.copy()
    camera.data.type='PERSP'
    cam_target=bpy.data.objects.new('Camera target',None); studio.objects.link(cam_target)
    track=camera.constraints.new('TRACK_TO'); track.target=cam_target; track.track_axis='TRACK_NEGATIVE_Z'; track.up_axis='UP_Y'
    for f in poses:
        fr=f['frame']
        # Vehicle pose: three (x,y,z) -> blender (x,-z,y); yaw(Y) -> yaw around Z.
        car_root.location=(f['pos'][0],-f['pos'][2],f['pos'][1])
        car_root.rotation_euler=(0,0,f['yaw'])
        car_root.keyframe_insert(data_path='location',frame=fr)
        car_root.keyframe_insert(data_path='rotation_euler',frame=fr)
        # Camera + target (same transform); fov (vertical, degrees) → lens (mm).
        camera.location=(f['cam'][0],-f['cam'][2],f['cam'][1])
        cam_target.location=(f['tgt'][0],-f['tgt'][2],f['tgt'][1])
        camera.data.lens= 36/(2*_m.tan(_m.radians(f['fov'])/2))  # sensor 36mm: lens = 36/(2·tan(fov/2))
        for n in ('location',): camera.keyframe_insert(data_path=n,frame=fr)
        cam_target.keyframe_insert(data_path='location',frame=fr)
        # Wheels: rolling (around X) + front steering (around Z).
        for cid,(rim,tire,brake) in corners.items():
            roll=f['wheel'][cid]; steer=f['steer'].get(cid,0) if cid in ('fl','fr') else 0
            for n in (rim,tire):
                o=bpy.data.objects.get(n)
                if not o: continue
                # Reset then apply: roll around local X, steer around local Z.
                base=wheel_base.get(n)
                o.rotation_euler=(_m.degrees(roll),0,0)  # rolling around X (blender axle)
                if steer: o.rotation_euler.z+=_m.degrees(steer)
                o.keyframe_insert(data_path='rotation_euler',frame=fr)
    if preview:
        scene.render.resolution_x=960;scene.render.resolution_y=600
    else:
        scene.render.resolution_x=1600;scene.render.resolution_y=1000
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    base='aura-t6-entrance-preview' if preview else 'aura-t6-entrance'
    framedir=ROOT/'output/playwright'/f'{base}-frames'
    framedir.mkdir(parents=True,exist_ok=True)
    scene.render.filepath=str(framedir/'frame_####')
    print('RENDER_START_ENTRANCE',scene.render.engine,total,'frames ->',framedir,flush=True)
    # Render frame-by-frame (frame_set + write_still) instead of animation=True:
    # this guarantees each frame's keyframes are applied before render, which
    # is more reliable than relying on the animation loop's frame advances.
    for fr in range(1, total+1):
        scene.frame_set(fr)
        deps=bpy.context.evaluated_depsgraph_get()
        deps.update()
        scene.render.filepath=str(framedir/f'frame_{fr:04d}')
        bpy.ops.render.render(write_still=True)
        if fr%20==0 or fr==total: print('FRAME',fr,'/',total,flush=True)
    outmp4=ROOT/'output/playwright'/f'{base}.mp4'
    pattern=str(framedir/'frame_%04d.png')
    cmd=['ffmpeg','-y','-framerate',str(fps),'-i',pattern,'-c:v','libx264',
         '-pix_fmt','yuv420p','-crf','23','-preset','fast' if preview else 'medium',str(outmp4)]
    print('MUX_START',shlex.join(cmd),flush=True)
    subprocess.run(cmd,check=True)
    print('RENDER_SAVED_ENTRANCE',outmp4)
else:
    scene.render.image_settings.file_format='PNG'
    filename=f'aura-t6-detail-{detail_view}.png' if detail_view else ('aura-t6-cycles-preview.png' if preview else 'aura-t6-cycles.png')
    output=ROOT/'output/playwright'/filename;scene.render.filepath=str(output)
    if not detail_view:bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'models/aura-t6-studio.blend'))
    print('RENDER_START',scene.cycles.device,flush=True)
    bpy.ops.render.render(write_still=True)
    print('RENDER_SAVED',output)
