/* ==========================================================================
   WakeOnCasa - Dashboard Frontend App Engine (Fases 1, 2, 3 & 4)
   ========================================================================== */

let devicesCache = [];
let activeCategory = 'all';
let eventSource = null;

document.addEventListener('DOMContentLoaded', () => {
  initEventListeners();
  loadDevices();
  initSSE();
  checkCloudStatus();
});

function initEventListeners() {
  // Filter Buttons
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      e.currentTarget.classList.add('active');
      activeCategory = e.currentTarget.dataset.category;
      renderDevices();
    });
  });

  // Buttons
  document.getElementById('btn-open-modal').addEventListener('click', openAddModal);
  document.getElementById('btn-refresh-status').addEventListener('click', refreshAllPing);
}

// ==========================================================================
// Real-time Server-Sent Events (SSE)
// ==========================================================================

function initSSE() {
  if (!window.EventSource) return;

  const indicator = document.getElementById('sse-indicator');

  eventSource = new EventSource('/api/stream-status');

  eventSource.onopen = () => {
    if (indicator) {
      indicator.style.display = 'inline-flex';
    }
  };

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'ping_update') {
        applyPingUpdates(data.statuses);
        
        if (data.changes && data.changes.length > 0) {
          data.changes.forEach(change => {
            const isOnline = change.new_status?.online;
            const devName = change.device?.name || 'Dispositivo';
            const msg = isOnline 
              ? `🟢 ${devName} está agora ONLINE!` 
              : `🔴 ${devName} ficou OFFLINE.`;
            showToast(msg, isOnline ? 'success' : 'error');
          });
        }
      }
    } catch (err) {
      console.error('Erro ao processar evento SSE:', err);
    }
  };

  eventSource.onerror = () => {
    if (indicator) {
      indicator.style.display = 'none';
    }
  };
}

function applyPingUpdates(statusMap) {
  if (!statusMap) return;

  devicesCache.forEach(dev => {
    if (statusMap[dev.id]) {
      dev.status = statusMap[dev.id];
      updateDeviceBadgeUI(dev.id, dev.status);
    }
  });
  updateStats();
}

function updateDeviceBadgeUI(deviceId, status) {
  const badge = document.getElementById(`badge-${deviceId}`);
  const statusText = document.getElementById(`status-text-${deviceId}`);
  if (!badge || !statusText) return;

  if (status?.online) {
    badge.className = 'device-badge online';
    statusText.textContent = `Online (${status.latency_ms}ms)`;
  } else {
    badge.className = 'device-badge offline';
    statusText.textContent = 'Offline';
  }
}

// ==========================================================================
// API Fetching & Render
// ==========================================================================

async function loadDevices() {
  try {
    const res = await fetch('/api/devices');
    const data = await res.json();
    devicesCache = data.devices || [];
    renderDevices();
    updateStats();
  } catch (err) {
    showToast('Erro ao carregar dispositivos', 'error');
  }
}

function renderDevices() {
  const grid = document.getElementById('devices-grid');
  const emptyState = document.getElementById('empty-state');

  const filtered = activeCategory === 'all' 
    ? devicesCache 
    : devicesCache.filter(d => d.category === activeCategory);

  if (filtered.length === 0) {
    grid.innerHTML = '';
    emptyState.classList.remove('hidden');
    return;
  }

  emptyState.classList.add('hidden');
  grid.innerHTML = filtered.map(dev => createDeviceCardHTML(dev)).join('');
}

function getCategoryIcon(category) {
  switch (category) {
    case 'server': return 'fa-server';
    case 'tv': return 'fa-tv';
    case 'console': return 'fa-gamepad';
    case 'router': return 'fa-network-wired';
    default: return 'fa-desktop';
  }
}

