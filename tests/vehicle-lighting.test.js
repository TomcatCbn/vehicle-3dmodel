import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { createVehicleLighting } from '../src/vehicle-lighting.js';
import { createLightingState } from '../src/lighting-state.js';

const AUTHORED_INTENSITY = {
  lowBeam: 3,
  highBeam: 5,
  tailLight: 1,
  brakeLight: 4,
  reverseLight: 2,
  ambientLight: 1.5,
  chargeIndicator: 2.5,
};

function fixture() {
  const root = new THREE.Group();
  const meshes = {};
  for (const [role, emissiveIntensity] of Object.entries(AUTHORED_INTENSITY)) {
    const material = new THREE.MeshStandardMaterial({ emissive: '#ffffff', emissiveIntensity });
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(.1, .1, .1), material);
    mesh.name = role;
    mesh.userData.lightRole = role;
    root.add(mesh);
    meshes[role] = mesh;
  }
  const bodyMaterial = new THREE.MeshStandardMaterial({ emissive: '#123456', emissiveIntensity: .7 });
  root.add(new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), bodyMaterial));
  const headlightAnchors = [-1, 1].map(side => {
    const anchor = new THREE.Group();
    anchor.userData.lightAnchor = 'headlight';
    anchor.rotation.y = side * .3;
    root.add(anchor);
    return anchor;
  });
  const ambientAnchors = [-1, 1].map(() => {
    const anchor = new THREE.Group();
    anchor.userData.lightAnchor = 'ambient';
    root.add(anchor);
    return anchor;
  });
  return { root, meshes, bodyMaterial, headlightAnchors, ambientAnchors };
}

function state() {
  return { lighting: createLightingState(), charging: false };
}

function intensity(meshes, role) {
  return meshes[role].material.emissiveIntensity;
}

test('headlight modes restore authored emission and configure paired spotlights', () => {
  const { root, meshes, bodyMaterial, headlightAnchors } = fixture();
  const lighting = createVehicleLighting(root);
  const current = state();
  assert.equal(lighting.lamps.length, 7);
  assert.equal(lighting.spotlights.length, 2);
  assert.equal(lighting.ambientLights.length, 2);
  assert.ok(lighting.spotlights.every(light => !light.visible));
  assert.ok(lighting.ambientLights.every(light => !light.visible));

  lighting.update(current);
  assert.equal(intensity(meshes, 'lowBeam'), AUTHORED_INTENSITY.lowBeam);
  assert.equal(intensity(meshes, 'tailLight'), AUTHORED_INTENSITY.tailLight);
  assert.equal(intensity(meshes, 'highBeam'), 0);
  assert.equal(bodyMaterial.emissiveIntensity, .7);
  assert.equal(bodyMaterial.emissive.getHexString(), '123456');
  lighting.spotlights.forEach((light, index) => {
    const anchor = headlightAnchors[index];
    assert.equal(light.parent, anchor);
    assert.equal(light.target.parent, anchor);
    assert.equal(light.color.getHexString(), 'e8f4ff');
    assert.deepEqual(light.target.position.toArray(), [-10, 0, 0]);
    assert.equal(light.castShadow, false);
    assert.equal(light.visible, true);
    assert.equal(light.intensity, 90);
    assert.equal(light.distance, 28);
    assert.equal(light.angle, .45);
  });

  current.lighting.headlights = 'high';
  lighting.update(current);
  assert.equal(intensity(meshes, 'lowBeam'), AUTHORED_INTENSITY.lowBeam);
  assert.equal(intensity(meshes, 'highBeam'), AUTHORED_INTENSITY.highBeam);
  for (const light of lighting.spotlights) {
    assert.equal(light.intensity, 180);
    assert.equal(light.distance, 45);
    assert.equal(light.angle, .34);
  }

  current.lighting.headlights = 'off';
  current.lighting.tailLights = false;
  lighting.update(current);
  for (const role of ['lowBeam', 'highBeam', 'tailLight']) assert.equal(intensity(meshes, role), 0);
  assert.ok(lighting.spotlights.every(light => !light.visible));

  current.lighting.headlights = 'low';
  current.lighting.tailLights = false;
  lighting.update(current);
  assert.equal(intensity(meshes, 'lowBeam'), AUTHORED_INTENSITY.lowBeam);
  assert.equal(intensity(meshes, 'tailLight'), 0);
  current.lighting.headlights = 'off';
  current.lighting.tailLights = true;
  lighting.update(current);
  assert.equal(intensity(meshes, 'tailLight'), AUTHORED_INTENSITY.tailLight);
});

test('motion, charging and ambient selection independently control their lamps', () => {
  const { root, meshes } = fixture();
  const lighting = createVehicleLighting(root);
  const current = state();
  current.lighting = { headlights: 'off', tailLights: false, ambient: 'ice' };
  const originalMaterials = Object.values(meshes).map(mesh => mesh.material);
  const originalSpots = [...lighting.spotlights];
  const originalPoints = [...lighting.ambientLights];

  lighting.update(current, { braking: true, reversing: true });
  assert.equal(intensity(meshes, 'tailLight'), 0);
  assert.equal(intensity(meshes, 'brakeLight'), AUTHORED_INTENSITY.brakeLight);
  assert.equal(intensity(meshes, 'reverseLight'), AUTHORED_INTENSITY.reverseLight);
  assert.equal(intensity(meshes, 'ambientLight'), AUTHORED_INTENSITY.ambientLight);
  assert.equal(meshes.ambientLight.material.emissive.getHexString(), '8fd8ff');
  assert.equal(intensity(meshes, 'chargeIndicator'), 0);
  for (const light of lighting.ambientLights) {
    assert.equal(light.visible, true);
    assert.equal(light.intensity, 2.5);
    assert.equal(light.distance, 2.4);
    assert.equal(light.decay, 2);
    assert.equal(light.castShadow, false);
    assert.equal(light.color.getHexString(), '8fd8ff');
  }

  current.charging = true;
  lighting.update(current);
  assert.equal(intensity(meshes, 'chargeIndicator'), AUTHORED_INTENSITY.chargeIndicator);
  current.charging = false;
  current.lighting.ambient = 'off';
  lighting.update(current);
  assert.equal(intensity(meshes, 'chargeIndicator'), 0);
  assert.equal(intensity(meshes, 'ambientLight'), 0);
  assert.ok(lighting.ambientLights.every(light => !light.visible && light.intensity === 0));
  assert.deepEqual(Object.values(meshes).map(mesh => mesh.material), originalMaterials);
  assert.deepEqual(lighting.spotlights, originalSpots);
  assert.deepEqual(lighting.ambientLights, originalPoints);
});

test('missing roles and anchors update safely', () => {
  const root = new THREE.Group();
  const mesh = new THREE.Mesh(
    new THREE.BoxGeometry(.1, .1, .1),
    new THREE.MeshStandardMaterial({ emissive: '#ffffff', emissiveIntensity: 1.25 }),
  );
  mesh.userData.lightRole = 'tailLight';
  root.add(mesh);
  const lighting = createVehicleLighting(root);
  const current = state();
  current.lighting.headlights = 'high';

  assert.doesNotThrow(() => lighting.update(current, { braking: true, reversing: true }));
  assert.equal(mesh.material.emissiveIntensity, 1.25);
  assert.equal(lighting.lamps.length, 1);
  assert.equal(lighting.spotlights.length, 0);
  assert.equal(lighting.ambientLights.length, 0);
});
