export const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));
export function createState() {
  return { locked: true, doorsOpen: false, doorAngle: 0, hoodOpen: false, hoodAngle: 0, windowTarget: 0, windowOpen: 0, ac: false, temperature: 22, plugged: false, charging: false, battery: 68, lights: true };
}
export function stepVehicle(state, dt) {
  const delta = clamp(state.windowTarget) - state.windowOpen;
  state.windowOpen = clamp(state.windowOpen + Math.sign(delta) * Math.min(Math.abs(delta), Math.max(0, dt) * 0.5));
  const doorTarget = state.doorsOpen ? 1 : 0;
  state.doorAngle += Math.sign(doorTarget - state.doorAngle) * Math.min(Math.abs(doorTarget - state.doorAngle), Math.max(0, dt) * 1.5);
  const hoodTarget=state.hoodOpen?1:0;
  state.hoodAngle+=Math.sign(hoodTarget-state.hoodAngle)*Math.min(Math.abs(hoodTarget-state.hoodAngle),Math.max(0,dt)*1.25);
  if (!state.plugged) state.charging = false;
  if (state.charging) state.battery = clamp(state.battery + Math.max(0, dt) * 0.08, 0, 100);
  if (state.battery >= 100) state.charging = false;
}
export function setCharging(state, on) {
  if (on && (!state.plugged || state.battery >= 100)) return false;
  state.charging = on;
  return true;
}
export function explodeOffset(offset, progress, start = 0, end = 1) {
  const t = clamp((progress - start) / (end - start));
  const eased = t * t * (3 - 2 * t);
  return offset.map(value => value === 0 || eased === 0 ? 0 : value * eased);
}
