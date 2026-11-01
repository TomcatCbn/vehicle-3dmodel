"""Create an independently articulated AURA T6 exterior reference model, not OEM CAD.
Run: blender --background --python scripts/build_aura_t6.py
"""
import bpy
import math
import json
import sys
from pathlib import Path
from mathutils import Vector, Matrix
from mathutils.geometry import tessellate_polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).resolve().parent))
from aura_surface import (belt_height, side_width, front_width, front_surface,
                          rear_width, rear_surface, side_surface, grille_top, smoothstep, section,
                          front_top, rear_window_point, rear_shoulder_point, tailgate_width, rear_split_height, diffuser_top,
                          front_deck_point, bonnet_point, bonnet_front, bonnet_rear, HOOD_HALF_SPAN, HOOD_HINGE,
                          front_deck_normal, bonnet_normal, bonnet_side_u, light_bar_point, TAILGATE_HINGE)
from vw_emblem import V as VW_V, W as VW_W, RING_INNER as VW_RING_INNER
OUT = ROOT / 'public/models'
SOURCE = ROOT / 'models'
OUT.mkdir(parents=True, exist_ok=True)
SOURCE.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
parts = []

def mat(name, color, metallic=0, roughness=.4, emission=0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Metallic'].default_value = metallic
    p.inputs['Roughness'].default_value = roughness
    if name == 'Paint':
        p.inputs['Coat Weight'].default_value = .85
        p.inputs['Coat Roughness'].default_value = .2
    if emission:
        p.inputs['Emission Color'].default_value = (*color, 1)
        p.inputs['Emission Strength'].default_value = emission
    return m

paint = mat('Paint', (.095,.265,.22), .48,.28)
handle_cup = mat('Paint handle cup', (.0304,.0848,.0704), .35,.40)
handle_mark = mat('Handle touch sensor etching', (.17,.27,.24), .05,.58)
model_plate = mat('Model plate matte black', (.006,.008,.011), 0,.48)
plate_lettering = mat('Model plate lettering', (.72,.77,.78), 0,.42)
black = mat('Obsidian trim', (.012,.018,.022), .35,.32)
rubber = mat('Tire rubber', (.015,.017,.019), 0,.88)
tire_letter = mat('Moulded tire lettering', (.011,.012,.013), 0,.76)
mirror_cap = mat('Mirror gloss black cap', (.005,.007,.009), .08,.28)
mirror_cap.node_tree.nodes.get('Principled BSDF').inputs['Coat Weight'].default_value=.45
sensor_black = mat('Sensor satin housing', (.006,.008,.010), .06,.37)
indicator_lens = mat('Mirror indicator smoked cover', (.09,.11,.12), 0,.16)
indicator_lens.node_tree.nodes.get('Principled BSDF').inputs['Transmission Weight'].default_value=.28
mirror_shell = mat('Mirror satin black upper cap', (.004,.005,.006), 0,.30)
mirror_shell.node_tree.nodes.get('Principled BSDF').inputs['Coat Weight'].default_value=.32
mirror_shell.node_tree.nodes.get('Principled BSDF').inputs['Coat Roughness'].default_value=.27
mirror_lower = mat('Mirror moulded lower housing', (.004,.005,.006), 0,.47)
mirror_ribs = mat('Mirror indicator optical prisms', (.24,.27,.28), 0,.26)
mirror_glass = mat('Mirror reflective glass', (.38,.45,.48), .98,.07)
sensor_optic = mat('Sensor optical glass', (.008,.015,.020), .08,.09)
sensor_optic.node_tree.nodes.get('Principled BSDF').inputs['Coat Weight'].default_value=.8
sensor_optic.node_tree.nodes.get('Principled BSDF').inputs['Transmission Weight'].default_value=.18
glass = mat('Glazing', (.045,.075,.095), .0,.08)
alloy = mat('Machined alloy', (.56,.62,.65), .88,.24)
steel = mat('Structural steel', (.12,.16,.18), .7,.42)
leather = mat('Gray perforated upholstery', (.20,.22,.215), 0,.82)
door_leather = mat('Gray door upholstery', (.19,.21,.205), 0,.78)
door_seam = mat('Gray upholstery stitching', (.075,.090,.085), 0,.86)
caliper_red = mat('Red brake caliper', (.68,.012,.018), .32,.32)
seat_dark = mat('Seat backs', (.075,.085,.082), 0,.7)
dash_soft = mat('Dashboard gray soft touch', (.16,.18,.18), 0,.74)
dash_lower = mat('Dashboard lower gray trim', (.22,.24,.235), 0,.70)
console_trim = mat('Center console light gray', (.34,.36,.35), 0,.68)
screen_glass = mat('Display piano black bezel', (.004,.006,.010), .08,.16)
screen_ui = mat('Display cool white graphics', (.56,.72,.86), .05,.30,.45)
screen_accent = mat('Display violet graphics', (.19,.10,.42), .05,.34,.35)
low_beam = mat('Low beam white blue LED', (.78,.94,1), 0,.16, 3)
high_beam = mat('High beam white blue LED', (.78,.94,1), 0,.16, 5)
for material in [low_beam,high_beam]:
    bsdf=material.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value=(.045,.070,.090,1)
    bsdf.inputs['Metallic'].default_value=.18
    bsdf.inputs['Coat Weight'].default_value=.75
    bsdf.inputs['Transmission Weight'].default_value=.12
brake_light = mat('Brake red LED', (1,.0225,.03125), 0,.25, 5)
reverse_light = mat('Reverse white LED', (.92,.96,1), 0,.25, 3)
rear_led = mat('Rear fine light guide LED',(.42,.004,.008),0,.3,1.3)
ambient_light = mat('Ambient warm LED', (1,.58,.28), 0,.3, 1.5)
charge_light = mat('Charge green LED', (.025,1,.225), 0,.25, 2)
charge_plastic = mat('Charge port grained polymer',(.018,.022,.025),0,.68)
charge_terminal = mat('Charge socket terminal alloy',(.43,.39,.29),.82,.25)
warning_yellow = mat('High voltage warning yellow',(.62,.53,.045),0,.62)
reflector_red = mat('Red reflector', (.35,.008,.012), .1,.24)
cell = mat('Battery modules', (.29,.49,.37), .55,.4)
screen = mat('Display', (.018,.032,.085), .10,.20,.18)
white = mat('Badging', (.76,.81,.8), .5,.3)
lamp_glass = mat('Lamp optical lens', (.028,.04,.05), 0,.06)
lamp_glass.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.12,.145,.17,1)
lamp_glass.node_tree.nodes.get('Principled BSDF').inputs['Transmission Weight'].default_value=.98
lamp_glass.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.035
optic = mat('Projector precision optics',(.16,.20,.23),.18,.10)
optic.node_tree.nodes.get('Principled BSDF').inputs['Coat Weight'].default_value=.7
lamp_chrome=mat('Smoked optical reflector',(.20,.24,.27),.94,.18)
badge_silver=mat('VW satin silver',(.76,.79,.82),.72,.20)
badge_edge=mat('VW polished edge',(.52,.57,.62),.96,.13)
badge_black=mat('VW piano black',(.004,.006,.009),.22,.15)
badge_black.node_tree.nodes.get('Principled BSDF').inputs['Coat Weight'].default_value=.8
rear_glazing=glass.copy();rear_glazing.name='Glazing rear privacy'
rear_glazing.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.025,.040,.045,1)
rear_glazing.node_tree.nodes.get('Principled BSDF').inputs['Transmission Weight'].default_value=.42
valance_black=mat('Rear valance satin insert',(.009,.013,.016),.18,.40)
well_liner = mat('Wheel well liner',(.008,.010,.012),0,.95)
roof_z=section([(-.32,1.60),(.15,1.632),(.75,1.634),(1.15,1.61),(1.45,1.56),(1.70,1.50)])
roof_w=section([(-.32,.740),(.15,.755),(.75,.765),(1.15,.765),(1.45,.755),(1.70,.735)])

def cabin_width(x,z):
    base=belt_height(x);t=max(0,min(1,(z-base)/(roof_z(x)-base)))
    return side_width(x,base)*(1-t)+roof_w(x)*t+.006*math.sin(t*math.pi)

def part(name, label, layer, position=(0,0,0), offset=(0,0,0), start=.05, motion='', side=0):
    p = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(p)
    p.location = position
    p['part'] = True
    p['label'] = label
    p['layer'] = layer
    p['offset'] = [offset[0], offset[2], -offset[1]]
    p['start'] = start
    p['motion'] = motion
    p['side'] = -side
    parts.append(p)
    return p

def parent(obj, group, material):
    obj.data.materials.append(material)
    bpy.context.view_layer.update()
    obj.parent = group
    obj.matrix_parent_inverse = group.matrix_world.inverted()
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj

def light_role(obj, role):
    obj['lightRole'] = role
    return obj

def light_anchor(name, location, group, role):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    bpy.context.view_layer.update()
    obj.parent = group
    obj.matrix_parent_inverse = group.matrix_world.inverted()
    obj['lightAnchor'] = role
    return obj

def mesh(name, vertices, faces, group, material, thickness=0, bevel=0):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    parent(obj, group, material)
    if thickness:
        mod = obj.modifiers.new('Panel thickness', 'SOLIDIFY')
        mod.thickness = thickness
        mod.use_rim = False
    if bevel:
        mod = obj.modifiers.new('Soft edges', 'BEVEL')
        mod.width = bevel
        mod.segments = 3
        mod.limit_method = 'ANGLE'
        mod.harden_normals = True
        weighted = obj.modifiers.new('Boundary normals', 'WEIGHTED_NORMAL')
        weighted.keep_sharp = True
    return obj

def merge_static_details(group,prefix,material):
    children=[child for child in group.children if child.type=='MESH' and child.name.startswith(prefix)]
    if len(children)<2:return
    bpy.context.view_layer.update();vs=[];fs=[]
    for child in children:
        assert not child.modifiers
        offset=len(vs)
        vs.extend(tuple(child.matrix_world@v.co) for v in child.data.vertices)
        fs.extend(tuple(offset+i for i in face.vertices) for face in child.data.polygons)
    mesh(prefix+' combined',vs,fs,group,material)
    for child in children:bpy.data.objects.remove(child,do_unlink=True)

def box(name, location, dimensions, material, group, bevel=.025):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new('Rounded edges', 'BEVEL')
        mod.width = min(bevel, min(dimensions)*.45)
        mod.segments = 4
        obj.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return parent(obj, group, material)

def tube(name, points, radius, material, group, cyclic=False, smooth=False):
    if smooth:
        points=[tuple(p) for p in points];dense=[]
        for i in range(len(points)-1):
            a,b,c,d=[Vector(points[k]) for k in [max(0,i-1),i,i+1,min(len(points)-1,i+2)]]
            for j in range(10):
                t=j/10
                dense.append(tuple(.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t)))
        points=dense+[points[-1]]
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    curve.resolution_u = 12
    curve.bevel_depth = radius
    curve.bevel_resolution = 3
    curve.use_fill_caps = True
    spline = curve.splines.new('POLY')
    spline.points.add(len(points)-1)
    for p, co in zip(spline.points, points):
        p.co = (*co, 1)
    spline.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target='MESH')
    obj.select_set(False)
    return parent(obj, group, material)

def cylinder(name, location, radius, depth, material, group, axis='Y', vertices=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location)
    obj = bpy.context.object
    obj.name = name
    if axis == 'Y': obj.rotation_euler.x = math.pi/2
    if axis == 'X': obj.rotation_euler.y = math.pi/2
    bevel = obj.modifiers.new('Edge fillet','BEVEL')
    bevel.width = .008
    bevel.segments = 2
    obj.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return parent(obj, group, material)

def ring(name, center, radius, material, group, axis='Y', wire=.007):
    pts = []
    for i in range(72):
        a=i/72*math.tau
        if axis == 'Y': pt=(center[0]+radius*math.cos(a),center[1],center[2]+radius*math.sin(a))
        elif axis == 'Z': pt=(center[0]+radius*math.cos(a),center[1]+radius*math.sin(a),center[2])
        else: pt=(center[0],center[1]+radius*math.cos(a),center[2]+radius*math.sin(a))
        pts.append(pt)
    return tube(name,pts,wire,material,group,True)

def wheel_lathe(name,x,side,profile,group,material):
    vs=[];fs=[];n=128
    for depth,r in profile:
        for i in range(n):
            a=i/n*math.tau;vs.append((x+r*math.cos(a),side*(.817+depth),.37+r*math.sin(a)))
    for j in range(len(profile)-1):
        for i in range(n):
            a=j*n+i;b=j*n+(i+1)%n;face=(a,b,b+n,a+n)
            fs.append(face if side>0 else tuple(reversed(face)))
    return mesh(name,vs,fs,group,material)

def loft(name, rows, group, material, crown=.02, thickness=.015):
    vs=[];fs=[];n=24
    smooth_rows=[]
    for k in range(len(rows)-1):
        p0,p1,p2,p3=rows[max(0,k-1)],rows[k],rows[k+1],rows[min(len(rows)-1,k+2)]
        for step in range(6):
            t=step/6
            smooth_rows.append(tuple(.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t) for a,b,c,d in zip(p0,p1,p2,p3)))
    rows=smooth_rows+[rows[-1]]
    for x,z,w in rows:
        for j in range(n+1):
            t=j/n*2-1
            vs.append((x,w*t,z+crown*(1-t*t)))
    for i in range(len(rows)-1):
        for j in range(n):
            a=i*(n+1)+j;b=a+n+1
            fs.append((a,b,b+1,a+1))
    return mesh(name,vs,fs,group,material,thickness)

def side_skin(name, x0,x1, side, group, arches=False):
    vs=[];fs=[];nx=96;ny=40
    end='front' if x0<-2 else 'rear' if x1>2 else None
    for i in range(nx+1):
        x=x0+(x1-x0)*i/nx
        bottom=.32
        if arches:
            for wx in [-1.418,1.418]:
                dx=x-wx
                if abs(dx)<.402: bottom=max(bottom,.37+math.sqrt(.402**2-dx*dx))
        top=belt_height(x)
        for j in range(ny+1):
            v=j/ny;z=bottom+(top-bottom)*v
            xx,w,_=side_surface(x,z,end)
            xx+=.024*math.sin(v*math.pi)*math.exp(-((x-.18)/.22)**2)
            vs.append((xx,side*w,z))
    for i in range(nx):
        for j in range(ny):
            a=i*(ny+1)+j;b=a+ny+1
            fs.append((a,b,b+1,a+1) if side<0 else (a,a+1,b+1,b))
    return mesh(name,vs,fs,group,paint,.006)

def rounded_outline(corners,radius=.035):
    corners=[Vector(p) for p in corners];outline=[]
    for i,p in enumerate(corners):
        before=corners[(i-1)%len(corners)];after=corners[(i+1)%len(corners)]
        a=p+(before-p)*min(.18,radius/(before-p).length)
        b=p+(after-p)*min(.18,radius/(after-p).length)
        for j in range(8):
            t=j/7;outline.append(a*(1-t)**2+2*p*t*(1-t)+b*t*t)
    dense=[]
    for i,a in enumerate(outline):
        b=outline[(i+1)%len(outline)];steps=max(1,math.ceil((b-a).length/.025))
        dense.extend(a.lerp(b,j/steps) for j in range(steps))
    return dense

def handle_outline(width,height,radius):
    points=[]
    for x,z,a in [(width/2-radius,height/2-radius,0),(-width/2+radius,height/2-radius,math.pi/2),(-width/2+radius,-height/2+radius,math.pi),(width/2-radius,-height/2+radius,math.pi*1.5)]:
        for i in range(9):
            angle=a+i/8*math.pi/2
            points.append((x+radius*math.cos(angle),z+radius*math.sin(angle)))
    return points

def recessed_door_handle(skin,group,x,side):
    z0=.984
    def point(dx,dz,depth):
        xx=x+dx;z=z0+dz;v=(z-.32)/(belt_height(xx)-.32)
        return (xx+.024*math.sin(v*math.pi)*math.exp(-((xx-.18)/.22)**2),side*(side_width(xx,z)+depth),z)
    for modifier in list(skin.modifiers):
        bpy.context.view_layer.objects.active=skin
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    cutter=box('Handle aperture cutter',point(0,0,0),(.224,.14,.080),black,group,.021)
    for modifier in list(cutter.modifiers):
        if modifier.type=='BEVEL':modifier.segments=8
        bpy.context.view_layer.objects.active=cutter
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.context.view_layer.objects.active=skin
    cut=skin.modifiers.new('Recessed handle opening','BOOLEAN');cut.operation='DIFFERENCE';cut.object=cutter
    bpy.ops.object.modifier_apply(modifier=cut.name)
    bpy.data.objects.remove(cutter,do_unlink=True)
    lip=skin.modifiers.new('Handle aperture edge','BEVEL');lip.width=.001;lip.segments=2;lip.limit_method='ANGLE'
    def shell(name,profiles,material,cap=False):
        vs=[];fs=[];n=36
        for width,height,radius,depth in profiles:
            vs.extend(point(dx,dz,depth) for dx,dz in handle_outline(width,height,radius))
        for j in range(len(profiles)-1):
            for i in range(n):
                a=j*n+i;b=j*n+(i+1)%n;face=(a,b,b+n,a+n)
                fs.append(face if side<0 else tuple(reversed(face)))
        if cap:
            face=tuple(range(n))
            back=mesh('Handle pocket back liner',vs[-n:],[face if side<0 else tuple(reversed(face))],group,material);back['detail']='handle'
        obj=mesh(name,vs,fs,group,material);obj['detail']='handle'
        return obj
    shell('Handle perimeter seal',[(.226,.082,.022,.0015),(.222,.078,.020,-.002)],rubber)
    shell('Handle recessed cup',[(.220,.076,.019,-.002),(.212,.068,.019,-.008),(.202,.058,.018,-.021),(.190,.048,.016,-.030),(.176,.038,.014,-.034),(.150,.024,.010,-.035),(.060,.012,.005,-.0352)],handle_cup,True)
    outline=handle_outline(.216,.036,.012)
    vs=[point(0,.020,.0015)]+[point(dx,dz+.020,.0008) for dx,dz in outline]
    fs=[]
    for i in range(len(outline)):
        face=(0,i+1,(i+1)%len(outline)+1);fs.append(face if side<0 else tuple(reversed(face)))
    flap=mesh('Handle flush upper flap',vs,fs,group,paint,.008);flap['detail']='handle'
    seam=tube('Handle fixed end cap joint',[point(.065,dz,.0016) for dz in [.003,.010,.020,.030,.037]],.00065,black,group);seam['detail']='handle'
    mark=tube('Handle touch sensor marking',[point(dx,dz+.020,.0012) for dx,dz in handle_outline(.014,.006,.0015)],.00025,handle_mark,group,True);mark['detail']='handle'

