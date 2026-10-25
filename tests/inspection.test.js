import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { createVehicle } from '../src/vehicle.js';
import { getInspectionMeshes, fitInspectionView, isolateMeshes, INSPECTION_VIEWS } from '../src/inspection.js';

async function model(){
  const b=await readFile(new URL('../public/models/aura-t6.glb',import.meta.url));
  const vehicle=createVehicle((await new GLTFLoader().parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'')).scene);
  vehicle.root.updateMatrixWorld(true);return vehicle;
}
function bounds(meshes){const box=new THREE.Box3();for(const mesh of meshes)box.union(new THREE.Box3().setFromObject(mesh));return box;}

test('detail selections find real exterior assemblies, and the badge excludes the surrounding bumper',async()=>{
  const vehicle=await model();
  for(const key of ['front','rear','lamp','badge','wheel'])assert.ok(getInspectionMeshes(vehicle,key).length>0,key);
  const badge=getInspectionMeshes(vehicle,'badge');
  assert.ok(badge.every(mesh=>mesh.material.name.startsWith('VW ')));
  const size=bounds(badge).getSize(new THREE.Vector3());
  assert.ok(size.y>.12&&size.y<.18);
  assert.ok(size.z>.12&&size.z<.18);
  assert.ok(bounds(getInspectionMeshes(vehicle,'wheel')).getSize(new THREE.Vector3()).y>.70);
});

test('all detail camera poses frame the actual geometry on desktop and portrait screens',async()=>{
  const vehicle=await model();
  for(const view of INSPECTION_VIEWS)for(const aspect of [2.0,.58]){
    const box=bounds(getInspectionMeshes(vehicle,view.id));
    const pose=fitInspectionView(box,view.direction,aspect,30);
    const camera=new THREE.PerspectiveCamera(30,aspect,.005,150);
    camera.position.copy(pose.position);camera.lookAt(pose.target);camera.updateMatrixWorld(true);
    for(const x of [box.min.x,box.max.x])for(const y of [box.min.y,box.max.y])for(const z of [box.min.z,box.max.z]){
      const p=new THREE.Vector3(x,y,z).project(camera);
      assert.ok(Math.abs(p.x)<=.83&&Math.abs(p.y)<=.83,`${view.id} clipped at aspect ${aspect}`);
      assert.ok(p.z>-1&&p.z<1);
    }
  }
});

test('isolating a component restores every original visibility flag on exit',async()=>{
  const vehicle=await model(),meshes=[];vehicle.root.traverse(node=>{if(node.isMesh)meshes.push(node);});
  meshes[0].visible=false;
  const before=meshes.map(mesh=>mesh.visible),selected=getInspectionMeshes(vehicle,'badge');
  const restore=isolateMeshes(vehicle.root,selected);
  assert.ok(selected.every(mesh=>mesh.visible));
  assert.ok(meshes.filter(mesh=>!selected.includes(mesh)).every(mesh=>!mesh.visible));
  restore();assert.deepEqual(meshes.map(mesh=>mesh.visible),before);
});
