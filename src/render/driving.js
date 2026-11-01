import * as THREE from 'three';
import { createDriveState, isBraking, maxDriveSpeed, setDirection, stepDrive, WHEEL_RADIUS } from '../drive-state.js';
import { createRaceTrack } from './racetrack.js';

function cameraOffset(view,pose){
  if(view==='track')return {position:new THREE.Vector3(135,145,145),target:new THREE.Vector3(0,0,-5)};
  const forward=new THREE.Vector3(-1,0,0).applyAxisAngle(new THREE.Vector3(0,1,0),pose.yaw);
  const side=new THREE.Vector3(0,0,1).applyAxisAngle(new THREE.Vector3(0,1,0),pose.yaw);
  if(view==='wheel')return {position:pose.position.clone().addScaledVector(forward,3.4).addScaledVector(side,3.6).add(new THREE.Vector3(0,1.3,0)),target:pose.position.clone().addScaledVector(forward,1.418).addScaledVector(side,.817).add(new THREE.Vector3(0,.45,0))};
  if(view==='side')return {position:pose.position.clone().addScaledVector(side,11).add(new THREE.Vector3(0,2.7,0)),target:pose.position.clone().add(new THREE.Vector3(0,.8,0))};
  const rear=view==='rear';
  return {position:pose.position.clone().addScaledVector(forward,rear?-8:8).addScaledVector(side,7).add(new THREE.Vector3(0,3.3,0)),target:pose.position.clone().addScaledVector(forward,rear?-2:2).add(new THREE.Vector3(0,.8,0))};
}

