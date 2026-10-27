import test from 'node:test';
import assert from 'node:assert/strict';
import * as lightingState from '../src/lighting-state.js';

const { AMBIENT_COLORS, createLightingState, deriveLighting } = lightingState;

test('ambient presets are immutable and exact', () => {
  assert.deepEqual(AMBIENT_COLORS, { off: null, warm: '#FFD9A0', ice: '#8FD8FF', purple: '#B49AFF' });
  assert.equal(Object.isFrozen(AMBIENT_COLORS), true);
});

test('lighting defaults are exact and fresh', () => {
  const first = createLightingState();
  const second = createLightingState();
  assert.deepEqual(first, { headlights: 'low', tailLights: true, ambient: 'off' });
  assert.notStrictEqual(first, second);
});

test('off, low, and high headlights derive exact effective outputs', () => {
  for (const [headlights, lowBeam, highBeam] of [['off', false, false], ['low', true, false], ['high', true, true]]) {
    assert.deepEqual(deriveLighting({ headlights, tailLights: true, ambient: 'off' }), {
      lowBeam,
      highBeam,
      tailLight: true,
      brakeLight: false,
      reverseLight: false,
      ambientColor: null,
    });
  }
});

test('invalid headlight modes fall back to off', () => {
  assert.deepEqual(deriveLighting({ headlights: 'invalid', tailLights: false, ambient: 'off' }), {
    lowBeam: false,
    highBeam: false,
    tailLight: false,
    brakeLight: false,
    reverseLight: false,
    ambientColor: null,
  });
});

test('brake and reverse lights independently override disabled tail lights', () => {
  for (const [motion, brakeLight, reverseLight] of [
    [{ braking: true }, true, false],
    [{ reversing: true }, false, true],
    [{ braking: true, reversing: true }, true, true],
  ]) {
    const result = deriveLighting({ headlights: 'off', tailLights: false, ambient: 'off' }, motion);
    assert.equal(result.tailLight, false);
    assert.equal(result.brakeLight, brakeLight);
    assert.equal(result.reverseLight, reverseLight);
  }
});

test('ambient presets derive exact colors and invalid or missing values derive null', () => {
  for (const [ambient, ambientColor] of Object.entries(AMBIENT_COLORS)) {
    assert.equal(deriveLighting({ headlights: 'off', tailLights: false, ambient }).ambientColor, ambientColor);
  }
  for (const ambient of ['unknown', 'toString', '__proto__', undefined]) {
    assert.equal(deriveLighting({ headlights: 'off', tailLights: false, ambient }).ambientColor, null);
  }
  assert.equal(deriveLighting({ headlights: 'off', tailLights: false }).ambientColor, null);
});
