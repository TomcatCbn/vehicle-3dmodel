# 决策 5：3D 车控与信号模型对接（现有 `state.js` 重构路径）

- **状态**：已定（架构方案层面）
- **决策日期**：2026-10-28
- **决策者**：用户
- **影响范围**：现有 `src/state.js`、`src/main.js`、`src/vehicle.js`、`src/drive-state.js`、`src/lighting-state.js`、`src/inspection.js`、`src/driving.js` 的重构路径

## 背景

决策 1-4 已定：Tauri 2.0 + Rust 后端，信号模型作为状态唯一来源（决策 3），MQTT/BLE 指令在信号模型层汇合（决策 4 D4.4）。本决策解决**现有 3D 渲染管线如何接入新架构**——这是保留现有 Three.js 投资的关键迁移路径。

现有 `state.js` 是纯 JS 对象，前端直接读写，`stepVehicle(state,dt)` 在帧循环里推进实际位置。重构后，**状态权威在后端 SignalModel**，前端 state 变为镜像。但迁移必须分阶段，不能一次性切断现有功能。

## 现有耦合地图（重构前必读）

### state.js 的字段与职责

| 字段 | 类型 | 语义 | 谁改 |
|------|------|------|------|
| `locked` | bool | 车锁逻辑状态 | UI 直改 (L48) |
| `doorsOpen` | bool | 车门目标状态 | UI 直改 (L49)；inspection 直改 (L97) |
| `doorAngle` | float 0-1 | 车门实际开度（平滑） | stepVehicle 推进 (L12) |
| `hoodOpen` | bool | 机盖目标 | UI 直改 (L107)；inspection 直改 (L96) |
| `hoodAngle` | float 0-1 | 机盖实际开度 | stepVehicle 推进 (L14) |
| `sunroofTarget` | float 0-1 | 天窗目标 | UI range input (L56) |
| `sunroofPosition` | float 0-1 | 天窗实际位置 | stepVehicle 推进 (L15-18) |
| `tailgateTarget` | float 0-1 | 尾门目标 | UI 直改 (L57-58) |
| `tailgatePosition` | float 0-1 | 尾门实际位置 | stepVehicle 推进 (L15-18) |
| `windowTarget` | float 0-1 | 车窗目标 | UI range input (L50) |
| `windowOpen` | float 0-1 | 车窗实际开度 | stepVehicle 推进 (L9-10) |
| `ac` | bool | 空调 | UI 直改 (L51) |
| `temperature` | int | 温度 | UI 直改 (L52) |
| `plugged` | bool | 充电枪连接 | UI 直改 (L53) |
| `charging` | bool | 充电中 | setCharging 校验后改 (L24-26) |
| `battery` | float 0-100 | 电量 | stepVehicle 推进 (L20) |
| `lighting` | object | 灯光状态 | UI 直改 (L60-65) |

**关键观察**：字段分两类——**逻辑状态**（locked/doorsOpen/hoodOpen/ac/plugged/charging/lighting，bool/枚举）和**实际位置**（doorAngle/hoodAngle/sunroofPosition/tailgatePosition/windowOpen/battery，float，由 stepVehicle 平滑推进）。这两类的迁移策略不同。

### 耦合点清单

| 文件 | 读 state | 写 state | 备注 |
|------|---------|---------|------|
| `main.js` L15 | `createState()` | `let state` 模块级可变单例 | 权威来源 |
| `main.js` syncControls (L18-47) | 全字段读 → 更新 DOM | 不写 | UI 同步 |
| `main.js` 事件处理器 (L48-65) | 校验读 | 直改字段 + syncControls | **绕过任何权威** |
| `main.js` frame (L148-170) | 读 | stepVehicle 推进实际位置 | 帧循环 |
| `vehicle.js` update (L79-129) | 读实际位置字段 | 不写 | 3D 驱动 |
| `drive-state.js` setDriving (L12-16) | 读 doorsOpen/doorAngle/hoodOpen/hoodAngle/tailgateTarget/tailgatePosition/plugged | 不写 | **联动校验**，检查实际位置 |
| `drive-state.js` setCharging (state.js L23-27) | 读 plugged/battery | 写 charging | 联动校验 |
| `inspection.js` onSelect (L96-98) | 读 | **直改** hoodOpen/hoodAngle/doorAngle/doorsOpen | 绕过联动，需路由 |
| `driving.js` sync (L43) | 读全字段 | 不写 | 行驶界面同步 |
| `lighting-state.js` deriveLighting | 读 lighting | 不写 | 纯派生 |