def recessed_charge_port(skin,group,side):
    x0=1.74;z0=.945
    def point(dx,dz,depth):
        x=x0+dx;z=z0+dz;xx,w,_=side_surface(x,z,'rear')
        return (xx,side*(w+depth),z)
    for modifier in list(skin.modifiers):
        bpy.context.view_layer.objects.active=skin
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    cutter=box('Charge aperture cutter',point(0,0,-.025),(.250,.26,.184),black,group,.027)
    for modifier in list(cutter.modifiers):
        if modifier.type=='BEVEL':modifier.segments=10
        bpy.context.view_layer.objects.active=cutter
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.context.view_layer.objects.active=skin
    cut=skin.modifiers.new('Recessed charge port opening','BOOLEAN');cut.operation='DIFFERENCE';cut.object=cutter
    bpy.ops.object.modifier_apply(modifier=cut.name)
    bpy.data.objects.remove(cutter,do_unlink=True)
    lip=skin.modifiers.new('Charge aperture edge','BEVEL');lip.width=.0012;lip.segments=3;lip.limit_method='ANGLE'
    def tagged(obj,inner=False):
        obj['detail']='chargeInner' if inner else 'charge'
        return obj
    def shell(name,profiles,material,cap=False):
        vs=[];fs=[];n=36
        for width,height,radius,depth in profiles:
            vs.extend(point(dx,dz,depth) for dx,dz in handle_outline(width,height,radius))
        for j in range(len(profiles)-1):
            for i in range(n):
                a=j*n+i;b=j*n+(i+1)%n;face=(a,b,b+n,a+n)
                fs.append(face if side<0 else tuple(reversed(face)))
        tagged(mesh(name,vs,fs,group,material,.002))
        if cap:tagged(mesh('Charge port recess back',vs[-n:],[tuple(range(n))],group,material))
    shell('Charge port perimeter weather seal',[(.250,.184,.028,.001),(.240,.174,.025,-.004)],rubber)
    shell('Charge port deep recessed housing',[(.238,.172,.025,-.003),(.226,.160,.024,-.018),(.214,.148,.022,-.047),(.202,.136,.020,-.074)],charge_plastic,True)
    tagged(box('Charge socket shaped mounting panel',point(.010,-.003,-.054),(.184,.014,.124),charge_plastic,group,.020))
    def cyl(name,dx,dz,depth,radius,width,material,vertices=40,inner=False):
        return tagged(cylinder(name,point(dx,dz,depth),radius,width,material,group,'Y',vertices),inner)
    def hoop(name,dx,dz,depth,radius,material,wire=.0015,inner=False):
        return tagged(ring(name,point(dx,dz,depth),radius,material,group,'Y',wire),inner)
    # Viewed from the left-rear camera, positive longitudinal dx appears on the left.
    # The official open-port photographs therefore place AC at +dx and DC at -dx.
    ac=.052;dc=-.045
    cyl('Charge AC socket deep well',ac,-.004,-.041,.040,.010,black,64)
    hoop('Charge AC socket sealing ring',ac,-.004,-.034,.041,charge_plastic,.003)
    hoop('Charge AC socket inner rim',ac,-.004,-.032,.034,black,.0014)
    for i in range(7):
        a=i/7*math.tau;dx=ac+.022*math.cos(a);dz=-.004+.022*math.sin(a)
        cyl('Charge AC signal terminal socket',dx,dz,-.032,.0052,.005,charge_plastic,24)
        cyl('Charge AC signal terminal hole',dx,dz,-.028,.0030,.002,black,24)
    cyl('Charge status indicator dark bezel',.098,.071,-.023,.009,.004,black,48,True)
    light_role(cyl('Charge port status green indicator',.098,.071,-.019,.0048,.0022,charge_light,48,True),'chargeIndicator')
    cyl('Charge DC socket deep well',dc,-.002,-.041,.054,.010,black,72)
    hoop('Charge DC socket sealing ring',dc,-.002,-.034,.055,charge_plastic,.003)
    hoop('Charge DC socket inner rim',dc,-.002,-.032,.049,black,.0015)
    for dx in [dc-.023,dc+.023]:
        cyl('Charge DC power terminal surround',dx,-.012,-.030,.014,.006,charge_plastic,48)
        hoop('Charge DC power terminal alloy rim',dx,-.012,-.025,.0108,charge_terminal,.0018)
        cyl('Charge DC power terminal recess',dx,-.012,-.024,.0088,.003,black,40)
        cyl('Charge DC power terminal contact',dx,-.012,-.022,.0058,.0015,charge_terminal,40)
    for dx,dz in [(dc-.022,.030),(dc,.034),(dc+.022,.030),(dc,.009),(dc-.022,-.039),(dc+.023,-.039)]:
        cyl('Charge DC signal terminal surround',dx,dz,-.029,.0058,.004,charge_plastic,28)
        cyl('Charge DC signal terminal hole',dx,dz,-.025,.0034,.002,black,24)
    for dx in [-.100,.100]:cyl('Charge housing captive screw',dx,.056,-.033,.004,.003,steel,20)
    warning=[point(-.010,.070,-.030),point(.010,.070,-.030),point(0,.052,-.030)]
    tagged(mesh('Charge high voltage warning triangle',warning,[(0,1,2)],group,warning_yellow))
    tagged(tube('Charge high voltage lightning glyph',[point(.002,.066,-.028),point(-.003,.061,-.028),point(.002,.061,-.028),point(-.002,.055,-.028)],.0008,black,group))
    # The caps are swung aside, leaving both socket faces and terminals inspectable.
    for name,dx,radius in [('AC',ac,.036),('DC',dc,.049)]:
        cap_dx=dx+(.043 if name=='AC' else -.061);cap_dz=-.018
        cyl('Charge '+name+' independent circular dust cap',cap_dx,cap_dz,-.007,radius,.006,charge_plastic,72,True)
        hoop('Charge '+name+' dust cap molded lip',cap_dx,cap_dz,-.002,radius*.94,black,.0017,True)
        cyl('Charge '+name+' dust cap top hinge',cap_dx,cap_dz+radius,-.003,.005,.024,black,32,True)
        tagged(tube('Charge '+name+' dust cap hinge arm',[point(dx,-.004+radius,-.020),point(cap_dx,cap_dz+radius,-.003)],.0032,charge_plastic,group),True)
        tagged(box('Charge '+name+' dust cap rectangular pull',point(cap_dx,cap_dz-.016,.002),(.027,.012,.041),charge_plastic,group,.004),True)
        tagged(tube('Charge '+name+' cap flexible tether',[point(dx-.014,-.031,-.015),point(cap_dx-.010,-.065,.004),point(-.010,-.078,.011),point(.004,-.058,-.017)],.0017,rubber,group,smooth=True),True)
    # The detached double cover hangs outside the sill, with two visible wells.
    holder=point(-.006,-.118,.065)
    cyl('Charge external double cap backing',-.006,-.118,.065,.063,.008,black,80,True)
    for dx,radius in [(-.034,.030),(.025,.035)]:
        hoop('Charge external double cap socket rim',dx,-.118,.072,radius,charge_plastic,.003,True)
        cyl('Charge external double cap recessed well',dx,-.118,.071,radius*.83,.003,charge_plastic,64,True)
    tagged(tube('Charge external double cap tether',[point(.004,-.058,-.017),point(-.008,-.084,.028),tuple(Vector(holder)+Vector((0,0,.015)))],.0020,rubber,group,smooth=True),True)
    tagged(cyl('Charge housing drain',.087,-.063,-.030,.006,.004,black,28))
    return point

def glazing_panel(name,corners,group):
    side=1 if corners[0][1]>0 else -1
    corners[:]=[(x,side*cabin_width(x,z),z) for x,y,z in corners]
    boundary=rounded_outline(corners)
    center=sum(boundary,Vector())/len(boundary);side=1 if center.y>0 else -1
    center.y=side*cabin_width(center.x,center.z)
    vs=[tuple(center)];fs=[];n=len(boundary)
    for ring_index in range(1,13):
        r=ring_index/12
        for point in boundary:
            p=center*(1-r)+point*r;p.y=side*cabin_width(p.x,p.z)
            vs.append(tuple(p))
        for i in range(n):
            k=1+(ring_index-1)*n+i;next_k=1+(ring_index-1)*n+(i+1)%n
            if ring_index==1:face=(0,k,next_k)
            else:face=(k-n,k,next_k,next_k-n)
            fs.append(face if side>0 else tuple(reversed(face)))
    obj=mesh(name,vs,fs,group,glass)
    normals=[];h=.0001
    for x,y,z in vs:
        dx=(cabin_width(x+h,z)-cabin_width(x-h,z))/(2*h)
        dz=(cabin_width(x,z+h)-cabin_width(x,z-h))/(2*h)
        normals.append(tuple(Vector((-dx,side,-dz)).normalized()))
    obj.data.normals_split_custom_set_from_vertices(normals)
    return obj

def vw_emblem(group,center,radius,normal,right,face_material=badge_silver):
    center=Vector(center);normal=Vector(normal).normalized();right=Vector(right).normalized()
    up=normal.cross(right).normalized()
    def point(x,y,depth):return tuple(center+radius*(right*x+up*y+normal*depth))
    def lathe(name,profile,material):
        vs=[];fs=[];n=128
        for r,depth in profile:
            for i in range(n):
                angle=i/n*math.tau;vs.append(point(r*math.cos(angle),r*math.sin(angle),depth))
        for j in range(len(profile)-1):
            for i in range(n):
                a=j*n+i;b=j*n+(i+1)%n;fs.append((a,b,b+n,a+n))
        return mesh(name,vs,fs,group,material)
    lathe('VW stepped black mounting bezel',[(1.13,-.055),(1.16,-.015),(1.16,.025),(1.145,.055),(1.12,.080),(1.065,.104),(1.02,.108)],badge_black)
    lathe('VW outer polished hairline',[(1.108,.091),(1.105,.098),(1.098,.102),(1.092,.098)],badge_edge)
    lathe('VW gently crowned black face',[(1.10-i*1.10/20,.109+.018*(1-(1-i/20)**2)) for i in range(21)],badge_black)
    # Flat annular face with a small edge chamfer, rather than a round wire hoop.
    lathe('VW flat silver roundel',[(1.001,.111),(1.000,.125),(.991,.132),(VW_RING_INNER+.007,.132),(VW_RING_INNER,.125),(VW_RING_INNER,.111)],badge_silver)
    for name,outline in [('V',VW_V),('W',VW_W)]:
        n=len(outline)
        vs=[point(x,y,depth) for depth in [.112,.134] for x,y in outline]
        profile=[Vector((x,y,0)) for x,y in outline]
        caps=tessellate_polygon([profile])
        assert len(caps)==n-2
        fs=[tuple(reversed(f)) for f in caps]+[tuple(i+n for i in f) for f in caps]
        fs.extend((i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n))
        obj=mesh('VW solid '+name+' face',vs,fs,group,face_material)
        for face in obj.data.polygons:face.use_smooth=False
        bevel=obj.modifiers.new('Minute machined edge','BEVEL');bevel.width=radius*.004;bevel.segments=2;bevel.limit_method='ANGLE'
        obj.modifiers.new('Flat graphic normals','WEIGHTED_NORMAL')

def badge(group,x,z,rear=False):
    surface=rear_surface if rear else front_surface
    slope=(surface(0,z+.0001)[0]-surface(0,z-.0001)[0])/.0002
    normal=Vector((1 if rear else -1,0,-slope if rear else slope)).normalized()
    vw_emblem(group,Vector((x,0,z))+normal*.003,.064,normal,(0,1 if rear else -1,0),rear_led if rear else badge_silver)

def rear_point(y,z,offset=0):
    h=.0001;p=Vector(rear_surface(y,z))
    dy=(rear_surface(y+h,z)[0]-rear_surface(y-h,z)[0])/(2*h)
    dz=(rear_surface(y,z+h)[0]-rear_surface(y,z-h)[0])/(2*h)
    return tuple(p+Vector((1,-dy,-dz)).normalized()*offset)

def text_label(text,location,size,group,rear=False,material=white,font=None):
    bpy.ops.object.text_add(location=location)
    obj=bpy.context.object
    obj.name='Badge '+text
    obj.data.body=text
    if font:obj.data.font=font
    obj.data.size=size
    obj.data.align_x='CENTER'
    obj.data.align_y='CENTER'
    obj.data.extrude=.0005
    matrix=Matrix(((0,0,1),(1,0,0),(0,1,0))) if rear else Matrix(((0,0,-1),(-1,0,0),(0,1,0)))
    obj.rotation_euler=matrix.to_euler()
    bpy.ops.object.convert(target='MESH')
    return parent(obj,group,material)

# Lower structure and energy system are explanatory simulation geometry.
chassis=part('chassis','底盘框架','chassis',(0,0,.27),(0,0,-.35),.35)
box('Floor frame',(0,0,.27),(4.0,1.62,.12),black,chassis,.055)
for y in [-.75,.75]:box('Side rail',(0,y,.3),(3.85,.08,.12),alloy,chassis)
for x in [-1.418,1.418]:
    cylinder('Axle',(x,0,.37),.035,1.7,steel,chassis)
    for side in [-1,1]:
        tube('Wishbone',[(x-.18,side*.35,.29),(x,side*.81,.37),(x+.18,side*.35,.29)],.027,steel,chassis)
        arm=[(x-.23,side*.34,.272),(x+.22,side*.34,.272),(x+.055,side*.72,.315),(x-.040,side*.77,.326)]
        mesh('Suspension lower control arm plate',arm,[(0,1,2,3)],chassis,steel,.018,.006)
        tube('Suspension control arm pressed edge',arm,.009,black,chassis,True)
        for bx,by,bz in [(x-.18,side*.36,.270),(x+.17,side*.36,.270),(x,side*.735,.329)]:
            cylinder('Suspension pivot bushing',(bx,by,bz),.031,.042,black,chassis,'X',48)
            cylinder('Suspension pivot bolt',(bx-.024,by,bz),.013,.010,alloy,chassis,'X',6)
        box('Suspension upright carrier',(x,side*.785,.374),(.095,.060,.150),alloy,chassis,.018)
        tube('Suspension toe link',[(x+.24,side*.34,.335),(x+.12,side*.55,.35),(x+.04,side*.755,.39)],.012,steel,chassis)
        tube('Suspension upper link',[(x-.12,side*.38,.46),(x-.04,side*.57,.45),(x,side*.765,.43)],.013,black,chassis)
        for bx,by,bz in [(x+.24,side*.34,.335),(x+.04,side*.755,.39),(x-.12,side*.38,.46)]:
            cylinder('Suspension link rubber sleeve',(bx,by,bz),.018,.028,rubber,chassis,'X',32)
            cylinder('Suspension link hex fastener',(bx-.017,by,bz),.009,.008,alloy,chassis,'X',6)
    # Open subframe rails leave the drivetrain visible rather than forming a solid plate.
    for y in [-.48,.48]:
        tube('Subframe swept side rail',[(x-.34,y,.30),(x-.25,y*1.25,.285),(x+.25,y*1.25,.285),(x+.34,y,.30)],.026,black,chassis,smooth=True)
    for dx in [-.26,.26]:
        box('Subframe crossmember',(x+dx,0,.292),(.070,1.12,.052),black,chassis,.014)
        for y in [-.51,.51]:
            cylinder('Subframe mounting collar',(x+dx,y,.300),.026,.060,steel,chassis,'Z',40)
            cylinder('Subframe mounting bolt',(x+dx,y,.265),.012,.012,alloy,chassis,'Z',6)
# Flat aero shields and visible ribs approximate the official underside photographs.
for x,width in [(-1.72,.62),(0,2.32),(1.77,.70)]:
    box('Underbody flat aero shield',(x,0,.196),(width,1.48,.018),well_liner,chassis,.018)
    for y in [-.58,-.29,0,.29,.58]:
        box('Underbody longitudinal guide rib',(x,y,.183),(width*.88,.014,.018),black,chassis,.005)
    for dx in [-width*.38,width*.38]:
        for y in [-.64,.64]:cylinder('Underbody shield fastener',(x+dx,y,.181),.008,.005,steel,chassis,'Z',24)
pack=part('battery_case','动力电池包','power',(0,0,.24),(0,0,-1.0),.54)
box('Battery enclosure',(0,0,.24),(2.52,1.42,.12),steel,pack,.03)
for i in range(8):
    for j in range(3):
        x=-1.09+i*.31;y=(j-1)*.44
        p=part(f'battery_{i}_{j}',f'电池模组 {i*3+j+1}','power',(x,y,.34),((i-3.5)*.035,(j-1)*.08,-.84),.6)
        box('Cell module',(x,y,.34),(.278,.408,.085),cell,p,.012)
        box('Cell connector',(x+.08,y,.386),(.035,.055,.012),alloy,p,.003)
for x in [-1.4,1.4]:
    p=part('drive_front' if x<0 else 'drive_rear','前电驱示意' if x<0 else '后电驱示意','power',(x,0,.38),(-.4 if x<0 else .4,0,-.55),.63)
    cylinder('Electric motor',(x,0,.38),.15,.58,alloy,p)
    box('Inverter',(x+.08,0,.55),(.34,.4,.16),steel,p)

