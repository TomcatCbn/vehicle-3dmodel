# 项目协作指南

本文件适用于整个仓库。面向用户的说明、文档和界面文案默认使用简体中文；代码标识符沿用现有英文命名。

## 项目定位

- AXIS Vehicle Lab：基于大众 ID. AURA T6 照片近似重建的可交互三维车辆，支持车控、细节查看、滚动拆解和直线行驶演示。
- 技术栈为原生 JavaScript ES Modules、Three.js 和 Vite；测试使用 Node.js 内置 `node:test`，模型由 Blender Python 脚本生成。
- 当前仅有浏览器本地状态，刷新会复位，MQTT/BLE 尚未接入。不要将界面动作或动画描述为已完成真实协议联调。
- 外观为照片近似，座舱、底盘、货厢和开合机构包含示意结构，不能据此推断原厂工程尺寸、配置、光学或车辆动力学。

## 代码与资产入口

| 路径 | 职责 |
| --- | --- |
| `index.html`、`src/style.css` | 页面、控制台、细节和行驶弹窗、响应式样式 |
| `src/main.js` | 场景初始化、控件同步、滚动拆解、拾取和统一动画循环 |
| `src/state.js` | 车辆状态、目标与实际开度、充电和拆解插值 |
| `src/vehicle.js` | 读取 GLB 元数据，驱动部件运动、材质、颜色和高亮 |
| `src/inspection.js` | 细节部件选择、隔离、运动包络取景及相机恢复 |
| `src/drive-state.js`、`src/driving.js` | 行驶计算、起步条件、道路演示和行驶界面 |
| `src/studio.js` | 环境照明、阴影、反射和场景展示 |
| `scripts/aura_surface.py` | 共享车身曲面、接边及曲面自检，不依赖 Blender |
| `scripts/vw_emblem.py` | 共用 VW 字形轮廓和比例自检 |
| `scripts/build_aura_t6.py` | 生成独立部件、运动元数据、Blender 源文件和 GLB |
| `scripts/render_aura_t6.py` | 从同一 Blender 模型输出 Cycles 核对图 |
| `tests/` | 状态、行驶、细节取景及实际 GLB 回归测试 |
| `models/references/`、`docs/references/aura-t6.md` | 建模参考图、来源和准确性说明 |

先阅读 `README.md`。`docs/superpowers/plans/` 保存各轮改动计划；参考文档中的旧分件数量和旧验证记录属于历史，当前行为以代码和实际资产为准。

## 常用命令

需要 Node.js 20.19+ 或 22.12+。

```sh
npm install
npm run dev
npm test
npm run build
```

开发服务默认监听 `0.0.0.0:5173`。启动前检查是否已有本项目服务，优先复用；端口变化时告知实际地址，不要误停其他进程。手机可通过同一局域网访问服务的 Network 地址。

几何修改后的生成与检查顺序：

```sh
python3 scripts/aura_surface.py
python3 scripts/vw_emblem.py
blender --background --python scripts/build_aura_t6.py
npm test
npm run build
blender --background --python scripts/render_aura_t6.py -- --preview --view=rear-photo --white
blender --background --python scripts/render_aura_t6.py -- --preview --view=rear-quarter
blender --background --python scripts/render_aura_t6.py -- --preview --view=trunk
```

- 必须等模型生成成功后再测试或渲染，避免检查上一版资产。
- 其他渲染视角见 `README.md`；`--white` 仅用于对照渲染，不改变默认 GLB 车漆。
- 当前本机 Blender 位于 `/opt/homebrew/bin/blender`，其他环境使用可用的 Blender 命令。生成脚本目前引用 macOS 的 `STHeiti Medium.ttc` 字体，换平台时先处理字体路径。

## 修改约定

- 优先修改现有模块和参数，不为局部外观调整引入框架、额外服务或新依赖。保持改动聚焦，避免无关重排和大范围格式化。
- 车辆状态集中在 `src/state.js`；主控制台和细节视图共享同一状态。新增电动功能应区分目标与实际位置，处理限位、反向、暂停及复位。未来接协议时复用这套状态，避免另建相互冲突的状态副本。
- 整车、细节和行驶视图复用同一模型、canvas、renderer 与动画循环；切换视图时恢复相机、可见性和交互设置，避免创建重复场景或循环。
- 保留当前联动：解锁后才能开门，关门后才能上锁，插枪后才能充电；车门、机盖、尾门未关拢或充电枪连接时禁止起步，天窗可保持开启行驶。
- 保留键盘操作、可访问名称、控件状态反馈和窄屏布局；视口模拟不等同于实体手机触控验证。

## 三维模型约定

- 可重复生成的脚本是模型维护入口。修改几何后同步更新 `models/aura-t6.blend`、`public/models/aura-t6.glb` 和 `public/models/aura-t6.json`；不要仅手改二进制资产而遗漏生成源。
- 不直接修改生成的 `dist/`。`output/` 为忽略跟踪的截图与渲染输出目录。
- 参考照片用于建模与核对，保存在 Blender 隐藏参考集合中，不以车身图片贴片替代可旋转、可开合、可拆解的三维结构。新增外部资产需记录来源和许可。
- 相邻车身面、灯具和饰件优先共用曲面函数，避免各自偏移后出现裂缝、回折、穿插或不连续反光。对照用户最新照片，同时检查正面和侧面角度。
- 保持已认可的 VW 徽标共用轮廓；局部车尾调整不要顺带改动已认可的前脸或徽标。
- GLB 的 `part`、`label`、`layer`、`offset`、`start`、`motion`、`side` 等 extras 是运行时接口。部件名称也用于细节选择与拾取路由，重命名时同步检查消费者和测试。
- Blender 使用 Z 轴向上，导出 GLB 使用 Y 轴向上，坐标转换为 `(x, z, -y)`；铰点、偏移和运动轴必须统一，避免重复转换。
- 尾门、后玻璃、中央尾灯和扰流板共用尾门铰点，外侧尾灯固定；前活动天窗与后固定玻璃分离。开合时撑杆应持续连接，拆解和复位不能破坏这些关系。
- 部件数量或元数据有意变化时更新相应资产测试，不能仅为消除失败而放宽断言。

## 验证与交付

- 逻辑或模型变更运行 `npm test`、`npm run build`；共享曲面和徽标变更还需运行对应 Python 自检。纯文档变更检查内容、路径和命令即可，不要求重建模型。
- 外观变更必须查看实际生成的模型渲染和浏览器画面；检查接缝、曲面反光、玻璃、灯组、内衬穿出，以及闭合、中间和全开姿态。测试通过不能替代视觉核对。
- 涉及界面、取景或模型尺寸时，核对桌面与手机视口（常用 `1280×900`、`390×844`），相关细节页的旋转、缩放和隔离，以及拆解到 100% 再复位。检查浏览器错误日志，结束后恢复临时视口设置。
- 在 `output/` 保存有代表性的截图。说明具体改动、实际完成的验证和仍存在的精度边界；引用截图或文件时给出可点击路径。
- 行为或模型维护流程变化时同步更新 `README.md`；重要外观校准与参考来源更新 `docs/references/aura-t6.md`。不要把未执行的检查写成已通过。
