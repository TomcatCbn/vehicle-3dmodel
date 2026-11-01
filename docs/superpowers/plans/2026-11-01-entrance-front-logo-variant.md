# 开场车头 Logo 特写可切换版实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 保留尾灯直回运镜，新增默认的“尾灯 → 单侧弧线 → 车头 Logo 特写 → 展台”版本，并允许在欢迎页切换。

**Architecture:** `entrancePose` 继续统一计算车辆、车轮和时间，仅通过第三个 `variant` 参数选择相机与注视点关键帧。`createEntrance` 通过 `getVariant` 在每次采样时读取当前选择；UI 只维护一个开场变体值，不进入车辆信号状态。离线导出复用同一 `variant` 参数。

**Tech Stack:** Three.js、原生 JavaScript ES Modules、Node.js `node:test`、Vite

---

### Task 1: 以 TDD 增加 front-logo 轨迹并保留 direct

**Files:**
- Modify: `tests/entrance.test.js`
- Modify: `src/render/entrance.js:58-130`

- [x] **Step 1: 让现有直回测试显式使用 direct，并新增车头 Logo 失败测试**

把现有直接回位测试中的所有 `entrancePose(...,home)` 调用改为 `entrancePose(...,home,'direct')`，包括循环和 `first`；其他不涉及该变体的测试保持默认调用。

在该测试后加入：

```js
test('front-logo variant follows one side to the nose badge then returns home',()=>{
  const front=entrancePose(ENTRANCE_DURATION*.74,home,'front-logo');
  assert.ok(local(front,front.camera).x<-3,'camera reaches the nose');
  assert.ok(Math.abs(local(front,front.target).x+2.35)<1e-9,'target is the nose badge');
  assert.ok(front.camera.distanceTo(front.target)<2.5,'nose badge close-up');
  assert.ok(entrancePose(ENTRANCE_DURATION*.74,home).camera.distanceTo(front.camera)<1e-10,'front-logo is the default');
  let previous;
  for(let i=0;i<=1000;i++){
    const t=i/1000,p=entrancePose(t*ENTRANCE_DURATION,home,'front-logo'),c=local(p,p.camera);
    assert.ok(!(Math.abs(c.x)<2.6&&Math.abs(c.z)<1.3&&c.y<1.9),'camera stays outside the closed body');
    assert.ok(p.camera.distanceTo(p.target)>1.8);
    if(t>=.42)assert.ok(c.z>=-1e-9,'front approach stays on one side');
    if(previous)assert.ok(p.camera.distanceTo(previous.camera)<.8,'continuous tracking');
    previous=p;
  }
  const final=entrancePose(ENTRANCE_DURATION,home,'front-logo');
  assert.ok(final.camera.distanceTo(home)<1e-10);
  assert.ok(final.target.distanceTo(new THREE.Vector3(0,.7,0))<1e-10);
});
```

- [x] **Step 2: 确认新测试在旧实现上失败**

Run: `node --test tests/entrance.test.js`

Expected: 新增 front-logo 测试 FAIL，因为旧实现忽略第三个参数且没有车头 Logo 特写；显式 direct 测试继续 PASS。

- [x] **Step 3: 实现共享前缀与两套后段关键帧**

将 `entrancePose` 签名改为：

```js
export function entrancePose(time,home,variant='front-logo') {
```

用以下代码替换当前 `cameraLocal`、`targetLocal` 及其三行注释：

```js
  // Camera keyframes (local vehicle space; +X = tail/logo, -X = nose).
  // Both variants share the tail close-up, then either return directly or
  // follow one side to the nose badge before easing back to home.
  const cameraKeys=[[0,initialCamera],[.16,v(-7.5,2,-9)],[.28,v(6,1.6,-3)],[.34,v(4.4,1.0,0.0)],[.38,v(4.2,1.0,0.0)],[.42,v(4.2,0.98,0.0)]];
  const targetKeys=[[0,initialTarget],[.16,v(0,.75,0)],[.28,v(1.0,.95,.1)],[.34,v(2.35,.96,0.0)],[.38,v(2.35,.96,0.0)],[.42,v(2.35,.96,0.0)]];
  if(variant==='direct'){
    cameraKeys.push([.46,v(3.8,1.2,1.2)],[1,home]);
    targetKeys.push([1,v(0,.7,0)]);
  }else{
    cameraKeys.push([.46,v(3.8,1.2,1.2)],[.52,v(2.0,1.5,3.2)],[.58,v(0.5,1.6,4.2)],[.66,v(-3.8,1.3,2.0)],[.72,v(-4.2,1.0,0.0)],[.76,v(-4.2,.98,0.0)],[1,home]);
    targetKeys.push([.46,v(1.8,.95,.6)],[.52,v(.6,.9,1.0)],[.58,v(-.4,.85,.6)],[.66,v(-2.0,.95,.4)],[.72,v(-2.35,.96,0.0)],[.76,v(-2.35,.96,0.0)],[1,v(0,.7,0)]);
  }
  const cameraLocal=sampleTrack(cameraKeys,t);
  const targetLocal=sampleTrack(targetKeys,t);
```

将 `phase` 改为：

```js
    phase:t<.28?'大弧转入':t<.42?'尾灯近赏':variant==='front-logo'&&t<.78?'车头近赏':'从容就位',
```

将 `createEntrance` 参数与 `apply` 改为：

```js
export function createEntrance({vehicle,camera,controls,studio,home,getVariant=()=> 'front-logo',onChange=()=>{},onComplete=()=>{}}) {
```

```js
    const pose=entrancePose(time,home(),getVariant());
```

