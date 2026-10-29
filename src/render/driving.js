import * as THREE from 'three';
import { createDriveState, isBraking, maxDriveSpeed, setDirection, stepDrive, WHEEL_RADIUS } from '../drive-state.js';

const views={front:[-7,2.6,7.6],side:[-.8,1.8,10.5],rear:[7,2.6,7.6]};

function createRoad(scene){
  const root=new THREE.Group();root.visible=false;scene.add(root);
  const surface=new THREE.Mesh(new THREE.PlaneGeometry(220,24),new THREE.MeshStandardMaterial({color:'#343b40',roughness:.96,metalness:0}));
  surface.rotation.x=-Math.PI/2;surface.position.y=-.003;surface.receiveShadow=true;root.add(surface);
  const shoulderMaterial=new THREE.MeshStandardMaterial({color:'#81897e',roughness:1});
  for(const z of [-16,16]){
    const verge=new THREE.Mesh(new THREE.PlaneGeometry(220,8),shoulderMaterial);verge.rotation.x=-Math.PI/2;verge.position.set(0,-.006,z);verge.receiveShadow=true;root.add(verge);
  }
  const white=new THREE.MeshStandardMaterial({color:'#d3d7cc',roughness:.8});
  for(const z of [-5.55,5.55]){
    const edge=new THREE.Mesh(new THREE.PlaneGeometry(220,.10),white);edge.rotation.x=-Math.PI/2;edge.position.set(0,.003,z);root.add(edge);
  }
  const marks=new THREE.Group(),posts=new THREE.Group();root.add(marks,posts);
  const dashGeometry=new THREE.PlaneGeometry(3,.11);
  for(let x=-108;x<=108;x+=9)for(const z of [-1.85,1.85]){
    const dash=new THREE.Mesh(dashGeometry,white);dash.rotation.x=-Math.PI/2;dash.position.set(x,.004,z);marks.add(dash);
  }
  const postGeometry=new THREE.BoxGeometry(.13,.7,.13),reflectorGeometry=new THREE.BoxGeometry(.14,.12,.14);
  const reflectorMaterial=new THREE.MeshStandardMaterial({color:'#f1b86c',emissive:'#e19742',emissiveIntensity:.2});
  for(let x=-108;x<=108;x+=12)for(const z of [-6.1,6.1]){
    const post=new THREE.Mesh(postGeometry,white);post.position.set(x,.35,z);posts.add(post);
    const reflector=new THREE.Mesh(reflectorGeometry,reflectorMaterial);reflector.position.set(x,.57,z);posts.add(reflector);
  }
  return {root,update(distance){marks.position.x=distance%9;posts.position.x=distance%12;}};
}

