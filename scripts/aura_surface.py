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
_rear_center=section([(.28,2.300),(.38,2.375),(.49,2.405),(.59,2.390),
                      (.67,2.365),(.80,2.365),(1.105,2.320)])
tailgate_width=section([(.64,.750),(.72,.775),(.90,.807),(1.105,.808)])


def rear_split_height(y):
    return .670+.045*smoothstep(.52,.81,abs(y))


def diffuser_top(y):
    return .470+.088*smoothstep(.35,.87,abs(y))


def front_top(u):
    return .994+.016*u*u


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
    turn = (.320+.010*math.sin(t*math.pi))*(1-math.sqrt(max(0.0,1-u**6)))
    plate_recess = .022*math.exp(-((z-.58)/.105)**2)*math.exp(-(y/.40)**4)
    return (_rear_center(z)-turn-plate_recess, y, z)


def grille_top(y):
    return .292+.188*(1-smoothstep(.53,.84,abs(y)))


def rear_window_point(t,u):
    """Upright backlight with a shallow lateral crown under the roof spoiler."""
    y=(.735+.095*t)*u
    bottom_x=2.170-.050*u**4
    return (1.80*(1-t)+bottom_x*t+.015*math.sin(math.pi*t),y,
            1.50-.375*t+.015*math.sin(math.pi*t)*(1-u*u))


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
    assert .035 < rear_surface(0,.78)[0]-rear_surface(0,1.105)[0] < .055
    assert rear_surface(0,.49)[0] > rear_surface(0,1.105)[0]+.07
    for z in [.72,.85,1.0]:
        assert tailgate_width(z)+.05 < rear_width(z)
    for u in [i/100 for i in range(-100,101)]:
        x,y,z=rear_window_point(1,u)
        end_x=rear_surface(y,1.105)[0]
        assert .025 < end_x-x < .170, (u,end_x-x)
    assert .13 < rear_surface(0,1.105)[0]-rear_window_point(1,0)[0] < .17
    assert rear_window_point(1,0)[0]-rear_window_point(1,1)[0] < .06
    for z in [.32,.55,.80,1.05,1.105]:
        for start,end,tag in [(-2.15,-1.84,'front'),(1.80,2.30,'rear')]:
            xs=[side_surface(start+(end-start)*i/200,z,tag)[0] for i in range(201)]
            assert all(b>a for a,b in zip(xs,xs[1:])), ('folded corner',tag,z)
    print('Exterior sections: joins, shoulder widths, C1 continuity and bumper curvature verified.')


if __name__ == '__main__': verify()
