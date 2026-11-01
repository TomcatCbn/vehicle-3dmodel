# Vehicle Lighting and Reverse Driving Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add independently controlled vehicle lamps, projected low/high beams, ambient presets, brake/reverse integration, and low-speed reverse driving.

**Architecture:** Author explicit lamp roles and anchors in the Blender GLB, derive effective lighting from pure state, and apply it in a focused Three.js controller. Keep driving state independent from rendering and expose only wheel/brake/reverse telemetry to the vehicle renderer.

**Tech Stack:** JavaScript ES modules, Three.js, Blender Python, glTF 2.0, Node.js `node:test`, Vite, HTML/CSS.

**Specification:** `docs/superpowers/specs/2026-10-25-vehicle-lighting-design.md`

**Blender prerequisite:** The regeneration steps require `blender` on PATH. Confirm with `command -v blender` before Task 3; if unavailable, install Blender or make its CLI available rather than editing the GLB by hand.

**Commit policy:** Commit steps are optional checkpoints. Skip every commit unless the user explicitly requests one; never amend, push, or create a PR without an explicit request.

---

## File Map

- Create `src/lighting-state.js`: lighting defaults, preset definitions, and pure effective-output derivation.
- Create `src/vehicle-lighting.js`: index authored lamp roles/anchors and apply emissive materials, two spotlights, and two interior point lights.
- Modify `src/state.js`: compose explicit lighting state into the shared vehicle state.
- Modify `src/drive-state.js`: signed speed/distance, direction changes, reverse speed limit, and brake derivation.
- Modify `src/vehicle.js`: delegate lamp updates and accept driving telemetry.
- Modify `src/driving.js`: direction UI, absolute readouts, reverse road/wheel movement, and telemetry returned to the renderer.
- Modify `src/main.js`: lighting controls and driving telemetry wiring.
- Modify `scripts/build_aura_t6.py`: independent emissive materials, lamp-role metadata, and headlight/ambient anchors.
- Modify `public/models/aura-t6.glb`, `public/models/aura-t6.json`, `models/aura-t6.blend`: regenerate through the documented Blender command.
- Modify `index.html` and `src/style.css`: accessible lighting/direction controls and responsive layout.
- Create `tests/lighting-state.test.js` and `tests/vehicle-lighting.test.js`: focused pure/runtime lighting coverage.
- Modify `tests/state.test.js`, `tests/driving.test.js`, `tests/vehicle.test.js`, `tests/model-asset.test.js`: defaults, reverse, integration, and production asset contracts.
- Modify `README.md`: document new interactions and reverse limits.

### Task 1: Signed Reverse Driving State

**Files:**
- Modify: `src/drive-state.js`
- Test: `tests/driving.test.js`

- [ ] **Step 1: Write failing direction, reverse, and braking tests**

Append these tests to `tests/driving.test.js` and change its import to include `isBraking`, `maxDriveSpeed`, and `setDirection`:

```js
import { createDriveState, setDriving, stepDrive, isBraking, maxDriveSpeed, setDirection } from '../src/drive-state.js';

test('direction changes only at standstill and reverse is limited to 20 km/h',()=>{
  const drive=createDriveState(),vehicle=createState();
  setDriving(drive,vehicle,true);stepDrive(drive,1);
  assert.equal(setDirection(drive,-1),false);
  assert.equal(drive.direction,1);
  setDriving(drive,vehicle,false);stepDrive(drive,20);
  assert.equal(drive.speed,0);
  assert.equal(setDirection(drive,-1),true);
  assert.equal(maxDriveSpeed(drive),20);
  drive.targetSpeed=100;setDriving(drive,vehicle,true);stepDrive(drive,30);
  assert.equal(drive.speed,-20);
  assert.ok(drive.distance<0);
  assert.equal(isBraking(drive),false);
  setDriving(drive,vehicle,false);
  assert.equal(isBraking(drive),true);
  stepDrive(drive,20);
  assert.equal(drive.speed,0);
  assert.equal(isBraking(drive),false);
  assert.equal(setDirection(drive,0),false);
});

test('reverse acceleration and braking rates preserve smooth signed speed',()=>{
  const drive=createDriveState(),vehicle=createState();
  setDirection(drive,-1);drive.targetSpeed=20;setDriving(drive,vehicle,true);
  stepDrive(drive,1);
  assert.equal(drive.speed,-10);
  drive.targetSpeed=0;stepDrive(drive,.25);
  assert.equal(drive.speed,-4);
  stepDrive(drive,1);
  assert.equal(drive.speed,0);
});

test('active deceleration is braking but maintaining speed is not',()=>{
  const drive=createDriveState(),vehicle=createState();
  drive.targetSpeed=40;setDriving(drive,vehicle,true);stepDrive(drive,20);
  assert.equal(isBraking(drive),false);
  drive.targetSpeed=10;
  assert.equal(isBraking(drive),true);
  stepDrive(drive,20);
  assert.equal(drive.speed,10);
  assert.equal(isBraking(drive),false);
});
```

- [ ] **Step 2: Run the tests and confirm the missing exports fail**

Run: `node --test tests/driving.test.js`

