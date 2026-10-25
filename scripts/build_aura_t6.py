"""Create an independently articulated AURA T6 exterior reference model, not OEM CAD.
Run: blender --background --python scripts/build_aura_t6.py
"""
import bpy
import math
import json
import sys
from pathlib import Path
from mathutils import Vector, Matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).resolve().parent))
from aura_surface import (belt_height, side_width, front_width, front_surface,
                          rear_width, rear_surface, side_surface, grille_top, smoothstep, section)
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

paint = mat('Paint', (.055,.22,.18), .65,.23)
black = mat('Obsidian trim', (.012,.018,.022), .35,.32)
rubber = mat('Tire rubber', (.015,.017,.019), 0,.88)
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
lamp_glass.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.25,.30,.35,1)
lamp_glass.node_tree.nodes.get('Principled BSDF').inputs['Transmission Weight'].default_value=.9
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

def badge(group,x,z,rear=False):
    normal=1 if rear else -1
    cylinder('VW badge backing',(x,0,z),.071,.012,black,group,'X')
    ring('VW roundel',(x+normal*.008,0,z),.063,white,group,'X',.004)
    for shape in [[(-.030,.034),(0,.001),(.030,.034)],[(-.042,.019),(-.022,-.034),(0,-.006),(.022,-.034),(.042,.019)]]:
        tube('VW lettering',[(x+normal*.012,y,z+dz) for y,dz in shape],.004,white,group)

