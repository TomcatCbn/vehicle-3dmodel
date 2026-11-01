import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { entrancePose, createEntrance, ENTRANCE_DURATION, VEHICLE_STOP_TIME } from '../src/render/entrance.js';

const home=new THREE.Vector3(-7.4,2.5,9.8);
test('broad entry turns past the parking heading, straightens and stops nose-first',()=>{
  const poses=Array.from({length:301},(_,i)=>entrancePose(i/300*VEHICLE_STOP_TIME,home));
  assert.ok(poses[0].position.z>17&&poses[0].position.x>17);
  assert.ok(Math.max(...poses.map(p=>p.yaw))>1.5,'turn far enough to reveal the rear');
  assert.ok(Math.min(...poses.map(p=>p.position.z))<-1,'broad arc continues beyond the parking line');
  const lengths=poses.slice(1).map((p,i)=>p.position.distanceTo(poses[i].position));
  assert.ok(lengths[0]>lengths[150]*1.6&&lengths[150]>lengths[285]*6);
  for(let i=0;i<299;i++){
    const nose=new THREE.Vector3(-1,0,0).applyAxisAngle(new THREE.Vector3(0,1,0),poses[i].yaw);
    assert.ok(nose.dot(poses[i+1].position.clone().sub(poses[i].position).normalize())>.98);
    assert.ok(poses[i+1].wheelAngle>poses[i].wheelAngle);
  }
  const stop=poses.at(-1),final=entrancePose(ENTRANCE_DURATION,home);
  assert.ok(stop.position.length()<1e-10);assert.equal(stop.yaw,0);assert.equal(stop.braking,false);
  const nearEnd=entrancePose(ENTRANCE_DURATION*.98,home);
  assert.ok(nearEnd.position.distanceTo(stop.position)>1e-5,'vehicle continues rolling until the camera settles');
  assert.ok(nearEnd.wheelAngle<final.wheelAngle,'wheels continue turning until the final frame');
  assert.equal(final.fov,30);assert.equal(final.framing,1);
  assert.ok(final.camera.distanceTo(home)<1e-10);assert.ok(final.target.distanceTo(new THREE.Vector3(0,.7,0))<1e-10);
});

function local(p,vector){return vector.clone().sub(p.position).applyAxisAngle(new THREE.Vector3(0,1,0),-p.yaw);}
function cameraFor(p,width=1280,height=900){
  const camera=new THREE.PerspectiveCamera(p.fov,width/height,.1,150);camera.position.copy(p.camera);camera.lookAt(p.target);
  camera.setViewOffset(width,height,width*.13*p.framing,0,width,height);camera.updateMatrixWorld(true);return camera;
}

test('camera closes on the tail logo then returns directly without orbiting the car',()=>{
  const tail=entrancePose(ENTRANCE_DURATION*.40,home,'direct');
  assert.ok(local(tail,tail.camera).x>3&&local(tail,tail.target).x>2);
  assert.ok(tail.camera.distanceTo(tail.target)<2.5,'logo close-up');
  let previous;
  for(let i=0;i<=1000;i++){
    const t=i/1000,p=entrancePose(t*ENTRANCE_DURATION,home,'direct'),c=local(p,p.camera),target=local(p,p.target);
    assert.ok(!(Math.abs(c.x)<2.6&&Math.abs(c.z)<1.3&&c.y<1.9),'camera stays outside the closed body');
    assert.ok(p.camera.distanceTo(p.target)>1.8);
    if(t>=.42){
      assert.ok(c.z>=-1e-9,'return stays on one side instead of orbiting around the nose');
      assert.ok(target.x>=-1e-9&&target.x<=2.35+1e-9,'target eases directly from the badge to the car centre');
    }
    if(previous)assert.ok(p.camera.distanceTo(previous.camera)<.8,'continuous tracking');
    previous=p;
  }
  const first=entrancePose(0,home,'direct'),entry=first.position.clone().add(new THREE.Vector3(0,.7,0)).project(cameraFor(first));
  assert.ok(entry.x<-.35&&entry.y>.15);
});

test('front-logo variant follows one side to the nose badge then returns home',()=>{
  const front=entrancePose(ENTRANCE_DURATION*.74,home,'front-logo');
  assert.ok(local(front,front.camera).x<-3,'camera reaches the nose');
  assert.ok(Math.abs(local(front,front.target).x+2.35)<1e-9,'target is the nose badge');
  assert.ok(front.camera.distanceTo(front.target)<2.5,'nose badge close-up');
  assert.ok(entrancePose(ENTRANCE_DURATION*.74,home).camera.distanceTo(front.camera)<1e-10,'front-logo is the default');
  let previous;
  for(let i=0;i<=1000;i++){
    const t=i/1000,p=entrancePose(t*ENTRANCE_DURATION,home,'front-logo'),c=local(p,p.camera);
    assert.ok(!(Math.abs(c.x)<2.6&&Math.abs(c.z)<1.3&&c.y<1.9),'camera stays outside the closed body');
    assert.ok(p.camera.distanceTo(p.target)>1.8);
    if(t>=.42)assert.ok(c.z>=-1e-9,'front approach stays on one side');
    if(previous)assert.ok(p.camera.distanceTo(previous.camera)<.8,'continuous tracking');
    previous=p;
  }
  const final=entrancePose(ENTRANCE_DURATION,home,'front-logo');
  assert.ok(final.camera.distanceTo(home)<1e-10);
  assert.ok(final.target.distanceTo(new THREE.Vector3(0,.7,0))<1e-10);
});