### 现有联动逻辑（AGENTS.md 约定，必须保留）

1. 解锁后才能开门（main.js L49 检查 `state.locked`）
2. 关门后才能上锁（main.js L48 检查 `state.doorsOpen`）
3. 插枪后才能充电（state.js setCharging L24 检查 `state.plugged`）
4. 车门/机盖/尾门未关拢或充电枪连接时禁止起步（drive-state.js setDriving L13 检查实际位置 + plugged）
5. 天窗可保持开启行驶（无检查）

**联动校验当前分散在三处**：main.js 事件处理器、state.js setCharging、drive-state.js setDriving。重构需**收敛到 SignalModel**。

## 核心架构问题：平滑推进逻辑放哪里

`stepVehicle(state,dt)` 把目标值平滑推进到实际位置（门/盖/天窗/尾门/窗/电量）。这是**帧率自适应的动画逻辑**。迁移到新架构时，它放哪里是关键决策。

### 选项 A：平滑留在前端镜像

后端 SignalModel 只持有**逻辑状态**（locked/doorsOpen/hoodOpen/sunroofTarget/...）和**目标值**，前端镜像持有**实际位置**，`stepVehicle` 留在帧循环继续推进实际位置。

- ✅ 迁移最小侵入——`stepVehicle` 不动，`vehicle.update` 不动
- ✅ 帧率自适应平滑保留（60fps 实际推进，视觉最流畅）
- ❌ **联动校验问题**：`setDriving` 检查 `doorAngle > .01`（实际位置），但实际位置只在前端，后端不知道门是否真关拢
- ❌ 后端 SignalModel 无法对"门正在关但还没关拢"做权威判断

### 选项 B：平滑移到后端 SignalModel（推荐）

后端 SignalModel 持有**逻辑状态 + 目标 + 实际位置**，运行自己的 tick（可配置速率，如 30-50Hz）用同一套 stepVehicle 公式推进实际位置。前端镜像接收快照，帧循环对快照做**轻量插值**（lerp）以应对网络抖动。

- ✅ 后端权威——联动校验用后端跟踪的实际位置，准确
- ✅ 前端只渲染——镜像纯快照，逻辑简单
- ✅ 联动逻辑全部收敛到 SignalModel
- ❌ stepVehicle 逻辑要用 Rust 重写（公式简单，迁移量小）
- ❌ 后端需跑 tick（30-50Hz，CPU 开销可忽略）
- ⚠️ 前端插值要处理"目标跳变"（如门从开到关，目标突变，插值会延迟）——需把"目标"也传给前端，前端用目标+实际双值插值

### 选项 C：混合——逻辑在后端，实际位置双写

后端持逻辑状态 + 目标，前端持实际位置（stepVehicle 推进），前端定期把实际位置回传后端。后端联动校验用回传的实际位置（有延迟）。

- ⚠️ 妥协方案，延迟可能让联动校验不准（门刚关拢，后端还不知道）
- ❌ 双写易不一致

### 决策：选 B

**理由**：
1. 联动校验必须用实际位置（现有 `setDriving` 就检查 `doorAngle > .01`），后端权威才能保证准确
2. stepVehicle 公式简单（线性逼近 + clamp），Rust 重写成本低
3. 前端插值比双写简单，且能处理网络抖动
4. MQTT/BLE 下发指令时，后端能立即知道当前实际状态做联动判断，无需等前端回传

**代价接受**：stepVehicle 用 Rust 重写一次（~30 行公式）；后端跑 tick（开销可忽略）；前端插值逻辑新增（~20 行）。

**前端插值策略**：前端镜像持有 `{target, actual}` 双值。后端快照含 `{target, actual}`。前端帧循环用 `actual = lerp(actual, snapshot.actual, dt * k)` 平滑跟随后端 actual（处理网络抖动），`target` 直接覆盖。这样：
- 后端 tick 推进 actual → 快照推前端 → 前端插值跟随 → vehicle.update 读前端 actual
- 目标跳变时（如开门指令），后端 target 立即变，actual 慢慢推进，前端看到 target 突变 + actual 渐进，行为与现状一致