floor=part('cabin_floor','座舱地板','cabin',(0,0,.49),(0,0,.25),.3)
box('Cabin floor',(.25,0,.49),(2.9,1.62,.085),black,floor,.03)
for side in [-1,1]:
    label='左' if side>0 else '右'
    for seam_x in [-1.01,.186,1.232]:
        start=.73 if seam_x>1 else .33
        seal=[]
        for i in range(33):
            z=start+(belt_height(seam_x)-start)*i/32
            v=(z-.32)/(belt_height(seam_x)-.32)
            xx=seam_x+.024*math.sin(v*math.pi)*math.exp(-((seam_x-.18)/.22)**2)
            seal.append((xx,side*(side_width(seam_x,z)-.005),z))
        tube('Door aperture weather seal',seal,.0045,black,floor)
    sill=part(f'sill_{side}',label+'侧门槛','body',(0,side*.895,.31),(0,side*.5,.05),.06)
    tube('Lower rocker edge',[(x,side*(side_width(x,.34)+.012),.318) for x in [-1.03+2.26*i/48 for i in range(49)]],.014,black,sill)
    # Doors share their real front hinge with the moving window assembly.
    for index,(x0,x1) in enumerate([(-1.008,.184),(.188,1.230)]):
        hinge=(x0,side*.875,belt_height(x0))
        p=part(f'door_{side}_{index}',label+('前门' if index==0 else '后门'),'body',hinge,(0,side*1.05,.16),.03,'door',side)
        skin=side_skin('Sculpted door skin',x0,x1,side,p,arches=index==1)
        lining_end=min(x1,1.0)
        mid=(x0+lining_end)/2; width=lining_end-x0-.04
        # The inner panel follows the door opening, including the rear wheel-arch
        # sweep, instead of leaving a rectangular insert floating on the skin.
        outline=[(x0+.055,1.008),(x1-.080,1.008),(x1-.080,.76),
                 (x1-.18,.49),(x1-.27,.425),(x0+.13,.425),(x0+.055,.475)]
        verts=[(x,side*.805,z) for x,z in outline]
        mesh('Inner door lining',verts,[tuple(range(len(verts))) if side<0 else tuple(reversed(range(len(verts))))],p,door_leather,.018,.008)
        box('Door upper black rail',((x0+x1)/2,side*.792,1.004),(x1-x0-.14,.026,.072),black,p,.012)
        box('Door padded armrest',(mid+.03,side*.775,.754),(width*.76,.085,.095),door_leather,p,.022)
        box('Door armrest underside',(mid+.03,side*.786,.689),(width*.69,.055,.042),door_seam,p,.012)
        box('Door lower storage recess',(mid+.03,side*.790,.548),(width*.46,.015,.105),door_seam,p,.020)
        box('Door interior release bezel',(lining_end-.20,side*.781,.884),(.18,.014,.063),alloy,p,.012)
        box('Door interior release inset',(lining_end-.20,side*.771,.884),(.14,.009,.035),black,p,.008)
        box('Door window switch panel',(mid+.17,side*.730,.803),(.15,.035,.012),seat_dark,p,.005)
        tube('Door upper stitched seam',[(x0+.04+(width-.05)*i/24,side*.792,.935) for i in range(25)],.0012,door_seam,p)
        handle_x=x1-.21
        recessed_door_handle(skin,p,handle_x,side)
        cladding_vs=[];cladding_fs=[]
        for j in range(7):
            for i in range(49):
                x=x0+(min(x1,1.01)-x0)*i/48
                height=.008+.128*smoothstep(-1.01,-.62,x)*(1-smoothstep(.91,1.22,x))
                z=.322+height*j/6
                xx=x+.024*math.sin((z-.32)/(belt_height(x)-.32)*math.pi)*math.exp(-((x-.18)/.22)**2)
                cladding_vs.append((xx,side*(side_width(x,z)+.008),z))
        for j in range(6):
            for i in range(48):
                k=j*49+i;face=(k,k+1,k+50,k+49)
                cladding_fs.append(face if side<0 else tuple(reversed(face)))
        mesh('Shaped door lower cladding',cladding_vs,cladding_fs,p,black,.004)
        if index==0:
            points=[(x0+.018,side*.872,belt_height(x0)+.012),(-.32,side*.740,1.60),(.17,side*.755,1.615),(.17,side*.868,belt_height(.17)+.012)]
        else:
            points=[(.215,side*.868,belt_height(.215)+.012),(.215,side*.755,1.615),(1.17,side*.770,1.588),(1.22,side*.870,belt_height(1.22)+.012)]
        w=part(f'window_{side}_{index}',label+('前窗' if index==0 else '后窗'),'cabin',hinge,(0,side*1.3,1.0),.19,'window',side)
        glazing_panel('Moving side glass',points,w)
        tube('Window lower seal',[points[0],points[3]],.007,black,p)
        belt_vs=[];belt_fs=[]
        for i in range(65):
            t=i/64;x=points[0][0]*(1-t)+points[3][0]*t
            low=belt_height(x)-.001;high=points[0][2]*(1-t)+points[3][2]*t
            belt_vs.extend([(x,side*(side_width(x,low)+.001),low),(x,side*cabin_width(x,high),high)])
        for i in range(64):
            k=i*2;face=(k,k+2,k+3,k+1);belt_fs.append(face if side<0 else tuple(reversed(face)))
        mesh('Continuous door belt seal',belt_vs,belt_fs,p,black,.003)
    for front in [True,False]:
        x0,x1=(-2.15,-1.012) if front else (1.234,2.30)
        p=part(f'fender_{side}_{front}',label+('前翼子板' if front else '后翼子板'),'body',offset=(-.3 if front else .3,side*.65,.12),start=.08)
        skin=side_skin('Curved wheel fender',x0,x1,side,p,True)
        if not front and side>0:
            charge_point=recessed_charge_port(skin,p,side)
            hinge=charge_point(-.121,0,.004)
            flap=part('charge_flap',label+'后充电口盖','body',hinge,(0,side*.65,.12),.08,'charge_flap',side)
            cover_outline=handle_outline(.240,.174,.027)
            vs=[charge_point(0,0,.005)]+[charge_point(dx,dz,.005) for dx,dz in cover_outline]
            fs=[(0,i+1,(i+1)%len(cover_outline)+1) for i in range(len(cover_outline))]
            cover=mesh('Charge flap painted outer panel',vs,fs,flap,paint,.006);cover['detail']='charge'
            joint=tube('Charge flap perimeter seal',[charge_point(dx,dz,.001) for dx,dz in cover_outline],.0022,rubber,flap,True);joint['detail']='charge'
            cylinder('Charge flap vertical hinge',hinge,.0045,.132,black,flap,'Z',40)
        wx=-1.418 if front else 1.418
        arch_vs=[];arch_fs=[];n=72
        for radius in [.402,.445]:
            for i in range(n+1):
                a=math.pi*i/n;x=wx+radius*math.cos(a);z=.37+radius*math.sin(a)
                arch_vs.append((x,side*(side_width(x,z)+.006),z))
        for i in range(n):
            face=(i,i+1,i+n+2,i+n+1)
            arch_fs.append(face if side>0 else tuple(reversed(face)))
        mesh('Flush wheel arch cladding',arch_vs,arch_fs,p,black,.005)
        well_vs=[];well_fs=[];n=96
        for inner in [False,True]:
            for i in range(n+1):
                a=math.pi*i/n;x=wx+.403*math.cos(a);z=.37+.403*math.sin(a)
                y=.715 if inner else side_width(x,z)-.004
                well_vs.append((x,side*y,z))
        for i in range(n):well_fs.append((i,i+1,i+n+2,i+n+1))
        mesh('Wheel well tunnel',well_vs,well_fs,p,well_liner)
        # Only the upper crescent closes the tire-to-arch gap; the axle and lower cavity stay open.
        inner_vs=[];inner_fs=[]
        for radius,y in [(.300,.670),(.360,.690),(.403,.715)]:
            for i in range(n+1):
                a=math.pi*i/n
                inner_vs.append((wx+radius*math.cos(a),side*y,.37+radius*math.sin(a)))
        for j in range(2):
            for i in range(n):
                k=j*(n+1)+i;face=(k,k+1,k+n+2,k+n+1)
                inner_fs.append(face if side>0 else tuple(reversed(face)))
        mesh('Wheel well curved upper inner return',inner_vs,inner_fs,p,well_liner)
        for direction in [-1,1]:
            points=[(wx+direction*r,side*(side_width(wx+direction*r,z)+.006),z) for r,z in [(.402,.32),(.402,.37),(.445,.37),(.445,.32)]]
            mesh('Arch lower return',points,[(0,1,2,3)],p,black,.004)
    # A/B/C pillars and fixed rear quarter glass.
    rail=part(f'roof_frame_{side}',label+'侧顶梁','body',offset=(0,side*.35,1.5),start=.22)
    pillar_vs=[];pillar_fs=[]
    for i in range(49):
        t=i/48;x=-1.01+.69*t-.015*math.sin(t*math.pi)
        z=1.112+.488*t;y=cabin_width(x,z)
        for j in range(5):
            v=j/4;s=smoothstep(.65,1,t)
            pillar_vs.append((x-.053*v*(1-s),side*(y+(.015*(1-s)+.044*s)*v),z+(.025*(1-s)-.022*s)*v))
    for i in range(48):
        for j in range(4):
            k=i*5+j;face=(k,k+5,k+6,k+1)
            pillar_fs.append(face if side<0 else tuple(reversed(face)))
    mesh('Swept A pillar panel',pillar_vs,pillar_fs,rail,paint,.008)
    rail_vs=[];rail_fs=[]
    for i in range(81):
        x=-.32+2.02*i/80
        for j in range(7):
            v=j/6;rail_vs.append((x,side*(roof_w(x)+.044*v),roof_z(x)-.022*v+.004*math.sin(v*math.pi)))
    for i in range(80):
        for j in range(6):
            k=i*7+j;face=(k,k+7,k+8,k+1)
            rail_fs.append(face if side>0 else tuple(reversed(face)))
    mesh('Continuous roof shoulder',rail_vs,rail_fs,rail,paint,.008)
    q=part(f'quarter_glass_{side}',label+'后侧固定玻璃','cabin',offset=(.35,side*1.15,1.0),start=.24)
    qpts=[(1.25,side*.870,1.132),(1.22,side*.770,1.587),(1.47,side*.780,1.545),(1.61,side*.864,1.15)]
    glazing_panel('Quarter glass',qpts,q)
    tube('Quarter window seal',rounded_outline(qpts),.006,black,q,True)
    pillar=part(f'pillar_b_{side}',label+'侧 B 柱','cabin',offset=(0,side*.8,1.1),start=.24)
    mesh('B pillar face',[(.173,side*.869,1.105),(.173,side*.756,1.626),(.212,side*.756,1.626),(.212,side*.869,1.105)],[(0,1,2,3)],pillar,black,.008)
    pillar_c=part(f'pillar_c_{side}',label+'后侧围','body',offset=(.4,side*.65,.6),start=.18)
    division=[(x,side*cabin_width(x,z),z) for x,z in [(1.17,1.588),(1.22,1.132),(1.25,1.132),(1.22,1.587)]]
    mesh('Rear window division trim',division,[(0,1,2,3)],pillar_c,black,.006)
    # Explicit strips avoid the open triangles of a single concave, nonplanar ngon.
    shoulder_vs=[];shoulder_fs=[]
    for i in range(49):
        t=i/48;x=1.235+1.065*t
        lower=Vector(side_surface(x,belt_height(x),'rear'));lower.y*=side
        if x<=1.61:
            u=(x-1.235)/.375
            upper=Vector((x,side*(.869-.005*u),1.132+.018*u))
        else:
            u=(x-1.61)/.69
            end=Vector(rear_window_point(1,side));end.x+=.008;end.y+=side*.020
            upper=Vector((1.61,side*.864,1.15)).lerp(end,u)
        for j in range(5):
            shoulder_vs.append(tuple(lower.lerp(upper,j/4)))
    for i in range(48):
        for j in range(4):
            k=i*5+j;face=(k,k+5,k+6,k+1)
            shoulder_fs.append(face if side<0 else tuple(reversed(face)))
    mesh('Continuous quarter lower shoulder',shoulder_vs,shoulder_fs,pillar_c,paint,.006)
    d_vs=[];d_fs=[];n=16
    lower_left=Vector(qpts[3]);upper_left=Vector(qpts[2])
    for j in range(n+1):
        v=j/n
        right=Vector(rear_window_point(1-v,side));right.x+=.008;right.y+=side*(.020*v+.012*(1-v)+.003)
        left=lower_left.lerp(upper_left,v)
        for i in range(n+1):
            u=i/n
            p=left.lerp(right,u)
            p.y+=side*.018*math.sin(u*math.pi)*math.sin(v*math.pi)
            d_vs.append(tuple(p))
    for j in range(n):
        for i in range(n):
            k=j*(n+1)+i
            d_fs.append((k,k+1,k+n+2,k+n+1) if side<0 else (k,k+n+1,k+n+2,k+1))
    mesh('Swept rear D pillar',d_vs,d_fs,pillar_c,paint,.008)
    mirror=part(f'mirror_{side}',label+'后视镜','body',(-.87,side*.99,1.12),(-.15,side*1.3,.25),.1)
    # The cover faces diagonally forward/outboard; the glass faces rearward/inboard.
    mirror_origin=Vector((-.875,side*1.092,1.155))
    mirror_u=Vector((.82,side*.57236,0)).normalized()
    mirror_n=Vector((-.57236,side*.82,0)).normalized()
    def mirror_point(u,z,depth):return tuple(mirror_origin+mirror_u*u+Vector((0,0,z))+mirror_n*depth)
    def mirror_outline(start,segments):
        points=[];p0=Vector(start)
        for c1,c2,end in segments:
            c1,c2,end=Vector(c1),Vector(c2),Vector(end)
            for i in range(24):
                t=i/24;points.append(p0*(1-t)**3+c1*(3*(1-t)**2*t)+c2*(3*(1-t)*t*t)+end*t**3)
            p0=end
        return points
    def mirror_edge_depth(u):return .0025*max(0,1-(u/.148)**2)
    def mirror_seam(u):return -.006*(1-((u-.0015)/.1455)**2)
    def mirror_rear_z(z):return z*(.65 if z>0 else .90)
    upper=mirror_outline((-.144,0),[
        ((-.047,-.008),(.050,-.008),(.147,0)),
        ((.139,.020),(.077,.086),(.012,.087)),
        ((-.040,.088),(-.123,.038),(-.144,.006)),
        ((-.146,.004),(-.146,.002),(-.144,0)),
    ])
    lower=mirror_outline((-.144,-.006),[
        ((-.145,-.025),(-.133,-.051),(-.105,-.056)),
        ((-.055,-.064),(.077,-.064),(.100,-.052)),
        ((.132,-.039),(.147,-.019),(.147,-.006)),
        ((.050,-.014),(-.047,-.014),(-.144,-.006)),
    ])
    def mirror_shell_surface(name,boundary,center,material,crown):
        center=Vector(center);count=len(boundary);vs=[mirror_point(center.x,center.y,mirror_edge_depth(center.x)+crown)];fs=[];rows=24
        for row in range(1,rows+1):
            r=row/rows
            for p0 in boundary:
                q=center.lerp(p0,r)
                vs.append(mirror_point(q.x,q.y,mirror_edge_depth(q.x)+crown*math.sqrt(max(0,1-r*r))))
            for i in range(count):
                k=1+(row-1)*count+i;q=1+(row-1)*count+(i+1)%count
                face=(0,k,q) if row==1 else (k-count,k,q,q-count)
                fs.append(face if side<0 else tuple(reversed(face)))
        # Share the edge vertices so the cap rolls into the shoulder without an inset seam.
        previous=1+(rows-1)*count
        for row in range(1,25):
            t=row/24;scale=1-.08*t;start=len(vs)
            for q in boundary:vs.append(mirror_point(q.x*scale,q.y*(1-t)+mirror_rear_z(q.y)*t,mirror_edge_depth(q.x)*(1-t)-.092*t))
            for i in range(count):
                j=(i+1)%count;face=(previous+i,start+i,start+j,previous+j)
                fs.append(face if side<0 else tuple(reversed(face)))
            previous=start
        mesh(name,vs,fs,mirror,material)
    mirror_shell_surface('Mirror upper wedge cap',upper,(-.006,.029),mirror_shell,.018)
    mirror_shell_surface('Mirror lower sculpted housing',lower,(-.004,-.030),mirror_lower,.012)
    # Curved support neck grows from the door gasket into the lower housing.
    foot_rows=[(.899,-.812,1.079,.043,.020),(.917,-.816,1.081,.044,.019),(.955,-.832,1.086,.041,.016),(.999,-.855,1.097,.035,.014),(1.038,-.880,1.111,.032,.014)]
    foot_sections=[section([(r[0],r[j]) for r in foot_rows]) for j in range(1,5)]
    vs=[];fs=[];nc=48;nx=48
    for row in range(nx+1):
        y=.899+.139*row/nx;cx,cz,rx,rz=[fn(y) for fn in foot_sections]
        for i in range(nc):
            a=i/nc*math.tau;c,sn=math.cos(a),math.sin(a)
            vs.append((cx+rx*math.copysign(abs(c)**.70,c),side*y,cz+rz*math.copysign(abs(sn)**.75,sn)))
    for row in range(nx):
        for i in range(nc):
            k=row*nc+i;q=row*nc+(i+1)%nc;face=(k,q,q+nc,k+nc)
            fs.append(face if side<0 else tuple(reversed(face)))
    face=tuple(range(nc));fs.append(face if side>0 else tuple(reversed(face)))
    mesh('Mirror continuous curved mounting neck',vs,fs,mirror,mirror_lower)
    gasket=[(x,side*.898,z) for x,y,z in vs[:nc]]
    tube('Mirror door mounting gasket',gasket,.0016,mirror_lower,mirror,True)
    perimeter=mirror_outline((-.144,0),[
        ((-.145,-.025),(-.133,-.051),(-.105,-.056)),
        ((-.055,-.064),(.077,-.064),(.100,-.052)),
        ((.132,-.039),(.147,-.019),(.147,0)),
        ((.139,.020),(.077,.086),(.012,.087)),
        ((-.040,.088),(-.123,.038),(-.144,.006)),
        ((-.146,.004),(-.146,.002),(-.144,0)),
    ])
    center=Vector((0,.010));outline=[]
    for q in perimeter:
        q=center.lerp(Vector((q.x*.92,mirror_rear_z(q.y))),.944)
        outline.append(mirror_point(q.x,q.y,-.094))
    vs=[mirror_point(0,.010,-.095)]+outline;count=len(outline)
    fs=[(0,i+1,(i+1)%count+1) for i in range(count)]
    mesh('Mirror reflective glass',vs,[tuple(reversed(f)) for f in fs] if side<0 else fs,mirror,mirror_glass)
    tube('Mirror glass perimeter gasket',outline,.0023,mirror_lower,mirror,True)
    tube('Mirror rear opening rolled edge',[mirror_point(q.x*.92,mirror_rear_z(q.y),-.093) for q in perimeter],.0022,mirror_shell,mirror,True)
    def mirror_light_band(name,material,half_height,depth,u0,u1):
        vs=[];fs=[];n=112
        for i in range(n+1):
            u=u0+(u1-u0)*i/n;h=half_height*(.35+.65*math.sin(math.pi*i/n)**.35)
            for dz in [-h,h]:vs.append(mirror_point(u,mirror_seam(u)-.0036+dz,mirror_edge_depth(u)+depth))
            if i:
                k=2*i;face=(k-2,k,k+1,k-1);fs.append(face if side<0 else tuple(reversed(face)))
        mesh(name,vs,fs,mirror,material,.0007)
    mirror_light_band('Mirror indicator recessed black channel',mirror_lower,.0041,.0005,-.142,.145)
    mirror_light_band('Mirror indicator continuous smoked lens',indicator_lens,.0027,.0014,-.139,.141)
    for i in range(140):
        u=-.137+.276*i/139;h=.0023*(.35+.65*math.sin(math.pi*i/139)**.35)
        tube('Mirror indicator prism rib',[mirror_point(u,mirror_seam(u)-.0036+dz,mirror_edge_depth(u)+.0022) for dz in [-h,h]],.00027,mirror_ribs,mirror)
    merge_static_details(mirror,'Mirror indicator prism rib',mirror_ribs)
    tube('Mirror lower housing mould joint',[mirror_point(u,mirror_seam(u)-.015,mirror_edge_depth(u)+.004) for u in [-.138+.277*i/96 for i in range(97)]],.0005,mirror_lower,mirror)
    camera_normal=(mirror_n*.35-Vector((0,0,.94))).normalized()
    camera_center=Vector(mirror_point(-.065,-.052,.011))
    for name,r,depth,offset,material in [('Mirror underside camera socket',.0105,.004,0,mirror_lower),('Mirror underside camera lens',.0068,.0015,.0023,sensor_optic)]:
        obj=cylinder(name,tuple(camera_center+camera_normal*offset),r,depth,material,mirror,'Z',48)
        obj.rotation_euler=camera_normal.to_track_quat('Z','Y').to_euler()
    camera_up=camera_normal.cross(mirror_u).normalized()
    tube('Mirror underside camera bezel',[tuple(camera_center+camera_normal*.002+(.0088*(mirror_u*math.cos(i/72*math.tau)+camera_up*math.sin(i/72*math.tau)))) for i in range(72)],.0007,mirror_shell,mirror,True)
    vent=part(f'side_vent_{side}',label+'前侧饰条','body',(-1.06,side*.944,1.01),(-.2,side*.55,.12),.1)
    contour=rounded_outline([(-1.23,0,1.055),(-.952,0,1.037),(-.973,0,.982),(-1.173,0,1.004)],.008)
    def fender_point(x,z,depth):return (x,side*(side_width(x,z)+depth),z)
    center=Vector((-1.087,0,1.023));n=len(contour)
    vs=[fender_point(center.x,center.z,.021)]
    for q in contour:vs.append(fender_point(q.x,q.z,.004))
    fs=[(0,i+1,(i+1)%n+1) for i in range(n)]
    mesh('Fender sculpted sensor wing',vs,fs if side<0 else [tuple(reversed(f)) for f in fs],vent,sensor_black,.004)
    tube('Fender raised upper lip',[fender_point(x,z,.009) for x,z in [(-1.222,1.050),(-1.16,1.041),(-1.09,1.035),(-1.018,1.034),(-.958,1.035)]],.0023,mirror_cap,vent,smooth=True)
    inset=[(-1.057,1.022),(-.972,1.031),(-.984,.993),(-1.050,1.006)]
    mesh('Fender recessed triangular optic insert',[fender_point(x,z,.022) for x,z in inset],[(0,1,2,3)],vent,mirror_cap,.002)
    for pts in [[(-1.037,1.017),(-1.007,1.021),(-.980,1.026)],[(-1.037,1.008),(-1.010,1.001),(-.985,.997)]]:
        tube('Fender optic sculpted fin',[fender_point(x,z,.025) for x,z in pts],.0013,black,vent,smooth=True)
    cx=-1.039;cz=1.014;cy=side*(side_width(cx,cz)+.026)
    cylinder('Fender camera socket',(cx,cy,cz),.0107,.003,sensor_black,vent,vertices=40)
    cylinder('Fender camera lens',(cx,cy+side*.002,cz),.0072,.002,sensor_optic,vent,vertices=40)
    ring('Fender camera retaining ring',(cx,cy+side*.002,cz),.009,black,vent,wire=.0008)
    tube('Fender forward recessed channel',[fender_point(x,z,.012) for x,z in [(-1.211,1.041),(-1.184,1.031),(-1.17,1.020)]],.0032,black,vent,smooth=True)
    vent.location.x-=.070
    # Wheels are true tire profiles, separately exploded from rims and brakes.
    for x in [-1.418,1.418]:
        position=(x,side*.817,.37)
        p=part(f'tire_{side}_{x}',label+('前轮胎' if x<0 else '后轮胎'),'chassis',position,(0,side*1.65,0),.36)
        profile=[(-.113,.270),(-.126,.287),(-.122,.313),(-.110,.342),(-.086,.362),(-.05,.372),(.05,.372),(.086,.362),(.110,.342),(.122,.313),(.126,.287),(.113,.270)]
        control=[Vector(p) for p in profile];profile=[]
        for i in range(len(control)-1):
            a,b,c,d=[control[k] for k in [max(0,i-1),i,i+1,min(len(control)-1,i+2)]]
            for j in range(6):
                t=j/6;q=.5*(2*b+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t)
                profile.append((q.x,min(.372,q.y)))
        profile.append(tuple(control[-1]))
        vs=[];fs=[];n=192
        for dy,r in profile:
            for k in range(n):
                a=k/n*math.tau;vs.append((x+r*math.cos(a),side*.817+dy,.37+r*math.sin(a)))
        for j in range(len(profile)-1):
            for k in range(n):
                a=j*n+k;b=j*n+(k+1)%n;fs.append((a,b,b+n,a+n))
        mesh('Touring tire',vs,fs,p,rubber)
        for dy in [-.065,-.025,.025,.065]:ring('Tread channel',(x,side*.817+dy,.37),.371,well_liner,p,wire=.0022)
        def side_depth(r):
            hits=[]
            for (ay,ar),(by,br) in zip(profile,profile[1:]):
                if min(ar,br)<=r<=max(ar,br) and abs(br-ar)>1e-8:
                    hits.append(ay+(by-ay)*(r-ar)/(br-ar))
            return max(hits) if hits else .075
        for r in [.289,.295,.350,.354]:ring('Sidewall fine moulding',(x,side*(.817+side_depth(r)+.0005),.37),r,rubber,p,wire=.0005)
        for k in range(120):
            a=k/120*math.tau
            pts=[]
            for dy in [-.092,-.065,-.025,.025,.065,.092]:
                aa=a+.030*(1-abs(dy)/.092)
                r=.372-.011*(abs(dy)/.092)**5
                pts.append((x+r*math.cos(aa),side*.817+dy,.37+r*math.sin(aa)))
            tube('Fine tread sipe',pts,.0009,well_liner,p)
        # Official wheel photographs confirm Hankook iON evo SUV and 255/45 R20 101V mouldings.
        for content,angle0,r,size,spacing in [('Hankook',.18,.331,.021,.043),('iON evo SUV',-1.45,.330,.012,.025),('OUTSIDE',2.0,.309,.008,.024),('255/45 R20 101V',-2.63,.315,.009,.020)]:
            for i,char in enumerate(content):
                a=angle0+(i-(len(content)-1)/2)*spacing
                normal=Vector((0,side,0));right=Vector((-side*math.cos(a),0,-math.sin(a)));up=normal.cross(right)
                bpy.ops.object.text_add(location=(x-side*r*math.sin(a),side*(.817+side_depth(r)+.0007),.37+r*math.cos(a)))
                lettering=bpy.context.object;lettering.name='Moulded tire '+content+' glyph'
                lettering.data.body=char;lettering.data.size=size;lettering.data.align_x='CENTER';lettering.data.align_y='CENTER';lettering.data.extrude=.00045
                lettering.rotation_euler=Matrix((right,up,normal)).transposed().to_euler()
                bpy.ops.object.convert(target='MESH')
                matrix=lettering.matrix_world.copy();inverse=matrix.inverted()
                for vertex in lettering.data.vertices:
                    q=matrix@vertex.co;r0=math.hypot(q.x-x,q.z-.37)
                    q.y=side*(.817+side_depth(r0)+.0008+vertex.co.z)
                    vertex.co=inverse@q
                parent(lettering,p,tire_letter)
            merge_static_details(p,'Moulded tire '+content,tire_letter)
        for k in range(80):
            a=k/80*math.tau
            r=.353;dy=side_depth(r)
            q=Vector((x+r*math.cos(a),side*(.817+dy),.37+r*math.sin(a)))
            tube('Tire shoulder mould nib',[tuple(q),tuple(q+Vector((.0008*math.cos(a),side*.0012,.0008*math.sin(a))))],.00028,rubber,p)
        for k in range(72):
            a=math.pi*.55+k/72*math.pi*.35
            tube('Sidewall fine hatching',[(x+r*math.cos(a),side*(.817+side_depth(r)+.0005),.37+r*math.sin(a)) for r in [.309,.322]],.00024,rubber,p)
        merge_static_details(p,'Fine tread sipe',well_liner)
        merge_static_details(p,'Tire shoulder mould nib',rubber)
        merge_static_details(p,'Sidewall fine hatching',rubber)
        rim_y=side*.932
        rim=part(f'rim_{side}_{x}',label+('前轮毂' if x<0 else '后轮毂'),'chassis',(x,rim_y,.37),(0,side*1.2,0),.43)
        wheel_lathe('Open alloy wheel barrel',x,side,[(-.09,.228),(.106,.228),(.13,.239),(.14,.250),(.137,.258),(.119,.260),(-.09,.260),(-.09,.228)],rim,black)
        wheel_lathe('Machined rim flange',x,side,[(.138,.244),(.140,.250),(.137,.256)],rim,alloy)
        ring('Polished outer lip',(x,side*.955,.37),.250,alloy,rim,wire=.003)
        ring('Recessed barrel edge',(x,side*.895,.37),.224,black,rim,wire=.004)
        for k in range(5):
            angle=k/5*math.tau+math.pi/2
            pts=[]
            outline=[(.055,-.39),(.135,-.40),(.221,-.48),(.250,-.45),(.250,-.22),(.147,-.23),(.118,-.14),(.118,.14),(.147,.23),(.250,.22),(.250,.45),(.221,.48),(.135,.40),(.055,.39)]
            for r,delta in outline:
                a=angle+delta
                depth=.091+.042*(r/.25)**2
                pts.append((x+r*math.cos(a),side*(.817+depth),.37+r*math.sin(a)))
            face=tuple(range(len(pts)))
            mesh('Sculpted split aero spoke',pts,[face if side<0 else tuple(reversed(face))],rim,mirror_cap,.024,.003)
            # Silver follows the outer U only; the spoke root stays gloss black.
            border=[];edge=[Vector((q[0]-x,q[2]-.37)) for q in pts[2:12]]
            for offset in [-.011,.011]:
                for i,q0 in enumerate(edge):
                    tangent=(edge[min(i+1,len(edge)-1)]-edge[max(0,i-1)]).normalized()
                    q=q0+offset*Vector((-tangent.y,tangent.x));r=q.length
                    border.append((x+q.x,side*(.817+.091+.042*(r/.25)**2+.003),.37+q.y))
            count=len(edge)
            faces=[(i,i+1,i+1+count,i+count) for i in range(count-1)]
            mesh('Diamond cut concave spoke face',border,faces if side<0 else [tuple(reversed(f)) for f in faces],rim,alloy,.001)
            a=angle+math.pi/5
            # Triangular ribbed aero pockets fill the rim valleys without closing the five windows.
            outline=[(.184,0),(.242,-.165),(.246,0),(.242,.165)]
            insert=[(x+r*math.cos(a+da),side*.947,.37+r*math.sin(a+da)) for r,da in outline]
            mesh('Recessed triangular aero insert',insert,[(0,1,2,3)] if side<0 else [(3,2,1,0)],rim,mirror_cap,.006,.001)
            for rib in range(17):
                da=-.133+rib*.266/16
                inner=.189+.040*abs(da)/.15
                tube('Aero insert rib',[(x+r*math.cos(a+da),side*.951,.37+r*math.sin(a+da)) for r in [inner,.232,.240]],.00085,black,rim)
            tube('Aero insert machined outer arc',[(x+.247*math.cos(a+da),side*.955,.37+.247*math.sin(a+da)) for da in [-.14+.28*i/20 for i in range(21)]],.0018,alloy,rim)
        cylinder('Hub',(x,side*.915,.37),.049,.025,black,rim)
        vw_emblem(rim,(x,side*.929,.37),.0275,(0,side,0),(-side,0,0))
        for bolt in range(5):
            a=bolt/5*math.tau;bx=x+.063*math.cos(a);bz=.37+.063*math.sin(a)
            cylinder('Wheel fastener recess',(bx,side*.918,bz),.013,.009,black,rim,vertices=40)
            ring('Wheel fastener deep well rim',(bx,side*.924,bz),.0115,black,rim,wire=.0014)
            ring('Wheel fastener machined inner edge',(bx,side*.925,bz),.0078,alloy,rim,wire=.0007)
            cylinder('Wheel fastener',(bx,side*.922,bz),.0065,.007,alloy,rim,vertices=12)
            cylinder('Wheel fastener hex socket',(bx,side*.926,bz),.0032,.001,black,rim,vertices=6)
        merge_static_details(rim,'Aero insert rib',black)
        valve_angle=math.pi/2+math.pi/5;vx=x+.230*math.cos(valve_angle);vz=.37+.230*math.sin(valve_angle)
        box('Tire valve rectangular recessed pocket',(vx,side*.946,vz),(.028,.006,.052),black,rim,.006)
        box('Tire valve pocket inner floor',(vx,side*.950,vz),(.018,.003,.037),well_liner,rim,.004)
        cylinder('Tire valve rubber stem',(vx,side*.954,vz),.0036,.012,rubber,rim,vertices=20)
        cylinder('Tire valve dust cap',(vx,side*.961,vz),.0045,.006,black,rim,vertices=20)
        bpy.context.view_layer.update()
        for child in rim.children_recursive:
            if child.type!='MESH':continue
            matrix=child.matrix_world.copy();inverse=matrix.inverted()
            for vertex in child.data.vertices:
                q=matrix@vertex.co;q.x=x+(q.x-x)*1.12;q.z=.37+(q.z-.37)*1.12
                vertex.co=inverse@q
            child.data.update()
        brake=part(f'brake_{side}_{x}',label+('前制动盘' if x<0 else '后制动盘'),'chassis',(x,side*.87,.37),(0,side*.75,0),.48)
        cylinder('Brake disc',(x,side*.87,.37),.195,.025,steel,brake)
        ring('Rotor edge',(x,side*.884,.37),.192,alloy,brake,wire=.0015)
        for r in [.145,.166,.184]:ring('Rotor swept machining',(x,side*.885,.37),r,alloy,brake,wire=.0003)
        box('Brake caliper',(x+.15,side*.88,.37),(.065,.06,.16),caliper_red,brake,.018)
        # Half-shaft connects wheel hub to differential at vehicle centerline.
        shaft_len=abs(side*.81)
        shaft_y=side*.435
        shaft=part(f'shaft_{side}_{x}',label+('前半轴' if x<0 else '后半轴'),'chassis',(x,shaft_y,.37),(0,side*.75,0),.50)
        cylinder('Half-shaft shaft',(x,shaft_y,.37),.038,shaft_len,steel,shaft)
        ring('CV joint outer boot',(x,side*.78,.37),.052,rubber,shaft,wire=.004)
        ring('CV joint inner boot',(x,side*.09,.37),.052,rubber,shaft,wire=.004)
        cylinder('CV joint outer housing',(x,side*.80,.37),.048,.06,steel,shaft)
        cylinder('CV joint inner housing',(x,side*.11,.37),.048,.06,steel,shaft)