- [x] **Step 4: 验证两版运镜**

Run: `node --test tests/entrance.test.js`

Expected: 7 项测试全部 PASS，0 项 FAIL；若安全距离或连续性断言失败，只调整 front-logo 的 0.42 后控制点，不放宽断言、不改变 direct 轨迹。

### Task 2: 以 UI 契约测试增加页面切换

**Files:**
- Modify: `tests/ui-contract.test.js`
- Modify: `index.html:28`
- Modify: `src/main.js:307,327,407`

- [x] **Step 1: 添加失败的 UI 契约测试**

在 `tests/ui-contract.test.js` 末尾加入：

```js
test('entrance offers direct and front-logo variants with accessible pressed states',async()=>{
  const [page,main]=await Promise.all([
    readFile(new URL('../index.html',import.meta.url),'utf8'),
    readFile(new URL('../src/main.js',import.meta.url),'utf8'),
  ]);
  assert.match(page,/aria-label="开场运镜"/);
  assert.match(page,/data-entrance-variant="direct" aria-pressed="false"/);
  assert.match(page,/data-entrance-variant="front-logo" class="selected" aria-pressed="true"/);
  assert.match(main,/let entranceVariant='front-logo'/);
  assert.match(main,/getVariant:\(\)=>entranceVariant/);
  assert.match(main,/entranceVariant=button\.dataset\.entranceVariant/);
});
```

- [x] **Step 2: 确认 UI 契约测试失败**

Run: `node --test tests/ui-contract.test.js`

Expected: 新测试 FAIL，现有 3 项 UI 测试 PASS。

- [x] **Step 3: 添加复用现有样式的按钮组**

在 `index.html` 的 `#replay-intro` 按钮前插入：

```html
<div class="view-selector" aria-label="开场运镜"><button data-entrance-variant="direct" aria-pressed="false">直回</button><button data-entrance-variant="front-logo" class="selected" aria-pressed="true">车头特写</button></div>
```

在 `src/main.js` 的场景状态声明中加入：

```js
  let entranceVariant='front-logo';
```

在 `createEntrance` 调用的 `home:defaultCamera,` 后加入：

```js
    getVariant:()=>entranceVariant,
```

在视角按钮绑定之后加入：

```js
  for(const button of document.querySelectorAll('[data-entrance-variant]'))button.addEventListener('click',()=>{entranceVariant=button.dataset.entranceVariant;document.querySelectorAll('[data-entrance-variant]').forEach(node=>{node.classList.toggle('selected',node===button);node.setAttribute('aria-pressed',String(node===button));});});
```

选择只影响后续播放，不自动重播，不修改 `state` 或 `displayState`。

- [x] **Step 4: 验证 UI 契约**

Run: `node --test tests/ui-contract.test.js`

Expected: 4 项 UI 测试全部 PASS。

### Task 3: 同步离线导出、文档与完整验证

**Files:**
- Modify: `scripts/export_entrance_poses.mjs`
- Modify: `public/models/entrance-poses.json`
- Modify: `README.md`
- Verify: `docs/decision/20-entrance-front-logo-variant.md`

- [x] **Step 1: 让导出脚本显式支持两个变体**

在 `home` 声明后加入：

```js
const variant=process.argv.find(arg=>arg.startsWith('--variant='))?.split('=')[1]??'front-logo';
if(!['front-logo','direct'].includes(variant))throw new Error(`未知开场变体：${variant}`);
```

将位姿调用改为：

```js
    const p=entrancePose(Math.min(animTime,ENTRANCE_DURATION),home,variant);
```

将输出路径和日志改为：

```js
const out=variant==='direct'?'public/models/entrance-poses-direct.json':'public/models/entrance-poses.json';
writeFileSync(out,JSON.stringify(frames,null,0));
console.log(`导出 ${frames.length} 帧到 ${out}（variant=${variant}，BULLET_DURATION=${BULLET_DURATION}s，含子弹时间）`);
```

- [x] **Step 2: 生成默认车头 Logo 版位姿**

Run: `node scripts/export_entrance_poses.mjs`

Expected: 导出 241 帧到 `public/models/entrance-poses.json`，日志包含 `variant=front-logo` 和 `BULLET_DURATION=10s`。

Run: `node scripts/export_entrance_poses.mjs --variant=direct`

Expected: 导出 241 帧到 `public/models/entrance-poses-direct.json`，用于验证直回版仍可导出；验证后删除该临时生成文件，不纳入本次长期资产。

- [x] **Step 3: 更新 README**

README 必须准确说明：默认开场为“大弧转入 → 尾灯特写 → 单侧弧线到车头 Logo → 拉远回展台”，欢迎页可切换“直回 / 车头特写”，实际时长约 10 秒、241 帧。离线默认命令导出头 Logo 版；`node scripts/export_entrance_poses.mjs --variant=direct` 可导出直回版到 `public/models/entrance-poses-direct.json`。删除已过时的“只做直接缓回”或“掠过两侧”描述，保留无关内容。

- [x] **Step 4: 完整自动验证**

Run: `npm test`

Expected: 88 项测试全部 PASS，0 项 FAIL。

Run: `npm run build`

Expected: 构建成功，退出码 0；仅允许已有大 chunk 提示。

Run: `git diff --check`

Expected: 无空白错误。

- [x] **Step 5: 浏览器分别验证两版**

打开 `http://localhost:5173`，默认重播应出现车头 Logo 特写再回展台；切到“直回”后重播应保持决策 19 的直接回位。两版结束后最终取景与鼠标交互均正常，控制台无新增错误。