Expected: FAIL during module import because `isBraking`, `maxDriveSpeed`, and `setDirection` are not exported yet.

- [ ] **Step 3: Implement signed driving with a direction-aware target**

Replace the contents of `src/drive-state.js` with:

```js
import { clamp } from './state.js';

export const WHEEL_RADIUS=.372;
export function createDriveState(){return {running:false,targetSpeed:40,speed:0,distance:0,direction:1};}
export function maxDriveSpeed(drive){return drive.direction===-1?20:100;}
export function setDirection(drive,direction){
  if(drive.speed!==0||![-1,1].includes(direction))return false;
  drive.direction=direction;
  drive.targetSpeed=clamp(drive.targetSpeed,0,maxDriveSpeed(drive));
  return true;
}
export function setDriving(drive,vehicle,on){
  if(on&&(vehicle.doorsOpen||vehicle.doorAngle>.01||vehicle.hoodOpen||vehicle.hoodAngle>.01||vehicle.plugged))return false;
  drive.running=on;
  return true;
}
export function signedTargetSpeed(drive){
  const magnitude=drive.running&&Number.isFinite(drive.targetSpeed)?clamp(drive.targetSpeed,0,maxDriveSpeed(drive)):0;
  return drive.direction*magnitude;
}
export function isBraking(drive){
  return drive.speed!==0&&Math.abs(drive.speed)>Math.abs(signedTargetSpeed(drive));
}
export function stepDrive(drive,dt){
  if(!Number.isFinite(dt)||dt<=0)return;
  const target=signedTargetSpeed(drive);
  const old=drive.speed,rate=Math.abs(target)>Math.abs(old)?10:24;
  const ramp=Math.min(dt,Math.abs(target-old)/rate);
  drive.speed=old+Math.sign(target-old)*rate*ramp;
  if(Math.abs(drive.speed-target)<1e-8)drive.speed=target;
  drive.distance+=((old+drive.speed)*.5*ramp+drive.speed*(dt-ramp))/3.6;
}
```

- [ ] **Step 4: Run all driving tests**

Run: `node --test tests/driving.test.js`

Expected: all driving tests PASS, including the original forward, parking, door, cable, bonnet, and invalid-time cases.

- [ ] **Step 5: Commit the driving-state checkpoint**

```bash
git add src/drive-state.js tests/driving.test.js
git commit -m "feat: add reverse driving state"
```

### Task 2: Pure Lighting Defaults and Output Derivation

**Files:**
- Create: `src/lighting-state.js`
- Modify: `src/state.js`
- Create: `tests/lighting-state.test.js`
- Modify: `tests/state.test.js`

- [ ] **Step 1: Write failing lighting-state tests**

Create `tests/lighting-state.test.js`:

```js
import test from 'node:test';
import assert from 'node:assert/strict';
import { AMBIENT_COLORS, createLightingState, deriveLighting } from '../src/lighting-state.js';

test('lighting defaults to low beams and tail lights with ambient off',()=>{
  assert.deepEqual(createLightingState(),{headlights:'low',tailLights:true,ambient:'off'});
});

test('off, low, and high produce independent front-lamp outputs',()=>{
  const lighting=createLightingState();
  for(const [mode,lowBeam,highBeam] of [['off',false,false],['low',true,false],['high',true,true]]){
    lighting.headlights=mode;
    const output=deriveLighting(lighting);
    assert.equal(output.lowBeam,lowBeam);
    assert.equal(output.highBeam,highBeam);
  }
});

test('brake and reverse telemetry override manual rear-light state independently',()=>{
  const lighting=createLightingState();lighting.tailLights=false;
  let output=deriveLighting(lighting,{braking:true,reversing:false});
  assert.equal(output.tailLight,false);
  assert.equal(output.brakeLight,true);
  assert.equal(output.reverseLight,false);
  output=deriveLighting(lighting,{braking:false,reversing:true});
  assert.equal(output.brakeLight,false);
  assert.equal(output.reverseLight,true);
});

test('ambient presets expose fixed colors and invalid values remain off',()=>{
  const lighting=createLightingState();
  assert.equal(deriveLighting(lighting).ambientColor,null);
  for(const [name,color] of Object.entries(AMBIENT_COLORS)){
    lighting.ambient=name;
    assert.equal(deriveLighting(lighting).ambientColor,color);
  }
  lighting.ambient='unknown';
  assert.equal(deriveLighting(lighting).ambientColor,null);
});
```

Append to `tests/state.test.js`:

```js
test('vehicle state owns one explicit lighting state object',()=>{
  const state=createState();
  assert.deepEqual(state.lighting,{headlights:'low',tailLights:true,ambient:'off'});
  assert.equal('lights' in state,false);
});
```

- [ ] **Step 2: Run the tests and confirm the new module is missing**