# Differentials at front and rear axle centerlines.
diff_housing=mat('Differential housing cast iron',(.075,.085,.095),.6,.38)
for diff_x in [-1.418,1.418]:
    diff=part(f'diff_{diff_x}','前差速器' if diff_x<0 else '后差速器','chassis',(diff_x,0,.37),(0,0,-.30),.52)
    box('Differential carrier housing',(diff_x,0,.37),(.22,.34,.22),diff_housing,diff,.02)
    cylinder('Differential input flange',(diff_x,0,.50),.065,.04,alloy,diff)
    for s in [-1,1]:
        cylinder('Differential side cover',(diff_x,s*.14,.37),.075,.04,steel,diff)

# The bonnet is a separate hinged panel, inset behind the fixed nose bridge.
front=part('front_bumper','前保险杠','body',offset=(-1.18,0,.08),start=.06)
hood=part('hood','前舱盖','body',HOOD_HINGE,(-.85,0,.95),.05,'hood')
inner_paint=mat('Paint inner stamping',(.055,.22,.18),.45,.42)
felt=mat('Bonnet insulation felt',(.008,.012,.013),0,.97)
service_plastic=mat('Front service cover satin polymer',(.004,.006,.008),0,.54)
service_tray=mat('Front service tray grained polymer',(.004,.006,.008),0,.72)
for material,strength in [(service_plastic,.16),(service_tray,.27)]:
    bsdf=material.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Specular IOR Level'].default_value=.15
    noise=material.node_tree.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=1800
    noise.inputs['Detail'].default_value=2
    bump=material.node_tree.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=strength;bump.inputs['Distance'].default_value=.00024
    material.node_tree.links.new(noise.outputs['Fac'],bump.inputs['Height'])
    material.node_tree.links.new(bump.outputs['Normal'],bsdf.inputs['Normal'])
washer_blue=mat('Washer fluid blue cap',(.012,.16,.68),0,.34)

def param_panel(name,fn,group,material,nx=48,ny=64,underside=False,thickness=0,normal=None):
    vs=[];fs=[];normals=[]
    for i in range(nx+1):
        for j in range(ny+1):
            s=i/nx;u=math.sin((j/ny-.5)*math.pi)
            vs.append(fn(s,u))
            if normal:normals.append(normal(s,u))
    for i in range(nx):
        for j in range(ny):
            k=i*(ny+1)+j;face=(k,k+ny+1,k+ny+2,k+1)
            fs.append(tuple(reversed(face)) if underside else face)
    obj=mesh(name,vs,fs,group,material,thickness)
    if normal:obj.data.normals_split_custom_set_from_vertices(normals)
    return obj

def polymer_uv(obj):
    uv=obj.data.uv_layers.new(name='Polymer grain 80 mm tile')
    for face in obj.data.polygons:
        for loop in face.loop_indices:
            p=obj.data.vertices[obj.data.loops[loop].vertex_index].co
            uv.data[loop].uv=(p.x*12.5,p.y*12.5)
    return obj

