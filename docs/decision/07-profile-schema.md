# 决策 7：车型 Profile 完整字段定义与 Schema

- **状态**：已定（架构方案层面；能力编号待决策 6 对齐 OneSDK）
- **决策日期**：2026-10-28
- **决策者**：用户
- **影响范围**：Profile 格式、AURA T6 实例、3D 部件映射、vehicle.js 改造（更新决策 5 D5.6）

## 背景

决策 3 定了 Profile 三层抽象骨架（静态描述 → 运行时实例 → 适配器），决策 5 定了 3D 对接迁移路径。本决策给出 Profile 的**完整字段定义**与第一个实例 AURA T6，并建立信号→GLB 部件的完整映射表。

用户决策：门控用**独立 4 门**（非同步），profile schema 与实例都支持独立门。这修改了决策 5 的 D5.6（vehicle.js 零改动）——vehicle.js 需改为读 `state.doors[id].angle` 而非 `state.doorAngle`。本决策记录此更新及改造方案。

## 现有 GLB 部件清单（99 部件，来源：build_aura_t6.py）

按 motion 类型分组：

### motion=door（4 个，独立门）
| GLB 部件名 | label | 信号 id |
|------------|-------|---------|
| `door_l_0` | 左前门 | `door.fl` |
| `door_r_0` | 右前门 | `door.fr` |
| `door_l_1` | 左后门 | `door.rl` |
| `door_r_1` | 右后门 | `door.rr` |

### motion=window（4 个，独立窗）
| GLB 部件名 | label | 信号 id |
|------------|-------|---------|
| `window_l_0` | 左前窗 | `window.fl` |
| `window_r_0` | 右前窗 | `window.fr` |
| `window_l_1` | 左后窗 | `window.rl` |
| `window_r_1` | 右后窗 | `window.rr` |

### motion=hood / hood_strut
| GLB 部件名 | label | motion | 信号 id |
|------------|-------|--------|---------|
| `hood` | 前舱盖 | hood | `hood` |
| `bonnet_strut_l` | 左机盖撑杆 | hood_strut | `hood`（跟随） |
| `bonnet_strut_r` | 右机盖撑杆 | hood_strut | `hood`（跟随） |

### motion=sunroof
| GLB 部件名 | label | 信号 id |
|------------|-------|---------|
| `sunroof` | 电动天窗 | `sunroof` |

### motion=tailgate / tailgate_strut（共用尾门铰点）
| GLB 部件名 | label | motion | 信号 id |
|------------|-------|--------|---------|
| `tailgate` | 尾门 | tailgate | `tailgate` |
| `rear_spoiler` | 后扰流板 | tailgate | `tailgate`（跟随） |
| `rear_glass` | 后挡风玻璃 | tailgate | `tailgate`（跟随） |
| `tail_lights` | 后贯穿尾灯 | tailgate | `tailgate`（跟随） |
| `tailgate_strut_l` | 左尾门电动撑杆 | tailgate_strut | `tailgate`（跟随） |
| `tailgate_strut_r` | 右尾门电动撑杆 | tailgate_strut | `tailgate`（跟随） |

### motion=cable / airflow（效果部件）
| GLB 部件名 | label | 信号映射 |
|------------|-------|----------|
| `charge_cable` | 充电枪 | `plugged`（可视） |
| `airflow` | 空调气流 | `ac`（可视） |

### 无 motion（静态部件，仅拆解动画用）
底盘框架/电池包/电池模组/前后电驱/座舱地板/侧门槛/翼子板(4)/侧顶梁(2)/后侧固定玻璃(2)/侧B柱(2)/后侧围(2)/后视镜(2)/前侧饰条(2)/轮胎(4)/轮毂(4)/制动盘(4)/前保险杠/前舱检修盖板/前贯穿灯带/纵向方灯(2)/前挡风玻璃/全景玻璃车顶/行李架(2)/后保险杠/外侧尾灯(2)/后备箱门框/后备箱内衬/仪表台与中控/方向盘/座椅(4)/中央扶手/车顶激光雷达

## Profile 完整字段定义

