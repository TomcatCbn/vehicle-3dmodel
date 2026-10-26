"""Shared exterior section curves in metres; independent of Blender for verification."""
import math
from bisect import bisect_right


def smoothstep(a, b, value):
    t = max(0.0, min(1.0, (value-a)/(b-a)))
    return t*t*(3-2*t)


def section(points):
    """Shape-preserving cubic sections keep highlights free of spline overshoot."""
    xs, ys = zip(*points)
    spans = [b-a for a, b in zip(xs, xs[1:])]
    slopes = [(b-a)/h for a, b, h in zip(ys, ys[1:], spans)]
    tangents = [0.0]
    for i in range(1, len(points)-1):
        before, after = slopes[i-1:i+1]
        if before*after <= 0:
            tangents.append(0.0)
        else:
            w1, w2 = 2*spans[i]+spans[i-1], spans[i]+2*spans[i-1]
            tangents.append((w1+w2)/(w1/before+w2/after))
    tangents.append(0.0)

    def value(x):
        if x <= xs[0]: return ys[0]
        if x >= xs[-1]: return ys[-1]
        i = bisect_right(xs, x)-1
        h = spans[i]; t = (x-xs[i])/h
        return ((2*t**3-3*t*t+1)*ys[i] + (t**3-2*t*t+t)*h*tangents[i]
                + (-2*t**3+3*t*t)*ys[i+1] + (t**3-t*t)*h*tangents[i+1])
    return value


belt_height = section([(-2.15,1.01),(-1.80,1.055),(-1.35,1.093),(-1.02,1.10),
                       (-.15,1.095),(.70,1.107),(1.35,1.12),(1.80,1.11),(2.30,1.105)])
_side_section = section([(.24,.795),(.32,.848),(.42,.882),(.52,.893),(.66,.894),
                         (.82,.913),(.95,.918),(1.015,.910),(1.065,.889),(1.09,.865),(1.16,.750)])


def side_width(x, z):
    section_z = z-(belt_height(x)-1.09)*smoothstep(.55,1.1,z)
    flare = sum(.021*math.exp(-((x-wx)/.50)**4)*math.exp(-((z-.77)/.27)**2)
                for wx in [-1.418,1.418])
    scoop = -.017*math.exp(-((x-.05)/1.05)**4)*math.exp(-((z-.64)/.14)**2)
    lower_scallop=-.010*math.exp(-((x-.12)/1.05)**4)*math.exp(-((z-(.47+.045*smoothstep(-1,.9,x)))/.065)**2)
    return _side_section(section_z)+flare+scoop+lower_scallop


def front_width(z):
    t=max(0.0,min(1.0,(z-.28)/.73))
    return .840+.020*t+.064*math.sin(math.pi*t)


rear_width=section([(.28,.810),(.38,.880),(.52,.928),(.78,.939),(.98,.914),(1.105,.876)])
_rear_center=section([(.28,2.300),(.38,2.365),(.49,2.400),(.59,2.400),
                      (.67,2.370),(.76,2.354),(.83,2.346),(.93,2.351),(1.025,2.342),(1.105,2.320)])
tailgate_width=section([(.64,.728),(.72,.738),(.90,.748),(1.105,.752)])
TAILGATE_HINGE=(1.69,0,1.58)


def rear_split_height(y):
    return .660+.010*smoothstep(.60,.76,abs(y))


def diffuser_top(y):
    return .470+.088*smoothstep(.35,.87,abs(y))


def front_top(u):
    return .994+.016*u*u


HOOD_HALF_SPAN=.865
HOOD_HINGE=(-1.045,0,1.095)


def front_deck_point(r,u):
    nominal_x=-2.15+1.125*r
    edge_z=belt_height(nominal_x)
    edge_x,edge_w,_=side_surface(nominal_x,edge_z,'front')
    nose_center=front_surface(0,front_top(0))[0]
    center_x=nose_center*(1-r)-1.025*r
    blend=smoothstep(0,.18,r)
    front_delta=front_surface(u*front_width(front_top(u)),front_top(u))[0]-nose_center
    corner_delta=front_surface(front_width(front_top(1)),front_top(1))[0]-nose_center
    corner=front_delta/corner_delta*(1-blend)+u**6*blend
    z=edge_z-.016*(1-u*u)*(1-r)**3+.019*math.sin(r*math.pi)**1.35*(1-u**18)
    z+=.0045*math.exp(-((abs(u)-.77)/.09)**2)*math.sin(r*math.pi)
    width_ratio=front_width(front_top(u))/front_width(front_top(1))
    return (center_x+(edge_x-center_x)*corner,edge_w*u*(width_ratio*(1-blend)+blend),z)


def bonnet_front(u):
    return .195+.012*u*u+.022*smoothstep(.64,.78,abs(u))+.041*smoothstep(.90,1,abs(u))


