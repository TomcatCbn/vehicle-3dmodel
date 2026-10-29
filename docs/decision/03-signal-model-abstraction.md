# 决策 3：信号模型抽象与车型可配置

- **状态**：已定（架构方案层面）
- **决策日期**：2026-10-28
- **决策者**：用户
- **影响范围**：Rust 后端信号模型、车型配置 schema、3D 可视化与信号的对接方式

## 背景

决策 1 锁定 Tauri 2.0 + Rust 后端，决策 2 锁定 MQTT 接真实后台。本决策解决"模拟任何车"的核心抽象——不同车型硬件软件差异如何隔离与配置。

用户明确：**车型可配置**，因为不同车型的硬件（车门数量、车窗数、天窗结构、灯光组合、传感器配置、充电接口、轴距等）与软件（支持的命令集、状态字段、协议版本、能力清单）都有差异。模拟器不能写死单一车型的状态结构。

## 核心设计

### 1. 三层抽象

```
┌─────────────────────────────────────────────────┐
│  Vehicle Profile（车型配置）                     │  静态描述
│  - 一辆车的硬件清单与软件能力                     │
│  - JSON/TOML 描述，可热加载                       │
├─────────────────────────────────────────────────┤
│  Signal Model（信号模型实例）                    │  运行时实例
│  - 按 Profile 实例化的状态机                     │
│  - 持有当前车的实时状态                          │
│  - 执行指令、产出状态变更事件                    │
├─────────────────────────────────────────────────┤
│  Signal Adapters（信号适配器）                   │  可视化映射
│  - 把抽象信号状态映射到具体 3D 部件动作          │
│  - 把抽象信号状态映射到具体协议报文               │
└─────────────────────────────────────────────────┘
```

**Vehicle Profile** 回答"这辆车有什么"，**Signal Model** 回答"这辆车现在是什么状态"，**Signal Adapters** 回答"如何呈现/传输这个状态"。

### 2. Vehicle Profile 结构

每辆车一个 profile 文件，描述硬件清单与软件能力。Profile 是静态描述，不含运行时状态。

```toml
# profiles/aura-t6.toml  （示例，字段后续按 OneSDK 接口对齐细化）

[vehicle]
profile_id = "aura-t6"
profile_version = "1.0.0"
brand = "Volkswagen"
model = "ID.AURA T6"
vin_pattern = "..."              # 用于车管注册
model_3d = "models/aura-t6.glb"  # 3D 资产路径

# ─── 硬件清单 ───
[hardware.doors]
count = 4                          # 4 门
positions = ["fl", "fr", "rl", "rr"]  # 四个门的位置标识
type = "hinged"                    # 铰接门 / 滑动门

[hardware.windows]
count = 4
sync = true                        # 当前实现为四窗同步

[hardware.sunroof]
type = "panoramic-sliding"         # 全景滑动天窗
segments = 2                       # 前活动 + 后固定

[hardware.tailgate]
type = "power-lift"                # 电动尾门
spoil_of = ["rear-glass", "center-tail-lamp", "spoiler"]  # 联动部件

[hardware.hood]
type = "hinged"

[hardware.lights]
headlights = "split-led"           # 分体 LED
tail_lights = true
ambient_interior = true
brake_auto = true
reverse_auto = true

[hardware.charging]
port = "ccs"                       # CCS / Type2 / GB/T
ac = true
dc = true

[hardware.driving]
max_speed_kmh = 100                # 模拟器演示限速
reverse_max_kmh = 20
wheels = 4

# ─── 软件能力 ───
[capabilities]
# 对齐 OneSDK Function 层接口前缀（fact: onesdk-v1-function-layer-interfaces）
supported = [
  "EXT-10001",  # 车门控制
  "EXT-10002",  # 车窗控制
  "EXT-10003",  # 天窗控制
  "EXT-10004",  # 尾门控制
  "EXT-10005",  # 灯光控制
  "EXT-10006",  # 空调控制
  "EXT-10007",  # 充电控制
  "EXT-10008",  # 车锁控制
  "ENERGY-10001",  # 电量查询
  "TRIP-10001",    # 行程
  # ... 不支持的能力不列，模拟器收到对应指令返回 unsupported
]

[capabilities.lock_interlock]
# 保留现有联动逻辑（AGENTS.md 约定）
unlock_before_open_door = true
close_door_before_lock = true
plug_before_charge = true
no_start_when_door_open = true
no_start_when_hood_open = true
no_start_when_tailgate_open = true
no_start_when_charging = true
sunroof_open_while_driving = true  # 天窗可保持开启行驶

# ─── 协议版本 ───
[protocol]
ble_version = "v2"                 # 对齐 fact: onesdk-v1-file-transfer-v1v2-protocol 等
mqtt_auth = "xp"                   # 对齐 fact: onesdk-v1-auth-xp / cea
command_channel = "mixed"          # 对齐 fact: onesdk-cmd-select-channel

# ─── 3D 部件映射 ───
# 把抽象信号（如 door.fl.open=true）映射到具体 GLB 部件名
[mapping.parts]
"door.fl" = "左前门"
"door.fr" = "右前门"
"sunroof.front" = "电动天窗"
"tailgate" = "尾门"
"hood" = "前舱盖"
# ... 完整映射表，由 Signal Adapter 读取
```

