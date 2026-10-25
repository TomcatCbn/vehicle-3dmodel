import test from 'node:test';
import assert from 'node:assert/strict';
import { createDriveState, setDriving, stepDrive } from '../src/drive-state.js';
import { createState } from '../src/state.js';

test('driving accelerates smoothly to the chosen speed and integrates distance in metres',()=>{
  const drive=createDriveState();
  assert.equal(drive.speed,0);
  assert.equal(setDriving(drive,createState(),true),true);
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
  const drive=createDriveState(),vehicle=createState();
  setDriving(drive,vehicle,true);stepDrive(drive,20);
  const speed=drive.speed;
  setDriving(drive,vehicle,false);stepDrive(drive,.2);
  assert.ok(drive.speed>0&&drive.speed<speed);
  stepDrive(drive,20);
  assert.equal(drive.speed,0);
  const distance=drive.distance;stepDrive(drive,2);
  assert.equal(drive.distance,distance);
  setDriving(drive,vehicle,true);stepDrive(drive,.1);
  assert.ok(drive.speed>0);
});
test('doors and charging cable prevent starting; invalid time cannot reverse the car',()=>{
  const drive=createDriveState(),vehicle=createState();
  vehicle.doorsOpen=true;
  assert.equal(setDriving(drive,vehicle,true),false);
  vehicle.doorsOpen=false;vehicle.doorAngle=.4;
  assert.equal(setDriving(drive,vehicle,true),false);
  vehicle.doorAngle=0;vehicle.plugged=true;
  assert.equal(setDriving(drive,vehicle,true),false);
  vehicle.plugged=false;
  assert.equal(setDriving(drive,vehicle,true),true);
  drive.targetSpeed=1000;stepDrive(drive,20);
  assert.equal(drive.speed,100);
  const distance=drive.distance;
  stepDrive(drive,-1);stepDrive(drive,NaN);
  assert.equal(drive.distance,distance);
  drive.targetSpeed=-40;stepDrive(drive,20);
  assert.equal(drive.speed,0);
});
