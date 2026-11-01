import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { maskForLampBloom } from '../src/render/presentation.js';

test('selective glow preserves opaque occlusion, passes through glazing and restores the scene exactly',()=>{
  const scene=new THREE.Scene();scene.background=new THREE.Color('#8293a0');scene.environment=new THREE.Texture();scene.fog=new THREE.Fog('#abcdef',1,20);
  const original={background:scene.background,environment:scene.environment,fog:scene.fog};
  const mesh=material=>{const node=new THREE.Mesh(new THREE.BoxGeometry(1,1,1),material);scene.add(node);return node;};
  const on=mesh(new THREE.MeshStandardMaterial({emissive:'#ff1830',emissiveIntensity:4}));on.userData.lightRole='tailLight';
  const off=mesh(new THREE.MeshStandardMaterial({emissiveIntensity:0}));off.userData.lightRole='brakeLight';
  const body=mesh(new THREE.MeshStandardMaterial({color:'#578d81'}));
  const glass=mesh(new THREE.MeshPhysicalMaterial({transmission:.8}));
  const mirror=mesh(new THREE.MeshBasicMaterial());mirror.isReflector=true;
  const originals=[on,off,body,glass,mirror].map(node=>node.material);
  for(let i=0;i<3;i++){
    const restore=maskForLampBloom(scene);
    assert.equal(on.material,originals[0]);assert.notEqual(off.material,originals[1]);assert.equal(body.material.color.getHex(),0);
    assert.equal(glass.material.opacity,0);assert.equal(glass.material.depthWrite,false);assert.equal(mirror.visible,false);
    assert.equal(scene.environment,null);assert.equal(scene.fog,null);
    restore();
    assert.deepEqual([on,off,body,glass,mirror].map(node=>node.material),originals);assert.equal(mirror.visible,true);
    for(const key of Object.keys(original))assert.equal(scene[key],original[key]);
  }
});

test('dimmed lamps do not glow and material arrays keep their original identity',()=>{
  const scene=new THREE.Scene(),materials=[new THREE.MeshStandardMaterial({emissive:'#ffffff',emissiveIntensity:4,opacity:.055}),new THREE.MeshStandardMaterial()];
  const node=new THREE.Mesh(new THREE.BoxGeometry(),materials);node.userData.lightRole='lowBeam';scene.add(node);
  const restore=maskForLampBloom(scene);assert.notEqual(node.material[0],materials[0]);restore();assert.equal(node.material,materials);
});
