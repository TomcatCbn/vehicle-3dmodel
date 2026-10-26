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