### 段 1：[vehicle] 车辆身份

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `profile_id` | string | 是 | Profile 唯一标识（如 `aura-t6`） |
| `profile_version` | string | 是 | Profile 版本（语义化版本） |
| `brand` | string | 是 | 品牌 |
| `model` | string | 是 | 车型名称 |
| `vin_pattern` | string | 是 | VIN 模式（用于车管注册，可含通配符） |
| `model_3d` | string | 是 | 3D 资产路径（相对 public/） |

### 段 2：[hardware] 硬件清单

#### [hardware.doors]

| 字段 | 类型 | 说明 |
|------|------|------|
| `count` | int | 门数量 |
| `positions` | string[] | 门位置 id 列表（如 `["fl","fr","rl","rr"]`） |
| `type` | string | 门类型：`hinged`/`sliding`/`suicide` |
| `control` | string | 控制模式：`independent`（独立）/ `sync`（同步） |

AURA T6 用 `independent`（用户决策）。`sync` 模式下所有门共享一个状态，前端镜像保持单值兼容旧实现。

#### [hardware.windows]

| 字段 | 类型 | 说明 |
|------|------|------|
| `count` | int | 窗数量 |
| `positions` | string[] | 窗位置 id 列表（与门对齐） |
| `control` | string | `independent`/`sync` |

#### [hardware.sunroof]

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | `none`/`panoramic-sliding`/`tilt-only`/`fixed` |
| `segments` | int | 分段数（全景滑动 = 2：前活动 + 后固定） |

#### [hardware.tailgate]

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | `none`/`hinged`/`power-lift` |
| `linked_parts` | string[] | 共用铰点的联动部件 GLB 名（如后扰流板/后挡风玻璃/后贯穿尾灯/撑杆） |

#### [hardware.hood]

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | `none`/`hinged` |

#### [hardware.lights]

| 字段 | 类型 | 说明 |
|------|------|------|
| `headlights` | string | `none`/`single-led`/`split-led` |
| `tail_lights` | bool | 有无尾灯 |
| `ambient_interior` | bool | 有无车内氛围灯 |
| `brake_auto` | bool | 是否自动刹车灯 |
| `reverse_auto` | bool | 是否自动倒车灯 |

#### [hardware.charging]

| 字段 | 类型 | 说明 |
|------|------|------|
| `port` | string | `none`/`ccs`/`type2`/`gbt` |
| `ac` | bool | 支持 AC |
| `dc` | bool | 支持 DC |

#### [hardware.driving]

| 字段 | 类型 | 说明 |
|------|------|------|
| `max_speed_kmh` | int | 演示限速 |
| `reverse_max_kmh` | int | 倒车限速 |
| `wheels` | int | 车轮数 |

### 段 3：[capabilities] 软件能力

#### [capabilities.supported]

字符串数组，对齐 OneSDK Function 层接口编号（待决策 6 对齐）。当前用占位前缀 + 功能描述：

| 占位编号 | 功能 | 对应现有 state 字段 |
|----------|------|---------------------|
| `EXT-10001` | 车门控制 | doors.*.open |
| `EXT-10002` | 车窗控制 | windows.*.target |
| `EXT-10003` | 天窗控制 | sunroof.target |
| `EXT-10004` | 尾门控制 | tailgate.target |
| `EXT-10005` | 灯光控制 | lighting.* |
| `EXT-10006` | 空调控制 | ac / temperature |
| `EXT-10007` | 充电控制 | charging |
| `EXT-10008` | 车锁控制 | locked |
| `EXT-10009` | 机盖控制 | hood.open |
| `ENERGY-10001` | 电量查询 | battery |
| `DRIVE-10001` | 行驶控制 | driving（前端动画） |

> 编号待决策 6 接入知识库后对齐 OneSDK 真实接口空间。当前为推导占位。

#### [capabilities.interlock]

联动约束（AGENTS.md 约定，必须保留）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `unlock_before_open_door` | bool | 解锁后才能开门 |
| `close_door_before_lock` | bool | 关门后才能上锁 |
| `plug_before_charge` | bool | 插枪后才能充电 |
| `no_start_when_door_open` | bool | 门未关拢禁起步 |
| `no_start_when_hood_open` | bool | 机盖未关拢禁起步 |
| `no_start_when_tailgate_open` | bool | 尾门未关拢禁起步 |
| `no_start_when_charging` | bool | 充电中禁起步 |
| `sunroof_open_while_driving` | bool | 天窗可保持开启行驶 |

