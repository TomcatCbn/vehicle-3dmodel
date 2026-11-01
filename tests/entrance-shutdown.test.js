import test from 'node:test';
import assert from 'node:assert/strict';
import { createMirror, applyLocalCommand } from '../src/state.js';
import { shutdownAfterEntrance } from '../src/entrance-shutdown.js';

test('natural completion turns all lamps off, locks an unlocked car and enters sleep',async()=>{
  const state=createMirror();state.locked=false;state.powerState='ready';state.lighting.ambient='ice';
  const sent=[];
  const ok=await shutdownAfterEntrance(()=>state,async command=>{sent.push(command);return applyLocalCommand(state,command).ok;});
  assert.equal(ok,true);assert.equal(state.locked,true);assert.equal(state.powerState,'sleep');
  assert.deepEqual(state.lighting,{headlights:'off',tailLights:false,ambient:'off'});
  assert.deepEqual(sent.map(c=>c.type),['set_headlight','toggle_tail_light','set_ambient','toggle_lock','set_power']);
  assert.equal(await shutdownAfterEntrance(()=>state,async()=>{throw Error('must not wake');}),true);
});

test('failed interlock stops the sequence rather than sleeping unlocked',async()=>{
  const state=createMirror();state.locked=false;state.doors.fl.open=true;
  const sent=[];const ok=await shutdownAfterEntrance(()=>state,async command=>{sent.push(command.type);return applyLocalCommand(state,command).ok;});
  assert.equal(ok,false);assert.equal(state.powerState,'standby');assert.equal(state.locked,false);assert.ok(!sent.includes('set_power'));
});

test('Tauri snake-case power state is reflected on the frontend',async()=>{
  const {followSnapshot}=await import('../src/state.js');
  const state=createMirror(),snapshot={...state,power_state:'sleep'};delete snapshot.powerState;followSnapshot(state,snapshot,.1);
  assert.equal(state.powerState,'sleep');
});
