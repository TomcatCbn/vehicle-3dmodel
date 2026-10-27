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
indicator_lens = mat('Mirror indicator clear ribs', (.29,.33,.35), .12,.19)
mirror_glass = mat('Mirror reflective glass', (.38,.45,.48), .98,.07)
sensor_optic = mat('Sensor optical glass', (.008,.015,.020), .08,.09)
sensor_optic.node_tree.nodes.get('Principled BSDF').inputs['Coat Weight'].default_value=.8
sensor_optic.node_tree.nodes.get('Principled BSDF').inputs['Transmission Weight'].default_value=.18
glass = mat('Glazing', (.045,.075,.095), .0,.08)
alloy = mat('Machined alloy', (.56,.62,.65), .88,.24)
steel = mat('Structural steel', (.12,.16,.18), .7,.42)
leather = mat('Ivory upholstery', (.58,.57,.49), 0,.85)
seat_dark = mat('Seat backs', (.075,.085,.077), 0,.7)
led = mat('Daylight LED', (.78,.94,1), .2,.22, 3)
red = mat('Rear light LED', (.8,.018,.025), .1,.25, 2)
reflector_red = mat('Red reflector', (.35,.008,.012), .1,.24)
cell = mat('Battery modules', (.29,.49,.37), .55,.4)
screen = mat('Display', (.14,.34,.33), .4,.18,.3)
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

def vw_emblem(group,center,radius,normal,right):
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
        obj=mesh('VW solid '+name+' face',vs,fs,group,badge_silver)
        for face in obj.data.polygons:face.use_smooth=False
        bevel=obj.modifiers.new('Minute machined edge','BEVEL');bevel.width=radius*.004;bevel.segments=2;bevel.limit_method='ANGLE'
        obj.modifiers.new('Flat graphic normals','WEIGHTED_NORMAL')

