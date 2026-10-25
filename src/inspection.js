import * as THREE from 'three';

export const INSPECTION_VIEWS=[
  {id:'front',label:'前脸',description:'机盖、前围与分体灯组',direction:[-1,.16,.22]},
  {id:'rear',label:'车尾',description:'尾门、后肩线与下包围',direction:[1,.18,.42]},
  {id:'lamp',label:'车灯',description:'右侧主灯的透镜与反射饰板',direction:[-1,.05,.35],isolated:true},
  {id:'badge',label:'车标',description:'前车标的字面、外环与底座',direction:[-1,.27,.03],isolated:true},
  {id:'wheel',label:'轮毂',description:'右前轮毂、轮胎与制动结构',direction:[.10,.10,1],isolated:true},
];
export function getInspectionMeshes(vehicle,id){
  const names={
    front:['前保险杠','前舱盖','前贯穿灯带','左纵向方灯','右纵向方灯','左前翼子板','右前翼子板'],
    rear:['尾门','后保险杠','后贯穿尾灯','后挡风玻璃','后扰流板','左后翼子板','右后翼子板','左后侧围','右后侧围'],
    lamp:['右纵向方灯'],badge:['前保险杠'],wheel:['右前轮毂','右前轮胎','右前制动盘'],
  };
  if(!names[id])throw new RangeError('Unknown inspection view');
  const meshes=[];
  for(const part of vehicle.parts){
    if(!names[id].includes(part.name))continue;
    part.traverse(node=>{if(node.isMesh&&(id!=='badge'||node.material.name.startsWith('VW ')))meshes.push(node);});
  }
  return meshes;
}

export function fitInspectionView(box,direction,aspect,fov=30){
  if(box.isEmpty())throw new Error('Inspection geometry is unavailable');
  const target=box.getCenter(new THREE.Vector3()),out=new THREE.Vector3(...direction).normalize();
  const right=new THREE.Vector3().crossVectors(new THREE.Vector3(0,1,0),out).normalize();
  const up=new THREE.Vector3().crossVectors(out,right).normalize();
  const tangent=Math.tan(THREE.MathUtils.degToRad(fov/2))*.80;
  let distance=0;
  for(const x of [box.min.x,box.max.x])for(const y of [box.min.y,box.max.y])for(const z of [box.min.z,box.max.z]){
    const p=new THREE.Vector3(x,y,z).sub(target);
    distance=Math.max(distance,p.dot(out)+Math.max(Math.abs(p.dot(up))/tangent,Math.abs(p.dot(right))/(tangent*aspect)));
  }
  return {target,position:target.clone().addScaledVector(out,distance),distance};
}

export function isolateMeshes(root,meshes){
  const selected=new Set(meshes),saved=[];
  root.traverse(node=>{if(node.isMesh){saved.push([node,node.visible]);node.visible=selected.has(node);}});
  return ()=>{for(const [node,visible] of saved)node.visible=visible;};
}