## 架构方案

### 1. 后端 SignalModel 职责扩展

决策 3 的 SignalModel 扩展为持有**三层状态**：

```rust
pub struct VehicleState {
    // 逻辑状态（指令直接改，联动校验用）
    pub locked: bool,
    pub doors_open: bool,
    pub hood_open: bool,
    pub sunroof_target: f32,
    pub tailgate_target: f32,
    pub window_target: f32,
    pub ac: bool,
    pub temperature: i8,
    pub plugged: bool,
    pub charging: bool,
    pub lighting: LightingState,

    // 实际位置（tick 推进，3D 渲染用）
    pub door_angle: f32,
    pub hood_angle: f32,
    pub sunroof_position: f32,
    pub tailgate_position: f32,
    pub window_open: f32,
    pub battery: f32,
}

impl SignalModel {
    /// 帧推进——Rust 版 stepVehicle
    pub fn tick(&mut self, dt: f32) {
        // 与 src/state.js stepVehicle 相同的公式
        self.state.window_open = clamp(
            self.state.window_open + sign(self.state.window_target - self.state.window_open)
                * min(abs(target - actual), dt * 0.5), 0.0, 1.0);
        // door_angle / hood_angle / sunroof / tailgate 同理
        // charging/battery 同理
    }

    /// 应用指令（来自 MQTT/BLE/本地 UI），含联动校验
    pub fn apply_command(&mut self, cmd: Command) -> CommandResult {
        // 1. 能力校验（profile.capabilities）
        // 2. 联动校验（interlock 模块，收敛现有三处逻辑）
        // 3. 改逻辑状态/目标
        // 4. 返回结果（含状态变更事件）
    }

    /// 起步前置校验（收敛 setDriving 逻辑）
    pub fn can_start_driving(&self) -> Result<()> {
        if self.state.doors_open || self.state.door_angle > 0.01
            || self.state.hood_open || self.state.hood_angle > 0.01
            || self.state.tailgate_target > 0.001 || self.state.tailgate_position > 0.001
            || self.state.plugged {
            return Err(InterlockViolation);
        }
        Ok(())
    }
}
```

**联动校验模块**（`src-tauri/src/signal/interlock.rs`）收敛现有三处逻辑：

```rust
pub fn can_open_door(state: &VehicleState) -> Result<()> {
    if state.locked { return Err(DoorLocked); }
    Ok(())
}
pub fn can_lock(state: &VehicleState) -> Result<()> {
    if state.doors_open { return Err(DoorOpen); }
    Ok(())
}
pub fn can_charge(state: &VehicleState) -> Result<()> {
    if !state.plugged || state.battery >= 100.0 { return Err(NoPlugOrFull); }
    Ok(())
}
pub fn can_start_driving(state: &VehicleState) -> Result<()> { /* 如上 */ }
```

### 2. 前端镜像重构

`src/state.js` 保留但角色变化：从"状态唯一来源"变为"SignalModel 快照的本地镜像"。

```js
// src/state.js（重构后）
import { createLightingState } from './lighting-state.js';

export const clamp = (v, min = 0, max = 1) => Math.min(max, Math.max(min, v));

// 镜像——结构与后端 VehicleState 对齐
export function createMirror() {
  return {
    // 逻辑状态
    locked: true, doorsOpen: false, hoodOpen: false,
    sunroofTarget: 0, tailgateTarget: 0, windowTarget: 0,
    ac: false, temperature: 22, plugged: false, charging: false,
    lighting: createLightingState(),
    // 实际位置（前端插值跟随后端 actual）
    doorAngle: 0, hoodAngle: 0, sunroofPosition: 0,
    tailgatePosition: 0, windowOpen: 0, battery: 68,
  };
}

// 前端插值——跟随后端快照的 actual，处理网络抖动
export function followSnapshot(mirror, snapshot, dt) {
  const k = 12;  // 插值速率，大于后端 tick 速率保证跟得上
  for (const field of ['doorAngle','hoodAngle','sunroofPosition','tailgatePosition','windowOpen','battery']) {
    mirror[field] = THREE.MathUtils.damp(mirror[field], snapshot[field], k, dt);
  }
  // 逻辑状态直接覆盖
  Object.assign(mirror, pick(snapshot, ['locked','doorsOpen','hoodOpen','sunroofTarget',...]));
}

// 保留 explodeOffset（3D 拆解用，与信号模型无关）
export function explodeOffset(offset, progress, start = 0, end = 1) { /* 不变 */ }
```

