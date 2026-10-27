import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { createStudio } from './studio.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { createVehicle } from './vehicle.js';
import { createInspection } from './inspection.js';
import { createDriving } from './driving.js';
import { createState, stepVehicle, setCharging, clamp } from './state.js';
import './style.css';

const $ = selector => document.querySelector(selector);
const icons={lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',door:'<path d="M5 21V8l5-5h9v18H5Z"/><path d="M8 10V8l3-3h5v5H8Zm6 5h2"/>',window:'<path d="M4 18V8l4-4h12v14H4Zm0-6h16M8 4v8m-6 9h20"/>',wind:'<path d="M3 8h12a3 3 0 1 0-3-3M2 12h17a3 3 0 1 1-3 3M4 16h6a3 3 0 1 1-3 3"/>',battery:'<rect x="3" y="6" width="17" height="12" rx="2"/><path d="M22 10v4M7 10v4m4-4v4m4-4v4"/>',light:'<path d="M4 7h8v10H4zM15 8l5-3m-5 7h6m-6 4 5 3"/>',tail:'<path d="M5 5h10l4 4v6l-4 4H5zM9 9h6l2 3-2 3H9z"/>',ambient:'<path d="M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1m0-12.8-2.1 2.1m-8.6 8.6-2.1 2.1"/><circle cx="12" cy="12" r="3"/>'};
for(const node of document.querySelectorAll('[data-icon]'))node.innerHTML=`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[node.dataset.icon]}</svg>`;
const headlightLabels={off:'关闭',low:'近光',high:'远光'};
let state=createState();
let toastTimer;
function toast(message){$('#toast').textContent=message;$('#toast').classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').classList.remove('visible'),2400);}
function syncControls(){
  const roofPercent=Math.round(state.sunroofPosition*100),roofTarget=Math.round(state.sunroofTarget*100);
  for(const output of document.querySelectorAll('[data-sunroof-value]'))output.textContent=roofPercent+'%';
  for(const range of document.querySelectorAll('[data-sunroof-range]')){
    range.value=roofTarget;range.style.setProperty('--range-progress',roofTarget+'%');range.setAttribute('aria-valuetext','目标 '+roofTarget+'%，当前 '+roofPercent+'%');
  }
  const gatePercent=Math.round(state.tailgatePosition*100),moving=Math.abs(state.tailgatePosition-state.tailgateTarget)>.0001;
  const gateStatus=moving?(state.tailgateTarget>state.tailgatePosition?'开启中 ':'关闭中 ')+gatePercent+'%':gatePercent===0?'已关闭':gatePercent===100?'已打开':'已暂停 '+gatePercent+'%';
  for(const output of document.querySelectorAll('[data-tailgate-status]'))output.textContent=gateStatus;
  for(const button of document.querySelectorAll('[data-tailgate-action]')){
    button.disabled=button.dataset.tailgateAction==='stop'?!moving:button.dataset.tailgateAction==='open'?state.tailgatePosition>=.999&&state.tailgateTarget>=.999:state.tailgatePosition<=.001&&state.tailgateTarget<=.001;
  }
  $('#lock-toggle').setAttribute('aria-checked',String(state.locked));$('#lock-status').textContent=state.locked?'已锁定':'已解锁';
  $('#door-status').textContent=state.doorsOpen?'已打开':'已关闭';$('#door-toggle').textContent=state.doorsOpen?'关闭':'打开';
  $('#hood-status').textContent=state.hoodOpen?'已打开':'已关闭';
  for(const button of document.querySelectorAll('[data-hood-toggle]')){
    button.textContent=state.hoodOpen?'关闭机盖':'打开机盖';button.setAttribute('aria-pressed',String(state.hoodOpen));
  }
  $('#headlight-status').textContent=headlightLabels[state.lighting.headlights];
  $('#headlight-toggle').textContent=headlightLabels[state.lighting.headlights];
  $('#headlight-toggle').setAttribute('aria-label',`前大灯，当前${headlightLabels[state.lighting.headlights]}，点击切换`);
  $('#tail-toggle').setAttribute('aria-checked',String(state.lighting.tailLights));
  $('#tail-status').textContent=state.lighting.tailLights?'已开启':'已关闭';
  for(const button of document.querySelectorAll('[data-ambient]'))button.setAttribute('aria-pressed',String(button.dataset.ambient===state.lighting.ambient));
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
for(const range of document.querySelectorAll('[data-sunroof-range]'))range.addEventListener('input',event=>{state.sunroofTarget=clamp(Number(event.target.value)/100);syncControls();});
for(const button of document.querySelectorAll('[data-tailgate-action]'))button.addEventListener('click',()=>{
  state.tailgateTarget=button.dataset.tailgateAction==='open'?1:button.dataset.tailgateAction==='close'?0:state.tailgatePosition;syncControls();
});
$('#headlight-toggle').addEventListener('click',()=>{
  const modes=['off','low','high'],index=modes.indexOf(state.lighting.headlights);
  state.lighting.headlights=modes[(index+1)%modes.length];syncControls();
});
$('#tail-toggle').addEventListener('click',()=>{state.lighting.tailLights=!state.lighting.tailLights;syncControls();});
for(const button of document.querySelectorAll('[data-ambient]'))button.addEventListener('click',()=>{state.lighting.ambient=button.dataset.ambient;syncControls();});
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
  let previousManual=false;
  const inspector=createInspection({canvas,camera,controls,vehicle,resize,getState:()=>state,
    onEnter(){previousManual=manualCamera;vehicle.root.rotation.y=0;vehicle.update(state,0,'all');},
    onExit(){manualCamera=previousManual;readScroll();},
    onIsolate(value,box){studio.setIsolated(value,box);},
    onSelect(id){
      if(id==='hood'){state.hoodOpen=true;state.hoodAngle=1;}
      if(id==='handle')state.doorAngle=state.doorsOpen?1:0;
      vehicle.update(state,0,'all');
    },
  });
  const driving=createDriving({canvas,camera,controls,scene,getState:()=>state,resize,toast,
    onEnter(){previousManual=manualCamera;vehicle.root.rotation.y=0;vehicle.update(state,0,'all');},
    onExit(){manualCamera=previousManual;readScroll();},
    onStage(value){studio.setDriving(value);},
  });
  for(const button of document.querySelectorAll('[data-hood-toggle]')){button.disabled=false;button.addEventListener('click',()=>{
    state.hoodOpen=!state.hoodOpen;
    if(inspector.active){state.hoodAngle=state.hoodOpen?1:0;vehicle.update(state,0,'all');inspector.refresh();}
    syncControls();
  });}
  function resize(){
    const rect=inspector.active?inspector.stage.getBoundingClientRect():driving.active?driving.stage.getBoundingClientRect():{width:innerWidth,height:innerHeight};
    renderer.setSize(rect.width,rect.height);camera.aspect=rect.width/rect.height;camera.updateProjectionMatrix();
    if(inspector.active)inspector.refit();
    if(driving.active)driving.refit();
  }
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
  function pickPart(event){
    const rect=canvas.getBoundingClientRect();
    pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(pointer,camera);
    const hit=raycaster.intersectObjects(vehicle.root.children,true)[0];if(!hit)return;
    let node=hit.object;while(node.parent&&!node.userData.part)node=node.parent;return node.userData.part?{node,detail:hit.object.userData.detail}:null;
  }
  canvas.addEventListener('pointerup',event=>{if(inspector.active||driving.active||!pointerStart||Math.hypot(event.clientX-pointerStart[0],event.clientY-pointerStart[1])>5)return;
    const hit=pickPart(event);if(hit)toast(`${hit.node.name} · ${({body:'车身部件',cabin:'座舱部件',chassis:'底盘部件',power:'动力部件'})[hit.node.userData.layer]}`);
  });
  canvas.addEventListener('dblclick',event=>{
    if(inspector.active||driving.active)return;
    const hit=pickPart(event);if(!hit)return;const node=hit.node;
    const id=hit.detail==='handle'?'handle':/后视镜/.test(node.name)?'mirror':/前侧饰条/.test(node.name)?'sensor':/车顶激光雷达/.test(node.name)?'roof-sensor':/轮胎/.test(node.name)?'tire':/轮毂|制动/.test(node.name)?'wheel':/天窗|全景|行李架/.test(node.name)?'roof':/前舱|机盖/.test(node.name)?'hood':/纵向方灯/.test(node.name)?'lamp':/尾|后翼子板|后侧围|后挡|后备箱/.test(node.name)?'rear':'front';
    inspector.open(id,canvas);
  });
  let touchDistance=0;
  canvas.addEventListener('touchstart',event=>{if(event.touches.length===2)touchDistance=Math.hypot(event.touches[0].clientX-event.touches[1].clientX,event.touches[0].clientY-event.touches[1].clientY);},{passive:true});
  canvas.addEventListener('touchmove',event=>{if(inspector.active||driving.active||event.touches.length!==2)return;event.preventDefault();const next=Math.hypot(event.touches[0].clientX-event.touches[1].clientX,event.touches[0].clientY-event.touches[1].clientY);if(touchDistance>0){const direction=camera.position.clone().sub(controls.target);direction.setLength(clamp(direction.length()*touchDistance/next,5,19));camera.position.copy(controls.target).add(direction);manualCamera=true;}touchDistance=next;},{passive:false});
  const clock=new THREE.Clock();let lastUi=0;
  function frame(){
    const dt=Math.min(clock.getDelta(),.05);stepVehicle(state,dt);progress=reduced?scrollProgress:THREE.MathUtils.damp(progress,scrollProgress,5,dt);
    const focused=inspector.active||driving.active;
    if(!focused&&exploring!==wasExploring){manualCamera=false;wasExploring=exploring;}
    if(!focused&&!manualCamera){
      if(exploring){targetCamera.set(...(innerWidth<=700?[-19,11,20]:[-13.5,8.6,14.5]));controls.target.lerp(new THREE.Vector3(0,.65,0),.04);}
      else if(view==='side')targetCamera.set(0,1.4,innerWidth<=700?24:13);
      else if(view==='top')targetCamera.set(-.01,innerWidth<=700?24:12.5,-.01);
      else targetCamera.copy(defaultCamera());
      camera.position.lerp(targetCamera,reduced?1:.035);
    }
    if(focused)camera.clearViewOffset();
    else{
      horizontalShift=THREE.MathUtils.damp(horizontalShift,innerWidth<=700?0:exploring?-.13:.13,4,dt);
      camera.setViewOffset(innerWidth,innerHeight,innerWidth*horizontalShift,innerWidth<=700?innerHeight*(exploring?-.22:.13):0,innerWidth,innerHeight);
    }
    vehicle.root.rotation.y=!focused&&exploring?progress*.2:0;
    const visibleProgress=focused?0:progress;
    studio.update(visibleProgress);
    const motion=driving.update(dt);
    vehicle.update(state,visibleProgress,!focused&&exploring?layer:'all',motion);controls.update();renderer.render(scene,camera);
    if(clock.elapsedTime-lastUi>.1){syncControls();$('#explosion-value').textContent=`${Math.round(progress*100)}%`;$('#explosion-fill').style.width=`${progress*100}%`;lastUi=clock.elapsedTime;}
    requestAnimationFrame(frame);
  }
  frame();
}
