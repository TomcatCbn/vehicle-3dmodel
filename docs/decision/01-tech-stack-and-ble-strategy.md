# 决策 1：技术栈载体与 BLE 策略

- **状态**：已定
- **决策日期**：2026-10-28
- **决策者**：用户
- **影响范围**：整个模拟器重构的技术栈选型、跨平台支持、BLE 接入路径

## 背景

项目从"3D 车展示 + 本地车控 UI"重构为"车信号模拟器平台"——可模拟任意车的输出信号，支持真实协议联调。核心链路：

```
手机 App ──MQTT── 后台 ──MQTT── 车模拟器
                                    │
                                    ├─ 3D 可视化
                                    ├─ 信号模型
                                    ├─ 车控执行
                                    └─ BLE peripheral（被手机连，鉴权流程）
```

现有资产：Three.js + Vite + 原生 ES Modules 的 3D 车辆可视化（99 个独立部件的 ID.AURA T6），含 Blender 生成脚本、GLB 模型、滚动拆解、细节查看、行驶演示。

新需求关键约束：

1. **Windows 与 macOS 双平台都要支持**——车既可被手机 BLE 连接，也可连上 MQTT。
2. **MQTT 后台是真实现成的**——模拟器向车管后台注册自己为一辆车，后台返回 MQTT 连接参数（broker 地址、deviceId、topic、凭证），模拟器用这些参数直连真实 MQTT broker。
3. 现有 3D 模型渲染投资尽量保留。

## 关键技术约束（决定选型的物理事实）

### 约束 1：浏览器无法做 BLE peripheral

Web Bluetooth API 在所有平台（Windows/macOS/Linux）**只支持 central 角色**（扮演手机去连车），**不支持 peripheral 角色**（扮演车被连）。

这意味着：
- 纯浏览器方案下，BLE 只能做 UI 演示（不真广播、不暴露 GATT 服务端），真实手机 App 连不上模拟器。
- 如果要"真实手机连模拟器做 BLE 鉴权"，必须有原生层支持 GATT 服务端。

这不是浏览器实现的差异，是 W3C 标准限制，任何浏览器方案都绕不过。

### 约束 2：BLE peripheral GATT 服务端在任何跨平台框架里都需要原生代码

OneSDK BLE 鉴权（AUTH0/AUTH1）需要 GATT 服务端——车端暴露 service/characteristic，手机读写 characteristic 完成 indicator、authKey、sessionKey、security message 交换。这不是简单广播，是完整的 GATT 服务端交互。

| 框架 | BLE peripheral 能力 | 现实 |
|------|---------------------|------|
| Flutter | `flutter_ble_peripheral` 只支持广播，**不支持 GATT 服务端**；要做鉴权需自写原生 plugin（Swift + Kotlin） | Dart 层做不了，必须写双端原生代码 |
| Rust (Tauri) | `btleplug` 支持 peripheral + GATT 服务端，Windows 实现质量不如 macOS | 跨平台一致但 Windows 弱 |
| 纯 Node bleno | macOS CoreBluetooth、Windows winrt | 平台差异大，社区维护质量参差 |

**结论**：跨平台框架选择不能消除原生代码需求，差异只在"原生代码多少"和"哪部分跨平台共享"。

### 约束 3：3D 渲染管线迁移成本

现有 Three.js 渲染管线包含：HDR 环境光、物理玻璃材质、VSM 软阴影、模糊地面反射、AgX 色调映射、滚动拆解动画、细节查看取景。重写到 Flutter 3D 引擎或 Rust 3D 库成本极高。

GLB 是标准格式理论上可换引擎加载，但渲染管线、材质参数、动画逻辑都绑死 Three.js API——重写等于重做。

**结论**：3D 部分应保留为 Web 资产，跨平台壳内嵌 WebView 承载，不做迁移。

## 选项评估

### 选项 A：纯浏览器 + mqtt.js

- ✅ 前端零改动
- ✅ MQTT 通过 WebSocket 直连真实后台 broker（需 broker 开 WS 端口）
- ❌ BLE peripheral 不可能（约束 1），真实手机连不上
- ❌ 违背"车可以被手机 BLE 连接"的硬需求

**淘汰**：不满足 BLE 硬需求。

### 选项 B：Node.js 后端 + 浏览器前端

- ✅ Node bleno 可做 BLE peripheral
- ✅ 前端几乎零改动
- ⚠️ macOS bleno 前台可用、后台不稳定
- ⚠️ Windows bleno 不稳定
- ⚠️ 双进程部署（Node + 浏览器），分发复杂

**保留为备选**，但分发与平台稳定性差。

### 选项 C：Flutter + WebView 内嵌 3D

- ✅ 3D 通过 WebView 保留
- ✅ Dart 学习曲线平缓
- ❌ BLE peripheral GATT 服务端需自写 Swift + Kotlin 双端原生 plugin
- ❌ 前后端通信走 JS channel 有延迟，不适合实时车控
- ⚠️ Flutter 生态 BLE peripheral 库弱

**淘汰**：BLE 路径需双端原生代码，比 Tauri 工作量大；JS channel 延迟不适合车控。

### 选项 D：Tauri 2.0（Rust 后端 + WebView 前端）