### 段 4：[protocol] 协议版本

| 字段 | 类型 | 说明 |
|------|------|------|
| `ble_version` | string | `v1`/`v2`（对齐 OneSDK BLE 协议） |
| `mqtt_auth` | string | `xp`/`cea`（对齐 OneSDK 鉴权） |
| `command_channel` | string | `ble`/`mqtt`/`mixed`（对齐通道选择） |

### 段 5：[ble] 蓝牙配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `service_uuid` | string | GATT service UUID |
| `advertised_name` | string | 广播名称 |
| `advertise_interval_ms` | int | 广播间隔 |
| `auth_char_uuid` | string | 鉴权 characteristic UUID |
| `rke_char_uuid` | string | RKE characteristic UUID |

> UUID 待决策 8 接入知识库后对齐 OneSDK BLE fact。当前用占位。

### 段 6：[mapping] 3D 部件映射

#### [mapping.parts]

信号 id → GLB 部件名映射。Signal Adapter（3D）读此表把信号状态映射到 GLB 部件动作。

```toml
[mapping.parts]
# 门
"door.fl" = "door_l_0"
"door.fr" = "door_r_0"
"door.rl" = "door_l_1"
"door.rr" = "door_r_1"
# 窗
"window.fl" = "window_l_0"
"window.fr" = "window_r_0"
"window.rl" = "window_l_1"
"window.rr" = "window_r_1"
# 机盖（含撑杆跟随）
"hood" = "hood"
"hood.strut.l" = "bonnet_strut_l"
"hood.strut.r" = "bonnet_strut_r"
# 天窗
"sunroof" = "sunroof"
# 尾门（含联动部件）
"tailgate" = "tailgate"
"tailgate.spoiler" = "rear_spoiler"
"tailgate.glass" = "rear_glass"
"tailgate.lamp" = "tail_lights"
"tailgate.strut.l" = "tailgate_strut_l"
"tailgate.strut.r" = "tailgate_strut_r"
# 效果部件
"plug.cable" = "charge_cable"
"ac.airflow" = "airflow"
```

#### [mapping.motion]

motion 类型 → 信号字段映射（vehicle.js 读此驱动 3D）：

| motion | 读信号字段 | 驱动方式 |
|--------|-----------|----------|
| `door` | `doors[id].angle` | 绕 Y 轴旋转 |
| `window` | `doors[id].angle`（跟随门）+ `windows[id].open` | 门旋转 + Y 位移 |
| `hood` | `hood.angle` | 绕轴旋转 |
| `hood_strut` | `hood.angle`（跟随） | 撑杆长度计算 |
| `sunroof` | `sunroof.position` | 位移 + 微旋 |
| `tailgate` | `tailgate.position` | 绕轴旋转 |
| `tailgate_strut` | `tailgate.position`（跟随） | 撑杆长度计算 |
| `cable` | `plugged` | 可见性 |
| `airflow` | `ac` | 可见性 |

## AURA T6 Profile 实例

