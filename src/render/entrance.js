import * as THREE from 'three';
import { WHEEL_RADIUS } from '../drive-state.js';

export const ENTRANCE_DURATION = 8.8;
export const VEHICLE_STOP_TIME = ENTRANCE_DURATION;
// Bullet-time: the logo close-up (animTime ≈ 0.30–0.42 of the entrance) is
// played in slow motion so the tail badge gets a brief hero beat, framed by
// normal-speed approaches on either side (fast → slow → easy). The remap turns
// real elapsed seconds into animTime (the value entrancePose expects); it is
// piecewise-linear and monotonic, so apply(ENTRANCE_DURATION) still settles the
// car and update(large dt) still triggers completion.
//   real [0, 1.5)        → animTime [0, 0.30·D)       normal (fast approach)
//   real [1.5, 4.0)      → animTime [0.30·D, 0.42·D)  bullet (logo hero, compressed)
//   real [4.0, BULLET_D) → animTime [0.42·D, D]       easy resume (variant-specific return home)
export const BULLET_DURATION = 10;
const _seg = ENTRANCE_DURATION;
function animTimeFor(elapsed){
  if(elapsed<=0)return 0;
  if(elapsed>=BULLET_DURATION)return _seg;
  if(elapsed<1.5) return (elapsed/1.5)*(0.30*_seg);
  if(elapsed<4.0) return 0.30*_seg + ((elapsed-1.5)/(4.0-1.5))*(0.12*_seg);
  return 0.42*_seg + ((elapsed-4.0)/(BULLET_DURATION-4.0))*(0.58*_seg);
}
const v = (x,y,z) => new THREE.Vector3(x,y,z);
const up=v(0,1,0);
// Trace the supplied sketch from its upper-left start to the lower-left finish.
// Rotate the sketch so its final tangent agrees with the parked model's -X.
const sketch=[[42,42],[110,68],[193,108],[252,151],[282,193],[288,235],[273,263],[245,275],[220,275],[201,266],[189,246],[177,228],[157,221],[139,222],[124,232],[110,252],[95,272],[78,292]];
const basis=Math.hypot(17,20),cos=17/basis,sin=20/basis;
const route=new THREE.CatmullRomCurve3(sketch.map(([x,y])=>v((cos*(x-78)-sin*(y-292))*.24,0,-(sin*(x-78)+cos*(y-292))*.24)),false,'centripetal');
route.arcLengthDivisions=1200;
const routeLength=route.getLength();
const samples=1200,wheelbase=2.836,halfTrack=.817;
const wheelDistances=Array.from({length:samples+1},()=>({fl:0,fr:0,rl:0,rr:0}));
function curvatureAt(u){
  const a=Math.max(0,u-.001),b=Math.min(1,u+.001),p=route.getTangentAt(a),q=route.getTangentAt(b);
  const angle=Math.atan2(q.z,-q.x)-Math.atan2(p.z,-p.x);
  return Math.atan2(Math.sin(angle),Math.cos(angle))/(routeLength*(b-a));
}
for(let i=1;i<=samples;i++){
  const k=curvatureAt((i-.5)/samples),ds=routeLength/samples,prev=wheelDistances[i-1],next=wheelDistances[i];
  for(const [front,id,z] of [[true,'fl',-halfTrack],[true,'fr',halfTrack],[false,'rl',-halfTrack],[false,'rr',halfTrack]]){
    const lateral=1-k*z;next[id]=prev[id]+ds*(front?Math.hypot(lateral,wheelbase*k):lateral);
  }
}
const smooth=t=>t*t*t*(t*(t*6-15)+10);
const interval=(t,start,end)=>THREE.MathUtils.clamp((t-start)/(end-start),0,1);

function sampleTrack(keys,t) {
  let i=0;while(i<keys.length-2&&t>keys[i+1][0])i++;
  const [a,p]=keys[i],[b,q]=keys[i+1],span=b-a,u=interval(t,a,b),u2=u*u,u3=u2*u;
  const before=keys[Math.max(0,i-1)],after=keys[Math.min(keys.length-1,i+2)];
  const m=i===0?v(0,0,0):q.clone().sub(before[1]).divideScalar(b-before[0]);
  const n=i+1===keys.length-1?v(0,0,0):after[1].clone().sub(p).divideScalar(after[0]-a);
  return p.clone().multiplyScalar(2*u3-3*u2+1).addScaledVector(m,(u3-2*u2+u)*span).addScaledVector(q,-2*u3+3*u2).addScaledVector(n,(u3-u2)*span);
}

