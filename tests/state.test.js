import test from 'node:test';
import assert from 'node:assert/strict';
import { createState, stepVehicle, setCharging, explodeOffset } from '../src/state.js';

test('windows move toward a requested position without overshooting', () => {
  const state = createState();
  state.windowTarget = 1;
  stepVehicle(state, 0.5);
  assert.ok(state.windowOpen > 0 && state.windowOpen < 1);
  stepVehicle(state, 20);
  assert.equal(state.windowOpen, 1);
  state.windowTarget = 0;
  stepVehicle(state, 20);
  assert.equal(state.windowOpen, 0);
});
test('charging requires a connected cable and stops when unplugged', () => {
  const state = createState();
  assert.equal(setCharging(state, true), false);
  assert.equal(state.charging, false);
  state.plugged = true;
  assert.equal(setCharging(state, true), true);
  const before = state.battery;
  stepVehicle(state, 20);
  assert.ok(state.battery > before);
  state.plugged = false;
  stepVehicle(state, 1);
  assert.equal(state.charging, false);
});
test('explosion is reversible, clamped, and preserves assembled positions', () => {
  const offset = [1.5, 3, -2];
  assert.deepEqual(explodeOffset(offset, -1, 0.2, 0.8), [0, 0, 0]);
  assert.deepEqual(explodeOffset(offset, 1, 0.2, 0.8), offset);
  assert.deepEqual(explodeOffset(offset, 0, 0.2, 0.8), [0, 0, 0]);
  assert.ok(explodeOffset(offset, 0.5, 0.2, 0.8)[1] > 0);
});
