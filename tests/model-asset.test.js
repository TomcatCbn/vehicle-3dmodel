import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import * as THREE from 'three';
import { createVehicle } from '../src/render/vehicle.js';
import { createState } from '../src/state.js';

async function loadModel() {
  const bytes = await readFile(new URL('../public/models/aura-t6.glb',import.meta.url));
  return new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');
}
test('exported Blender GLB includes four doors, four moving panes and all structural layers', async () => {
  const gltf = await loadModel(), vehicle = createVehicle(gltf.scene);
  assert.equal(vehicle.parts.length,99);
  assert.equal(vehicle.parts.filter(p=>p.userData.motion==='door').length,4);
  assert.equal(vehicle.parts.filter(p=>p.userData.motion==='window').length,4);
  for (const layer of ['body','cabin','chassis','power']) assert.ok(vehicle.parts.some(p=>p.userData.layer===layer));
  for (const part of vehicle.parts) {
    assert.equal(part.userData.offset.length,3);
    assert.ok(part.userData.offset.every(Number.isFinite));
  }
  vehicle.update(createState(),0);
  const bounds = new THREE.Box3();
  for (const part of vehicle.parts) bounds.union(new THREE.Box3().setFromObject(part));
  const size = bounds.getSize(new THREE.Vector3());
  assert.ok(size.x>4.7 && size.x<5,'SUV length remains plausible');
  assert.ok(size.y>1.6 && size.y<1.8,'vehicle is upright after glTF axis conversion');
  assert.ok(size.z>1.8 && size.z<2.4,'vehicle width remains plausible');
});
test('real GLB reassembles after all imported nodes have been exploded', async () => {
  const vehicle = createVehicle((await loadModel()).scene), state = createState();
  const positions = vehicle.parts.map(p=>p.position.clone());
  vehicle.update(state,1);
  assert.ok(vehicle.parts.every((p,i)=>p.position.distanceTo(positions[i])>.1));
  vehicle.update(state,0);
  vehicle.parts.forEach((p,i)=>assert.ok(p.position.distanceTo(positions[i])<1e-9));
  state.doorAngle=1;state.windowOpen=1;
  vehicle.update(state,0);
  const door=vehicle.parts.find(p=>p.userData.motion==='door');
  const window=vehicle.parts.find(p=>p.userData.motion==='window');
  assert.ok(Math.abs(door.rotation.y)>.5);
  assert.ok(window.position.y<window.userData.base.y-.5);
});

test('real glazing uses a physical transmission material rather than opaque metallic panels', async () => {
  const vehicle = createVehicle((await loadModel()).scene);
  const window = vehicle.parts.find(part=>part.userData.motion==='window');
  let glazing;
  window.traverse(node=>{if(node.isMesh&&node.material.name.startsWith('Glazing'))glazing=node.material;});
  assert.ok(glazing?.isMeshPhysicalMaterial);
  assert.ok(glazing.transmission>.4);
  assert.equal(glazing.metalness,0);
  assert.ok(glazing.roughness<.12);
});

test('closed rear corners hide the cargo sill and aperture seal behind the painted skin',async()=>{
  const vehicle=createVehicle((await loadModel()).scene);
  vehicle.update(createState(),0);vehicle.root.updateMatrixWorld(true);
  for(const y of [-.725,-.71,.71,.725])for(const height of [.640,.652,.70]){
    const ray=new THREE.Raycaster(new THREE.Vector3(3.2,height,-y),new THREE.Vector3(-1,0,0));
    const first=ray.intersectObject(vehicle.root,true)[0];
    assert.ok(first?.object.material.name.startsWith('Paint'),`exposed cargo trim at ${y}, ${height}`);
  }
});