def bonnet_rear(u):
    return .988-.006*u**4


def bonnet_point(s,u,depth=0):
    r=bonnet_front(u)+(bonnet_rear(u)-bonnet_front(u))*s
    x,y,z=front_deck_point(r,HOOD_HALF_SPAN*u)
    return x,y,z-depth


def front_deck_normal(r,u):
    h=.0001
    a=front_deck_point(max(0,r-h),u);b=front_deck_point(min(1,r+h),u)
    c=front_deck_point(r,max(-1,u-h));d=front_deck_point(r,min(1,u+h))
    v=[b[i]-a[i] for i in range(3)];w=[d[i]-c[i] for i in range(3)]
    normal=(v[1]*w[2]-v[2]*w[1],v[2]*w[0]-v[0]*w[2],v[0]*w[1]-v[1]*w[0])
    length=math.sqrt(sum(x*x for x in normal))
    return tuple(x/length for x in normal)


def bonnet_normal(s,u):
    r=bonnet_front(u)+(bonnet_rear(u)-bonnet_front(u))*s
    return front_deck_normal(r,HOOD_HALF_SPAN*u)


def bonnet_side_u(r):
    gap=.004*smoothstep(bonnet_front(1)-.016,bonnet_front(1),r)*(1-smoothstep(bonnet_rear(1),1,r))
    return HOOD_HALF_SPAN+gap


def light_bar_point(u,v,offset=0):
    # An elliptical return rounds each end of the lens into the painted corner.
    width=.846+.020*math.sqrt(max(0,1-(2*v-1)**2))
    y=u*width;z=.915+.066*v+.023*u**6
    p=front_surface(y,z);h=.0001
    dy=(front_surface(y+h,z)[0]-front_surface(y-h,z)[0])/(2*h)
    dz=(front_surface(y,z+h)[0]-front_surface(y,z-h)[0])/(2*h)
    normal=(-1,dy,dz);length=math.sqrt(sum(x*x for x in normal))
    return tuple(p[i]+normal[i]*offset/length for i in range(3))


def front_surface(y, z):
    u = max(-1.0, min(1.0, y/front_width(z)))
    t = max(0.0, min(1.0, (z-.28)/.73))
    turn = (.300+.015*math.sin(t*math.pi))*(1-math.sqrt(max(0.0,1-u**4)))
    center=-2.322-.100*math.sin(math.pi*t)+.038*math.exp(-((z-.75)/.15)**2)
    pocket=.017*math.exp(-((abs(y)-.725)/.145)**4-((z-.741)/.140)**4)
    return (center+turn+pocket, y, z)


def rear_surface(y, z):
    u = max(-1.0, min(1.0, y/rear_width(z)))
    t = max(0.0, min(1.0, (z-.28)/.825))
    turn = (.320+.010*math.sin(t*math.pi))*(1-math.sqrt(max(0.0,1-u**4)))
    plate_recess = .036*math.exp(-((z-.555)/.105)**2)*math.exp(-(y/.35)**6)
    plate_cheek = .014*math.exp(-((z-.615)/.055)**2)*math.exp(-((abs(y)-.46)/.15)**2)
    return (_rear_center(z)-turn-plate_recess+plate_cheek, y, z)


def grille_top(y):
    return .292+.188*(1-smoothstep(.53,.84,abs(y)))


def rear_window_point(t,u):
    """Upright backlight with a shallow lateral crown under the roof spoiler."""
    y=(.640+.095*t)*u
    bottom_x=2.215-.050*u**4
    return (1.80*(1-t)+bottom_x*t+.015*math.sin(math.pi*t),y,
            1.50-.360*t+.015*math.sin(math.pi*t)*(1-u*u))


def rear_shoulder_point(r,u):
    start=rear_window_point(1,u);end=rear_surface(u*tailgate_width(1.105),1.105)
    a=(start[0],start[1],start[2]);b=(start[0]+(end[0]-start[0])*.60,start[1]+(end[1]-start[1])*.33,start[2]-.008)
    c=(end[0],end[1]-(end[1]-start[1])*.15,end[2]+.019)
    return tuple((1-r)**3*a[i]+3*(1-r)**2*r*b[i]+3*(1-r)*r*r*c[i]+r**3*end[i] for i in range(3))


def side_surface(x, z, end=None):
    width = side_width(x,z)
    if end == 'front':
        blend = 1-smoothstep(-2.15,-1.84,x)
        x += (front_surface(front_width(z),z)[0]+2.15)*blend
        width = width*(1-blend)+front_width(z)*blend
    elif end == 'rear':
        blend = smoothstep(1.80,2.30,x)
        x += (rear_surface(rear_width(z),z)[0]-2.30)*blend
        width = width*(1-blend)+rear_width(z)*blend
    return x, width, z


