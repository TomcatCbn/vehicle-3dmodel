# 决策 2：MQTT 接入架构方案

- **状态**：已定（架构方案层面；具体报文格式后续对齐）
- **决策日期**：2026-10-28
- **决策者**：用户
- **影响范围**：Rust 后端 MQTT 模块、车管注册流程、模拟器与后台的通信边界

## 背景

决策 1 已定技术栈为 Tauri 2.0（Rust 后端 + WebView 前端），MQTT 后台为现成真实系统。本决策确定模拟器如何接入该后台的架构方案，不展开具体报文格式（后续单独决策对齐 OneSDK 私有协议）。

## 核心链路

```
                                  ① HTTP 注册
                                  (POST /vehicle/register)
   ┌─────────────────┐ ───────────────────────────────→ ┌─────────────────┐
   │                 │                                   │                 │
   │   车模拟器      │ ←──────────────────────────────── │  车管后台       │
   │  (Rust 后端)    │       ② 返回 MQTT 连接参数         │                 │
   │                 │   (broker/deviceId/topic/凭证)     └─────────────────┘
   │                 │                                                         
   │                 │   ③ MQTT 连接                                             
   │                 │ ←───────────────────┐                                     
   │                 │                     │                                     
   └─────────────────┘                     ▼                                     
                          ┌─────────────────────────────┐                      
                          │     MQTT Broker (现成)      │                      
                          │   订阅 Xp/Msg/Push/+deviceId│                      
                          │   发布 状态/响应到对应 topic │                      
                          └─────────────────────────────┘                                     
                                       ↑                                     
                                       │ ④ 远控指令 / 状态推送                                     
                                       │                                     
                          ┌────────────┴────────────────┐                      
                          │      手机 App / OneSDK      │                      
                          └─────────────────────────────┘                      
```

## 架构方案

### 1. 角色定位

模拟器扮演**车端**角色，在车管后台注册为一辆真实车，获得与真实车相同的 MQTT 接入身份。

- **不是** MQTT broker——不替后台承载消息路由
- **不是** 协议网关——不翻译或代理手机与后台之间的消息
- **是** 车端 MQTT 客户端——订阅车端 topic 接收指令，发布车端状态/响应

### 2. 三阶段接入流程

**阶段 1：注册（HTTP，一次性）**

- Rust 后端启动时执行
- 调用车管后台注册接口，提交模拟器的车辆身份信息（VIN、车型标识、能力清单等）
- 后台校验通过后返回 MQTT 连接参数：broker 地址、端口、deviceId、订阅/发布 topic 模板、鉴权凭证（用户名/密码或证书）
- 凭证缓存到本地加密存储，下次启动可复用，避免重复注册

**阶段 2：连接（MQTT）**

- Rust 后端用 `rumqttc` 建立与 broker 的连接
- 使用注册返回的凭证完成鉴权
- 连接成功后按 topic 模板订阅车端推送 topic（对齐 OneSDK fact：`Xp/Msg/Push/+deviceId`）
- 注册 `on_message` 回调，进入指令处理循环
- 维持心跳与重连机制（`rumqttc` 内置 last will 与自动重连）

**阶段 3：双向通信**

- **下行（后台 → 模拟器）**：远控指令、配置下发、状态查询——Rust 后端解析报文，派发给信号模型执行
- **上行（模拟器 → 后台）**：状态变更、命令响应、事件上报——信号模型产出状态，Rust 后端打包报文发布到对应 topic

### 3. 模块边界（Rust 后端）

```
src-tauri/src/
├── registration/         # 车管注册
│   ├── mod.rs
│   ├── client.rs          # HTTP 客户端，调后台注册接口
│   └── credential.rs      # 凭证本地加密存储
├── mqtt/                  # MQTT 接入层
│   ├── mod.rs
│   ├── connection.rs      # rumqttc 连接管理、重连、心跳
│   ├── subscriber.rs      # 订阅管理、on_message 派发
│   ├── publisher.rs       # 发布管理
│   └── topic.rs           # topic 模板与路由
├── codec/                 # 报文编解码（待对齐 OneSDK 私有协议）
│   ├── mod.rs
│   ├── decoder.rs         # 下行报文解析
│   └── encoder.rs         # 上行报文打包
└── signal/                # 信号模型（决策 3 细化）
    └── mod.rs
```

### 4. 前后端通信

前端**不直接**连 MQTT，所有 MQTT 操作走 Rust 后端。

- **前端 → 后端**：Tauri commands
  - `register_vehicle(payload)`：触发注册
  - `get_connection_status()`：查询连接状态
  - `send_vehicle_command(cmd)`：发车控指令（本地发起，经后端走信号模型或直发 MQTT）
- **后端 → 前端**：Tauri events
  - `mqtt://status-changed`：连接状态变更
  - `mqtt://message-received`：收到指令（前端可选展示）
  - `signal://state-changed`：信号模型状态变更（前端驱动 3D 与 UI）
  - `signal://command-ack`：命令执行结果

### 5. 指令来源双通道

模拟器同时支持两种指令发起方式：