test('front display plate is centred above the intake with a close-fitting plinth and camera above it',async()=>{
  const vehicle=createVehicle((await loadModel()).scene);
  vehicle.update(createState(),0);vehicle.root.updateMatrixWorld(true);
  const front=vehicle.parts.find(part=>part.name==='前保险杠'),meshes=[];
  front.traverse(node=>{if(node.isMesh)meshes.push(node);});
  const box=name=>{
    const mesh=meshes.find(mesh=>mesh.name===name);assert.ok(mesh,name);
    return new THREE.Box3().setFromObject(mesh);
  };
  const plate=box('Front_license_plate'),plinth=box('Front_plate_mounting_plinth'),camera=box('Front_camera_bezel');
  const size=plate.getSize(new THREE.Vector3()),centre=plate.getCenter(new THREE.Vector3());
  assert.ok(size.z>.43&&size.z<.45&&size.y>.14&&size.y<.15);
  assert.ok(Math.abs(centre.z)<1e-5&&centre.y>.63&&centre.y<.65);
  assert.ok(camera.min.y>plate.max.y+.035&&Math.abs(camera.getCenter(new THREE.Vector3()).z)<1e-5);
  assert.ok(plinth.min.y>=plate.min.y-.010&&plinth.max.y<=plate.max.y+.010);
  assert.ok(!meshes.some(mesh=>mesh.name==='Lower_central_plate_support'),'plate bracket must not hang into the intake');
});

test('model plates use neutral black-and-white lettering without advertising meshes or materials',async()=>{
  const vehicle=createVehicle((await loadModel()).scene),names=[];
  let plates=0;
  vehicle.root.traverse(node=>{
    names.push(node.name);
    if(!node.isMesh)return;
    names.push(node.material.name);
    if(node.name==='Front_license_plate'||node.name==='Rear_license_plate'){
      plates++;assert.equal(node.material.name,'Model plate matte black');
      assert.ok(Math.max(node.material.color.r,node.material.color.g,node.material.color.b)<.02);
    }
  });
  assert.equal(plates,2);
  assert.ok(!names.some(name=>/汽车之家|看车|买车|Front display plate/.test(name)));
  assert.ok(names.filter(name=>name.startsWith('Badge_IDAURA_T6')).length>=2);
});

test('each handle opens into a recessed finger cup and its flap follows the door hinge',async()=>{
  const vehicle=createVehicle((await loadModel()).scene),state=createState();
  vehicle.update(state,0);vehicle.root.updateMatrixWorld(true);
  const before=[];
  for(const door of vehicle.parts.filter(part=>part.userData.motion==='door')){
    const detail=[];door.traverse(node=>{if(node.isMesh&&node.userData.detail==='handle')detail.push(node);});
    assert.ok(detail.length>=5,door.name);
    const flap=detail.find(node=>node.name.startsWith('Handle_flush_upper_flap'));
    assert.ok(flap);
    const box=new THREE.Box3().setFromObject(flap),center=box.getCenter(new THREE.Vector3()),side=Math.sign(door.userData.base.z);
    const ray=new THREE.Raycaster(new THREE.Vector3(center.x,.964,side*1.3),new THREE.Vector3(0,0,-side));
    const hit=ray.intersectObject(vehicle.root,true)[0];
    assert.equal(hit?.object.userData.detail,'handle',door.name+' has a real opening in the skin');
    assert.ok(/^Handle_(recessed_cup|pocket_back_liner)/.test(hit.object.name));
    assert.ok((center.z-hit.point.z)*side>.02,door.name+' cup lies behind the flush flap');
    const vertex=new THREE.Vector3().fromBufferAttribute(flap.geometry.attributes.position,0).applyMatrix4(flap.matrixWorld);
    before.push({door,flap,vertex});
  }
  state.doorAngle=1;vehicle.update(state,0);vehicle.root.updateMatrixWorld(true);
  for(const {door,flap,vertex} of before){
    const open=new THREE.Vector3().fromBufferAttribute(flap.geometry.attributes.position,0).applyMatrix4(flap.matrixWorld);
    assert.ok(open.distanceTo(vertex)>.1);
    assert.ok(Math.abs(open.distanceTo(door.userData.base)-vertex.distanceTo(door.userData.base))<1e-5);
  }
  vehicle.setColor('#b7c3cb');
  const silver=new THREE.Color('#b7c3cb');
  vehicle.root.traverse(mesh=>{
    if(!mesh.isMesh||mesh.material.name!=='Paint handle cup')return;
    const color=mesh.material.color;
    assert.ok(color.b>color.r&&color.g>color.r,'cup follows the silver body colour');
    assert.ok(color.r<silver.r*.5&&color.g<silver.g*.5&&color.b<silver.b*.5,'cup retains its darker recessed finish');
  });
});