param_panel('Separate crowned bonnet outer skin',bonnet_point,hood,paint,64,64,thickness=.004,normal=bonnet_normal)
param_panel('Fixed upper nose bridge',lambda s,u:front_deck_point((bonnet_front(u)-.003)*s,HOOD_HALF_SPAN*u),front,paint,32,96,thickness=.007,normal=lambda s,u:front_deck_normal((bonnet_front(u)-.003)*s,HOOD_HALF_SPAN*u))
param_panel('Fixed rear cowl lip',lambda s,u:front_deck_point(bonnet_rear(u)+.003+(1-bonnet_rear(u)-.003)*s,HOOD_HALF_SPAN*u),front,paint,8,64,thickness=.005,normal=lambda s,u:front_deck_normal(bonnet_rear(u)+.003+(1-bonnet_rear(u)-.003)*s,HOOD_HALF_SPAN*u))
for side in [-1,1]:
    fender=next(p for p in parts if p.name==f'fender_{side}_True')
    param_panel('Upper fender shoulder beside bonnet',lambda s,u,side=side:front_deck_point(s,side*(bonnet_side_u(s)+(1-bonnet_side_u(s))*(u+1)/2)),fender,paint,80,20,underside=side<0,thickness=.005,normal=lambda s,u,side=side:front_deck_normal(s,side*(bonnet_side_u(s)+(1-bonnet_side_u(s))*(u+1)/2)))
param_panel('Bonnet pressed inner panel',lambda s,u:bonnet_point(.025+.95*s,.965*u,.017),hood,inner_paint,48,64,underside=True,thickness=.003)
hem=[]
for s,u in [(0,-1),(1,-1),(1,1),(0,1),(0,-1)]:
    if not hem:hem.append(bonnet_point(.025+.95*s,.97*u,.009))
    else:
        a,b=prev,(s,u)
        hem.extend(bonnet_point(.025+.95*(a[0]+(b[0]-a[0])*i/32),.97*(a[1]+(b[1]-a[1])*i/32),.009) for i in range(1,33))
    prev=(s,u)
tube('Bonnet folded perimeter hem',hem,.0035,inner_paint,hood,True)

def stamping_rib(name,coords,width=.025):
    centers=[Vector(bonnet_point(s,u,.017)) for s,u in coords];vs=[];fs=[]
    for i,p in enumerate(centers):
        tangent=centers[min(i+1,len(centers)-1)]-centers[max(0,i-1)]
        cross=Vector((-tangent.y,tangent.x,0)).normalized()
        for lateral,depth in [(-1,0),(-.65,.005),(-.25,.010),(.25,.010),(.65,.005),(1,0)]:
            v=p+cross*(width*lateral);v.z-=depth;vs.append(tuple(v))
    for i in range(len(centers)-1):
        for j in range(5):
            k=i*6+j;fs.append((k,k+1,k+7,k+6))
    mesh(name,vs,fs,hood,inner_paint,.001)

for side in [-1,1]:
    stamping_rib('Stamped perimeter reinforcement',[(.08,side*.83),(.2,side*.91),(.45,side*.93),(.76,side*.89),(.93,side*.78)],.025)
    stamping_rib('Pressed diagonal bonnet bead',[(.18,side*.10),(.23,side*.27),(.18,side*.42),(.28,side*.68),(.26,side*.83)],.025)
    stamping_rib('Rear hinge reinforcement bead',[(.84,side*.1),(.87,side*.35),(.82,side*.58),(.9,side*.79)],.026)
    for s,u in [(.115,.61),(.13,.30),(.87,.82)]:
        points=[bonnet_point(s+ds,side*(u+du),.020) for ds,du in [(-.04,-.075),(.04,-.075),(.05,-.055),(.05,.055),(.04,.075),(-.04,.075),(-.05,.055),(-.05,-.055)]]
        mesh('Recessed inner stamping access pocket',points,[tuple(reversed(range(8)))],hood,well_liner,.002)
        tube('Access pocket rolled edge',points,.0016,inner_paint,hood,True)
pad_width=section([(0,.60),(.17,.84),(.55,.87),(.84,.79),(1,.60)])
param_panel('Moulded acoustic insulation pad',lambda s,u:bonnet_point(.30+.59*s,pad_width(s)*u,.036),hood,felt,40,56,underside=True,thickness=.007)
for side in [-1,1]:
    tube('Insulation pad bound edge',[bonnet_point(.30+.59*i/48,side*pad_width(i/48),.039) for i in range(49)],.004,felt,hood)
for u in [-.60,-.20,.20,.60]:
    param_panel('Insulation retaining spring clip',lambda s,v,u=u:bonnet_point(.52+.17*s,u+.037*v,.045),hood,alloy,8,4,underside=True,thickness=.001)
    for du in [-.025,.025]:
        tube('Stamped clip stiffening line',[bonnet_point(.53+.15*i/12,u+du,.047) for i in range(13)],.0015,steel,hood)
for s,u in [(.34,-.67),(.34,0),(.34,.67),(.86,-.5),(.86,.5)]:
    x,y,z=bonnet_point(s,u,.043)
    cylinder('Insulation fir tree retainer',(x,y,z),.009,.004,black,hood,'Z',24)
lock_x,_,lock_z=bonnet_point(.08,0,.035)
tube('Bonnet latch striker',[(lock_x-.018,-.035,lock_z),(lock_x-.018,-.035,lock_z-.037),(lock_x-.018,.035,lock_z-.037),(lock_x-.018,.035,lock_z)],.005,steel,hood)
for side in [-1,1]:
    x,y,z=bonnet_point(.10,side*.84,.023)
    cylinder('Bonnet adjustable rubber stop',(x,y,z-.009),.012,.018,rubber,hood,'Z',32)
    box('Bonnet hinge reinforcement',(-1.075,side*.63,1.072),(.12,.11,.018),inner_paint,hood,.006)

bay=part('front_service_bay','前储物舱','body',offset=(-.25,0,.46),start=.17)
outline=rounded_outline([(-2.18,-.70,.988),(-2.00,-.83,.988),(-1.16,-.81,1.045),(-1.08,-.65,1.061),(-1.08,.65,1.061),(-1.16,.81,1.045),(-2.00,.83,.988),(-2.18,.70,.988)],.065)
# Official open-bonnet photographs show a deep storage tub, not a flat service cover.
n=128
def storage_point(scale,z,a):
    return (-1.64+scale*.452*math.copysign(abs(math.cos(a))**.52,math.cos(a)),
            scale*.654*math.copysign(abs(math.sin(a))**.52,math.sin(a)),z)
vs=[];fs=[]
for i in range(n):
    a=i/n*math.tau
    outer=(-1.64+.552*math.copysign(abs(math.cos(a))**.52,math.cos(a)),
           .752*math.copysign(abs(math.sin(a))**.52,math.sin(a)),.986)
    inner=storage_point(1.035,.982,a)
    vs.extend([outer,inner])
for i in range(n):fs.append((2*i,2*((i+1)%n),2*((i+1)%n)+1,2*i+1))
polymer_uv(mesh('Front bay moulded perimeter tray',vs,fs,bay,service_tray,.010))
profiles=[(1.035,.982),(1.015,.965),(.982,.925),(.935,.845),(.870,.775),(.805,.746),(.785,.741)]
vs=[];fs=[]
for scale,z in profiles:
    for i in range(n):vs.append(storage_point(scale,z,i/n*math.tau))
for j in range(len(profiles)-1):
    for i in range(n):
        a=j*n+i;b=j*n+(i+1)%n;fs.append((a,b,b+n,a+n))
polymer_uv(mesh('Front storage tub deep shell',vs,fs,bay,service_plastic,.004))
floor_start=(len(profiles)-1)*n
polymer_uv(mesh('Front storage tub floor',vs[floor_start:],[tuple(range(n))],bay,service_tray,.004))
tube('Continuous front compartment weather seal',[storage_point(1.045,.989,i/n*math.tau) for i in range(n)],.008,rubber,bay,True)
tube('Front storage tub rolled upper lip',[storage_point(1.005,.978,i/n*math.tau) for i in range(n)],.0045,service_plastic,bay,True)
# Moulded lower service recess, pull handle and shallow stiffening channels are all below the rim.
box('Front storage service recess',(-1.68,0,.749),(.35,.115,.012),well_liner,bay,.025)
box('Front storage service recess inner floor',(-1.68,0,.756),(.305,.076,.006),service_plastic,bay,.018)
tube('Front storage service pull handle',[(-1.79,-.030,.766),(-1.79,.030,.766),(-1.73,.038,.774),(-1.66,.030,.766),(-1.66,-.030,.766)],.005,black,bay,smooth=True)
for side in [-1,1]:
    for offset in [0,.040]:
        tube('Front storage floor stiffening channel',[(-1.94+i*.56/48,side*(.28+offset),.749+.002*math.sin(i/48*math.pi)) for i in range(49)],.0032,service_plastic,bay)
    for x in [-1.96,-1.80,-1.48,-1.32]:
        tube('Front storage inner wall mould rib',[(x,side*.625,.957),(x,side*.586,.866),(x,side*.510,.772)],.0030,service_tray,bay)
for x in [-1.94,-1.34]:
    for y in [-.43,.43]:
        cylinder('Front storage drain recess',(x,y,.746),.012,.004,well_liner,bay,'Z',32)
        ring('Front storage drain rim',(x,y,.749),.012,service_plastic,bay,'Z',.0014)
for x in [-2.105,-1.175]:
    for y in [-.665,0,.665]:
        cylinder('Front bay captive fastener',(x,y,.997),.010,.005,black,bay,'Z',32)
        box('Front bay fastener slot',(x,y,1.000),(.010,.002,.0015),steel,bay,.0005)
box('Front storage latch mounting plate',(-2.137,0,.992),(.046,.142,.012),service_plastic,bay,.010)
tube('Front storage latch loop',[(-2.151,-.035,1.003),(-2.151,.035,1.003),(-2.132,.035,1.010),(-2.132,-.035,1.010)],.004,black,bay)
for side in [-1,1]:
    for i in range(24):
        y=side*(.16+i*.018)
        box('Front cowl ventilation slot',(-1.117,y,1.065),(.052,.007,.004),well_liner,bay,.002)
box('Washer neck plinth',(-1.94,-.710,1.000),(.100,.108,.026),black,bay,.014)
cylinder('Washer reservoir filler neck',(-1.94,-.710,1.012),.031,.032,white,bay,'Z',48)
cylinder('Blue washer fluid filler cap',(-1.94,-.710,1.032),.039,.010,washer_blue,bay,'Z',64)
box('Washer cap finger tab',(-1.973,-.710,1.035),(.025,.048,.009),washer_blue,bay,.004)
tube('Washer symbol windscreen',[(-1.955,-.733,1.039),(-1.935,-.737,1.039),(-1.925,-.716,1.039),(-1.935,-.695,1.039),(-1.955,-.699,1.039)],.001,white,bay)
box('Windscreen lower cowl',(-1.082,0,1.075),(.13,1.56,.04),black,bay,.017)
for y0,y1 in [(-.68,.15),(.08,.68)]:
    tube('Front wiper arm',[(-1.01,y0,1.117),(-.985,(y0+y1)/2,1.135),(-1.004,y1,1.128)],.0065,black,bay)
    tube('Front wiper blade',[(-1.003,y0+.06,1.137),(-1.003,y1,1.143)],.009,black,bay)
for side in [-1,1]:
    box('Body hinge bracket',(-1.076,side*.66,1.036),(.09,.08,.06),steel,bay,.006)
    fixed=(-1.17,side*.77,.962);moving=bonnet_point(.40,side*.91,.024)
    length=(Vector(moving)-Vector(fixed)).length
    strut=part(f'bonnet_strut_{side}',('左' if side>0 else '右')+'机盖撑杆','body',fixed,(-.25,side*.08,.46),.17,'hood_strut')
    strut['moving']=[moving[0],moving[2],-moving[1]]
    strut['hinge']=[HOOD_HINGE[0],HOOD_HINGE[2],-HOOD_HINGE[1]]
    strut['piston_length']=.38
    cylinder('Bonnet gas strut barrel',(fixed[0],fixed[1],fixed[2]+.17),.010,.34,black,strut,'Z',32)
    piston=cylinder('Bonnet gas strut piston',(fixed[0],fixed[1],fixed[2]+length-.19),.0045,.38,alloy,strut,'Z',24)
    piston['strut_component']='piston'
    tip=cylinder('Bonnet gas strut upper socket',(fixed[0],fixed[1],fixed[2]+length),.012,.025,black,strut,'Z',24)
    tip['strut_component']='tip'
    strut.rotation_euler=(Vector(moving)-Vector(fixed)).to_track_quat('Z','Y').to_euler()

# A curved fascia grid wraps around both corners instead of a flat cube.
vs=[];fs=[];ny=96;nz=48
for j in range(nz+1):
    for i in range(ny+1):
        u=math.sin((i/ny-.5)*math.pi);t=j/nz
        lower=grille_top(u*.888)
        for _ in range(4):lower=grille_top(u*front_width(lower))
        z=lower+(front_top(u)-lower)*t
        vs.append(front_surface(u*front_width(z),z))
for j in range(nz):
    for i in range(ny):
        a=j*(ny+1)+i;b=a+ny+1;fs.append((a,b,b+1,a+1))
fascia=mesh('Compound curved front fascia',vs,fs,front,paint,.012)
# Real recessed openings stop the lamps looking pasted onto a flat front panel.
for modifier in list(fascia.modifiers):
    if modifier.type=='SOLIDIFY':modifier.use_rim=True
    bpy.context.view_layer.objects.active=fascia
    bpy.ops.object.modifier_apply(modifier=modifier.name)
for side in [-1,1]:
    cutter=box('Lamp aperture cutter',(front_surface(side*.75,.741)[0],side*.75,.741),(.30,.198,.238),black,front,.039)
    slope=(front_surface(side*.75+.001,.741)[0]-front_surface(side*.75-.001,.741)[0])/.002
    cutter.rotation_euler.z=-math.atan(slope)
    bpy.context.view_layer.objects.active=cutter
    for modifier in list(cutter.modifiers):bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.context.view_layer.objects.active=fascia
    cut=fascia.modifiers.new('Recessed projector opening','BOOLEAN');cut.operation='DIFFERENCE';cut.object=cutter
    bpy.ops.object.modifier_apply(modifier=cut.name)
    bpy.data.objects.remove(cutter,do_unlink=True)
bevel=fascia.modifiers.new('Lamp aperture lip','BEVEL');bevel.width=.004;bevel.segments=3;bevel.limit_method='ANGLE'
intake_vs=[];intake_fs=[]
for j in range(13):
    for i in range(57):
        u=i/56*2-1;y=u*.82
        z=.292+(grille_top(y)-.292)*j/12
        x,_,_=front_surface(y,z);intake_vs.append((x+.035,y,z))
for j in range(12):
    for i in range(56):
        a=j*57+i;intake_fs.append((a,a+57,a+58,a+1))
mesh('Recessed active grille',intake_vs,intake_fs,front,black,.004)
for z in [.337,.385,.431]:
    width=.74 if z<.36 else .67 if z<.4 else .57
    param_panel('Flat horizontal intake louvre',lambda s,u,z=z,width=width:(front_surface(u*width,z)[0]+.012,u*width,z-.004+.008*s),front,black,2,48,thickness=.014)
for y in [-.53,0,.53]:
    tube('Grille vertical divider',[(front_surface(y,z)[0]+.008,y,z) for z in [.30,.36,.43]],.006,black,front)
tube('Intake upper rolled edge',[(front_surface(y,grille_top(y))[0]+.003,y,grille_top(y)) for y in [-.82+1.64*i/72 for i in range(73)]],.007,black,front)
tube('Lower splitter',[(front_surface(y,.295)[0]-.007,y,.285) for y in [-.82+1.64*i/48 for i in range(49)]],.014,black,front)
for side in [-1,1]:
    for y,z in [(side*.82,.55),(side*.45,.56)]:
        x=front_surface(y,z)[0]
        cylinder('Front parking sensor',(x-.004,y,z),.012,.004,paint,front,'X',24)
plate_z=.642
plate_x=min(front_surface(y,z)[0] for y in [-.23,0,.23] for z in [.565,plate_z,.719])-.014
box('Front plate mounting plinth',(plate_x+.009,0,plate_z),(.026,.458,.155),black,front,.008)
box('Front license plate',(plate_x-.009,0,plate_z),(.006,.440,.145),model_plate,front,.006)
text_label('ID.AURA T6',(plate_x-.014,0,plate_z),.041,front,False,plate_lettering)
camera_z=.788;camera_x=front_surface(0,camera_z)[0]
cylinder('Front camera bezel',(camera_x-.003,0,camera_z),.014,.004,alloy,front,'X',40)
cylinder('Front camera dark socket',(camera_x-.006,0,camera_z),.0115,.005,black,front,'X',40)
cylinder('Front camera lens',(camera_x-.009,0,camera_z),.0075,.002,sensor_optic,front,'X',40)
camera_brow=[]
for i in range(33):
    a=math.pi*i/32
    camera_brow.append((camera_x-.008,.0124*math.cos(a),camera_z+.0124*math.sin(a)))
tube('Front camera painted eyebrow',camera_brow,.0026,paint,front)
cover_outline=rounded_outline([(0,.445,.466),(0,.525,.466),(0,.525,.566),(0,.445,.566)],.009)
tube('Front tow eye cover joint',[(front_surface(y,z)[0]-.0015,y,z) for x,y,z in cover_outline],.0008,black,front,True)
badge(front,front_surface(0,.944)[0]-.003,.944)
lightbar=part('front_light_bar','前贯穿灯带','body',offset=(-1.2,0,.25),start=.1)
param_panel('Rounded continuous light bar housing',lambda v,u:light_bar_point(u,v,.0015),lightbar,black,20,128)
bar_lens=lamp_glass.copy();bar_lens.name='Front light bar smoked optical lens'
bar_bsdf=bar_lens.node_tree.nodes.get('Principled BSDF')
bar_bsdf.inputs['Base Color'].default_value=(.055,.070,.080,1)
bar_bsdf.inputs['Transmission Weight'].default_value=.76
bar_bsdf.inputs['Roughness'].default_value=.07
param_panel('Continuous rounded light bar optical cover',lambda v,u:light_bar_point(u,v,.005),lightbar,bar_lens,20,128)
boundary=[(u,0) for u in [-1+2*i/96 for i in range(97)]]
boundary.extend((1,i/32) for i in range(1,33))
boundary.extend((1-2*i/96,1) for i in range(1,97))
boundary.extend((-1,1-i/32) for i in range(1,32))
edge_vs=[light_bar_point(u,v,offset) for offset in [0,.005] for u,v in boundary];n=len(boundary)
mesh('Rolled light bar perimeter return',edge_vs,[(i+n,(i+1)%n+n,(i+1)%n,i) for i in range(n)],lightbar,black)
tube('Thin light bar sealing edge',[light_bar_point(u,v,.004) for u,v in boundary],.0013,black,lightbar,True)
bar_reflector=mat('Front guide dark optical channels',(.018,.025,.032),.35,.30)
bar_led=mat('Front flat light guide LED',(.65,.75,.80),0,.26,1.2)
for side in [-1,1]:
    for center in [.65,.77,.89]:
        points=[light_bar_point(side*(center+du),v,.003) for du,v in [(-.042,.37),(.042,.37),(.042,.61),(-.042,.61)]]
        mesh('Recessed end optical channel',points,[(0,1,2,3)] if side<0 else [(3,2,1,0)],lightbar,bar_reflector,.001)
    for name,start,end,v,width in [('Slim flat running light',.09,.978,.18,.05),('Tapered outboard light guide',.48,.978,.52,.08)]:
        vs=[];fs=[];n=64
        for row in [-1,1]:
            for i in range(n+1):
                t=i/n;u=side*(start+(end-start)*t)
                taper=smoothstep(0,.10,t)*(1-smoothstep(.88,1,t))
                sweep=.25*t*t if name=='Tapered outboard light guide' else 0
                vs.append(light_bar_point(u,v+sweep+row*width*taper,.008))
        for i in range(n):
            face=(i,i+1,i+n+2,i+n+1)
            fs.append(tuple(reversed(face)) if side>0 else face)
        light_role(mesh(name,vs,fs,lightbar,bar_led),'lowBeam')
