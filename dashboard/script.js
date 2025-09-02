// Base API
const API_BASE = "localhost:5000/api";

let autoRefreshEnabled = true;
let refreshTimer = null;
let dht22Chart, systemChart, rackChart;

// --- Helpers ---
function getEl(id) {
  return document.getElementById(id);
}
function formatTime(ts) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
function formatDateTime(ts) {
  return new Date(ts).toLocaleString();
}
function showError(msg) {
  console.error(msg);
  const n = getEl('notifications');
  if (n) {
    const div = document.createElement('div');
    div.className = 'error';
    div.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${msg}`;
    n.appendChild(div);
    setTimeout(() => div.remove(), 4000);
  }
}

// --- Chart setup ---
function createChart(ctx, datasets, options) {
  return new Chart(ctx, {
    type: 'line',
    data: { labels: [], datasets },
    options
  });
}
function initCharts() {
  const baseOpt = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { position: 'top' } },
    scales: { x: { ticks: { color: '#64748b' } }, y: { ticks: { color: '#64748b' } } }
  };

  const dhtEl = getEl('dht22Chart');
  if (dhtEl) {
    dht22Chart = createChart(dhtEl.getContext('2d'), [
      { label: 'Temperature (°C)', data: [], borderColor: 'red' },
      { label: 'Humidity (%)', data: [], borderColor: 'blue', yAxisID: 'y1' }
    ], baseOpt);
  }
  const sysEl = getEl('systemChart');
  if (sysEl) {
    systemChart = createChart(sysEl.getContext('2d'), [
      { label: 'RAM (%)', data: [], borderColor: 'purple' },
      { label: 'CPU (%)', data: [], borderColor: 'orange' },
      { label: 'Storage (%)', data: [], borderColor: 'green' }
    ], baseOpt);
  }
  const rackEl = getEl('rackChart');
  if (rackEl) {
    rackChart = createChart(rackEl.getContext('2d'), [
      { label: 'Rack Temp (°C)', data: [], borderColor: 'orange' },
      { label: 'Rack Humidity (%)', data: [], borderColor: 'cyan', yAxisID: 'y1' }
    ], baseOpt);
  }
}

// --- Fetchers ---
async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function refreshData() {
  try {
    const [latest, summary, power, analysis] = await Promise.all([
      fetchJson(`${API_BASE}/latest?limit=20`).catch(() => null),
      fetchJson(`${API_BASE}/summary`).catch(() => null),
      fetchJson(`${API_BASE}/power_flow`).catch(() => null),
      fetchJson(`${API_BASE}/analysis`).catch(() => null),
    ]);

    if (latest?.success) updateDashboard(latest.data);
    if (summary?.success) getEl('totalRecords').textContent = summary.data.total_records || 0;
    if (power?.success) updatePowerFlow(power.data);
    if (analysis?.success) updateAnalysis(analysis.data);

    updateCharts();
    const lu = getEl('lastUpdate');
    if (lu) lu.textContent = new Date().toLocaleTimeString();
  } catch (e) {
    showError(e.message);
  }
}

async function updateCharts() {
  try {
    const [dht, sys, rack] = await Promise.all([
      dht22Chart ? fetchJson(`${API_BASE}/timeseries/dht22?hours=6`).catch(() => null) : null,
      systemChart ? fetchJson(`${API_BASE}/timeseries/system?hours=6`).catch(() => null) : null,
      rackChart ? fetchJson(`${API_BASE}/timeseries/rack?hours=6`).catch(() => null) : null,
    ]);

    if (dht?.success && dht22Chart) {
      const data = dht.data;
      dht22Chart.data.labels = data.map(d => formatTime(d.timestamp));
      dht22Chart.data.datasets[0].data = data.map(d => d.temperature);
      dht22Chart.data.datasets[1].data = data.map(d => d.humidity);
      dht22Chart.update();
    }
    if (sys?.success && systemChart) {
      const data = sys.data;
      systemChart.data.labels = data.map(d => formatTime(d.timestamp));
      systemChart.data.datasets[0].data = data.map(d => d.ram_usage_percent);
      systemChart.data.datasets[1].data = data.map(d => d.cpu_usage_percent);
      systemChart.data.datasets[2].data = data.map(d => d.storage_usage_percent);
      systemChart.update();
    }
    if (rack?.success && rackChart) {
      const data = rack.data;
      rackChart.data.labels = data.map(d => formatTime(d.timestamp));
      rackChart.data.datasets[0].data = data.map(d => d.temperature);
      rackChart.data.datasets[1].data = data.map(d => d.humidity);
      rackChart.update();
    }
  } catch (e) {
    console.error(e);
  }
}

// --- Dashboard Updates ---
function updateDashboard(d) {
  if (d.dht22?.length) updateDHT22(d.dht22.at(-1));
  if (d.system?.length) updateSystem(d.system.at(-1));
  if (d.rack) updateRack(d.rack);
}
function updateDHT22(d) {
  const s = getEl('dht22Status'), el = getEl('dht22Data');
  if (!s || !el) return;
  s.textContent = d.status === 'success' ? 'Online' : 'Error';
  el.textContent = `Temp: ${d.temperature}°C, Hum: ${d.humidity}%`;
}
function updateSystem(d) {
  const s = getEl('systemStatus'), el = getEl('systemData');
  if (!s || !el) return;
  s.textContent = d.status === 'success' ? 'Online' : 'Error';
  el.textContent = `CPU ${d.cpu_usage_percent}%, RAM ${d.ram_usage_percent}%`;
}
function updateRack(d) {
  const s = getEl('rackStatus'), el = getEl('rackData');
  if (!s || !el) return;
  s.textContent = d.status === 'ONLINE' ? 'Online' : 'Offline';
  el.textContent = `Temp: ${d.temperature || '-'}°C, Hum: ${d.humidity || '-'}%`;
}
function updatePowerFlow(d) {
  const el = getEl('powerFlowDiagram');
  if (!el) return;
  el.textContent = `Solar: ${d.solar_input?.power_w || 0}W → AC: ${d.ac_output?.power_w || 0}W`;
}
function updateAnalysis(d) {
  const el = getEl('analysisData');
  if (!el) return;
  el.textContent = JSON.stringify(d);
}

// --- Auto Refresh ---
function toggleAuto() {
  autoRefreshEnabled = !autoRefreshEnabled;
  if (autoRefreshEnabled) startAuto(); else clearInterval(refreshTimer);
}
function startAuto() {
  clearInterval(refreshTimer);
  const interval = parseInt(getEl('refreshInterval')?.value) || 5000;
  refreshTimer = setInterval(() => autoRefreshEnabled && refreshData(), interval);
}

// --- Init ---
document.addEventListener('DOMContentLoaded', () => {
  initCharts();
  refreshData();
  startAuto();
  const btn = getEl('autoRefreshBtn');
  if (btn) btn.addEventListener('click', toggleAuto);
});
