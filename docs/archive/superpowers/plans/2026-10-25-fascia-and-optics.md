# AURA T6 前后脸与灯具校准

用户已明确要求继续按多视图校准外观，并提供主前灯近照。本轮直接在现有 Blender 生成流程中实现，不改协议与控制界面。

- [x] `scripts/aura_surface.py`：前围增加连续弧度和灯具周围的冲压凹面；尾部减少重复起伏，统一圆角和上下收放。
- [x] `scripts/build_aura_t6.py`：前贯穿饰板、机盖前沿与前围共用曲面；主灯改为外侧上下透镜、内侧矩形光学单元、下侧反射饰板与烟灰罩面。
- [x] `scripts/build_aura_t6.py`：后挡玻璃下沿前后位置随横向曲率变化，缩短尾门上方过宽的平台；D 柱、尾灯、雨刷和尾门接边同步调整。
- [x] `scripts/render_aura_t6.py`：补充灯具近景，核对正前、正后、侧面和三分之四视角。
- [x] 运行 `python3 scripts/aura_surface.py`、`npm test`、`npm run build`；浏览器复核开门降窗、拆解复位并保存实际画面。

验收以可见的曲面和光学结构改进为准。参考照片不提供工程截面，完成本轮并不意味着达到原厂 CAD 或广告图精度。

验证记录：最终模型保留 89 个独立部件；11 项 Node 测试通过，Vite 构建成功（主包现有 620 kB 提示仍存在）。新增 Python 曲面检查先复现后翼子板回折，再验证修正后前后转角的纵向坐标均单调。后玻璃与同一横向位置的尾门接合距离约 35 mm。浏览器核对车门打开、车窗 100%、拆解 100% 和复位，错误日志为空。

证据：`output/playwright/aura-t6-detail-lamp.png` 为当前灯具的 Cycles 近景；`aura-t6-detail-front.png`、`aura-t6-detail-rear.png`、`aura-t6-detail-side.png` 为当前几何核对图。实际页面为 `aura-t6-fascia-browser.png`、`aura-t6-fascia-rear-browser.png`、`aura-t6-fascia-controls.png`、`aura-t6-fascia-exploded.png`。