test('moving glass meets the painted door shoulder rather than floating outside it', async () => {
  const vehicle = createVehicle((await loadModel()).scene);
  vehicle.root.updateMatrixWorld(true);
  for (const window of vehicle.parts.filter(part=>part.userData.motion==='window')) {
    const door=vehicle.parts.find(part=>part.name===window.name.replace('窗','门'));
    assert.ok(door);
    const glassPoints=[],shoulder=[];
    for (const [part,points,painted] of [[window,glassPoints,false],[door,shoulder,true]]) {
      part.traverse(mesh=>{
        if(!mesh.isMesh || (painted && !mesh.material.name.startsWith('Paint')))return;
        const positions=mesh.geometry.attributes.position;
        for(let i=0;i<positions.count;i++) {
          const p=new THREE.Vector3().fromBufferAttribute(positions,i).applyMatrix4(mesh.matrixWorld);
          if(!painted || p.y>1.065)points.push(p);
        }
      });
    }
    const bottom=Math.min(...glassPoints.map(p=>p.y));
    const lowerEdge=glassPoints.filter(p=>p.y<bottom+.008);
    assert.ok(lowerEdge.length>3);
    for(const point of lowerEdge) {
      const distance=Math.sqrt(Math.min(...shoulder.map(p=>p.distanceToSquared(point))));
      assert.ok(distance<.03,`${window.name} floats ${(distance*1000).toFixed(1)} mm from its shoulder`);
    }
  }
});

test('each wheel contains a deep rim barrel instead of a flat opaque wheel cap', async () => {
  const vehicle=createVehicle((await loadModel()).scene);
  vehicle.root.updateMatrixWorld(true);
  const rims=vehicle.parts.filter(part=>part.name.endsWith('轮毂'));
  assert.equal(rims.length,4);
  for(const rim of rims) {
    const depth=new THREE.Box3().setFromObject(rim).getSize(new THREE.Vector3()).z;
    assert.ok(depth>.18 && depth<.30,`${rim.name} has ${depth.toFixed(3)} m axial depth`);
  }
});

test('wheel cavities keep the upper arch liner but have no flat sheet across the wheel opening',async()=>{
  const vehicle=createVehicle((await loadModel()).scene);
  vehicle.update(createState(),0);vehicle.root.updateMatrixWorld(true);
  for(const label of ['右前翼子板','左前翼子板','右后翼子板','左后翼子板']){
    const fender=vehicle.parts.find(part=>part.name===label),side=label.startsWith('右')?1:-1,x=label.includes('前')?-1.418:1.418;
    const ray=new THREE.Raycaster(new THREE.Vector3(x+.10,.18,side*2),new THREE.Vector3(0,0,-side));
    assert.equal(ray.intersectObject(fender,true).length,0,label+' must not contain a full circular backing sheet');
    const liner=fender.children.find(node=>node.name.startsWith('Wheel_well_tunnel'));
    assert.ok(liner,'upper curved wheel-well liner is retained');
    assert.equal(liner.material.metalness,0);
    assert.ok(liner.material.roughness>.8);
    const upperRay=new THREE.Raycaster(new THREE.Vector3(x,.755,side*2),new THREE.Vector3(0,0,-side));
    const hit=upperRay.intersectObject(fender,true)[0];
    assert.equal(hit?.object.material.name,'Wheel well liner','upper tire-to-arch gap must still have a curved inner backing');
  }
});

test('five rim windows remain physically open after adding the aero inserts',async()=>{
  const vehicle=createVehicle((await loadModel()).scene);
  vehicle.update(createState(),0);vehicle.root.updateMatrixWorld(true);
  const rim=vehicle.parts.find(part=>part.name==='右前轮毂');
  for(let i=0;i<5;i++){
    const angle=i/5*Math.PI*2+Math.PI/2,r=.21*1.12;
    const ray=new THREE.Raycaster(new THREE.Vector3(-1.418+r*Math.cos(angle),.37+r*Math.sin(angle),1.5),new THREE.Vector3(0,0,-1));
    assert.equal(ray.intersectObject(rim,true).length,0,'rim window '+i+' must not become a solid cover');
  }
});

