import { createLightingState } from './lighting-state.js';

export const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));

const DEFAULT_POSITIONS = ['fl', 'fr', 'rl', 'rr'];

// ── New nested-structure API (M1.4, decisions 5+7) ──

export function createMirror(positions = DEFAULT_POSITIONS) {
  const doors = {}, windows = {};
  for (const id of positions) {
    doors[id] = { open: false, angle: 0 };
    windows[id] = { target: 0, open: 0 };
  }
  return {
    locked: true,
    doors,
    windows,
    hood: { open: false, angle: 0 },
    sunroof: { target: 0, position: 0 },
    tailgate: { target: 0, position: 0 },
    ac: false,
    temperature: 22,
    plugged: false,
    charging: false,
    battery: 68,
    lighting: createLightingState(),
    powerState: 'standby',
    driving: false,
  };
}

// Browser fallback: advance positions locally (mirrors Rust SignalModel::tick).
export function stepLocalMirror(state, dt) {
  dt = Number.isFinite(dt) ? Math.max(0, dt) : 0;
  for (const win of Object.values(state.windows)) {
    const target = clamp(win.target);
    const delta = target - win.open;
    win.open = clamp(win.open + Math.sign(delta) * Math.min(Math.abs(delta), dt * 0.5));
  }
  for (const door of Object.values(state.doors)) {
    const target = door.open ? 1 : 0;
    const delta = target - door.angle;
    door.angle = clamp(door.angle + Math.sign(delta) * Math.min(Math.abs(delta), dt * 1.5));
  }
  const hoodTarget = state.hood.open ? 1 : 0;
  state.hood.angle = clamp(state.hood.angle + Math.sign(hoodTarget - state.hood.angle) * Math.min(Math.abs(hoodTarget - state.hood.angle), dt * 1.25));
  const srTarget = clamp(state.sunroof.target);
  state.sunroof.position = clamp(state.sunroof.position + Math.sign(srTarget - state.sunroof.position) * Math.min(Math.abs(srTarget - state.sunroof.position), dt * 0.38));
  const tgTarget = clamp(state.tailgate.target);
  state.tailgate.position = clamp(state.tailgate.position + Math.sign(tgTarget - state.tailgate.position) * Math.min(Math.abs(tgTarget - state.tailgate.position), dt * 0.34));
  if (!state.plugged) state.charging = false;
  if (state.charging) state.battery = clamp(state.battery + dt * 0.08, 0, 100);
  if (state.battery >= 100) state.charging = false;
}

// Tauri mode: damp-interpolate frontend mirror toward backend snapshot (decision 5 D5.2).
export function followSnapshot(mirror, snapshot, dt) {
  const k = 12;
  for (const id of Object.keys(mirror.doors)) {
    if (!snapshot.doors || !snapshot.doors[id]) continue;
    mirror.doors[id].angle = THREE_damp(mirror.doors[id].angle, snapshot.doors[id].angle, k, dt);
    mirror.doors[id].open = snapshot.doors[id].open;
  }
  for (const id of Object.keys(mirror.windows)) {
    if (!snapshot.windows || !snapshot.windows[id]) continue;
    mirror.windows[id].open = THREE_damp(mirror.windows[id].open, snapshot.windows[id].open, k, dt);
    mirror.windows[id].target = snapshot.windows[id].target;
  }
  if (snapshot.hood) {
    mirror.hood.angle = THREE_damp(mirror.hood.angle, snapshot.hood.angle, k, dt);
    mirror.hood.open = snapshot.hood.open;
  }
  if (snapshot.sunroof) {
    mirror.sunroof.position = THREE_damp(mirror.sunroof.position, snapshot.sunroof.position, k, dt);
    mirror.sunroof.target = snapshot.sunroof.target;
  }
  if (snapshot.tailgate) {
    mirror.tailgate.position = THREE_damp(mirror.tailgate.position, snapshot.tailgate.position, k, dt);
    mirror.tailgate.target = snapshot.tailgate.target;
  }
  mirror.battery = THREE_damp(mirror.battery, snapshot.battery, k, dt);
  mirror.locked = snapshot.locked;
  mirror.ac = snapshot.ac;
  mirror.temperature = snapshot.temperature;
  mirror.plugged = snapshot.plugged;
  mirror.charging = snapshot.charging;
  if (snapshot.lighting) mirror.lighting = { ...snapshot.lighting };
  // Power state and driving flag (decision 8)
  if (snapshot.powerState !== undefined) mirror.powerState = snapshot.powerState;
  if (snapshot.driving !== undefined) mirror.driving = snapshot.driving;
}

// Exponential damp (matches THREE.MathUtils.damp without importing three).
function THREE_damp(current, target, lambda, dt) {
  return current + (target - current) * (1 - Math.exp(-lambda * dt));
}

