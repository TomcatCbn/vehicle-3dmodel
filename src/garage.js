// Garage page — vehicle instance management (decision 08 D8.9/D8.10).
// Dual-mode: Tauri invoke for desktop, localStorage fallback for browser dev.

import { invoke } from './tauri-bridge.js';

function tauriAvailable() {
  return typeof window !== 'undefined' &&
         Boolean(window.__TAURI__) &&
         Boolean(window.__TAURI__?.core?.invoke);
}

// ── localStorage fallback (browser mode) ──
const LS_INSTANCES = 'vehicle-sim:instances';
const LS_LAST = 'vehicle-sim:last-instance';

function localListInstances() {
  try { return JSON.parse(localStorage.getItem(LS_INSTANCES) || '[]'); } catch { return []; }
}
function localSaveInstances(list) {
  localStorage.setItem(LS_INSTANCES, JSON.stringify(list));
}
function localListTemplates() {
  return [{
    name: 'aura-t6',
    display_name: 'AURA T6',
    model_path: '/models/aura-t6.glb',
    positions: ['fl', 'fr', 'rl', 'rr'],
    has_sunroof: true,
    has_tailgate: true,
    has_hood: true,
  }];
}

// ── Data access ──

async function getTemplates() {
  if (tauriAvailable()) {
    try { return await invoke('profile_list_templates'); } catch { return []; }
  }
  return localListTemplates();
}

async function getInstances() {
  if (tauriAvailable()) {
    try { return await invoke('profile_list_instances'); } catch { return []; }
  }
  return localListInstances();
}

async function createInstance(template, displayName, vin) {
  if (tauriAvailable()) {
    return await invoke('profile_create_instance', { template, displayName, vin });
  }
  const list = localListInstances();
  const instance = {
    id: `${template}-${Date.now()}`,
    template,
    display_name: displayName,
    vin,
    created_at: new Date().toISOString(),
  };
  list.push(instance);
  localSaveInstances(list);
  return instance;
}

async function deleteInstance(id) {
  if (tauriAvailable()) {
    return await invoke('profile_delete_instance', { id });
  }
  localSaveInstances(localListInstances().filter(i => i.id !== id));
}

export async function getLastInstanceId() {
  if (tauriAvailable()) {
    try { return await invoke('profile_get_last_instance'); } catch { return null; }
  }
  return localStorage.getItem(LS_LAST) || null;
}

async function setLastInstanceId(id) {
  if (tauriAvailable()) {
    return await invoke('profile_set_last_instance', { id });
  }
  localStorage.setItem(LS_LAST, id);
}

// ── Rendering ──

function formatDate(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' });
  } catch { return ''; }
}

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

export async function renderGarage() {
  const garagePage = document.getElementById('garage-page');
  if (!garagePage) return;

  const instances = await getInstances();

  if (instances.length === 0) {
    garagePage.innerHTML = `
      <div class="garage-empty">
        <span class="eyebrow">GARAGE</span>
        <h2>我的车库</h2>
        <p>${tauriAvailable() ? '还没有车辆实例' : '浏览器模式下实例保存在本地'}</p>
        <button id="garage-add" class="garage-add-btn">+ 添加车辆</button>
      </div>`;
  } else {
    const cards = instances.map(inst => `
      <article class="garage-card" data-instance-id="${escapeHtml(inst.id)}">
        <div class="garage-card-header">
          <span class="garage-card-template">${escapeHtml(inst.template)}</span>
          <button class="garage-card-delete" data-delete-id="${escapeHtml(inst.id)}" aria-label="删除车辆" title="删除">×</button>
        </div>
        <h3 class="garage-card-name">${escapeHtml(inst.display_name)}</h3>
        <dl class="garage-card-meta">
          <dt>VIN</dt><dd>${escapeHtml(inst.vin || '—')}</dd>
          <dt>创建</dt><dd>${formatDate(inst.created_at)}</dd>
        </dl>
        <button class="garage-card-select" data-select-id="${escapeHtml(inst.id)}">选择此车辆 →</button>
      </article>`).join('');

    garagePage.innerHTML = `
      <div class="garage-content">
        <header class="garage-header">
          <div><span class="eyebrow">GARAGE</span><h2>我的车库</h2></div>
          <button id="garage-add" class="garage-add-btn">+ 添加车辆</button>
        </header>
        <div class="garage-grid">${cards}</div>
      </div>`;
  }

  // Wire up the add button.
  document.getElementById('garage-add')?.addEventListener('click', openCreateDialog);

  // Wire up select and delete buttons.
  for (const btn of garagePage.querySelectorAll('[data-select-id]')) {
    btn.addEventListener('click', () => selectInstance(btn.dataset.selectId));
  }
  for (const btn of garagePage.querySelectorAll('[data-delete-id]')) {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.deleteId;
      if (!confirm('确定删除这辆车吗？')) return;
      await deleteInstance(id);
      await renderGarage();
    });
  }
}

