import * as THREE from 'three';
import { explodeOffset } from './state.js';
import { createVehicleLighting } from './vehicle-lighting.js';

function polymerGrain(){
  const size=64,heights=new Float32Array(size*size),data=new Uint8Array(size*size*4);
  let seed=71423;
  for(let i=0;i<heights.length;i++){seed=(Math.imul(seed,1664525)+1013904223)>>>0;heights[i]=seed/4294967296;}
  const height=(x,y)=>heights[((y+size)%size)*size+(x+size)%size];
  for(let y=0;y<size;y++)for(let x=0;x<size;x++){
    const normal=new THREE.Vector3((height(x-1,y)-height(x+1,y))*.24,(height(x,y-1)-height(x,y+1))*.24,1).normalize();
    const i=(y*size+x)*4;
    data[i]=Math.round((normal.x*.5+.5)*255);data[i+1]=Math.round((normal.y*.5+.5)*255);data[i+2]=Math.round((normal.z*.5+.5)*255);data[i+3]=255;
  }
  const texture=new THREE.DataTexture(data,size,size);
  texture.wrapS=texture.wrapT=THREE.RepeatWrapping;texture.magFilter=THREE.LinearFilter;
  texture.minFilter=THREE.LinearMipmapLinearFilter;texture.generateMipmaps=true;texture.needsUpdate=true;
  return texture;
}

/** Bind the named, articulated Blender nodes without replacing their authored geometry. */
export function createVehicle(root) {
  const parts = [], effects = [], paintMaterials = [];
  const yAxis = new THREE.Vector3(0,1,0);
  const axle = new THREE.Vector3(0,0,1);
  let serviceGrain;
  root.traverse(node => {
    if (node.userData.effect) effects.push(node);
    if (!node.userData.part) return;
    node.name = node.userData.label || node.name;
    const meshes = [];
    node.traverse(child => {
      if (!child.isMesh) return;
      child.castShadow = true;
      child.receiveShadow = true;
      if (child.material.name.startsWith('Glazing')) {
        // Thin glazing needs transmission, rather than opaque VSM self shadows.
        child.castShadow = false;
        child.receiveShadow = false;
        const roof = node.name.includes('全景')||node.userData.motion==='sunroof';
        const privacy = child.material.name.includes('rear privacy');
        child.material = new THREE.MeshPhysicalMaterial({
          name: child.material.name,
          color: roof ? '#253844' : privacy ? '#203138' : '#354a50',
          metalness: 0, roughness: .105, transmission: roof ? .12 : privacy ? .42 : .72,
          thickness: .006, ior: 1.48, attenuationColor: '#709080', attenuationDistance: .07,
          envMapIntensity: 1.1, clearcoat: 0,
          side: THREE.DoubleSide,
        });
      } else if(child.material.name.startsWith('Front service ')){
        const tray=child.material.name.includes('tray');
        serviceGrain??=polymerGrain();
        child.material=new THREE.MeshPhysicalMaterial({
          name:child.material.name,color:new THREE.Color().setRGB(.004,.006,.008),
          metalness:0,roughness:tray ? .72 : .54,specularIntensity:tray ? .12 : .15,
          envMapIntensity:tray ? .10 : .14,clearcoat:0,
          normalMap:serviceGrain,normalScale:new THREE.Vector2(tray ? .30 : .18,tray ? .30 : .18),
        });
      } else child.material = child.material.clone();
      const material = child.material;
      if (material.transmission > 0) {
        child.castShadow = false;
        child.receiveShadow = false;
      }
      if (material.name.startsWith('Paint')) paintMaterials.push(material);
      meshes.push({mesh:child, opacity:material.opacity, transparent:material.transparent, depthWrite:material.depthWrite});
    });
    node.userData.base = node.position.clone();
    node.userData.baseQuaternion = node.quaternion.clone();
    node.userData.meshes = meshes;
    node.userData.strutComponents=[];
    node.traverse(child=>{if(child.userData.strut_component)node.userData.strutComponents.push(child);});
    parts.push(node);
  });
  const lighting=createVehicleLighting(root);
  let lastLayer;
  const rotation = new THREE.Quaternion();
  const hoodRotation=new THREE.Quaternion(),tailgateRotation=new THREE.Quaternion(),hinge=new THREE.Vector3(),moving=new THREE.Vector3(),direction=new THREE.Vector3();
  function update(state, progress, layer='all', motion={}) {
    const wheelAngle=motion.wheelAngle||0;
    hoodRotation.setFromAxisAngle(axle,-(state.hoodAngle||0)*1.12*(1-progress));
    tailgateRotation.setFromAxisAngle(axle,(state.tailgatePosition||0)*1.45*(1-progress));
    for (const part of parts) {
      const data = part.userData;
      const [x,y,z] = explodeOffset(data.offset,progress,data.start,Math.min(1,data.start+.42));
      part.position.copy(data.base);
      part.position.x += x;part.position.y += y;part.position.z += z;
      part.quaternion.copy(data.baseQuaternion);
      if(data.motion==='hood')part.quaternion.premultiply(hoodRotation);
      if(data.motion==='tailgate')part.quaternion.premultiply(tailgateRotation);
      if(data.motion==='sunroof'){
        const opening=(state.sunroofPosition||0)*(1-progress);
        const lift=THREE.MathUtils.smoothstep(opening,0,.15),slide=THREE.MathUtils.smoothstep(opening,.15,1);
        part.position.x+=.78*slide;part.position.y+=.065*lift;
        rotation.setFromAxisAngle(axle,.045*lift*(1-.65*slide));part.quaternion.premultiply(rotation);
      }
      if(data.motion==='hood_strut'||data.motion==='tailgate_strut'){
        hinge.fromArray(data.hinge);moving.fromArray(data.moving).sub(hinge).applyQuaternion(data.motion==='hood_strut'?hoodRotation:tailgateRotation).add(hinge);
        direction.subVectors(moving,data.base);const length=direction.length();
        part.quaternion.setFromUnitVectors(yAxis,direction.normalize());
        for(const child of data.strutComponents)child.position.y=child.userData.strut_component==='tip'?length:length-data.piston_length/2;
      }
      if(/轮胎$|轮毂$/.test(part.name)){
        rotation.setFromAxisAngle(axle,wheelAngle);
        part.quaternion.premultiply(rotation);
      }
      if (data.motion === 'door' || data.motion === 'window') {
        rotation.setFromAxisAngle(yAxis,-data.side*state.doorAngle*.95*(1-progress));
        part.quaternion.premultiply(rotation);
      }
      if (data.motion === 'window') part.position.y -= state.windowOpen*.54*(1-progress);
      if (lastLayer !== layer) {
        for (const {mesh,opacity,transparent,depthWrite} of data.meshes) {
          const dimmed = layer !== 'all' && data.layer !== layer;
          const material = mesh.material;
          const nextTransparent = dimmed || transparent;
          if (material.transparent !== nextTransparent) {
            material.transparent = nextTransparent;
            material.needsUpdate = true;
          }
          material.opacity = dimmed ? .055 : opacity;
          material.depthWrite = dimmed ? false : depthWrite;
        }
      }
    }
    for (const effect of effects) effect.visible = progress<.12 && (effect.userData.effect==='cable' ? state.plugged : state.ac);
    lighting.update(state,motion);
    lastLayer = layer;
  }
  function setColor(color) { for (const material of paintMaterials) material.color.set(color); }
  return {root,parts,update,setColor,lighting};
}