```toml
# profiles/aura-t6.toml

[vehicle]
profile_id = "aura-t6"
profile_version = "1.0.0"
brand = "Volkswagen"
model = "ID.AURA T6"
vin_pattern = "LSGAB*SIMULATOR*"
model_3d = "models/aura-t6.glb"

[hardware.doors]
count = 4
positions = ["fl", "fr", "rl", "rr"]
type = "hinged"
control = "independent"

[hardware.windows]
count = 4
positions = ["fl", "fr", "rl", "rr"]
control = "independent"

[hardware.sunroof]
type = "panoramic-sliding"
segments = 2

[hardware.tailgate]
type = "power-lift"
linked_parts = ["rear_spoiler", "rear_glass", "tail_lights", "tailgate_strut_l", "tailgate_strut_r"]

[hardware.hood]
type = "hinged"

[hardware.lights]
headlights = "split-led"
tail_lights = true
ambient_interior = true
brake_auto = true
reverse_auto = true

[hardware.charging]
port = "ccs"
ac = true
dc = true

[hardware.driving]
max_speed_kmh = 100
reverse_max_kmh = 20
wheels = 4

[capabilities]
supported = [
  "EXT-10001",  # 车门控制
  "EXT-10002",  # 车窗控制
  "EXT-10003",  # 天窗控制
  "EXT-10004",  # 尾门控制
  "EXT-10005",  # 灯光控制
  "EXT-10006",  # 空调控制
  "EXT-10007",  # 充电控制
  "EXT-10008",  # 车锁控制
  "EXT-10009",  # 机盖控制
  "ENERGY-10001",  # 电量查询
  "DRIVE-10001",  # 行驶控制
]

[capabilities.interlock]
unlock_before_open_door = true
close_door_before_lock = true
plug_before_charge = true
no_start_when_door_open = true
no_start_when_hood_open = true
no_start_when_tailgate_open = true
no_start_when_charging = true
sunroof_open_while_driving = true

[protocol]
ble_version = "v2"
mqtt_auth = "xp"
command_channel = "mixed"

[ble]
service_uuid = "0000AURA-0000-1000-8000-00805F9B34FB"  # 占位，待决策 8 对齐
advertised_name = "ID.AURA T6"
advertise_interval_ms = 100
auth_char_uuid = "0000AUTH-0000-1000-8000-00805F9B34FB"  # 占位
rke_char_uuid = "0000RKE0-0000-1000-8000-00805F9B34FB"  # 占位

[mapping.parts]
"door.fl" = "door_l_0"
"door.fr" = "door_r_0"
"door.rl" = "door_l_1"
"door.rr" = "door_r_1"
"window.fl" = "window_l_0"
"window.fr" = "window_r_0"
"window.rl" = "window_l_1"
"window.rr" = "window_r_1"
"hood" = "hood"
"hood.strut.l" = "bonnet_strut_l"
"hood.strut.r" = "bonnet_strut_r"
"sunroof" = "sunroof"
"tailgate" = "tailgate"
"tailgate.spoiler" = "rear_spoiler"
"tailgate.glass" = "rear_glass"
"tailgate.lamp" = "tail_lights"
"tailgate.strut.l" = "tailgate_strut_l"
"tailgate.strut.r" = "tailgate_strut_r"
"plug.cable" = "charge_cable"
"ac.airflow" = "airflow"
```

## VehicleState 结构（决策 3 + 本决策细化）

按 AURA T6 profile 实例化后的 VehicleState（Rust + 前端镜像同构）：

```rust
pub struct VehicleState {
    pub locked: bool,

    // 独立门（按 profile.hardware.doors.positions 生成）
    pub doors: HashMap<String, DoorState>,   // "fl" → { open: bool, angle: f32 }

    // 独立窗
    pub windows: HashMap<String, WindowState>,  // "fl" → { target: f32, open: f32 }

    pub hood: HoodState,        // { open: bool, angle: f32 }
    pub sunroof: SunroofState,  // { target: f32, position: f32 }
    pub tailgate: TailgateState, // { target: f32, position: f32 }

    pub ac: bool,
    pub temperature: i8,
    pub plugged: bool,
    pub charging: bool,
    pub battery: f32,

    pub lighting: LightingState,
}

pub struct DoorState { pub open: bool, pub angle: f32 }
pub struct WindowState { pub target: f32, pub open: f32 }
pub struct HoodState { pub open: bool, pub angle: f32 }
pub struct SunroofState { pub target: f32, pub position: f32 }
pub struct TailgateState { pub target: f32, pub position: f32 }
```

前端镜像结构相同（JS 对象）。

## vehicle.js 改造（更新决策 5 D5.6）

决策 5 D5.6 原定 vehicle.js 零改动。用户选择独立门后，vehicle.js 需改为读 `state.doors[id].angle`。改动集中在 `createVehicle` 和 `update` 两处。

### 改造点 1：createVehicle 接收 mapping，给门/窗部件标注 id