### 3. Signal Model 运行时实例

Signal Model 是按 Profile 实例化的运行时状态机。它**不知道** 3D、不知道 MQTT、不知道 BLE——只持有车的状态并执行状态转换。

```rust
// src-tauri/src/signal/model.rs  （示意，具体 API 后续决策细化）

pub struct SignalModel {
    profile: VehicleProfile,
    state: VehicleState,        // 当前车端状态
    command_queue: CommandQueue, // 对齐 fact: onesdk-command-queue
}

impl SignalModel {
    pub fn from_profile(profile: VehicleProfile) -> Self { ... }

    // 接收指令（来自 MQTT 或本地 UI），校验能力、执行联动、产出状态变更
    pub fn apply_command(&mut self, cmd: Command) -> CommandResult {
        // 1. 检查 profile.capabilities 是否支持该指令
        // 2. 检查联动约束（如开门前必须解锁）
        // 3. 执行状态转换
        // 4. 入命令队列，启动延迟监听（100ms/200ms/7s，对齐 fact）
        // 5. 返回状态变更事件
    }

    // 状态变更事件流（订阅者监听）
    pub fn state_changes(&self) -> impl Iterator<Item = StateChange> { ... }

    // 当前状态快照（用于上报后台/同步前端）
    pub fn snapshot(&self) -> VehicleState { ... }
}
```

VehicleState 是**动态字段集**，不是固定结构——不同 profile 的车门数、车窗数不同，状态字段也不同：

```rust
// src-tauri/src/signal/state.rs

pub struct VehicleState {
    // 标量字段（所有车共有）
    pub locked: bool,
    pub battery: f32,
    pub temperature: i8,
    pub ac: bool,
    pub charging: bool,
    pub plugged: bool,

    // 动态字段集（按 profile 硬件清单生成）
    pub doors: HashMap<DoorId, DoorState>,       // 4 门车有 4 项，2 门车有 2 项
    pub windows: HashMap<WindowId, f32>,          // 开度 0-1
    pub lights: LightState,                      // 按 profile.lights 配置
    pub sunroof: Option<SunroofState>,           // profile 没配天窗则为 None
    pub tailgate: Option<TailgateState>,
    pub hood: Option<HoodState>,
    // ...
}
```

### 4. Signal Adapters

Signal Model 产出的是抽象状态变更，需要适配器映射到具体呈现/传输。

**3D 适配器**：监听状态变更，按 profile 的 `mapping.parts` 表把信号状态映射到 GLB 部件动作，驱动 3D 渲染。这层负责"门开了 → 哪个 mesh 转 60°"。

**MQTT 适配器**：监听状态变更，按对齐后的 OneSDK 报文格式打包，发布到对应 topic。

**BLE 适配器**：监听状态变更，按 GATT characteristic 结构更新通知值。

三个适配器订阅同一个 Signal Model 的状态变更流，互不依赖。

## 关键设计决策

### D3.1 Profile 是静态描述，Model 是运行时实例

**选择**：Profile（TOML/JSON）描述硬件清单与能力，不含运行时状态；Signal Model 加载 Profile 后实例化运行时状态。
**理由**：静态描述可热加载、可版本化、可分享；运行时状态隔离在 Model 内，逻辑清晰。
**代价**：Profile 与 Model 是两个概念，需要维护实例化逻辑。
**缓解**：提供 `SignalModel::from_profile()` 构造器封装实例化逻辑。

### D3.2 Profile 格式选 TOML（主格式）+ JSON Schema 校验

**选择**：Profile 用 TOML 写（人读友好），用 JSON Schema 定义结构校验。
**理由**：TOML 适合手写车型配置；JSON Schema 提供机器校验；两者都是标准格式，不引入运行时依赖。
**代价**：需要维护 schema 文件。
**缓解**：schema 与 profile 一起版本化，启动时校验。

### D3.3 VehicleState 用动态字段集（HashMap），不是固定 struct

**选择**：状态按 profile 硬件清单动态生成字段集（如 `doors: HashMap<DoorId, DoorState>`），不是写死 4 个门字段。
**理由**：支持"模拟任何车"——2 门车、4 门车、无天窗车都用同一个 VehicleState 结构。
**代价**：访问状态需按 id 查找，比固定字段略繁琐；类型检查弱化。
**缓解**：提供强类型访问器（`state.door("fl")?` 返回 `Result<DoorState>`）；profile 校验阶段保证 id 合法。

### D3.4 现有 AURA T6 作为第一个 Profile

**选择**：现有 `src/state.js` 的字段（locked/doorsOpen/hoodOpen/sunroof/sunroofPosition/tailgate/tailgatePosition/windowOpen/battery/ac/temperature/plugged/charging/lighting）迁移为第一个 Profile `profiles/aura-t6.toml`。
**理由**：保留现有 3D 车控逻辑作为第一个验证案例；不破坏现有功能；为后续车型提供参考实现。
**代价**：现有 `state.js` 需重构为"按 profile 实例化的状态"，不是直接改。
**缓解**：分阶段迁移——先建 Profile 与 Model，现有前端 state 作为 Model 的镜像视图，逐步替换。

