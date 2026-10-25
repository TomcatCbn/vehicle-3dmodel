import { clamp } from './state.js';

export const WHEEL_RADIUS=.372;
export function createDriveState(){return {running:false,targetSpeed:40,speed:0,distance:0};}
export function setDriving(drive,vehicle,on){
  if(on&&(vehicle.doorsOpen||vehicle.doorAngle>.01||vehicle.hoodOpen||vehicle.hoodAngle>.01||vehicle.plugged))return false;
  drive.running=on;
  return true;
}
export function stepDrive(drive,dt){
  if(!Number.isFinite(dt)||dt<=0)return;
  const target=drive.running&&Number.isFinite(drive.targetSpeed)?clamp(drive.targetSpeed,0,100):0;
  const old=drive.speed,rate=target>old?10:24;
  const ramp=Math.min(dt,Math.abs(target-old)/rate);
  drive.speed=old+Math.sign(target-old)*rate*ramp;
  if(Math.abs(drive.speed-target)<1e-8)drive.speed=target;
  drive.distance+=((old+drive.speed)*.5*ramp+drive.speed*(dt-ramp))/3.6;
}