for side in [-1,1]:
    lamp_x=front_surface(side*.75,.741)[0]
    lamp=part(f'headlight_{side}',('左' if side>0 else '右')+'纵向方灯','body',(lamp_x,side*.75,.741),(-1.2,side*.12,.18),.12)
    def lp(depth,dy,dz):return (lamp_x+depth,side*(.75+dy),.741+dz)
    box('Inset smoked headlamp chamber',lp(.023,0,0),(.055,.187,.224),black,lamp,.036)
    outline=[(-.085,-.088),(-.066,-.108),(.062,-.108),(.087,-.080),(.087,.077),(.060,.108),(-.060,.108),(-.085,.081)]
    boundary=rounded_outline([lp(-.008,y,z) for y,z in outline],.024)
    tube('Headlamp perimeter gasket',boundary,.004,black,lamp,True)
    # Outboard stacked optical modules and the separate inboard rectangular channel.
    for dz in [-.043,.054]:
        box('Outboard optical chamber',lp(.002,.035,dz),(.021,.068,.072),lamp_chrome,lamp,.015)
        box('Outboard lens surround',lp(-.010,.035,dz),(.008,.055,.059),black,lamp,.014)
        scale=.78 if dz<0 else 1.0;vs=[];fs=[];segments=72
        for depth,radius in [(.003,.031),(-.003,.029),(-.009,.026),(-.014,.022)]:
            for i in range(segments):
                a=i/segments*math.tau
                vs.append(lp(depth,.035+scale*radius*math.cos(a),dz+scale*radius*math.sin(a)))
        for j in range(3):
            for i in range(segments):
                a=j*segments+i;b=j*segments+(i+1)%segments;fs.append((a,b,b+segments,a+segments))
        mesh('Projector optical reflector cup',vs,fs,lamp,lamp_chrome,.001)
        for width,height,depth,material in [(.061,.065,-.009,black),(.055,.058,-.012,lamp_chrome)]:
            frame=[lp(depth,.035+dy*scale,dz+dz0*scale) for dy,dz0 in handle_outline(width,height,.010)]
            tube('Projector stepped optical bezel',frame,.0009,material,lamp,True)
        ring('Projector lens retaining ring',lp(-.020,.035,dz),.0225*scale,lamp_chrome,lamp,'X',.0011)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=64,ring_count=32,location=lp(-.015,.035,dz))
        lens=bpy.context.object;lens.name='Upper projection lens' if dz>0 else 'Lower projection lens'
        lens.scale=(.009,.022,.021 if dz>0 else .015)
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        light_role(parent(lens,lamp,high_beam if dz>0 else low_beam),'highBeam' if dz>0 else 'lowBeam')
        if dz<0:
            for dy in [-.014,-.005,.005,.014]:
                tube('Lower collimator facet',[lp(-.022,.035+dy,dz-.010),lp(-.024,.035+dy,dz+.010)],.0008,lamp_chrome,lamp)
    box('Inboard rectangular optical chamber',lp(.002,-.041,.021),(.020,.063,.084),black,lamp,.010)
    inner=rounded_outline([lp(-.011,y,z) for y,z in [(-.066,-.004),(-.017,-.009),(-.017,.050),(-.066,.057)]],.009)
    tube('Inboard rectangular reflector frame',inner,.0018,lamp_chrome,lamp,True)
    box('Inboard rectangular projector',lp(-.012,-.042,.023),(.005,.030,.025),optic,lamp,.003)
    for dy in [-.012,-.009,-.006,-.003,0,.003,.006,.009,.012]:
        tube('Rectangular optic micro rib',[lp(-.015,-.042+dy,.014),lp(-.015,-.042+dy,.032)],.00042,lamp_chrome,lamp)
    for dz in [-.005,.051]:
        for dy in [-.057,-.047,-.037,-.027]:
            tube('Rectangular optic horizontal prism',[lp(-.014,dy-.003,dz),lp(-.014,dy+.003,dz)],.00045,optic,lamp)
    blade=[lp(-.010,y,z) for y,z in [(-.071,-.082),(-.018,-.062),(.057,-.076),(-.017,-.087)]]
    mesh('Swept lower reflector blade',blade,[(0,1,2,3)],lamp,lamp_chrome,.001)
    text_label('IQ.LIGHT',lp(-.024,.033,.008),.007,lamp)
    for dy in [.012,.035,.058]:
        ring('Headlamp lower triple optical element',lp(-.016,dy,-.079),.0062,optic,lamp,'X',.0010)
        cylinder('Headlamp lower triple optical recess',lp(-.012,dy,-.079),.0053,.003,black,lamp,'X',32)
        tube('Headlamp lower optical support',[lp(-.004,dy,-.069),lp(-.006,dy,-.074)],.0012,lamp_chrome,lamp)
    for dy in [-.069,.077]:
        tube('Headlamp internal carrier bracket',[lp(.014,dy,-.081),lp(.013,dy,.077)],.0021,black,lamp)
    # Single curved optical cover avoids double refraction from a rounded solid box.
    center=Vector(lp(-.028,0,0));vs=[tuple(center)];fs=[];n=len(boundary)
    for j in range(1,9):
        r=j/8
        for edge in boundary:
            p=center.lerp(edge,r);p.x=lamp_x-.018-.010*(1-r*r);vs.append(tuple(p))
        for i in range(n):
            a=1+(j-1)*n+i;b=1+(j-1)*n+(i+1)%n
            face=(0,b,a) if j==1 else (a-n,b-n,b,a)
            fs.append(face if side>0 else tuple(reversed(face)))
    mesh('Curved smoked headlamp cover',vs,fs,lamp,lamp_glass)
    slope=(front_surface(side*.75+.001,.741)[0]-front_surface(side*.75-.001,.741)[0])/.002
    lamp.rotation_euler.z=-math.atan(slope)
    light_anchor('Headlight anchor',lp(-.035,.035,-.043),lamp,'headlight')

windscreen=part('windscreen','前挡风玻璃','cabin',offset=(-.45,0,1.2),start=.18)
loft('Curved windscreen',[(-1.025,1.103,.868),(-.86,1.265,.825),(-.60,1.475,.780),(-.32,1.60,.740)],windscreen,glass,.022,0)
front_sensor=part('front_sensor','前挡双目感知','cabin',offset=(-.45,0,1.2),start=.18)
# This is a separate assembly below the roof lidar, visible through the windscreen.
panel_outline=[(-.622,-.170,1.432),(-.622,.170,1.432),(-.602,.103,1.493),(-.602,-.103,1.493)]
mesh('Front stereo trapezoid mounting panel',panel_outline,[(0,1,2,3)],front_sensor,sensor_black,.022,.004)
tube('Front stereo panel lower bright edge',[panel_outline[0],panel_outline[1]],.0016,steel,front_sensor)
for y in [-.052,.052]:
    box('Front stereo individual lens pedestal',(-.632,y,1.462),(.020,.044,.042),black,front_sensor,.008)
    ring('Front stereo lens retaining ring',(-.645,y,1.466),.0155,steel,front_sensor,'X',.0012)
    cylinder('Front stereo optical lens',(-.647,y,1.466),.0125,.005,sensor_optic,front_sensor,'X',64)
    cylinder('Front stereo inner pupil',(-.650,y,1.466),.0050,.001,black,front_sensor,'X',48)
box('Front sensor lower scalloped cover',(-.535,0,1.385),(.112,.126,.092),sensor_black,front_sensor,.034)
cylinder('Front sensor lower service aperture',(-.594,0,1.392),.013,.004,black,front_sensor,'X',40)
tube('Interior mirror mounting arm',[(-.518,0,1.386),(-.452,0,1.350),(-.414,0,1.348)],.017,black,front_sensor,smooth=True)
box('Interior rear view mirror housing',(-.378,0,1.334),(.043,.236,.074),black,front_sensor,.027)
box('Interior rear view mirror reflective inset',(-.353,0,1.336),(.004,.208,.052),mirror_glass,front_sensor,.018)
box('Interior mirror lower switch',(-.351,0,1.307),(.008,.024,.010),sensor_black,front_sensor,.003)

# The official key is a detail-only assembly, hidden in the assembled vehicle.
print('BUILD_STAGE key',flush=True)
key=part('remote_key','遥控钥匙','cabin',(0,0,.84),(0,0,.45),.30)
key['detailOnly']=True
key_shell=mat('Key pebble graphite soft touch',(.030,.034,.037),.05,.48)
key_seam=mat('Key shell seam',(.007,.009,.011),0,.60)
key_glyph=mat('Key laser etched glyphs',(.38,.42,.44),0,.65)
bpy.ops.mesh.primitive_uv_sphere_add(segments=96,ring_count=64,location=(0,0,.84))
obj=bpy.context.object;obj.name='Key rounded pebble upper and lower shell';obj.scale=(.048,.024,.008)
bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);parent(obj,key,key_shell)
tube('Key continuous shell split',[(.0478*math.cos(i/128*math.tau),.0238*math.sin(i/128*math.tau),.840) for i in range(128)],.00045,key_seam,key,True)
def key_surface(x,y):return .84+.008*math.sqrt(max(0,1-(x/.048)**2-(y/.024)**2))+.00018
def key_path(name,coords,cx,cy,scale=.010,cyclic=False):
    points=[Vector((cx+x*scale,cy+y*scale)) for x,y in coords]
    if cyclic:points.append(points[0])
    vs=[];fs=[];half=.00014
    for i,p in enumerate(points):
        tangent=(points[min(i+1,len(points)-1)]-points[max(0,i-1)]).normalized();normal=Vector((-tangent.y,tangent.x))*half
        for q in [p-normal,p+normal]:vs.append((q.x,q.y,key_surface(q.x,q.y)))
        if i:fs.append((2*i-2,2*i-1,2*i+1,2*i))
    return mesh(name,vs,fs,key,key_glyph)
key_path('Key lock body glyph',[(-.45,-.45),(-.45,.30),(.45,.30),(.45,-.45)],.022,.004,cyclic=True)
key_path('Key lock shackle glyph',[(-.30,.30),(-.30,.65),(-.15,.85),(.15,.85),(.30,.65),(.30,.30)],.022,.004)
key_path('Key unlock body glyph',[(-.45,-.45),(-.45,.30),(.45,.30),(.45,-.45)],.002,.004,cyclic=True)
key_path('Key unlock shackle glyph',[(-.30,.30),(-.30,.65),(-.15,.85),(.15,.85),(.30,.65),(.38,.55)],.002,.004)
key_path('Key vehicle outline glyph',[(-.75,-.25),(-.55,.20),(-.25,.50),(.35,.50),(.72,.10),(.72,-.30),(-.75,-.25)],-.018,.004,cyclic=True)
for x in [-.0235,-.0125]:key_path('Key vehicle wheel glyph',[(.16*math.cos(i/32*math.tau),.16*math.sin(i/32*math.tau)) for i in range(32)],x,-.001,cyclic=True)
key_path('Key parking P glyph',[(-.20,-.70),(-.20,.70),(.25,.70),(.50,.40),(.50,.05),(.25,-.15),(-.20,-.15)],-.034,.004)
for radius in [.0035,.0060]:
    coords=[(-radius/.010*math.cos(a),radius/.010*math.sin(a)) for a in [math.pi*.55+i/24*math.pi*.90 for i in range(25)]]
    key_path('Key parking radio arc',coords,-.034,.004)
print('BUILD_STAGE roof',flush=True)
roof=part('panoramic_roof','全景玻璃车顶','cabin',offset=(0,0,1.9),start=.22)
def roof_point(x,y):return (x,y,roof_z(x)+.022*(1-(y/roof_w(x))**2))
param_panel('Fixed rear panoramic glass',lambda s,u:roof_point(.735+.965*s,roof_w(.735+.965*s)*u),roof,glass,48,48,thickness=.005)
param_panel('Fixed front roof header',lambda s,u:roof_point(-.32+.085*s,roof_w(-.32+.085*s)*u),roof,glass,8,48,thickness=.005)
for side in [-1,1]:
    param_panel('Fixed glass aperture side surround',lambda s,u,side=side:roof_point(-.235+.970*s,side*(.605+(roof_w(-.235+.970*s)-.605)*(u+1)/2)),roof,glass,48,8,underside=side<0,thickness=.005)
    tube('Sunroof sliding guide rail',[(-.23+1.72*i/48,side*.618,roof_z(-.23+1.72*i/48)+.006) for i in range(49)],.006,black,roof)
seal=[]
for x,y in [(-.235,-.604),(.735,-.604),(.735,.604),(-.235,.604),(-.235,-.604)]:
    if not seal:seal.append(roof_point(x,y))
    else:
        a=last
        seal.extend(roof_point(a[0]+(x-a[0])*i/24,a[1]+(y-a[1])*i/24) for i in range(1,25))
    last=(x,y)
tube('Sunroof continuous aperture seal',seal,.004,rubber,roof,True)
sunroof=part('sunroof','电动天窗','cabin',(-.23,0,1.60),(0,0,2.12),.23,'sunroof')
param_panel('Sliding front sunroof glass',lambda s,u:roof_point(-.23+.96*s,.600*u),sunroof,glass,48,48,thickness=.005)
for side in [-1,1]:
    box('Sunroof sliding carriage',(.43,side*.573,1.613),(.12,.035,.035),black,sunroof,.006)

for side in [-1,1]:
    rack=part(f'roof_rack_{side}',('左' if side>0 else '右')+'行李架','body',offset=(0,side*.2,2.05),start=.25)
    # Broad low-profile rail sections taper into two separate feet, leaving a visible daylight gap.
    rail_height=section([(-.20,1.625),(-.04,1.688),(.18,1.709),(.82,1.704),(1.19,1.652),(1.47,1.582)])
    rail_width=section([(-.20,.008),(-.04,.020),(.18,.023),(.82,.024),(1.19,.023),(1.47,.009)])
    vs=[];fs=[];nx=72;nc=16
    for i in range(nx+1):
        x=-.20+1.67*i/nx;z=rail_height(x);w=rail_width(x)
        for j in range(nc):
            a=j/nc*math.tau
            vs.append((x,side*(.689+w*math.cos(a)),z+.014*math.sin(a)))
    for i in range(nx):
        for j in range(nc):
            k=i*nc+j;q=i*nc+(j+1)%nc;face=(k,q,q+nc,k+nc)
            fs.append(face if side<0 else tuple(reversed(face)))
    front_cap=tuple(range(nc));rear_cap=tuple(nx*nc+j for j in range(nc))
    fs.extend([front_cap if side<0 else tuple(reversed(front_cap)),tuple(reversed(rear_cap)) if side<0 else rear_cap])
    mesh('Roof rail sculpted arch',vs,fs,rack,mirror_cap)
    # The narrow silver insert is inset into the inner vertical face, not a round chrome tube.
    strip=[];faces=[]
    for i in range(49):
        x=.025+1.12*i/48;z=rail_height(x);y=side*(.689-rail_width(x)-.0006)
        for dz in [-.0045,.0045]:strip.append((x,y,z+dz))
        if i:faces.append((2*i-2,2*i-1,2*i+1,2*i))
    mesh('Roof rail inner silver insert',strip,faces if side<0 else [tuple(reversed(f)) for f in faces],rack,alloy,.001)
    for x in [-.14,1.37]:
        z=roof_z(x)+.009
        box('Roof rail integrated foot',(x,side*.689,z+.012),(.15,.060,.038),mirror_cap,rack,.016)
spoiler=part('rear_spoiler','后扰流板','body',TAILGATE_HINGE,(.6,0,1.45),.2,'tailgate')
spoiler_vs=[];spoiler_fs=[];nx=32;ny=64
spoiler_height=section([(0,1.535),(.40,1.545),(.75,1.536),(1,1.524)])
spoiler_width=section([(0,.752),(.40,.775),(.80,.786),(1,.762)])
for bottom in [False,True]:
    for i in range(nx+1):
        r=i/nx
        for j in range(ny+1):
            u=math.sin((j/ny-.5)*math.pi)
            x=1.68+.30*r+.025*(1-r)*u**6-.035*r*u**8
            z=spoiler_height(r)+.011*(1-u*u)-(.018 if bottom else 0)
            spoiler_vs.append((x,spoiler_width(r)*u,z))
count=(nx+1)*(ny+1)
for i in range(nx):
    for j in range(ny):
        k=i*(ny+1)+j;face=(k,k+ny+1,k+ny+2,k+1)
        spoiler_fs.append(face);spoiler_fs.append(tuple(k+count for k in reversed(face)))
for i in range(nx):
    for j in [0,ny]:
        k=i*(ny+1)+j;face=(k,k+count,k+ny+1+count,k+ny+1)
        spoiler_fs.append(face if j==0 else tuple(reversed(face)))
for i in [0,nx]:
    for j in range(ny):
        k=i*(ny+1)+j;face=(k,k+1,k+1+count,k+count)
        spoiler_fs.append(face if i==0 else tuple(reversed(face)))
mesh('Rounded integrated roof spoiler',spoiler_vs,spoiler_fs,spoiler,paint,bevel=.003)
for side in [-1,1]:
    points=[(1.72,side*.736,1.529),(1.95,side*.768,1.517),(1.94,side*.726,1.430),(1.84,side*.696,1.466)]
    mesh('Spoiler black side endplate',points,[(0,1,2,3)] if side>0 else [(3,2,1,0)],spoiler,black,.006,.002)
