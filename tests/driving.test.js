import test from 'node:test';
import assert from 'node:assert/strict';
import { createDriveState, isBraking, maxDriveSpeed, setDirection, signedTargetSpeed, stepDrive } from '../src/drive-state.js';
import { createMirror, applyLocalCommand } from '../src/state.js';

// ── Driving dynamics tests ──

test('driving accelerates smoothly to the chosen speed and integrates distance in metres',()=>{
  const drive=createDriveState();
  assert.equal(drive.speed,0);
  drive.running=true;
  drive.targetSpeed=36;
  stepDrive(drive,1);
  assert.ok(drive.speed>0&&drive.speed<36);
  for(let i=0;i<200;i++)stepDrive(drive,.1);
  assert.equal(drive.speed,36);
  const before=drive.distance;
  stepDrive(drive,1);
  assert.ok(Math.abs(drive.distance-before-10)<1e-8);
});
test('parking decelerates to zero, holds the road still, and permits another start',()=>{
  const drive=createDriveState();
  drive.running=true;stepDrive(drive,20);
  const speed=drive.speed;
  drive.running=false;stepDrive(drive,.2);
  assert.ok(drive.speed>0&&drive.speed<speed);
  stepDrive(drive,20);
  assert.equal(drive.speed,0);
  const distance=drive.distance;stepDrive(drive,2);
  assert.equal(drive.distance,distance);
  drive.running=true;stepDrive(drive,.1);
  assert.ok(drive.speed>0);
});
test('speed clamps to max, negative or NaN dt does not advance, negative target holds zero',()=>{
  const drive=createDriveState();
  drive.running=true;
  drive.targetSpeed=1000;stepDrive(drive,20);
  assert.equal(drive.speed,100);
  const distance=drive.distance;
  stepDrive(drive,-1);stepDrive(drive,NaN);
  assert.equal(drive.distance,distance);
  drive.targetSpeed=-40;stepDrive(drive,20);
  assert.equal(drive.speed,0);
});

// ── Interlock tests (browser-mode applyLocalCommand, mirrors Rust can_start_driving) ──

test('interlock: doors and charging cable prevent starting',()=>{
  const state=createMirror();
  assert.equal(applyLocalCommand(state,{type:'toggle_driving',on:true}).ok,true);
  state.doors.fl.open=true;
  assert.equal(applyLocalCommand(state,{type:'toggle_driving',on:true}).ok,false);
  state.doors.fl.open=false;state.doors.fl.angle=.4;
  assert.equal(applyLocalCommand(state,{type:'toggle_driving',on:true}).ok,false);
  state.doors.fl.angle=0;state.plugged=true;
  assert.equal(applyLocalCommand(state,{type:'toggle_driving',on:true}).ok,false);
  state.plugged=false;
  assert.equal(applyLocalCommand(state,{type:'toggle_driving',on:true}).ok,true);
});
test('interlock: an open or still closing bonnet prevents starting',()=>{
  const state=createMirror();
  state.hood.open=true;
  assert.equal(applyLocalCommand(state,{type:'toggle_driving',on:true}).ok,false);
  state.hood.open=false;state.hood.angle=.4;
  assert.equal(applyLocalCommand(state,{type:'toggle_driving',on:true}).ok,false);
  state.hood.angle=0;
  assert.equal(applyLocalCommand(state,{type:'toggle_driving',on:true}).ok,true);
});
test('interlock: tailgate must be fully closed before driving, while an open sunroof is allowed',()=>{
  const state=createMirror();
  state.tailgate.target=1;
  assert.equal(applyLocalCommand(state,{type:'toggle_driving',on:true}).ok,false);
  state.tailgate.target=0;state.tailgate.position=.3;
  assert.equal(applyLocalCommand(state,{type:'toggle_driving',on:true}).ok,false);
  state.tailgate.position=0;state.sunroof.target=1;state.sunroof.position=1;
  assert.equal(applyLocalCommand(state,{type:'toggle_driving',on:true}).ok,true);
});
test('interlock: stopping is always allowed regardless of vehicle state',()=>{
  const state=createMirror();
  state.doors.fl.open=true;
  state.plugged=true;
  state.hood.open=true;
  assert.equal(applyLocalCommand(state,{type:'toggle_driving',on:false}).ok,true);
});

// ── Direction and speed dynamics tests ──

test('direction changes require standstill and reverse clamps speed, distance, and braking',()=>{
  const drive=createDriveState();
  assert.equal(drive.direction,1);
  assert.equal(maxDriveSpeed(drive),100);
  assert.equal(signedTargetSpeed(drive),0);
  drive.running=true;stepDrive(drive,1);
  assert.equal(setDirection(drive,-1),false);
  assert.equal(drive.direction,1);
  drive.running=false;stepDrive(drive,20);
  assert.equal(drive.speed,0);
  assert.equal(isBraking(drive),false);
  drive.targetSpeed=100;
  assert.equal(setDirection(drive,0),false);
  assert.equal(drive.direction,1);
  assert.equal(drive.targetSpeed,100);
  assert.equal(setDirection(drive,-1),true);
  assert.equal(drive.direction,-1);
  assert.equal(drive.targetSpeed,20);
  assert.equal(maxDriveSpeed(drive),20);
  drive.targetSpeed=100;
  drive.running=true;
  assert.equal(signedTargetSpeed(drive),-20);
  stepDrive(drive,20);
  assert.equal(drive.speed,-20);
  assert.ok(drive.distance<0);
  drive.running=false;
  assert.equal(isBraking(drive),true);
  stepDrive(drive,20);
  assert.equal(drive.speed,0);
  assert.equal(isBraking(drive),false);
});
test('reverse accelerates negatively and brakes to a standstill without overshooting',()=>{
  const drive=createDriveState();
  assert.equal(setDirection(drive,-1),true);
  drive.running=true;drive.targetSpeed=20;
  stepDrive(drive,1);
  assert.equal(drive.speed,-10);
  drive.targetSpeed=0;stepDrive(drive,.25);
  assert.equal(drive.speed,-4);
  stepDrive(drive,1);
  assert.equal(drive.speed,0);
});
test('constant speed is not braking, while requested deceleration is braking until settled',()=>{
  const drive=createDriveState();
  drive.running=true;stepDrive(drive,20);
  assert.equal(drive.speed,40);
  assert.equal(isBraking(drive),false);
  drive.targetSpeed=10;
  assert.equal(isBraking(drive),true);
  stepDrive(drive,20);
  assert.equal(drive.speed,10);
  assert.equal(isBraking(drive),false);
  drive.targetSpeed=Infinity;
  assert.equal(signedTargetSpeed(drive),0);
});
test('direction changes preserve non-finite targets and their zero motion target',()=>{
  for(const targetSpeed of [Infinity,NaN]){
    const drive=createDriveState();
    drive.targetSpeed=targetSpeed;
    assert.equal(setDirection(drive,-1),true);
    assert.equal(drive.targetSpeed,targetSpeed);
    drive.running=true;
    assert.equal(signedTargetSpeed(drive),0);
    stepDrive(drive,1);
    assert.equal(drive.speed,0);
  }
});
