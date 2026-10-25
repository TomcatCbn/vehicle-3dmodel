import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { createStudio } from './studio.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { createVehicle } from './vehicle.js';
import { createState, stepVehicle, setCharging, clamp } from './state.js';
import './style.css';

const $ = selector => document.querySelector(selector);
const icons={lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',door:'<path d="M5 21V8l5-5h9v18H5Z"/><path d="M8 10V8l3-3h5v5H8Zm6 5h2"/>',window:'<path d="M4 18V8l4-4h12v14H4Zm0-6h16M8 4v8m-6 9h20"/>',wind:'<path d="M3 8h12a3 3 0 1 0-3-3M2 12h17a3 3 0 1 1-3 3M4 16h6a3 3 0 1 1-3 3"/>',battery:'<rect x="3" y="6" width="17" height="12" rx="2"/><path d="M22 10v4M7 10v4m4-4v4m4-4v4"/>'};
for(const node of document.querySelectorAll('[data-icon]'))node.innerHTML=`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[node.dataset.icon]}</svg>`;
let state=createState();
let toastTimer;
function toast(message){$('#toast').textContent=message;$('#toast').classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').classList.remove('visible'),2400);}
function syncControls(){
  $('#lock-toggle').setAttribute('aria-checked',String(state.locked));$('#lock-status').textContent=state.locked?'已锁定':'已解锁';
  $('#door-status').textContent=state.doorsOpen?'已打开':'已关闭';$('#door-toggle').textContent=state.doorsOpen?'关闭':'打开';
  $('#ac-toggle').setAttribute('aria-checked',String(state.ac));$('#ac-status').textContent=state.ac?'运行中':'已关闭';$('#temperature').textContent=state.temperature;
  $('#window-value').innerHTML=`${Math.round(state.windowOpen*100)}<span>%</span>`;
  $('#battery-value').textContent=Math.floor(state.battery);$('#battery-fill').style.width=`${state.battery}%`;
  $('#charge-status').textContent=state.charging?'正在充电 · 时间加速模拟':state.plugged?'充电枪已连接':'充电枪未连接';
  $('#plug-toggle').textContent=state.plugged?'拔出充电枪':'连接充电枪';$('#charge-toggle').disabled=!state.plugged||state.battery>=100;$('#charge-toggle').textContent=state.charging?'停止充电':'开始充电';
}
$('#lock-toggle').addEventListener('click',()=>{if(!state.locked&&state.doorsOpen){toast('请先关闭车门，再锁定车辆');return;}state.locked=!state.locked;syncControls();toast(state.locked?'车辆已锁定':'车辆已解锁');});
$('#door-toggle').addEventListener('click',()=>{if(state.locked){toast('请先解锁车辆');return;}state.doorsOpen=!state.doorsOpen;syncControls();});
$('#window-range').addEventListener('input',event=>{state.windowTarget=Number(event.target.value)/100;event.target.style.setProperty('--range-progress',`${event.target.value}%`);});
$('#ac-toggle').addEventListener('click',()=>{state.ac=!state.ac;syncControls();});
for(const [selector,delta] of [['#temp-down',-1],['#temp-up',1]])$(selector).addEventListener('click',()=>{state.temperature=clamp(state.temperature+delta,16,30);syncControls();});
$('#plug-toggle').addEventListener('click',()=>{state.plugged=!state.plugged;if(!state.plugged)state.charging=false;syncControls();toast(state.plugged?'充电枪已连接':'充电枪已拔出');});
$('#charge-toggle').addEventListener('click',()=>{if(setCharging(state,!state.charging)){syncControls();toast(state.charging?'开始充电，电量按加速时间增长':'充电已停止');}});
$('#reset-state').addEventListener('click',()=>{state=createState();$('#window-range').value=0;$('#window-range').style.setProperty('--range-progress','0%');syncControls();toast('车辆已恢复初始状态');});
syncControls();

startScene().catch(error => { $('#webgl-error').hidden=false; $('#webgl-error').textContent='模型暂时无法加载，请检查本地模型文件与浏览器 WebGL 支持后刷新。'; $('.telemetry>span:first-child').textContent='模型加载失败'; $('.live-indicator').textContent='场景不可用'; console.error(error); });

async function startScene(){
  const canvas=$('#vehicle-canvas');
  const renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:true,powerPreference:'high-performance'});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio,1.8));renderer.setSize(innerWidth,innerHeight);
  renderer.toneMapping=THREE.AgXToneMapping;renderer.toneMappingExposure=.9;
  renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.VSMShadowMap;
  const scene=new THREE.Scene();
  const studio=await createStudio(renderer,scene);
  $('.telemetry>span:first-child').textContent='正在加载 AURA T6…';
  const gltf=await new GLTFLoader().loadAsync('/models/aura-t6.glb');
  const vehicle=createVehicle(gltf.scene);scene.add(vehicle.root);$('#part-count').textContent=`${vehicle.parts.length} 个独立部件`;
  $('.telemetry>span:first-child').textContent='AURA T6 已就绪';
  const camera=new THREE.PerspectiveCamera(30,innerWidth/innerHeight,.1,150);
  const controls=new OrbitControls(camera,canvas);controls.enableDamping=true;controls.dampingFactor=.07;controls.enablePan=false;controls.enableZoom=false;controls.minPolarAngle=.12;controls.maxPolarAngle=Math.PI/2-.03;controls.target.set(0,.7,0);
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  let layer='all', view='perspective', scrollProgress=0, progress=0, exploring=false, wasExploring=false, manualCamera=false, horizontalShift=innerWidth<=700?0:.13;
  const targetCamera=new THREE.Vector3();
  function defaultCamera(){const mobile=innerWidth<=700;return new THREE.Vector3(...(mobile?[-14.5,4.7,15]:[-7.4,2.5,9.8]));}
  camera.position.copy(defaultCamera());controls.update();
  controls.addEventListener('start',()=>{manualCamera=true;});
  function resize(){renderer.setSize(innerWidth,innerHeight);camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();if(!manualCamera)camera.position.copy(defaultCamera());}
  addEventListener('resize',resize);resize();
  function readScroll(){const rect=$('#explore').getBoundingClientRect();const mobile=innerWidth<=700;exploring=rect.top<innerHeight*.75;scrollProgress=clamp((-rect.top+innerHeight*.2)/(rect.height-innerHeight*.9));
    $('#explore-hud').hidden=!exploring;$('#nav-control').classList.toggle('active',!exploring);$('#nav-explore').classList.toggle('active',exploring);
    if(mobile&&!exploring){const upper=Math.max(0,scrollY-90);canvas.style.opacity=String(clamp(1-upper/440));}else canvas.style.opacity='1';
  }
  addEventListener('scroll',readScroll,{passive:true});readScroll();
  for(const button of document.querySelectorAll('[data-view]'))button.addEventListener('click',()=>{view=button.dataset.view;manualCamera=false;document.querySelectorAll('[data-view]').forEach(node=>{node.classList.toggle('selected',node===button);node.setAttribute('aria-pressed',String(node===button));});});
  $('#reset-camera').addEventListener('click',()=>{manualCamera=false;view='perspective';controls.target.set(0,.7,0);document.querySelector('[data-view="perspective"]').click();});
  for(const button of document.querySelectorAll('[data-color]'))button.addEventListener('click',()=>{vehicle.setColor(button.dataset.color);$('#color-name').textContent=button.getAttribute('aria-label');document.querySelectorAll('[data-color]').forEach(node=>{node.classList.toggle('selected',node===button);node.setAttribute('aria-pressed',String(node===button));});});
  for(const button of document.querySelectorAll('[data-layer]'))button.addEventListener('click',()=>{layer=button.dataset.layer;document.querySelectorAll('[data-layer]').forEach(node=>node.classList.toggle('selected',node===button));});
  const raycaster=new THREE.Raycaster();const pointer=new THREE.Vector2();let pointerStart=null;
  canvas.addEventListener('pointerdown',event=>{pointerStart=[event.clientX,event.clientY];});
  canvas.addEventListener('pointerup',event=>{if(!pointerStart||Math.hypot(event.clientX-pointerStart[0],event.clientY-pointerStart[1])>5)return;
    pointer.set(event.clientX/innerWidth*2-1,-event.clientY/innerHeight*2+1);raycaster.setFromCamera(pointer,camera);const hit=raycaster.intersectObjects(vehicle.root.children,true)[0];if(!hit)return;
    let node=hit.object;while(node.parent&&!node.userData.part)node=node.parent;if(node.userData.part)toast(`${node.name} · ${({body:'车身部件',cabin:'座舱部件',chassis:'底盘部件',power:'动力部件'})[node.userData.layer]}`);
  });
  let touchDistance=0;
  canvas.addEventListener('touchstart',event=>{if(event.touches.length===2)touchDistance=Math.hypot(event.touches[0].clientX-event.touches[1].clientX,event.touches[0].clientY-event.touches[1].clientY);},{passive:true});
  canvas.addEventListener('touchmove',event=>{if(event.touches.length!==2)return;event.preventDefault();const next=Math.hypot(event.touches[0].clientX-event.touches[1].clientX,event.touches[0].clientY-event.touches[1].clientY);if(touchDistance>0){const direction=camera.position.clone().sub(controls.target);direction.setLength(clamp(direction.length()*touchDistance/next,5,19));camera.position.copy(controls.target).add(direction);manualCamera=true;}touchDistance=next;},{passive:false});
  const clock=new THREE.Clock();let lastUi=0;
  function frame(){
    const dt=Math.min(clock.getDelta(),.05);stepVehicle(state,dt);progress=reduced?scrollProgress:THREE.MathUtils.damp(progress,scrollProgress,5,dt);
    if(exploring!==wasExploring){manualCamera=false;wasExploring=exploring;}
    if(!manualCamera){
      if(exploring){targetCamera.set(...(innerWidth<=700?[-19,11,20]:[-13.5,8.6,14.5]));controls.target.lerp(new THREE.Vector3(0,.65,0),.04);}
      else if(view==='side')targetCamera.set(0,1.4,innerWidth<=700?24:13);
      else if(view==='top')targetCamera.set(-.01,innerWidth<=700?24:12.5,-.01);
      else targetCamera.copy(defaultCamera());
      camera.position.lerp(targetCamera,reduced?1:.035);
    }
    horizontalShift=THREE.MathUtils.damp(horizontalShift,innerWidth<=700?0:exploring?-.13:.13,4,dt);
    camera.setViewOffset(innerWidth,innerHeight,innerWidth*horizontalShift,innerWidth<=700?innerHeight*(exploring?-.22:.13):0,innerWidth,innerHeight);
    vehicle.root.rotation.y=exploring?progress*.2:0;
    studio.update(progress);
    vehicle.update(state,progress,exploring?layer:'all');controls.update();renderer.render(scene,camera);
    if(clock.elapsedTime-lastUi>.1){syncControls();$('#explosion-value').textContent=`${Math.round(progress*100)}%`;$('#explosion-fill').style.width=`${progress*100}%`;lastUi=clock.elapsedTime;}
    requestAnimationFrame(frame);
  }
  frame();
}