Run: `node --test tests/lighting-state.test.js tests/state.test.js`

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/lighting-state.js`.

- [ ] **Step 3: Implement pure lighting derivation and compose vehicle defaults**

Create `src/lighting-state.js`:

```js
export const AMBIENT_COLORS=Object.freeze({off:null,warm:'#FFD9A0',ice:'#8FD8FF',purple:'#B49AFF'});
export function createLightingState(){return {headlights:'low',tailLights:true,ambient:'off'};}
export function deriveLighting(lighting,motion={}){
  const mode=['off','low','high'].includes(lighting.headlights)?lighting.headlights:'off';
  return {
    lowBeam:mode!=='off',
    highBeam:mode==='high',
    tailLight:Boolean(lighting.tailLights),
    brakeLight:Boolean(motion.braking),
    reverseLight:Boolean(motion.reversing),
    ambientColor:Object.hasOwn(AMBIENT_COLORS,lighting.ambient)?AMBIENT_COLORS[lighting.ambient]:null,
  };
}
```

Add this import at the top of `src/state.js`:

```js
import { createLightingState } from './lighting-state.js';
```

In `createState()`, replace `lights: true` with `lighting: createLightingState()`, leaving every other existing state field unchanged:

```js
return { locked: true, doorsOpen: false, doorAngle: 0, hoodOpen: false, hoodAngle: 0, windowTarget: 0, windowOpen: 0, ac: false, temperature: 22, plugged: false, charging: false, battery: 68, lighting: createLightingState() };
```

- [ ] **Step 4: Run state and lighting tests**

Run: `node --test tests/lighting-state.test.js tests/state.test.js`

Expected: all tests PASS.

- [ ] **Step 5: Commit the pure lighting checkpoint**

```bash
git add src/lighting-state.js src/state.js tests/lighting-state.test.js tests/state.test.js
git commit -m "feat: add explicit vehicle lighting state"
```

### Task 3: Author Independent Model Lamps and Anchors

**Files:**
- Modify: `scripts/build_aura_t6.py`
- Modify: `tests/model-asset.test.js`
- Regenerate: `public/models/aura-t6.glb`
- Regenerate: `public/models/aura-t6.json`
- Regenerate: `models/aura-t6.blend`

- [ ] **Step 1: Write the failing production-asset contract**

Append to `tests/model-asset.test.js`:

```js
test('real GLB exposes every independent light role and exactly two headlight and ambient anchors',async()=>{
  const root=(await loadModel()).scene,nodes=[];
  root.traverse(node=>nodes.push(node));
  for(const role of ['lowBeam','highBeam','tailLight','brakeLight','reverseLight','ambientLight','chargeIndicator']){
    assert.ok(nodes.some(node=>node.isMesh&&node.userData.lightRole===role),`missing ${role}`);
  }
  assert.equal(nodes.filter(node=>node.userData.lightAnchor==='headlight').length,2);
  assert.equal(nodes.filter(node=>node.userData.lightAnchor==='ambient').length,2);
  const charge=nodes.find(node=>node.userData.lightRole==='chargeIndicator');
  assert.notEqual(charge.userData.lightRole,'lowBeam');
});
```

- [ ] **Step 2: Run the asset test against the old GLB**

Run: `node --test tests/model-asset.test.js`

Expected: the new test FAILS with `missing lowBeam`; all pre-existing asset tests still run.

- [ ] **Step 3: Add model materials and explicit metadata helpers**

In `scripts/build_aura_t6.py`, replace the `led` and `red` material declarations with:

```python
low_led = mat('Low beam emission', (.78,.94,1), .2,.22, 3)
high_led = mat('High beam emission', (.88,.96,1), .15,.18, 5)
tail_led = mat('Tail light emission', (.8,.018,.025), .1,.25, 2)
brake_led = mat('Brake light emission', (1,.008,.012), .1,.22, 5)
reverse_led = mat('Reverse light emission', (.9,.95,1), .1,.2, 3)
ambient_led = mat('Ambient light emission', (1,.72,.42), 0,.3, 1.5)
charge_led = mat('Charge indicator emission', (.2,1,.55), 0,.25, 2)
```

Add these helpers immediately after `parent()`:

```python
def light_role(obj, role):
    obj['lightRole'] = role
    return obj

def light_anchor(name, location, group, role):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.update()
    obj.parent = group
    obj.matrix_parent_inverse = group.matrix_world.inverted()
    obj.location = location
    obj['lightAnchor'] = role
    return obj
