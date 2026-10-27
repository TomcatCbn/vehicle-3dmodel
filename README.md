# AXIS Vehicle Lab — ID. AURA T6

本地 3D 车辆交互与滚动拆解演示。默认模型在 Blender 中根据大众官网图片及用户提供的实拍进行外观近似重建，不是原厂 CAD；内部、底盘和电池采用仿真示意结构。

## 运行

需要 Node.js 20.19+ 或 22.12+。

```sh
npm install
npm run dev
```

打开终端显示的地址。手机连接同一局域网时可访问 Network 地址。

```sh
npm test
npm run build
```

## 模型文件

- `models/aura-t6.blend`：可直接用 Blender 打开的模型源文件，含独立部件和隐藏的外观参考图集合。
- `public/models/aura-t6.glb`：浏览器加载的 glTF 2.0 资产。
- `scripts/build_aura_t6.py`：可重复生成模型的 Blender 脚本。
- `scripts/aura_surface.py`：车身、前后围的共享截面曲线及接边验证，可独立于 Blender 运行。
- `scripts/vw_emblem.py`：前后车标与轮毂中心标共用的 VW 字形轮廓和比例自检。
- `scripts/render_aura_t6.py`：用 Cycles 渲染同一套真实三维几何，输出至 `output/playwright/`。
- `docs/references/aura-t6.md`：官网来源及模型准确性边界。

