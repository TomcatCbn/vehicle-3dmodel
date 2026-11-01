# 决策 6：车机大屏文件传输（CEA2.x 协议 · 车端实现）

- **状态**：已定（架构方案层面；具体实现分阶段推进）
- **决策日期**：2026-10-29
- **决策者**：用户
- **影响范围**：Rust 后端新增 `file_transfer/` 模块；前端新增文件传输 UI；Cargo.toml 新增依赖
- **协议来源**：`~/Downloads/file-transfer-2x-review.html`（CEA2.x 文件传输 SDK 联合研发评审稿，2026-10-26，SDK 提议·待联合确认）

## 背景

M1（车信号模拟器骨架）和 M2（inspection/driving 路由改造）已完成。模拟器已具备完整的 3D 车控能力：Tauri 2.0 + Rust 后端 SignalModel 管理车锁/车门/车窗/灯光/充电等信号状态，前端通过 `sendCommand` → Tauri invoke → 后端 tick → `followSnapshot` 双值插值驱动 3D 渲染。

M3 进入文件传输领域：模拟器（扮演车机）通过 Wi-Fi 直连向手机推送文件。方向为**车→手机**，传输通道为 **Wi-Fi 局域网直连**（模拟器和手机在同一局域网），协议对齐 CEA2.x 文件传输 SDK。

CEA2.x 协议是一套完整的端到端文件传输方案，包含 QR 扫码授权、TLS 1.3 加密通道、会话鉴权、文件列表、分批下载、暂停/恢复/取消、车端通知等机制。本决策确定模拟器（车端）的架构方案和实现路径。

## 协议概要

### 完整流程

```
车端生成 QR ──→ 手机扫码（获得 Server IP:Port + 文件预览 + certSha256 + shareSecret）
                                              │
                    手机连入同一局域网 Wi-Fi    │
                                              ▼
                    TLS 1.3 握手（手机校验 certSha256 == QR 中的指纹）
                                              │
                    campability（shareId + shareSecret → sessionId）── shareSecret 一次性消费
                                              │
                    list（sessionId → 1-9 个文件列表，含 fileId/status）
                                              │
                    App 勾选文件 → download（每文件独立 TLS 数据连接）
                                              │
                    暂停 / 恢复 / 取消（单文件粒度）
                                              │
                    finishShare（结束分享，取消未完成项，清理）
```

### 报文分帧

| 帧类型 | 格式 | 大小约束 |
|--------|------|----------|
| **控制帧** | 4B uint32 BE 长度头 + JSON 正文 | JSON 1-4096B，无 BOM |
| **数据帧（手机→车）** | 2B uint16 BE（值=43）+ 43B ASCII token | 共 45B |
| **数据帧（车→手机）** | contentLength 字节原始文件正文 | 无协议头 |

### 控制报文 Action 清单

| Action | 方向 | 请求参数 | 响应参数 |
|--------|------|----------|----------|
| campability | phone→vehicle | shareId, shareSecret | sessionId, limits |
| list | phone→vehicle | sessionId | files[] (fileId/name/size/kind/status) |
| download | phone→vehicle | sessionId, fileId, token, filePath, offset | dataPort, size, acceptedOffset, contentLength |
| pause | phone→vehicle | sessionId, fileId, token | pausedOffset |
| resume | phone→vehicle | sessionId, fileId, token, offset | acceptedOffset |
| cancel | phone→vehicle | sessionId, fileId, filePath, token | state: cancelled |
| stop | phone→vehicle | sessionId, scope: share, reason | — |

### 车端通知（Notification，单向不等 ACK）

| Code | 含义 | Info |
|------|------|------|
| 1001 | 资源状态变更 | sessionId, fileId, 新状态 |
| 1002 | session 失效 | sessionId |
| -2001 | 文件错误 | sessionId, fileId, token |

### 端口与并发

- 控制端口：19890（默认）
- 数据端口：19891-19895（可复用同一端口接受多连接，同一 TCP 连接不传多个文件）
- 并发默认 2 文件，可配 1
- QR ≤2048 UTF-8 字节，list Response ≤4096B

### TLS 安全约束

- TLS 1.3 only，禁 0-RTT，禁 session resumption
- 证书通过 QR 中 `certSha256` 带外校验（不走 CA 信任链）
- 控制报文 `Security={}`，TLS 提供加密与完整性，不另加自定义 AES 层
- shareSecret 一次性消费，campability 后失效
- QR.Security.mode = "tls13-qr-v1"