```

- [ ] **Step 4: Bind front lamps, rear lamps, reverse lamps, and charging to separate roles**

Wrap the two existing running-light `tube()` calls with `light_role(..., 'lowBeam')` and replace their material argument `led` with `low_led`:

```python
light_role(tube('Continuous slim running light',led_points,.0028,low_led,lightbar),'lowBeam')
light_role(tube('Brow light guide',brow,.006,low_led,lightbar,smooth=True),'lowBeam')
```

Replace the projection-lens `parent()` call inside the `for dz in [-.043,.054]` loop, and add one anchor after that loop:

```python
lens_material = high_led if dz>0 else low_led
parent(lens,lamp,lens_material)
light_role(lens,'highBeam' if dz>0 else 'lowBeam')
```

Insert after the projection-lens loop, before the inboard chamber is created:

```python
light_anchor('Headlight beam anchor',lp(-.035,.035,-.043),lamp,'headlight')
```

Replace the high-mounted stop lamp call with:

```python
light_role(box('High mounted stop lamp',(1.915,0,1.505),(.010,.59,.012),brake_led,spoiler,.005),'brakeLight')
```

In both rear light-guide creation loops, select tail vs brake by the existing `height` value and tag the returned mesh. The flat-guide final expression becomes:

```python
guide_material = brake_led if height<1.07 else tail_led
guide_role = 'brakeLight' if height<1.07 else 'tailLight'
light_role(mesh('Flat rear light guide',vs,fs,rear_lights,guide_material,.001),guide_role)
```

The tapered-guide final expression becomes:

```python
guide_material = brake_led if height<1.07 else tail_led
guide_role = 'brakeLight' if height<1.07 else 'tailLight'
light_role(mesh('Tapered side tail light guide',vs,fs,rear_lights,guide_material,.001),guide_role)
```

Insert reverse lamps after the rear license plate label and before `rear_lights=part(...)`:

```python
for side in [-1,1]:
    y=side*.62;z=.49;x=rear_surface(y,z)[0]+.012
    light_role(box('Reverse lamp',(x,y,z),(.014,.16,.035),reverse_led,rear_bumper,.006),'reverseLight')
```

Replace the charging indicator call with:

```python
light_role(box('Charge indicator',(1.74,1.025,1.04),(.08,.12,.01),charge_led,cable,.004),'chargeIndicator')
```

No remaining lamp or charging call may use the removed `led` or `red` names.

- [ ] **Step 5: Add two interior strips and two interior light anchors**

Insert immediately after the existing `Driver display` dashboard box:

```python
for side in [-1,1]:
    light_role(box('Dashboard ambient strip',(-.48,side*.48,1.0),(.025,.50,.012),ambient_led,dash,.004),'ambientLight')
    light_anchor('Cabin ambient anchor',(-.20,side*.43,1.28),dash,'ambient')
```

- [ ] **Step 6: Regenerate and validate the model**

Run:

```bash
blender --background --python scripts/build_aura_t6.py
```

Expected: `AURA_EXPORT` reports 89 parts and writes the GLB/JSON/Blend outputs without a Blender exception.

Run: `node --test tests/model-asset.test.js`

Expected: all asset tests PASS, including 89 parts, original bounds, all seven light roles, and exactly two anchors of each type.

- [ ] **Step 7: Commit the authored model checkpoint**

```bash
git add scripts/build_aura_t6.py tests/model-asset.test.js public/models/aura-t6.glb public/models/aura-t6.json models/aura-t6.blend
git commit -m "feat: author independent vehicle lamp geometry"
```

### Task 4: Three.js Lamp and Projected-Light Controller

**Files:**
- Create: `src/vehicle-lighting.js`
- Create: `tests/vehicle-lighting.test.js`

- [ ] **Step 1: Write failing material and real-light tests**

Create `tests/vehicle-lighting.test.js`:

```js
import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { createVehicleLighting } from '../src/vehicle-lighting.js';
import { createState } from '../src/state.js';

function fixture(){
  const root=new THREE.Group(),materials={};
  for(const role of ['lowBeam','highBeam','tailLight','brakeLight','reverseLight','ambientLight','chargeIndicator']){
    const material=new THREE.MeshStandardMaterial({emissive:'#ffffff',emissiveIntensity:role==='brakeLight'?5:2});
    const mesh=new THREE.Mesh(new THREE.BoxGeometry(.1,.1,.1),material);
    mesh.userData.lightRole=role;root.add(mesh);materials[role]=material;
  }
  for(let i=0;i<2;i++){
    const headlight=new THREE.Object3D();headlight.userData.lightAnchor='headlight';root.add(headlight);
    const ambient=new THREE.Object3D();ambient.userData.lightAnchor='ambient';root.add(ambient);
  }
  return {root,materials};
}

test('manual lamps restore authored intensity and switch completely off',()=>{
  const {root,materials}=fixture(),lighting=createVehicleLighting(root),state=createState();
  lighting.update(state);
  assert.equal(materials.lowBeam.emissiveIntensity,2);
  assert.equal(materials.highBeam.emissiveIntensity,0);
  assert.equal(materials.tailLight.emissiveIntensity,2);
  assert.equal(lighting.spotlights.length,2);
  assert.ok(lighting.spotlights.every(light=>light.visible&&light.intensity===90));
  state.lighting.headlights='high';lighting.update(state);
  assert.equal(materials.highBeam.emissiveIntensity,2);
  assert.ok(lighting.spotlights.every(light=>light.intensity===180&&light.distance===45));
  state.lighting.headlights='off';state.lighting.tailLights=false;lighting.update(state);
  assert.equal(materials.lowBeam.emissiveIntensity,0);
  assert.equal(materials.highBeam.emissiveIntensity,0);
  assert.equal(materials.tailLight.emissiveIntensity,0);
  assert.ok(lighting.spotlights.every(light=>!light.visible));
});