重新生成（需要 Blender）：

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
blender --background --python scripts/render_aura_t6.py -- --preview --view=lamp
blender --background --python scripts/render_aura_t6.py -- --preview --view=badge
blender --background --python scripts/render_aura_t6.py -- --preview --view=hood
blender --background --python scripts/render_aura_t6.py -- --preview --view=hood-quarter
blender --background --python scripts/render_aura_t6.py -- --preview --view=front-photo --white
blender --background --python scripts/render_aura_t6.py -- --preview --view=rear-photo --white
blender --background --python scripts/render_aura_t6.py -- --preview --view=trunk
blender --background --python scripts/render_aura_t6.py -- --preview --view=sunroof
```

输出为同一三维模型的正交视图，以及轮毂、主灯或车标近景，保存在 `output/playwright/aura-t6-detail-*.png`，用于和多视图参考核对。

`front-photo --white` 使用同一模型的白色正前透视视图核对实拍比例，不改变默认 GLB 车漆。机盖与固定前沿使用共享曲面法线；前舱检修盖与外围托盘采用不同粗糙度的黑色非金属塑料。Blender 使用程序噪声凹凸，浏览器在模型 UV 上生成可重复的微法线；直接使用裸 GLB 时不会包含浏览器生成的颗粒贴图。

GLB 使用 `part`、`label`、`layer`、`offset`、`start`、`motion`、`side` 自定义元数据驱动拆解和车控。Blender 的坐标系在导出时转换为 glTF 的 Y 轴向上坐标系。

## 交互

- 拖动车辆旋转；自由、侧面和俯视视角；手机双指缩放。
- 点击「放大看细节」进入全屏三维查看，可切换前脸、前舱、车尾、天窗、门把手、车灯、车标、轮毂、后视镜、翼子板感知、车顶感知和轮胎；拖动旋转，滚轮、双指或 ＋/− 缩放，重置按钮恢复当前部位的视角。双击门把手也可进入近景，查看齐平上盖、内凹握槽、端盖接缝与触控刻线；把手结构随车门运动，没有独立执行机构。
- 控制台可开合「前舱盖」。选择「前舱」细节会打开机盖，展示冲压内板、隔音衬板、两根伸缩撑杆、检修盖板和蓝色加注口；在细节页可用「关闭机盖」切换闭盖检查，退出后保留该状态。前脸细节页也有机盖开合按钮。
- 「电动后备箱」支持开启、暂停、关闭和中途反向，显示实际开度。后玻璃、中央尾灯和扰流板随尾门抬起，外侧尾灯保持固定，两侧撑杆跟随伸缩。车尾细节页也有相同控制。
- 「电动天窗」滑杆设置目标开度，前玻璃先抬升再向后滑动，后玻璃固定；打开后能看到真实车顶开口。「天窗」细节页可边操作边查看，退出后保留开度。细节相机按完整运动范围取景，开合时不自动追随；可用 ＋ 放大。
- 勾选「仅看所选部件」隐藏周围车身；车灯、车标、轮毂和轮胎默认独立展示。手机细节导航分为两行，十二个入口无需横向挤压。按 Esc 或「返回整车」退出，恢复车控状态、相机和拆解位置。双击车身部件也可进入对应部位的近景；后视镜、翼子板感知组件、车顶设备和轮胎可直接进入各自细节页。
- 前大灯可循环切换关闭、近光和远光；近光/远光带前方投射照明。尾灯独立开关；主动减速时制动灯自动高亮，实际倒车时白色倒车灯自动点亮。车内氛围灯支持关闭、暖白、冰蓝和紫色；充电指示灯只随充电状态变化。
- 点击「行驶演示」，再点「起步」；前进目标速度可调至 0–100 km/h，停稳后可切换倒车，倒车限速 20 km/h。支持平滑加减速、停车、重新起步以及前侧/侧面/后侧观察。轮胎、轮毂和路面随有符号行程一致换向，车速与本次行程按绝对值显示，车身保持在跟随镜头中。
- 车门、机盖或尾门打开、尚未关拢，或充电枪连接时无法起步。天窗可以保持开启。退出行驶会停驶并恢复整车或拆解位置；切换到后台会停车。每次进入行驶演示都会重新计算本次行程。
- 四种车漆颜色，车锁、车门、四窗同步开度、空调温度、连接充电枪与充电。
- 先解锁再开门；关门后才能上锁；插枪后才能充电。电量采用加速时间模拟。
- 向下滚动逐步拆解车身、座舱、轮组与动力系统；向上滚动重新组装。
- 拆解时按类别高亮，点击部件查看名称。
- 支持窄屏布局、键盘操作及减少动态效果偏好。

最新六张近照用于校准后视镜的上下壳、灯缝与底部镜头，低矮车顶感知外壳、黑色拱形行李架及内侧银条，翼子板楔形感知组件，以及五瓣 U 形轮辐、三角肋板、气门嘴和圆润胎肩。胎侧 Hankook / iON 字样沿三维曲面排列，未标注未经确认的轮胎尺寸。VW 字形轮廓保持不变，细化黑色底座和前摄像头眉边。

后视镜以斜向前外侧的曲面重建弧顶楔形上盖和分层下壳，镜片朝后且朝车内；底座缩窄、下移，与弯曲支颈连续连接。灯罩嵌在上下壳接缝，镜头嵌于下缘倒角面。镜面方向和曲率仍为照片近似，不代表实车光学标定。

新增渲染视角 `mirror`、`mirror-rear`（隔离核对镜片和底座）、`sensor`、`roof-sensor`、`roof-close`、`tire`，与既有 `badge`、`wheel` 一起核对局部结构。

轮舱保留外侧轮眉，内侧采用仅覆盖上半部的弧形回折内衬；去除四块完整圆盘式封底面，既遮住轮胎上方缝隙，也避免拆解时出现黑色“铁皮圆盘”。

## 范围

当前为浏览器内交互，刷新恢复默认值。MQTT / BLE 尚未接入；现有协议应在确定报文、鉴权与设备角色后对接车辆状态逻辑。

实时场景使用日落色背景、摄影棚 HDR、物理玻璃、软阴影和模糊地面反射。HDR 来源及 CC0 说明见 `public/environments/LICENSE.md`。现有几何仍未达到广告图的车型精度。用户提供的汽车之家环视是图片序列，只作为多角度建模参考，无法直接获得独立车门或零件模型。

空调以气流和温度设定展示；车窗当前为四窗同步控制。未包含车辆物理或电池电化学模型，内部示意结构不可用于推断实车配置。

前舱按用户开盖照片重建可见的检修盖板、机盖内板与固定前沿；盖板下方没有建模为发动机舱或储物箱。压筋、内衬和撑杆尺寸仍是照片近似。

前后展示牌统一为黑底白字 `ID.AURA T6`，包含薄黑底座及前牌上方摄像头；牌面采用三维文字，不显示照片中的第三方广告。尺寸和位置为照片估计，不代表实车法规号牌安装数据。

车尾按用户正后照片校准。天窗轨迹、尾门开合角度、撑杆和货厢为交互示意，未核实原厂尺寸或选装配置；未实现防夹策略。当前模型含 99 个独立部件。

行驶为直线视觉演示（含低速倒车），速度与行程仅在本地计算，未接入 MQTT / BLE，不包含转向、碰撞、真实能耗或车辆动力学。手机布局已通过浏览器 390×844 视口检查，双指操作仍需实体手机验证。
