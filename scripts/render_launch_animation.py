"""Launch-stage entrance animation — 10s cinematic car reveal.

Opens the existing aura-t6.blend, builds a dark launch stage, drives the car
along an infinity-single-loop path (real left turn), animates a one-shot
camera with Track-To, and renders an mp4. Original meshes/materials untouched;
all additions go into a 'Launch stage' collection. Run:

    blender --background --python scripts/render_launch_animation.py -- --preview
    blender --background --python scripts/render_launch_animation.py
"""
import bpy, bmesh, math, sys, json, subprocess, shlex
from pathlib import Path
from mathutils import Vector, Matrix, Euler

ROOT = Path(__file__).resolve().parents[1]
BLEND = ROOT / 'models/aura-t6.blend'
preview = '--preview' in sys.argv
quick = '--quick' in sys.argv  # render only a few key frames for fast verify

# ── Constants ──
FPS = 24
DURATION = 10
TOTAL = FPS * DURATION  # 240
WHEEL_RADIUS = 0.372
WHEELBASE = 2.84
HALF_TRACK = 0.93

# ── Open the blend file ──
bpy.ops.wm.open_mainfile(filepath=str(BLEND))
scene = bpy.context.scene

# ── Launch stage collection ──
stage = bpy.data.collections.new('Launch stage')
scene.collection.children.link(stage)

def to_stage(obj):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    stage.objects.link(obj)

# ── Dark enclosed background ──
# Large inverted sphere / cylinder so no exterior shows.
bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=60, depth=40,
                                    location=(0, 0, 15))
bg = bpy.context.object
bg.name = 'Stage shell'
bg.rotation_euler = (0, 0, 0)
bg_mat = bpy.data.materials.new('Stage shell mat')
bg_mat.use_nodes = True
bg_bsdf = bg_mat.node_tree.nodes['Principled BSDF']
bg_bsdf.inputs['Base Color'].default_value = (0.012, 0.014, 0.018, 1)
bg_bsdf.inputs['Roughness'].default_value = 1
bg_bsdf.inputs['Metallic'].default_value = 0
bg.data.materials.append(bg_mat)
to_stage(bg)
# Flip normals inward
bpy.context.view_layer.objects.active = bg
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.flip_normals()
bpy.ops.object.mode_set(mode='OBJECT')

# ── Reflective dark floor ──
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, 0))
floor = bpy.context.object
floor.name = 'Stage floor'
floor_mat = bpy.data.materials.new('Stage floor mat')
floor_mat.use_nodes = True
fbsdf = floor_mat.node_tree.nodes['Principled BSDF']
fbsdf.inputs['Base Color'].default_value = (0.035, 0.038, 0.045, 1)
fbsdf.inputs['Metallic'].default_value = 0.35
fbsdf.inputs['Roughness'].default_value = 0.18
floor.data.materials.append(floor_mat)
to_stage(floor)

# ── Lighting: overhead spots + linear strips + ambient ──
def area_light(name, loc, power, color, size_x, size_y, rot=(0, 0, 0)):
    data = bpy.data.lights.new(name, 'AREA')
    data.energy = power
    data.color = color
    data.shape = 'RECTANGLE'
    data.size = size_x
    data.size_y = size_y
    obj = bpy.data.objects.new(name, data)
    stage.objects.link(obj)
    obj.location = loc
    obj.rotation_euler = rot
    return obj

# Key overhead softboxes
area_light('Key overhead', (0, -2, 9), 6000, (0.85, 0.92, 1), 8, 4,
           rot=(math.radians(20), 0, 0))
area_light('Warm rim', (6, 4, 5), 3000, (1, 0.72, 0.5), 5, 2,
           rot=(math.radians(-30), math.radians(25), 0))
area_light('Cool fill', (-6, -3, 5), 2500, (0.7, 0.82, 1), 5, 3,
           rot=(math.radians(25), math.radians(-20), 0))