test('brake, reverse, ambient, and charging outputs remain independent',()=>{
  const {root,materials}=fixture(),lighting=createVehicleLighting(root),state=createState();
  state.lighting.tailLights=false;state.lighting.ambient='ice';
  lighting.update(state,{braking:true,reversing:true});
  assert.equal(materials.tailLight.emissiveIntensity,0);
  assert.equal(materials.brakeLight.emissiveIntensity,5);
  assert.equal(materials.reverseLight.emissiveIntensity,2);
  assert.equal(materials.ambientLight.emissive.getHexString(),'8fd8ff');
  assert.ok(lighting.ambientLights.every(light=>light.visible&&light.color.getHexString()==='8fd8ff'));
  assert.equal(materials.chargeIndicator.emissiveIntensity,0);
  state.charging=true;lighting.update(state);
  assert.equal(materials.chargeIndicator.emissiveIntensity,2);
  state.lighting.ambient='off';lighting.update(state);
  assert.equal(materials.ambientLight.emissiveIntensity,0);
  assert.ok(lighting.ambientLights.every(light=>!light.visible));
});

test('a missing individual lamp mesh does not break remaining lighting',()=>{
  const root=new THREE.Group(),material=new THREE.MeshStandardMaterial({emissive:'#fff',emissiveIntensity:3});
  const mesh=new THREE.Mesh(new THREE.BoxGeometry(),material);mesh.userData.lightRole='tailLight';root.add(mesh);
  const lighting=createVehicleLighting(root),state=createState();
  assert.doesNotThrow(()=>lighting.update(state,{braking:true,reversing:true}));
  assert.equal(material.emissiveIntensity,3);
  assert.equal(lighting.spotlights.length,0);
});
```

- [ ] **Step 2: Confirm the runtime controller is missing**

Run: `node --test tests/vehicle-lighting.test.js`

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/vehicle-lighting.js`.

- [ ] **Step 3: Implement the focused Three.js controller**

Create `src/vehicle-lighting.js`:

```js
import * as THREE from 'three';
import { deriveLighting } from './lighting-state.js';

export function createVehicleLighting(root){
  const lamps=[],spotlights=[],ambientLights=[];
  root.traverse(node=>{
    if(node.isMesh&&node.userData.lightRole){
      lamps.push({role:node.userData.lightRole,material:node.material,intensity:node.material.emissiveIntensity});
    }
    if(node.userData.lightAnchor==='headlight'){
      const light=new THREE.SpotLight('#e8f4ff',0,28,.45,.55,2);
      const target=new THREE.Object3D();target.position.set(-10,0,0);
      node.add(light,target);light.target=target;light.castShadow=false;light.visible=false;
      spotlights.push(light);
    }
    if(node.userData.lightAnchor==='ambient'){
      const light=new THREE.PointLight('#ffffff',0,2.4,2);light.castShadow=false;light.visible=false;
      node.add(light);ambientLights.push(light);
    }
  });
  function update(state,motion={}){
    const output=deriveLighting(state.lighting,motion);
    const enabled={
      lowBeam:output.lowBeam,
      highBeam:output.highBeam,
      tailLight:output.tailLight,
      brakeLight:output.brakeLight,
      reverseLight:output.reverseLight,
      ambientLight:Boolean(output.ambientColor),
      chargeIndicator:state.charging,
    };
    for(const lamp of lamps){
      lamp.material.emissiveIntensity=enabled[lamp.role]?lamp.intensity:0;
      if(lamp.role==='ambientLight'&&output.ambientColor)lamp.material.emissive.set(output.ambientColor);
    }
    for(const light of spotlights){
      light.visible=output.lowBeam;
      light.intensity=output.highBeam?180:90;
      light.distance=output.highBeam?45:28;
      light.angle=output.highBeam ? .34 : .45;
    }
    for(const light of ambientLights){
      light.visible=Boolean(output.ambientColor);
      light.intensity=output.ambientColor?2.5:0;
      if(output.ambientColor)light.color.set(output.ambientColor);
    }
  }
  return {lamps,spotlights,ambientLights,update};
}
```

- [ ] **Step 4: Run the controller tests**

Run: `node --test tests/vehicle-lighting.test.js`

Expected: all three tests PASS with two spotlights and two ambient point lights in the full fixture.

- [ ] **Step 5: Commit the runtime lighting checkpoint**

```bash
git add src/vehicle-lighting.js tests/vehicle-lighting.test.js
git commit -m "feat: render vehicle lighting roles"
```

### Task 5: Connect Driving Telemetry to Vehicle Rendering

**Files:**
- Modify: `src/vehicle.js`
- Modify: `src/driving.js`
- Modify: `src/main.js`
- Modify: `tests/vehicle.test.js`
- Modify: `tests/model-asset.test.js`

- [ ] **Step 1: Write a failing createVehicle integration test**

Append to `tests/vehicle.test.js`:

```js
test('vehicle update applies lighting state and brake telemetry through its controller',()=>{
  const root=sceneFixture(),part=root.children[0];
  const material=new THREE.MeshStandardMaterial({emissive:'#f00',emissiveIntensity:4});
  const lamp=new THREE.Mesh(new THREE.BoxGeometry(.1,.1,.1),material);
  lamp.userData.lightRole='brakeLight';part.add(lamp);
  const vehicle=createVehicle(root),state=createState();
  vehicle.update(state,0,'all',{wheelAngle:0,braking:false,reversing:false});
  assert.equal(lamp.material.emissiveIntensity,0);
  vehicle.update(state,0,'all',{wheelAngle:0,braking:true,reversing:false});
  assert.equal(lamp.material.emissiveIntensity,4);
});
```