test('the roof sensor stays on the fixed header clear of the full sliding glass travel',async()=>{
  const vehicle=createVehicle((await loadModel()).scene),state=createState();
  const sensor=vehicle.parts.find(part=>part.name==='车顶激光雷达'),sunroof=vehicle.parts.find(part=>part.name==='电动天窗');
  for(let i=0;i<=10;i++){
    state.sunroofPosition=i/10;vehicle.update(state,0);vehicle.root.updateMatrixWorld(true);
    const a=new THREE.Box3().setFromObject(sensor),b=new THREE.Box3().setFromObject(sunroof);
    assert.ok(a.max.x<b.min.x-.005,'fixed sensor must stay forward of the moving glass');
  }
});

test('mirror camera retaining rings follow the shallow underside bevel rather than hanging vertically',async()=>{
  const vehicle=createVehicle((await loadModel()).scene);
  vehicle.update(createState(),0);vehicle.root.updateMatrixWorld(true);
  for(const part of vehicle.parts.filter(part=>part.name.endsWith('后视镜'))){
    const bezel=part.children.find(node=>node.name.startsWith('Mirror_underside_camera_bezel'));
    assert.ok(bezel);
    const size=new THREE.Box3().setFromObject(bezel).getSize(new THREE.Vector3());
    assert.ok(size.y<.011&&size.x>.014&&size.z>.014,'camera bezel must stay close to the shallow underside bevel');
  }
});

test('mirror glass faces rearward and toward the driver rather than straight along the car axis',async()=>{
  const vehicle=createVehicle((await loadModel()).scene);
  vehicle.update(createState(),0);vehicle.root.updateMatrixWorld(true);
  for(const part of vehicle.parts.filter(part=>part.name.endsWith('后视镜'))){
    const glass=part.children.find(node=>node.name.startsWith('Mirror_reflective_glass'));
    assert.ok(glass);
    const normal=new THREE.Vector3().fromBufferAttribute(glass.geometry.getAttribute('normal'),0).applyNormalMatrix(new THREE.Matrix3().getNormalMatrix(glass.matrixWorld));
    const out=new THREE.Vector3(0,0,part.name.startsWith('右')?1:-1);
    assert.ok(normal.x>.35&&normal.dot(out)<-.4,'rear-facing mirror should angle inward toward the driver');
    const centre=new THREE.Vector3().fromBufferAttribute(glass.geometry.getAttribute('position'),0).applyMatrix4(glass.matrixWorld);
    for(const dy of [0,-.033]){
      const target=centre.clone().add(new THREE.Vector3(0,dy,0));
      const ray=new THREE.Raycaster(target.addScaledVector(normal,.40),normal.clone().negate());
      assert.ok(ray.intersectObject(part,true)[0]?.object===glass,'mounting neck must not obstruct the central/lower mirror surface');
    }
  }
});

test('all four wheel assemblies turn around their authored axle and restore when driving ends',async()=>{
  const vehicle=createVehicle((await loadModel()).scene),state=createState();
  const wheels=vehicle.parts.filter(part=>/轮胎$|轮毂$/.test(part.name));
  assert.equal(wheels.length,8);
  const brakes=vehicle.parts.filter(part=>part.name.endsWith('制动盘'));
  const angle=Math.PI/3;
  vehicle.update(state,0,'all',{wheelAngle:angle});
  for(const wheel of wheels){
    assert.ok(wheel.position.distanceTo(wheel.userData.base)<1e-8);
    const up=new THREE.Vector3(0,1,0).applyQuaternion(wheel.quaternion);
    assert.ok(Math.abs(up.x+Math.sin(angle))<1e-6,`${wheel.name} rotates in the direction of travel`);
    const axis=new THREE.Vector3(0,0,1).applyQuaternion(wheel.quaternion);
    assert.ok(axis.distanceTo(new THREE.Vector3(0,0,1))<1e-8);
  }
  for(const brake of brakes)assert.ok(brake.quaternion.angleTo(brake.userData.baseQuaternion)<1e-8);
  vehicle.update(state,0);
  for(const wheel of wheels)assert.ok(wheel.quaternion.angleTo(wheel.userData.baseQuaternion)<1e-8);
});