function createDeviceCardHTML(device) {
  const iconClass = getCategoryIcon(device.category);
  const statusClass = device.status?.online ? 'online' : 'offline';
  const statusText = device.status?.online 
    ? `Online (${device.status.latency_ms}ms)` 
    : 'Offline';

  return `
    <div class="device-card" id="card-${device.id}">
      <div class="card-top">
        <div class="device-icon-box">
          <i class="fa-solid ${iconClass}"></i>
        </div>
        <div class="device-badge ${statusClass}" id="badge-${device.id}">
          <span class="pulse-dot"></span>
          <span id="status-text-${device.id}">${statusText}</span>
        </div>
      </div>

      <div class="device-info">
        <h3>${escapeHtml(device.name)}</h3>
        <div class="device-meta">
          <div class="meta-item">
            <span class="meta-label">IP:</span>
            <span>${device.ip || 'N/A'}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">MAC:</span>
            <span>${device.mac}</span>
          </div>
        </div>
      </div>

      <div class="card-actions">
        <button class="btn-wake" id="btn-wake-${device.id}" onclick="wakeDevice('${device.id}')">
          <i class="fa-solid fa-bolt"></i> LIGAR
        </button>
        <button class="icon-btn" onclick="shutdownDevice('${device.id}')" title="Desligamento Remoto">
          <i class="fa-solid fa-power-off"></i>
        </button>
        <button class="icon-btn" onclick="pingDevice('${device.id}')" title="Testar Conectividade">
          <i class="fa-solid fa-signal"></i>
        </button>
        <button class="icon-btn" onclick="openEditModal('${device.id}')" title="Editar">
          <i class="fa-solid fa-pen-to-square"></i>
        </button>
        <button class="icon-btn danger" onclick="deleteDevice('${device.id}')" title="Excluir">
          <i class="fa-solid fa-trash"></i>
        </button>
      </div>
    </div>
  `;
}

function updateStats() {
  document.getElementById('stat-total').textContent = devicesCache.length;
  
  const onlineCount = devicesCache.filter(d => d.status?.online).length;
  document.getElementById('stat-online').textContent = onlineCount;
  document.getElementById('stat-offline').textContent = devicesCache.length - onlineCount;
}

// ==========================================================================
// Actions: WoL, Shutdown, Ping, Ping All
// ==========================================================================

