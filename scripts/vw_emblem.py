"""Flat VW letter profiles traced by proportion from the user's badge reference."""
import math

RING_INNER=.913


def stroke(points,width):
    normals=[]
    for a,b in zip(points,points[1:]):
        dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        normals.append((-dy/length,dx/length))
    left=[];right=[]
    for i,p in enumerate(points):
        if i==0:n=normals[0];distance=width/2
        elif i==len(points)-1:n=normals[-1];distance=width/2
        else:
            a,b=normals[i-1],normals[i];n=(a[0]+b[0],a[1]+b[1])
            length=math.hypot(*n);n=(n[0]/length,n[1]/length)
            distance=width/2/(n[0]*b[0]+n[1]*b[1])
        left.append((p[0]+n[0]*distance,p[1]+n[1]*distance))
        right.append((p[0]-n[0]*distance,p[1]-n[1]*distance))
    return left+list(reversed(right))


def clip_roundel(points,radius=.930):
    # A convex disk clips the four letter terminals into the surrounding ring.
    for i in range(256):
        angle=(i+.5)/256*math.tau;nx,ny=math.cos(angle),math.sin(angle)
        limit=radius*math.cos(math.pi/256);result=[]
        for a,b in zip(points,points[1:]+points[:1]):
            da=a[0]*nx+a[1]*ny-limit;db=b[0]*nx+b[1]*ny-limit
            if da<=0:result.append(a)
            if (da<=0)!=(db<=0):
                t=da/(da-db);result.append((a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t))
        points=result
    clean=[]
    for p in points:
        if not clean or math.dist(p,clean[-1])>1e-7:clean.append(p)
    if math.dist(clean[0],clean[-1])<1e-7:clean.pop()
    points=clean
    area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1]))
    return points if area>0 else list(reversed(points))


V=clip_roundel(stroke([(-.420,.910),(0,.130),(.420,.910)],.085))
W=clip_roundel(stroke([(-.820,.580),(-.340,-.840),(0,-.140),(.340,-.840),(.820,.580)],.085))


def verify():
    for outline in [V,W]:
        assert len(outline)>6
        assert all(math.hypot(x,y)<=.9300001 for x,y in outline)
        assert all(min(math.hypot(a+x,b-y) for a,b in outline)<1e-8 for x,y in outline)
        area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(outline,outline[1:]+outline[:1]))/2
        assert .12<area<.5
    v_tip=min(y for x,y in V)
    w_peak=max(y for x,y in W if abs(x)<.1)
    assert .065<v_tip-w_peak<.10, (v_tip,w_peak)
    print('VW profiles: symmetric flat strokes, clipped terminals and separate V/W verified.')


if __name__=='__main__':verify()