def text_label(text,location,size,group,rear=False):
    bpy.ops.object.text_add(location=location)
    obj=bpy.context.object
    obj.name='Badge '+text
    obj.data.body=text
    obj.data.size=size
    obj.data.align_x='CENTER'
    obj.data.align_y='CENTER'
    obj.data.extrude=.0005
    matrix=Matrix(((0,0,1),(1,0,0),(0,1,0))) if rear else Matrix(((0,0,-1),(-1,0,0),(0,1,0)))
    obj.rotation_euler=matrix.to_euler()
    bpy.ops.object.convert(target='MESH')
    return parent(obj,group,white)

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
        side_skin('Sculpted door skin',x0,x1,side,p,arches=index==1)
        lining_end=min(x1,1.0)
        box('Inner door lining',((x0+lining_end)/2,side*.815,.73),(lining_end-x0-.04,.035,.58),seat_dark,p,.03)
        handle_x=x1-.21
        handle_y=side_width(handle_x,.98)+.009
        box('Semi recessed handle',(handle_x,side*handle_y,.98),(.18,.018,.032),black,p,.012)
        box('Handle lip',(handle_x,side*(handle_y+.010),.993),(.165,.010,.012),paint,p,.005)
        cladding_vs=[];cladding_fs=[]
        for j in range(7):
            for i in range(49):
                x=x0+(min(x1,1.01)-x0)*i/48
                height=.008+.112*smoothstep(-1.01,-.62,x)*(1-smoothstep(.91,1.22,x))
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
        plate=[(wx,side*.714,.37)]+[(wx+.405*math.cos(i/128*math.tau),side*.714,max(.05,.37+.405*math.sin(i/128*math.tau))) for i in range(128)]
        mesh('Wheel well rear liner',plate,[(0,i+1,(i+1)%128+1) for i in range(128)],p,well_liner)
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
    mesh('Quarter lower shoulder',[(1.235,side*.869,belt_height(1.235)),(1.61,side*.864,1.15),(2.05,side*.855,1.105),(1.75,side*side_width(1.75,belt_height(1.75)),belt_height(1.75))],[(0,1,3),(1,2,3)],pillar_c,paint,.008)
    d_vs=[];d_fs=[];n=16
    lower_left=Vector(qpts[3]);lower_right=Vector((2.05,side*.855,1.105))
    upper_left=Vector(qpts[2]);upper_right=Vector((1.72,side*.779,1.50))
    for j in range(n+1):
        v=j/n
        for i in range(n+1):
            u=i/n
            p=(lower_left*(1-u)+lower_right*u)*(1-v)+(upper_left*(1-u)+upper_right*u)*v
            p.y+=side*.035*math.sin(u*math.pi)*math.sin(v*math.pi)
            d_vs.append(tuple(p))
    for j in range(n):
        for i in range(n):
            k=j*(n+1)+i
            d_fs.append((k,k+1,k+n+2,k+n+1) if side<0 else (k,k+n+1,k+n+2,k+1))
    mesh('Swept rear D pillar',d_vs,d_fs,pillar_c,paint,.008)
    mirror=part(f'mirror_{side}',label+'后视镜','body',(-.87,side*.99,1.12),(-.15,side*1.3,.25),.1)
    tube('Mirror stem',[(-.96,side*.88,1.11),(-.87,side*1.015,1.13)],.020,black,mirror,smooth=True)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=40,ring_count=20,location=(-.85,side*1.04,1.15))
    housing=bpy.context.object;housing.name='Streamlined mirror housing';housing.scale=(.145,.091,.056)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);parent(housing,mirror,black)
    box('Mirror glass',(-.715,side*1.04,1.153),(.009,.132,.065),alloy,mirror,.018)
    tube('Mirror indicator',[(-.97,side*1.01,1.146),(-.955,side*1.09,1.146),(-.89,side*1.126,1.146)],.0025,white,mirror,smooth=True)
    vent=part(f'side_vent_{side}',label+'前侧饰条','body',(-1.06,side*.944,1.01),(-.2,side*.55,.12),.1)
    box('Fender blade',(-1.08,side*.945,1.01),(.22,.014,.05),black,vent,.015)
    cylinder('Fender camera',(-1.08,side*.956,1.012),.014,.011,black,vent,vertices=24)
    cylinder('Fender camera lens',(-1.08,side*.963,1.012),.008,.004,glass,vent,vertices=24)
    # Wheels are true tire profiles, separately exploded from rims and brakes.
    for x in [-1.418,1.418]:
        position=(x,side*.817,.37)
        p=part(f'tire_{side}_{x}',label+('前轮胎' if x<0 else '后轮胎'),'chassis',position,(0,side*1.65,0),.36)
        profile=[(-.115,.255),(-.125,.28),(-.112,.335),(-.08,.366),(-.045,.372),(.045,.372),(.08,.366),(.112,.335),(.125,.28),(.115,.255)]
        vs=[];fs=[];n=192
        for dy,r in profile:
            for k in range(n):
                a=k/n*math.tau;vs.append((x+r*math.cos(a),side*.817+dy,.37+r*math.sin(a)))
        for j in range(len(profile)-1):
            for k in range(n):
                a=j*n+k;b=j*n+(k+1)%n;fs.append((a,b,b+n,a+n))
        mesh('Touring tire',vs,fs,p,rubber)
        for dy in [-.065,-.025,.025,.065]:ring('Tread channel',(x,side*.817+dy,.37),.371,black,p,wire=.002)
        for r in [.29,.326,.34]:ring('Sidewall moulding',(x,side*.936,.37),r,rubber,p,wire=.0018)
        for k in range(96):
            a=k/96*math.tau
            pts=[]
            for dy in [-.08,0,.08]:
                aa=a+.035*(1-abs(dy)/.08)
                pts.append((x+.371*math.cos(aa),side*.817+dy,.37+.371*math.sin(aa)))
            tube('Fine tread sipe',pts,.0012,black,p)
        for content,dz,size in [('TOURING',.318,.013),('235 / 50 R20',-.326,.011)]:
            bpy.ops.object.text_add(location=(x,side*.940,.37+dz))
            lettering=bpy.context.object;lettering.name='Raised tire specification';lettering.data.body=content
            lettering.data.size=size;lettering.data.align_x='CENTER';lettering.data.align_y='CENTER';lettering.data.extrude=.0004
            lettering.rotation_euler=Matrix(((-side,0,0),(0,0,side),(0,1,0))).to_euler()
            bpy.ops.object.convert(target='MESH');parent(lettering,p,rubber)
        merge_static_details(p,'Fine tread sipe',black)
        rim_y=side*.932
        rim=part(f'rim_{side}_{x}',label+('前轮毂' if x<0 else '后轮毂'),'chassis',(x,rim_y,.37),(0,side*1.2,0),.43)
        wheel_lathe('Open alloy wheel barrel',x,side,[(-.09,.228),(.106,.228),(.13,.239),(.14,.250),(.137,.258),(.119,.260),(-.09,.260),(-.09,.228)],rim,black)
        wheel_lathe('Machined rim flange',x,side,[(.138,.244),(.140,.250),(.137,.256)],rim,alloy)
        ring('Polished outer lip',(x,side*.955,.37),.250,alloy,rim,wire=.003)
        ring('Recessed barrel edge',(x,side*.895,.37),.224,black,rim,wire=.004)
        for k in range(5):
            angle=k/5*math.tau+math.pi/2
            pts=[]
            outline=[(.055,-.40),(.135,-.32),(.224,-.50),(.250,-.45),(.250,-.20),(.181,0),(.250,.20),(.250,.45),(.224,.50),(.135,.32),(.055,.40)]
            for r,delta in outline:
                a=angle+delta
                depth=.091+.042*(r/.25)**2
                pts.append((x+r*math.cos(a),side*(.817+depth),.37+r*math.sin(a)))
            face=tuple(range(len(pts)))
            mesh('Sculpted split aero spoke',pts,[face if side<0 else tuple(reversed(face))],rim,black,.024,.003)
            center=sum((Vector(p) for p in pts),Vector())/len(pts)
            border=[]
            for scale in [1,.82]:
                for p in pts:
                    q=center+(Vector(p)-center)*scale
                    r=math.hypot(q.x-x,q.z-.37);q.y=side*(.817+.091+.042*(r/.25)**2+.003)
                    border.append(tuple(q))
            count=len(pts)
            faces=[(i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count)]
            mesh('Diamond cut concave spoke face',border,faces if side<0 else [tuple(reversed(f)) for f in faces],rim,alloy,.0015)
            a=angle+math.pi/5
            insert=[(x+r*math.cos(a+da),side*.899,.37+r*math.sin(a+da)) for r,da in [(.16,-.10),(.235,-.16),(.235,.16),(.16,.10)]]
            mesh('Recessed aero insert',insert,[(0,1,2,3)],rim,black,.006,.002)
            for rib in range(7):
                a=angle+math.pi/5-.12+rib*.04
                tube('Aero insert rib',[(x+r*math.cos(a),side*.902,.37+r*math.sin(a)) for r in [.17,.20,.231]],.0013,steel,rim)
        cylinder('Hub',(x,side*.915,.37),.049,.025,black,rim)
        ring('Hub detail',(x,side*.930,.37),.027,alloy,rim,wire=.002)
        for shape in [[(-.014,.015),(0,.0005),(.014,.015)],[(-.018,.008),(-.009,-.015),(0,-.003),(.009,-.015),(.018,.008)]]:
            tube('Wheel VW lettering',[(x+dx,side*.933,.37+dz) for dx,dz in shape],.0018,white,rim)
        for bolt in range(5):
            a=bolt/5*math.tau
            cylinder('Wheel fastener recess',(x+.063*math.cos(a),side*.918,.37+.063*math.sin(a)),.011,.004,black,rim,vertices=20)
            cylinder('Wheel fastener',(x+.063*math.cos(a),side*.922,.37+.063*math.sin(a)),.0065,.007,alloy,rim,vertices=12)
        merge_static_details(rim,'Aero insert rib',steel)
        brake=part(f'brake_{side}_{x}',label+('前制动盘' if x<0 else '后制动盘'),'chassis',(x,side*.87,.37),(0,side*.75,0),.48)
        cylinder('Brake disc',(x,side*.87,.37),.195,.025,steel,brake)
        ring('Rotor edge',(x,side*.884,.37),.192,alloy,brake,wire=.0015)
        holes_vs=[];holes_fs=[]
        for k in range(24):
            a=k/24*math.tau
            for r in [.153,.178]:
                center=Vector((x+r*math.cos(a),side*.884,.37+r*math.sin(a)));start=len(holes_vs)
                holes_vs.append(tuple(center))
                for i in range(12):
                    angle=i/12*math.tau;holes_vs.append(tuple(center+Vector((.003*math.cos(angle),0,.003*math.sin(angle)))))
                holes_fs.extend((start,start+i+1,start+(i+1)%12+1) for i in range(12))
        mesh('Rotor perforation details',holes_vs,holes_fs,brake,black)
        box('Brake caliper',(x+.15,side*.88,.37),(.065,.06,.16),black,brake,.018)

