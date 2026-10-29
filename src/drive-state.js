import { clamp } from './state.js';

export const WHEEL_RADIUS=.372;
export function createDriveState(){return {running:false,targetSpeed:40,speed:0,distance:0,direction:1};}
export function maxDriveSpeed(drive){return drive.direction===-1?20:100;}
export function setDirection(drive,direction){
  if(drive.speed!==0||(direction!==-1&&direction!==1))return false;
  drive.direction=direction;
  if(Number.isFinite(drive.targetSpeed))drive.targetSpeed=clamp(drive.targetSpeed,0,maxDriveSpeed(drive));
  return true;
}
export function setDriving(drive,vehicle,on){
  if(on){
    const doorsOpen=vehicle.doors?Object.values(vehicle.doors).some(d=>d.open||d.angle>.01):(vehicle.doorsOpen||vehicle.doorAngle>.01);
    const hoodOpen=vehicle.hood?.open??vehicle.hoodOpen,hoodAngle=vehicle.hood?.angle??vehicle.hoodAngle;
    const tgTarget=vehicle.tailgate?.target??vehicle.tailgateTarget,tgPos=vehicle.tailgate?.position??vehicle.tailgatePosition;
    if(doorsOpen||hoodOpen||hoodAngle>.01||tgTarget>.001||tgPos>.001||vehicle.plugged)return false;
  }
  drive.running=on;
  return true;
}
export function signedTargetSpeed(drive){
  if(!drive.running||!Number.isFinite(drive.targetSpeed))return 0;
  const magnitude=clamp(drive.targetSpeed,0,maxDriveSpeed(drive));
  return magnitude===0?0:drive.direction*magnitude;
}
export function isBraking(drive){return drive.speed!==0&&Math.abs(drive.speed)>Math.abs(signedTargetSpeed(drive));}
export function stepDrive(drive,dt){
  if(!Number.isFinite(dt)||dt<=0)return;
  const target=signedTargetSpeed(drive);
  const old=drive.speed,rate=Math.abs(target)>Math.abs(old)?10:24;
  const ramp=Math.min(dt,Math.abs(target-old)/rate);
  drive.speed=old+Math.sign(target-old)*rate*ramp;
  if(Math.abs(drive.speed-target)<1e-8)drive.speed=target;
  drive.distance+=((old+drive.speed)*.5*ramp+drive.speed*(dt-ramp))/3.6;
}
