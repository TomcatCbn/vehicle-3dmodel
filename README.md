# Vehicle Simulator — 车信号模拟器

车信号模拟器平台：用 Tauri 2.0 + Rust 后端驱动信号状态机，前端 Three.js 渲染可交互三维车辆，目标是扮演一辆真实车的角色——可被手机 BLE 连接鉴权并执行车控，可连上车管后台 MQTT broker 接收远控指令并回传状态。支持 Windows 与 macOS 双平台。

当前基于大众 ID. AURA T6 照片近似重建的三维车辆进行开发，支持车控、细节查看、滚动拆解和赛车场行驶演示。三维模型不是原厂 CAD，内部、底盘和电池采用仿真示意结构。

## 架构

```
┌──────────────────────────────────────────────┐
│  前端 (Three.js + Vite)                       │
│  ┌─────────────┐  ┌──────────────────────┐   │
│  │ 3D 渲染管线  │  │ 控制面板 / 细节 / 行驶  │   │
│  └─────────────┘  └──────────┬───────────┘   │
│        followSnapshot(damp)  │ sendCommand    │
│  ┌───────────────────────────▼─────────────┐ │
│  │ state.js 双值插值 + applyLocalCommand     │ │
│  └───────────────────────────┬─────────────┘ │
└──────────────────────────────┼───────────────┘
                               │ Tauri invoke
┌──────────────────────────────┼───────────────┐
│  Rust 后端 (SignalModel)     │               │
│  ┌───────────────────────────▼─────────────┐ │
│  │ command.rs  ← VehicleCommand enum        │ │
│  │ model.rs    ← tick / apply / snapshot     │ │
│  │ interlock.rs← 联动校验                    │ │
│  │ state.rs    ← VehicleState (HashMap)      │ │
│  └─────────────────────────────────────────┘ │
│  未来: MQTT 客户端 / BLE peripheral / Profile │
└──────────────────────────────────────────────┘
```

- **双模式**：Tauri 桌面端走后端 SignalModel（invoke → tick → snapshot 广播 → followSnapshot 插值）；浏览器端回退到 `applyLocalCommand` 本地执行。
- **状态集中**：车辆状态集中在 `src/state.js`（前端）和 `src-tauri/src/signal/state.rs`（后端），前端通过快照跟随后端。
- **联动校验**：后端 `interlock.rs` 接管解锁→开门、关门→上锁、插枪→充电、门/盖关拢→起步等联动逻辑。
- **渲染管线**：整车、细节和行驶视图复用同一模型、canvas、renderer 与动画循环；现有 Three.js 渲染管线是长期投资，不重写。

## 运行

需要 Node.js 20.19+ 或 22.12+。Tauri 桌面端还需要 Rust 工具链（`rustup`）。

### 浏览器模式

```sh
npm install
npm run dev
```

打开终端显示的地址。手机连接同一局域网时可访问 Network 地址。浏览器模式下指令走本地 `applyLocalCommand`，状态不持久，刷新复位。

### Tauri 桌面模式

```sh
cargo tauri dev    # 开发（Vite + Tauri 窗口同时启动）
cargo tauri build  # 打包
```

桌面模式下指令走后端 SignalModel，状态由 Rust tick 循环推进。开发时 Vite 监听 `0.0.0.0:5173`；启动前确保端口空闲，否则 Vite 切到 5174 但 Tauri 仍加载 5173 导致加载旧代码。

### 测试与构建

```sh
npm test           # 前端测试 (node:test)
cargo test         # Rust 后端测试 (src-tauri/)
npm run build      # Vite 构建
```

## 项目结构

| 路径 | 职责 |
| --- | --- |
| `src/main.js` | 场景初始化、控件同步、滚动拆解、拾取和统一动画循环 |
| `src/state.js`、`src/lighting-state.js` | 前端车辆信号状态、双值插值、本地命令执行 |
| `src/tauri-bridge.js` | Tauri/Web 双模式封装（invoke/listen） |
| `src/render/` | vehicle.js（部件运动）、vehicle-lighting.js（灯组）、inspection.js（细节查看）、driving.js（行驶）、studio.js（环境照明） |
| `src/drive-state.js` | 行驶计算（动力学、起步条件、道路演示） |
| `src-tauri/src/signal/` | Rust SignalModel：state.rs（状态）、command.rs（命令）、model.rs（tick/apply/snapshot）、interlock.rs（联动校验） |
| `src-tauri/src/lib.rs` | Tauri 入口：SignalModel 管理 + tick 循环 + 日志系统 |
| `index.html`、`src/style.css` | 页面、控制台、细节和行驶弹窗、响应式样式 |
| `scripts/` | Blender Python 模型生成与渲染脚本 |
| `tests/` | 前端测试（状态、行驶、细节取景、灯光、UI 契约、GLB 回归） |
| `docs/decision/` | 架构决策文档（BLE/MQTT/信号模型/Profile） |
| `docs/references/aura-t6.md` | 模型来源及准确性边界 |

