import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import * as THREE from 'three';
import { createVehicle } from '../src/vehicle.js';
import { createState } from '../src/state.js';

async function loadModel() {
  const bytes = await readFile(new URL('../public/models/aura-t6.glb',import.meta.url));
  return new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');
}
test('exported Blender GLB includes four doors, four moving panes and all structural layers', async () => {
  const gltf = await loadModel(), vehicle = createVehicle(gltf.scene);
  assert.equal(vehicle.parts.length,89);
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

test('all four wheel assemblies turn around their authored axle and restore when driving ends',async()=>{
  const vehicle=createVehicle((await loadModel()).scene),state=createState();
  const wheels=vehicle.parts.filter(part=>/轮胎$|轮毂$/.test(part.name));
  assert.equal(wheels.length,8);
  const brakes=vehicle.parts.filter(part=>part.name.endsWith('制动盘'));
  const angle=Math.PI/3;
  vehicle.update(state,0,'all',angle);
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