**关键变化**：
- `createState` → `createMirror`（语义更准）
- `stepVehicle` 删除（后端 tick 接管）→ 替换为 `followSnapshot`（轻量插值）
- `setCharging` 删除（后端 interlock 接管）
- `clamp`、`explodeOffset` 保留（纯工具函数，3D 拆解用）

### 3. main.js 改造

```js
// main.js（重构后关键片段）
import { createMirror, followSnapshot, explodeOffset, clamp } from './state.js';
// 不再 import stepVehicle / setCharging

let mirror = createMirror();
let snapshot = createMirror();  // 后端快照缓存

// 后端状态变更事件 → 更新 snapshot
window.__TAURI__.event.listen('signal://state-changed', (event) => {
  Object.assign(snapshot, event.payload);
});

// 事件处理器：不再直改 mirror，改发 Tauri command
$('#lock-toggle').addEventListener('click', () => {
  invoke('send_vehicle_command', { cmd: { type: 'toggle_lock' } });
  // 不再 syncControls——由 state-changed 事件驱动
});
$('#door-toggle').addEventListener('click', () => {
  invoke('send_vehicle_command', { cmd: { type: 'toggle_door' } });
});

// frame 循环
function frame() {
  const dt = Math.min(clock.getDelta(), .05);
  followSnapshot(mirror, snapshot, dt);  // 替代 stepVehicle
  progress = reduced ? scrollProgress : THREE.MathUtils.damp(progress, scrollProgress, 5, dt);
  // ... vehicle.update(mirror, ...) —— vehicle.js 不变，仍读 mirror 字段
  vehicle.update(mirror, visibleProgress, layer, motion);
  // syncControls 改为读 mirror（mirror 现在是后端快照的镜像）
  if (clock.elapsedTime - lastUi > .1) { syncControls(mirror); ... }
  requestAnimationFrame(frame);
}
```

**关键变化**：
- `state` → `mirror`（语义）+ `snapshot`（后端快照）
- 事件处理器直改字段 → `invoke('send_vehicle_command', ...)` 发后端
- `stepVehicle(state, dt)` → `followSnapshot(mirror, snapshot, dt)`
- `syncControls()` 读 `mirror`（字段名不变，vehicle.js 无需改）

### 4. vehicle.js 不改

`vehicle.update(state, progress, layer, motion)` 读的字段（`hoodAngle`/`tailgatePosition`/`sunroofPosition`/`doorAngle`/`windowOpen`/`plugged`/`ac`）在镜像里同名同结构。**vehicle.js 零改动**——这是保留 3D 投资的关键。

### 5. inspection.js / driving.js 路由改造

这两个文件目前直接改 state（inspection onSelect L96-98）。改造为发命令：

```js
// inspection.js onSelect 改造
onSelect(id) {
  if (id === 'hood') invoke('send_vehicle_command', { cmd: { type: 'open_hood' } });
  if (id === 'handle') invoke('send_vehicle_command', { cmd: { type: 'toggle_door' } });
  // 不再直改 state——等 state-changed 事件回来更新 mirror
  // vehicle.update 由 frame 循环读 mirror 驱动
}
```

`driving.js` 的 `setDriving` 调用改为发命令，后端 `can_start_driving` 校验：

```js
// driving.js startStop 改造
toggle.addEventListener('click', () => {
  invoke('send_vehicle_command', { cmd: { type: 'toggle_driving' } })
    .catch(err => toast('请先关好车门、机盖和尾门，并拔出充电枪，再起步'));
});
```

`drive-state.js` 的 `setDriving`/`setDirection` 逻辑迁移到后端 SignalModel，前端 `driving.js` 只负责行驶界面 UI 与相机，不再做联动校验。