In the existing wheel test in `tests/model-asset.test.js`, replace:

```js
vehicle.update(state,0,'all',angle);
```

with:

```js
vehicle.update(state,0,'all',{wheelAngle:angle});
```

- [ ] **Step 2: Run integration tests against the old vehicle API**

Run: `node --test tests/vehicle.test.js tests/model-asset.test.js`

Expected: the new brake integration test FAILS because `createVehicle()` does not delegate lighting yet; the numeric wheel-angle call no longer represents the new API.

- [ ] **Step 3: Delegate vehicle lighting and consume a telemetry object**

Add to `src/vehicle.js`:

```js
import { createVehicleLighting } from './vehicle-lighting.js';
```

Remove `lights` from the first `createVehicle()` declaration so it becomes:

```js
const parts = [], effects = [], paintMaterials = [];
```

Delete the old broad `material.name.includes('LED')` collection line. After the initial `root.traverse(...)` block and before `let lastLayer`, add:

```js
const lighting=createVehicleLighting(root);
```

Change the update signature and wheel angle use to:

```js
function update(state, progress, layer='all', motion={}) {
  const wheelAngle=motion.wheelAngle||0;
```

Delete the old `for (const {material,intensity} of lights)...` line and replace it with:

```js
lighting.update(state,motion);
```

Return the controller for inspection/testing:

```js
return {root,parts,update,setColor,lighting};
```

- [ ] **Step 4: Return braking/reverse telemetry from driving and pass it in main**

Change the import in `src/driving.js` to:

```js
import { createDriveState, setDriving, stepDrive, WHEEL_RADIUS, isBraking } from './drive-state.js';
```

Replace the returned `update(dt)` method with:

```js
update(dt){
  if(!active)return {wheelAngle:0,braking:false,reversing:false};
  stepDrive(drive,dt);road.update(drive.distance);sync();
  return {wheelAngle:(drive.distance/WHEEL_RADIUS)%(Math.PI*2),braking:isBraking(drive),reversing:drive.speed<0};
},
```

In `src/main.js`, replace the single render expression `vehicle.update(state,visibleProgress,!focused&&exploring?layer:'all',driving.update(dt));` with:

```js
const motion=driving.update(dt);
vehicle.update(state,visibleProgress,!focused&&exploring?layer:'all',motion);
```

Keep `controls.update();renderer.render(scene,camera);` immediately after it.

- [ ] **Step 5: Run vehicle, driving, and asset tests**

Run: `node --test tests/vehicle.test.js tests/driving.test.js tests/model-asset.test.js tests/vehicle-lighting.test.js`

Expected: all tests PASS; wheel rotation still uses the same angle and brake telemetry reaches the new lamp controller.

- [ ] **Step 6: Commit the rendering integration checkpoint**

```bash
git add src/vehicle.js src/driving.js src/main.js tests/vehicle.test.js tests/model-asset.test.js
git commit -m "feat: connect driving telemetry to vehicle lights"
```

### Task 6: Accessible Lighting and Direction Controls

**Files:**
- Modify: `index.html`
- Modify: `src/main.js`
- Modify: `src/driving.js`
- Modify: `src/style.css`

- [ ] **Step 1: Add console lighting controls**

Add this block in `index.html` immediately after the window control and before the AC control:

```html
<div class="lighting-control">
  <div class="control-row"><span class="control-icon" data-icon="light"></span><div class="control-label">前大灯<span id="headlight-status">近光</span></div><button class="small-button" id="headlight-toggle" aria-label="切换前大灯">近光</button></div>
  <div class="control-row"><span class="control-icon" data-icon="tail"></span><div class="control-label">尾灯<span id="tail-status">已开启</span></div><button class="switch" id="tail-toggle" role="switch" aria-checked="true" aria-label="尾灯"></button></div>
  <div class="control-row ambient-row"><span class="control-icon" data-icon="ambient"></span><div class="control-label">车内氛围灯<span>固定颜色预设</span></div><div class="ambient-presets" role="group" aria-label="氛围灯颜色"><button data-ambient="off" aria-pressed="true">关闭</button><button data-ambient="warm" aria-pressed="false" aria-label="暖白">暖白</button><button data-ambient="ice" aria-pressed="false" aria-label="冰蓝">冰蓝</button><button data-ambient="purple" aria-pressed="false" aria-label="紫色">紫色</button></div></div>
</div>
```

- [ ] **Step 2: Add forward/reverse controls to the driving footer**

Replace the entire `.drive-speed-setting` element in `index.html` with:

```html
<div class="drive-speed-setting">
  <div class="drive-setting-heading"><label for="drive-range">目标速度 <output id="drive-target" for="drive-range">40</output><span>km/h</span></label><div class="drive-direction" role="group" aria-label="行驶方向"><button data-direction="1" aria-pressed="true">前进</button><button data-direction="-1" aria-pressed="false">倒车</button></div></div>
  <input id="drive-range" type="range" min="0" max="100" value="40" step="5" aria-label="目标速度"/><div class="range-labels"><span>0</span><span id="drive-speed-mid">50</span><span id="drive-speed-max">100 km/h</span></div>
</div>
```

