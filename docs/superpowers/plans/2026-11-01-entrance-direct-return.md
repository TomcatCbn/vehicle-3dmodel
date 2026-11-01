# 开场尾灯特写后直接缓回整车实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除开场后段绕车两侧和车头特写，让相机从尾灯特写直接平滑回到整车机位。

**Architecture:** 保留 `entrancePose` 的现有接口、车辆路径和时间重映射，只精简 `cameraLocal`、`targetLocal` 的关键帧及阶段文案。测试直接检查局部车体系中的后段轨迹，Blender 位姿 JSON 继续由同一函数导出。

**Tech Stack:** Three.js、原生 JavaScript ES Modules、Node.js `node:test`、Vite

---

### Task 1: 用回归测试锁定直接回位轨迹并精简关键帧

**Files:**
- Modify: `tests/entrance.test.js:34-50`
- Modify: `src/render/entrance.js:73-88`

- [ ] **Step 1: 将运镜测试改为尾灯后直接回位，并保留连续性检查**

把 `camera closes on the tail logo, arcs along the side, then finishes in a nose close-up` 整个测试替换为：

```js
test('camera closes on the tail logo then returns directly without orbiting the car',()=>{
  const tail=entrancePose(ENTRANCE_DURATION*.40,home);
  assert.ok(local(tail,tail.camera).x>3&&local(tail,tail.target).x>2);
  assert.ok(tail.camera.distanceTo(tail.target)<2.5,'logo close-up');
  let previous;
  for(let i=0;i<=1000;i++){
    const t=i/1000,p=entrancePose(t*ENTRANCE_DURATION,home),c=local(p,p.camera),target=local(p,p.target);
    assert.ok(!(Math.abs(c.x)<2.6&&Math.abs(c.z)<1.3&&c.y<1.9),'camera stays outside the closed body');
    assert.ok(p.camera.distanceTo(p.target)>1.8);
    if(t>=.42){
      assert.ok(c.z>=-1e-9,'return stays on one side instead of orbiting around the nose');
      assert.ok(target.x>=-1e-9&&target.x<=2.35+1e-9,'target eases directly from the badge to the car centre');
    }
    if(previous)assert.ok(p.camera.distanceTo(previous.camera)<.8,'continuous tracking');
    previous=p;
  }
  const first=entrancePose(0,home),entry=first.position.clone().add(new THREE.Vector3(0,.7,0)).project(cameraFor(first));
  assert.ok(entry.x<-.35&&entry.y>.15);
});
```

- [ ] **Step 2: 运行测试并确认旧环绕轨迹失败**

Run: `node --test tests/entrance.test.js`

Expected: 新测试 FAIL，旧轨迹在 `t >= .42` 后出现负的局部 `target.x` 或负的局部 `camera.z`，其余测试保持通过。

- [ ] **Step 3: 删除后段环绕关键帧并更新阶段名称**

在 `src/render/entrance.js` 中，将 `cameraLocal` 和 `targetLocal` 两行替换为：

```js
  const cameraLocal=sampleTrack([[0,initialCamera],[.16,v(-7.5,2,-9)],[.28,v(6,1.6,-3)],[.34,v(4.4,1.0,0.0)],[.38,v(4.2,1.0,0.0)],[.42,v(4.2,0.98,0.0)],[1,home]],t);
  const targetLocal=sampleTrack([[0,initialTarget],[.16,v(0,.75,0)],[.28,v(1.0,.95,.1)],[.34,v(2.35,.96,0.0)],[.38,v(2.35,.96,0.0)],[.42,v(2.35,.96,0.0)],[1,v(0,.7,0)]],t);
```

将上方关键帧说明替换为：

```js
  // Logo close-up (0.28–0.42): dead-centre on the tail badge, compressed beat.
  // Return (0.42–1): ease directly back to home without orbiting the car.
```

将 `phase` 行替换为：

```js
    phase:t<.28?'大弧转入':t<.42?'尾灯近赏':'从容就位',
```

- [ ] **Step 4: 运行开场测试并确认通过**

Run: `node --test tests/entrance.test.js`

Expected: 6 项测试全部 PASS，0 项 FAIL。

### Task 2: 同步离线位姿与说明并完成验证

**Files:**
- Modify: `public/models/entrance-poses.json`
- Modify: `README.md:92,125,132`
- Verify: `docs/decision/19-entrance-direct-return.md`

- [ ] **Step 1: 从更新后的单一数据源重新导出 Blender 位姿**

Run: `node scripts/export_entrance_poses.mjs`

Expected: 输出 `导出 241 帧到 public/models/entrance-poses.json（BULLET_DURATION=10s，含子弹时间）`，文件中的后段相机位姿与浏览器使用的新轨迹一致。

- [ ] **Step 2: 更新 README 中的开场流程说明**

将 README 三处 `车辆驶近→尾灯近赏→掠过车侧→整车`、`车从远处驶近→尾灯近赏→掠过车侧→整车` 和 `相机尾灯近赏与掠过车侧` 分别改为：

```text
车辆驶近→尾灯近赏→直接缓回整车
车从远处驶近→尾灯近赏→直接缓回整车
相机尾灯近赏后直接缓回整车
```

- [ ] **Step 3: 运行完整自动检查**

Run: `npm test`

Expected: 86 项测试全部 PASS，0 项 FAIL。

Run: `npm run build`

Expected: Vite 构建成功，退出码为 0；仅允许已有的大 chunk 提示，不允许构建错误。

Run: `git diff --check`

Expected: 无空白错误，退出码为 0。

- [ ] **Step 4: 浏览器实际重播并核对后段运镜**

打开 `http://localhost:5173`，重播开场动画，确认前段大弧转入和尾灯特写保留；尾灯后不再绕到另一侧或车头特写，而是连续回位；结束后整车取景和鼠标交互正常。检查浏览器控制台无新增错误。
