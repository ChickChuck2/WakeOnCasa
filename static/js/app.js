/* ==========================================================================
   WakeOnCasa - Dashboard Frontend App Engine
   ========================================================================== */

let devicesCache = [];
let activeCategory = 'all';

document.addEventListener('DOMContentLoaded', () => {
  initEventListeners();
  loadDevices();
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
// API Fetching & Render
// ==========================================================================

async function loadDevices() {
  try {
    const res = await fetch('/api/devices');
    const data = await res.json();
    devicesCache = data.devices || [];
    renderDevices();
    updateStats();
    refreshAllPing();
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
            <span>${device.ip}</span>
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
// Actions: WoL, Ping, Ping All
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

async function pingDevice(deviceId) {
  const badge = document.getElementById(`badge-${deviceId}`);
  const statusText = document.getElementById(`status-text-${deviceId}`);

  try {
    const res = await fetch(`/api/ping/${deviceId}`);
    const data = await res.json();

    const devIndex = devicesCache.findIndex(d => d.id === deviceId);
    if (devIndex !== -1) {
      devicesCache[devIndex].status = data.status;
    }

    if (data.status?.online) {
      badge.className = 'device-badge online';
      statusText.textContent = `Online (${data.status.latency_ms}ms)`;
    } else {
      badge.className = 'device-badge offline';
      statusText.textContent = 'Offline';
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
    const statuses = data.statuses || {};

    devicesCache.forEach(dev => {
      if (statuses[dev.id]) {
        dev.status = statuses[dev.id];
        const badge = document.getElementById(`badge-${dev.id}`);
        const statusText = document.getElementById(`status-text-${dev.id}`);

        if (badge && statusText) {
          if (dev.status.online) {
            badge.className = 'device-badge online';
            statusText.textContent = `Online (${dev.status.latency_ms}ms)`;
          } else {
            badge.className = 'device-badge offline';
            statusText.textContent = 'Offline';
          }
        }
      }
    });
    updateStats();
    showToast('Status de rede atualizados', 'success');
  } catch (err) {
    showToast('Erro ao atualizar status global', 'error');
  }
}

// ==========================================================================
// Modal & CRUD Operations
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