Change `#drive-help` text to:

```html
<p id="drive-help">倒车限速 20 km/h · 停稳后可切换方向 · 退出后停驶 · Esc 返回</p>
```

- [ ] **Step 3: Wire lighting state to console buttons**

Add these entries to the `icons` object in `src/main.js`:

```js
light:'<path d="M9 3 4 7v10l5 4h3V3H9Zm5 4 5-2m-5 7h7m-7 5 5 2"/><path d="M4 7h5v10H4z"/>',
tail:'<path d="M4 5h16l-2 14H6L4 5Zm2 5h12M7 14h10"/>',
ambient:'<path d="M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1m0-12.8-2.1 2.1m-8.6 8.6-2.1 2.1"/><circle cx="12" cy="12" r="4"/>',
```

Add before `syncControls()`:

```js
const headlightLabels={off:'关闭',low:'近光',high:'远光'};
```

Add inside `syncControls()`:

```js
$('#headlight-status').textContent=headlightLabels[state.lighting.headlights];
$('#headlight-toggle').textContent=headlightLabels[state.lighting.headlights];
$('#headlight-toggle').setAttribute('aria-label',`前大灯，当前${headlightLabels[state.lighting.headlights]}，点击切换`);
$('#tail-toggle').setAttribute('aria-checked',String(state.lighting.tailLights));
$('#tail-status').textContent=state.lighting.tailLights?'已开启':'已关闭';
for(const button of document.querySelectorAll('[data-ambient]'))button.setAttribute('aria-pressed',String(button.dataset.ambient===state.lighting.ambient));
```

Add listeners before the reset listener:

```js
$('#headlight-toggle').addEventListener('click',()=>{
  const modes=['off','low','high'],index=modes.indexOf(state.lighting.headlights);
  state.lighting.headlights=modes[(index+1)%modes.length];syncControls();
});
$('#tail-toggle').addEventListener('click',()=>{state.lighting.tailLights=!state.lighting.tailLights;syncControls();});
for(const button of document.querySelectorAll('[data-ambient]'))button.addEventListener('click',()=>{state.lighting.ambient=button.dataset.ambient;syncControls();});
```

The existing reset listener already replaces state with `createState()`, so it restores low/tail/on, ambient/off without another state path.

- [ ] **Step 4: Wire direction, speed limits, and absolute readouts**

Change the `src/driving.js` import to include all used helpers:

```js
import { createDriveState, setDriving, stepDrive, WHEEL_RADIUS, isBraking, maxDriveSpeed, setDirection } from './drive-state.js';
```

Replace `sync()` with:

```js
function sync(){
  const speed=Math.abs(drive.speed),target=Math.abs(drive.targetSpeed),limit=maxDriveSpeed(drive);
  document.querySelector('#drive-speed').textContent=Math.round(speed);
  document.querySelector('#drive-distance').textContent=(Math.abs(drive.distance)/1000).toFixed(2);
  document.querySelector('#drive-target').textContent=target;
  const vehicle=getState(),blocked=vehicle.doorsOpen||vehicle.doorAngle>.01||vehicle.plugged;
  document.querySelector('#drive-status').textContent=isBraking(drive)?'正在减速':drive.running?(speed<target-.5?'正在加速':'行驶中'):speed>.1?'正在停车':blocked?'请先关门并拔枪':'已停稳';
  toggle.textContent=drive.running?'停车':'起步';toggle.setAttribute('aria-pressed',String(drive.running));
  range.max=limit;range.value=target;range.style.setProperty('--range-progress',`${target/limit*100}%`);
  document.querySelector('#drive-speed-mid').textContent=limit/2;
  document.querySelector('#drive-speed-max').textContent=`${limit} km/h`;
  for(const button of document.querySelectorAll('[data-direction]')){
    const selected=Number(button.dataset.direction)===drive.direction;
    button.setAttribute('aria-pressed',String(selected));button.disabled=drive.speed!==0;
  }
}
```

Replace the range listener and add direction listeners:

```js
range.addEventListener('input',()=>{drive.targetSpeed=Number(range.value);sync();});
for(const button of document.querySelectorAll('[data-direction]'))button.addEventListener('click',()=>{
  if(setDirection(drive,Number(button.dataset.direction)))sync();
  else toast('请先停车，待车辆停稳后再切换方向');
});
```

When `open()` recreates `drive=createDriveState()`, its existing `range.value=drive.targetSpeed` remains valid; `sync()` sets the forward max/labels and direction states. The visibility handler continues to force speed zero and calls `sync()`, re-enabling direction selection while hidden.

- [ ] **Step 5: Add compact responsive styles**

Append to `src/style.css`:

