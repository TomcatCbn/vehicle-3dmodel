import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { createVehicle } from '../src/render/vehicle.js';
import { createState } from '../src/state.js';

function sceneFixture() {
  const root = new THREE.Group();
  for (const [name, layer, motion, side] of [['车门','body','door',-1],['车窗','cabin','window',-1],['动力电池包','power','',0]]) {
    const part = new THREE.Group();part.name = name;
    part.position.set(.5,1,-.9);
    part.userData = { part:true, label:name, layer, motion, side, offset:[0,1,side], start:.1 };
    const material = new THREE.MeshStandardMaterial({color:'#7caaa0'});material.name = 'Paint';
    part.add(new THREE.Mesh(new THREE.BoxGeometry(.4,.4,.1),material));root.add(part);
  }
  return root;
}
test('GLB part metadata drives reversible assembly and preserves the imported geometry', () => {
  const root = sceneFixture(), vehicle = createVehicle(root);
  assert.equal(vehicle.parts.length,3);
  const original = vehicle.parts.map(part => part.position.clone());
  vehicle.update(createState(),1);
  assert.ok(vehicle.parts.every((part,i) => part.position.distanceTo(original[i])>.5));
  vehicle.update(createState(),0);
  vehicle.parts.forEach((part,i) => assert.ok(part.position.distanceTo(original[i])<1e-9));
});
test('door and window share the opening rotation while glass lowers continuously', () => {
  const vehicle = createVehicle(sceneFixture()), state = createState();
  state.doorAngle = 1;state.windowOpen = .8;
  vehicle.update(state,0);
  const [door,window] = vehicle.parts;
  assert.ok(Math.abs(door.rotation.y)>.5);
  assert.equal(window.rotation.y,door.rotation.y);
  assert.ok(window.position.y<door.position.y-.3);
  vehicle.update(state,1);
  assert.equal(door.rotation.y,0);
});
test('layer highlighting restores materials and paint changes imported bodywork', () => {
  const vehicle = createVehicle(sceneFixture());
  vehicle.update(createState(),1,'power');
  assert.ok(vehicle.parts[0].children[0].material.opacity<.1);
  assert.equal(vehicle.parts[2].children[0].material.opacity,1);
  vehicle.update(createState(),0,'all');
  assert.equal(vehicle.parts[0].children[0].material.transparent,false);
  vehicle.setColor('#d4c4a5');
  assert.equal(vehicle.parts[0].children[0].material.color.getHexString(),'d4c4a5');
});

test('explicit low-beam roles preserve authored intensity and switch fully off', () => {
  const root = new THREE.Group(), part = new THREE.Group();
  part.userData = { part:true, layer:'body', offset:[0,0,0], start:0 };
  const material = new THREE.MeshStandardMaterial({emissive:'#ffffff',emissiveIntensity:2.4});
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(.4,.1,.1),material);
  mesh.userData.lightRole = 'lowBeam';
  part.add(mesh);root.add(part);
  const vehicle = createVehicle(root), state = createState();
  vehicle.update(state,0);
  assert.equal(mesh.material.emissiveIntensity,2.4);
  state.lighting.headlights = 'off';
  vehicle.update(state,0);
  assert.equal(mesh.material.emissiveIntensity,0);
});

test('createVehicle controls brake lights from the motion object', () => {
  const root = new THREE.Group(), part = new THREE.Group();
  part.userData = { part:true, layer:'body', offset:[0,0,0], start:0 };
  const material = new THREE.MeshStandardMaterial({emissive:'#ffffff',emissiveIntensity:4});
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(.4,.1,.1),material);
  mesh.userData.lightRole = 'brakeLight';
  part.add(mesh);root.add(part);
  const vehicle = createVehicle(root), state = createState();
  vehicle.update(state,0);
  assert.equal(mesh.material.emissiveIntensity,0);
  vehicle.update(state,0,'all',{wheelAngle:0,braking:true,reversing:false});
  assert.equal(mesh.material.emissiveIntensity,4);
});