# Linear light strips (blue-white ambiance) along floor edges
for i, (x, y) in enumerate([(-12, 6), (12, 6), (-12, -6), (12, -6)]):
    area_light(f'Strip {i}', (x, y, 0.15), 200, (0.6, 0.75, 1), 0.3, 10,
               rot=(0, 0, math.radians(90) if abs(x) > 5 else 0))

# Subtle world ambient
world = bpy.data.worlds.new('Launch ambient')
world.use_nodes = True
wn = world.node_tree.nodes
wn.clear()
out = wn.new('ShaderNodeOutputWorld')
bg_n = wn.new('ShaderNodeBackground')
bg_n.inputs['Color'].default_value = (0.015, 0.02, 0.03, 1)
bg_n.inputs['Strength'].default_value = 0.6
world.node_tree.links.new(bg_n.outputs[0], out.inputs[0])
scene.world = world

# ── Identify car parts & build CAR_CTRL ──
# Wheels: rim_<side>_<xpos>, tire_<side>_<xpos>
#   side=-1 → y=-0.93 (left), side=1 → y=+0.93 (right)
#   xpos=-1.418 → front (x=-1.42), xpos=1.418 → rear (x=+1.42)
WHEELS = {
    'fl': ('rim_-1_-1.418', 'tire_-1_-1.418'),  # front-left
    'fr': ('rim_1_-1.418',  'tire_1_-1.418'),   # front-right
    'rl': ('rim_-1_1.418',  'tire_-1_1.418'),   # rear-left
    'rr': ('rim_1_1.418',   'tire_1_1.418'),     # rear-right
}
# Wheel rolling axis: car forward is -X, axle along Y → roll around Y.
ROLL_AXIS = Vector((0, 1, 0))

# CAR_CTRL: parent all top-level car objects (exclude stage shell/floor/lights)
car_root = bpy.data.objects.new('CAR_CTRL', None)
stage.objects.link(car_root)
car_root.location = (0, 0, 0)
bpy.context.view_layer.update()
car_inv = car_root.matrix_world.inverted()
car_objs = []
for o in list(bpy.data.objects):
    if o.parent is not None:
        continue
    if o in set(stage.objects) or o.type in ('CAMERA', 'LIGHT'):
        continue
    if o.name.startswith('aura-') and 'user' in o.name.lower():
        continue  # marketing empties
    if abs(o.location.x) > 5 and o.type == 'EMPTY':
        continue  # decor empties
    car_objs.append(o)
for o in car_objs:
    o.parent = car_root
    o.matrix_parent_inverse = car_inv
bpy.context.view_layer.update()
print(f'[LAUNCH] CAR_CTRL parented {len(car_objs)} objects')

# ── Path: infinity single-loop, real left turn ──
# Top-view waypoints (X right, Y forward-up). Car enters upper-left, moves to
# center, turns LEFT (curves toward +X,+Y), loops clockwise-on-right, returns
# to center, parks at hero angle.
# The path crosses itself once at center (∞ single loop).
path_points = [
    (-12,   8, 0),   # entry, upper-left
    (-6,    4, 0),   # approaching center
    (-2,    1, 0),   # near center
    ( 0,    0, 0),   # center — enter loop
    ( 1,    3, 0),   # curving up (left turn)
    ( 4,    3.5, 0), # top of loop
    ( 6,    1, 0),   # right side
    ( 5,   -2.5, 0), # bottom-right
    ( 2,   -3.5, 0), # bottom
    (-1,   -2, 0),   # curving back
    ( 0,    0, 0),   # center — exit loop (self-cross)
    ( 0.3,  0.5, 0), # settle toward hero pose
]

# Build Bezier curve
curve_data = bpy.data.curves.new('CAR_PATH', type='CURVE')
curve_data.dimensions = '3D'
curve_data.resolution_u = 24
spline = curve_data.splines.new('BEZIER')
spline.bezier_points.add(len(path_points) - 1)
for i, (x, y, z) in enumerate(path_points):
    bp = spline.bezier_points[i]
    bp.co = (x, y, z)
    bp.handle_left_type = 'AUTO'
    bp.handle_right_type = 'AUTO'