hood=part('hood','前舱盖','body',offset=(-.85,0,.95),start=.05)
hood_vs=[];hood_fs=[];nx=64;ny=64
for i in range(nx+1):
    r=i/nx;nominal_x=-2.15+1.125*r;edge_z=belt_height(nominal_x)
    edge_x,edge_w,_=side_surface(nominal_x,edge_z,'front')
    center_x=-2.34+1.315*r
    for j in range(ny+1):
        u=math.sin((j/ny-.5)*math.pi)
        blend=smoothstep(0,.18,r)
        corner=(1-math.sqrt(max(0,1-u**6)))*(1-blend)+u**6*blend
        z=edge_z+.045*math.sin(r*math.pi)**.6*(1-u**18)
        z+=.009*math.exp(-((abs(u)-.77)/.055)**2)*math.sin(r*math.pi)
        hood_vs.append((center_x+(edge_x-center_x)*corner,edge_w*u,z))
for i in range(nx):
    for j in range(ny):
        k=i*(ny+1)+j;hood_fs.append((k,k+ny+1,k+ny+2,k+1))
mesh('Continuous crowned bonnet',hood_vs,hood_fs,hood,paint,.005)
front=part('front_bumper','前保险杠','body',offset=(-1.18,0,.08),start=.06)
# A curved fascia grid wraps around both corners instead of a flat cube.
vs=[];fs=[];ny=96;nz=48
for j in range(nz+1):
    for i in range(ny+1):
        u=math.sin((i/ny-.5)*math.pi);t=j/nz
        lower=grille_top(u*.888)
        for _ in range(4):lower=grille_top(u*front_width(lower))
        z=lower+(1.01-lower)*t
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
    cutter=box('Lamp aperture cutter',(front_surface(side*.75,.735)[0],side*.75,.735),(.30,.18,.205),black,front,.033)
    slope=(front_surface(side*.75+.001,.735)[0]-front_surface(side*.75-.001,.735)[0])/.002
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
    tube('Horizontal intake louvre',[(front_surface(y,z)[0]+.012,y,z) for y in [-width+2*width*i/48 for i in range(49)]],.006,black,front)