test('tail detail stays framed and the final shot restores full-car framing on desktop',()=>{
  for(const [width,height] of [[1280,900],[1920,1080]]){
    for(const t of [.34,.38,.42,1]){
      const pose=entrancePose(t*ENTRANCE_DURATION,home),camera=cameraFor(pose,width,height);
      const ranges=t===1?[[-2.45,2.45],[0,1.8],[-1.2,1.2]]:[[2.2,2.5],[0.9,1.05],[-.15,.15]];
      for(const x of ranges[0])for(const y of ranges[1])for(const z of ranges[2]){
        const p=new THREE.Vector3(x,y,z).applyAxisAngle(new THREE.Vector3(0,1,0),pose.yaw).add(pose.position).project(camera);
        assert.ok(Math.abs(p.x)<.95&&Math.abs(p.y)<.95,`shot ${t} at ${width}`);assert.ok(p.z>-1&&p.z<1);
      }
    }
  }
});

test('skip, replay and completion restore transforms and orbit controls without drift',()=>{
  const vehicle={root:new THREE.Group()},camera=new THREE.PerspectiveCamera(30,1,.1,150);
  const controls={enabled:true,enableDamping:true,target:new THREE.Vector3(),update(){camera.lookAt(this.target);}};
  let shadowPosition,shadowYaw;
  const studio={setVehiclePose(position,yaw){shadowPosition=position.clone();shadowYaw=yaw;}};
  const changes=[];let completions=0;
  const entrance=createEntrance({vehicle,camera,controls,studio,home:()=>home,onChange:active=>changes.push(active),onComplete:()=>completions++});
  for(let i=0;i<3;i++){
    entrance.start();assert.equal(controls.enabled,false);assert.equal(controls.enableDamping,false);
    entrance.update(.5);assert.ok(vehicle.root.position.length()>10);
    const before=vehicle.root.position.clone();entrance.update(NaN);assert.ok(vehicle.root.position.equals(before));
    entrance.finish();entrance.finish();
    assert.equal(completions,0,'skipping never triggers shutdown');
    assert.equal(entrance.active,false);assert.ok(vehicle.root.position.length()<1e-10);
    assert.equal(vehicle.root.rotation.y,0);assert.equal(shadowYaw,0);assert.ok(shadowPosition.length()<1e-10);
    assert.ok(camera.position.distanceTo(home)<1e-10);assert.equal(camera.fov,30);
    assert.equal(controls.enabled,true);assert.equal(controls.enableDamping,true);
  }
  entrance.start();entrance.start();entrance.update(ENTRANCE_DURATION+10);
  entrance.update(1);assert.equal(completions,1,'only natural completion triggers shutdown once');
  assert.equal(entrance.active,false);assert.equal(changes.at(-1),false);
  assert.equal(controls.enabled,true);assert.equal(controls.enableDamping,true);
});


test('the drawn path changes steering direction and each wheel follows its own turning distance',()=>{
  const poses=Array.from({length:501},(_,i)=>entrancePose(i/500*VEHICLE_STOP_TIME,home));
  const left=poses.map(p=>p.steeringByWheel.fl),right=poses.map(p=>p.steeringByWheel.fr);
  assert.ok(Math.min(...left)<-.2&&Math.max(...left)>.2,'both turns have visible steering');
  assert.ok(Math.max(...left.map(Math.abs),...right.map(Math.abs))<.8,'steering stays within a plausible range');
  assert.ok(poses.some(p=>Math.abs(p.steeringByWheel.fl-p.steeringByWheel.fr)>.01),'inner and outer wheels steer differently');
  assert.ok(poses.some(p=>Math.abs(p.wheelAngles.rl-p.wheelAngles.rr)>.5),'inner and outer wheels roll different distances');
  for(const p of poses)for(const angle of Object.values(p.wheelAngles))assert.ok(Number.isFinite(angle));
});

test('the opening camera stays fixed while the car approaches through the broad right turn',()=>{
  const first=entrancePose(0,home),later=entrancePose(ENTRANCE_DURATION*.27,home);
  assert.ok(first.camera.distanceTo(later.camera)<1e-9);
  assert.ok(first.target.distanceTo(later.target)<1e-9);
  assert.equal(first.fov,later.fov);assert.equal(first.framing,later.framing);
  assert.ok(later.camera.distanceTo(later.position)<first.camera.distanceTo(first.position));
  assert.ok(entrancePose(ENTRANCE_DURATION*.2,home).steeringByWheel.fr>0,'front wheels steer right');
  for(let i=24;i<=40;i++){
    const p=entrancePose(ENTRANCE_DURATION*i/100,home);
    const projected=p.position.clone().add(new THREE.Vector3(0,.7,0)).project(cameraFor(p,1063,935));
    assert.ok(Math.abs(projected.x)<.9&&Math.abs(projected.y)<.9,'car remains visible as the camera begins following');
  }
});