loft('Spoiler dark underside',[(1.76,1.512,.768),(1.955,1.507,.760)],spoiler,black,.006,.005)
light_role(box('High mounted stop lamp',(1.983,0,1.517),(.010,.52,.008),brake_light,spoiler,.003),'brakeLight')
rear_camera_trim=mat('Rear camera moulded black',(.004,.005,.006),0,.38)
rear_camera_trim.node_tree.nodes.get('Principled BSDF').inputs['Specular IOR Level'].default_value=.18
wiper_polymer=mat('Rear wiper textured polymer',(.005,.006,.007),0,.62)
wiper_polymer.node_tree.nodes.get('Principled BSDF').inputs['Specular IOR Level'].default_value=.16
# The photographed upper camera sits in a low fairing above the spoiler edge.
upper_camera_vertices=[(1.82,-.052,1.529),(1.985,-.052,1.529),(1.956,-.034,1.579),(1.862,-.034,1.579),
                       (1.82,.052,1.529),(1.985,.052,1.529),(1.956,.034,1.579),(1.862,.034,1.579)]
mesh('Rear upper camera housing',upper_camera_vertices,[(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)],spoiler,rear_camera_trim,bevel=.004)
cylinder('Rear upper camera lens',(1.977,0,1.554),.011,.005,sensor_optic,spoiler,'X',40)

rear_glass=part('rear_glass','后挡风玻璃','cabin',TAILGATE_HINGE,(.7,0,1.2),.2,'tailgate')
backlight_vs=[];backlight_fs=[];nx=48;ny=96
for i in range(nx+1):
    for j in range(ny+1):backlight_vs.append(rear_window_point(i/nx,math.sin((j/ny-.5)*math.pi)))
for i in range(nx):
    for j in range(ny):
        k=i*(ny+1)+j;backlight_fs.append((k,k+ny+1,k+ny+2,k+1))
mesh('Convex rear windscreen',backlight_vs,backlight_fs,rear_glass,rear_glazing)
def rear_glass_detail_point(t,u,offset=.002):
    x,y,z=rear_window_point(t,u)
    return x+offset,y,z
for a,b,c,d in [(0,.075,-1,1),(.945,1,-1,1),(.075,.945,-1,-.965),(.075,.945,.965,1)]:
    param_panel('Rear glass ceramic edge',lambda s,u:rear_glass_detail_point(a+(b-a)*s,c+(d-c)*(u+1)/2),rear_glass,black,12,32)
heater=mat('Rear glass heater conductor',(.055,.025,.012),.12,.62)
for t in [.25+.075*i for i in range(9)]:
    tube('Rear window heating trace',[rear_glass_detail_point(t,-.92+1.84*i/48,.0025) for i in range(49)],.00035,heater,rear_glass)
for side in [-1,1]:
    tube('Rear glass edge seal',[rear_window_point(i/64,side) for i in range(65)],.0035,black,rear_glass)
def wiper_point(y,z,offset=.012):
    t=(1.50-z)/.360
    for _ in range(5):
        u=y/(.640+.095*t)
        t+=(rear_window_point(t,u)[2]-z)/.360
    x=rear_window_point(t,y/(.640+.095*t))[0]
    return (x+offset,y,z)
cylinder('Rear wiper pivot',wiper_point(.11,1.195),.022,.012,black,rear_glass,'X',40)
# Broad moulded pivot cover tapers into the arm, with a flat rubber wiping edge.
wiper_stations=[(.145,.022,.016),(.110,.024,.024),(.070,.021,.026),(-.100,.016,.022),(-.255,.010,.016)]
vs=[];fs=[];section=[(-.004,-1),(.009,-1),(.014,-.6),(.014,.6),(.009,1),(-.004,1)]
for y,width,depth in wiper_stations:
    for dx,dz in section:vs.append(wiper_point(y,1.190+dz*width,depth+dx))
for j in range(len(wiper_stations)-1):
    for i in range(len(section)):
        k=j*len(section)+i;q=j*len(section)+(i+1)%len(section);fs.append((k,q,q+len(section),k+len(section)))
fs.extend([tuple(reversed(range(len(section)))),tuple((len(wiper_stations)-1)*len(section)+i for i in range(len(section)))])
mesh('Rear wiper arm',vs,fs,rear_glass,wiper_polymer,bevel=.001)
vs=[];fs=[]
for i in range(33):
    y=-.445+.380*i/32
    for dx,dz in [(0,-.005),(.008,-.005),(.008,.005),(0,.005)]:vs.append(wiper_point(y,1.181+dz,.019+dx))
for j in range(32):
    for i in range(4):k=j*4+i;q=j*4+(i+1)%4;fs.append((k,q,q+4,k+4))
mesh('Rear wiper blade',vs,fs,rear_glass,rubber,bevel=.0008)
tube('Rear wiper pivot cap seam',[wiper_point(y,1.190+z,.040) for y,z in [(.072,-.019),(.066,0),(.072,.019)]],.0007,black,rear_glass)
tailgate=part('tailgate','尾门','body',TAILGATE_HINGE,(1.12,0,.6),.1,'tailgate')
deck_vs=[];deck_fs=[];nx=16;ny=64
for i in range(nx+1):
    r=i/nx
    for j in range(ny+1):
        u=j/ny*2-1
        deck_vs.append(rear_shoulder_point(r,u))
for i in range(nx):
    for j in range(ny):
        k=i*(ny+1)+j;deck_fs.append((k,k+1,k+ny+2,k+ny+1))
mesh('Rolled tailgate upper shoulder',deck_vs,deck_fs,tailgate,paint,.006)
rear_vs=[];rear_fs=[];ny=64;nz=24
for j in range(nz+1):
    v=j/nz
    for i in range(ny+1):
        u=math.sin((i/ny-.5)*math.pi);bottom=.67
        for _ in range(6):bottom=rear_split_height(u*(tailgate_width(bottom)-.002))+.002
        z=bottom+(1.105-bottom)*v
        rear_vs.append(rear_surface(u*(tailgate_width(z)-.002),z))
for j in range(nz):
    for i in range(ny):
        a=j*(ny+1)+i;rear_fs.append((a,a+1,a+ny+2,a+ny+1))
mesh('Sculpted tailgate face',rear_vs,rear_fs,tailgate,paint,.008)
# Fixed rear quarters surround the separate tailgate with a narrow real shut gap.
for side in [-1,1]:
    quarter=next(p for p in parts if p.name==f'fender_{side}_False')
    vs=[];fs=[];ny=24;nz=48
    for j in range(nz+1):
        v=j/nz
        for i in range(ny+1):
            u=math.sin(i/ny*math.pi/2);bottom=.71
            for _ in range(6):
                y=(tailgate_width(bottom)+.002)*(1-u)+rear_width(bottom)*u
                bottom=rear_split_height(y)+.002
            z=bottom+(1.105-bottom)*v
            y=(tailgate_width(z)+.002)*(1-u)+rear_width(z)*u
            vs.append(rear_surface(side*y,z))
    for j in range(nz):
        for i in range(ny):
            k=j*(ny+1)+i;face=(k,k+1,k+ny+2,k+ny+1)
            fs.append(face if side>0 else tuple(reversed(face)))
    mesh('Fixed curved rear quarter return',vs,fs,quarter,paint,.006)
    vs=[];fs=[];nx=16;ny=24;start_u=tailgate_width(1.105)/rear_width(1.105)
    for i in range(nx+1):
        r=i/nx
        for j in range(ny+1):
            y=side*(tailgate_width(1.105)+.004+(rear_width(1.105)-tailgate_width(1.105)-.004)*j/ny)
            vs.append(rear_shoulder_point(r,y/tailgate_width(1.105)))
    for i in range(nx):
        for j in range(ny):
            k=i*(ny+1)+j;face=(k,k+1,k+ny+2,k+ny+1)
            fs.append(face if side<0 else tuple(reversed(face)))
    mesh('Fixed rolled rear corner shoulder',vs,fs,quarter,paint,.006)
badge(tailgate,rear_surface(0,1.061)[0]+.005,1.061,True)
text_label('I D. A U R A',(rear_surface(0,.963)[0]+.005,0,.963),.030,tailgate,True,black)
text_label('T6',(rear_surface(.64,.765)[0]+.01,.64,.765),.027,tailgate,True,black)
# Separate parking camera under the tailgate lip, above the display plate.
pc_z=.680;pc_x=rear_surface(0,pc_z)[0]+.017
mesh('Rear parking camera housing',[(pc_x,-.037,.702),(pc_x,.037,.702),(pc_x,.027,.653),(pc_x,-.027,.653)],[(0,1,2,3)],tailgate,sensor_black,.010,.003)
cylinder('Rear parking camera lens',(pc_x+.008,0,.676),.012,.005,sensor_optic,tailgate,'X',40)
tube('Rear parking camera retaining ring',[(pc_x+.012,.014*math.cos(i/64*math.tau),.676+.014*math.sin(i/64*math.tau)) for i in range(64)],.0012,mirror_shell,tailgate,True)
rear_font=bpy.data.fonts.load('/System/Library/Fonts/STHeiti Medium.ttc')
text_label('一汽-大众',(rear_surface(-.57,.765)[0]+.008,-.57,.765),.025,tailgate,True,black,rear_font)
lower_seal=[]
for i in range(65):
    u=i/64*2-1;z=.67
    for _ in range(6):z=rear_split_height(u*tailgate_width(z))
    lower_seal.append(rear_point(u*tailgate_width(z),z,-.002))
tube('Arched tailgate lower weather seal',lower_seal,.0022,black,tailgate)
for side in [-1,1]:
    tube('Tailgate side weather seal',[rear_point(side*tailgate_width(z),z,-.002) for z in [.714+.391*i/48 for i in range(49)]],.002,black,tailgate)
rear_bumper=part('rear_bumper','后保险杠','body',offset=(1.25,0,.08),start=.06)
bumper_vs=[];bumper_fs=[];ny=64;nz=24
for j in range(nz+1):
    v=j/nz
    for i in range(ny+1):
        u=math.sin((i/ny-.5)*math.pi);top=.71
        for _ in range(6):top=rear_split_height(u*rear_width(top))-.002
        z=.29+(top-.29)*v
        bumper_vs.append(rear_surface(u*rear_width(z),z))
for j in range(nz):
    for i in range(ny):
        a=j*(ny+1)+i;bumper_fs.append((a,a+1,a+ny+2,a+ny+1))
mesh('Wrapped rear bumper',bumper_vs,bumper_fs,rear_bumper,paint,.008)
diffuser_vs=[];diffuser_fs=[]
for j in range(13):
    for i in range(57):
        u=math.sin((i/56-.5)*math.pi);top=.55
        for _ in range(6):top=diffuser_top(u*(rear_width(top)-.04))
        z=.295+(top-.295)*j/12;y=u*(rear_width(z)-.04)
        diffuser_vs.append(rear_point(y,z,.006))
for j in range(12):
    for i in range(56):
        a=j*57+i;diffuser_fs.append((a,a+1,a+58,a+57))
mesh('Contoured rear diffuser',diffuser_vs,diffuser_fs,rear_bumper,black,.012)
insert_vs=[];insert_fs=[];ny=64;nz=12
for j in range(nz+1):
    for i in range(ny+1):
        u=i/ny*2-1;y=u*.76;bottom=.318+.010*u**4;top=.447-.037*smoothstep(.35,1,abs(u))
        z=bottom+(top-bottom)*j/nz;insert_vs.append(rear_point(y,z,.014))
for j in range(nz):
    for i in range(ny):
        k=j*(ny+1)+i;insert_fs.append((k,k+1,k+ny+2,k+ny+1))
mesh('Recessed lower valance insert',insert_vs,insert_fs,rear_bumper,valance_black,.004)
tube('Lower valance arched rim',[rear_point(y,.447-.037*smoothstep(.35,1,abs(y/.76)),.017) for y in [-.76+1.52*i/64 for i in range(65)]],.003,black,rear_bumper)
tube('Diffuser curved lower lip',[rear_point(y,.315+.008*(y/.78)**4,.016) for y in [-.78+1.56*i/64 for i in range(65)]],.006,black,rear_bumper)
for side in [-1,1]:
    for name,margin,material in [('Recessed reflector surround',.008,black),('Swept rear reflector',0,reflector_red)]:
        outline=[]
        for y,z in [(.46-margin,.566-margin),(.79+margin,.566-margin),(.79+margin,.602+margin),(.53-margin,.602+margin)]:
            outline.append((rear_surface(side*y,z)[0]+(.007 if margin else .009),side*y,z))
        outline=rounded_outline(outline,.012)
        center=sum(outline,Vector())/len(outline);offset=.007 if margin else .009
        center.x=rear_surface(center.y,center.z)[0]+offset
        vs=[tuple(center)];fs=[];n=len(outline)
        for j in range(1,9):
            for edge in outline:
                p=center.lerp(edge,j/8);p.x=rear_surface(p.y,p.z)[0]+offset;vs.append(tuple(p))
            for i in range(n):
                a=1+(j-1)*n+i;b=1+(j-1)*n+(i+1)%n
                face=(0,a,b) if j==1 else (a-n,a,b,b-n)
                fs.append(face if side>0 else tuple(reversed(face)))
        mesh(name,vs,fs,rear_bumper,material,.001)
    for y,z in [(side*.32,.38),(side*.77,.41)]:
        x=rear_surface(y,z)[0]
        cylinder('Rear parking sensor',(x+.024,y,z),.012,.004,black,rear_bumper,'X',24)
plate_x=rear_surface(0,.555)[0]+.012
box('Rear license plate',(plate_x,0,.555),(.018,.46,.155),model_plate,rear_bumper,.008)
text_label('ID.AURA T6',(plate_x+.013,0,.555),.042,rear_bumper,True,plate_lettering)
for side in [-1,1]:
    y=side*.62;z=.49
    x=rear_surface(y,z)[0]
    box('Reverse lamp dark optical bezel',(x+.024,y,z),(.016,.182,.054),black,rear_bumper,.012)
    light_role(box('White reverse lamp',(x+.035,y,z),(.006,.148,.030),reverse_light,rear_bumper,.010),'reverseLight')
rear_lights=part('tail_lights','后贯穿尾灯','body',TAILGATE_HINGE,(1.18,0,.27),.12,'tailgate')
rear_brake=brake_light.copy();rear_brake.name='Rear dotted brake chamber'
rear_brake.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.08,.003,.005,1)
rear_lens=lamp_glass.copy();rear_lens.name='Rear smoked optical cover'
rear_lens.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.030,.018,.022,1)
rear_lens.node_tree.nodes.get('Principled BSDF').inputs['Transmission Weight'].default_value=.64

def rear_band(group,side=None):
    def y_value(u,z):
        if side is None:return u*(tailgate_width(z)-.002)
        q=(u+1)/2
        return side*((tailgate_width(z)+.002)*(1-q)+rear_width(z)*q)
    for name,material,depth in [('Rear light bar backing',black,.002),('Rear light bar optical cover',rear_lens,.008)]:
        vs=[];fs=[];ny=80;nz=8
        for j in range(nz+1):
            z=1.029+.076*j/nz
            for i in range(ny+1):
                u=math.sin((i/ny-.5)*math.pi);vs.append(rear_point(y_value(u,z),z,depth))
        for j in range(nz):
            for i in range(ny):
                k=j*(ny+1)+i;face=(k,k+1,k+ny+2,k+ny+1)
                fs.append(face if side is None or side>0 else tuple(reversed(face)))
        mesh(name,vs,fs,group,material)
    vs=[];fs=[];ny=96
    for row in [-1,1]:
        for i in range(ny+1):
            y=y_value(i/ny*2-1,1.056)
            z=1.052+.040*smoothstep(.80,.855,abs(y))+row*.0045
            y=y_value(i/ny*2-1,z)
            vs.append(rear_point(y,z,.010))
    for i in range(ny):
        if side is None and abs((vs[i][1]+vs[i+1][1])/2)<.075:continue
        face=(i,i+1,i+ny+2,i+ny+1);fs.append(face if side is None or side>0 else tuple(reversed(face)))
    light_role(mesh('Single slim red rear light guide',vs,fs,group,rear_led,.001),'tailLight')
    # Two fine prism rows replace a coarse, tooth-like reflective strip.
    prism_vs=[];prism_fs=[]
    cells=max(1,math.ceil(abs(y_value(1,1.037)-y_value(-1,1.037))/.0035))
    for i in range(cells):
        u=(i+.5)/cells*2-1;y=y_value(u,1.037)
        if side is None and abs(y)<.09:continue
        half=abs(y_value(min(1,u+1/cells),1.037)-y)*.72
        for z0 in [1.034,1.0373]:
            for z in [z0,z0+.0023]:
                for yy in [y-half,y+half]:prism_vs.append(rear_point(yy,z,.0104))
            k=len(prism_vs)-4;prism_fs.append((k,k+1,k+3,k+2))
    mesh('Rear lower microprism array',prism_vs,prism_fs,group,lamp_chrome,.0005)
    vs=[];fs=[]
    cells=max(1,math.ceil(abs(y_value(1,1.089)-y_value(-1,1.089))/.0035))
    for i in range(cells):
        y=y_value((i+.5)/cells*2-1,1.089)
        if not .45<abs(y)<.845:continue
        for z0 in [1.084,1.088,1.092]:
            k=len(vs)
            for yy,z in [(y-.0009,z0-.0007),(y+.0009,z0-.0007),(y+.0009,z0+.0007),(y-.0009,z0+.0007)]:vs.append(rear_point(yy,z,.0095))
            fs.append((k,k+1,k+2,k+3))
    light_role(mesh('Ruby upper tail lamp chamber',vs,fs,group,rear_brake),'brakeLight')
    vs=[];fs=[]
    for z in [1.032,1.036]:
        for i in range(ny+1):vs.append(rear_point(y_value(i/ny*2-1,z),z,.0095))
    for i in range(ny):fs.append((i,i+1,i+ny+2,i+ny+1) if side is None or side>0 else (i+ny+1,i+ny+2,i+1,i))
    mesh('Lower tail lamp separator',vs,fs,group,black)