```css
.lighting-control{border-bottom:1px solid var(--line)}
.ambient-row{align-items:flex-start;padding:14px 0;gap:8px}
.ambient-presets{display:grid;grid-template-columns:repeat(2,1fr);gap:4px;min-width:112px}
.ambient-presets button,.drive-direction button{border:1px solid #ffffff1c;background:#ffffff05;color:#b8c5c4;border-radius:5px;padding:6px 8px;font-size:10px;min-height:30px}
.ambient-presets button[aria-pressed=true],.drive-direction button[aria-pressed=true]{background:var(--mint);border-color:var(--mint);color:#183625}
.drive-setting-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}
.drive-setting-heading label{flex:1}
.drive-direction{display:flex;gap:4px;flex-shrink:0}
.drive-direction button{padding:5px 10px;min-height:29px;white-space:nowrap}
@media(max-width:700px){
  .lab-section{height:1600px}
  .ambient-row{flex-wrap:wrap}
  .ambient-row .control-label{flex:1}
  .ambient-presets{grid-template-columns:repeat(4,1fr);flex-basis:100%;margin-left:37px}
  .ambient-presets button{min-height:36px}
  .drive-setting-heading{gap:8px}
  .drive-direction button{padding:5px 8px;font-size:9px}
}
```

- [ ] **Step 6: Run regression tests and a production build**

Run: `npm test && npm run build`

Expected: all tests PASS and Vite produces `dist/` without JavaScript or CSS errors.

- [ ] **Step 7: Commit the UI checkpoint**

```bash
git add index.html src/main.js src/driving.js src/style.css
git commit -m "feat: add vehicle lighting controls"
```

### Task 7: Documentation and End-to-End Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document the final interaction contract**

Replace the driving bullet in `README.md` with:

```markdown
- 点击「行驶演示」，再点「起步」；前进目标速度为 0–100 km/h，停稳后可切换倒车，倒车限速 20 km/h。支持平滑加减速、停车、重新起步以及前侧/侧面/后侧观察。轮胎、轮毂和路面随有符号行程一致换向，车速与行程按绝对值显示。
```

Insert this lighting bullet immediately before the driving bullet:

```markdown
- 前大灯可循环切换关闭、近光和远光；近光/远光带前方投射照明，尾灯独立开关。主动减速时制动灯自动高亮，实际倒车时白色倒车灯自动点亮。车内氛围灯支持关闭、暖白、冰蓝和紫色；充电指示灯只随充电状态变化。
```

Update the scope sentence about straight-line driving to state that the demo includes forward and low-speed reverse, still without steering, collisions, real energy use, or vehicle dynamics.

- [ ] **Step 2: Run the complete automated suite**

Run: `npm test`

Expected: all state, lighting, driving, vehicle, inspection, and production-model tests PASS.

- [ ] **Step 3: Run the production build**

Run: `npm run build`

Expected: Vite build succeeds with the regenerated GLB included in `dist/models/`.

- [ ] **Step 4: Verify model reproducibility and geometry checks**

Run:

```bash
python3 scripts/aura_surface.py
python3 scripts/vw_emblem.py
blender --background --python scripts/build_aura_t6.py
```

Expected: all scripts exit 0 and the final `AURA_EXPORT` reports 89 parts. Re-run `npm test` after regeneration to verify the checked-in asset contract remains true.

- [ ] **Step 5: Perform desktop visual and interaction checks**

Start or reuse `npm run dev`, open the printed Local URL, and verify:

1. Initial low beams and tail lights are visibly on; high beams add brighter projector emission and a longer ground beam; Off makes both completely dark.
2. Tail Off does not disable brake or reverse lamps.
3. Lowering target speed and pressing Stop illuminate brake lamps only while decelerating; they return to normal at constant speed/standstill.
4. Direction buttons are disabled while moving. At standstill, Reverse changes the slider maximum to 20, road/wheels reverse, and white reverse lamps illuminate only with negative signed speed.
5. Warm White `#FFD9A0`, Ice Blue `#8FD8FF`, and Purple `#B49AFF` affect only the cabin; Off removes cabin emission/fill.
6. Charging indication responds to charging, not headlight/tail/ambient controls.
7. Reset restores Low, Tail On, Ambient Off, and the next driving session starts Forward at the default target speed.
8. Inspection, exploded view, doors/windows, locks, bonnet, charging, and forward acceleration retain their existing behavior.

- [ ] **Step 6: Perform narrow-screen and keyboard checks**

At a 390×844 viewport, verify all three lighting rows and both driving direction buttons fit without horizontal overflow or covering the dashboard readouts. Navigate every new button by Tab, activate with Enter/Space, confirm visible focus, visible text state, `aria-pressed`/`aria-checked`, and disabled direction controls while moving. Repeat the lighting checks with `prefers-reduced-motion: reduce`.

- [ ] **Step 7: Review and commit the completed feature**

Run `git diff --check` and inspect `git status --short` to ensure only intended source, tests, documentation, and generated model files changed. Then, only when a commit is explicitly requested:

```bash
git add README.md docs/superpowers/specs/2026-10-25-vehicle-lighting-design.md docs/superpowers/plans/2026-10-25-vehicle-lighting.md src scripts tests index.html public/models models
git commit -m "feat: add complete vehicle lighting system"
```

Do not stage dependency directories, logs, screenshots, or unrelated workspace changes.