def badge(group,x,z,rear=False):
    surface=rear_surface if rear else front_surface
    slope=(surface(0,z+.0001)[0]-surface(0,z-.0001)[0])/.0002
    normal=Vector((1 if rear else -1,0,-slope if rear else slope)).normalized()
    vw_emblem(group,Vector((x,0,z))+normal*.003,.064,normal,(0,1 if rear else -1,0))

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
    for side in [-1,1]:tube('Wishbone',[(x-.18,side*.35,.29),(x,side*.81,.37),(x+.18,side*.35,.29)],.027,steel,chassis)
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
        box('Inner door lining',((x0+lining_end)/2,side*.815,.73),(lining_end-x0-.04,.035,.58),seat_dark,p,.03)
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
        side_skin('Curved wheel fender',x0,x1,side,p,True)
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
        if not front:
            flap_y=side_width(1.74,.945)+.005
            box('Charge flap',(1.74,side*flap_y,.945),(.235,.006,.17),paint,p,.025)
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
    # Two continuous shells share the indicator seam; the rear opening carries a mirror face.
    mirror_sections=[(-1.005,.002,.002),(-.992,.060,.028),(-.960,.109,.052),(-.90,.139,.068),(-.82,.140,.066),(-.735,.117,.047)]
    mirror_w=section([(x,w) for x,w,h in mirror_sections]);mirror_h=section([(x,h) for x,w,h in mirror_sections])
    def mirror_point(x,a,extra=0):
        c=math.cos(a);sn=math.sin(a)
        return (x,side*(1.047+(mirror_w(x)+extra)*math.copysign(abs(c)**.82,c)),1.151+.022*(x+.9)+(mirror_h(x)+extra)*math.copysign(abs(sn)**.82,sn)*(1 if sn>=0 else .65))
    for name,begin,material in [('Mirror upper crowned shell',0,mirror_cap),('Mirror lower satin shell',math.pi,sensor_black)]:
        vs=[];fs=[];nx=56;na=32
        for i in range(nx+1):
            x=-1.005+.270*i/nx
            for j in range(na+1):vs.append(mirror_point(x,begin+math.pi*j/na))
        for i in range(nx):
            for j in range(na):
                k=i*(na+1)+j;face=(k,k+na+1,k+na+2,k+1)
                fs.append(face if side<0 else tuple(reversed(face)))
        mesh(name,vs,fs,mirror,material,.002)
    stem=[(-.96,side*.895,1.112),(-.79,side*.909,1.096),(-.76,side*1.038,1.115),(-.91,side*1.062,1.126),
          (-.96,side*.895,1.148),(-.79,side*.909,1.125),(-.76,side*1.038,1.146),(-.91,side*1.062,1.153)]
    mesh('Mirror sculpted mounting foot',stem,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],mirror,sensor_black,bevel=.012)
    # Glass occupies the rear-facing opening instead of a thick rectangular block.
    vs=[(-.730,side*1.047,1.151)];outline=[]
    for i in range(96):
        a=i/96*math.tau;q=Vector(mirror_point(-.735,a));q.x=-.731
        q.y=side*1.047+(q.y-side*1.047)*.94;q.z=1.151+(q.z-1.151)*.91
        outline.append(tuple(q))
    vs+=outline;faces=[(0,i+1,(i+1)%96+1) for i in range(96)]
    mesh('Mirror reflective glass',vs,[tuple(reversed(f)) for f in faces] if side<0 else faces,mirror,mirror_glass)
    tube('Mirror glass perimeter gasket',outline,.0022,sensor_black,mirror,True)
    seam=[mirror_point(-1.0+.252*i/64,0,.001) for i in range(65)]
    tube('Mirror indicator dark channel',seam,.0034,sensor_black,mirror)
    tube('Mirror indicator clear light guide',seam,.0019,indicator_lens,mirror)
    for i in range(62):
        x=-.987+.237*i/61;q=Vector(mirror_point(x,0,.0028))
        tube('Mirror indicator prism rib',[tuple(q+Vector((0,0,-.002))),tuple(q+Vector((0,0,.002)))],.00035,indicator_lens,mirror)
    merge_static_details(mirror,'Mirror indicator prism rib',indicator_lens)
    cylinder('Mirror underside camera socket',(-.88,side*1.13,1.116),.012,.006,sensor_black,mirror,'Z',40)
    cylinder('Mirror underside camera lens',(-.88,side*1.13,1.112),.0078,.002,sensor_optic,mirror,'Z',40)
    ring('Mirror underside camera bezel',(-.88,side*1.13,1.112),.0095,black,mirror,'Z',.0008)
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
        # Individual letters follow the sidewall crown; no unverified tire size is shown.
        for content,angle0,r,size,spacing in [('Hankook',.18,.331,.021,.043),('iON',-1.45,.330,.019,.042),('OUTSIDE',2.0,.309,.008,.024),('EV',-2.63,.329,.010,.028)]:
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
            for offset in [-.0035,.0035]:
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
            for rib in range(9):
                da=-.133+rib*.03325
                inner=.189+.040*abs(da)/.15
                tube('Aero insert rib',[(x+r*math.cos(a+da),side*.951,.37+r*math.sin(a+da)) for r in [inner,.232,.240]],.0010,black,rim)
            tube('Aero insert machined outer arc',[(x+.247*math.cos(a+da),side*.955,.37+.247*math.sin(a+da)) for da in [-.14+.28*i/20 for i in range(21)]],.0018,alloy,rim)
        cylinder('Hub',(x,side*.915,.37),.049,.025,black,rim)
        vw_emblem(rim,(x,side*.929,.37),.0275,(0,side,0),(-side,0,0))
        for bolt in range(5):
            a=bolt/5*math.tau
            cylinder('Wheel fastener recess',(x+.063*math.cos(a),side*.918,.37+.063*math.sin(a)),.011,.004,black,rim,vertices=20)
            cylinder('Wheel fastener',(x+.063*math.cos(a),side*.922,.37+.063*math.sin(a)),.0065,.007,alloy,rim,vertices=12)
        merge_static_details(rim,'Aero insert rib',black)
        cylinder('Tire valve rubber stem',(x,side*.947,.37+.230),.0036,.012,rubber,rim,vertices=16)
        cylinder('Tire valve dust cap',(x,side*.956,.37+.230),.0045,.006,black,rim,vertices=16)
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
        box('Brake caliper',(x+.15,side*.88,.37),(.065,.06,.16),black,brake,.018)

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

