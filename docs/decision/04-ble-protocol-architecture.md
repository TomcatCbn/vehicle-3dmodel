# 决策 4：BLE 协议核心层架构

- **状态**：已定（架构方案层面；具体协议字段后续接入知识库对齐）
- **决策日期**：2026-10-28
- **决策者**：用户
- **影响范围**：Rust 后端 BLE 模块、协议状态机、与 Signal Model 的对接

## 背景

决策 1 选定 B2 策略（协议核心纯软件 + 平台 BLE 适配层）。本决策确定 BLE 协议核心层的架构方案与职责边界，具体协议字段（AUTH0/AUTH1 报文结构、密钥派生算法、RKE 命令编码等）待接入知识库 OneSDK BLE fact 后单独决策对齐。

## 用户需求

1. **车端发送蓝牙广播**——模拟器扮演 BLE peripheral，对外广播
2. **手机发起蓝牙连接**——真实手机 App（OneSDK）作为 central 主动连接模拟器
3. **手机发起鉴权**——连接建立后由手机端发起 AUTH0/AUTH1 鉴权流程
4. **车端按鉴权流程响应**——模拟器作为车端正确响应每一步鉴权交互
5. **车端响应 RKE 车控指令**——鉴权通过后，手机可下发 RKE 车控指令，车端执行并响应

## 核心链路

```
   手机 App (OneSDK, central)              车模拟器 (peripheral)
   ─────────────────────                  ─────────────────────
            │                                      │
            │          ① BLE 扫描                   │
            │ ◄─────────────────────────────────── │ start_advertising()
            │                                      │   广播 service UUID
            │          ② 建立连接                   │
            │ ───────────────────────────────────► │ on_connect()
            │                                      │   暴露 GATT service
            │                                      │   /characteristics
            │          ③ AUTH0                     │
            │   write(authKey + indicator)         │
            │ ───────────────────────────────────► │ protocol.handle_auth0()
            │                                      │   派生 sessionKey
            │                                      │   派生 hmacKey
            │   notify(R01, R1)                    │
            │ ◄─────────────────────────────────── │ protocol.send_auth0_reply()
            │                                      │
            │          ④ AUTH1                     │
            │   write(xor(sessionKey, R12+sec))    │
            │ ───────────────────────────────────► │ protocol.handle_auth1()
            │                                      │   验证 R12=R1+2
            │                                      │   鉴权完成
            │                                      │   启动 polling 就绪
            │   notify(auth_ok)                   │
            │ ◄─────────────────────────────────── │
            │                                      │
            │          ⑤ RKE 车控                   │
            │   write(rke_command)                │
            │ ───────────────────────────────────► │ protocol.handle_rke()
            │                                      │   派发给 SignalModel
            │                                      │   SignalModel.apply_command()
            │                                      │   产出状态变更
            │   notify(rke_response)               │
            │ ◄─────────────────────────────────── │ protocol.send_rke_response()
            │                                      │
            │          ⑥ 断开                       │
            │ ───────────────────────────────────► │ on_disconnect()
            │                                      │   清理会话
```

## 架构方案

### 1. 三层结构

```
┌─────────────────────────────────────────────────────┐
│  Platform BLE Adapter（平台适配层）                 │
│  - btleplug 实现（macOS 优先，Windows 后续）         │
│  - mock 适配器（开发期默认，不接真实硬件）           │
│  - 暴露 trait：广播/GATT/通知                       │
├─────────────────────────────────────────────────────┤
│  Protocol Core（协议核心层，纯软件，跨平台）         │
│  - 鉴权状态机（AUTH0/AUTH1）                        │
│  - RKE 命令处理                                     │
│  - 密钥派生与会话管理                                │
│  - 不依赖任何 BLE 库                                │
├─────────────────────────────────────────────────────┤
│  Signal Model 对接（决策 3）                         │
│  - RKE 命令派发给 SignalModel.apply_command()       │
│  - 状态变更通过 adapter 回传                         │
└─────────────────────────────────────────────────────┘
```

**Platform BLE Adapter** 负责"字节进出 BLE"（GATT 读写/通知），**Protocol Core** 负责"字节意味着什么"（协议状态转换）。两层解耦——核心协议逻辑可单测，硬件差异隔离在适配层。

### 2. 协议核心层状态机

