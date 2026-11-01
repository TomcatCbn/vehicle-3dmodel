// 导出欢迎页开场动画每帧位姿为 JSON，供 Blender 渲染视频使用。
// 单一数据源：entrance.js 的 entrancePose + 子弹时间重映射，Blender 只读取不重新实现。
// 按真实播放时间采样（含 logo 段慢动作），这样 Blender 渲染的视频和应用内一致。
import * as THREE from 'three';
import { entrancePose, ENTRANCE_DURATION, BULLET_DURATION } from '../src/render/entrance.js';

const home = new THREE.Vector3(-7.4, 2.5, 9.8);
const variant=process.argv.find(arg=>arg.startsWith('--variant='))?.split('=')[1]??'front-logo';
if(!['front-logo','direct'].includes(variant))throw new Error(`未知开场变体：${variant}`);

// 复刻 entrance.js 的子弹时间重映射（real elapsed → animTime）。
const _seg = ENTRANCE_DURATION;
function animTimeFor(elapsed){
  if(elapsed<=0)return 0;
  if(elapsed>=BULLET_DURATION)return _seg;
  if(elapsed<1.5) return (elapsed/1.5)*(0.30*_seg);
  if(elapsed<4.0) return 0.30*_seg + ((elapsed-1.5)/(4.0-1.5))*(0.12*_seg);
  return 0.42*_seg + ((elapsed-4.0)/(BULLET_DURATION-4.0))*(0.58*_seg);
}

const frames = [];
const fps = 24;
const total = Math.round(BULLET_DURATION * fps); // 10s @24fps = 241 帧（含首帧）
for (let i = 0; i <= total; i++) {
  const realTime = (i / total) * BULLET_DURATION;
  const animTime = animTimeFor(realTime);
  const p = entrancePose(Math.min(animTime, ENTRANCE_DURATION), home, variant);
  frames.push({
    frame: i + 1,
    time: realTime,
    animTime,
    pos: [p.position.x, p.position.y, p.position.z],
    yaw: p.yaw,
    cam: [p.camera.x, p.camera.y, p.camera.z],
    tgt: [p.target.x, p.target.y, p.target.z],
    fov: p.fov,
    wheel: { fl: p.wheelAngles.fl, fr: p.wheelAngles.fr, rl: p.wheelAngles.rl, rr: p.wheelAngles.rr },
    steer: { fl: p.steeringByWheel.fl, fr: p.steeringByWheel.fr },
    phase: p.phase,
  });
}
import { writeFileSync } from 'fs';
const out=variant==='direct'?'public/models/entrance-poses-direct.json':'public/models/entrance-poses.json';
writeFileSync(out,JSON.stringify(frames,null,0));
console.log(`导出 ${frames.length} 帧到 ${out}（variant=${variant}，BULLET_DURATION=${BULLET_DURATION}s，含子弹时间）`);
// 验证 logo 段慢动作：realTime 1.5~4.0 应映射到 animTime 2.64~3.70（logo 段，压缩）
console.log('logo段起点 realTime=1.5 animTime=', animTimeFor(1.5).toFixed(2));
console.log('logo段中点 realTime=2.75 animTime=', animTimeFor(2.75).toFixed(2));
console.log('logo段终点 realTime=4.0 animTime=', animTimeFor(4.0).toFixed(2));