### QR 结构（≤2048B）

```json
{
  "OEM": "svw",
  "WIFI": "T:SAE;S:example-hotspot;P:<password>;;",
  "Server": { "IPv4": "192.0.2.10", "Port": 19890 },
  "App": "com.example.jv.share",
  "Files": [
    { "FileName": "图片001.jpg", "Path": "/share/image-001.jpg", "Size": 65536 }
  ],
  "ShareId": "11111111-1111-4111-8111-111111111111",
  "EndTime": 1792569690,
  "Security": {
    "mode": "tls13-qr-v1",
    "certSha256": "aaaa...64hex",
    "shareSecret": "VVVV...43chars"
  }
}
```

### 会话与文件状态机

```
分享(Share)：PENDING → CLAIMED → EXPIRED
会话(Session)：READY → DOWNLOADING → CLOSING → CLOSED
文件(File)：WAITING → DOWNLOADING ↔ PAUSED → COMPLETED / FAILED / CANCELLED
```

### StatusCode 错误码

| Code | 含义 | Code | 含义 |
|------|------|------|------|
| 0 | OK | 1/2 | OEM_MISMATCH / VERSION_UNSUPPORTED |
| 100 | INVALID_ARGUMENT | 101 | SHARE_EXPIRED |
| 102 | FILE_MISSING | 103 | RESOURCE_CHANGED |
| 104 | INVALID_TOKEN | 105 | INVALID_STATE |
| 106 | OFFSET_MISMATCH | 107 | BUSY |
| 108 | METADATA_TOO_LARGE | 109 | INTERNAL_ERROR |
| 110 | AUTH_FAILED | — | 失败 Parameter={message, retryable} |

## 核心决策

### D6.1 传输模式：局域网直连（不做热点管理）

**决策**：模拟器只监听 TCP 端口，手机和模拟器在同一局域网（同一 Wi-Fi 或手机开热点电脑连上），QR 里填模拟器本机 IP，模拟器不管理热点。

**理由**：
- macOS/Windows 自动创建 Wi-Fi 热点需要系统级权限（`networksetup`/`netsh`），跨平台差异大且不稳定
- 测试场景下，开发者和手机在同一 Wi-Fi 即可，热点是真实车辆的部署细节
- 真实车辆场景中车端开热点，模拟器用局域网替代，协议层面完全一致

**IP 发现**：
- Rust 后端启动时枚举网络接口，找到非回环的 IPv4 地址
- 多个网卡时取第一个或由用户在配置中指定
- QR 的 `Server.IPv4` 填入检测到的局域网 IP

**与协议的差异**：QR 中 `WIFI` 字段在真实车辆包含热点 SSID/密码，模拟器局域网模式下该字段可填占位值或省略（手机已连同一网络）。`Server.IPv4` 和 `Server.Port` 是手机实际连接用的地址。

### D6.2 TLS 证书：固定预置测试证书

**决策**：使用固定预置的自签证书（PEM 文件），随仓库分发，每次启动指纹不变，方便调试。

**方案**：
- 用 `rcgen` 或 `openssl` CLI 预先生成一对自签证书和私钥
- 证书文件存放于 `src-tauri/certs/test-cert.pem` 和 `src-tauri/certs/test-key.pem`
- 证书 SAN 包含 `127.0.0.1` 和常见局域网 IP（或使用 IP SAN 通配）
- 启动时加载 PEM 文件，计算 DER 编码的 SHA-256 指纹，填入 QR 的 `certSha256`
- 运行时不做证书生成或轮换

**理由**：
- 调试时指纹不变，QR 内容稳定，便于复现问题
- 避免 `rcgen` 作为运行时依赖（仅开发时用一次）
- 真实车辆会运行时生成证书，模拟器简化为固定证书不影响协议验证

**安全声明**：测试证书仅用于模拟器联调，不用于任何生产环境。私钥提交到仓库仅因这是测试工具，不是生产系统。

### D6.3 模块独立性：与 SignalModel 完全解耦

**决策**：文件传输作为独立功能域，不与现有 `signal/` 模块耦合。

**关系边界**：