### 6. drive-state.js 拆分

`drive-state.js` 现有职责混合：行驶计算（speed/distance）+ 起步联动校验。拆分：

- **行驶计算**（speed/distance/wheelAngle）保留前端——这是 3D 演示动画，与信号模型无关，刷新复位可接受
- **起步联动校验**（`setDriving` 检查车门/机盖/尾门/充电枪）迁移到后端 `SignalModel.can_start_driving`

```js
// drive-state.js（重构后，保留行驶计算，删除联动校验）
export function createDriveState() {
  return { running: false, targetSpeed: 40, speed: 0, distance: 0, direction: 1 };
}
// setDriving 删除——起步由后端校验，前端只发 toggle_driving 命令
// 行驶推进 stepDrive 保留（3D 动画）
```

### 7. lighting-state.js 不改

`lighting-state.js` 是纯派生函数（`deriveLighting`），输入 lighting 状态 + motion，输出渲染用的灯组状态。后端 SignalModel 持有 lighting 逻辑状态，前端镜像持有同样的 lighting 字段，`deriveLighting` 在前端继续运行（纯函数，无副作用）。**零改动**。

## 文件级改动汇总

| 文件 | 改动 | 幅度 |
|------|------|------|
| `src/state.js` | `createState`→`createMirror`；删 `stepVehicle`/`setCharging`；加 `followSnapshot`；保留 `clamp`/`explodeOffset` | 中 |
| `src/main.js` | `state`→`mirror`+`snapshot`；事件处理器改 `invoke`；frame 用 `followSnapshot`；监听 `signal://state-changed` | 中 |
| `src/vehicle.js` | **不改** | 0 |
| `src/vehicle-lighting.js` | **不改** | 0 |
| `src/lighting-state.js` | **不改** | 0 |
| `src/inspection.js` | onSelect 改 `invoke` | 小 |
| `src/driving.js` | `setDriving` 调用改 `invoke`；sync 读 mirror | 小 |
| `src/drive-state.js` | 删 `setDriving`；保留 `createDriveState`/`stepDrive`/`setDirection` | 小 |
| `src/studio.js` | **不改** | 0 |

**3D 渲染相关文件零改动**（vehicle/vehicle-lighting/lighting-state/studio）——这是保留投资的核心。

## 分阶段迁移（4 阶段，每阶段可验证）

### 阶段 M1：后端 SignalModel 骨架 + 本地回环（不接 MQTT/BLE）

**目标**：后端能跑 SignalModel，前端通过 Tauri command 发指令、收事件，3D 仍能动。无 MQTT/BLE。

**步骤**：
1. Rust 后端建 `SignalModel` 结构（VehicleState 三层），tick 用 Rust 重写 stepVehicle 公式
2. Rust 后端建 `interlock` 模块，收敛现有三处联动校验
3. 暴露 Tauri command：`send_vehicle_command(cmd)` → SignalModel.apply_command
4. 发 Tauri event：`signal://state-changed` 携带快照
5. 前端 `state.js` 改 `createMirror`/`followSnapshot`
6. 前端 `main.js` 事件处理器改 `invoke`，frame 用 `followSnapshot`
7. `vehicle.js` 不动——验证 3D 仍正常动

**验证**：点解锁→开门→天窗→尾门，3D 动画与重构前一致；尝试锁车时门开→后端拒绝→toast 提示；起步时门开→后端拒绝。

### 阶段 M2：inspection/driving 路由改造

**目标**：细节查看与行驶演示的直改 state 全部改为发命令。

**步骤**：
1. inspection.js onSelect 改 `invoke`
2. driving.js `setDriving` 调用改 `invoke`，后端 `can_start_driving` 校验
3. drive-state.js 删 `setDriving`，保留行驶计算

**验证**：细节查看打开机盖→3D 动；行驶起步被门开拦截→toast；行驶中车控仍可操作。

### 阶段 M3：接入 MQTT 适配器

**目标**：后台下发指令能更新 SignalModel，3D 响应。

**步骤**：
1. Rust 后端 MQTT 模块接真实后台（决策 2）
2. MQTT 下行指令 → SignalModel.apply_command（与本地 UI 同路径）
3. SignalModel 状态变更 → MQTT 上行发布

