import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

async function html(){
  return readFile(new URL('../index.html',import.meta.url),'utf8');
}

test('lighting console exposes headlight, tail and ambient controls',async()=>{
  const page=await html();
  for(const id of ['headlight-status','headlight-toggle','tail-status','tail-toggle'])assert.match(page,new RegExp(`id="${id}"`),id);
  for(const value of ['off','warm','ice','purple'])assert.match(page,new RegExp(`data-ambient="${value}"`),`ambient ${value}`);
  assert.match(page,/role="switch"[^>]*aria-label="尾灯"/);
  assert.match(page,/role="group"[^>]*aria-label="氛围灯颜色"/);
});

test('driving footer offers forward and reverse direction controls',async()=>{
  const page=await html();
  for(const value of ['1','-1'])assert.match(page,new RegExp(`data-direction="${value}"`),`direction ${value}`);
  for(const id of ['drive-speed-mid','drive-speed-max'])assert.match(page,new RegExp(`id="${id}"`),id);
  assert.match(page,/倒车限速 20 km\/h/);
});

test('garage route removes hidden and file transfer stays openable in browser mode',async()=>{
  const [main,transfer,styles]=await Promise.all([
    readFile(new URL('../src/main.js',import.meta.url),'utf8'),
    readFile(new URL('../src/file-transfer.js',import.meta.url),'utf8'),
    readFile(new URL('../src/style.css',import.meta.url),'utf8'),
  ]);
  assert.match(main,/\$\('#garage-page'\)\.hidden = page !== 'garage'/);
  assert.match(transfer,/btn\.disabled = false/);
  assert.match(transfer,/tauriAvailable\(\) \? '未启动' : '仅桌面'/);
  assert.doesNotMatch(styles,/data-power="sleep"\] \.ft-open/);
});

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
