# AURA T6 车尾与整车曲面校准

继续使用用户的多视图细节图。保留已认可的六处 VW 徽标字形与材质，保留主灯的光学细节和 89 个独立交互部件。

- [x] 车身侧面分散上肩曲率，调整下腰线；前脸缩小灯具周围过强的凹陷。
- [x] 后围采用较平稳的中央截面与圆顺的外角，减少整体鼓包；后玻璃调整为较直立、较浅横向拱面，并与尾门重新接合。
- [x] 将尾门中央面与两侧固定后围分开，生成弧形下边界和约 4 mm 真实间隙；保险杠上缘跟随边界。
- [x] 改善尾灯侧向黑色罩面和末端收尖；黑色下包围随下部车身收拢，增加分层饰面。
- [x] 渲染正后、侧后、正前、侧面与整体视图；检查界面加载、开门降窗、拆解和复位。
- [x] 运行共享曲面/徽标检查、实际 GLB 测试与生产构建，保存当前实际浏览器画面。

照片提供外观参考，仍不把本轮结果描述为原厂 CAD 或广告级精度。

最终验证：`python3 scripts/aura_surface.py`、`python3 scripts/vw_emblem.py` 均通过；最终 GLB 的 11 项测试通过；Vite 构建成功，保留现有约 620 kB 主包提示。浏览器验证开门、四窗 100%、拆解 100% 和复位，错误日志为空；1280 × 900 与 390 × 844 视口均检查。

最终几何核对图：`output/playwright/aura-t6-detail-rear-quarter.png`、`aura-t6-detail-rear.png`、`aura-t6-detail-side.png`、`aura-t6-detail-front.png`、`aura-t6-cycles-preview.png`。实际页面证据：`aura-t6-tail-front-browser.png`、`aura-t6-tail-rear-browser.png`、`aura-t6-tail-controls.png`、`aura-t6-tail-exploded.png`、`aura-t6-tail-mobile.png`（均在同一输出目录）。
