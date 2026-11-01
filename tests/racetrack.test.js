import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { sampleRaceTrack as sample } from '../src/render/racetrack.js';
const up=new THREE.Vector3(0,1,0),length=sample(0).length;
const wheelPosition=(pose,id)=>new THREE.Vector3(id[0]==='f'?-1.418:1.418,0,id[1]==='l'?-.817:.817).applyAxisAngle(up,pose.yaw).add(pose.position);

test('wheel headings agree with actual contact-point travel around the entire circuit',()=>{
  for(let i=0;i<400;i++){
    const s=length*i/400,p=sample(s),before=sample(s-.002),after=sample(s+.002);
    for(const id of ['fl','fr','rl','rr']){
      const velocity=wheelPosition(after,id).sub(wheelPosition(before,id)).normalize();
      const heading=new THREE.Vector3(-1,0,0).applyAxisAngle(up,p.yaw+(p.steeringByWheel[id]??0));
      assert.ok(velocity.dot(heading)>.99999,`wheel ${id} slides at sample ${i}`);
    }
  }
});

test('inner and outer front wheels steer differently and accumulate distinct rolling distances',()=>{
  const p=Array.from({length:200},(_,i)=>sample(length*i/200)).sort((a,b)=>Math.abs(b.curvature)-Math.abs(a.curvature))[0];
  assert.ok(Math.abs(p.steeringByWheel.fl-p.steeringByWheel.fr)>.01);
  assert.ok(Math.max(Math.abs(p.steeringByWheel.fl),Math.abs(p.steeringByWheel.fr))<Math.PI/4);
  const end=sample(length);assert.ok(Math.abs(end.wheelAngles.rl-end.wheelAngles.rr)>1);
});

test('reverse preserves heading and retraces the circuit with negative wheel travel',()=>{
  const a=sample(0,1),b=sample(0,-1),back=sample(-2,-1);
  assert.equal(a.yaw,b.yaw);assert.ok(a.position.distanceTo(b.position)<1e-9);
  for(const id of ['fl','fr','rl','rr'])assert.ok(back.wheelAngles[id]<0);
  const seamBefore=sample(length-.001),seamAfter=sample(length+.001);
  assert.ok(seamAfter.position.distanceTo(seamBefore.position)<.01);
  for(const id of ['fl','fr','rl','rr'])assert.ok(Math.abs(seamAfter.wheelAngles[id]-seamBefore.wheelAngles[id])<.02);
});