bay=part('front_service_bay','前舱检修盖板','body',offset=(-.25,0,.46),start=.17)
outline=rounded_outline([(-2.18,-.70,.988),(-2.00,-.83,.988),(-1.16,-.81,1.045),(-1.08,-.65,1.061),(-1.08,.65,1.061),(-1.16,.81,1.045),(-2.00,.83,.988),(-2.18,.70,.988)],.065)
vs=[(-1.64,0,.92),*outline]
polymer_uv(mesh('Front bay moulded perimeter tray',vs,[(0,i+1,(i+1)%len(outline)+1) for i in range(len(outline))],bay,service_tray,.012))
tube('Continuous front compartment weather seal',outline,.010,rubber,bay,True)
# A wide closed service panel follows the visible cover in the photo; it is not a frunk.
vs=[];fs=[];n=128;profiles=[(1,.957),(.99,.981),(.96,.996),(.87,1.006),(.55,1.009),(0,1.010)]
for scale,z in profiles:
    for i in range(n):
        a=i/n*math.tau
        x=-1.64+scale*.435*math.copysign(abs(math.cos(a))**.5,math.cos(a))
        y=scale*.696*math.copysign(abs(math.sin(a))**.5,math.sin(a))
        vs.append((x,y,z))
for j in range(len(profiles)-1):
    for i in range(n):
        k=j*n+i;l=j*n+(i+1)%n;fs.append((k,l,l+n,k+n))
polymer_uv(mesh('Broad sealed service access cover',vs,fs,bay,service_plastic))
cover_ring=[(-1.64+.43*math.copysign(abs(math.cos(i/n*math.tau))**.5,math.cos(i/n*math.tau)),.69*math.copysign(abs(math.sin(i/n*math.tau))**.5,math.sin(i/n*math.tau)),.978) for i in range(n)]
tube('Service cover perimeter joint',cover_ring,.0035,black,bay,True)
tube('Service cover upper moulded bead',[(x*.94+(-1.64)*.06,y*.94,1.003) for x,y,z in cover_ring],.004,service_plastic,bay,True)
box('Maintenance key recessed well',(-1.62,-.32,1.010),(.115,.35,.008),well_liner,bay,.025)
tube('Service key handle',[(-1.65,-.45,1.018),(-1.65,-.21,1.018),(-1.60,-.19,1.018),(-1.59,-.21,1.018)],.006,black,bay)
for x in [-2.08,-1.15]:
    for y in [-.67,0,.67]:
        cylinder('Service tray captive fastener',(x,y,.994 if x<-2 else 1.049),.011,.005,black,bay,'Z',24)