rear_band(rear_lights)
for side in [-1,1]:
    outer=part(f'outer_tail_lamp_{side}',('左' if side>0 else '右')+'外侧尾灯','body',offset=(.8,side*.35,.26),start=.13)
    rear_band(outer,side)
    for y0 in [side*.47,side*.56,side*.65,side*.795]:
        group=rear_lights if abs(y0)<.75 else outer
        points=[rear_point(y,z,.0097) for y,z in [(y0-.030,1.042),(y0+.030,1.042),(y0+.030,1.047),(y0-.030,1.047)]]
        mesh('Short lower rear optical insert',points,[(0,1,2,3)],group,lamp_chrome)
    vs=[];fs=[];n=64
    for j in range(9):
        for i in range(n+1):
            t=i/n;scale=smoothstep(0,.22,t);z=1.067+(-.038+.076*j/8)*scale
            x,w,_=side_surface(1.82+.48*t,z,'rear');vs.append((x,side*(w+.006),z))
    for j in range(8):
        for i in range(n):
            k=j*(n+1)+i;face=(k,k+1,k+n+2,k+n+1)
            fs.append(face if side<0 else tuple(reversed(face)))
    mesh('Tapered side tail lamp housing',vs,fs,outer,black,.003)
    mesh('Smoked side tail lamp cover',[(x,y+side*.002,z) for x,y,z in vs],fs,outer,rear_lens)
    vs=[];fs=[]
    for row in [-1,1]:
        for i in range(n+1):
            t=i/n;scale=smoothstep(0,.22,t);z=1.067+(-.0055+.0305*smoothstep(.45,1,t)+row*.003)*scale
            x,w,_=side_surface(1.82+.48*t,z,'rear');vs.append((x,side*(w+.010),z))
    for i in range(n):
        face=(i,i+1,i+n+2,i+n+1);fs.append(face if side<0 else tuple(reversed(face)))
    light_role(mesh('Single tapered side rear light guide',vs,fs,outer,rear_led,.001),'tailLight')

# The full rear door shares the roof hinge; these narrow frames move with its glass.
for side in [-1,1]:
    vs=[];fs=[];n=48
    for i in range(n+1):
        t=i/n;inner=Vector(rear_window_point(t,side))
        outer=inner+Vector((.008,side*(.020*(1-t)+.012*t),.002*(1-t)))
        vs.extend([tuple(inner),tuple(outer)])
    for i in range(n):
        k=i*2;face=(k,k+1,k+3,k+2)
        fs.append(face if side>0 else tuple(reversed(face)))
    mesh('Moving tailgate glass side frame',vs,fs,tailgate,paint,.006)
    tube('Moving rear glass inner seal',[rear_window_point(i/48,side) for i in range(49)],.004,black,tailgate)
vs=[];fs=[];ny=48;nz=16
for j in range(nz+1):
    z=.684+.405*j/nz
    for i in range(ny+1):
        y=(i/ny*2-1)*(tailgate_width(z)-.038)
        vs.append(rear_point(y,z,-.027))
for j in range(nz):
    for i in range(ny):
        k=j*(ny+1)+i;fs.append((k,k+ny+1,k+ny+2,k+1))
cargo_plastic=mat('Cargo moulded trim',(.012,.016,.018),0,.72)
carpet=mat('Luggage compartment carpet',(.021,.024,.025),0,.97)
mesh('Tailgate inner trim panel',vs,fs,tailgate,cargo_plastic,.012)
box('Tailgate interior pull handle',(2.30,0,.723),(.035,.23,.035),black,tailgate,.011)

frame=part('rear_aperture_frame','后备箱门框','body',offset=(.35,0,.16),start=.18)
aperture=rounded_outline([(2.30,-.725,.652),(2.18,-.755,1.115),(1.808,-.678,1.50),(1.70,-.64,1.548),(1.70,.64,1.548),(1.808,.678,1.50),(2.18,.755,1.115),(2.30,.725,.652)],.045)
aperture=[Vector((min(x,rear_surface(y,z)[0]-.040) if z<=1.14 else x,y,z)) for x,y,z in aperture]
tube('Rear aperture folded metal flange',[(x-.015,y,z) for x,y,z in aperture],.018,paint,frame,True)
tube('Continuous tailgate aperture seal',[(x+.003,y,z) for x,y,z in aperture],.011,rubber,frame,True)
param_panel('Cargo loading sill',lambda s,u:(rear_surface(.72*u,.635)[0]-.040-.14*(1-s),.72*u,.648),frame,cargo_plastic,4,48,thickness=.025)
box('Rear roof inner crossmember',(1.70,0,1.525),(.08,1.30,.045),black,frame,.012)
cargo=part('luggage_compartment','后备箱内衬','cabin',offset=(.40,0,.40),start=.31)
box('Carpeted luggage floor',(1.73,0,.558),(1.10,1.36,.055),carpet,cargo,.018)
box('Luggage floor service flap',(1.75,0,.588),(.67,1.02,.008),carpet,cargo,.010)
box('Luggage floor pull tab',(2.03,0,.594),(.055,.11,.012),black,cargo,.004)
for side in [-1,1]:
    box('Cargo inner side wall',(1.73,side*.681,.79),(1.05,.052,.43),cargo_plastic,cargo,.020)
    box('Rear wheelhouse inner trim',(1.46,side*.625,.71),(.56,.17,.27),carpet,cargo,.055)
    box('Luggage tie down recess',(2.08,side*.59,.60),(.095,.065,.018),black,cargo,.008)
    fixed=(1.77,side*.72,1.30);moving=(2.21,side*.70,1.12)
    length=(Vector(moving)-Vector(fixed)).length
    strut=part(f'tailgate_strut_{side}',('左' if side>0 else '右')+'尾门电动撑杆','body',fixed,(.38,side*.14,.35),.19,'tailgate_strut')
    strut['moving']=[moving[0],moving[2],-moving[1]]
    strut['hinge']=[TAILGATE_HINGE[0],TAILGATE_HINGE[2],-TAILGATE_HINGE[1]]
    strut['piston_length']=.45
    cylinder('Tailgate actuator barrel',(fixed[0],fixed[1],fixed[2]+.225),.014,.45,black,strut,'Z',32)
    piston=cylinder('Tailgate actuator piston',(fixed[0],fixed[1],fixed[2]+length-.225),.006,.45,alloy,strut,'Z',24);piston['strut_component']='piston'
    tip=cylinder('Tailgate actuator upper socket',(fixed[0],fixed[1],fixed[2]+length),.015,.026,black,strut,'Z',24);tip['strut_component']='tip'
    strut.rotation_euler=(Vector(moving)-Vector(fixed)).to_track_quat('Z','Y').to_euler()
tube('Rear valance pressed upper contour',[rear_point(y,z,.022) for y,z in [(-.68,.335),(-.48,.432),(.48,.432),(.68,.335)]],.004,black,rear_bumper)
for z in [.351,.389]:
    tube('Lower valance horizontal moulding',[rear_point(y,z,.021) for y in [-.57+1.14*i/48 for i in range(49)]],.003,black,rear_bumper)

# Visible cabin components are individually removable for the scroll explorer.
# The gray three-screen cockpit follows the user-supplied interior photograph.
def display_panel(name,x,y,z,width,height,group):
    box(name+' bezel',(x,y,z),(.026,width+.024,height+.024),screen_glass,group,.010)
    box(name+' surface',(x+.015,y,z),(.004,width,height),screen,group,.002)
    box(name+' violet lower field',(x+.0175,y,z-height*.27),(.001,width*.94,height*.34),screen_accent,group,0)
    for i in range(5):
        box(name+' status graphic',(x+.0185,y-width*.34+i*width*.17,z+height*.36),(.001,width*.075,.0035),screen_ui,group,0)
    for i in range(3):
        box(name+' lower control graphic',(x+.0185,y-width*.26+i*width*.26,z-height*.40),(.001,width*.12,.003),screen_ui,group,0)

dash=part('dashboard','仪表台与中控','cabin',(-.83,0,1.04),(-.2,0,.65),.3)
box('Dashboard upper padded panel',(-.84,0,1.035),(.38,1.54,.17),dash_soft,dash,.050)
box('Dashboard lower gray panel',(-.75,0,.925),(.27,1.43,.16),dash_lower,dash,.035)
box('Dashboard continuous black glass',(-.680,0,1.185),(.022,1.38,.195),screen_glass,dash,.010)
display_panel('Driver display',-.652,-.47,1.19,.34,.135,dash)
display_panel('Center display',-.585,0,1.215,.52,.285,dash)
display_panel('Passenger display',-.652,.45,1.185,.45,.165,dash)
for side in [-1,1]:
    box('Dashboard outer vent',(-.632,side*.665,1.18),(.025,.115,.145),screen_glass,dash,.010)
    for offset in [-.039,-.020,0,.020,.039]:
        box('Dashboard vertical vent vane',(-.615,side*.665+offset,1.18),(.010,.005,.105),steel,dash,.002)
    light_role(box('Dashboard ambient strip',(-.620,side*.40,1.048),(.012,.55,.008),ambient_light,dash,.003),'ambientLight')
    light_anchor('Dashboard ambient anchor',(-.20,side*.43,1.28),dash,'ambient')
box('Dashboard satin accent strip',(-.611,0,1.025),(.012,1.43,.014),alloy,dash,.004)
box('Center lower air vent',(-.586,0,.994),(.024,.39,.061),screen_glass,dash,.009)
for z in [.978,.994,1.010]:box('Center vent horizontal vane',(-.570,0,z),(.009,.34,.004),steel,dash,.001)
box('Hazard switch',(-.562,0,.994),(.006,.031,.016),reflector_red,dash,.002)
box('Glovebox lid',(-.600,.43,.912),(.025,.49,.105),dash_lower,dash,.014)
box('Glovebox release',(-.583,.43,.934),(.009,.072,.014),alloy,dash,.004)

steering=part('steering','方向盘','cabin',(-.5,-.47,1.08),(-.2,-.1,.7),.33)
cylinder('Steering column',(-.48,-.47,1.075),.040,.20,black,steering,'X',40)
wheel_outline=handle_outline(.32,.35,.105)
tube('Steering squircle rim',[(-.370,-.47+u,1.085+v) for u,v in wheel_outline],.0175,leather,steering,True)
for sy in [-1,1]:
    box('Steering horizontal spoke',(-.354,-.47+sy*.105,1.090),(.050,.120,.052),leather,steering,.016)
    box('Steering switch panel',(-.324,-.47+sy*.107,1.094),(.012,.065,.036),screen_glass,steering,.007)
    for dz in [-.009,.009]:box('Steering switch key',(-.316,-.47+sy*.107,1.094+dz),(.005,.036,.005),alloy,steering,.001)
box('Steering airbag hub',(-.345,-.47,1.075),(.065,.18,.145),leather,steering,.034)
vw_emblem(steering,(-.307,-.47,1.078),.024,(1,0,0),(0,1,0))

def seat_perforations(name,plane,center,width,height,group):
    vs=[];fs=[];columns=7;rows=9
    for row in range(rows):
        for column in range(columns):
            u=-width/2+(column+.5)*width/columns
            v=-height/2+(row+.5)*height/rows
            start=len(vs)
            for i in range(8):
                a=i/8*math.tau;du=.0016*math.cos(a);dv=.0016*math.sin(a)
                if plane=='back':vs.append((center[0],center[1]+u+du,center[2]+v+dv))
                else:vs.append((center[0]+u+du,center[1]+v+dv,center[2]))
            fs.append(tuple(start+i for i in range(8)))
    return mesh(name,vs,fs,group,door_seam)

for row,x in enumerate([-.15,.88]):
    for side in [-1,1]:
        y=side*.43
        p=part(f'seat_{row}_{side}',('前排' if row==0 else '后排')+('左座椅' if side>0 else '右座椅'),'cabin',(x,y,.6),(-.1 if row==0 else .15,side*.16,.65),.31)
        box('Seat base',(x,y,.64),(.55,.52,.16),leather,p,.060)
        box('Seat cushion insert',(x-.025,y,.713),(.46,.36,.048),leather,p,.022)
        box('Seat back',(x+.23,y,.98),(.15,.40,.54),leather,p,.050)
        box('Seat back insert',(x+.143,y,.985),(.025,.32,.41),leather,p,.011)
        box('Seat backing',(x+.315,y,.98),(.050,.47,.54),seat_dark,p,.025)
        for sy in [-1,1]:
            box('Seat cushion side bolster',(x-.005,y+sy*.215,.705),(.50,.078,.125),leather,p,.030)
            box('Seat back side bolster',(x+.205,y+sy*.210,.985),(.17,.076,.49),leather,p,.030)
            tube('Seat cushion stitched seam',[(x-.20+i*.38/24,y+sy*.145,.739) for i in range(25)],.0010,door_seam,p)
            tube('Seat back stitched seam',[(x+.128,y+sy*.130,.83+i*.31/24) for i in range(25)],.0010,door_seam,p)
        seat_perforations('Seat cushion perforated insert','base',(x-.025,y,.738),.32,.34,p)
        seat_perforations('Seat back perforated insert','back',(x+.129,y,.985),.28,.34,p)
        for sy in [-1,1]:cylinder('Head restraint post',(x+.23,y+sy*.072,1.245),.0055,.095,steel,p,'Z',20)
        box('Head restraint',(x+.23,y,1.315),(.14,.30,.17),leather,p,.042)
        box('Seat belt buckle stem',(x+.16,y-side*.267,.715),(.040,.026,.095),black,p,.009)
        box('Seat belt buckle release',(x+.16,y-side*.267,.765),(.027,.028,.018),reflector_red,p,.004)

console=part('center_console','中央扶手','cabin',(0,0,.7),(0,0,.4),.32)
box('Console',(-.02,0,.720),(1.12,.30,.30),console_trim,console,.045)
box('Console charging pad',(-.37,0,.878),(.25,.25,.020),seat_dark,console,.009)
box('Console charging pad marking',(-.37,0,.890),(.085,.11,.004),dash_lower,console,.002)
box('Console center seam',(.20,0,.882),(.64,.007,.014),black,console,.003)
for sy in [-1,1]:
    box('Split armrest lid',(.20,sy*.074,.895),(.64,.137,.052),console_trim,console,.020)
box('Console front sliding tray',(-.135,0,.884),(.17,.255,.028),leather,console,.012)
lidar=part('lidar','车顶激光雷达','body',(-.33,0,1.625),(0,0,2.0),.23)
# A low teardrop dome is entirely on the fixed front header, clear of the sliding glass.
def lidar_point(a,r,height):
    x=-.345+.100*r*math.cos(a);y=.150*r*math.sin(a)*(.80-.20*math.cos(a))
    base=roof_z(max(-.32,x))+.022*(1-(y/roof_w(-.32))**2)
    return (x,y,base+height)
vs=[];fs=[];n=96
profile=[(1,.003),(1.015,.009),(.995,.016),(.90,.025),(.65,.034),(.28,.037),(0,.038)]
for r,h in profile:
    for i in range(n):vs.append(lidar_point(i/n*math.tau,r,h))
for j in range(len(profile)-1):
    for i in range(n):
        k=j*n+i;q=j*n+(i+1)%n;fs.append((k,q,q+n,k+n))
mesh('Roof sensor low crowned teardrop shell',vs,fs,lidar,mirror_cap)
tube('Roof sensor perimeter seal',[lidar_point(i/n*math.tau,1.01,.005) for i in range(n)],.0014,sensor_black,lidar,True)
vs=[];fs=[]
for i in range(49):
    a=math.pi*.64+math.pi*.72*i/48
    for height in [.012,.027]:vs.append(lidar_point(a,1.004,height))
    if i:fs.append((2*i-2,2*i,2*i+1,2*i-1))
mesh('Roof sensor curved front optic',vs,fs,lidar,sensor_optic,.001)
box('Roof sensor front camera recess',(-.447,0,1.650),(.004,.112,.022),sensor_black,lidar,.002)
box('Roof sensor front camera glass',(-.450,0,1.650),(.003,.077,.014),sensor_optic,lidar,.001)
cylinder('Roof sensor front camera lens',(-.453,0,1.650),.006,.003,sensor_optic,lidar,'X',32)

cable=part('charge_cable','充电枪','body',motion='cable')
cable['part']=False;cable['effect']='cable'
tube('Charge cable',[(1.74,.99,1.0),(1.9,1.3,.7),(1.95,1.65,.05),(1.3,1.95,.025),(.6,1.98,.025)],.022,black,cable)
box('Charge connector',(1.74,1.0,.99),(.14,.21,.09),black,cable,.028)
air=part('airflow','空调气流','cabin',motion='airflow')
air['part']=False;air['effect']='airflow'
for side in [-1,0,1]:
    for dz in [0,.035,.07]:tube('Vent airflow',[(-.6,side*.4,1.13+dz),(-.35,side*.4,1.17+dz),(-.05,side*.4,1.13+dz)],.003,screen,air)

# Emit small cabin details after the exterior Boolean work and verify them before export.
for group in parts:
    if group.get('motion')!='door':continue
    _,side_text,index_text=group.name.split('_');side=int(side_text);index=int(index_text)
    x0,x1=[(-1.008,.184),(.188,1.230)][index];lining_end=min(x1,1.0)
    cylinder('Door lower speaker grille',(lining_end-.13,side*.779,.54),.062,.008,seat_dark,group,'Y',48)
assert sum(child.name.startswith('Door lower speaker grille') for group in parts for child in group.children_recursive)==4
assert bpy.data.objects.get('Front storage tub floor') is not None
assert bpy.data.objects.get('Charge port deep recessed housing') is not None
print('BUILD_STAGE references',flush=True)

# Keep the public reference images as Blender-only image empties, excluded from GLB.
refs=bpy.data.collections.new('Reference images — not exported')
bpy.context.scene.collection.children.link(refs)
for i,path in enumerate(sorted(p for p in (SOURCE/'references').rglob('*') if p.suffix in {'.jpg','.png'})):
    obj=bpy.data.objects.new(path.stem,None)
    obj.empty_display_type='IMAGE'
    obj.data=bpy.data.images.load(str(path),check_existing=True)
    obj.data.pack()
    obj.empty_display_size=5
    obj.location=(8,i*3,2)
    obj.hide_render=True
    refs.objects.link(obj)
refs.hide_viewport=True
refs.hide_render=True

scene=bpy.context.scene
scene['model']='ID. AURA T6 — exterior reference reconstruction'
scene['source']='https://www.vw.com.cn/BrandCarModel.html?source=AURAT6'
scene['accuracy']='Approximate exterior; schematic interior and running gear; not OEM CAD'
# Export only the articulated model; metadata is read directly by the browser.
bpy.ops.object.select_all(action='DESELECT')
for p in parts:
    p.select_set(True)
    for child in p.children_recursive:child.select_set(True)
bpy.context.view_layer.objects.active=parts[0]
bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE/'aura-t6.blend'))
bpy.ops.export_scene.gltf(filepath=str(OUT/'aura-t6.glb'),export_format='GLB',use_selection=True,export_extras=True,export_yup=True,export_apply=True,export_cameras=False,export_lights=False)
report={'model':'ID. AURA T6','parts':sum(bool(p.get('part')) for p in parts),'source':scene['source'],'accuracy':scene['accuracy'],'generator':'Blender '+bpy.app.version_string}
(OUT/'aura-t6.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('AURA_EXPORT',json.dumps(report,ensure_ascii=False))