### D3.5 3D 部件映射放在 Profile，不放在代码里

**选择**：信号状态与 3D 部件的映射关系（如 `door.fl → 左前门` GLB 部件名）写在 Profile 的 `mapping.parts` 里，不写死在代码。
**理由**：换车型时 3D 部件命名可能不同（如英文 `door_fl` vs 中文 `左前门`），映射关系应随 profile 配置，不应硬编码。
**代价**：Profile 文件略长；映射错误时需调试配置。
**缓解**：启动时校验映射表引用的 GLB 部件名是否存在于模型。

### D3.6 能力清单驱动指令校验

**选择**：Profile 的 `capabilities.supported` 列表决定模拟器响应哪些指令；收到未列出的指令返回 `unsupported`。
**理由**：不同车型支持的软件能力不同（如低端车无哨兵、无天窗）；能力清单让模拟器行为可配置。
**代价**：能力编号需对齐 OneSDK 接口前缀（如 `EXT-10001`），前期需查知识库 fact 对照。
**缓解**：参考知识库 fact `onesdk-v1-function-layer-interfaces` 的接口编号空间建立映射表。

## 现有 `src/state.js` 迁移路径

当前 `state.js`：
```js
{ locked: true, doorsOpen: false, doorAngle: 0, hoodOpen: false, 
  hoodAngle: 0, sunroofTarget:0, sunroofPosition:0, ... }
```

迁移后：
- `profiles/aura-t6.toml` 描述这辆车的硬件清单与能力（字段值从现有 state 推导）
- Rust `SignalModel` 加载 profile 后实例化 `VehicleState`，初始值与现有 state 默认值一致
- 前端 `state.js` 保留但角色变化：从"状态唯一来源"变为"Model 状态的镜像"——通过 Tauri events 接收 Model 状态变更，更新本地镜像驱动 3D
- 前端操作改为发 Tauri command 给后端，后端 Model 执行状态转换，事件回前端更新镜像

迁移分阶段（决策 5 细化）：
1. 建 Profile 文件与 Model 结构，AURA T6 字段先迁移
2. 前端 state 改为 Model 镜像，本地操作走后端往返
3. 接入 MQTT 适配器，后台下发指令也能更新 Model

## 模块边界（Rust 后端）

```
src-tauri/src/
├── profile/                # Profile 加载与校验
│   ├── mod.rs
│   ├── loader.rs           # TOML 解析、JSON Schema 校验
│   └── schema/             # Profile JSON Schema 文件
├── signal/                  # 信号模型
│   ├── mod.rs
│   ├── model.rs            # SignalModel 状态机
│   ├── state.rs           # VehicleState 动态字段集
│   ├── command.rs          # 命令定义、队列、延迟监听
│   └── interlock.rs        # 联动约束校验
└── adapter/                # 信号适配器
    ├── mod.rs
    ├── threed.rs           # 3D 部件映射适配器（状态→GLB 部件动作）
    ├── mqtt.rs             # MQTT 报文适配器（状态→OneSDK 报文）
    └── ble.rs              # BLE GATT 适配器（状态→characteristic 值）
```

## 待后续决策

- 决策 4：BLE 协议核心层 API（对齐 OneSDK BLE fact：AUTH0/AUTH1、polling、密钥派生）
- 决策 5：3D 车控与信号模型如何对接（现有 `state.js` 重构详细路径）
- 决策 6：OneSDK 私有协议报文格式对齐细节
- 决策 7（新增）：车型 Profile 完整字段定义与 schema（基于现有 AURA T6 state 字段 + OneSDK 接口编号空间推导）

## 决策依据证据

本决策基于以下事实约束：

1. OneSDK Function 层接口编号空间（知识库 fact `onesdk-v1-function-layer-interfaces`）：Trip/Energy/Widget/Charging/Sentry/Camera/Diagnose/FileTransfer 等模块的接口前缀与编号
2. OneSDK Vehicle Plugin 层按业务域拆分（知识库 fact `onesdk-v1-vehicle-plugin-components`）：每个插件封装对应域的车端接口
3. OneSDK 命令队列与延迟监听（知识库 fact `onesdk-command-queue`）：offerCmd 入队、100ms 延迟、200ms 间隔、7s 超时
4. OneSDK 车辆状态数据模型（知识库 fact `onesdk-vehicle-state-model`）：VehicleState（原始）与 DigitalVehicleState（数字化）分离
5. 现有项目 `src/state.js` 结构：locked/doorsOpen/hoodOpen/sunroof/sunroofPosition/tailgate/tailgatePosition/windowOpen/battery/ac/temperature/plugged/charging/lighting
6. 现有项目 GLB 部件名（中文命名）：`左前门`/`右前门`/`电动天窗`/`尾门`/`前舱盖` 等

知识库来源核验：上述 fact 引用 `SRC-2026-000044-e71d`（OneSDK 架构设计文档 Part 1，V0.14.0/baseline V3.1），标题与版本匹配 ✓。