## 模型文件

- `models/aura-t6.blend`：可直接用 Blender 打开的模型源文件，含独立部件和隐藏的外观参考图集合。
- `public/models/aura-t6.glb`：浏览器加载的 glTF 2.0 资产。
- `scripts/build_aura_t6.py`：可重复生成模型的 Blender 脚本。
- `scripts/aura_surface.py`：车身、前后围的共享截面曲线及接边验证，可独立于 Blender 运行。
- `scripts/vw_emblem.py`：前后车标与轮毂中心标共用的 VW 字形轮廓和比例自检。
- `scripts/render_aura_t6.py`：用 Cycles 渲染同一套真实三维几何，输出至 `output/playwright/`；加 `--animation` 可复现欢迎页默认开场流程（车辆驶近→尾灯近赏→单侧弧线到车头 Logo→拉远回展台）渲染成 H.264 mp4，位姿数据来自 `scripts/export_entrance_poses.mjs` 导出的 `entrance-poses.json`。
- `docs/references/aura-t6.md`：官网来源及模型准确性边界。

重新生成（需要 Blender；当前机器可使用 `/Users/uvaw4pv/software/Blender.app/Contents/MacOS/Blender`）：

```sh
python3 scripts/aura_surface.py
python3 scripts/vw_emblem.py
blender --background --python scripts/build_aura_t6.py
blender --background --python scripts/render_aura_t6.py
```

快速核对正面、背面或侧面时，可分别使用：

```sh
blender --background --python scripts/render_aura_t6.py -- --preview --view=front
blender --background --python scripts/render_aura_t6.py -- --preview --view=rear
blender --background --python scripts/render_aura_t6.py -- --preview --view=rear-quarter
blender --background --python scripts/render_aura_t6.py -- --preview --view=front-quarter
blender --background --python scripts/render_aura_t6.py -- --preview --view=handle
blender --background --python scripts/render_aura_t6.py -- --preview --view=side
blender --background --python scripts/render_aura_t6.py -- --preview --view=wheel
blender --background --python scripts/render_aura_t6.py -- --preview --view=door-interior
blender --background --python scripts/render_aura_t6.py -- --preview --view=lamp
blender --background --python scripts/render_aura_t6.py -- --preview --view=badge
blender --background --python scripts/render_aura_t6.py -- --preview --view=hood
blender --background --python scripts/render_aura_t6.py -- --preview --view=hood-quarter
blender --background --python scripts/render_aura_t6.py -- --preview --view=front-photo --white
blender --background --python scripts/render_aura_t6.py -- --preview --view=rear-photo --white
blender --background --python scripts/render_aura_t6.py -- --preview --view=trunk
blender --background --python scripts/render_aura_t6.py -- --preview --view=sunroof
blender --background --python scripts/render_aura_t6.py -- --preview --view=interior
blender --background --python scripts/render_aura_t6.py -- --preview --view=seats
# 动画短片：复现欢迎页默认开场流程（车从远处驶近→尾灯近赏→单侧弧线到车头 Logo→拉远回展台），渲染 PNG 序列后用 ffmpeg 合成 H.264 mp4
blender --background --python scripts/render_aura_t6.py -- --preview --animation                 # 快速预览（241帧/960×600/Cycles 64采样）
blender --background --python scripts/render_aura_t6.py -- --animation                          # 正式（241帧/1600×1000/Cycles 96采样）
# 位姿数据由 scripts/export_entrance_poses.mjs 从 src/render/entrance.js 导出，改开场动画后重跑该脚本更新 public/models/entrance-poses.json
node scripts/export_entrance_poses.mjs
node scripts/export_entrance_poses.mjs --variant=direct  # 另导出直回版到 public/models/entrance-poses-direct.json
```

