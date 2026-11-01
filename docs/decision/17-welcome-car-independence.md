# 决策 17 — 欢迎页与爱车页 3D 状态独立

> 编号：17
> 关联：决策 08（D8.7 三页面架构、D8.8 欢迎页 vs 爱车页）

## 背景

决策 08 定义了「欢迎 / 爱车 / 车库」三页面架构，并明确欢迎页为展厅模式（3D 展示 + 滚动拆解 + 细节查看 + 颜色，无控制面板、无后台服务），爱车页为用车模式（3D + 控制面板 + 后台 SignalModel）。D8.7 还提到「切页时重建场景」。

实际实现中三页共享同一个 `state`、`vehicle`、`camera` 以及 `view`/`manualCamera`/`scrollProgress`/`exploring`/`layer` 等闭包变量，没有任何隔离：

- 在爱车页开车门、拖动相机、滚动拆解后切到欢迎页，车门开度、相机视角、拆解进度全部串了过去；
- 默认进入的是爱车页，而非欢迎页，与「首次进入即展厅」的预期不符。

用户反馈两点：①首次进入应是欢迎页；②欢迎页与爱车页的 3D 状态需独立，不能互相影响。

## 选项

### A. 切页重建场景

按 D8.7 字面「切页时重建场景」，每次切页销毁并重建 vehicle / camera / 控制状态。

- 优点：彻底隔离。
- 缺点：重建 GLB 加载与场景组装成本高，切页有明显卡顿；与 AGENTS.md「复用同一模型、canvas、renderer 与动画循环，避免创建重复场景或循环」的约定冲突。否决。

### B. 共享模型，按页隔离渲染状态与相机参数（采用）

保留单一 canvas / renderer / vehicle / camera / 动画循环，新增「按页区分」的状态层：

1. **信号状态独立**：新增 `displayState = createMirror()` 作为欢迎页的展厅中性状态（车门/窗/机盖/天窗/尾门全关、未充电、灯默认）。渲染时按当前页选择 `renderState()`：欢迎页用 `displayState`，爱车页用 `state`（仍由后端 tick / 用户控制驱动）。`displayState` 永不随用户操作或后端快照变化。
2. **相机/视图参数独立**：为 `view`/`manualCamera`/`scrollProgress`/`progress`/`exploring`/`wasExploring`/`horizontalShift`/`layer` 维护 per-page 槽位 `pageCam.welcome` / `pageCam.car`；切页时先把当前活跃变量快照回离开页的槽位，再载入目标页的槽位。
3. **写入拦截**：欢迎页为只读展厅，`sendCommand` 在欢迎页直接拦截并提示「展厅模式，请到爱车页操作」，确保爱车页的 `state` 不被欢迎页操作污染。
4. **颜色共享**：车身颜色由 `vehicle.setColor` 全局生效，两页同步，不隔离。

### C. 仅隔离相机，信号状态共享

只把相机/视图参数 per-page 化，车门等信号姿态仍共用 `state`。

- 优点：改动最小。
- 缺点：欢迎页会显示爱车页的车门开度，未满足「完全独立」。否决。

## 结论

采用 B：

- 默认页改为欢迎页（`index.html` body `data-page="welcome"`，导航 active 移至「欢迎」）。
- 新增 `displayState` + `renderState()`，欢迎页所有 `vehicle.update` / inspection / driving 的 `getState` / entrance 的渲染均走 `renderState()`。
- `switchPage` dispatch `app:page-switch` 事件，`startScene` 内监听并执行 `pageCam` 的存取。
- 颜色保持共享。

**两页定位（D8.8 修订）**：

- **欢迎页 = 展车页（可立即试驾）**：`displayState` 初始化为 `locked:false, powerState:'ready'`，进入即解锁 + 上电，可直接起步行驶、开空调等。`sendCommand` 在欢迎页操作本地 `displayState`（不走后端），保留门/盖/尾门/充电枪起步联锁。切到欢迎页时 `ensureDisplayReady()` 重置为解锁 + Ready。
- **爱车页 = 真实用车模拟**：默认锁定 + Standby（后端 `SignalModel` 默认值），用户需手动解锁（自动进入 Ready）才能操作高压功能。`sendCommand` 在爱车页走后端命令，`state` 由后端 tick 驱动。
- 起步联锁（车门/机盖/尾门未关拢、充电枪连接禁止起步）两页都保留不放松。
- 修复 `driving.js` 起步失败时写死「请先关好车门…」覆盖真实错误的问题，改为透出 `sendCommand`/`applyLocalCommand` 的真实原因。

## 欢迎页开场动画调整（出场停稳后保持可起步）

- **出场停稳后不熄火锁车关灯**：`entrance.onComplete` 在欢迎页直接 return，不调用 `shutdownAfterEntrance`。爱车页保留原有 shutdown（关灯→锁车→熄火）。这样欢迎页车停后保持解锁 + Ready，可直接起步；解决了「停稳后无法起步」（因 shutdown 把 displayState 改成 locked+sleep 导致）。
- **尾灯近赏聚焦车标 logo 特写（压缩）**：镜头落到车尾后，从车尾 logo 正中（车标 (2.35,0.96,0)）拉近特写。相机关键帧在 0.34~0.42 段正对 logo，dist≈1.9。logo 特写段压缩到 animTime 0.30~0.42（原 0.50）。
- **子弹时间快-慢-从容**：logo 近赏段用慢动作播放。`animTimeFor(elapsed)` 时间重映射（在 `update` 层，不改 `entrancePose` 位姿曲线）：真实 [0,1.5)→快驶近、[1.5,4.0)→logo 段慢（压缩）、[4.0,10.0)→从容恢复。总真实时长 `BULLET_DURATION=10s`。
- **logo 后顺时针弧线到车头特写再回 home**：logo 特写后（0.42~0.82）相机逐步拉远，沿顺时针弧线从车尾→左侧→右侧→车头，结束在车头特写（camL.x<-4, tgtL.x<-1）。之后 0.82~1.0 平滑回到最终整车视角（home）。测试检查点更新：logo 用 t=0.40、车侧用 t=0.58（|z|>3，左侧弧）、车头 t=0.82。
- **Blender 视频同步**：`scripts/export_entrance_poses.mjs` 按 BULLET_DURATION 真实时间采样（含子弹时间重映射），Blender 渲染的 mp4 与应用内一致。

## 影响

- **欢迎页**：展车，解锁 + 上电就绪，可直接试驾、滚动拆解、颜色、细节查看。操作走本地 `displayState`，不影响爱车页。
- **爱车页**：真实用车模拟，默认锁定 + Standby，需手动解锁上电。`state` 由后端驱动。
- **两页完全独立**：欢迎页的 driving 状态走本地 `displayState`，爱车页走后端 `state`，互不串扰。在爱车页开车门、拖相机、滚动拆解后切到欢迎页，看到的是就绪展车；切回爱车页恢复各自相机/视图；车身颜色两页一致。
- 复用现有 canvas / vehicle / camera / 循环，不重建场景，切页无额外加载开销。
- `pageCam` 仅在 `startScene` 闭包内维护，不影响其它模块；inspection / driving 通过已有的 `getState` 回调自动按页取状态，无需改其内部。