path_obj = bpy.data.objects.new('CAR_PATH', curve_data)
stage.objects.link(path_obj)

# Sample the curve densely for arc-length-parametric motion
curve_obj = path_obj
# Evaluate curve at parameter u (0..1) → world position + tangent
deps_graph = bpy.context.evaluated_depsgraph_get()
curve_eval = curve_obj.evaluated_get(deps_graph)
curve_data_eval = curve_eval.data
SAMPLES = 2000
sample_pts = []
for i in range(SAMPLES + 1):
    u = i / SAMPLES
    pos = curve_data_eval.splines[0].bezier_points  # fallback
# Use Blender's curve evaluation via mesh conversion for reliable sampling
# Convert curve to mesh temporarily
temp_mesh = curve_eval.to_mesh()
# Actually use matrix_world sampling via depsgraph is complex; use mathutils approach:
# Simpler: use bpy.path & curve.bezier_points with de Casteljau
def bezier_eval(spline, t):
    """Evaluate Bezier spline at parameter t (0..1) using segment lookup."""
    bps = spline.bezier_points
    n = len(bps)
    # find segment
    seg_t = t * (n - 1)
    seg = min(int(seg_t), n - 2)
    local = seg_t - seg
    p0 = bps[seg].co
    p1 = bps[seg].handle_right
    p2 = bps[seg + 1].handle_left
    p3 = bps[seg + 1].co
    u = local
    # cubic Bezier
    pos = (1-u)**3 * p0 + 3*(1-u)**2*u * p1 + 3*(1-u)*u**2 * p2 + u**3 * p3
    # tangent
    tang = 3*(1-u)**2*(p1-p0) + 6*(1-u)*u*(p2-p1) + 3*u**2*(p3-p2)
    return pos.copy(), tang.copy()

# Build arc-length table
raw = []  # (cumlen, pos, tang)
cum = 0
prev = None
for i in range(SAMPLES + 1):
    t = i / SAMPLES
    pos, tang = bezier_eval(spline, t)
    if prev:
        cum += (pos - prev).length
    raw.append((cum, pos, tang))
    prev = pos.copy()
total_len = cum

def sample_at_arc(s):
    """Sample path at arc length s (0..total_len). Returns (pos, tangent_dir)."""
    s = max(0, min(s, total_len))
    # binary search
    lo, hi = 0, len(raw) - 1
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if raw[mid][0] < s:
            lo = mid
        else:
            hi = mid
    c0, p0, t0 = raw[lo]
    c1, p1, t1 = raw[hi]
    frac = (s - c0) / (c1 - c0) if c1 > c0 else 0
    pos = p0.lerp(p1, frac)
    tang = t0.lerp(t1, frac).normalized()
    return pos, tang

# Speed profile: fast approach → slow (logo bullet) → resume → decelerate
# Map frame (0..TOTAL) to arc length (0..total_len) with variable speed.
# Phases (in frames): F1-56 entry accel, F56-109 loop, F109-128 decel, 
# F128-159 bullet slow, F159-217 resume, F217-240 park decel.
def arc_for_frame(f):
    """Arc length at frame f, with speed variation."""
    t = f / TOTAL  # 0..1
    # Segment breakpoints (fraction of total time → fraction of total arc)
    # Entry (0-0.23): 0 → 0.30 of arc (accelerating)
    # Loop (0.23-0.45): 0.30 → 0.62 (steady, includes loop)
    # Decel (0.45-0.53): 0.62 → 0.68 (slowing for logo)
    # Bullet (0.53-0.66): 0.68 → 0.72 (very slow, logo hero)
    # Resume (0.66-0.90): 0.72 → 0.95 (speed up)
    # Park (0.90-1.0): 0.95 → 1.0 (decelerate to stop)
    bps = [
        (0.00, 0.00), (0.23, 0.30), (0.45, 0.62), (0.53, 0.68),
        (0.66, 0.72), (0.90, 0.95), (1.00, 1.00),
    ]
    for i in range(len(bps) - 1):
        if bps[i][0] <= t <= bps[i+1][0]:
            u = (t - bps[i][0]) / (bps[i+1][0] - bps[i][0]) if bps[i+1][0] > bps[i][0] else 1
            # smoothstep for natural ease
            u = u * u * (3 - 2 * u)
            return (bps[i][1] + u * (bps[i+1][1] - bps[i][1])) * total_len
    return total_len