test('the bonnet and telescopic supports meet the authored hinge in open and closed poses',async()=>{
  const vehicle=createVehicle((await loadModel()).scene),state=createState();
  const hood=vehicle.parts.find(part=>part.userData.motion==='hood');
  assert.ok(hood,'the bonnet has its own hinge metadata');
  const supports=vehicle.parts.filter(part=>part.userData.motion==='hood_strut');
  assert.equal(supports.length,2);
  const sample=hood.userData.meshes.find(({mesh})=>mesh.name.includes('outer_skin')).mesh;
  sample.geometry.computeBoundingBox();
  const point=sample.geometry.boundingBox.min.clone();
  vehicle.root.updateMatrixWorld(true);
  const before=point.clone().applyMatrix4(sample.matrixWorld);
  state.hoodAngle=1;vehicle.update(state,0);vehicle.root.updateMatrixWorld(true);
  const after=point.clone().applyMatrix4(sample.matrixWorld);
  assert.ok(after.y>before.y+.6,'bonnet rises in front of the windscreen');
  assert.ok(hood.position.distanceTo(hood.userData.base)<1e-8,'hinge does not translate');
  for(const angle of [0,.5,1]){
    state.hoodAngle=angle;vehicle.update(state,0);vehicle.root.updateMatrixWorld(true);
    for(const support of supports){
      const pivot=new THREE.Vector3(...support.userData.hinge);
      const moving=new THREE.Vector3(...support.userData.moving).sub(pivot).applyAxisAngle(new THREE.Vector3(0,0,1),-angle*1.12).add(pivot);
      let tip;support.traverse(node=>{if(node.userData.strut_component==='tip')tip=node;});
      assert.ok(tip,'support has a separate moving socket');
      const end=tip.getWorldPosition(new THREE.Vector3());
      assert.ok(end.distanceTo(moving)<1e-5,'support socket remains on the bonnet');
    }
  }
  state.hoodAngle=0;vehicle.update(state,0);vehicle.root.updateMatrixWorld(true);
  assert.ok(point.clone().applyMatrix4(sample.matrixWorld).distanceTo(before)<1e-7);
  vehicle.update({...state,hoodAngle:1},1);
  assert.ok(hood.quaternion.angleTo(hood.userData.baseQuaternion)<1e-7,'exploded view restores the neutral panel orientation');
});

test('front service cover and tray use distinct grained dielectric polymers',async()=>{
  const vehicle=createVehicle((await loadModel()).scene);
  const bay=vehicle.parts.find(part=>part.name==='前舱检修盖板');
  const coverMesh=bay.userData.meshes.find(({mesh})=>mesh.name.startsWith('Broad_sealed')).mesh;
  const trayMesh=bay.userData.meshes.find(({mesh})=>mesh.name.startsWith('Front_bay_moulded')).mesh;
  for(const mesh of [coverMesh,trayMesh])assert.ok(mesh.geometry.attributes.uv?.array.some(value=>value>2),'grain repeats over the real panel UV coordinates');
  const cover=coverMesh.material,tray=trayMesh.material;
  for(const material of [cover,tray]){
    assert.equal(material.metalness,0);
    assert.ok(material.normalMap?.isDataTexture,'moulded polymer has a repeatable fine normal texture');
    assert.ok(material.envMapIntensity<.5,'dark service plastics do not mirror the warm studio floor');
    assert.ok(Math.max(material.color.r,material.color.g,material.color.b)<.025);
    const pixels=material.normalMap.image.data;
    assert.ok(new Set(pixels.filter((_,i)=>i%4===0)).size>8,'grain varies across the surface');
  }
  assert.ok(tray.roughness>cover.roughness+.1,'tray remains duller than the removable cover');
});

test('power tailgate carries its glass, central lamp and spoiler while outer lamps stay fixed',async()=>{
  const vehicle=createVehicle((await loadModel()).scene),state=createState();
  const moving=vehicle.parts.filter(part=>part.userData.motion==='tailgate');
  assert.equal(moving.length,4);
  for(const name of ['尾门','后挡风玻璃','后扰流板','后贯穿尾灯'])assert.ok(moving.some(part=>part.name===name),name);
  const fixed=vehicle.parts.filter(part=>part.name.endsWith('外侧尾灯'));
  assert.equal(fixed.length,2);
  const fixedPose=fixed.map(part=>[part.position.clone(),part.quaternion.clone()]);
  const center=part=>{const mesh=part.userData.meshes[0].mesh;return new THREE.Vector3().fromBufferAttribute(mesh.geometry.attributes.position,0).applyMatrix4(mesh.matrixWorld);};
  vehicle.update(state,0);vehicle.root.updateMatrixWorld(true);
  const before=moving.map(center),gate=moving.find(part=>part.name==='尾门');
  const bottom=new THREE.Box3().setFromObject(gate).min.y;
  state.tailgatePosition=1;vehicle.update(state,0);vehicle.root.updateMatrixWorld(true);
  assert.ok(new THREE.Box3().setFromObject(gate).min.y>bottom+.9);
  const after=moving.map(center);
  for(let i=1;i<moving.length;i++)assert.ok(Math.abs(before[i].distanceTo(before[0])-after[i].distanceTo(after[0]))<1e-5);
  fixed.forEach((part,i)=>{assert.ok(part.position.distanceTo(fixedPose[i][0])<1e-8);assert.ok(part.quaternion.angleTo(fixedPose[i][1])<1e-8);});
  state.tailgatePosition=0;vehicle.update(state,0);vehicle.root.updateMatrixWorld(true);
  moving.forEach((part,i)=>assert.ok(center(part).distanceTo(before[i])<1e-6));
});