box('Washer neck plinth',(-1.86,-.716,1.003),(.095,.10,.025),black,bay,.014)
cylinder('Washer reservoir filler neck',(-1.86,-.716,1.014),.031,.032,white,bay,'Z',40)
cylinder('Blue washer fluid filler cap',(-1.86,-.716,1.033),.038,.009,washer_blue,bay,'Z',64)
box('Washer cap finger tab',(-1.893,-.716,1.035),(.025,.048,.009),washer_blue,bay,.004)
tube('Washer symbol windscreen',[(-1.875,-.733,1.039),(-1.855,-.737,1.039),(-1.845,-.716,1.039),(-1.855,-.695,1.039),(-1.875,-.699,1.039)],.001,white,bay)
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
        mesh(name,vs,fs,lightbar,bar_led)
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
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,location=lp(-.015,.035,dz))
        lens=bpy.context.object;lens.name='Upper projection lens' if dz>0 else 'Lower projection lens'
        lens.scale=(.009,.022,.021 if dz>0 else .015)
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);parent(lens,lamp,optic)
        if dz<0:
            for dy in [-.014,-.005,.005,.014]:
                tube('Lower collimator facet',[lp(-.022,.035+dy,dz-.010),lp(-.024,.035+dy,dz+.010)],.0008,lamp_chrome,lamp)
    box('Inboard rectangular optical chamber',lp(.002,-.041,.021),(.020,.063,.084),black,lamp,.010)
    inner=rounded_outline([lp(-.011,y,z) for y,z in [(-.066,-.004),(-.017,-.009),(-.017,.050),(-.066,.057)]],.009)
    tube('Inboard rectangular reflector frame',inner,.0018,lamp_chrome,lamp,True)
    box('Inboard rectangular projector',lp(-.012,-.042,.023),(.005,.030,.025),optic,lamp,.003)
    for dy in [-.009,-.003,.003,.009]:
        tube('Rectangular optic micro rib',[lp(-.015,-.042+dy,.014),lp(-.015,-.042+dy,.032)],.0005,lamp_chrome,lamp)
    blade=[lp(-.010,y,z) for y,z in [(-.071,-.082),(-.018,-.062),(.057,-.076),(-.017,-.087)]]
    mesh('Swept lower reflector blade',blade,[(0,1,2,3)],lamp,lamp_chrome,.001)
    text_label('IQ.LIGHT',lp(-.024,.033,.008),.007,lamp)
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

windscreen=part('windscreen','前挡风玻璃','cabin',offset=(-.45,0,1.2),start=.18)
loft('Curved windscreen',[(-1.025,1.103,.868),(-.86,1.265,.825),(-.60,1.475,.780),(-.32,1.60,.740)],windscreen,glass,.022,0)
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
box('High mounted stop lamp',(1.983,0,1.517),(.010,.52,.008),red,spoiler,.003)
box('Rear upper camera housing',(1.94,0,1.499),(.042,.078,.029),black,spoiler,.012)
cylinder('Rear upper camera lens',(1.966,0,1.499),.010,.005,glass,spoiler,'X',24)
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
cylinder('Rear wiper pivot',wiper_point(.11,1.195),.022,.016,black,rear_glass,'X',24)
tube('Rear wiper arm',[wiper_point(.11,1.195),wiper_point(-.12,1.19),wiper_point(-.26,1.18)],.007,black,rear_glass)
tube('Rear wiper blade',[wiper_point(y,1.183,.020) for y in [-.31+.41*i/24 for i in range(25)]],.009,black,rear_glass)
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
rear_lights=part('tail_lights','后贯穿尾灯','body',TAILGATE_HINGE,(1.18,0,.27),.12,'tailgate')
rear_led=mat('Rear fine light guide LED',(.42,.004,.008),0,.3,1.3)
rear_optic=mat('Rear ruby optical chamber',(.085,.002,.004),.15,.23)
rear_lens=lamp_glass.copy();rear_lens.name='Rear smoked optical cover'
rear_lens.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.030,.018,.022,1)
rear_lens.node_tree.nodes.get('Principled BSDF').inputs['Transmission Weight'].default_value=.64