| 维度 | SignalModel（车控） | FileTransfer（文件传输） |
|------|---------------------|--------------------------|
| 状态 | 车锁/门/窗/灯/充电等 | 分享/会话/文件下载状态 |
| 触发 | UI 按钮 / MQTT / BLE | 扫码 / 手机 App 请求 |
| tick 循环 | 30Hz 推进平滑位置 | 无（事件驱动） |
| Tauri 命令 | send_vehicle_command / get_vehicle_state | start_share / get_qr / list_files / ... |
| 事件 | signal://state-changed | filetransfer://share-started 等 |
| 共享 | 仅共享日志基础设施（debug_log） | 同左 |

**唯一可能的交互**：未来车控指令触发文件导出（如"导出日志"），但这通过独立的 Tauri 命令桥接，不经过 SignalModel 的 tick 循环。

**理由**：
- 文件传输与车控信号在协议层、状态层、时序层完全正交
- 耦合会增加 SignalModel 复杂度，违反"状态集中在 state.js"的单一职责原则
- 独立模块可以单独测试、单独演进

### D6.4 QR 渲染：Rust 生成 JSON + 前端渲染 QR 图

**决策**：Rust 后端生成 QR JSON 字符串（≤2048B），通过 Tauri 命令传给前端，前端负责 QR 码图片渲染。

**理由**：
- QR 内容是协议数据（JSON），应在后端生成和校验
- QR 图片渲染是纯展示逻辑，前端有成熟的轻量库（如 `qrcode-generator` ~5KB）
- 避免在 Rust 侧引入 QR 图片生成依赖（`qrcode` crate 虽轻量，但图片渲染在前端更灵活——可调整尺寸、颜色、叠加 logo）

### D6.5 Tauri-only 限制

**决策**：文件传输功能仅在 Tauri 模式下可用，浏览器模式（`npm run dev`）下显示"需要 Tauri 环境"提示。

**理由**：
- TLS 1.3 服务端、TCP 监听、文件系统访问均依赖原生能力，浏览器无法提供
- 与 SignalModel 不同（后者有 `applyLocalCommand` 本地回退），文件传输没有浏览器回退路径
- 前端 UI 可以展示 QR 和文件列表（只读），但服务端启动必须依赖 Tauri

## 模块划分

```
src-tauri/src/
├── signal/              # 现有车控信号模型（不变）
├── file_transfer/       # 新增：文件传输功能域
│   ├── mod.rs           # 模块入口，Tauri 命令注册，服务启动/停止
│   ├── config.rs        # 配置：端口、证书路径、文件目录、OEM、并发数
│   ├── qr.rs            # QR JSON 生成与字节校验（≤2048B）
│   ├── tls.rs           # TLS 1.3 服务端：证书加载 + 指纹计算 + 监听器
│   ├── control.rs       # 控制通道：4B 分帧读写 + 报文分发 + Action 处理 + Notification 发送
│   ├── data.rs          # 数据通道：token 验证 + 文件正文流式发送
│   ├── session.rs       # 会话状态机：Share → Session → File 状态
│   ├── message.rs       # 报文结构体（envelope + 各 Action 的 Parameter 类型）
│   └── files.rs         # 文件管理：扫描目录、元数据、可下载状态
├── lib.rs               # 注册 file_transfer 模块和命令
└── main.rs              # 不变
```

### 各模块职责

#### `mod.rs` — 模块入口

- 注册 Tauri 命令：`ft_start_share`、`ft_get_qr`、`ft_stop_share`、`ft_list_files`、`ft_get_status`
- 管理 `FileTransferService` 生命周期（启动/停止 TLS 监听器）
- 通过 Tauri 事件向前端推送状态变更

#### `config.rs` — 配置

```rust
struct FtConfig {
    control_port: u16,       // 默认 19890
    data_port: u16,          // 默认 19891
    cert_path: PathBuf,      // certs/test-cert.pem
    key_path: PathBuf,       // certs/test-key.pem
    file_dir: PathBuf,       // 可分享文件目录
    oem: String,             // "svw"
    max_parallel: u8,        // 默认 2
    share_timeout_secs: u64, // 默认 90（QR EndTime）
}
```

#### `qr.rs` — QR 生成

- 生成 QR JSON：OEM / Server{IP,Port} / Files[] / ShareId / EndTime / Security{mode, certSha256, shareSecret}
- 字节校验：序列化后 UTF-8 字节数 ≤2048
- shareSecret 生成：32 字节随机 → Base64URL 无填充 → 43 字符

#### `tls.rs` — TLS 服务端