输出为同一三维模型的正交视图，以及轮毂、主灯、车标或座舱近景，保存在 `output/playwright/aura-t6-detail-*.png`，用于和多视图参考核对。`interior` 从后排方向检查左舵三联屏驾驶区，`seats` 从前方向后检查前后座椅和中央扶手。`--animation` 模式复现欢迎页默认开场流程，输出 `output/playwright/aura-t6-entrance[-preview].mp4`（车辆沿路线驶近、相机尾灯近赏后沿单侧弧线到车头 Logo 再拉远回展台，车轮滚动转向；PNG 序列临时存于 `*-frames/` 子目录，合成后可删除）。

座舱按用户内饰照片采用灰色分层仪表台、仪表／中控／副驾三屏、双辐圆角方向盘、浅灰中央通道和灰色座椅；补充了屏幕图形、出风口、缝线、穿孔表面、头枕与安全带卡扣。它们仍是照片近似和交互示意，不代表原厂车机界面、真实通风结构或工程尺寸。

`front-photo --white` 使用同一模型的白色正前透视视图核对实拍比例，不改变默认 GLB 车漆。机盖与固定前沿使用共享曲面法线；前舱检修盖与外围托盘采用不同粗糙度的黑色非金属塑料。Blender 使用程序噪声凹凸，浏览器在模型 UV 上生成可重复的微法线；直接使用裸 GLB 时不会包含浏览器生成的颗粒贴图。

GLB 使用 `part`、`label`、`layer`、`offset`、`start`、`motion`、`side` 自定义元数据驱动拆解和车控。Blender 的坐标系在导出时转换为 glTF 的 Y 轴向上坐标系。

## 交互

