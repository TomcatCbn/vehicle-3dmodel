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
_side_section = section([(.24,.795),(.32,.848),(.42,.884),(.52,.900),(.66,.892),
                         (.82,.911),(.965,.918),(1.045,.906),(1.09,.865),(1.16,.750)])


def side_width(x, z):
    section_z = z-(belt_height(x)-1.09)*smoothstep(.55,1.1,z)
    flare = sum(.021*math.exp(-((x-wx)/.50)**4)*math.exp(-((z-.77)/.27)**2)
                for wx in [-1.418,1.418])
    scoop = -.012*math.exp(-((x-.05)/1.05)**4)*math.exp(-((z-.63)/.14)**2)
    return _side_section(section_z)+flare+scoop


front_width = section([(.28,.840),(.38,.888),(.64,.914),(.82,.918),(.94,.900),(1.01,.860)])
_front_x = section([(.28,-2.322),(.40,-2.365),(.68,-2.405),(.87,-2.392),(1.01,-2.340)])
rear_width = section([(.28,.820),(.40,.902),(.58,.928),(.82,.933),(1.0,.903),(1.105,.855)])
_rear_x = section([(.28,2.300),(.40,2.400),(.53,2.405),(.66,2.365),(.86,2.382),(1.105,2.310)])


def front_surface(y, z):
    u = max(-1.0, min(1.0, y/front_width(z)))
    t = max(0.0, min(1.0, (z-.28)/.73))
    turn = (.245+.035*math.sin(t*math.pi))*(1-math.sqrt(max(0.0,1-u**6)))
    return (_front_x(z)+turn, y, z)


def rear_surface(y, z):
    u = max(-1.0, min(1.0, y/rear_width(z)))
    t = max(0.0, min(1.0, (z-.28)/.825))
    turn = (.26+.025*math.sin(t*math.pi))*(1-math.sqrt(max(0.0,1-u**6)))
    plate_recess = .018*math.exp(-((z-.60)/.115)**2)*math.exp(-(y/.40)**4)
    return (_rear_x(z)-turn-plate_recess, y, z)


def grille_top(y):
    return .292+.188*(1-smoothstep(.53,.84,abs(y)))


def side_surface(x, z, end=None):
    width = side_width(x,z)
    if end == 'front':
        blend = 1-smoothstep(-2.15,-1.84,x)
        x += (front_surface(front_width(z),z)[0]+2.15)*blend
        width = width*(1-blend)+front_width(z)*blend
    elif end == 'rear':
        blend = smoothstep(1.98,2.30,x)
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
    assert rear_surface(0,.40)[0] > rear_surface(0,1.105)[0]+.08
    print('Exterior sections: joins, shoulder widths, C1 continuity and bumper curvature verified.')


if __name__ == '__main__': verify()