async function wakeDevice(deviceId) {
  const btn = document.getElementById(`btn-wake-${deviceId}`);
  if (!btn) return;

  btn.classList.add('waking');
  btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ENVIANDO...`;

  try {
    const res = await fetch(`/api/wake/${deviceId}`, { method: 'POST' });
    const data = await res.json();

    if (res.ok) {
      showToast(data.message, 'success');
    } else {
      showToast(data.detail || 'Erro ao ligar dispositivo', 'error');
    }
  } catch (err) {
    showToast('Falha na comunicação com o servidor', 'error');
  } finally {
    setTimeout(() => {
      btn.classList.remove('waking');
      btn.innerHTML = `<i class="fa-solid fa-bolt"></i> LIGAR`;
      pingDevice(deviceId);
    }, 1500);
  }
}

async function shutdownDevice(deviceId) {
  const dev = devicesCache.find(d => d.id === deviceId);
  if (!dev) return;

  if (!confirm(`Deseja realmente enviar comando de desligamento remoto para ${dev.name} (${dev.ip})?`)) return;

  try {
    const res = await fetch(`/api/shutdown/${deviceId}`, { method: 'POST' });
    const data = await res.json();

    if (data.success) {
      showToast(data.message, 'success');
    } else {
      showToast(data.message || 'Falha ao desligar', 'error');
    }
  } catch (err) {
    showToast('Erro de comunicação', 'error');
  }
}

async function pingDevice(deviceId) {
  try {
    const res = await fetch(`/api/ping/${deviceId}`);
    const data = await res.json();

    const devIndex = devicesCache.findIndex(d => d.id === deviceId);
    if (devIndex !== -1) {
      devicesCache[devIndex].status = data.status;
      updateDeviceBadgeUI(deviceId, data.status);
    }
    updateStats();
  } catch (err) {
    console.error('Ping failure:', err);
  }
}

async function refreshAllPing() {
  try {
    const res = await fetch('/api/ping-all');
    const data = await res.json();
    applyPingUpdates(data.statuses);
    showToast('Status de rede atualizados', 'success');
  } catch (err) {
    showToast('Erro ao atualizar status global', 'error');
  }
}

// ==========================================================================
// Network Scan Modal & Auto-Discovery
// ==========================================================================

function openScanModal() {
  document.getElementById('scan-modal').classList.remove('hidden');
  startNetworkScan();
}

function closeScanModal() {
  document.getElementById('scan-modal').classList.add('hidden');
}

async function startNetworkScan() {
  const loading = document.getElementById('scan-loading');
  const resultsContainer = document.getElementById('scan-results');

  loading.classList.remove('hidden');
  resultsContainer.innerHTML = '';

  try {
    const res = await fetch('/api/scan-network');
    const data = await res.json();
    const discovered = data.discovered || [];

    loading.classList.add('hidden');

    if (discovered.length === 0) {
      resultsContainer.innerHTML = '<p class="scan-intro">Nenhum dispositivo ativo encontrado na sub-rede local no momento.</p>';
      return;
    }

    resultsContainer.innerHTML = `
      <table class="scan-results-table">
        <thead>
          <tr>
            <th>Nome / Host</th>
            <th>Endereço IP</th>
            <th>Endereço MAC</th>
            <th>Ação</th>
          </tr>
        </thead>
        <tbody>
          ${discovered.map(dev => `
            <tr>
              <td><strong>${escapeHtml(dev.name)}</strong></td>
              <td><code>${dev.ip}</code></td>
              <td><code>${dev.mac}</code></td>
              <td>
                ${dev.already_added ? `
                  <span class="device-badge online"><i class="fa-solid fa-check"></i> Cadastrado</span>
                ` : `
                  <button class="btn btn-primary btn-sm" onclick="addDiscoveredDevice('${dev.name}', '${dev.ip}', '${dev.mac}')">
                    <i class="fa-solid fa-plus"></i> Adicionar
                  </button>
                `}
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } catch (err) {
    loading.classList.add('hidden');
    resultsContainer.innerHTML = '<p class="scan-intro" style="color: var(--danger);">Erro ao realizar varredura de rede.</p>';
  }
}

async function addDiscoveredDevice(name, ip, mac) {
  const payload = {
    name: name,
    ip: ip,
    mac: mac,
    category: 'desktop',
    notes: 'Adicionado via Varredura de Rede'
  };

  try {
    const res = await fetch('/api/devices', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      showToast(`Dispositivo ${name} adicionado!`, 'success');
      loadDevices();
      startNetworkScan();
    } else {
      showToast('Erro ao cadastrar dispositivo', 'error');
    }
  } catch (err) {
    showToast('Falha na comunicação', 'error');
  }
}

// ==========================================================================
// Settings & Webhooks Modal
// ==========================================================================

async function openSettingsModal() {
  try {
    const res = await fetch('/api/settings');
    const cfg = await res.json();

    document.getElementById('setting-interval').value = cfg.ping_interval_seconds || 10;
    document.getElementById('setting-webhook').value = cfg.webhook_url || '';
    document.getElementById('setting-firebase-url').value = cfg.firebase_database_url || '';
    document.getElementById('setting-firebase-secret').value = cfg.firebase_auth_secret || '';
    document.getElementById('setting-notify-online').checked = cfg.notify_online !== false;
    document.getElementById('setting-notify-offline').checked = cfg.notify_offline !== false;

    document.getElementById('settings-modal').classList.remove('hidden');
  } catch (err) {
    showToast('Erro ao carregar configurações', 'error');
  }
}

function closeSettingsModal() {
  document.getElementById('settings-modal').classList.add('hidden');
}

async function handleSettingsSubmit(event) {
  event.preventDefault();

  const payload = {
    ping_interval_seconds: parseInt(document.getElementById('setting-interval').value) || 10,
    webhook_url: document.getElementById('setting-webhook').value,
    firebase_database_url: document.getElementById('setting-firebase-url').value,
    firebase_auth_secret: document.getElementById('setting-firebase-secret').value,
    notify_online: document.getElementById('setting-notify-online').checked,
    notify_offline: document.getElementById('setting-notify-offline').checked,
  };

  try {
    const res = await fetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      showToast('Configurações salvas com sucesso!', 'success');
      closeSettingsModal();
    } else {
      showToast('Erro ao salvar configurações', 'error');
    }
  } catch (err) {
    showToast('Falha na conexão', 'error');
  }
}

// ==========================================================================
// Device CRUD Modals
// ==========================================================================

function openAddModal() {
  document.getElementById('modal-title').innerHTML = '<i class="fa-solid fa-plus-circle"></i> Adicionar Dispositivo';
  document.getElementById('device-id').value = '';
  document.getElementById('device-name').value = '';
  document.getElementById('device-ip').value = '';
  document.getElementById('device-mac').value = '';
  document.getElementById('device-category').value = 'desktop';
  document.getElementById('device-notes').value = '';
  document.getElementById('device-modal').classList.remove('hidden');
}

function openEditModal(deviceId) {
  const dev = devicesCache.find(d => d.id === deviceId);
  if (!dev) return;

  document.getElementById('modal-title').innerHTML = '<i class="fa-solid fa-pen-to-square"></i> Editar Dispositivo';
  document.getElementById('device-id').value = dev.id;
  document.getElementById('device-name').value = dev.name;
  document.getElementById('device-ip').value = dev.ip;
  document.getElementById('device-mac').value = dev.mac;
  document.getElementById('device-category').value = dev.category || 'desktop';
  document.getElementById('device-notes').value = dev.notes || '';
  document.getElementById('device-modal').classList.remove('hidden');
}

function closeModal() {
  document.getElementById('device-modal').classList.add('hidden');
}

async function handleFormSubmit(event) {
  event.preventDefault();
  
  const id = document.getElementById('device-id').value;
  const payload = {
    name: document.getElementById('device-name').value,
    ip: document.getElementById('device-ip').value,
    mac: document.getElementById('device-mac').value,
    category: document.getElementById('device-category').value,
    notes: document.getElementById('device-notes').value,
  };

  try {
    let res;
    if (id) {
      res = await fetch(`/api/devices/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    } else {
      res = await fetch('/api/devices', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    }

    if (res.ok) {
      showToast(id ? 'Dispositivo atualizado!' : 'Dispositivo cadastrado!', 'success');
      closeModal();
      loadDevices();
    } else {
      const errData = await res.json();
      showToast(errData.detail || 'Erro ao salvar dispositivo', 'error');
    }
  } catch (err) {
    showToast('Erro de comunicação com a API', 'error');
  }
}

async function deleteDevice(deviceId) {
  if (!confirm('Deseja realmente excluir este dispositivo?')) return;

  try {
    const res = await fetch(`/api/devices/${deviceId}`, { method: 'DELETE' });
    if (res.ok) {
      showToast('Dispositivo removido', 'success');
      loadDevices();
    } else {
      showToast('Erro ao remover dispositivo', 'error');
    }
  } catch (err) {
    showToast('Falha ao comunicar exclusão', 'error');
  }
}

// ==========================================================================
// Utilities
// ==========================================================================

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <i class="fa-solid ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}"></i>
    <span>${escapeHtml(message)}</span>
  `;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

async function checkCloudStatus() {
  const el = document.getElementById('cloud-indicator');
  const txt = document.getElementById('cloud-status-text');
  if (!el || !txt) return;

  try {
    const res = await fetch('/api/health');
    const data = await res.json();
    if (data.firebase_connected) {
      el.className = 'cloud-indicator connected';
      txt.textContent = 'Nuvem Sync: Ok';
    } else if (data.firebase_enabled) {
      el.className = 'cloud-indicator disconnected';
      txt.textContent = 'Nuvem Sync: Conectando...';
    } else {
      el.className = 'cloud-indicator disconnected';
      txt.textContent = 'Nuvem: Off';
    }
  } catch (err) {
    if (el && txt) {
      el.className = 'cloud-indicator disconnected';
      txt.textContent = 'Nuvem: Off';
    }
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/[&<>"']/g, match => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[match]));
}