async function selectInstance(id) {
  await setLastInstanceId(id);
  selectedInstanceId = id;
  // Navigate to car page.
  document.querySelector('[data-page="car"]')?.click();
}

// Track selected instance for the car page.
let selectedInstanceId = null;
export function getSelectedInstanceId() { return selectedInstanceId; }

// ── Create dialog ──

let createDialog = null;
let createStep = 'template'; // 'template' | 'form'
let selectedTemplate = null;

function ensureCreateDialog() {
  if (createDialog) return createDialog;
  createDialog = document.createElement('dialog');
  createDialog.id = 'garage-create-dialog';
  createDialog.setAttribute('aria-labelledby', 'garage-create-title');
  createDialog.className = 'garage-create-dialog';
  document.body.appendChild(createDialog);
  return createDialog;
}

async function openCreateDialog() {
  const dialog = ensureCreateDialog();
  createStep = 'template';
  selectedTemplate = null;
  await renderCreateStep();
  if (!dialog.open) dialog.showModal();
}

async function renderCreateStep() {
  const dialog = ensureCreateDialog();

  if (createStep === 'template') {
    const templates = await getTemplates();
    const templateCards = templates.map(t => `
      <button class="garage-template-card" data-template-name="${escapeHtml(t.name)}">
        <span class="garage-template-name">${escapeHtml(t.display_name)}</span>
        <span class="garage-template-info">${t.positions.length} 门 · ${t.has_sunroof ? '天窗' : '无天窗'} · ${t.has_tailgate ? '电动尾门' : '无尾门'}</span>
      </button>`).join('');

    dialog.innerHTML = `
      <header class="garage-create-header">
        <h2 id="garage-create-title">选择车型</h2>
        <button class="garage-create-close" data-close aria-label="关闭">×</button>
      </header>
      <div class="garage-create-body">
        <p class="garage-create-hint">选择一个车型模板来创建车辆实例</p>
        <div class="garage-template-list">${templateCards}</div>
      </div>`;

    dialog.querySelectorAll('[data-template-name]').forEach(btn => {
      btn.addEventListener('click', () => {
        selectedTemplate = btn.dataset.templateName;
        createStep = 'form';
        renderCreateStep();
      });
    });
  } else {
    const templates = await getTemplates();
    const tmpl = templates.find(t => t.name === selectedTemplate);
    const displayName = tmpl ? tmpl.display_name : '';

    dialog.innerHTML = `
      <header class="garage-create-header">
        <h2 id="garage-create-title">创建车辆实例</h2>
        <button class="garage-create-close" data-close aria-label="关闭">×</button>
      </header>
      <div class="garage-create-body">
        <div class="garage-create-form">
          <div class="garage-form-row">
            <label for="garage-vin">车辆识别码 (VIN)</label>
            <input id="garage-vin" type="text" placeholder="如 LSVAA000000000001" maxlength="17" autocomplete="off"/>
          </div>
          <div class="garage-form-row">
            <label for="garage-name">车辆名称</label>
            <input id="garage-name" type="text" placeholder="${escapeHtml(displayName)}" maxlength="32" autocomplete="off"/>
          </div>
          <p class="garage-form-hint">模板：${escapeHtml(selectedTemplate)}</p>
          <div class="garage-form-actions">
            <button class="garage-form-back" data-back>← 返回</button>
            <button class="garage-form-submit" data-submit disabled>创建</button>
          </div>
        </div>
      </div>`;

    const vinInput = dialog.querySelector('#garage-vin');
    const nameInput = dialog.querySelector('#garage-name');
    const submitBtn = dialog.querySelector('[data-submit]');

    const validate = () => {
      submitBtn.disabled = vinInput.value.trim().length < 1;
    };
    vinInput.addEventListener('input', validate);
    vinInput.focus();

    dialog.querySelector('[data-back]').addEventListener('click', () => {
      createStep = 'template';
      renderCreateStep();
    });

    submitBtn.addEventListener('click', async () => {
      const vin = vinInput.value.trim();
      const name = nameInput.value.trim() || displayName;
      if (!vin) return;

      submitBtn.disabled = true;
      submitBtn.textContent = '创建中…';
      try {
        await createInstance(selectedTemplate, name, vin);
        dialog.close();
        await renderGarage();
      } catch (e) {
        submitBtn.disabled = false;
        submitBtn.textContent = '创建';
        const hint = dialog.querySelector('.garage-form-hint');
        if (hint) hint.textContent = `创建失败：${e}`;
      }
    });
  }

  dialog.querySelector('[data-close]')?.addEventListener('click', () => dialog.close());
}

// ── Initialization ──

export async function setupGarage() {
  await renderGarage();

  // Load last selected instance on startup (D8.15).
  const lastId = await getLastInstanceId();
  if (lastId) {
    selectedInstanceId = lastId;
  }
}