- 加载 PEM 证书和私钥
- 计算 DER 证书的 SHA-256 指纹（用于 QR certSha256）
- 创建 `tokio-rustls` TLS 1.3 监听器（控制端口 + 数据端口）
- TLS 配置：仅 TLS 1.3，禁 0-RTT，禁 session resumption

#### `control.rs` — 控制通道

- **帧读写**：读 4B uint32 BE → 读 N B JSON；写 4B + JSON
- **报文分发**：解析 envelope 的 Type（Request/Response/Notification）→ 路由到 handler
- **Action 处理**：
  - campability：校验 shareSecret → 消费 → 创建 session → 返回 sessionId + limits
  - list：返回文件列表（fileId/name/size/kind/status）
  - download：生成 token → 绑定数据连接 → 返回 dataPort/contentLength/token
  - pause/resume/cancel：操作单文件状态
  - stop：结束分享，取消未完成项
- **Notification 发送**：1001（资源变更）/ 1002（session 失效）/ -2001（文件错误）

#### `data.rs` — 数据通道

- 读 2B uint16 BE（值=43）→ 读 43B ASCII token
- 校验 token 归属（session + file + offset）
- 从文件 offset 位置流式发送 contentLength 字节
- 发送完毕不自动关闭 socket（由控制通道 cancel/stop 触发）

#### `session.rs` — 会话状态机

```rust
struct Share {
    share_id: Uuid,
    share_secret: String,    // campability 后置 None
    end_time: i64,           // UTC 秒
    files: Vec<FileInfo>,
    status: ShareStatus,     // Pending / Claimed / Expired
}

struct Session {
    session_id: Uuid,
    share_id: Uuid,
    files: HashMap<FileId, FileDownloadState>,
    status: SessionStatus,   // Ready / Downloading / Closing / Closed
}

struct FileDownloadState {
    file_id: String,
    token: Option<String>,
    offset: u64,
    status: FileStatus,      // Waiting / Downloading / Paused / Completed / Failed / Cancelled
}
```

#### `message.rs` — 报文结构体

- 通用 envelope：ver / Type / ID / From / Direction / Security / Priority / TimeStamp / Action / Parameter
- Request 变体：campability / list / download / pause / resume / cancel / stop
- Response：StatusCode + Parameter（成功或 {message, retryable}）
- Notification：Code + Info

#### `files.rs` — 文件管理

- 扫描配置目录，生成文件元数据（fileId/name/size/kind）
- 可下载状态检查：文件存在、可读、大小匹配
- fileId 生成：`f-0001` 到 `f-0009`（对应 QR Files 数组索引）

## 前端 UI

文件传输 UI 作为独立面板，与车控控制面板并列：

```
┌─────────────────────────────────┐
│  文件传输                        │
│  ┌───────────────────────────┐  │
│  │  [QR 码图片]               │  │
│  │  等待手机扫码...           │  │
│  │  ShareId: xxx-xxx          │  │
│  │  剩余时间: 75s             │  │
│  └───────────────────────────┘  │
│  可分享文件:                     │
│  • 图片001.jpg (64KB)           │
│  • 视频001.mp4 (2MB)            │
│  [开始分享] [停止分享]           │
│  传输状态:                       │
│  • 图片001.jpg: 45% 传输中       │
│  • 视频001.mp4: 等待中          │
└─────────────────────────────────┘
```

前端通过 Tauri 事件接收状态推送：
- `filetransfer://share-started` — 分享开始
- `filetransfer://qr-ready` — QR 已生成
- `filetransfer://session-created` — 手机已鉴权
- `filetransfer://download-progress` — 下载进度
- `filetransfer://share-closed` — 分享结束

## 新增依赖

```toml
[dependencies]
# 新增
tokio-rustls = "0.26"       # TLS 1.3 异步服务端
rustls-pemfile = "2"        # PEM 文件加载
sha2 = "0.10"               # 证书 SHA-256 指纹
uuid = { version = "1", features = ["v4"] }  # sessionId / requestId 生成

[dev-dependencies]
rcgen = "0.13"              # 仅开发时生成测试证书（一次性）
```

不引入：
- `axum` / `hyper` — 协议是原始 TLS + 自定义分帧，不是 HTTP
- `rumqttc` — 文件传输不走 MQTT
- 前端 QR 库 — 使用轻量 JS 库，通过 npm 安装（非 Rust 依赖）

## 与现有系统的关系