**验证**：手机 App（或 MQTT 工具）发开门指令→3D 车门动；模拟器操作→手机 App 看到状态变化。

### 阶段 M4：接入 BLE 适配器

**目标**：手机 BLE 鉴权后 RKE 指令能更新 SignalModel。

**步骤**：
1. Rust 后端 BLE 协议核心层（决策 4）
2. RKE 命令 → SignalModel.apply_command（与本地 UI/MQTT 同路径）
3. 状态变更 → BLE 通知手机

**验证**：mock 适配器模拟手机鉴权→RKE 开门→3D 动；真实 btleplug（macOS）真手机连。

## 关键设计决策

### D5.1 平滑推进逻辑移到后端 SignalModel（选 B 不选 A）

**选择**：`stepVehicle` 用 Rust 重写在 SignalModel.tick，前端只做轻量插值。
**理由**：联动校验需实际位置（`setDriving` 检查 `doorAngle > .01`），后端权威才能保证准确；MQTT/BLE 下发指令时后端能立即判断当前实际状态。
**代价**：stepVehicle 公式 Rust 重写（~30 行）；后端跑 tick（开销可忽略）；前端插值逻辑新增。
**缓解**：公式简单直接翻译；tick 速率 30-50Hz 足够；前端插值用 THREE.MathUtils.damp 一行搞定。

### D5.2 前端镜像用"目标+实际"双值插值

**选择**：前端镜像持 `{target, actual}`，后端快照含两者，前端 `followSnapshot` 用 damp 跟随 actual，target 直接覆盖。
**理由**：目标跳变时（开门指令）后端 target 立即变、actual 渐进推进，前端看到同样行为，与现状一致；damp 跟随 actual 处理网络抖动。
**代价**：镜像字段多一倍（target + actual）。
**缓解**：现有 state 本来就有 target/actual 双字段（sunroofTarget/sunroofPosition 等），结构天然对齐。

### D5.3 事件处理器不再直改 state，改发 Tauri command

**选择**：所有 UI 操作（锁/门/窗/天窗/尾门/机盖/空调/温度/充电枪/充电/灯光/起步）改为 `invoke('send_vehicle_command', {cmd})`，由后端 SignalModel 处理后回事件更新镜像。
**理由**：状态唯一来源在后端；联动校验集中；MQTT/BLE 下发指令与本地 UI 走同一路径。
**代价**：UI 响应多一次往返延迟（Tauri IPC ~1ms，可忽略）。
**缓解**：Tauri command 同步执行无 IO，延迟可忽略；乐观更新可选（先改镜像再等后端确认）但建议先不做，保持简单。

### D5.4 联动校验收敛到后端 interlock 模块

**选择**：现有分散在 main.js 事件处理器、state.js setCharging、drive-state.js setDriving 的联动校验，全部迁移到 `src-tauri/src/signal/interlock.rs`。
**理由**：单一权威；MQTT/BLE 下发指令也走同一校验；避免前端漏检。
**代价**：前端不能再"快速失败"（如点开门时前端不立即知道锁着）。
**缓解**：后端 apply_command 同步返回 Result，前端 invoke 拿到错误立即 toast；延迟可忽略。

### D5.5 行驶计算保留前端，起步校验移后端

**选择**：`drive-state.js` 的行驶推进逻辑（speed/distance/wheelAngle 动画）保留前端，`setDriving` 联动校验移后端。
**理由**：行驶是 3D 演示动画（刷新复位可接受），与信号模型无关；起步联动校验是车辆安全约束，应在后端权威。
**代价**：行驶状态不在 SignalModel（后端不知道车在跑）。
**缓解**：如后续需 MQTT 上报行驶状态，再扩展 SignalModel 加 driving 字段；当前演示场景不需要。

### D5.6 3D 渲染相关文件零改动

**选择**：`vehicle.js`/`vehicle-lighting.js`/`lighting-state.js`/`studio.js` 不改。
**理由**：这些文件读 state 字段（现 mirror）同名同结构，接口不变；保留 3D 投资的核心就是不碰渲染层。
**代价**：无。
**缓解**：无。

### D5.7 迁移分 4 阶段，每阶段可独立验证