test('sunroof lifts and slides over fixed rear glass, leaving a genuine aperture',async()=>{
  const vehicle=createVehicle((await loadModel()).scene),state=createState();
  const pane=vehicle.parts.find(part=>part.userData.motion==='sunroof');
  assert.ok(pane,'separate moving sunroof panel');
  const ray=new THREE.Raycaster(new THREE.Vector3(.2,4,0),new THREE.Vector3(0,-1,0));
  vehicle.update(state,0);vehicle.root.updateMatrixWorld(true);
  const isPane=mesh=>{let node=mesh;while(node&&!node.userData.part)node=node.parent;return node===pane;};
  assert.ok(isPane(ray.intersectObjects(vehicle.root.children,true)[0].object));
  const before=pane.position.clone();
  state.sunroofPosition=1;vehicle.update(state,0);vehicle.root.updateMatrixWorld(true);
  assert.ok(pane.position.x>before.x+.75);
  assert.ok(pane.position.y>before.y+.06);
  assert.ok(!isPane(ray.intersectObjects(vehicle.root.children,true)[0].object));
  const fixed=vehicle.parts.find(part=>part.name==='全景玻璃车顶');
  assert.ok(new THREE.Box3().setFromObject(pane).min.y>new THREE.Box3().setFromObject(fixed).max.y+.005);
  vehicle.update(state,1);
  assert.ok(pane.quaternion.angleTo(pane.userData.baseQuaternion)<1e-7);
});

test('tailgate electric struts keep their moving sockets attached through the full stroke',async()=>{
  const vehicle=createVehicle((await loadModel()).scene),state=createState();
  const supports=vehicle.parts.filter(part=>part.userData.motion==='tailgate_strut');
  assert.equal(supports.length,2);
  for(const angle of [0,.25,.5,.75,1]){
    state.tailgatePosition=angle;vehicle.update(state,0);vehicle.root.updateMatrixWorld(true);
    for(const support of supports){
      const hinge=new THREE.Vector3(...support.userData.hinge);
      const expected=new THREE.Vector3(...support.userData.moving).sub(hinge).applyAxisAngle(new THREE.Vector3(0,0,1),angle*1.45).add(hinge);
      const tip=support.userData.strutComponents.find(node=>node.userData.strut_component==='tip');
      assert.ok(tip.getWorldPosition(new THREE.Vector3()).distanceTo(expected)<1e-5);
    }
  }
});