export function createInspection({canvas,camera,controls,vehicle,resize,onEnter,onExit,onIsolate}){
  const dialog=document.querySelector('#detail-dialog'),stage=document.querySelector('#detail-stage');
  const isolate=document.querySelector('#detail-isolate'),nav=document.querySelector('#detail-views');
  const home=canvas.parentNode,next=canvas.nextSibling;
  let active=false,current='rear',box=null,selected=[],snapshot,opener,restoreVisibility=()=>{},fitDistance=0;
  nav.innerHTML=INSPECTION_VIEWS.map(view=>`<button type="button" data-detail-view="${view.id}" aria-pressed="false">${view.label}</button>`).join('');
  function flushOrbit(){const damping=controls.enableDamping;controls.enableDamping=false;controls.update();controls.enableDamping=damping;}
  function fit(){
    const view=INSPECTION_VIEWS.find(view=>view.id===current);
    const pose=fitInspectionView(box,view.direction,camera.aspect,camera.fov);
    flushOrbit();controls.target.copy(pose.target);camera.position.copy(pose.position);fitDistance=pose.distance;
    controls.minDistance=Math.max(.04,box.getSize(new THREE.Vector3()).length()*.12);
    controls.maxDistance=fitDistance*5;controls.update();
  }
  function visibility(){
    restoreVisibility();restoreVisibility=isolate.checked?isolateMeshes(vehicle.root,selected):()=>{};
    controls.maxPolarAngle=isolate.checked?Math.PI-.04:Math.PI/2-.03;
    onIsolate(isolate.checked,box);
  }
  function select(id){
    restoreVisibility();restoreVisibility=()=>{};current=id;
    const view=INSPECTION_VIEWS.find(view=>view.id===id);
    selected=getInspectionMeshes(vehicle,id);vehicle.root.updateMatrixWorld(true);box=new THREE.Box3();
    for(const mesh of selected)box.union(new THREE.Box3().setFromObject(mesh));
    document.querySelector('#detail-title').textContent=view.label;
    document.querySelector('#detail-description').textContent=view.description;
    canvas.setAttribute('aria-label',`可旋转缩放的${view.label}三维细节`);
    for(const button of nav.querySelectorAll('button'))button.setAttribute('aria-pressed',String(button.dataset.detailView===id));
    isolate.checked=Boolean(view.isolated);visibility();fit();
  }
  function open(id='rear',trigger=document.activeElement){
    if(active){select(id);return;}
    flushOrbit();opener=trigger;
    snapshot={position:camera.position.clone(),target:controls.target.clone(),near:camera.near,
      minDistance:controls.minDistance,maxDistance:controls.maxDistance,minPolarAngle:controls.minPolarAngle,maxPolarAngle:controls.maxPolarAngle,
      enableZoom:controls.enableZoom,enablePan:controls.enablePan,opacity:canvas.style.opacity,label:canvas.getAttribute('aria-label')};
    active=true;box=null;onEnter();
    document.body.classList.add('inspection-open');stage.append(canvas);canvas.style.opacity='1';
    camera.near=.005;controls.enableZoom=true;controls.enablePan=true;controls.minPolarAngle=.04;
    dialog.showModal();resize();select(id);canvas.focus({preventScroll:true});
  }
  function close(){dialog.close();}
  dialog.addEventListener('close',()=>{
    if(!active)return;
    flushOrbit();active=false;restoreVisibility();restoreVisibility=()=>{};box=null;
    home.insertBefore(canvas,next);canvas.style.opacity=snapshot.opacity;canvas.setAttribute('aria-label',snapshot.label);
    document.body.classList.remove('inspection-open');camera.near=snapshot.near;
    for(const key of ['minDistance','maxDistance','minPolarAngle','maxPolarAngle','enableZoom','enablePan'])controls[key]=snapshot[key];
    controls.target.copy(snapshot.target);camera.position.copy(snapshot.position);controls.update();onIsolate(false);onExit();resize();
    opener?.focus({preventScroll:true});
  });
  function zoom(factor){
    const offset=camera.position.clone().sub(controls.target);
    offset.setLength(THREE.MathUtils.clamp(offset.length()*factor,controls.minDistance,controls.maxDistance));
    camera.position.copy(controls.target).add(offset);controls.update();
  }
  for(const button of document.querySelectorAll('[data-inspect-open]')){
    button.disabled=false;button.addEventListener('click',()=>open('rear',button));
  }
  nav.addEventListener('click',event=>{const button=event.target.closest('[data-detail-view]');if(button)select(button.dataset.detailView);});
  isolate.addEventListener('change',visibility);
  document.querySelector('#detail-close').addEventListener('click',close);
  document.querySelector('#detail-reset').addEventListener('click',fit);
  document.querySelector('#detail-zoom-in').addEventListener('click',()=>zoom(.8));
  document.querySelector('#detail-zoom-out').addEventListener('click',()=>zoom(1.25));
  dialog.addEventListener('keydown',event=>{
    if(event.ctrlKey||event.metaKey||event.altKey)return;
    if(['+','=','-','r','R'].includes(event.key)){
      event.preventDefault();if(event.key==='-')zoom(1.25);else if(event.key.toLowerCase()==='r')fit();else zoom(.8);
    }
  });
  return {get active(){return active;},stage,open,
    refit(){
      if(!box)return;
      const view=INSPECTION_VIEWS.find(view=>view.id===current),pose=fitInspectionView(box,view.direction,camera.aspect,camera.fov);
      const offset=camera.position.clone().sub(controls.target).multiplyScalar(pose.distance/fitDistance);
      fitDistance=pose.distance;controls.maxDistance=fitDistance*5;camera.position.copy(controls.target).add(offset);controls.update();
    },
  };
}