def rear_band(group,side=None):
    def y_value(u,z):
        if side is None:return u*(tailgate_width(z)-.002)
        q=(u+1)/2
        return side*((tailgate_width(z)+.002)*(1-q)+(rear_width(z)-.002)*q)
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
    vs=[];fs=[];ny=80
    for z in [1.0585,1.0645]:
        for i in range(ny+1):
            u=i/ny*2-1;y=y_value(u,z)
            vs.append(rear_point(y,z,.009))
    for i in range(ny):
        # The emblem covers the central gap in the light guide.
        if side is None and abs(vs[i][1])<.075:continue
        face=(i,i+1,i+ny+2,i+ny+1)
        fs.append(face if side is None or side>0 else tuple(reversed(face)))
    mesh('Single slim red rear light guide',vs,fs,group,rear_led,.001)
    for z0,z1,name,material in [(1.083,1.096,'Ruby upper tail lamp chamber',rear_optic),(1.032,1.036,'Lower tail lamp separator',black)]:
        vs=[];fs=[]
        for z in [z0,z1]:
            for i in range(ny+1):
                y=y_value(i/ny*2-1,z);vs.append(rear_point(y,z,.0095))
        for i in range(ny):fs.append((i,i+1,i+ny+2,i+ny+1) if side is None or side>0 else (i+ny+1,i+ny+2,i+1,i))
        mesh(name,vs,fs,group,material)

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
            t=i/n;scale=smoothstep(0,.22,t);z=1.067+(-.0055+row*.003)*scale
            x,w,_=side_surface(1.82+.48*t,z,'rear');vs.append((x,side*(w+.010),z))
    for i in range(n):
        face=(i,i+1,i+n+2,i+n+1);fs.append(face if side<0 else tuple(reversed(face)))
    mesh('Single tapered side rear light guide',vs,fs,outer,rear_led,.001)

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
dash=part('dashboard','仪表台与中控','cabin',(-.83,0,1.04),(-.2,0,.65),.3)
box('Dashboard',(-.83,0,1.04),(.35,1.52,.17),black,dash,.055)
box('Center display',(-.63,0,1.19),(.023,.42,.25),black,dash,.015)
box('Display surface',(-.614,0,1.19),(.006,.39,.22),screen,dash,.005)
box('Driver display',(-.74,.46,1.16),(.04,.3,.12),black,dash,.015)
steering=part('steering','方向盘','cabin',(-.5,.47,1.08),(-.2,.1,.7),.33)
ring('Steering wheel',(-.5,.47,1.08),.13,black,steering,'X',.018)
box('Steering center',(-.49,.47,1.07),(.055,.11,.065),black,steering,.015)
for row,x in enumerate([-.15,.88]):
    for side in [-1,1]:
        p=part(f'seat_{row}_{side}',('前排' if row==0 else '后排')+('左座椅' if side>0 else '右座椅'),'cabin',(x,side*.43,.6),(-.1 if row==0 else .15,side*.16,.65),.31)
        box('Seat base',(x,side*.43,.64),(.55,.52,.16),leather,p,.07)
        box('Seat back',(x+.23,side*.43,.93),(.15,.51,.58),leather,p,.065)
        box('Seat backing',(x+.29,side*.43,.93),(.07,.48,.51),seat_dark,p,.03)
        box('Head restraint',(x+.23,side*.43,1.29),(.13,.29,.17),leather,p,.045)
        for sy in [-1,1]:box('Seat side bolster',(x,side*.43+sy*.22,.7),(.46,.07,.12),leather,p,.03)
console=part('center_console','中央扶手','cabin',(0,0,.7),(0,0,.4),.32)
box('Console',(.03,0,.71),(.83,.25,.24),black,console,.05)
box('Arm rest',(.25,0,.86),(.36,.25,.065),leather,console,.03)
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

cable=part('charge_cable','充电枪','body',motion='cable')
cable['part']=False;cable['effect']='cable'
tube('Charge cable',[(1.74,.99,1.0),(1.9,1.3,.7),(1.95,1.65,.05),(1.3,1.95,.025),(.6,1.98,.025)],.022,black,cable)
box('Charge connector',(1.74,1.0,.99),(.14,.21,.09),black,cable,.028)
box('Charge indicator',(1.74,1.025,1.04),(.08,.12,.01),led,cable,.004)
air=part('airflow','空调气流','cabin',motion='airflow')
air['part']=False;air['effect']='airflow'
for side in [-1,0,1]:
    for dz in [0,.035,.07]:tube('Vent airflow',[(-.6,side*.4,1.13+dz),(-.35,side*.4,1.17+dz),(-.05,side*.4,1.13+dz)],.003,screen,air)

# Keep the public reference images as Blender-only image empties, excluded from GLB.
refs=bpy.data.collections.new('Reference images — not exported')
bpy.context.scene.collection.children.link(refs)
for i,path in enumerate(sorted(p for p in (SOURCE/'references').iterdir() if p.suffix in {'.jpg','.png'})):
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