test('production lamps expose independent runtime roles and paired anchors',async()=>{
  const scene=(await loadModel()).scene;
  scene.updateMatrixWorld(true);
  const expectedCounts={lowBeam:6,highBeam:2,tailLight:5,brakeLight:4,reverseLight:2,ambientLight:2,chargeIndicator:1};
  const expectedAssociations=[
    {role:'lowBeam',part:'front_light_bar',count:4,strength:1},
    {role:'lowBeam',part:'headlight_-1',count:1,strength:3,name:'Lower'},
    {role:'lowBeam',part:'headlight_1',count:1,strength:3,name:'Lower'},
    {role:'highBeam',part:'headlight_-1',count:1,strength:5,name:'Upper'},
    {role:'highBeam',part:'headlight_1',count:1,strength:5,name:'Upper'},
    {role:'tailLight',part:'tail_lights',count:1,strength:1},
    {role:'tailLight',part:'outer_tail_lamp_-1',count:2,strength:1},
    {role:'tailLight',part:'outer_tail_lamp_1',count:2,strength:1},
    {role:'brakeLight',part:'tail_lights',count:1,strength:5,name:'Ruby'},
    {role:'brakeLight',part:'outer_tail_lamp_-1',count:1,strength:5,name:'Ruby'},
    {role:'brakeLight',part:'outer_tail_lamp_1',count:1,strength:5,name:'Ruby'},
    {role:'brakeLight',part:'rear_spoiler',count:1,strength:5,name:'High'},
    {role:'reverseLight',part:'rear_bumper',count:2,strength:3},
    {role:'ambientLight',part:'dashboard',count:2,strength:1.5},
    {role:'chargeIndicator',part:'charge_cable',count:1,strength:2},
  ];
  const roleMeshes=new Map(Object.keys(expectedCounts).map(role=>[role,[]]));
  const anchors={headlight:[],ambient:[]},materialRoles=new Map();
  const partOf=node=>{
    for(let parent=node.parent;parent;parent=parent.parent)if(Object.hasOwn(parent.userData,'part'))return parent;
  };
  scene.traverse(node=>{
    if(node.isMesh&&node.userData.lightRole){
      const role=node.userData.lightRole;
      assert.ok(roleMeshes.has(role),`unexpected lamp role ${role}`);
      roleMeshes.get(role).push(node);
      if(!materialRoles.has(node.material))materialRoles.set(node.material,new Set());
      materialRoles.get(node.material).add(role);
    }
    if(node.userData.lightAnchor in anchors)anchors[node.userData.lightAnchor].push(node);
  });
  for(const [role,meshes] of roleMeshes)assert.equal(meshes.length,expectedCounts[role],`${role} mesh count`);
  for(const {role,part,count,strength,name} of expectedAssociations){
    const meshes=roleMeshes.get(role).filter(mesh=>partOf(mesh)?.name===part);
    assert.equal(meshes.length,count,`${role} meshes under ${part}`);
    for(const mesh of meshes){
      if(name)assert.ok(mesh.name.includes(name),`${mesh.name} identifies its ${role} optics`);
      assert.ok(mesh.material.emissiveIntensity>0,`${mesh.name} has authored emission`);
      assert.equal(mesh.material.emissiveIntensity,strength,`${mesh.name} emissive intensity under ${part}`);
    }
  }
  for(const [material,roles] of materialRoles)assert.equal(roles.size,1,`${material.name} is shared across lamp roles`);
  const assertWorldPosition=(position,expected,label)=>{
    assert.ok(position.toArray().every(Number.isFinite),`${label} has a finite world position`);
    position.toArray().forEach((value,index)=>assert.ok(Math.abs(value-expected[index])<=1e-4,`${label} ${'xyz'[index]}: expected ${expected[index]}, got ${value}`));
  };
  assert.equal(anchors.headlight.length,2);
  for(const part of ['headlight_-1','headlight_1']){
    const matches=anchors.headlight.filter(anchor=>anchor.parent.name===part);
    assert.equal(matches.length,1,`${part} headlight anchor count`);
    assert.ok(matches[0].parent.userData.part,`${part} anchor has a part parent`);
    const base=matches[0].parent.getWorldPosition(new THREE.Vector3());
    const expected=[base.x-.035,base.y-.043,base.z+Math.sign(base.z)*.035];
    assertWorldPosition(matches[0].getWorldPosition(new THREE.Vector3()),expected,`${part} headlight anchor follows current lamp geometry`);
  }
  assert.equal(anchors.ambient.length,2);
  const ambientPositions=anchors.ambient.map(anchor=>{
    assert.ok(anchor.parent.userData.part,`${anchor.name} has a part parent`);
    assert.equal(anchor.parent.name,'dashboard',`${anchor.name} has the dashboard parent`);
    const position=anchor.getWorldPosition(new THREE.Vector3());
    assert.ok(position.toArray().every(Number.isFinite),`${anchor.name} has a finite world position`);
    return position;
  });
  for(const expected of [[-.2,1.28,.43],[-.2,1.28,-.43]]){
    assert.ok(ambientPositions.some(position=>position.toArray().every((value,index)=>Math.abs(value-expected[index])<=1e-4)),`missing ambient anchor at ${expected.join(', ')}`);
  }
});
