import * as THREE from 'three';
import { deriveLighting } from '../lighting-state.js';

export function createVehicleLighting(root) {
  const lamps = [];
  const spotlights = [];
  const ambientLights = [];

  root.traverse(node => {
    if (node.isMesh && node.userData.lightRole) {
      lamps.push({
        role: node.userData.lightRole,
        material: node.material,
        emissiveIntensity: node.material.emissiveIntensity,
      });
    }
    if (node.userData.lightAnchor === 'headlight') {
      const light = new THREE.SpotLight('#e8f4ff', 90, 28, .45);
      const target = new THREE.Object3D();
      target.position.set(-10, 0, 0);
      light.visible = false;
      light.castShadow = false;
      light.target = target;
      node.add(light, target);
      spotlights.push(light);
    }
    if (node.userData.lightAnchor === 'ambient') {
      const light = new THREE.PointLight('#ffffff', 0, 2.4, 2);
      light.visible = false;
      light.castShadow = false;
      node.add(light);
      ambientLights.push(light);
    }
  });

  function update(state, motion = {}) {
    const derived = deriveLighting(state.lighting, motion);
    const ambientEnabled = derived.ambientColor !== null;
    for (const lamp of lamps) {
      const enabled = lamp.role === 'chargeIndicator'
        ? Boolean(state.charging)
        : lamp.role === 'ambientLight'
          ? ambientEnabled
          : Boolean(derived[lamp.role]);
      if (lamp.role === 'ambientLight' && ambientEnabled) lamp.material.emissive.set(derived.ambientColor);
      lamp.material.emissiveIntensity = enabled ? lamp.emissiveIntensity : 0;
    }
    for (const light of spotlights) {
      light.visible = derived.lowBeam;
      light.intensity = derived.highBeam ? 180 : 90;
      light.distance = derived.highBeam ? 45 : 28;
      light.angle = derived.highBeam ? .34 : .45;
    }
    for (const light of ambientLights) {
      light.visible = ambientEnabled;
      light.intensity = ambientEnabled ? 2.5 : 0;
      if (ambientEnabled) light.color.set(derived.ambientColor);
    }
  }

  return { lamps, spotlights, ambientLights, update };
}