export function createDriving({canvas,camera,controls,scene,getState,resize,onEnter,onExit,onStage,toast,sendCommand}){
  const dialog=document.querySelector('#drive-dialog'),stage=document.querySelector('#drive-stage');
  const toggle=document.querySelector('#drive-toggle'),range=document.querySelector('#drive-range');
  const road=createRoad(scene),home=canvas.parentNode,next=canvas.nextSibling;
  let active=false,drive=createDriveState(),snapshot,opener,view='front';
  function flushOrbit(){const damping=controls.enableDamping;controls.enableDamping=false;controls.update();controls.enableDamping=damping;}
  function sync(){
    const speed=Math.abs(drive.speed),target=Math.abs(drive.targetSpeed),limit=maxDriveSpeed(drive);
    document.querySelector('#drive-speed').textContent=Math.round(speed);
    document.querySelector('#drive-distance').textContent=(Math.abs(drive.distance)/1000).toFixed(2);
    document.querySelector('#drive-target').textContent=target;
    const vehicle=getState();
    const doorsOpen=vehicle.doors?Object.values(vehicle.doors).some(d=>d.open||d.angle>.01):(vehicle.doorsOpen||vehicle.doorAngle>.01);
    const hoodOpen=vehicle.hood?.open??vehicle.hoodOpen,hoodAngle=vehicle.hood?.angle??vehicle.hoodAngle;
    const tgTarget=vehicle.tailgate?.target??vehicle.tailgateTarget,tgPos=vehicle.tailgate?.position??vehicle.tailgatePosition;
    const blocked=doorsOpen||hoodOpen||hoodAngle>.01||tgTarget>.001||tgPos>.001||vehicle.plugged;
    document.querySelector('#drive-status').textContent=isBraking(drive)?'正在减速':drive.running?(speed<target-.5?'正在加速':'行驶中'):speed>.1?'正在停车':blocked?'请关好车门、机盖、尾门并拔枪':'已停稳';
    toggle.textContent=drive.running?'停车':'起步';toggle.setAttribute('aria-pressed',String(drive.running));
    range.max=limit;range.value=target;range.style.setProperty('--range-progress',`${target/limit*100}%`);
    document.querySelector('#drive-speed-mid').textContent=limit/2;
    document.querySelector('#drive-speed-max').textContent=`${limit} km/h`;
    for(const button of document.querySelectorAll('[data-direction]')){
      const selected=Number(button.dataset.direction)===drive.direction;
      button.setAttribute('aria-pressed',String(selected));button.disabled=drive.speed!==0;
    }
  }
  function fit(){
    const direction=new THREE.Vector3(...views[view]);
    // The vehicle remains fixed in a following camera; only the road advances.
    const target=new THREE.Vector3(0,.72,0);
    direction.sub(target).multiplyScalar(Math.max(1,.95/camera.aspect));
    flushOrbit();controls.target.copy(target);camera.position.copy(target).add(direction);controls.update();
  }
  async function startStop(){
    const on=!drive.running;
    if(on){
      const ok=await sendCommand({type:'toggle_driving',on:true});
      if(!ok){toast('请先关好车门、机盖和尾门，并拔出充电枪，再起步');return;}
    }else{
      await sendCommand({type:'toggle_driving',on:false});
    }
    drive.running=on;
    sync();
  }
  const open=event=>{
    if(active)return;
    flushOrbit();opener=event.currentTarget;
    snapshot={position:camera.position.clone(),target:controls.target.clone(),near:camera.near,opacity:canvas.style.opacity,label:canvas.getAttribute('aria-label'),
      minDistance:controls.minDistance,maxDistance:controls.maxDistance,minPolarAngle:controls.minPolarAngle,maxPolarAngle:controls.maxPolarAngle,enableZoom:controls.enableZoom,enablePan:controls.enablePan};
    active=true;drive=createDriveState();range.value=drive.targetSpeed;view='front';
    onEnter();road.root.visible=true;onStage(true);document.body.classList.add('driving-open');stage.append(canvas);
    canvas.style.opacity='1';canvas.setAttribute('aria-label','可旋转的车辆行驶三维演示');camera.near=.05;
    controls.enableZoom=true;controls.enablePan=false;controls.minDistance=5;controls.maxDistance=28;controls.minPolarAngle=.15;controls.maxPolarAngle=Math.PI/2-.04;
    dialog.showModal();resize();fit();sync();
    for(const button of document.querySelectorAll('[data-drive-view]'))button.setAttribute('aria-pressed',String(button.dataset.driveView===view));
    toggle.focus({preventScroll:true});
  };
  for(const button of document.querySelectorAll('[data-drive-open]')){button.disabled=false;button.addEventListener('click',open);}
  toggle.addEventListener('click',startStop);
  range.addEventListener('input',()=>{drive.targetSpeed=Number(range.value);sync();});
  for(const button of document.querySelectorAll('[data-direction]'))button.addEventListener('click',()=>{
    if(setDirection(drive,Number(button.dataset.direction)))sync();
    else toast('请先停车，待车辆停稳后再切换方向');
  });
  for(const button of document.querySelectorAll('[data-drive-view]'))button.addEventListener('click',()=>{
    view=button.dataset.driveView;fit();
    for(const other of document.querySelectorAll('[data-drive-view]'))other.setAttribute('aria-pressed',String(other===button));
  });
  document.querySelector('#drive-close').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('close',()=>{
    if(!active)return;
    flushOrbit();active=false;drive=createDriveState();road.root.visible=false;onStage(false);
    home.insertBefore(canvas,next);canvas.style.opacity=snapshot.opacity;canvas.setAttribute('aria-label',snapshot.label);document.body.classList.remove('driving-open');
    camera.near=snapshot.near;
    for(const key of ['minDistance','maxDistance','minPolarAngle','maxPolarAngle','enableZoom','enablePan'])controls[key]=snapshot[key];
    controls.target.copy(snapshot.target);camera.position.copy(snapshot.position);controls.update();onExit();resize();opener?.focus({preventScroll:true});
  });
  // A hidden tab must not silently resume motion when the user returns.
  document.addEventListener('visibilitychange',()=>{if(active&&document.hidden){drive.running=false;drive.speed=0;sync();}});
  return {get active(){return active;},stage,refit:fit,
    update(dt){
      if(!active)return {wheelAngle:0,braking:false,reversing:false};
      stepDrive(drive,dt);road.update(drive.distance);sync();
      return {wheelAngle:(drive.distance/WHEEL_RADIUS)%(Math.PI*2),braking:isBraking(drive),reversing:drive.speed<0};
    },
  };
}