# ── Camera system: CAM_CTRL, CAMERA, LOOK_AT, FOCUS ──
cam_data = bpy.data.cameras.new('CAMERA')
cam_data.lens = 50
camera = bpy.data.objects.new('CAMERA', cam_data)
stage.objects.link(camera)
scene.camera = camera

look_at = bpy.data.objects.new('LOOK_AT', None)
stage.objects.link(look_at)
look_at.location = (0, 0, 0.7)

focus = bpy.data.objects.new('FOCUS', None)
stage.objects.link(focus)
focus.location = (0, 0, 0.7)

# Track To constraint
track = camera.constraints.new('TRACK_TO')
track.target = look_at
track.track_axis = 'TRACK_NEGATIVE_Z'
track.up_axis = 'UP_Y'

# CAM_CTRL (empty parent for camera position — not strictly needed but per spec)
cam_ctrl = bpy.data.objects.new('CAM_CTRL', None)
stage.objects.link(cam_ctrl)

# ── Keyframe the car along path ──
scene.frame_start = 1
scene.frame_end = TOTAL
scene.render.fps = FPS

# Save wheel base rotations
wheel_base_rot = {}
for cid, (rim, tire) in WHEELS.items():
    for n in (rim, tire):
        o = bpy.data.objects.get(n)
        if o:
            wheel_base_rot[n] = o.rotation_euler.copy()

prev_arc = 0
for f in range(1, TOTAL + 1):
    arc = arc_for_frame(f)
    pos, tang = sample_at_arc(arc)
    # Car yaw: forward is -X, so yaw_z = atan2(-tang.y, -tang.x) maps -X→tangent
    # Actually: we want the car's -X direction to point along tangent.
    # -X rotated by yaw_z gives direction (−cos(yaw_z), −sin(yaw_z)).
    # Set equal to tangent (tx, ty): −cos = tx → cos=−tx, −sin=ty → sin=−ty
    # yaw_z = atan2(−ty, −tx)
    yaw_z = math.atan2(-tang.y, -tang.x)
    car_root.location = (pos.x, pos.y, 0)
    car_root.rotation_euler = (0, 0, yaw_z)
    car_root.keyframe_insert(data_path='location', frame=f)
    car_root.keyframe_insert(data_path='rotation_euler', frame=f)

    # Wheel rolling: distance traveled since last frame → rotation around Y
    ds = arc - prev_arc
    roll_angle = ds / WHEEL_RADIUS
    prev_arc = arc
    # Steering: curvature from tangent change (approximate via finite diff)
    # Use next-frame tangent for steering
    arc_next = arc_for_frame(min(f + 1, TOTAL))
    _, tang_next = sample_at_arc(arc_next)
    # curvature ~ d(yaw)/ds
    dyaw = math.atan2(tang_next.y, tang_next.x) - math.atan2(tang.y, tang.x)
    dyaw = math.atan2(math.sin(dyaw), math.cos(dyaw))
    curvature = dyaw / ds if ds > 1e-6 else 0
    steer_fl = math.atan2(WHEELBASE * curvature, 1 + HALF_TRACK * curvature)
    steer_fr = math.atan2(WHEELBASE * curvature, 1 - HALF_TRACK * curvature)

    for cid, (rim, tire) in WHEELS.items():
        for n in (rim, tire):
            o = bpy.data.objects.get(n)
            if not o:
                continue
            base = wheel_base_rot.get(n, Euler((0, 0, 0)))
            # Rolling: accumulate around Y
            roll = Euler((0, roll_angle, 0))
            o.rotation_euler = (base.x + roll.x, base.y + roll.y, base.z)
            # Front wheel steering around Z
            if cid in ('fl', 'fr'):
                steer = steer_fl if cid == 'fl' else steer_fr
                o.rotation_euler = (base.x + roll.x, base.y + roll.y,
                                    base.z + steer)
            o.keyframe_insert(data_path='rotation_euler', frame=f)