- 模型加载后播放约 10 秒的桌面出场（离线按 24 fps 导出 241 帧）：默认前段镜头固定，车辆从远处沿参考草图的大型右弧驶近，再反向回转；镜头随后跟随车尾、贴近尾灯，再沿单侧弧线到车头 VW Logo 特写，最后拉远回展台。欢迎页可切换「直回 / 车头特写」，选择作用于下一次播放；「直回」在尾灯特写后直接缓回整车。车辆在收尾时持续低速行驶，与镜头同时停稳；左右前轮依照弯道曲率分别转向，四轮按各自路径距离滚动。出场期间可点击「跳过出场」、按 Esc、拖动车辆、滚动、切导航或切后台结束；工具栏 ▶ 可重播。须先停车、关好车门/机盖/尾门并拔枪；「减少动态效果」偏好下保持静态展示。出场运动是近似运动学视觉演示，不触发车辆行驶信号；自然停稳时会通过车辆状态机关闭前后灯和氛围灯、锁车并熄火进入休眠，跳过动画不会自动执行这些命令。
- 欢迎页在车停稳后展示“车辆展示 + 车端模拟”探索面板：主入口进入爱车页车控台，另有细节结构和行驶场景入口，面向开发、测试与演示串联现有三维反馈和信号状态功能。桌面端位于右侧，手机端改为三个并列入口；面板只描述本地仿真能力，不代表 BLE / MQTT 已完成真实协议联调。
- 拖动车辆旋转；自由、侧面和俯视视角；手机双指缩放。
- 控制台分五个可折叠分组：车门与锁、车窗与天窗、电动后备箱、灯光、空调与充电。车门支持四门独立开合，车窗支持四窗独立滑杆控制；联动校验由后端 interlock 模块接管（解锁后才能开门，关门后才能上锁，插枪后才能充电）。
- 点击「放大看细节」进入全屏三维查看，可切换前脸、前舱、车尾、天窗、门把手、充电口、车灯、车标、轮毂、后视镜、翼子板感知、车顶感知、前挡感知、遥控钥匙和轮胎，共 15 个入口；拖动旋转，滚轮、双指或 ＋/− 缩放，重置按钮恢复当前部位的视角。双击门把手、充电舱或前挡感知组件也可进入对应近景；把手结构随车门运动，没有独立执行机构。
- 控制台可开合「前舱盖」。选择「前舱」细节会打开机盖，展示冲压内板、隔音衬板、两根伸缩撑杆、深槽储物舱和蓝色加注口；在细节页可用「关闭机盖」切换闭盖检查，退出后保留该状态。前脸细节页也有机盖开合按钮。
- 「电动后备箱」支持开启、暂停、关闭和中途反向，显示实际开度。后玻璃、中央尾灯和扰流板随尾门抬起，外侧尾灯保持固定，两侧撑杆跟随伸缩。车尾细节页也有相同控制。
- 「电动天窗」滑杆设置目标开度，前玻璃先抬升再向后滑动，后玻璃固定；打开后能看到真实车顶开口。「天窗」细节页可边操作边查看，退出后保留开度。细节相机按完整运动范围取景，开合时不自动追随；可用 ＋ 放大。
- 勾选「仅看所选部件」隐藏周围车身；充电口、车灯、车标、轮毂、前挡感知、遥控钥匙和轮胎默认独立展示，充电口隔离可避免已连接充电枪遮挡凹舱。手机细节导航自动分行，15 个入口无需横向挤压。按 Esc 或「返回整车」退出，恢复车控状态、相机和拆解位置。双击车身部件也可进入对应部位的近景；后视镜、翼子板感知组件、车顶设备和轮胎可直接进入各自细节页。
- 前大灯可循环切换关闭、近光和远光，透镜与贯穿灯带带柔和光晕，近远光具有不同强度及照射范围。尾灯独立开关并向车尾周围投下红色补光；主动减速时制动灯自动高亮，实际倒车时白色倒车灯及后方地面照明点亮。车内氛围灯支持关闭、暖白、冰蓝和紫色，实际照亮座舱；充电指示灯随充电状态发出绿色光晕与近处补光。深灰地面便于对比光斑；只有已点亮灯组参与光晕，关闭后不残留发光。
- 点击「行驶演示」，再点「起步」；前进目标速度可调至 0–100 km/h，停稳后可切换倒车，倒车限速 20 km/h。场景为约 550 米的封闭赛车场，包含红白路肩、起终点格线、维修区和看台，可切换前侧、侧面、后侧、转向近景与赛道全景。以后轴中心轨迹约束车身运动，左右前轮按阿克曼几何分别转向，四轮按各自走过的弧长滚动，倒车不掉头。弯前根据曲率自动减速；自动镜头与车身同步，拖拽后保留手动角度，选择视角可恢复跟拍。车速与本次行程按绝对值显示。
- 车门、机盖或尾门打开、尚未关拢，或充电枪连接时无法起步。天窗可以保持开启。退出行驶会停驶并恢复整车或拆解位置；切换到后台会停车。每次进入行驶演示都会重新计算本次行程。
- 贝珠白、星河蓝、烟霞紫、远山绿和云雀灰五种照片近似车漆，默认远山绿；另支持车锁、四门独立开合、四窗独立开度、电动天窗、空调温度、连接充电枪与充电。
- 先解锁再开门；关门后才能上锁；车锁无需高压，在 Sleep 和 Standby 状态均可操作，解锁会自动上高压进入 Ready 并开放全部面板车控；插枪后才能充电。电量采用加速时间模拟。
- 向下滚动逐步拆解车身、座舱、轮组与动力系统；向上滚动重新组装。
- 拆解时按类别高亮，点击部件查看名称。
- 支持窄屏布局、键盘操作及减少动态效果偏好。

最新六张近照用于校准后视镜的上下壳、灯缝与底部镜头，低矮车顶感知外壳、黑色拱形行李架及内侧银条，翼子板楔形感知组件，以及五瓣 U 形轮辐、三角肋板、气门嘴和圆润胎肩。胎侧 Hankook / iON evo SUV 字样沿三维曲面排列；2026-10-30 官方细节图补充确认了 `255/45 R20 101V` 规格。VW 字形轮廓保持不变，细化黑色底座和前摄像头眉边。

本轮继续依据同一汽车之家细节目录，校准尾灯外角上扬导光带、上部点阵灯腔、下沿双排微棱纹、扁平后雨刷与上下后摄像头。新增 `rear-lamp`、`rear-wiper`、`rear-camera` 同源渲染视角；例如 `blender --background --python scripts/render_aura_t6.py -- --preview --view=rear-wiper`。这些结构归入现有尾灯、尾门、后玻璃和扰流板，不增加控制状态或改变分件接口；参考图号与边界见 `docs/references/aura-t6.md`。

2026-10-31 按用户提供的充电舱与尾灯发光照片，将绿色充电状态灯布置在凹入端口内，接入充电信号；后 VW 字形随尾灯／制动灯发出红光；倒车灯改为黑色灯框和紧凑白色光窗，仍由倒车状态控制。外盖继续沿既有铰点联动，未增加第二套车控状态。