for y in [-.53,0,.53]:
    tube('Grille vertical divider',[(front_surface(y,z)[0]+.008,y,z) for z in [.30,.36,.43]],.006,black,front)
tube('Intake upper rolled edge',[(front_surface(y,grille_top(y))[0]+.003,y,grille_top(y)) for y in [-.82+1.64*i/72 for i in range(73)]],.007,black,front)
tube('Lower splitter',[(front_surface(y,.295)[0]-.007,y,.285) for y in [-.82+1.64*i/48 for i in range(49)]],.014,black,front)
for side in [-1,1]:
    for y,z in [(side*.82,.55),(side*.45,.56)]:
        x=front_surface(y,z)[0]
        cylinder('Front parking sensor',(x-.004,y,z),.012,.004,paint,front,'X',24)
plate_x=front_surface(0,.642)[0]-.013
box('Front license plate',(plate_x,0,.642),(.014,.42,.135),black,front,.009)
text_label('ID. AURA T6',(plate_x-.009,0,.642),.036,front)
badge(front,front_surface(0,.955)[0]-.012,.955)
lightbar=part('front_light_bar','前贯穿灯带','body',offset=(-1.2,0,.25),start=.1)
band_vs=[];band_fs=[]
for top in [False,True]:
    for i in range(49):
        u=math.sin((i/48-.5)*math.pi);y=u*.856
        z=(.932 if not top else .987)+.025*abs(u)**6
        x=front_surface(y,z)[0]-.004;band_vs.append((x,y,z))
for i in range(48):band_fs.append((i,i+49,i+50,i+1))
mesh('Swept headlight fascia',band_vs,band_fs,lightbar,black,.004)
for side in [-1,1]:
    led_points=[]
    for i in range(30):
        y=side*(.08+.73*i/29);u=abs(y)/.856;z=.951+.034*u**7
        led_points.append((front_surface(y,z)[0]-.010,y,z))
    tube('Continuous slim running light',led_points,.0028,led,lightbar)
    brow=[]
    for y,z in [(side*.53,.971),(side*.76,.977),(side*.845,1.003)]:brow.append((front_surface(y,z)[0]-.008,y,z))
    tube('Brow light guide',brow,.006,led,lightbar,smooth=True)
    lamp_x=front_surface(side*.75,.735)[0]
    lamp=part(f'headlight_{side}',('左' if side>0 else '右')+'纵向方灯','body',(lamp_x,side*.75,.735),(-1.2,side*.12,.18),.12)
    box('Recessed projector housing',(lamp_x+.015,side*.75,.735),(.055,.16,.185),black,lamp,.031)
    for dz in [-.043,.043]:
        for dy in [-.030,.030]:
            cylinder('Projector chrome bowl',(lamp_x-.014,side*.75+dy,.735+dz),.024,.010,alloy,lamp,'X',32)
            cylinder('Projector optical element',(lamp_x-.021,side*.75+dy,.735+dz),.017,.005,led,lamp,'X',32)
    box('Projector outer lens',(lamp_x-.028,side*.75,.735),(.006,.148,.173),lamp_glass,lamp,.026)
    slope=(front_surface(side*.75+.001,.735)[0]-front_surface(side*.75-.001,.735)[0])/.002
    lamp.rotation_euler.z=-math.atan(slope)

