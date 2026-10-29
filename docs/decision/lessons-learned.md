# 踩坑记录

> 实际遇到过的、非直觉的技术坑。修改涉及区域前先阅读，避免重复踩坑。

## 1. GLB 部件命名用数字 side code，不用字母

**现象**：车门、车窗的 3D 模型不动，但后备箱、前舱盖、天窗正常。命令日志显示 Rust 正确执行，前端 `state.doors.fl.angle` 已更新到 1.0，但 3D 部件不响应。

**根因**：GLB 模型中部件 `name` 字段使用数字表示侧别，但数字的含义与直觉相反：

| GLB name | side | 含义 | signal id |
|---|---|---|---|
| `door_1_0` | -1 | 左前门 | `door.fl` |
| `door_-1_0` | 1 | 右前门 | `door.fr` |
| `door_1_1` | -1 | 左后门 | `door.rl` |
| `door_-1_1` | 1 | 右后门 | `door.rr` |
| `window_1_0` | -1 | 左前窗 | `window.fl` |
| `window_-1_0` | 1 | 右前窗 | `window.fr` |
| `bonnet_strut_1` | — | 左撑杆 | `hood.strut.l` |
| `tailgate_strut_1` | — | 左尾门撑杆 | `tailgate.strut.l` |

**关键陷阱**：name 里的数字 `1` 对应 side=-1（左），`-1` 对应 side=1（右）——数字和 side 字段是反的。door 和 window 的命名规则一致，但直觉上 `door_-1_0` 看起来像"左"，实际是"右"。

最初 `AURA_T6_MAPPING` 里 door 写反了（`door.fl`→`door_-1_0`=右前门），而 window 写对了（`window.fl`→`window_1_0`=左前窗），导致车门和车窗关联到不同侧的部件。

**为什么难发现**：映射不匹配时不会报错，只是 `glbToSignal` 查不到，`doorId` 为 `undefined`，部件静默不动。日志只记录命令成功，看不到映射失败。

**修复**：用 GLTF JSON 解析脚本核对 GLB 内所有节点的 `name` 和 `extras`，将映射改为实际名称。

**预防**：新增或修改 `AURA_T6_MAPPING` 时，用以下命令核对 GLB 实际节点名：

```python
python3 -c "
import struct, json
with open('public/models/aura-t6.glb', 'rb') as f:
    f.read(12)
    chunk_len = struct.unpack('<I', f.read(4))[0]
    f.read(4)
    gltf = json.loads(f.read(chunk_len))
    for node in gltf.get('nodes', []):
        extras = node.get('extras', {})
        if extras.get('motion') in ('door','window','hood','tailgate','sunroof','hood_strut','tailgate_strut'):
            print(f'{node[\"name\"]:30s} motion={extras[\"motion\"]:15s} side={extras.get(\"side\")}')
"
```

## 2. serde 内部标签模式 + Option + JSON null = 反序列化失败

**现象**：`ToggleLock`、`ToggleHood`、`SetSunroof`、`Tailgate`（无 `Option` 字段）能工作，但 `ToggleDoor`、`SetWindow`（有 `Option<String>` 字段）的 Tauri invoke 抛异常。

**根因**：Rust serde 的 `#[serde(tag = "type")]` 内部标签模式（internally tagged enum）下，`Option<T>` 字段收到 JSON `null` 会反序列化失败。前端发 `{ type: 'toggle_door', id: null }` 时，serde 无法将 `null` 匹配到 `Option<String>`。

**修复**：给 `Option<T>` 字段加 `#[serde(default)]`：

```rust
ToggleDoor {
    #[serde(default)]
    id: Option<String>,
},
SetWindow {
    #[serde(default)]
    id: Option<String>,
    target: f32,
},
```

`#[serde(default)]` 让 serde 在遇到 `null` 或缺失字段时使用 `Option::default()`（即 `None`）。

**预防**：在 `#[serde(tag = "type")]` 枚举中新增 `Option<T>` 字段时，必须加 `#[serde(default)]`。添加 serde 反序列化测试覆盖 `null` 和缺失两种情况。

## 3. 不要永久缓存 Tauri 可用性

**现象**：修好 serde 问题后，命令仍然不工作。诊断标签显示 `L toggle_door`（走了本地回退）而不是 `✓ toggle_door`。

**根因**：之前的设计中，第一次 Tauri invoke 失败（因为 serde bug）后设置 `tauriFailed = true`，后续所有命令都跳过 Tauri 走本地回退。而本地回退修改 `state` 后，帧循环里的 `followSnapshot(state, latestSnapshot, dt)` 每帧用后端快照覆盖，本地修改被冲掉——表现为"没反应"。

**修复**：
- 去掉 `tauriFailed` 永久标记
- 每次调用 `sendCommand` 时独立检查 `tauriAvailable()`（运行时检查 `window.__TAURI__`）
- invoke 失败只影响当前调用，不影响后续

**预防**：永远不要因为一次失败就永久禁用某条路径。用 per-call error handling，每次独立尝试。模块加载时的 `isTauri` 常量也不可靠——HMR 热更新后 `window.__TAURI__` 可能延迟注入。