def verify():
    assert bonnet_side_u(0)==HOOD_HALF_SPAN
    assert bonnet_side_u(.5)==HOOD_HALF_SPAN+.004
    assert bonnet_side_u(1)==HOOD_HALF_SPAN
    for u in [i/20 for i in range(-20,21)]:
        xs=[front_deck_point(i/200,u)[0] for i in range(51)]
        assert all(b>a for a,b in zip(xs,xs[1:])),('front deck fold',u)
    for u in [-1,-.8,-.4,0,.4,.8,1]:
        for r in [0,.2,.5,.8,1]:
            normal=front_deck_normal(r,u)
            assert all(math.isfinite(n) for n in normal)
            assert abs(sum(n*n for n in normal)-1)<1e-9
            assert normal[2]>.35
        for v in [0,.1,.5,.9,1]:
            a=light_bar_point(u,v,.005);b=light_bar_point(-u,v,.005)
            assert max(abs(a[i]-b[i]*(1 if i!=1 else -1)) for i in range(3))<1e-8
            assert abs(math.dist(a,light_bar_point(u,v))-.005)<1e-9
            assert a[2]<front_top(u)+.005
    assert light_bar_point(1,.5)[1]>light_bar_point(1,0)[1]+.015
    assert abs(bonnet_front(.5)-bonnet_front(0))<.006
    for u in [-1,-.5,0,.5,1]:
        x,y,z=front_deck_point(0,u)
        assert abs(z-front_top(u))<1e-9
        assert abs(x-front_surface(y,z)[0])<1e-9
        a=bonnet_point(0,u)
        b=front_deck_point(bonnet_front(u)-.003,HOOD_HALF_SPAN*u)
        assert .002<math.dist(a,b)<.006
    assert bonnet_point(0,0)[0]>-2.14
    assert bonnet_point(1,0)[0]>HOOD_HINGE[0]-.02
    for z in [.34,.48,.70,.90,1.0]:
        a = side_surface(-2.15,z,'front'); b = front_surface(front_width(z),z)
        c = side_surface(2.30,z,'rear'); d = rear_surface(rear_width(z),z)
        assert max(abs(i-j) for i,j in zip(a,b)) < 1e-10
        assert max(abs(i-j) for i,j in zip(c,d)) < 1e-10
    for x in [-2.0,-1.418,-.5,.5,1.418,2.0]:
        for z in [.34,.60,.90,1.04]:
            assert .79 < side_width(x,z) < .945
        assert .84 < side_width(x,belt_height(x)) < .90
    for fn, knots in [(front_width,[.38,.64,.82,.94]), (belt_height,[-1.8,-1.35,-1.02,-.15,.7,1.35,1.8])]:
        h = 1e-5
        for x in knots:
            left=(fn(x)-fn(x-h))/h; right=(fn(x+h)-fn(x))/h
            assert abs(left-right) < .005, (x,left,right)
    assert front_surface(0,.68)[0] < front_surface(0,1.01)[0]-.05
    assert .025 < rear_surface(0,.78)[0]-rear_surface(0,1.105)[0] < .045
    assert rear_surface(.5,.49)[0] > rear_surface(.5,1.105)[0]+.07
    for z in [.72,.85,1.0]:
        assert tailgate_width(z)+.05 < rear_width(z)
    for u in [i/100 for i in range(-100,101)]:
        x,y,z=rear_window_point(1,u)
        end_x=rear_surface(y,1.105)[0]
        assert .025 < end_x-x < .170, (u,end_x-x)
    assert .09 < rear_surface(0,1.105)[0]-rear_window_point(1,0)[0] < .12
    assert rear_window_point(1,0)[0]-rear_window_point(1,1)[0] < .06
    for u in [-1,-.8,-.4,0,.4,.8,1]:
        assert math.dist(rear_shoulder_point(0,u),rear_window_point(1,u))<1e-9
        assert math.dist(rear_shoulder_point(1,u),rear_surface(u*tailgate_width(1.105),1.105))<1e-9
        zs=[rear_shoulder_point(i/100,u)[2] for i in range(101)]
        assert all(b<a for a,b in zip(zs,zs[1:])),('rear shoulder folds',u)
    for z in [.32,.55,.80,1.05,1.105]:
        for start,end,tag in [(-2.15,-1.84,'front'),(1.80,2.30,'rear')]:
            xs=[side_surface(start+(end-start)*i/200,z,tag)[0] for i in range(201)]
            assert all(b>a for a,b in zip(xs,xs[1:])), ('folded corner',tag,z)
    print('Exterior sections: joins, shoulder widths, C1 continuity and bumper curvature verified.')


if __name__ == '__main__': verify()