```js
// src/vehicle.js
export function createVehicle(root, mapping = {}) {
  // 反向映射：GLB 部件名 → 信号 id
  const partToSignal = {};
  for (const [signal, glbName] of Object.entries(mapping)) {
    partToSignal[glbName] = signal;
  }

  // ... 现有遍历逻辑
  root.traverse(node => {
    if (!node.userData.part) return;
    // 新增：从 mapping 标注门/窗 id
    const signal = partToSignal[node.name];
    if (signal?.startsWith('door.')) node.userData.doorId = signal.slice(5);
    if (signal?.startsWith('window.')) node.userData.windowId = signal.slice(7);
    // ... 现有材质/网格处理
  });
  // ...
}
```

### 改造点 2：update 读独立门/窗状态

```js
function update(state, progress, layer = 'all', motion = {}) {
  // ... hood/tailgate/sunroof 不变（单值）
  hoodRotation.setFromAxisAngle(axle, -(state.hood?.angle || 0) * 1.12 * (1 - progress));
  tailgateRotation.setFromAxisAngle(axle, (state.tailgate?.position || 0) * 1.45 * (1 - progress));

  for (const part of parts) {
    // ... 拆解偏移不变
    // ... hood/tailgate/sunroof/hood_strut/tailgate_strut 不变
    // ... 轮胎不变

    // 门：独立读 doors[id].angle
    if (data.motion === 'door') {
      const id = data.doorId;
      const angle = state.doors?.[id]?.angle ?? 0;
      rotation.setFromAxisAngle(yAxis, -data.side * angle * .95 * (1 - progress));
      part.quaternion.premultiply(rotation);
    }
    // 窗：跟随对应门旋转 + 独立下降
    if (data.motion === 'window') {
      const id = data.windowId;
      const doorAngle = state.doors?.[id]?.angle ?? 0;
      const windowOpen = state.windows?.[id]?.open ?? 0;
      rotation.setFromAxisAngle(yAxis, -data.side * doorAngle * .95 * (1 - progress));
      part.quaternion.premultiply(rotation);
      part.position.y -= windowOpen * .54 * (1 - progress);
    }
    // ... layer 切换不变
  }
  // ... effects 不变（plugged/ac 读 state.plugged/state.ac）
}
```

### 改动量

- createVehicle：新增 ~8 行（mapping 反向 + 标注 id）
- update：door/window 分支从合并改为分开，新增 ~10 行
- 其余（hood/sunroof/tailgate/strut/轮胎/effects/layer）不变

### main.js 调用变更

```js
// main.js 启动时
const profile = await fetch('/profiles/aura-t6.toml').then(r => r.text()).then(parseToml);
const vehicle = createVehicle(gltf.scene, profile.mapping.parts);
```

### 兼容性

- `state.doors?.[id]?.angle ?? 0` 用可选链 + 空值合并，profile 未配 mapping 时退化到 0（门不动），不崩溃
- 现有 hood/tailgate/sunroof 字段从扁平（`state.hoodAngle`）改为嵌套（`state.hood.angle`），需同步更新 main.js syncControls 和 inspection/driving 读取

## 前端镜像改造（决策 5 state.js 更新）