# ── Camera keyframes (6-phase timeline) ──
# F1-56: low wide → front close-up, 35mm→70mm
# F56-109: along fender→side→rear
# F109-128: to tail, push to logo
# F128-159: logo bullet, camera micro-orbit ~15°
# F159-217: pull back, rise, orbit to diagonal front
# F217-240: settle to 35-45° hero
cam_keys = [
    # (frame, cam_loc, look_at_loc, lens)
    (1,   (-14, -10, 2.5), (0, 0, 0.9), 35),
    (56,  (-5, -5, 1.6),  (-1.5, 0, 0.9), 70),
    (109, (3, -4, 1.8),   (2, 0, 0.9), 50),
    (128, (5, 0, 1.0),    (2.39, 0, 0.6), 85),   # logo close-up, target on badge
    (159, (4.5, 2, 1.3),  (2.39, 0, 0.6), 85),   # micro-orbit
    (217, (-8, 6, 4.0),   (0, 0, 0.9), 50),      # pull back, rise
    (240, (-7, 7, 3.2),   (0, 0, 0.9), 50),      # hero 35-45°
]
for fr, cloc, lloc, lens in cam_keys:
    camera.location = cloc
    look_at.location = lloc
    camera.data.lens = lens
    camera.keyframe_insert(data_path='location', frame=fr)
    look_at.keyframe_insert(data_path='location', frame=fr)
    camera.data.keyframe_insert(data_path='lens', frame=fr)

# ── Render settings ──
scene.render.engine = 'BLENDER_EEVEE'
scene.eevee.taa_render_samples = 64 if preview else 128
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.view_settings.view_transform = 'AgX'
scene.view_settings.exposure = 0.15
scene.render.image_settings.file_format = 'PNG'

# ── Save the animated blend file ──
save_path = ROOT / 'models/launch-animation.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(save_path))
print(f'[LAUNCH] Saved blend: {save_path}')

# ── Render ──
base = 'launch-preview' if preview else 'launch'
if quick:
    # Render only key frames for fast verification
    key_frames = [1, 56, 109, 128, 159, 217, 240]
else:
    key_frames = range(1, TOTAL + 1)

framedir = ROOT / 'output' / 'playwright' / f'{base}-frames'
framedir.mkdir(parents=True, exist_ok=True)

for fr in key_frames:
    scene.frame_set(fr)
    bpy.context.view_layer.update()
    scene.render.filepath = str(framedir / f'frame_{fr:04d}')
    bpy.ops.render.render(write_still=True)
    if fr % 24 == 0 or fr == 1 or fr == TOTAL:
        print(f'[LAUNCH] Rendered frame {fr}/{TOTAL}', flush=True)

# Mux to mp4 with ffmpeg (only if full render)
if not quick:
    outmp4 = ROOT / 'output' / 'playwright' / f'{base}.mp4'
    pattern = str(framedir / 'frame_%04d.png')
    cmd = ['ffmpeg', '-y', '-framerate', str(FPS), '-i', pattern,
           '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20',
           '-preset', 'fast' if preview else 'medium', str(outmp4)]
    print(f'[LAUNCH] MUX: {shlex.join(cmd)}', flush=True)
    subprocess.run(cmd, check=True)
    print(f'[LAUNCH] SAVED: {outmp4}')
else:
    print(f'[LAUNCH] Quick verify frames in {framedir}')