后视镜以斜向前外侧的曲面重建弧顶楔形上盖和分层下壳，镜片朝后且朝车内；底座缩窄、下移，与弯曲支颈连续连接。灯罩嵌在上下壳接缝，镜头嵌于下缘倒角面。镜面方向和曲率仍为照片近似，不代表实车光学标定。

新增渲染视角 `mirror`、`mirror-rear`（隔离核对镜片和底座）、`sensor`、`roof-sensor`、`roof-close`、`tire`，与既有 `badge`、`wheel` 一起核对局部结构。

轮舱保留外侧轮眉，内侧采用仅覆盖上半部的弧形回折内衬；去除四块完整圆盘式封底面，既遮住轮胎上方缝隙，也避免拆解时出现黑色“铁皮圆盘”。

## 当前状态与路线图

- **M1 已完成**：Tauri 2.0 + Rust 后端骨架、SignalModel 状态机（12 测试）、前端双模式（invoke 回退本地）、控制面板重构（5 分组 / 4 门 / 4 窗）、日志系统。
- **M2 已完成**：inspection onSelect 和 hood toggle 改为只发 command（不再直改 state）；删除前端 `setDriving`，起步校验由后端 `interlock::can_start_driving` 接管；测试重写。
- **M3 待定**：MQTT 接入——模拟器作为车端 MQTT 客户端，向车管后台注册 → 拿连接参数 → 直连 broker，远控指令经 SignalModel 执行后回传响应。
- **M4 待定**：BLE 接入——模拟器作为 BLE peripheral 广播 + GATT 服务端，手机连接鉴权后执行 RKE 车控。协议字段待对齐 OneSDK 私有协议后细化。

当前 BLE 和 MQTT 尚未接入真实协议，不要将界面动作或动画描述为已完成真实协议联调。

## 范围

浏览器模式下刷新恢复默认值。Tauri 桌面模式下状态由后端管理，窗口关闭后复位（未持久化）。MQTT / BLE 尚未接入；现有协议应在确定报文、鉴权与设备角色后对接车辆状态逻辑。

实时场景使用日落色背景、摄影棚 HDR、物理玻璃、软阴影和模糊地面反射。HDR 来源及 CC0 说明见 `public/environments/LICENSE.md`。现有几何仍未达到广告图的车型精度。用户提供的汽车之家环视是图片序列，只作为多角度建模参考，无法直接获得独立车门或零件模型。

空调以气流和温度设定展示；车窗支持四窗独立控制。未包含车辆物理或电池电化学模型，内部示意结构不可用于推断实车配置。

前舱按 2026-10-30 官方开盖细节图重建为约 0.24 m 深的圆角储物槽，包含连续密封条、底面、渐变侧壁、内部筋、排水位、锁扣和加注口；机盖内板与固定前沿保留。槽体、压筋、内衬和撑杆尺寸仍是照片近似，不代表原厂容积或工程结构。

前后展示牌统一为黑底白字 `ID.AURA T6`，包含薄黑底座及前牌上方摄像头；牌面采用三维文字，不显示照片中的第三方广告。尺寸和位置为照片估计，不代表实车法规号牌安装数据。

车尾按用户正后照片校准。天窗轨迹、尾门开合角度、撑杆和货厢为交互示意，未核实原厂尺寸或选装配置；未实现防夹策略。当前模型含 108 个独立总成（含半轴和差速器）。2026-10-30 按官方细节页全部 327 张图逐张核对，清单见 `docs/references/official-detail-coverage.md`；本轮补齐充电舱 AC／DC 端子、防尘盖与系绳、前挡双目感知与内后视镜、遥控钥匙、主灯内部光学元素及示意底盘连接结构。

本轮验证：80/80 前端测试、46/46 Rust 测试、生产构建、共享曲面与 VW 字形自检通过；同源 Cycles 渲染和 1280×900、390×844 浏览器画面已核对，五色车漆与 15 个细节入口可用，拆解 100% 后复位 0%，浏览器错误日志为空。上述细节仍是照片近似，内部结构、材质和底盘不代表原厂 CAD、光学标定或工程尺寸。

行驶为赛道运动学演示（含低速倒车），速度与行程仅在本地计算，未接入 MQTT / BLE；转向与滚动采用无侧滑几何关系，未模拟轮胎极限滑移、碰撞、悬架或真实能耗。手机布局已通过浏览器 390×844 视口检查，双指操作仍需实体手机验证。