**选择**：M1（后端骨架+本地回环）→ M2（inspection/driving 路由）→ M3（MQTT）→ M4（BLE），每阶段独立验证不破坏现有功能。
**理由**：降低风险；每阶段有明确验证点；MQTT/BLE 不阻塞前端重构。
**代价**：阶段间有过渡状态（如 M1 完成后本地 UI 走后端但无 MQTT）。
**缓解**：过渡状态功能完整（本地车控全可用），只是协议未接。

## 命令枚举（前端→后端）

为统一前端 UI、MQTT 下行、BLE RKE 三条指令路径，定义命令枚举：

```rust
// src-tauri/src/signal/command.rs
pub enum VehicleCommand {
    ToggleLock,
    ToggleDoor,
    SetWindow { target: f32 },
    SetSunroof { target: f32 },
    Tailgate { action: TailgateAction },  // Open/Close/Stop
    ToggleHood,
    ToggleAc,
    SetTemperature { value: i8 },
    TogglePlug,
    ToggleCharging,
    SetHeadlight { mode: HeadlightMode },  // Off/Low/High
    ToggleTailLight,
    SetAmbient { color: AmbientColor },    // Off/Warm/Ice/Purple
    ToggleDriving,
    // ... 其他能力按 profile.capabilities 扩展
}
```

前端 `invoke('send_vehicle_command', { cmd })` 传此枚举；MQTT 解码后转此枚举；BLE RKE 解码后转此枚举。**三路汇合到 SignalModel.apply_command**。

## 模块边界（Rust 后端，决策 3 基础上扩展）

```
src-tauri/src/
├── signal/
│   ├── mod.rs
│   ├── model.rs          # SignalModel（含 tick、apply_command、snapshot）
│   ├── state.rs          # VehicleState 三层（逻辑+目标+实际）
│   ├── command.rs        # VehicleCommand 枚举
│   ├── interlock.rs      # 联动校验（收敛现有三处逻辑）
│   └── tick.rs           # tick 循环（30-50Hz 推进实际位置）
├── adapter/
│   ├── threed.rs         # 状态→Tauri event 快照（前端镜像源）
│   ├── mqtt.rs           # 状态→MQTT 报文（决策 2）
│   └── ble.rs            # 状态→BLE 通知（决策 4）
└── commands/             # Tauri commands 入口
    └── vehicle.rs        # send_vehicle_command 等
```

## 待后续决策

- 决策 6：OneSDK 私有协议报文格式对齐（MQTT 报文编解码、BLE RKE 命令编码）
- 决策 7：车型 Profile 完整字段定义与 schema（含 3D 部件映射表完整版）
- 决策 8：BLE 鉴权具体协议字段对齐（接入知识库 OneSDK BLE fact 后细化）

## 决策依据证据

本决策基于以下事实约束：

1. 现有 `src/state.js` 结构：逻辑状态字段（locked/doorsOpen/hoodOpen/ac/plugged/charging/lighting）与实际位置字段（doorAngle/hoodAngle/sunroofPosition/tailgatePosition/windowOpen/battery）分离，target/actual 双字段模式已存在
2. 现有 `stepVehicle` 公式（src/state.js L7-22）：线性逼近 + clamp，公式简单可 Rust 重写
3. 现有联动校验分散点：main.js L48（锁车检查门开）、main.js L49（开门检查锁）、state.js L24（充电检查插枪）、drive-state.js L13（起步检查门/盖/尾门/充电枪实际位置）
4. `vehicle.update`（src/vehicle.js L79-129）读字段清单：hoodAngle/tailgatePosition/sunroofPosition/doorAngle/windowOpen/plugged/ac——字段名稳定，接口不变则零改动
5. inspection.js onSelect（src/main.js L96-98）直改 state：`state.hoodOpen=true; state.hoodAngle=1` 绕过联动，需路由到命令
6. AGENTS.md 约定：状态集中在 state.js；视图复用同一模型/canvas/renderer/动画循环；保留现有联动逻辑

代码层验证：上述行号与字段名均来自实际读取的 `src/state.js`/`src/main.js`/`src/vehicle.js`/`src/drive-state.js`/`src/inspection.js`/`src/driving.js` 源码 ✓。
