# 决策 08 实现进度

> 对应 `docs/decision/08-vehicle-lifecycle-and-ui.md`

## 阶段一：Rust 后端基础

- [x] 1.1 `state.rs` — 添加 `PowerState` 枚举 + `power_state` 字段 + `driving` 字段
- [x] 1.2 `command.rs` — 添加 `SetPower { state: PowerState }` 命令
- [x] 1.3 `interlock.rs` — 添加电源状态 interlock（熄火时检查行驶状态）+ 高压命令判断
- [x] 1.4 `model.rs` — `tick()` 按电源状态门控；`apply_command()` 按电源状态拒绝/允许
- [x] 1.5 `cargo build` + `cargo test` 通过（39/39）

## 阶段二：Profile 模块

- [x] 2.1 `profile/mod.rs` — Template + Instance 结构体 + 加载/列表/创建/删除逻辑
- [x] 2.2 `profiles/templates/aura-t6.toml` — 内置 AURA T6 模板
- [x] 2.3 `profiles/instances/` 目录 + `.gitkeep`
- [x] 2.4 `lib.rs` — 注册 profile 模块 + 6 个 Tauri 命令
- [x] 2.5 `cargo build` + `cargo test` 通过（45/45）

## 阶段三：前端页面架构

- [x] 3.1 `index.html` — 三页 tab 导航 + header 电源控件 + 连接状态分组 + 车库页占位
- [x] 3.2 `main.js` — 页面路由 + 电源状态同步 + `sendCommand` 支持 `set_power` + 控制面板灰显
- [x] 3.3 `state.js` — `powerState`/`driving` 字段 + 电源状态感知的 `applyLocalCommand` + `set_power` 命令
- [x] 3.4 `style.css` — 页面切换样式 + 电源状态样式 + 车库页样式 + 控制面板灰显
- [x] 3.5 `npm test` + `npm run build` 通过（58/58 + 39/39）

## 阶段四：车库页面

- [x] 4.1 车辆实例列表渲染（卡片网格 + 空状态）
- [x] 4.2 创建实例流程（选模板 → 填 VIN/名称 → 保存）
- [x] 4.3 记住上次选择（启动加载 last-instance + 选择实例时保存）
- [x] 4.4 双模式支持（Tauri invoke + localStorage 浏览器回退）
- [x] 4.5 `npm test` + `npm run build` + `cargo test` 通过（58/58 + 45/45）

## 阶段五：电源状态 UI

- [x] 5.1 header 电源控件（状态显示 + 上电/熄火按钮）
- [x] 5.2 控制面板按电源状态灰显（Sleep 全禁用、Standby 高压禁用、Ready 全解锁）
- [x] 5.3 连接状态分组（MQTT/BLE 指示灯占位 + BLE 开关占位 + 文件传输状态占位）

## 待定项（不在此轮实现）

- MQTT 实际连接（决策 02，等知识库）
- BLE 实际广播（决策 01/04，等知识库）
- BLE 鉴权后可操作范围（等知识库）
- 寻车信号
- 运行时状态持久化