```
┌─────────────────────── Tauri App ───────────────────────┐
│                                                         │
│  ┌──────────────┐          ┌──────────────────────┐    │
│  │  signal/     │          │  file_transfer/       │    │
│  │  SignalModel │          │  FileTransferService  │    │
│  │              │          │                       │    │
│  │  车控状态     │          │  分享/会话/文件状态    │    │
│  │  30Hz tick    │          │  事件驱动             │    │
│  │  ↓            │          │  ↓                    │    │
│  │  state-changed│          │  share-started 等     │    │
│  └──────┬───────┘          └──────────┬───────────┘    │
│         │                            │                  │
│         │  共享：debug_log / logs/    │                  │
│         │                            │                  │
│  ┌──────┴────────────────────────────┴──────────────┐  │
│  │              前端 (WebView)                        │  │
│  │  车控面板                文件传输面板              │  │
│  │  state.js (镜像)         file-transfer.js (新增)  │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

- **日志共享**：文件传输模块复用 `lib.rs` 的 `debug_log` 函数，写入同一日志文件
- **前端独立**：新增 `src/file-transfer.js`，不修改 `src/state.js`；两个面板状态独立
- **lib.rs 注册**：新增 `mod file_transfer;` 和对应的 Tauri 命令注册
- **不影响现有测试**：文件传输模块的测试独立于 `signal/` 测试

## 分阶段实现路径

### M3.1 — TLS 骨架 + 控制通道 + 会话状态机

**目标**：手机能扫码 → TLS 握手 → campability → list → 看到文件列表 → stop

**交付物**：
- `file_transfer/` 模块骨架（mod / config / qr / tls / control / session / message / files）
- 固定测试证书（PEM 文件）
- TLS 1.3 控制端口监听
- campability / list / stop 处理器
- QR JSON 生成 + 前端 QR 展示
- 文件目录扫描 + 元数据
- 会话状态机（Share → Session）
- 本地 127.0.0.1 回环测试

**验证**：用 `openssl s_client` 或简单 TLS 客户端测试控制通道分帧和报文解析

### M3.2 — 数据通道 + 下载/暂停/恢复/取消

**目标**：手机能下载文件，支持暂停/恢复/取消

**交付物**：
- 数据端口 TLS 监听
- token 验证 + 文件正文流式发送
- download / pause / resume / cancel 处理器
- 文件级状态机（WAITING/DOWNLOADING/PAUSED/COMPLETED/FAILED/CANCELLED）
- 并发控制（默认 2 文件）
- 前端下载进度展示

**验证**：本地回环下载文件，验证内容完整性、暂停恢复后 offset 正确

### M3.3 — 通知 + 前端集成 + 局域网联调

**目标**：完整协议流程，局域网真机联调

**交付物**：
- Notification 发送（1001/1002/-2001）
- 超时处理（会话空闲 120s、数据无进展 30s、QR EndTime 90s）
- 前端完整 UI（QR 展示/隐藏、文件列表、进度、状态）
- 局域网 IP 自动检测
- Tauri 命令完整注册

**验证**：手机和电脑同一 Wi-Fi，扫码 → 下载文件 → 暂停/恢复 → 完成或取消 → 结束分享

### M3.4 — 边界与错误处理

**目标**：处理异常场景，提升健壮性

**交付物**：
- 错误码完整实现（StatusCode 0-110）
- 网络断开/超时回收
- QR 过期/失效处理
- 重复 campability 防护（BUSY）
- 文件不可用通知（FILE_MISSING / RESOURCE_CHANGED）
- 日志完善（不含 token/secret/私有路径）

## 待确认项

1. **OEM 标识**：QR 中 OEM 字段当前用 "svw"，需确认是否需要可配置
2. **WIFI 字段**：局域网模式下 QR 的 WIFI 字段如何填——占位值还是省略（需与手机端 SDK 确认是否校验此字段）
3. **文件类型**：协议支持 image/video，模拟器是否需要限制文件类型，还是允许任意文件
4. **证书 SAN**：固定测试证书的 IP SAN 需要包含哪些地址（127.0.0.1 + 常见 192.168.x.x？还是用通配？）——取决于手机端 TLS 是否做主机名校验
5. **错误码与通知字段**：协议文档标注"需车端确认"，当前按 SDK 提议实现，联调时可能调整
6. **App 包名**：QR 中 App 字段填什么——模拟器没有真实 App 包名