- ✅ 前端零迁移——现有 Vite 应用直接作为 Tauri frontend
- ✅ Rust 后端：MQTT（rumqttc）、BLE（btleplug）、HTTP（reqwest）都有成熟库
- ✅ BLE peripheral 走 btleplug，支持 GATT 服务端，跨平台单一代码库
- ✅ 单二进制分发，双平台用户各下一个文件
- ✅ Tauri commands 直接调 Rust 函数，IPC 延迟低，适合实时车控
- ⚠️ Rust 学习曲线较陡
- ⚠️ Windows 上 btleplug GATT 服务端实现质量不如 macOS

**胜出**。

## 最终决策

### 决策 1.1：技术栈采用 Tauri 2.0

- 前端：保留现有 Vite + Three.js + 原生 ES Modules，作为 Tauri webview frontend
- 后端：Rust（Tauri backend），承载 MQTT 客户端、BLE peripheral、HTTP 注册、协议状态机、信号模型
- 通信：Tauri commands（Rust ↔ JS IPC）

### 决策 1.2：BLE 策略采用 B2（协议核心 + 平台适配层）

BLE peripheral 真实程度选择 B2：协议状态机核心做成纯软件模块，BLE 硬件接入做成平台适配层。

- **协议核心层**（Rust 纯软件，跨平台一致，可单测）：
  - AUTH0/AUTH1 状态机
  - authKey/sessionKey/hmacKey 派生逻辑
  - polling 配置与状态管理
  - 命令队列与延迟监听
  - 不依赖任何 BLE 硬件库，纯算法与状态转换

- **平台 BLE 适配层**（`btleplug` 实现，分阶段接入）：
  - 暴露 trait 接口：`start_advertising` / `stop_advertising` / `expose_gatt_service` / `on_characteristic_write` / `on_characteristic_read` / `notify`
  - 第一阶段：mock 适配器（不接真实硬件，UI 演示鉴权流程）——开发期默认
  - 第二阶段：`btleplug` 适配器，macOS 优先打通真实手机可连
  - 第三阶段：Windows btleplug 适配器打磨，视实际稳定性决定是否默认启用

- **协议核心与适配层解耦**：核心层只定义状态转换与数据流，不引用 btleplug；适配层把核心层的状态变化映射到 GATT characteristic 的读写/通知。这样协议逻辑可单测、跨平台一致，硬件差异隔离在适配层。

### 决策 1.3：MQTT 接入真实后台

- 模拟器启动后通过 HTTP 向车管后台注册自己为一辆车
- 后台返回 MQTT 连接参数（broker 地址、deviceId、topic、凭证）
- Rust 后端用 `rumqttc` 维持 MQTT 连接，订阅车端 topic，发布状态/响应
- 前端不直接连 MQTT，只通过 Tauri commands 与 Rust 后端通信

## 影响与后续工作

### 现有资产保留

- ✅ Three.js 3D 可视化：作为 Tauri webview frontend，零迁移
- ✅ `src/state.js`：演进为"信号模型实例"（一辆车的本地状态），协议层在状态变更时同步
- ✅ `src/vehicle.js`：3D 部件运动仍由 state 驱动，state 来源从"本地 UI 操作"扩展为"本地 UI 操作 + 协议层事件"
- ✅ `src/main.js` 控制台：保留，操作从"直接改 state"改为"发指令给 Rust 后端 → 后端更新信号模型 → 状态变更事件回前端"
- ✅ Blender 生成脚本、GLB 模型：完全不动

### 新增结构（后续决策细化）

- `src-tauri/`：Rust 后端
  - `src/mqtt/`：MQTT 客户端与 topic 路由
  - `src/ble/`：协议核心层 + 平台适配层
  - `src/signal/`：信号模型抽象（支持任意车）
  - `src/registration/`：车管后台注册
- 前端协议层薄封装：通过 Tauri commands 调后端，状态变更通过事件回前端

### 待后续决策细化

- 决策 2：MQTT 接入细节（注册流程、topic 规约、报文格式是否对齐 OneSDK 私有协议）
- 决策 3：信号模型抽象（如何支持"模拟任何车"，schema 配置化方案）
- 决策 4：BLE 协议核心层 API（对齐知识库 OneSDK BLE fact：AUTH0/AUTH1、polling 配置、密钥派生）
- 决策 5：3D 车控与信号模型如何对接（现有 `state.js` 重构路径）

## 决策依据证据

本决策基于以下事实约束：

1. Web Bluetooth API 标准限制——不支持 peripheral 角色（W3C Web Bluetooth 草案，所有浏览器实现一致）
2. OneSDK BLE 鉴权流程需要 GATT 服务端（知识库 fact `onesdk-ble-auth-flow`：AUTH0/AUTH1 两阶段，indicator + authKey + sessionKey + security message 交换）
3. 现有 Three.js 渲染管线重写成本（HDR/物理玻璃/VSM 软阴影/AgX 色调映射/滚动拆解动画/细节取景）
4. OneSDK MQTT topic 规约（知识库 fact `onesdk-mqtt-connection`：订阅 `Xp/Msg/Push/+deviceId` 与 `Xmart/Msg/User/uid`）

知识库来源核验：上述 fact 引用 `SRC-2026-000044-e71d`（OneSDK 架构设计文档 Part 1，V0.14.0/baseline V3.1），标题与版本匹配 ✓。