// Browser fallback: apply a command locally (mirrors Rust apply_command).
// Returns { ok: true } or { ok: false, error: 'message' }.
// Power state gating per decision 8 D8.12.
export function applyLocalCommand(state, command) {
  const anyDoorOpen = () => Object.values(state.doors).some(d => d.open);
  const anyDoorAjar = () => Object.values(state.doors).some(d => d.open || d.angle > 0.01);
  const isHighVoltage = (cmd) => ['toggle_ac', 'toggle_charging'].includes(cmd.type) ||
    (cmd.type === 'toggle_driving' && cmd.on === true);

  // Power state gating
  const ps = state.powerState || 'standby';
  if (ps === 'sleep' && command.type !== 'set_power' && command.type !== 'reset') {
    return { ok: false, error: '车辆处于休眠状态，请先上电' };
  }
  if (ps === 'standby' && isHighVoltage(command)) {
    return { ok: false, error: '高压未闭合，请先上电至 Ready' };
  }

  switch (command.type) {
    case 'toggle_lock':
      if (!state.locked && anyDoorOpen()) return { ok: false, error: '请先关闭车门，再锁定车辆' };
      state.locked = !state.locked;
      return { ok: true };
    case 'toggle_door':
      if (state.locked) return { ok: false, error: '请先解锁车辆' };
      if (command.id) {
        const door = state.doors[command.id];
        if (door) door.open = !door.open;
      } else {
        const next = !anyDoorOpen();
        for (const door of Object.values(state.doors)) door.open = next;
      }
      return { ok: true };
    case 'set_window': {
      const t = clamp(command.target);
      if (command.id) {
        const win = state.windows[command.id];
        if (win) win.target = t;
      } else {
        for (const win of Object.values(state.windows)) win.target = t;
      }
      return { ok: true };
    }
    case 'set_sunroof':
      state.sunroof.target = clamp(command.target);
      return { ok: true };
    case 'tailgate':
      if (command.action === 'open') state.tailgate.target = 1;
      else if (command.action === 'close') state.tailgate.target = 0;
      else state.tailgate.target = state.tailgate.position;
      return { ok: true };
    case 'toggle_hood':
      state.hood.open = !state.hood.open;
      return { ok: true };
    case 'toggle_ac':
      state.ac = !state.ac;
      return { ok: true };
    case 'set_temperature':
      state.temperature = Math.max(16, Math.min(30, command.value));
      return { ok: true };
    case 'toggle_plug':
      state.plugged = !state.plugged;
      if (!state.plugged) state.charging = false;
      return { ok: true };
    case 'toggle_charging': {
      const on = !state.charging;
      if (on && !state.plugged) return { ok: false, error: '请先连接充电枪' };
      if (on && state.battery >= 100) return { ok: false, error: '电量已满' };
      state.charging = on;
      return { ok: true };
    }
    case 'set_headlight':
      state.lighting.headlights = command.mode;
      return { ok: true };
    case 'toggle_tail_light':
      state.lighting.tailLights = !state.lighting.tailLights;
      return { ok: true };
    case 'set_ambient':
      state.lighting.ambient = command.color;
      return { ok: true };
    case 'toggle_driving':
      if (command.on) {
        if (anyDoorAjar()) return { ok: false, error: '请先关好车门' };
        if (state.hood.open || state.hood.angle > 0.01) return { ok: false, error: '请先关好机盖' };
        if (state.tailgate.target > 0.001 || state.tailgate.position > 0.001) return { ok: false, error: '请先关好尾门' };
        if (state.plugged) return { ok: false, error: '请拔出充电枪' };
      }
      state.driving = command.on;
      return { ok: true };
    case 'set_power':
      if (command.state === 'sleep' && state.driving) {
        return { ok: false, error: '请先停止行驶' };
      }
      state.powerState = command.state;
      return { ok: true };
    case 'reset':
      Object.assign(state, createMirror());
      return { ok: true };
    default:
      return { ok: false, error: '未知命令' };
  }
}

export function explodeOffset(offset, progress, start = 0, end = 1) {
  const t = clamp((progress - start) / (end - start));
  const eased = t * t * (3 - 2 * t);
  return offset.map(value => value === 0 || eased === 0 ? 0 : value * eased);
}

// ── Legacy API (deprecated — kept for test compatibility) ──

export function createState() {
  return { locked: true, doorsOpen: false, doorAngle: 0, hoodOpen: false, hoodAngle: 0, sunroofTarget:0, sunroofPosition:0, tailgateTarget:0, tailgatePosition:0, windowTarget: 0, windowOpen: 0, ac: false, temperature: 22, plugged: false, charging: false, battery: 68, lighting: createLightingState() };
}

export function stepVehicle(state, dt) {
  dt=Number.isFinite(dt)?Math.max(0,dt):0;
  const delta = clamp(state.windowTarget) - state.windowOpen;
  state.windowOpen = clamp(state.windowOpen + Math.sign(delta) * Math.min(Math.abs(delta), Math.max(0, dt) * 0.5));
  const doorTarget = state.doorsOpen ? 1 : 0;
  state.doorAngle += Math.sign(doorTarget - state.doorAngle) * Math.min(Math.abs(doorTarget - state.doorAngle), Math.max(0, dt) * 1.5);
  const hoodTarget=state.hoodOpen?1:0;
  state.hoodAngle+=Math.sign(hoodTarget-state.hoodAngle)*Math.min(Math.abs(hoodTarget-state.hoodAngle),Math.max(0,dt)*1.25);
  for(const [position,target,speed] of [['sunroofPosition','sunroofTarget',.38],['tailgatePosition','tailgateTarget',.34]]){
    const delta=clamp(state[target])-state[position];
    state[position]=clamp(state[position]+Math.sign(delta)*Math.min(Math.abs(delta),dt*speed));
  }
  if (!state.plugged) state.charging = false;
  if (state.charging) state.battery = clamp(state.battery + Math.max(0, dt) * 0.08, 0, 100);
  if (state.battery >= 100) state.charging = false;
}

export function setCharging(state, on) {
  if (on && (!state.plugged || state.battery >= 100)) return false;
  state.charging = on;
  return true;
}