```js
// src/state.js（决策 7 更新）
import { createLightingState } from './lighting-state.js';
export const clamp = (v, min = 0, max = 1) => Math.min(max, Math.max(min, v));

export function createMirror(positions = ['fl','fr','rl','rr']) {
  const doors = {}, windows = {};
  for (const id of positions) {
    doors[id] = { open: false, angle: 0 };
    windows[id] = { target: 0, open: 0 };
  }
  return {
    locked: true,
    doors, windows,
    hood: { open: false, angle: 0 },
    sunroof: { target: 0, position: 0 },
    tailgate: { target: 0, position: 0 },
    ac: false, temperature: 22,
    plugged: false, charging: false, battery: 68,
    lighting: createLightingState(),
  };
}

export function followSnapshot(mirror, snapshot, dt) {
  const k = 12;
  // 实际位置插值
  for (const id of Object.keys(mirror.doors)) {
    mirror.doors[id].angle = THREE.MathUtils.damp(mirror.doors[id].angle, snapshot.doors[id].angle, k, dt);
  }
  for (const id of Object.keys(mirror.windows)) {
    mirror.windows[id].open = THREE.MathUtils.damp(mirror.windows[id].open, snapshot.windows[id].open, k, dt);
  }
  mirror.hood.angle = THREE.MathUtils.damp(mirror.hood.angle, snapshot.hood.angle, k, dt);
  mirror.sunroof.position = THREE.MathUtils.damp(mirror.sunroof.position, snapshot.sunroof.position, k, dt);
  mirror.tailgate.position = THREE.MathUtils.damp(mirror.tailgate.position, snapshot.tailgate.position, k, dt);
  mirror.battery = THREE.MathUtils.damp(mirror.battery, snapshot.battery, k, dt);
  // 逻辑状态直接覆盖
  Object.assign(mirror, pick(snapshot, ['locked','ac','temperature','plugged','charging','lighting']));
  for (const id of Object.keys(mirror.doors)) mirror.doors[id].open = snapshot.doors[id].open;
  for (const id of Object.keys(mirror.windows)) mirror.windows[id].target = snapshot.windows[id].target;
  mirror.hood.open = snapshot.hood.open;
  mirror.sunroof.target = snapshot.sunroof.target;
  mirror.tailgate.target = snapshot.tailgate.target;
}

export function explodeOffset(offset, progress, start = 0, end = 1) { /* 不变 */ }
```

## main.js syncControls 改造

现有 syncControls 读 `state.doorsOpen`/`state.doorAngle` 等扁平字段。改为读嵌套：

```js
function syncControls(mirror) {
  // 门：当前 UI 是同步控制，显示"全关/有开"
  const anyDoorOpen = Object.values(mirror.doors).some(d => d.open);
  const anyDoorMoving = Object.values(mirror.doors).some(d => Math.abs(d.angle) > .01);
  $('#door-status').textContent = anyDoorOpen ? '已打开' : '已关闭';
  $('#door-toggle').textContent = anyDoorOpen ? '关闭' : '打开';
  // ... 其余字段读嵌套
  $('#hood-status').textContent = mirror.hood.open ? '已打开' : '已关闭';
  $('#sunroof-value')... = Math.round(mirror.sunroof.position * 100);
  // ...
}
```

## 命令枚举（决策 5 更新，支持独立门）

```rust
pub enum VehicleCommand {
    ToggleLock,
    ToggleDoor { id: Option<String> },  // None = 全部门，Some("fl") = 指定门
    SetWindow { id: Option<String>, target: f32 },
    SetSunroof { target: f32 },
    Tailgate { action: TailgateAction },
    ToggleHood,
    ToggleAc,
    SetTemperature { value: i8 },
    TogglePlug,
    ToggleCharging,
    SetHeadlight { mode: HeadlightMode },
    ToggleTailLight,
    SetAmbient { color: AmbientColor },
    ToggleDriving,
}
```

前端 UI 当前发 `ToggleDoor { id: None }`（全部门同步），未来可扩展单独控制。

## JSON Schema 校验

Profile 用 JSON Schema 校验结构合法性。Schema 文件单独存放：

```
src-tauri/src/profile/schema/
└── vehicle-profile.schema.json
```

校验时机：加载 profile 时校验结构、字段类型、必填项、positions 与 mapping.parts 引用一致性。

> JSON Schema 文件内容较长，实现阶段生成。决策文档记录字段定义（上文表格）作为 schema 的规格来源。

## 关键设计决策

### D7.1 门控用独立模式（用户决策）

**选择**：Profile schema 与 AURA T6 实例都用 `control = "independent"`，4 门各有 open/angle 状态。
**理由**：GLB 里 4 门独立命名；独立模式支持未来单独控制；符合"模拟任何车"目标。
**代价**：更新决策 5 D5.6——vehicle.js 需改为读 `state.doors[id].angle`；前端镜像从扁平 state 变为嵌套。
**缓解**：vehicle.js 改动量小（~18 行）；`?? 0` 兜底未配 mapping 时不崩溃；UI 暂发 `id: None` 同步控制，渐进增强。