windscreen=part('windscreen','前挡风玻璃','cabin',offset=(-.45,0,1.2),start=.18)
loft('Curved windscreen',[(-1.025,1.103,.868),(-.86,1.265,.825),(-.60,1.475,.780),(-.32,1.60,.740)],windscreen,glass,.022,0)
roof=part('panoramic_roof','全景玻璃车顶','cabin',offset=(0,0,1.9),start=.22)
roof_vs=[];roof_fs=[];nx=96;ny=48
for i in range(nx+1):
    x=-.32+2.02*i/nx
    for j in range(ny+1):
        u=j/ny*2-1;roof_vs.append((x,roof_w(x)*u,roof_z(x)+.022*(1-u*u)))
for i in range(nx):
    for j in range(ny):
        k=i*(ny+1)+j;roof_fs.append((k,k+ny+1,k+ny+2,k+1))
mesh('Crowned panoramic roof',roof_vs,roof_fs,roof,glass)
for side in [-1,1]:
    rack=part(f'roof_rack_{side}',('左' if side>0 else '右')+'行李架','body',offset=(0,side*.2,2.05),start=.25)
    tube('Roof rail',[(-.17,side*.655,1.655),(.10,side*.655,1.684),(1.08,side*.66,1.67),(1.48,side*.66,1.59)],.012,black,rack,smooth=True)
    for x,z in [(-.15,1.645),(1.26,1.617)]:box('Roof rail foot',(x,side*.655,z),(.16,.055,.06),black,rack,.02)
spoiler=part('rear_spoiler','后扰流板','body',offset=(.6,0,1.45),start=.2)
loft('Integrated roof spoiler',[(1.50,1.55,.785),(1.70,1.51,.800),(1.89,1.505,.790)],spoiler,paint,.012,.016)
loft('Spoiler underside',[(1.67,1.485,.775),(1.89,1.485,.780)],spoiler,black,.008,.008)
box('High mounted stop lamp',(1.902,0,1.502),(.010,.59,.012),red,spoiler,.005)
box('Rear upper camera housing',(1.90,0,1.469),(.042,.078,.039),black,spoiler,.014)
cylinder('Rear upper camera lens',(1.925,0,1.469),.012,.005,glass,spoiler,'X',24)
rear_glass=part('rear_glass','后挡风玻璃','cabin',offset=(.7,0,1.2),start=.2)
loft('Rear windscreen',[(1.70,1.50,.735),(1.88,1.32,.785),(2.08,1.125,.830)],rear_glass,glass,.015,0)
cylinder('Rear wiper pivot',(2.030,.11,1.195),.022,.016,black,rear_glass,'X',24)
tube('Rear wiper arm',[(2.040,.11,1.195),(2.045,-.12,1.19),(2.050,-.26,1.18)],.007,black,rear_glass)
tube('Rear wiper blade',[(2.047,-.31,1.183),(2.050,-.08,1.183),(2.047,.10,1.183)],.009,black,rear_glass)
tailgate=part('tailgate','尾门','body',offset=(1.12,0,.6),start=.1)
deck_vs=[];deck_fs=[];nx=16;ny=64
for i in range(nx+1):
    r=i/nx
    for j in range(ny+1):
        u=j/ny*2-1;end_x=rear_surface(u*rear_width(1.105),1.105)[0]
        deck_vs.append((2.08*(1-r)+end_x*r,u*(.830*(1-r)+rear_width(1.105)*r),1.125-.020*r+.010*math.sin(r*math.pi)*(1-u*u)))
for i in range(nx):
    for j in range(ny):
        k=i*(ny+1)+j;deck_fs.append((k,k+1,k+ny+2,k+ny+1))
mesh('Rolled tailgate upper shoulder',deck_vs,deck_fs,tailgate,paint,.006)
rear_vs=[];rear_fs=[];ny=64;nz=24
for j in range(nz+1):
    z=.665+(.440*j/nz)
    for i in range(ny+1):rear_vs.append(rear_surface(math.sin((i/ny-.5)*math.pi)*rear_width(z),z))
