import * as THREE from 'three';
import { explodeOffset } from './state.js';

/** Bind the named, articulated Blender nodes without replacing their authored geometry. */
export function createVehicle(root) {
  const parts = [], effects = [], paintMaterials = [], lights = [];
  const yAxis = new THREE.Vector3(0,1,0);
  const axle = new THREE.Vector3(0,0,1);
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
        const roof = node.name.includes('全景');
        const privacy = child.material.name.includes('rear privacy');
        child.material = new THREE.MeshPhysicalMaterial({
          name: child.material.name,
          color: roof ? '#253844' : privacy ? '#203138' : '#354a50',
          metalness: 0, roughness: .105, transmission: roof ? .12 : privacy ? .42 : .72,
          thickness: .006, ior: 1.48, attenuationColor: '#709080', attenuationDistance: .07,
          envMapIntensity: 1.1, clearcoat: 0,
          side: THREE.DoubleSide,
        });
      } else child.material = child.material.clone();
      const material = child.material;
      if (material.transmission > 0) {
        child.castShadow = false;
        child.receiveShadow = false;
      }
      if (material.name.startsWith('Paint')) paintMaterials.push(material);
      if (material.name.includes('LED')) lights.push({material, intensity:material.emissiveIntensity});
      meshes.push({mesh:child, opacity:material.opacity, transparent:material.transparent, depthWrite:material.depthWrite});
    });
    node.userData.base = node.position.clone();
    node.userData.baseQuaternion = node.quaternion.clone();
    node.userData.meshes = meshes;
    parts.push(node);
  });
  let lastLayer;
  const rotation = new THREE.Quaternion();
  function update(state, progress, layer='all', wheelAngle=0) {
    for (const part of parts) {
      const data = part.userData;
      const [x,y,z] = explodeOffset(data.offset,progress,data.start,Math.min(1,data.start+.42));
      part.position.copy(data.base);
      part.position.x += x;part.position.y += y;part.position.z += z;
      part.quaternion.copy(data.baseQuaternion);
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
    for (const {material,intensity} of lights) material.emissiveIntensity = state.lights ? intensity : .05;
    lastLayer = layer;
  }
  function setColor(color) { for (const material of paintMaterials) material.color.set(color); }
  return {root,parts,update,setColor};
}