export function createDriving({canvas,camera,controls,scene,getState,resize,onEnter,onExit,onStage,toast,sendCommand,setVehiclePose,isManual=()=>false,onView=()=>{}}){
  const dialog=document.querySelector('#drive-dialog'),stage=document.querySelector('#drive-stage');
  const toggle=document.querySelector('#drive-toggle'),range=document.querySelector('#drive-range'),track=createRaceTrack(scene),home=canvas.parentNode,next=canvas.nextSibling;
  let active=false,drive=createDriveState(),snapshot,opener,view='front',pose,lastPosition,cornerBraking=false,cornerLimited=false;
  function flushOrbit(){const damping=controls.enableDamping;controls.enableDamping=false;controls.update();controls.enableDamping=damping;}
  function cameraPose(){if(!pose)return;const next=cameraOffset(view,pose);flushOrbit();controls.maxDistance=view==='track'?300:38;controls.target.copy(next.target);camera.position.copy(next.position);camera.fov=38;camera.updateProjectionMatrix();controls.update();}
  function followCamera(dt){if(!pose)return;if(isManual()){if(lastPosition&&view!=='track'){const delta=pose.position.clone().sub(lastPosition);camera.position.add(delta);controls.target.add(delta);}return;}const next=cameraOffset(view,pose);camera.position.copy(next.position);controls.target.copy(next.target);}
  function sync(){
    const speed=Math.abs(drive.speed),target=Math.abs(drive.targetSpeed),limit=maxDriveSpeed(drive),vehicle=getState();
    document.querySelector('#drive-speed').textContent=Math.round(speed);
    document.querySelector('#drive-distance').textContent=(Math.abs(drive.distance)/1000).toFixed(2);
    document.querySelector('#drive-target').textContent=target;
    const doorsOpen=vehicle.doors?Object.values(vehicle.doors).some(d=>d.open||d.angle>.01):(vehicle.doorsOpen||vehicle.doorAngle>.01);
    const hoodOpen=vehicle.hood?.open??vehicle.hoodOpen,hoodAngle=vehicle.hood?.angle??vehicle.hoodAngle;
    const tgTarget=vehicle.tailgate?.target??vehicle.tailgateTarget,tgPos=vehicle.tailgate?.position??vehicle.tailgatePosition;
    const blocked=doorsOpen||hoodOpen||hoodAngle>.01||tgTarget>.001||tgPos>.001||vehicle.plugged;
    document.querySelector('#drive-status').textContent=cornerBraking?'弯道减速':isBraking(drive)?'正在减速':drive.running?(cornerLimited?'弯道限速':speed<target-.5?'正在加速':'赛道行驶中'):speed>.1?'正在停车':blocked?'请关好车门、机盖、尾门并拔枪':'已停稳';
    if(pose){const left=THREE.MathUtils.radToDeg(pose.steeringByWheel.fl),right=THREE.MathUtils.radToDeg(pose.steeringByWheel.fr);document.querySelector('#drive-steering').textContent=`前轮转角 左 ${left.toFixed(1)}° / 右 ${right.toFixed(1)}°`;}
    toggle.textContent=drive.running?'停车':'起步';toggle.setAttribute('aria-pressed',String(drive.running));
    range.max=limit;range.value=target;range.style.setProperty('--range-progress',`${target/limit*100}%`);
    document.querySelector('#drive-speed-mid').textContent=limit/2;document.querySelector('#drive-speed-max').textContent=`${limit} km/h`;
    for(const button of document.querySelectorAll('[data-direction]')){const selected=Number(button.dataset.direction)===drive.direction;button.setAttribute('aria-pressed',String(selected));button.disabled=drive.speed!==0;}
  }
  async function startStop(){
    const on=!drive.running;
    console.log('[DRIVE] startStop on=',on,'page=',document.body.dataset.page);
    if(on){const ok=await sendCommand({type:'toggle_driving',on:true});console.log('[DRIVE] sendCommand ok=',ok);if(!ok){
      // sendCommand already toasted the real reason (e.g. "高压未闭合，请先上电至
      // Ready" or "请先关好车门"). Do not overwrite it with a generic hint.
      return;}}
    else await sendCommand({type:'toggle_driving',on:false});
    drive.running=on;console.log('[DRIVE] drive.running=',drive.running);sync();
  }
  const open=event=>{
    if(active)return;
    console.log('[DRIVE] open clicked, page=',document.body.dataset.page);
    flushOrbit();opener=event.currentTarget;
    snapshot={position:camera.position.clone(),target:controls.target.clone(),near:camera.near,far:camera.far,fov:camera.fov,opacity:canvas.style.opacity,label:canvas.getAttribute('aria-label'),minDistance:controls.minDistance,maxDistance:controls.maxDistance,minPolarAngle:controls.minPolarAngle,maxPolarAngle:controls.maxPolarAngle,enableZoom:controls.enableZoom,enablePan:controls.enablePan};
    active=true;drive=createDriveState();range.value=drive.targetSpeed;view='front';onEnter();pose=track.sample(0,1);setVehiclePose(pose);track.root.visible=true;onStage(true);document.body.classList.add('driving-open');stage.append(canvas);
    lastPosition=pose.position.clone();canvas.style.opacity='1';canvas.setAttribute('aria-label','赛车场中的可旋转车辆演示');camera.near=.05;camera.far=500;controls.enableZoom=true;controls.enablePan=false;controls.minDistance=4;controls.maxDistance=38;controls.minPolarAngle=.12;controls.maxPolarAngle=Math.PI/2-.03;
    dialog.showModal();resize();camera.clearViewOffset();cameraPose();sync();
    console.log('[DRIVE] dialog opened, active=',active,'drive.running=',drive.running);
    for(const button of document.querySelectorAll('[data-drive-view]'))button.setAttribute('aria-pressed',String(button.dataset.driveView===view));toggle.focus({preventScroll:true});
  };
  for(const button of document.querySelectorAll('[data-drive-open]')){button.disabled=false;button.addEventListener('click',open);}
  toggle.addEventListener('click',startStop);range.addEventListener('input',()=>{drive.targetSpeed=Number(range.value);sync();});
  for(const button of document.querySelectorAll('[data-direction]'))button.addEventListener('click',()=>{if(setDirection(drive,Number(button.dataset.direction)))sync();else toast('请先停车，待车辆停稳后再切换方向');});
  for(const button of document.querySelectorAll('[data-drive-view]'))button.addEventListener('click',()=>{view=button.dataset.driveView;onView();cameraPose();for(const other of document.querySelectorAll('[data-drive-view]'))other.setAttribute('aria-pressed',String(other===button));});
  document.querySelector('#drive-close').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('close',()=>{
    if(!active)return;sendCommand({type:'toggle_driving',on:false});flushOrbit();active=false;drive=createDriveState();track.root.visible=false;onStage(false);setVehiclePose(null);home.insertBefore(canvas,next);canvas.style.opacity=snapshot.opacity;canvas.setAttribute('aria-label',snapshot.label);document.body.classList.remove('driving-open');camera.near=snapshot.near;camera.far=snapshot.far;camera.fov=snapshot.fov;camera.updateProjectionMatrix();
    for(const key of ['minDistance','maxDistance','minPolarAngle','maxPolarAngle','enableZoom','enablePan'])controls[key]=snapshot[key];controls.target.copy(snapshot.target);camera.position.copy(snapshot.position);controls.update();pose=null;onExit();resize();opener?.focus({preventScroll:true});
  });
  document.addEventListener('visibilitychange',()=>{if(active&&document.hidden){drive.running=false;drive.speed=0;sendCommand({type:'toggle_driving',on:false});sync();}});
  return {get active(){return active;},stage,refit:cameraPose,
    update(dt){
      if(!active)return {wheelAngle:0,wheelAngles:null,steeringByWheel:null,braking:false,reversing:false,pose:null};
      const requested=drive.targetSpeed;
      let safeSpeed=requested;
      for(const ahead of[0,12,25,40]){const p=track.sample(drive.distance+ahead*drive.direction,drive.direction);safeSpeed=Math.min(safeSpeed,Math.sqrt(4.5/Math.max(Math.abs(p.curvature),.0001))*3.6);}
      cornerLimited=safeSpeed<requested-.5;cornerBraking=drive.running&&Math.abs(drive.speed)>safeSpeed+.5;drive.targetSpeed=safeSpeed;
      const braking=isBraking(drive);stepDrive(drive,dt);drive.targetSpeed=requested;pose=track.sample(drive.distance,drive.direction);track.update();setVehiclePose(pose);followCamera(dt);lastPosition=pose.position.clone();sync();
      return {wheelAngle:drive.distance/WHEEL_RADIUS,wheelAngles:pose.wheelAngles,steeringByWheel:pose.steeringByWheel,steeringAngle:pose.steeringByWheel.fl,braking,reversing:drive.speed<0,pose};
    },
  };
}