### D7.2 Profile 的 mapping.parts 是信号→GLB 的唯一映射来源

**选择**：信号 id（如 `door.fl`）与 GLB 部件名（如 `door_l_0`）的映射只写在 profile，vehicle.js 通过参数接收。
**理由**：换车型时部件命名可能不同，映射随 profile 走不硬编码。
**代价**：vehicle.js createVehicle 多接收一个参数。
**缓解**：参数有默认值 `mapping = {}`，未传时门不动但不崩溃。

### D7.3 能力编号用占位，待决策 6 对齐

**选择**：能力清单用推导占位编号（EXT-10001 等），标注"待对齐 OneSDK"。
**理由**：决策 6 暂缓（知识库工具不可用），不阻塞 profile schema 定义。
**代价**：编号可能与 OneSDK 真实接口空间不符。
**缓解**：编号格式对齐知识库已核验的 fact（onesdk-v1-function-layer-interfaces 的前缀模式 EXT-/ENERGY-/TRIP- 等）；决策 6 对齐时批量替换。

### D7.4 BLE 配置段用占位 UUID

**选择**：Profile 的 `[ble]` 段用占位 UUID/名称，标注"待决策 8 对齐"。
**理由**：OneSDK BLE 具体 UUID/字段待知识库恢复后对齐。
**代价**：BLE 适配器实现阶段需回填真实值。
**缓解**：UUID 字段格式合法（符合 UUID 规范），不影响 schema 校验。

### D7.5 行驶状态不纳入 VehicleState

**选择**：行驶（speed/distance/direction）保留前端 drive-state.js，不纳入后端 VehicleState。
**理由**：行驶是 3D 演示动画（刷新复位可接受），与车控信号模型职责不同；起步联动校验已在后端 interlock。
**代价**：后端不知道车在跑，无法 MQTT 上报行驶状态。
**缓解**：如后续需上报，扩展 VehicleState 加 driving 字段，非破坏性。

### D7.6 Profile 用 TOML，JSON Schema 仅做结构校验

**选择**：Profile 主格式 TOML（人读友好），JSON Schema 定义结构校验规则。
**理由**：决策 3 已定，本决策延续。
**代价**：需维护 schema 文件。
**缓解**：schema 与 profile 一起版本化，加载时校验。

## 待后续决策

- 决策 6：OneSDK 私有协议报文格式对齐（含能力编号真实值、MQTT 报文、BLE RKE 编码）
- 决策 8：BLE 鉴权具体协议字段对齐（含真实 service/characteristic UUID、AUTH0/AUTH1 报文结构）
- 决策 9（可能）：第二个车型 Profile（验证 schema 通用性，如 2 门车或无天窗车）

## 决策依据证据

本决策基于以下事实约束：

1. 现有 GLB 部件清单（scripts/build_aura_t6.py part() 调用，99 个部件）：4 门独立命名（door_l_0/r_0/l_1/r_1）、4 窗独立命名、hood+2 撑杆、sunroof、tailgate+4 联动部件+2 撑杆、cable、airflow
2. 现有 vehicle.js update（src/vehicle.js L79-129）：door/window 共用 `state.doorAngle`/`state.windowOpen` 单值，motion 类型 door/window/hood/hood_strut/sunroof/tailgate/tailgate_strut
3. 现有 state.js 字段（src/state.js L4-5）：locked/doorsOpen/doorAngle/hoodOpen/hoodAngle/sunroofTarget/sunroofPosition/tailgateTarget/tailgatePosition/windowTarget/windowOpen/ac/temperature/plugged/charging/battery/lighting
4. OneSDK Function 层接口编号空间（知识库 fact `onesdk-v1-function-layer-interfaces`）：EXT-/ENERGY-/TRIP-/Widget-/Charging-/Sentry-/Camera-/Diagnose-/FileTransfer- 前缀
5. AGENTS.md 约定：状态集中在 state.js；保留现有联动逻辑；不为局部外观调整引入框架

代码层验证：部件清单与 motion 类型均来自实际读取的 scripts/build_aura_t6.py 源码 ✓；vehicle.js update 逻辑来自实际读取的 src/vehicle.js 源码 ✓。
