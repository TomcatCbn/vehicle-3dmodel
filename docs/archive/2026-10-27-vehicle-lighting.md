# 车辆灯光分支合入审查

审查日期：2026-10-27。对象为 `origin/feature/vehicle-lighting` 的固定提交 `41d2bf97bdadcae3a5f61bc79574c60da1245fe7`，合入前主线为 `6e1c1ef7f2626810edd86ddf02a1094785dabdc1`，共同基点为 `0a5edc6d127e353421382bef2d378e076114626e`。

依据仓库 `AGENTS.md`、`README.md` 和 `docs/superpowers/specs/2026-10-25-vehicle-lighting-design.md`，分别检查规范与需求符合性。两个并行审查代理因额度限制未能运行，以下由主代理逐项审查，不构成独立双人批准。

## Standards

发现并修复 1 项整合问题，无未解决的阻塞项。

- **[P2，已修复] 灯光锚点回归写死旧车身坐标。** `tests/model-asset.test.js` 的新用例保存了分支旧车身的绝对位置；与主线最新曲面一起重建时，灯具前后位置相差约 1.3 毫米，导致完整测试失败。依据 `AGENTS.md` 中“相邻车身面、灯具和饰件优先共用曲面”和“不能仅为消除失败而放宽断言”的约定，改为检查锚点相对当前灯组的设计偏移；仍要求左右各一个锚点、正确父级和 `1e-4` 米的误差上限。

冲突处理保留主线最新后视镜、轮舱内衬、把手暗色握槽和前后黑底白字车型牌；将新的灯光角色、锚点与倒车灯合入生成脚本后，重新生成 Blender 和 GLB。保留 99 个独立总成以及原有元数据接口。未引入新依赖、第二个画布或动画循环，未修改已认可的徽标轮廓。

## Spec

未发现未解决的需求缺失或超出设计范围的行为。

- 近光、远光和关闭分别控制透镜、灯带及两盏投射灯；远光保留近光。尾灯独立切换。
- 制动灯随实际行驶中的减速请求点亮，停稳后熄灭；倒车灯随实际负向速度点亮。普通尾灯关闭不影响两者。
- 氛围灯支持关闭、暖白、冰蓝和紫色，充电指示独立于车灯开关。
- 设计明确包含低速倒车：前进限速 100 km/h，倒车限速 20 km/h，运动中禁止换向；退出后重新进入恢复前进与零行程。
- 车辆状态、车控联锁、细节隔离与开合、拆解复位继续使用原有实现。

## 验证证据

- 共享曲面、VW 字形 Python 自检通过。
- 使用合并后的生成脚本重建 `models/aura-t6.blend`、`public/models/aura-t6.glb` 与清单后，完整 Node 测试 56/56 通过，生产构建通过。
- 查看同源 Cycles 的后侧与主灯渲染：`output/playwright/aura-t6-detail-rear-quarter.png`、`aura-t6-detail-lamp.png`。Cycles 用于核对几何与材质，运行时开关状态以浏览器验证为准。
- 在 1280×900 和 390×844 浏览器视口核对灯光控件、氛围灯预设、充电与灯光的独立性、复位、前进与倒车、移动时换向禁用、停车减速、细节缩放与隔离恢复、尾门开合、拆解至 100% 后复位。确认只有一个 canvas，应用错误日志为空。
- 页面截图：`output/playwright/aura-lighting-high.png`、`aura-lighting-off.png`、`aura-lighting-reverse.png`、`aura-lighting-brake.png`、`aura-lighting-mobile-controls.png`、`aura-lighting-mobile-drive.png`、`aura-lighting-tailgate-open.png`、`aura-lighting-exploded.png`、`aura-lighting-assembled.png`。临时视口设置已恢复。

## 精度与验证边界

灯具分工、倒车灯位置及座舱氛围灯为交互示意，未核实原厂配光或硬件配置；灯光不投射动态阴影。仅完成浏览器视口验证，未做实体手机性能、触控或 MQTT/BLE 联调。构建仍有现有的 JavaScript 分块大于 500 kB 提示。