export function entrancePose(time,home,variant='front-logo') {
  const t=THREE.MathUtils.clamp(time/ENTRANCE_DURATION,0,1);
  const arrival=THREE.MathUtils.clamp(time/VEHICLE_STOP_TIME,0,1);
  const travel=1-(1-arrival)**1.8;
  const position=route.getPointAt(travel),tangent=route.getTangentAt(travel);
  const yaw=arrival===1?0:Math.atan2(tangent.z,-tangent.x);
  const curvature=arrival===1?0:curvatureAt(travel);
  const straighten=1-smooth(interval(arrival,.94,1));
  const steeringByWheel={fl:Math.atan2(wheelbase*curvature,1+halfTrack*curvature)*straighten,fr:Math.atan2(wheelbase*curvature,1-halfTrack*curvature)*straighten};
  const index=Math.min(samples-1,Math.floor(travel*samples)),fraction=travel*samples-index;
  const wheelAngles=Object.fromEntries(['fl','fr','rl','rr'].map(id=>[id,THREE.MathUtils.lerp(wheelDistances[index][id],wheelDistances[index+1][id],fraction)/WHEEL_RADIUS]));
  const entry=route.getPointAt(0),entryTangent=route.getTangentAt(0),entryYaw=Math.atan2(entryTangent.z,-entryTangent.x);
  const fixedCamera=v(60,12,-30),fixedTarget=v(40,.7,0);
  const initialCamera=fixedCamera.clone().sub(entry).applyAxisAngle(up,-entryYaw);
  const initialTarget=fixedTarget.clone().sub(entry).applyAxisAngle(up,-entryYaw);
  // Camera keyframes (local vehicle space; +X = tail/logo, -X = nose).
  // Both variants share the tail close-up, then either return directly or
  // follow one side to the nose badge before easing back to home.
  const cameraKeys=[[0,initialCamera],[.16,v(-7.5,2,-9)],[.28,v(6,1.6,-3)],[.34,v(4.4,1.0,0.0)],[.38,v(4.2,1.0,0.0)],[.42,v(4.2,0.98,0.0)]];
  const targetKeys=[[0,initialTarget],[.16,v(0,.75,0)],[.28,v(1.0,.95,.1)],[.34,v(2.35,.96,0.0)],[.38,v(2.35,.96,0.0)],[.42,v(2.35,.96,0.0)]];
  if(variant==='direct'){
    cameraKeys.push([.46,v(3.8,1.2,1.2)],[1,home]);
    targetKeys.push([1,v(0,.7,0)]);
  }else{
    cameraKeys.push([.46,v(3.8,1.2,1.2)],[.52,v(2.0,1.5,3.2)],[.58,v(0.5,1.6,4.2)],[.66,v(-3.8,1.3,2.0)],[.72,v(-4.3,1.0,0.5)],[.76,v(-4.3,.98,0.5)],[1,home]);
    targetKeys.push([.46,v(1.8,.95,.6)],[.52,v(.6,.9,1.0)],[.58,v(-.4,.85,.6)],[.66,v(-2.0,.95,.4)],[.72,v(-2.35,.96,0.0)],[.74,v(-2.35,.96,0.0)],[.76,v(-2.35,.96,0.0)],[1,v(0,.7,0)]);
  }
  const cameraLocal=sampleTrack(cameraKeys,t);
  const targetLocal=sampleTrack(targetKeys,t);
  const follow=smooth(interval(t,.32,.38));
  const targetFollow=smooth(interval(t,.28,.36));
  const camera=cameraLocal.applyAxisAngle(up,yaw).add(position).lerp(fixedCamera,1-follow);
  const target=targetLocal.applyAxisAngle(up,yaw).add(position).lerp(fixedTarget,1-targetFollow);
  return {
    progress:t,position,yaw,camera,target,
    fov:THREE.MathUtils.lerp(55,30+4*Math.sin(Math.PI*t)**2,follow),framing:smooth(interval(t,.84,1)),
    roll:0,wheelAngle:routeLength*travel/WHEEL_RADIUS,wheelAngles,steeringByWheel,
    braking:arrival>.85&&arrival<1,
    phase:t<.28?'大弧转入':t<.42?'尾灯近赏':variant==='front-logo'&&t<.78?'车头近赏':'从容就位',
  };
}

/** Shares the application's renderer and frame loop; never changes vehicle signals. */
export function createEntrance({vehicle,camera,controls,studio,home,getVariant=()=> 'front-logo',onChange=()=>{},onComplete=()=>{}}) {
  let active=false, elapsed=0, orbit, wheelAngle=0, wheelAngles={fl:0,fr:0,rl:0,rr:0};
  function apply(time) {
    const pose=entrancePose(time,home(),getVariant());
    vehicle.root.position.copy(pose.position);vehicle.root.rotation.y=pose.yaw;
    camera.position.copy(pose.camera);camera.fov=pose.fov;camera.updateProjectionMatrix();
    controls.target.copy(pose.target);controls.update();camera.rotateZ(pose.roll);
    studio.setVehiclePose(pose.position,pose.yaw);
    wheelAngle=pose.wheelAngle;wheelAngles=pose.wheelAngles;
    return pose;
  }
  function finish() {
    if(!active)return;
    apply(ENTRANCE_DURATION);
    controls.enabled=orbit.enabled;controls.enableDamping=orbit.damping;
    active=false;onChange(false);
  }
  return {
    get active(){return active;},
    get wheelAngle(){return wheelAngle;},
    get wheelAngles(){return wheelAngles;},
    start() {
      if(active)finish();
      orbit={enabled:controls.enabled,damping:controls.enableDamping};
      controls.enableDamping=false;controls.update();controls.enabled=false;
      elapsed=0;active=true;apply(0);onChange(true);
    },
    finish,
    update(dt) {
      if(!active)return null;
      if(Number.isFinite(dt)&&dt>0)elapsed+=dt;
      // Bullet-time remap: real elapsed → animTime (logo beat in slow motion).
      const animTime=animTimeFor(elapsed);
      const pose=apply(animTime);
      if(animTime>=ENTRANCE_DURATION){finish();onComplete();}
      return pose;
    },
  };
}
