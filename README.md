# AXIS Vehicle Lab — ID. AURA T6

本地 3D 车辆交互与滚动拆解演示。默认模型在 Blender 中根据大众官网图片进行外观近似重建，不是原厂 CAD；内部、底盘和电池采用仿真示意结构。

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
blender --background --python scripts/render_aura_t6.py -- --preview --view=side
blender --background --python scripts/render_aura_t6.py -- --preview --view=wheel
blender --background --python scripts/render_aura_t6.py -- --preview --view=lamp
blender --background --python scripts/render_aura_t6.py -- --preview --view=badge
```

输出为同一三维模型的正交视图，以及轮毂、主灯或车标近景，保存在 `output/playwright/aura-t6-detail-*.png`，用于和多视图参考核对。

GLB 使用 `part`、`label`、`layer`、`offset`、`start`、`motion`、`side` 自定义元数据驱动拆解和车控。Blender 的坐标系在导出时转换为 glTF 的 Y 轴向上坐标系。

## 交互

- 拖动车辆旋转；自由、侧面和俯视视角；手机双指缩放。
- 点击「放大看细节」进入全屏三维查看，可切换前脸、车尾、车灯、车标和轮毂；拖动旋转，滚轮、双指或 ＋/− 缩放，重置按钮恢复当前部位的视角。
- 勾选「仅看所选部件」隐藏周围车身；车灯、车标和轮毂默认独立展示。按 Esc 或「返回整车」退出，恢复车控状态、相机和拆解位置。双击车身部件也可进入对应部位的近景。
- 点击「行驶演示」，再点「起步」；目标速度可调至 0–100 km/h，支持平滑加减速、停车、重新起步以及前侧/侧面/后侧观察。轮胎与轮毂按同一累计行程旋转，路面和路边道钉反向滚动，车身保持在跟随镜头中。
- 开门、车门尚未关拢或充电枪连接时无法起步。退出行驶会停驶并恢复整车或拆解位置；切换到后台会停车。每次进入行驶演示都会重新计算本次行程。
- 四种车漆颜色，车锁、车门、四窗同步开度、空调温度、连接充电枪与充电。
- 先解锁再开门；关门后才能上锁；插枪后才能充电。电量采用加速时间模拟。
- 向下滚动逐步拆解车身、座舱、轮组与动力系统；向上滚动重新组装。
- 拆解时按类别高亮，点击部件查看名称。
- 支持窄屏布局、键盘操作及减少动态效果偏好。

## 范围

当前为浏览器内交互，刷新恢复默认值。MQTT / BLE 尚未接入；现有协议应在确定报文、鉴权与设备角色后对接车辆状态逻辑。

实时场景使用日落色背景、摄影棚 HDR、物理玻璃、软阴影和模糊地面反射。HDR 来源及 CC0 说明见 `public/environments/LICENSE.md`。现有几何仍未达到广告图的车型精度。用户提供的汽车之家环视是图片序列，只作为多角度建模参考，无法直接获得独立车门或零件模型。

空调以气流和温度设定展示；车窗当前为四窗同步控制。未包含车辆物理或电池电化学模型，内部示意结构不可用于推断实车配置。

行驶为直线视觉演示，速度与行程仅在本地计算，未接入 MQTT / BLE，不包含转向、碰撞、真实能耗或车辆动力学。手机布局已通过浏览器 390×844 视口检查，双指操作仍需实体手机验证。