for j in range(nz):
    for i in range(ny):
        a=j*(ny+1)+i;rear_fs.append((a,a+1,a+ny+2,a+ny+1))
mesh('Sculpted tailgate face',rear_vs,rear_fs,tailgate,paint,.008)
badge(tailgate,rear_surface(0,1.061)[0]+.008,1.061,True)
text_label('I D. A U R A',(rear_surface(0,.937)[0]+.005,0,.937),.028,tailgate,True)
text_label('T6',(rear_surface(.65,.74)[0]+.01,.65,.74),.026,tailgate,True)
tube('Tailgate lower shut line',[(rear_surface(y,.672)[0]+.003,y,.672) for y in [-.77+1.54*i/48 for i in range(49)]],.0025,black,tailgate)
for side in [-1,1]:
    tube('Tailgate side shut line',[(rear_surface(side*(rear_width(z)-.07),z)[0]+.003,side*(rear_width(z)-.07),z) for z in [.68+.42*i/40 for i in range(41)]],.0015,black,tailgate)
rear_bumper=part('rear_bumper','后保险杠','body',offset=(1.25,0,.08),start=.06)
bumper_vs=[];bumper_fs=[];ny=64;nz=24
for j in range(nz+1):
    z=.29+.37*j/nz
    for i in range(ny+1):bumper_vs.append(rear_surface(math.sin((i/ny-.5)*math.pi)*rear_width(z),z))
for j in range(nz):
    for i in range(ny):
        a=j*(ny+1)+i;bumper_fs.append((a,a+1,a+ny+2,a+ny+1))
mesh('Wrapped rear bumper',bumper_vs,bumper_fs,rear_bumper,paint,.008)
diffuser_vs=[];diffuser_fs=[]
for j in range(13):
    for i in range(57):
        u=i/56*2-1;y=u*.82;z=.295+(.475+.08*abs(u)**4-.295)*j/12
        x,_,_=rear_surface(y,z);diffuser_vs.append((x+.006,y,z))
for j in range(12):
    for i in range(56):
        a=j*57+i;diffuser_fs.append((a,a+1,a+58,a+57))
mesh('Contoured rear diffuser',diffuser_vs,diffuser_fs,rear_bumper,black,.012)
tube('Diffuser lower lip',[(rear_surface(y,.31)[0]+.018,y,.31) for y in [-.8+1.6*i/48 for i in range(49)]],.012,black,rear_bumper)
for side in [-1,1]:
    y=side*.65;z=.585;x=rear_surface(y,z)[0]
    reflector=box('Rear reflector',(x+.006,y,z),(.014,.26,.026),reflector_red,rear_bumper,.009)
    slope=(rear_surface(y+.001,z)[0]-rear_surface(y-.001,z)[0])/.002
    reflector.rotation_euler.z=-math.atan(slope)
    for y in [side*.42,side*.81]:
        x=rear_surface(y,.6)[0]
        cylinder('Rear parking sensor',(x+.003,y,.6),.012,.004,paint,rear_bumper,'X',24)
plate_x=rear_surface(0,.566)[0]+.012
box('Rear license plate',(plate_x,0,.566),(.018,.44,.145),black,rear_bumper,.012)
text_label('ID. AURA T6',(plate_x+.013,0,.566),.042,rear_bumper,True)
rear_lights=part('tail_lights','后贯穿尾灯','body',offset=(1.18,0,.27),start=.12)
lamp_vs=[];lamp_fs=[]
for z in [1.045,1.112]:
    for i in range(49):
        y=(i/48*2-1)*.845;x=rear_surface(y,z)[0]+.006
        lamp_vs.append((x,y,z))
for i in range(48):lamp_fs.append((i,i+1,i+50,i+49))
mesh('Wrapped tail lamp lens',lamp_vs,lamp_fs,rear_lights,black,.012,.005)
for side in [-1,1]:
    for z in [1.063,1.093]:
        tube('Rear dual light signature',[(rear_surface(y,z)[0]+.014,y,z) for y in [side*(.08+.74*i/40) for i in range(41)]],.004,red,rear_lights)
    tube('Tail lamp side return',[(2.07,side*.860,1.086),(2.01,side*.887,1.102),(1.93,side*.905,1.107)],.006,red,rear_lights,smooth=True)

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
box('Lidar housing',(-.33,0,1.63),(.17,.29,.075),black,lidar,.027)
box('Lidar lens',(-.42,0,1.636),(.013,.23,.035),glass,lidar,.01)

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