```rust
// src-tauri/src/ble/protocol.rs  （示意，具体字段后续对齐 OneSDK BLE fact）

pub enum AuthState {
    Disconnected,
    Connected,           // GATT 连接建立，未鉴权
    Auth0Pending,        // 收到 AUTH0 请求，待处理
    Auth0Replied,        // 已回复 AUTH0，等待 AUTH1
    Auth1Pending,        // 收到 AUTH1 请求，待处理
    Authenticated,       // 鉴权完成，可接收 RKE
}

pub struct BleSession {
    state: AuthState,
    session_key: Option<SessionKey>,    // AUTH0 后派生
    hmac_key: Option<HmacKey>,          // AUTH0 后派生
    // 其他会话字段待对齐 fact 后补充
}

pub struct ProtocolCore {
    session: BleSession,
    signal_model: Sender<SignalCommand>,  // 派发 RKE 给 SignalModel
}

impl ProtocolCore {
    // 平台适配层回调：连接建立
    pub fn on_connect(&mut self) { self.session.state = Connected; }

    // 平台适配层回调：characteristic 被写入
    pub fn on_characteristic_write(&mut self, char_id: CharId, data: &[u8]) -> WriteResult {
        match (self.session.state, char_id) {
            (Connected, AUTH_CHAR)        => self.handle_auth0(data),
            (Auth0Replied, AUTH_CHAR)     => self.handle_auth1(data),
            (Authenticated, RKE_CHAR)     => self.handle_rke(data),
            _ => Err(UnexpectedWrite),
        }
    }

    // AUTH0 处理：解析 authKey/indicator → 派生密钥 → 产出回复数据
    fn handle_auth0(&mut self, data: &[u8]) -> WriteResult { /* 待对齐 fact */ }

    // AUTH1 处理：验证 R12 → 标记鉴权完成
    fn handle_auth1(&mut self, data: &[u8]) -> WriteResult { /* 待对齐 fact */ }

    // RKE 处理：解析命令 → 派发 SignalModel → 产出响应
    fn handle_rke(&mut self, data: &[u8]) -> WriteResult {
        let cmd = self.decode_rke(data)?;
        let result = self.signal_model.send(SignalCommand::from_rke(cmd))?;
        self.encode_rke_response(result)
    }
}
```

### 3. 平台适配层 trait

```rust
// src-tauri/src/ble/adapter.rs  （示意）

#[async_trait]
pub trait BlePeripheral: Send + Sync {
    /// 开始广播指定 service UUID
    async fn start_advertising(&self, service_uuid: Uuid) -> Result<()>;

    /// 停止广播
    async fn stop_advertising(&self) -> Result<()>;

    /// 暴露 GATT service 与 characteristics
    async fn expose_gatt_service(
        &self,
        service: GattServiceDef,
        on_write: Box<dyn Fn(CharId, &[u8]) -> Vec<u8> + Send + Sync>,
    ) -> Result<()>;

    /// 主动通知 characteristic 值（用于 AUTH0/AUTH1/RKE 回复）
    async fn notify(&self, char_id: CharId, value: &[u8]) -> Result<()>;

    /// 注册连接/断开回调
    async fn on_connection_change(&self, handler: Box<dyn Fn(ConnectionEvent) + Send + Sync>) -> Result<()>;
}
```

**两个实现**：
- `MockBlePeripheral`：不接真实硬件，记录调用、触发回调模拟手机写入——开发期默认，可单测
- `BtleplugPeripheral`：用 `btleplug` 接真实 BLE——macOS 优先打通，Windows 后续

Protocol Core 只依赖 `BlePeripheral` trait，不知道具体实现——可单测、可换实现。

### 4. 与 Signal Model 对接

RKE 车控指令与本地 UI 指令在 **Signal Model 层汇合**（决策 3 已定）：

```
RKE 命令（BLE 下行）  ┐
                     ├─→ SignalModel.apply_command()  ─→ 状态变更事件
本地 UI 指令          ┘                                      │
（Tauri command）                                             ├──→ 3D 适配器（更新 GLB 部件）
                                                              ├──→ MQTT 适配器（上报状态）
                                                              └──→ BLE 适配器（通知手机 RKE 响应）
```

BLE 下行 RKE 命令执行后，状态变更同时：
- 通过 3D 适配器更新前端 3D（车门动了）
- 通过 MQTT 适配器上报后台（让云端知道车控结果）
- 通过 BLE 适配器通知手机 RKE 响应（让 App 收到执行结果）

三个适配器订阅同一个状态变更流，互不依赖。

## 关键设计决策

### D4.1 协议核心不依赖 BLE 硬件库

**选择**：Protocol Core 只定义状态转换与数据流，不引用 `btleplug`；通过 `BlePeripheral` trait 抽象硬件交互。
**理由**：核心协议逻辑（AUTH0/AUTH1/RKE 状态转换、密钥派生、命令编解码）可单测、跨平台一致；硬件差异隔离在适配层。
**代价**：需要定义 trait 接口与两个实现（mock + btleplug）。
**缓解**：mock 实现简单（记录调用即可），btleplug 实现分阶段（macOS 优先）。

### D4.2 鉴权状态机用 enum 表示状态转换

**选择**：用 `AuthState` enum 显式表示鉴权各阶段，状态转换通过方法触发。
**理由**：编译期保证状态转换合法性（如未鉴权时收 RKE 命令直接拒绝）；状态机可读可测。
**代价**：新增状态需改 enum。
**缓解**：状态机本身稳定（AUTH0/AUTH1/RKE 几个阶段），变更少。

### D4.3 车端被动响应，不主动发起