- **后台下发**（真实手机 App 或后台运维发起）→ MQTT → Rust 后端 → 信号模型 → 状态变更 → 前端 3D 响应
- **模拟器本地发起**（前端控制台操作）→ Tauri command → Rust 后端 → 信号模型 → 状态变更 → 前端 3D 响应

两条路径在**信号模型层汇合**——无论指令来自 MQTT 还是本地 UI，都先更新信号模型，再由信号模型统一产出状态变更事件。这保证状态唯一来源，避免前端直接改 state 与后台推送冲突。

本地发起的指令**可选是否回传后台**：
- 默认：本地执行 + 本地状态变更（不发布到 MQTT，避免后台收到模拟器自身操作的回环）
- 可配置：本地执行 + 发布状态到 MQTT（让真实手机 App 看到模拟器的状态变化）

### 6. 与 OneSDK 私有协议的对齐点（后续决策细化）

待对齐的具体项（本决策不展开，仅记录待办）：

- topic 模板规约（对齐 `Xp/Msg/Push/+deviceId` 与 `Xmart/Msg/User/uid`）
- 报文格式（TLV 结构、字段定义）
- 鉴权方式（xp 私有协议：XP-Encryption-Type / XP-Authorization / XP-Signature）
- 命令编码与接口编号空间（对齐 OneSDK Function 层接口前缀：TRIP-10001 等）
- 状态推送格式（VehicleState / DigitalVehicleState 模型）

对齐工作将基于知识库已核验的 fact：
- `onesdk-mqtt-connection`（topic 与重连）
- `onesdk-v1-auth-xp` / `onesdk-v1-auth-cea`（鉴权方案）
- `onesdk-vehicle-state-model`（状态数据模型）
- `onesdk-command-queue`（命令队列与延迟监听）
- `onesdk-cmd-select-channel`（通道选择策略）

## 关键设计决策

### D2.1 模拟器只做车端 MQTT 客户端，不做 broker

**选择**：模拟器作为 MQTT 客户端连真实后台 broker，不本地起 broker。
**理由**：后台是真实现成的，本地起 broker 会让模拟器与真实手机/后台隔离，失去联调价值。
**代价**：模拟器依赖后台可用性；后台不可用时模拟器无法独立运行。
**缓解**：本地发起的指令不依赖后台（直接走信号模型）；仅"后台下发指令"通道需要后台在线。

### D2.2 前端不直接连 MQTT

**选择**：所有 MQTT 操作走 Rust 后端，前端通过 Tauri commands/events 通信。
**理由**：
- MQTT 凭证不出后端（安全）
- 协议状态机、命令队列、延迟监听逻辑放后端更干净，前端专注可视化
- 避免前端 mqtt.js 与后端 rumqttc 维护两套 MQTT 逻辑
**代价**：前端不能直接订阅 topic，所有消息经后端中转。
**缓解**：后端通过 Tauri events 推送前端关心的消息，前端按需订阅事件。

### D2.3 信号模型作为状态唯一来源

**选择**：无论指令来自 MQTT 还是本地 UI，都先更新信号模型，再由信号模型产出状态变更事件。
**理由**：避免前端直接改 `state.js` 与后台推送冲突；保证状态唯一来源。
**代价**：现有 `state.js` 需重构为信号模型的本地视图，前端不能再直接改 state。
**缓解**：信号模型状态变更通过事件推回前端，前端 state 作为模型的镜像，3D 与 UI 仍按现有模式响应。

### D2.4 注册凭证本地缓存

**选择**：注册成功后凭证缓存到本地加密存储，下次启动复用。
**理由**：避免每次启动重复注册（后台可能有频率限制或审批流程）。
**代价**：凭证可能过期，需要处理重新注册逻辑。
**缓解**：MQTT 连接失败时检测凭证失效，自动触发重新注册。

## 待后续决策

- 决策 3：信号模型抽象（如何支持"模拟任何车"，schema 配置化方案）
- 决策 4：BLE 协议核心层 API（对齐 OneSDK BLE fact）
- 决策 5：3D 车控与信号模型如何对接（现有 `state.js` 重构路径）
- 决策 6（新增）：OneSDK 私有协议报文格式对齐细节

## 决策依据证据

本决策基于以下事实约束：

1. OneSDK MQTT topic 规约（知识库 fact `onesdk-mqtt-connection`）：订阅 `Xp/Msg/Push/+deviceId`（设备级）和 `Xmart/Msg/User/uid`（用户级），断开自动重连后重新订阅
2. OneSDK 命令队列与延迟监听（知识库 fact `onesdk-command-queue`）：offerCmd 入队、100ms 延迟监听、7s 超时判定失败
3. OneSDK 状态数据模型（知识库 fact `onesdk-vehicle-state-model`）：区分 VehicleState（原始）与 DigitalVehicleState（数字化），1.0 用 SP 缓存
4. OneSDK 控车通道选择（知识库 fact `onesdk-cmd-select-channel`）：5 种模式，BLE 优先/网络优先/混合

知识库来源核验：上述 fact 引用 `SRC-2026-000044-e71d`（OneSDK 架构设计文档 Part 1，V0.14.0/baseline V3.1），标题与版本匹配 ✓。
