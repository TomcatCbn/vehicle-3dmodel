# Vehicle Lighting and Reverse Driving Design

Date: 2026-10-25
Status: Approved for specification review

## Goal

Add a complete, user-facing lighting system to the existing 3D vehicle simulator. The system includes low beams, high beams, tail lights, brake lights, reverse lights, interior ambient lighting, projected headlight illumination, and driving-state integration. Add a low-speed reverse demonstration so reverse lights have a real vehicle state to follow.

## Scope

Included:

- Independent low-beam, high-beam, tail-light, brake-light, reverse-light, and ambient-light geometry and materials.
- Explicit model metadata for identifying each lighting role.
- Manual headlight, tail-light, and ambient-light controls.
- Automatic brake-light and reverse-light behavior.
- Forward/reverse driving direction with reverse limited to 20 km/h.
- Desktop, narrow-screen, and keyboard-accessible controls.
- Unit, model-asset, and regression tests.

Excluded:

- Automatic headlights based on scene brightness.
- Fog lights, turn signals, hazard lights, and adaptive steering headlights.
- Custom ambient-light colors or brightness sliders.
- New post-processing, bloom, shadow-casting vehicle lights, or a vehicle dynamics simulation.
- MQTT/BLE integration or persistent settings.

## Chosen Architecture

Use a model/runtime split rather than hard-coding lamp positions in the browser or simulating everything with emissive materials.

### Model layer

Extend `scripts/build_aura_t6.py` and regenerate `public/models/aura-t6.glb`.

Each required lamp role has independent geometry and material slots, plus explicit `lightRole` metadata. Required roles are:

- `lowBeam`: left and right low-beam projectors and light-guide materials.
- `highBeam`: left and right additional high-beam projectors and their light-anchor metadata.
- `tailLight`: normal rear position lights.
- `brakeLight`: rear brake segments and the high-mounted stop lamp.
- `reverseLight`: white rear reversing lamps.
- `ambientLight`: interior light strips.

The existing charging indicator must not belong to any of these roles. Its appearance remains controlled only by charging state. Existing broad material-name matching must not be used for the new lighting behavior.

Headlight anchor nodes define the positions and forward directions of runtime spotlights. Anchors remain under the corresponding model hierarchy so transforms continue to follow the vehicle and exploded parts.

### Runtime lighting module

Add a focused lighting controller instead of placing the complete feature in `vehicle.js`. Its responsibilities are:

1. Index lamp meshes, original emissive values, materials, and headlight anchors after GLB loading.
2. Derive effective lamp output from manual lighting state and driving state.
3. Apply emissive color/intensity to each lamp role.
4. Update headlight spotlights and interior local lights.
5. Skip an absent individual lamp mesh safely without breaking the rest of the scene.

`vehicle.js` delegates lighting updates to this controller while retaining ownership of vehicle construction and per-frame updates. Existing vehicle materials not associated with a lighting role remain untouched.

Use exactly two forward spotlights for low/high beams. High beam includes low beam and adds longer-range, higher-intensity illumination. Vehicle spotlights and interior local lights do not cast shadows. Do not add a post-processing pipeline.

### UI and state

The vehicle console gains:

- A headlight control cycling through Off, Low, and High.
- An independent tail-light on/off control.
- Ambient-light presets: Off, Warm White, Ice Blue, and Purple.
- A forward/reverse direction control in the driving panel.

The UI exposes current values with visible text and appropriate accessible state, not color alone. Controls fit the existing 390×844 layout and remain keyboard-operable.

Default state after initial load or reset:

- Headlights: Low.
- Tail lights: On.
- Ambient lights: Off.
- Driving direction: Forward.

The existing single unused `lights` boolean is replaced or migrated to explicit lighting state; no parallel sources of truth are introduced.

## Behavior

### Headlights and tail lights

- Off turns all low- and high-beam emissive elements and forward spotlights off completely.
- Low enables low-beam elements and the standard forward spotlight beam.
- High keeps low beams enabled and adds the high-beam elements and stronger, longer-range spotlights.
- Tail lights are manually independent of headlights.
- Turning off normal tail lights does not suppress brake lights or reverse lights.

### Brake lights

Brake lights illuminate at full brake intensity while the vehicle is moving and the driver actively requests deceleration, including the Stop action. When the request returns to maintaining or increasing speed, normal tail-light behavior resumes. A stationary vehicle does not keep brake lights illuminated merely because its speed is zero.

Brake-light output takes priority over normal tail-light output on any shared rear assembly; separate reverse-light output is unaffected.

### Reverse driving and reverse lights

- Direction can change only when `drive.speed === 0` km/h.
- The direction control is disabled or rejected while moving; it must not cause an instantaneous transition from forward motion to reverse motion.
- Forward retains the existing 0–100 km/h target-speed range.
- Reverse uses a 0–20 km/h target-speed range and the existing smooth acceleration/deceleration model.
- Signed travel and wheel rotation agree with the selected direction; the displayed speed is the absolute, nonnegative speed in km/h.
- Reverse lights turn on only when the vehicle is actually moving backward, not merely when Reverse is selected at standstill.
- Leaving driving mode, resetting, or switching to a background tab preserves existing safety behavior: stop driving and restore the appropriate vehicle state.

### Ambient and charging lights

- Ambient presets apply fixed colors and a restrained fixed intensity to interior strips and local fill lighting: Warm White `#FFD9A0`, Ice Blue `#8FD8FF`, and Purple `#B49AFF`.
- Off sets ambient emissive output and local fill lighting to zero.
- Charging indication is independent of headlight, tail-light, and ambient-light controls.

## Failure Handling and Performance

- Missing individual lamp meshes are ignored at runtime so unrelated vehicle controls continue working.
- Model-asset tests treat every required production role and both headlight anchors as mandatory, preventing an incomplete GLB from passing validation.
- Existing whole-model load/error handling remains in place.
- No per-frame geometry creation or material re-cloning is introduced.
- Vehicle-mounted lights do not cast shadows; there are two headlight spotlights and two low-intensity interior point lights.

## Testing and Acceptance

### Automated tests

Using the existing Node test runner and Three.js fixture style:

- Verify default lighting and driving-direction state and reset behavior.
- Verify Off/Low/High headlight output, including low beams remaining active in High.
- Verify independent tail-light output and complete off-state emissive intensity.
- Verify brake lights override normal tail state only during active deceleration and do not latch at standstill.
- Verify reverse lights require actual backward travel.
- Verify direction changes are rejected while moving and allowed while stopped.
- Verify reverse target speed is limited to 20 km/h and signed distance/wheel motion reverses consistently.
- Verify every ambient preset and Off behavior.
- Verify charging indication is unchanged by lighting controls.
- Verify runtime restoration of original material state and safe handling of a missing individual lamp mesh.
- Verify the production GLB contains all required roles, independent materials, and both headlight anchors.

### Verification

Run `npm test` and `npm run build` after implementation. Regenerate and validate the GLB with the documented Blender workflow. Inspect the running scene for every manual lighting mode, braking, reverse driving, charging independence, reset, and exploded-view behavior. Check desktop and 390×844 layouts and keyboard operation.

The feature is accepted when all automated checks pass and the visible behavior matches these rules without regressing existing lock, door, window, charging, inspection, or forward-driving controls.
