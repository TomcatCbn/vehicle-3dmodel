import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { createStudio } from './render/studio.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { createVehicle } from './render/vehicle.js';
import { createInspection } from './render/inspection.js';
import { createDriving } from './render/driving.js';
import { createEntrance } from './render/entrance.js';
import { shutdownAfterEntrance } from './entrance-shutdown.js';
import { createPresentation } from './render/presentation.js';
import { createMirror, stepLocalMirror, followSnapshot, applyLocalCommand, clamp } from './state.js';
import { setupFileTransfer } from './file-transfer.js';
import { setupGarage } from './garage.js';
import './style.css';

const $ = selector => document.querySelector(selector);
const icons={lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',door:'<path d="M5 21V8l5-5h9v18H5Z"/><path d="M8 10V8l3-3h5v5H8Zm6 5h2"/>',window:'<path d="M4 18V8l4-4h12v14H4Zm0-6h16M8 4v8m-6 9h20"/>',wind:'<path d="M3 8h12a3 3 0 1 0-3-3M2 12h17a3 3 0 1 1-3 3M4 16h6a3 3 0 1 1-3 3"/>',battery:'<rect x="3" y="6" width="17" height="12" rx="2"/><path d="M22 10v4M7 10v4m4-4v4m4-4v4"/>',light:'<path d="M4 7h8v10H4zM15 8l5-3m-5 7h6m-6 4 5 3"/>',tail:'<path d="M5 5h10l4 4v6l-4 4H5zM9 9h6l2 3-2 3H9z"/>',ambient:'<path d="M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1m0-12.8-2.1 2.1m-8.6 8.6-2.1 2.1"/><circle cx="12" cy="12" r="3"/>',link:'<path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"/><path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/>'};
for(const node of document.querySelectorAll('[data-icon]'))node.innerHTML=`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[node.dataset.icon]}</svg>`;
const headlightLabels={off:'关闭',low:'近光',high:'远光'};

// Signal→GLB part mapping for AURA T6 (decision 7 mapping.parts).
// GLB uses side codes: name suffix _1 = side -1 = 左, _-1 = side 1 = 右.
// Verified against GLB extras: door_1_0=左前门, door_-1_0=右前门, etc.
const AURA_T6_MAPPING = {
  'door.fl':'door_1_0','door.fr':'door_-1_0','door.rl':'door_1_1','door.rr':'door_-1_1',
  'window.fl':'window_1_0','window.fr':'window_-1_0','window.rl':'window_1_1','window.rr':'window_-1_1',
  'hood':'hood','hood.strut.l':'bonnet_strut_1','hood.strut.r':'bonnet_strut_-1',
  'sunroof':'sunroof',
  'tailgate':'tailgate','tailgate.spoiler':'rear_spoiler','tailgate.glass':'rear_glass','tailgate.lamp':'tail_lights','tailgate.strut.l':'tailgate_strut_1','tailgate.strut.r':'tailgate_strut_-1',
  'plug.cable':'charge_cable','ac.airflow':'airflow',
};

let state = createMirror();
// Decision 08 D8.8 (revised): welcome page = showroom that is immediately
// drivable — kept unlocked + Ready so the visitor can start driving right
// away, fully independent of the live `state` (which the car page drives as a
// realistic simulation: locked + Standby by default, manual unlock/power-up).
const displayState = createMirror();
displayState.locked = false;
displayState.powerState = 'ready';
function renderState() {
  return document.body.dataset.page === 'welcome' ? displayState : state;
}
let toastTimer;
function toast(message){$('#toast').textContent=message;$('#toast').classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').classList.remove('visible'),2400);}

// Unified command sender: Tauri invoke with per-call error handling.
// No permanent "tauriFailed" flag — each call retries Tauri independently.
let latestSnapshot = null;
let unlistenStateChanged = null;
let eventReady = false;

// Check Tauri availability at call time (not module load time).
function tauriAvailable() {
  return typeof window !== 'undefined' &&
         Boolean(window.__TAURI__) &&
         Boolean(window.__TAURI__?.core?.invoke);
}

// ── Page routing (decision 8 D8.7) — three pages share canvas ──
function switchPage(page) {
  document.body.dataset.page = page;
  $('#garage-page').hidden = page !== 'garage';
  for (const link of document.querySelectorAll('nav .nav-link')) {
    link.classList.toggle('active', link.dataset.page === page);
  }
  if (page === 'garage') { window.scrollTo(0, 0); }
  // Notify the scene loop to swap per-page camera/view state (D8.8).
  dispatchEvent(new CustomEvent('app:page-switch', { detail: { page } }));
  // Welcome page = showroom that's immediately drivable: ensure it stays
  // unlocked + Ready on entry (displayState is the local drivable mirror).
  // Car page = realistic simulation: starts locked + Standby, user must
  // manually unlock (auto-enters Ready) — no auto-ready here.
  if (page === 'welcome') ensureDisplayReady();
  // Re-trigger scroll handler to update canvas visibility
  dispatchEvent(new Event('scroll'));
}
for (const link of document.querySelectorAll('nav .nav-link')) {
  link.addEventListener('click', (e) => { e.preventDefault(); switchPage(link.dataset.page); });
}
$('#welcome-car-control').addEventListener('click',()=>switchPage('car'));

async function sendCommand(command) {
  // Welcome page = showroom: operate on the local displayState so the live
  // backend-driven `state` (car page) stays unaffected. toggle_driving start
  // still respects the door/hood/tailgate/plug interlock against displayState.
  if (document.body.dataset.page === 'welcome') {
    const result = applyLocalCommand(displayState, command);
    if (!result.ok) { toast(result.error); return false; }
    return true;
  }
  if (tauriAvailable()) {
    try {
      const result = await window.__TAURI__.core.invoke('send_vehicle_command', { command });
      latestSnapshot = result;
      return true;
    } catch (e) {
      toast(String(e));
      return false;
    }
  }
  // Browser mode (car page): apply command directly to mirror state.
  const result = applyLocalCommand(state, command);
  if (!result.ok) { toast(result.error); return false; }
  return true;
}

// Keep the welcome-page displayState in its drivable showroom state: unlocked
// + Ready. Called on welcome-page entry. Local-only, never touches backend.
function ensureDisplayReady() {
  displayState.locked = false;
  displayState.powerState = 'ready';
}

function syncControls(){
  const anyDoorOpen = Object.values(state.doors).some(d => d.open);
  const maxWindowOpen = Math.max(0, ...Object.values(state.windows).map(w => w.open));
  const roofPercent = Math.round(state.sunroof.position * 100);
  const roofTarget = Math.round(state.sunroof.target * 100);
  for(const output of document.querySelectorAll('[data-sunroof-value]'))output.textContent=roofPercent+'%';
  for(const range of document.querySelectorAll('[data-sunroof-range]')){
    range.value=roofTarget;range.style.setProperty('--range-progress',roofTarget+'%');range.setAttribute('aria-valuetext','目标 '+roofTarget+'%，当前 '+roofPercent+'%');
  }
  const gatePercent=Math.round(state.tailgate.position*100),moving=Math.abs(state.tailgate.position-state.tailgate.target)>.0001;
  const gateStatus=moving?(state.tailgate.target>state.tailgate.position?'开启中 ':'关闭中 ')+gatePercent+'%':gatePercent===0?'已关闭':gatePercent===100?'已打开':'已暂停 '+gatePercent+'%';
  for(const output of document.querySelectorAll('[data-tailgate-status]'))output.textContent=gateStatus;
  for(const button of document.querySelectorAll('[data-tailgate-action]')){
    button.disabled=button.dataset.tailgateAction==='stop'?!moving:button.dataset.tailgateAction==='open'?state.tailgate.position>=.999&&state.tailgate.target>=.999:state.tailgate.position<=.001&&state.tailgate.target<=.001;
  }
  $('#lock-toggle').setAttribute('aria-checked',String(state.locked));$('#lock-status').textContent=state.locked?'已锁定':'已解锁';
  $('#door-status').textContent=anyDoorOpen?'已打开':'已关闭';$('#door-toggle').textContent=anyDoorOpen?'关闭':'打开';
  $('#hood-status').textContent=state.hood.open?'已打开':'已关闭';
  for(const button of document.querySelectorAll('[data-hood-toggle]')){
    button.textContent=state.hood.open?'关闭机盖':'打开机盖';button.setAttribute('aria-pressed',String(state.hood.open));
  }
  $('#headlight-status').textContent=headlightLabels[state.lighting.headlights];
  $('#headlight-toggle').textContent=headlightLabels[state.lighting.headlights];
  $('#headlight-toggle').setAttribute('aria-label',`前大灯，当前${headlightLabels[state.lighting.headlights]}，点击切换`);
  $('#tail-toggle').setAttribute('aria-checked',String(state.lighting.tailLights));
  $('#tail-status').textContent=state.lighting.tailLights?'已开启':'已关闭';
  for(const button of document.querySelectorAll('[data-ambient]'))button.setAttribute('aria-pressed',String(button.dataset.ambient===state.lighting.ambient));
  $('#ac-toggle').setAttribute('aria-checked',String(state.ac));$('#ac-status').textContent=state.ac?'运行中':'已关闭';$('#temperature').textContent=state.temperature;
  $('#window-value').innerHTML=`${Math.round(maxWindowOpen*100)}<span>%</span>`;
  $('#battery-value').textContent=Math.floor(state.battery);$('#battery-fill').style.width=`${state.battery}%`;
  $('#charge-status').textContent=state.charging?'正在充电 · 时间加速模拟':state.plugged?'充电枪已连接':'充电枪未连接';
  $('#plug-toggle').textContent=state.plugged?'拔出充电枪':'连接充电枪';$('#charge-toggle').disabled=!state.plugged||state.battery>=100;$('#charge-toggle').textContent=state.charging?'停止充电':'开始充电';
  // Individual door cells
  for(const cell of document.querySelectorAll('[data-door]')){
    const id = cell.dataset.door;
    const door = state.doors[id];
    if (!door) continue;
    cell.setAttribute('data-open', String(door.open));
    const statusEl = cell.querySelector('[data-door-status-id]');
    if (statusEl) statusEl.textContent = door.open ? '已打开' : '已关闭';
  }
  // Individual window sliders
  for(const range of document.querySelectorAll('[data-window-range-id]')){
    const id = range.dataset.windowRangeId;
    const win = state.windows[id];
    if (!win) continue;
    const pct = Math.round(win.target * 100);
    if (document.activeElement !== range) { range.value = pct; range.style.setProperty('--range-progress', pct + '%'); }
    const valEl = document.querySelector(`[data-window-value-id="${id}"]`);
    if (valEl) valEl.textContent = pct + '%';
  }
  // Power state UI (decision 8 D8.11/D8.12)
  const ps = state.powerState || 'standby';
  const psLabels = { sleep: 'Sleep', standby: 'Standby', ready: 'Ready' };
  $('#power-state-label').textContent = psLabels[ps] || ps;
  $('#power-state-label').dataset.state = ps;
  $('#power-on-btn').disabled = ps === 'ready';
  $('#power-off-btn').disabled = ps === 'sleep' || state.driving;
  document.body.dataset.power = ps;
  // Control panel visual state
  const panel = $('.control-panel');
  panel.classList.toggle('power-sleep', ps === 'sleep');
  panel.classList.toggle('power-standby', ps === 'standby');
  panel.classList.toggle('power-ready', ps === 'ready');
}

// ── Event handlers → sendCommand ──
// Interlock checks are handled by Rust interlock module; frontend no longer
// pre-checks to avoid state sync race conditions.
$('#lock-toggle').addEventListener('click', async () => {
  await sendCommand({ type: 'toggle_lock' });
});
$('#door-toggle').addEventListener('click', async () => {
  await sendCommand({ type: 'toggle_door', id: null });
});
$('#window-range').addEventListener('input', async event => {
  const target = Number(event.target.value) / 100;
  event.target.style.setProperty('--range-progress', `${event.target.value}%`);
  await sendCommand({ type: 'set_window', id: null, target });
});
$('#ac-toggle').addEventListener('click', async () => { await sendCommand({ type: 'toggle_ac' }); });
for(const [selector,delta] of [['#temp-down',-1],['#temp-up',1]])$(selector).addEventListener('click', async () => {
  await sendCommand({ type: 'set_temperature', value: clamp(state.temperature + delta, 16, 30) });
});
$('#plug-toggle').addEventListener('click', async () => {
  const wasPlugged = tauriAvailable() ? latestSnapshot?.plugged : state.plugged;
  await sendCommand({ type: 'toggle_plug' });
  toast(wasPlugged ? '充电枪已拔出' : '充电枪已连接');
});
$('#charge-toggle').addEventListener('click', async () => {
  await sendCommand({ type: 'toggle_charging' });
});
$('#reset-state').addEventListener('click', async () => {
  await sendCommand({ type: 'reset' });
  $('#window-range').value = 0; $('#window-range').style.setProperty('--range-progress', '0%');
  for(const range of document.querySelectorAll('[data-window-range-id]')){ range.value = 0; range.style.setProperty('--range-progress', '0%'); }
  toast('车辆已恢复初始状态');
});
for(const range of document.querySelectorAll('[data-sunroof-range]'))range.addEventListener('input', async event => {
  await sendCommand({ type: 'set_sunroof', target: clamp(Number(event.target.value) / 100) });
});
for(const button of document.querySelectorAll('[data-tailgate-action]'))button.addEventListener('click', async () => {
  await sendCommand({ type: 'tailgate', action: button.dataset.tailgateAction });
});
$('#headlight-toggle').addEventListener('click', async () => {
  const modes = ['off', 'low', 'high'];
  const index = modes.indexOf(state.lighting.headlights);
  await sendCommand({ type: 'set_headlight', mode: modes[(index + 1) % modes.length] });
});
$('#tail-toggle').addEventListener('click', async () => { await sendCommand({ type: 'toggle_tail_light' }); });
for(const button of document.querySelectorAll('[data-ambient]'))button.addEventListener('click', async () => {
  await sendCommand({ type: 'set_ambient', color: button.dataset.ambient });
});

// ── Power state controls (decision 8 D8.2/D8.11) ──
$('#power-on-btn').addEventListener('click', async () => {
  const ok = await sendCommand({ type: 'set_power', state: 'ready' });
  if (ok) toast('已上电至 Ready · 高压功能解锁');
});
$('#power-off-btn').addEventListener('click', async () => {
  const ok = await sendCommand({ type: 'set_power', state: 'sleep' });
  if (ok) toast('已熄火 · 进入休眠状态');
});
// BLE broadcast toggle (decision 8 D8.4 — independent of power state)
$('#ble-toggle').addEventListener('click', () => {
  const btn = $('#ble-toggle');
  const on = btn.getAttribute('aria-checked') === 'true';
  btn.setAttribute('aria-checked', String(!on));
  $('#ble-status').textContent = !on ? '广播中' : '关闭';
  $('#ble-indicator').classList.toggle('active', !on);
  $('#ble-indicator').title = !on ? 'BLE 广播中' : 'BLE 关闭';
  toast(!on ? 'BLE 广播已开启' : 'BLE 广播已关闭');
});

// ── Collapsible group headers ──
for(const header of document.querySelectorAll('.group-header')){
  header.addEventListener('click', () => {
    const expanded = header.getAttribute('aria-expanded') === 'true';
    header.setAttribute('aria-expanded', String(!expanded));
    header.nextElementSibling.hidden = expanded;
  });
}

// ── Individual door toggles ──
for(const cell of document.querySelectorAll('[data-door]')){
  cell.addEventListener('click', async () => {
    await sendCommand({ type: 'toggle_door', id: cell.dataset.door });
  });
}

// ── Individual window sliders ──
for(const range of document.querySelectorAll('[data-window-range-id]')){
  range.style.setProperty('--range-progress', range.value + '%');
  range.addEventListener('input', async event => {
    const id = event.target.dataset.windowRangeId;
    const target = Number(event.target.value) / 100;
    event.target.style.setProperty('--range-progress', event.target.value + '%');
    await sendCommand({ type: 'set_window', id, target });
  });
}

syncControls();

// In Tauri mode, listen for backend state-changed events.
if (tauriAvailable()) {
  try {
    window.__TAURI__.event.listen('signal://state-changed', (event) => {
      latestSnapshot = event.payload.state;
    }).then(unlisten => { unlistenStateChanged = unlisten; eventReady = true; })
      .catch(() => {});
  } catch {}
}

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
  const vehicle=createVehicle(gltf.scene, AURA_T6_MAPPING);scene.add(vehicle.root);$('#part-count').textContent=`${vehicle.parts.length} 个独立部件`;
  vehicle.setColor(document.querySelector('[data-color].selected').dataset.color);
  $('.telemetry>span:first-child').textContent='AURA T6 已就绪';
  const camera=new THREE.PerspectiveCamera(30,innerWidth/innerHeight,.1,150);
  const presentation=createPresentation(renderer,scene,camera);
  const controls=new OrbitControls(camera,canvas);controls.enableDamping=true;controls.dampingFactor=.07;controls.enablePan=false;controls.enableZoom=false;controls.minPolarAngle=.12;controls.maxPolarAngle=Math.PI/2-.03;controls.target.set(0,.7,0);
  const motionPreference=matchMedia('(prefers-reduced-motion: reduce)');
  let reduced=motionPreference.matches;
  let entranceVariant='front-logo';
  let layer='all', view='perspective', scrollProgress=0, progress=0, exploring=false, wasExploring=false, manualCamera=false, horizontalShift=innerWidth<=700?0:.13;
  // Per-page camera/view state (decision 08 D8.8: welcome & car 3D stay
  // independent). On page switch we snapshot the active vars back into the
  // departing page's slot and load the arriving page's slot, so dragging the
  // camera / scrolling the explode view on one page never bleeds into the other.
  let activePage=document.body.dataset.page;
  const pageCam={
    welcome:{view:'perspective',manualCamera:false,scrollProgress:0,progress:0,exploring:false,wasExploring:false,horizontalShift:innerWidth<=700?0:.13,layer:'all'},
    car:{view:'perspective',manualCamera:false,scrollProgress:0,progress:0,exploring:false,wasExploring:false,horizontalShift:innerWidth<=700?0:.13,layer:'all'},
  };
  function applyPageCam(page){
    Object.assign(pageCam[activePage],{view,manualCamera,scrollProgress,progress,exploring,wasExploring,horizontalShift,layer});
    activePage=page;
    const s=pageCam[page];
    view=s.view;manualCamera=s.manualCamera;scrollProgress=s.scrollProgress;progress=s.progress;exploring=s.exploring;wasExploring=s.wasExploring;horizontalShift=s.horizontalShift;layer=s.layer;
  }
  addEventListener('app:page-switch',e=>{applyPageCam(e.detail.page);});
  const targetCamera=new THREE.Vector3();
  function defaultCamera(){const mobile=innerWidth<=700;return new THREE.Vector3(...(mobile?[-14.5,4.7,15]:[-7.4,2.5,9.8]));}
  camera.position.copy(defaultCamera());controls.update();
  const entrance=createEntrance({vehicle,camera,controls,studio,home:defaultCamera,
    getVariant:()=>entranceVariant,
    onComplete(){
      // Car page (realistic sim): natural shutdown — lights off, lock, sleep.
      // Welcome page (showroom): keep the car as-is (unlocked + Ready) so the
      // visitor can start driving immediately; do NOT run shutdown.
      if(document.body.dataset.page==='welcome')return;
      shutdownAfterEntrance(()=>tauriAvailable()&&latestSnapshot?latestSnapshot:state,sendCommand)
        .catch(error=>{toast('自动熄火未完成：'+String(error));console.error(error);});
    },
    onChange(active){
      studio.setEntrance(active);
      document.body.classList.toggle('entrance-active',active);
      $('#entrance-overlay').hidden=!active;$('#lab').inert=active;
      $('.telemetry>span:first-child').textContent=active?'AURA T6 正在入场':'AURA T6 已就绪';
      if(!active&&document.activeElement===$('#skip-intro'))$('#replay-intro').focus({preventScroll:true});
    },
  });
  // Cancel before OrbitControls or a dialog saves its camera snapshot.
  document.addEventListener('pointerdown',event=>{
    if(entrance.active&&!event.target.closest('#entrance-overlay'))entrance.finish();
  },true);
  document.addEventListener('click',event=>{
    if(entrance.active&&!event.target.closest('#entrance-overlay, #replay-intro'))entrance.finish();
  },true);
  document.addEventListener('keydown',event=>{
    if(entrance.active&&event.key==='Escape'){event.preventDefault();entrance.finish();}
  });
  document.addEventListener('visibilitychange',()=>{if(document.hidden)entrance.finish();});
  motionPreference.addEventListener('change',event=>{reduced=event.matches;if(reduced)entrance.finish();});
  $('#skip-intro').addEventListener('click',()=>entrance.finish());
  controls.addEventListener('start',()=>{manualCamera=true;});
  let previousManual=false;
  const inspector=createInspection({canvas,camera,controls,vehicle,resize,getState:()=>renderState(),
    onEnter(){entrance.finish();previousManual=manualCamera;vehicle.root.rotation.y=0;vehicle.update(renderState(),0,'all');},
    onExit(){manualCamera=previousManual;readScroll();},
    onIsolate(value,box){studio.setIsolated(value,box);},
    onSelect(id){
      // M2: route through backend command — no direct state mutation.
      if(id==='hood'&&!renderState().hood.open)sendCommand({type:'toggle_hood'});
      if(id==='charge'&&!renderState().plugged)sendCommand({type:'toggle_plug'});
      vehicle.update(renderState(),0,'all');
    },
  });
  const driving=createDriving({canvas,camera,controls,scene,getState:()=>renderState(),resize,toast,sendCommand,
    onEnter(){entrance.finish();previousManual=manualCamera;manualCamera=false;vehicle.root.position.set(0,0,0);vehicle.root.rotation.y=0;vehicle.update(renderState(),0,'all');},
    onExit(){manualCamera=previousManual;readScroll();},
    onStage(value){studio.setDriving(value);},
    isManual:()=>manualCamera,
    onView(){manualCamera=false;},
    setVehiclePose(pose){
      if(pose){vehicle.root.position.copy(pose.position);vehicle.root.rotation.y=pose.yaw;studio.setVehiclePose(pose.position,pose.yaw);}
      else{vehicle.root.position.set(0,0,0);vehicle.root.rotation.y=0;studio.setVehiclePose(vehicle.root.position,0);}
    },
  });
  for(const button of document.querySelectorAll('[data-hood-toggle]')){button.disabled=false;button.addEventListener('click', async ()=>{
    await sendCommand({type:'toggle_hood'});
    if(inspector.active)inspector.refresh();
  });}

  // M3.1: file transfer UI (Tauri-only, enabled inside setupFileTransfer).
  setupFileTransfer();
  // Decision 08 D8.10: garage page — instance list + create flow.
  setupGarage();
  function resize(){
    const rect=inspector.active?inspector.stage.getBoundingClientRect():driving.active?driving.stage.getBoundingClientRect():{width:innerWidth,height:innerHeight};
    renderer.setSize(rect.width,rect.height);presentation.resize(rect.width,rect.height);camera.aspect=rect.width/rect.height;camera.updateProjectionMatrix();
    if(inspector.active)inspector.refit();
    if(driving.active)driving.refit();
  }
  addEventListener('resize',resize);resize();
  function readScroll(){
    if(entrance.active)entrance.finish();
    const page=document.body.dataset.page;
    if(page==='car'||page==='garage'){exploring=false;scrollProgress=0;$('#explore-hud').hidden=true;canvas.style.opacity=page==='garage'?'0':'1';return;}
    const rect=$('#explore').getBoundingClientRect();const mobile=innerWidth<=700;
    exploring=rect.top<innerHeight*.75;scrollProgress=clamp((-rect.top+innerHeight*.2)/(rect.height-innerHeight*.9));
    $('#explore-hud').hidden=!exploring;
    if(mobile&&!exploring){const upper=Math.max(0,scrollY-90);canvas.style.opacity=String(clamp(1-upper/440));}else canvas.style.opacity='1';
  }
  addEventListener('scroll',readScroll,{passive:true});readScroll();
  for(const button of document.querySelectorAll('[data-view]'))button.addEventListener('click',()=>{view=button.dataset.view;manualCamera=false;document.querySelectorAll('[data-view]').forEach(node=>{node.classList.toggle('selected',node===button);node.setAttribute('aria-pressed',String(node===button));});});
  for(const button of document.querySelectorAll('[data-entrance-variant]'))button.addEventListener('click',()=>{entranceVariant=button.dataset.entranceVariant;document.querySelectorAll('[data-entrance-variant]').forEach(node=>{node.classList.toggle('selected',node===button);node.setAttribute('aria-pressed',String(node===button));});});
  $('#reset-camera').addEventListener('click',()=>{manualCamera=false;view='perspective';controls.target.set(0,.7,0);document.querySelector('[data-view="perspective"]').click();});
  function entranceBlocked(){
    const s=renderState();
    const open=Object.values(s.doors).some(door=>door.open||door.angle>.001)||s.hood.open||s.hood.angle>.001||s.tailgate.target>.001||s.tailgate.position>.001;
    return open||s.plugged||s.driving;
  }
  function startEntrance(){
    if(entranceBlocked()){toast('请先停车、关好车门、机盖、尾门并拔枪，再重播出场');return;}
    if(reduced){toast('已启用减少动态效果，保持静态展示');return;}
    if(inspector.active||driving.active||exploring||document.body.dataset.page==='garage')return;
    manualCamera=false;view='perspective';
    document.querySelectorAll('[data-view]').forEach(node=>{const selected=node.dataset.view===view;node.classList.toggle('selected',selected);node.setAttribute('aria-pressed',String(selected));});
    entrance.start();
  }
  $('#replay-intro').addEventListener('click',()=>{startEntrance();if(entrance.active)$('#skip-intro').focus({preventScroll:true});});
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
    const id=hit.detail==='handle'?'handle':hit.detail?.startsWith('charge')?'charge':/前挡双目/.test(node.name)?'windscreen-sensor':/后视镜/.test(node.name)?'mirror':/前侧饰条/.test(node.name)?'sensor':/车顶激光雷达/.test(node.name)?'roof-sensor':/轮胎/.test(node.name)?'tire':/轮毂|制动/.test(node.name)?'wheel':/天窗|全景|行李架/.test(node.name)?'roof':/前舱|机盖/.test(node.name)?'hood':/纵向方灯/.test(node.name)?'lamp':/尾|后翼子板|后侧围|后挡|后备箱/.test(node.name)?'rear':'front';
    inspector.open(id,canvas);
  });
  let touchDistance=0;
  canvas.addEventListener('touchstart',event=>{if(event.touches.length===2)touchDistance=Math.hypot(event.touches[0].clientX-event.touches[1].clientX,event.touches[0].clientY-event.touches[1].clientY);},{passive:true});
  canvas.addEventListener('touchmove',event=>{if(inspector.active||driving.active||event.touches.length!==2)return;event.preventDefault();const next=Math.hypot(event.touches[0].clientX-event.touches[1].clientX,event.touches[0].clientY-event.touches[1].clientY);if(touchDistance>0){const direction=camera.position.clone().sub(controls.target);direction.setLength(clamp(direction.length()*touchDistance/next,5,19));camera.position.copy(controls.target).add(direction);manualCamera=true;}touchDistance=next;},{passive:false});
  const clock=new THREE.Clock();let lastUi=0,lastPoll=0;
  startEntrance();
  function frame(){
    const elapsed=clock.getDelta(),dt=Math.min(elapsed,.05);
    // Advance state: backend tick in Tauri mode, local tick in browser mode.
    if (tauriAvailable()) {
      if (!eventReady && clock.elapsedTime - lastPoll > 0.1) {
        lastPoll = clock.elapsedTime;
        window.__TAURI__.core.invoke('get_vehicle_state').then(s => { latestSnapshot = s; }).catch(() => {});
      }
      if (latestSnapshot) {
        followSnapshot(state, latestSnapshot, dt);
      } else {
        stepLocalMirror(state, dt);
      }
    } else {
      stepLocalMirror(state, dt);
    }
    if(entrance.active&&entranceBlocked())entrance.finish();
    // Presentation motion stays separate from signal state and the driving demo.
    if(entrance.active){
      const pose=entrance.update(elapsed);
      horizontalShift=(innerWidth<=700?0:.13)*pose.framing;
      camera.setViewOffset(innerWidth,innerHeight,innerWidth*horizontalShift,innerWidth<=700?innerHeight*.13*pose.framing:0,innerWidth,innerHeight);
      if($('#entrance-phase').textContent!==pose.phase)$('#entrance-phase').textContent=pose.phase;
      $('#entrance-progress').style.transform=`scaleX(${pose.progress})`;
      studio.update(0);vehicle.update(renderState(),0,'all',{wheelAngle:pose.wheelAngle,wheelAngles:pose.wheelAngles,steeringByWheel:pose.steeringByWheel,braking:pose.braking});presentation.render();
      if(clock.elapsedTime-lastUi>.1){syncControls();lastUi=clock.elapsedTime;}
      requestAnimationFrame(frame);return;
    }
    progress=reduced?scrollProgress:THREE.MathUtils.damp(progress,scrollProgress,5,dt);
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
    const motion=driving.update(Math.min(elapsed,.25));
    const drivingWheelAngles=motion.wheelAngles;
    motion.wheelAngle+=entrance.wheelAngle;
    motion.wheelAngles=Object.fromEntries(Object.entries(entrance.wheelAngles).map(([id,angle])=>[id,angle+(drivingWheelAngles?.[id]??motion.wheelAngle-entrance.wheelAngle)]));
    vehicle.update(renderState(),visibleProgress,!focused&&exploring?layer:'all',motion);controls.update();presentation.render();
    if(clock.elapsedTime-lastUi>.1){syncControls();$('#explosion-value').textContent=`${Math.round(progress*100)}%`;$('#explosion-fill').style.width=`${progress*100}%`;lastUi=clock.elapsedTime;}
    requestAnimationFrame(frame);
  }
  frame();
}