**选择**：模拟器作为车端，所有交互由手机端发起（连接、AUTH0、AUTH1、RKE 命令），车端只响应。
**理由**：对齐 OneSDK fact（`onesdk-ble-auth-flow`：App 发起 indicator + authKey，车端 TBox 响应）；符合真实车端角色。
**代价**：模拟器无法主动测试手机端，需真实手机 App 配合联调。
**缓解**：mock 适配器可模拟手机写入流程，用于无真实手机时的自测。

### D4.4 RKE 命令通过 Signal Model 统一执行

**选择**：BLE 下行的 RKE 命令不直接改状态，而是派发给 `SignalModel.apply_command()`，与本地 UI 指令走同一路径。
**理由**：状态唯一来源（决策 3 已定）；避免 BLE 与本地 UI 各自改状态导致冲突；联动约束（解锁才能开门等）统一在 Signal Model 校验。
**代价**：RKE 响应需等 Signal Model 处理完成后才能回传手机。
**缓解**：Signal Model 同步执行（无 IO），响应延迟可忽略；命令队列与延迟监听对齐 fact `onesdk-command-queue`。

### D4.5 BLE 会话与 Signal Model 解耦

**选择**：BleSession 只持有鉴权相关状态（密钥、鉴权阶段），不持有车辆状态；车辆状态在 Signal Model。
**理由**：BLE 会话是连接级状态（一次连接一套密钥），车辆状态是全局状态（与连接无关）；解耦后多次断连重连不影响车辆状态。
**代价**：RKE 处理需桥接 BleSession（密钥校验）与 Signal Model（状态变更）。
**缓解**：ProtocolCore 持有两者引用，在 handle_rke 中完成桥接。

### D4.6 广播内容随 profile 配置

**选择**：广播的 service UUID、广播间隔、广播数据由 Vehicle Profile 配置（决策 3 的 profile 文件加 `[ble]` 段）。
**理由**：不同车型 BLE 配置可能不同（service UUID、广播参数）；配置化支持多车型。
**代价**：Profile 增加一段配置。
**缓解**：提供默认值，profile 不配则用默认。

## 模块边界（Rust 后端）

```
src-tauri/src/ble/
├── mod.rs                  # BLE 模块入口
├── protocol.rs             # 协议核心层（状态机、密钥派生、命令编解码）
├── adapter/                # 平台适配层
│   ├── mod.rs
│   ├── trait.rs            # BlePeripheral trait 定义
│   ├── mock.rs             # mock 实现（开发期默认）
│   └── btleplug.rs         # btleplug 实现（macOS 优先，Windows 后续）
├── session.rs              # BleSession 会话管理
└── gatt.rs                 # GATT service/characteristic 定义
```

## 待后续决策

- 决策 5：3D 车控与信号模型如何对接（现有 `state.js` 重构详细路径）
- 决策 6：OneSDK 私有协议报文格式对齐细节（含 BLE AUTH0/AUTH1 报文结构、RKE 命令编码）
- 决策 7：车型 Profile 完整字段定义与 schema（含 BLE 配置段）
- 决策 8（新增）：BLE 鉴权具体协议字段对齐（接入知识库 OneSDK BLE fact 后细化）

## 决策依据证据

本决策基于以下事实约束：

1. OneSDK BLE 鉴权流程（知识库 fact `onesdk-ble-auth-flow`）：AUTH0/AUTH1 两阶段；AUTH0 由 App 发起 indicator + authKey，车端 TBox 返回 R01/R1，App 验证 R01=R0+1，派生 sessionKey=hkdf_sha256(R0||R1)，hmacKey=hmac(authKey, R01||R12)；AUTH1 由 App 发送 xor(sessionKey, R12+security message)，车端验证 R12=R1+2 完成鉴权，启动 polling
2. OneSDK polling 配置（知识库 fact `onesdk-polling-config`）：欢迎模式、polling 开关、解锁/闭锁距离、自校准；AUTH1 完成后启动，基于 RSSI 测距
3. OneSDK 命令队列（知识库 fact `onesdk-command-queue`）：offerCmd 入队、延迟 100ms 监听、200ms 间隔、7s 超时
4. OneSDK 控车通道选择（知识库 fact `onesdk-cmd-select-channel`）：5 种模式，BLE/MQTT/混合；RKE 走 BLE 通道
5. Web Bluetooth API 标准限制（决策 1 已记录）：浏览器不支持 peripheral，必须原生层

知识库来源核验：上述 fact 引用 `SRC-2026-000044-e71d`（OneSDK 架构设计文档 Part 1，V0.14.0/baseline V3.1），标题与版本匹配 ✓。

## 待知识库对齐的协议字段（决策 8 占位）

接入知识库 OneSDK BLE fact 后需细化的字段：
- AUTH0 报文结构（indicator/authKey 字段布局、UID/KEYID/随机数 R0/timestamp/polling 配置）
- AUTH0 回复报文（R01/R1 字段布局）
- AUTH1 报文（security message 结构、xor 编码）
- sessionKey 派生参数（hkdf_sha256 的 info/salt）
- hmacKey 派生参数
- RKE 命令编码（命令类型、参数结构）
- RKE 响应编码（执行结果、状态回传）
- GATT service/characteristic UUID（如有标准）
- 广播数据结构
