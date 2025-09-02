// Configuration for Docker setup
const API_BASE = 'http://localhost:5000/api';
let autoRefreshEnabled = true;
let refreshTimer = null;
let dht22Chart = null;
let systemChart = null;
let rackChart = null;

// --- Helper Functions ---
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
    console.error('Error:', msg);
    // Optional: show notification to user
    const notification = document.createElement('div');
    notification.className = 'error-notification';
    notification.style.cssText = `
        position: fixed; top: 20px; right: 20px; z-index: 1000;
        background: #ef4444; color: white; padding: 12px 20px;
        border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        max-width: 400px; font-size: 14px;
    `;
    notification.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${msg}`;
    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 5000);
}

// --- Chart Initialization ---
function initCharts() {
    const baseOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'top',
                labels: {
                    usePointStyle: true,
                    padding: 15,
                    font: { size: 12, weight: '600' }
                }
            },
            tooltip: {
                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                titleColor: '#f8fafc',
                bodyColor: '#f8fafc',
                borderColor: '#334155',
                borderWidth: 1,
                cornerRadius: 8
            }
        },
        scales: {
            x: {
                grid: { color: '#e2e8f0' },
                ticks: { color: '#64748b', font: { size: 11 } }
            },
            y: {
                grid: { color: '#e2e8f0' },
                ticks: { color: '#64748b', font: { size: 11 } }
            }
        },
        elements: {
            line: { tension: 0.4, borderWidth: 2 },
            point: { radius: 3, hoverRadius: 6 }
        }
    };

    // DHT22 Chart (dual axis)
    const dht22Ctx = getEl('dht22Chart');
    if (dht22Ctx) {
        dht22Chart = new Chart(dht22Ctx.getContext('2d'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Temperature (°C)',
                    data: [],
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    fill: true,
                    yAxisID: 'y'
                }, {
                    label: 'Humidity (%)',
                    data: [],
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true,
                    yAxisID: 'y1'
                }]
            },
            options: {
                ...baseOptions,
                scales: {
                    ...baseOptions.scales,
                    y: {
                        ...baseOptions.scales.y,
                        position: 'left',
                        title: { display: true, text: 'Temperature (°C)', color: '#ef4444' }
                    },
                    y1: {
                        ...baseOptions.scales.y,
                        position: 'right',
                        title: { display: true, text: 'Humidity (%)', color: '#3b82f6' },
                        grid: { drawOnChartArea: false }
                    }
                }
            }
        });
    }

    // System Chart
    const systemCtx = getEl('systemChart');
    if (systemCtx) {
        systemChart = new Chart(systemCtx.getContext('2d'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'RAM Usage (%)',
                    data: [],
                    borderColor: '#8b5cf6',
                    backgroundColor: 'rgba(139, 92, 246, 0.1)',
                    fill: true
                }, {
                    label: 'CPU Usage (%)',
                    data: [],
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    fill: true
                }, {
                    label: 'Storage Usage (%)',
                    data: [],
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    fill: true
                }]
            },
            options: {
                ...baseOptions,
                scales: {
                    ...baseOptions.scales,
                    y: {
                        ...baseOptions.scales.y,
                        beginAtZero: true,
                        max: 100,
                        title: { display: true, text: 'Usage (%)' }
                    }
                }
            }
        });
    }

    // RACK Chart  
    const rackCtx = getEl('rackChart');
    if (rackCtx) {
        rackChart = new Chart(rackCtx.getContext('2d'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'RACK Temperature (°C)',
                    data: [],
                    borderColor: '#f97316',
                    backgroundColor: 'rgba(249, 115, 22, 0.1)',
                    fill: true,
                    yAxisID: 'y'
                }, {
                    label: 'RACK Humidity (%)',
                    data: [],
                    borderColor: '#06b6d4',
                    backgroundColor: 'rgba(6, 182, 212, 0.1)',
                    fill: true,
                    yAxisID: 'y1'
                }]
            },
            options: {
                ...baseOptions,
                scales: {
                    ...baseOptions.scales,
                    y: {
                        ...baseOptions.scales.y,
                        position: 'left',
                        title: { display: true, text: 'Temperature (°C)', color: '#f97316' }
                    },
                    y1: {
                        ...baseOptions.scales.y,
                        position: 'right',
                        title: { display: true, text: 'Humidity (%)', color: '#06b6d4' },
                        grid: { drawOnChartArea: false }
                    }
                }
            }
        });
    }

    console.log('Charts initialized successfully');
}

// --- API Fetching ---
async function fetchJson(url) {
    try {
        console.log('Fetching:', url);
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('Fetched data from', url, ':', data);
        return data;
    } catch (error) {
        console.error('Fetch error for', url, ':', error);
        throw error;
    }
}

// --- Main Data Refresh ---
async function refreshData() {
    console.log('Starting data refresh...');
    
    try {
        // Fetch latest data
        const latest = await fetchJson(`${API_BASE}/latest?limit=20`);
        if (latest?.success) {
            console.log('Latest data received:', latest.data);
            updateDashboard(latest.data);
        } else {
            console.warn('Latest data fetch failed:', latest);
        }

        // Fetch summary
        const summary = await fetchJson(`${API_BASE}/summary`);
        if (summary?.success) {
            updateStatusBar(summary.data);
        }

        // Update charts
        await updateCharts();

        // Update last update time
        const lastUpdateEl = getEl('lastUpdate');
        if (lastUpdateEl) {
            lastUpdateEl.textContent = new Date().toLocaleTimeString();
        }

        console.log('Data refresh completed successfully');

    } catch (error) {
        showError('Failed to refresh data: ' + error.message);
    }
}

// --- Dashboard Updates ---
function updateDashboard(data) {
    console.log('Updating dashboard with:', data);

    // Update PZEM-016 AC
    if (data.pzem_ac && data.pzem_ac.length > 0) {
        updatePZEMCard('pzem016', data.pzem_ac[0]);
    } else {
        updatePZEMCard('pzem016', null);
    }

    // Update PZEM-017 DC  
    if (data.pzem_dc && data.pzem_dc.length > 0) {
        updatePZEMCard('pzem017', data.pzem_dc[0]);
    } else {
        updatePZEMCard('pzem017', null);
    }

    // Update DHT22
    if (data.dht22 && data.dht22.length > 0) {
        updateDHT22Card(data.dht22[0]);
    } else {
        updateDHT22Card(null);
    }

    // Update System
    if (data.system && data.system.length > 0) {
        updateSystemCard(data.system[0]);
    } else {
        updateSystemCard(null);
    }

    // Update RACK
    if (data.rack) {
        updateRackCard(data.rack);
    } else {
        updateRackCard(null);
    }

    // Update Power Flow
    updatePowerFlowDiagram(data);
}

function updatePZEMCard(deviceId, data) {
    const statusEl = getEl(`${deviceId}Status`);
    const dataEl = getEl(`${deviceId}Data`);
    
    if (!statusEl || !dataEl) {
        console.warn(`PZEM card elements not found for ${deviceId}`);
        return;
    }

    if (!data) {
        statusEl.className = 'status-badge status-error';
        statusEl.textContent = 'No Data';
        dataEl.innerHTML = '<div class="error">No data available</div>';
        return;
    }

    // Update status badge
    statusEl.className = `status-badge status-${data.status === 'success' ? 'success' : 'error'}`;
    statusEl.textContent = data.status === 'success' ? 'Online' : 'Error';

    // Update data content
    if (data.status === 'success' && data.parsed_data?.status === 'success') {
        const parsed = data.parsed_data;
        let content = '';

        if (deviceId === 'pzem016') {
            // PZEM-016 AC readings
            content = `
                <div class="sensor-reading">
                    <span class="reading-label"><i class="fas fa-bolt"></i> AC Voltage</span>
                    <span class="reading-value">${parsed.voltage_v || 0} <span class="reading-unit">V</span></span>
                </div>
                <div class="sensor-reading">
                    <span class="reading-label"><i class="fas fa-plug"></i> AC Current</span>
                    <span class="reading-value">${parsed.current_a || 0} <span class="reading-unit">A</span></span>
                </div>
                <div class="sensor-reading">
                    <span class="reading-label"><i class="fas fa-lightbulb"></i> AC Power</span>
                    <span class="reading-value">${parsed.power_w || 0} <span class="reading-unit">W</span></span>
                </div>
                <div class="sensor-reading">
                    <span class="reading-label"><i class="fas fa-chart-bar"></i> Energy</span>
                    <span class="reading-value">${parsed.energy_kwh || 0} <span class="reading-unit">kWh</span></span>
                </div>
                <div class="sensor-reading">
                    <span class="reading-label"><i class="fas fa-wave-square"></i> Frequency</span>
                    <span class="reading-value">${parsed.frequency_hz || 0} <span class="reading-unit">Hz</span></span>
                </div>
                <div class="sensor-reading">
                    <span class="reading-label"><i class="fas fa-signal"></i> Power Factor</span>
                    <span class="reading-value">${parsed.power_factor || 0}</span>
                </div>
            `;
        } else if (deviceId === 'pzem017') {
            // PZEM-017 DC readings
            content = `
                <div class="sensor-reading">
                    <span class="reading-label"><i class="fas fa-sun"></i> Solar Voltage</span>
                    <span class="reading-value">${parsed.voltage_v || 0} <span class="reading-unit">V</span></span>
                </div>
                <div class="sensor-reading">
                    <span class="reading-label"><i class="fas fa-battery-half"></i> Solar Current</span>
                    <span class="reading-value">${parsed.current_a || 0} <span class="reading-unit">A</span></span>
                </div>
                <div class="sensor-reading">
                    <span class="reading-label"><i class="fas fa-bolt"></i> Solar Power</span>
                    <span class="reading-value">${parsed.power_w || 0} <span class="reading-unit">W</span></span>
                </div>
                <div class="sensor-reading">
                    <span class="reading-label"><i class="fas fa-chart-line"></i> Energy</span>
                    <span class="reading-value">${parsed.energy_kwh || 0} <span class="reading-unit">kWh</span></span>
                </div>
                <div class="sensor-reading">
                    <span class="reading-label"><i class="fas fa-solar-panel"></i> Status</span>
                    <span class="reading-value">${parsed.solar_status || 'Unknown'}</span>
                </div>
            `;
        }

        content += `<div class="timestamp">
            <i class="fas fa-clock"></i> ${formatDateTime(data.timestamp)}
        </div>`;

        dataEl.innerHTML = content;
    } else {
        // Error state
        dataEl.innerHTML = `
            <div class="error">
                <i class="fas fa-exclamation-circle"></i>
                <strong>Error:</strong> ${data.error_message || 'Failed to read sensor'}
            </div>
            <div class="timestamp">
                <i class="fas fa-clock"></i> ${formatDateTime(data.timestamp)}
            </div>
        `;
    }
}

function updateDHT22Card(data) {
    const statusEl = getEl('dht22Status');
    const dataEl = getEl('dht22Data');

    if (!statusEl || !dataEl) return;

    if (!data) {
        statusEl.className = 'status-badge status-error';
        statusEl.textContent = 'No Data';
        dataEl.innerHTML = '<div class="error">No data available</div>';
        return;
    }

    statusEl.className = `status-badge status-${data.status === 'success' ? 'success' : 'error'}`;
    statusEl.textContent = data.status === 'success' ? 'Online' : 'Error';

    if (data.status === 'success') {
        dataEl.innerHTML = `
            <div class="sensor-reading">
                <span class="reading-label"><i class="fas fa-thermometer-half"></i> Temperature</span>
                <span class="reading-value">${data.temperature || 0}<span class="reading-unit">°C</span></span>
            </div>
            <div class="sensor-reading">
                <span class="reading-label"><i class="fas fa-tint"></i> Humidity</span>
                <span class="reading-value">${data.humidity || 0}<span class="reading-unit">%</span></span>
            </div>
            <div class="timestamp">
                <i class="fas fa-clock"></i> ${formatDateTime(data.timestamp)}
            </div>
        `;
    } else {
        dataEl.innerHTML = `
            <div class="error">
                <i class="fas fa-exclamation-circle"></i>
                <strong>Error:</strong> ${data.error_message || 'Sensor read failed'}
            </div>
            <div class="timestamp">
                <i class="fas fa-clock"></i> ${formatDateTime(data.timestamp)}
            </div>
        `;
    }
}

function updateSystemCard(data) {
    const statusEl = getEl('systemStatus');
    const dataEl = getEl('systemData');

    if (!statusEl || !dataEl) return;

    if (!data) {
        statusEl.className = 'status-badge status-error';
        statusEl.textContent = 'No Data';
        dataEl.innerHTML = '<div class="error">No data available</div>';
        return;
    }

    statusEl.className = `status-badge status-${data.status === 'success' ? 'success' : 'error'}`;
    statusEl.textContent = data.status === 'success' ? 'Online' : 'Error';

    if (data.status === 'success') {
        dataEl.innerHTML = `
            <div class="sensor-reading">
                <span class="reading-label"><i class="fas fa-memory"></i> RAM Usage</span>
                <span class="reading-value">${data.ram_usage_percent || 0}<span class="reading-unit">%</span></span>
            </div>
            <div class="sensor-reading">
                <span class="reading-label"><i class="fas fa-microchip"></i> CPU Usage</span>
                <span class="reading-value">${data.cpu_usage_percent || 0}<span class="reading-unit">%</span></span>
            </div>
            <div class="sensor-reading">
                <span class="reading-label"><i class="fas fa-hdd"></i> Storage</span>
                <span class="reading-value">${data.storage_usage_percent || 0}<span class="reading-unit">%</span></span>
            </div>
            <div class="sensor-reading">
                <span class="reading-label"><i class="fas fa-thermometer-quarter"></i> CPU Temp</span>
                <span class="reading-value">${data.cpu_temperature || 0}<span class="reading-unit">°C</span></span>
            </div>
            <div class="timestamp">
                <i class="fas fa-clock"></i> ${formatDateTime(data.timestamp)}
            </div>
        `;
    } else {
        dataEl.innerHTML = `
            <div class="error">
                <i class="fas fa-exclamation-circle"></i>
                <strong>Error:</strong> ${data.error_message || 'System monitoring failed'}
            </div>
            <div class="timestamp">
                <i class="fas fa-clock"></i> ${formatDateTime(data.timestamp)}
            </div>
        `;
    }
}

function updateRackCard(data) {
    const statusEl = getEl('rackStatus');
    const dataEl = getEl('rackData');

    if (!statusEl || !dataEl) return;

    if (!data) {
        statusEl.className = 'status-badge status-error';
        statusEl.textContent = 'No Data';
        dataEl.innerHTML = '<div class="error">No RACK data available</div>';
        return;
    }

    const isOnline = data.status === 'ONLINE';
    statusEl.className = `status-badge status-${isOnline ? 'success' : 'error'}`;
    statusEl.textContent = isOnline ? 'Online' : 'Offline';

    dataEl.innerHTML = `
        <div class="sensor-reading">
            <span class="reading-label"><i class="fas fa-power-off"></i> Status</span>
            <span class="control-status ${isOnline ? 'online' : 'offline'}">${data.status || 'Unknown'}</span>
        </div>
        <div class="sensor-reading">
            <span class="reading-label"><i class="fas fa-lightbulb"></i> Lamp</span>
            <span class="control-status ${data.lamp === 'ON' ? 'on' : 'off'}">${data.lamp || 'OFF'}</span>
        </div>
        <div class="sensor-reading">
            <span class="reading-label"><i class="fas fa-fan"></i> Exhaust</span>
            <span class="control-status ${data.exhaust === 'ON' ? 'on' : 'off'}">${data.exhaust || 'OFF'}</span>
        </div>
        <div class="sensor-reading">
            <span class="reading-label"><i class="fas fa-thermometer-half"></i> Temperature</span>
            <span class="reading-value">${data.temperature || '--'}<span class="reading-unit">°C</span></span>
        </div>
        <div class="sensor-reading">
            <span class="reading-label"><i class="fas fa-tint"></i> Humidity</span>
            <span class="reading-value">${data.humidity || '--'}<span class="reading-unit">%</span></span>
        </div>
        <div class="timestamp">
            <i class="fas fa-clock"></i> ${formatDateTime(data.last_update)}
        </div>
    `;
}

function updatePowerFlowDiagram(data) {
    const statusEl = getEl('powerFlowStatus');
    const diagramEl = getEl('powerFlowDiagram');

    if (!statusEl || !diagramEl) return;

    // Extract power values
    const solarPower = data.pzem_dc?.[0]?.parsed_data?.power_w || 0;
    const acPower = data.pzem_ac?.[0]?.parsed_data?.power_w || 0;
    const solarVoltage = data.pzem_dc?.[0]?.parsed_data?.voltage_v || 0;
    const acVoltage = data.pzem_ac?.[0]?.parsed_data?.voltage_v || 0;

    statusEl.className = 'status-badge status-success';
    statusEl.textContent = 'Active';

    const solarActive = solarPower > 1;
    const acActive = acPower > 1;

    diagramEl.innerHTML = `
        <div class="power-flow-container">
            <div class="power-node">
                <div class="power-node-icon">☀️</div>
                <div class="power-node-label">Solar Panel</div>
                <div class="power-node-value">${solarPower.toFixed(1)}W</div>
                <div class="power-node-detail">${solarVoltage.toFixed(1)}V</div>
            </div>
            
            <div class="power-arrow ${solarActive ? '' : 'inactive'}">
                <i class="fas fa-arrow-right"></i>
            </div>
            
            <div class="power-node">
                <div class="power-node-icon">🔋</div>
                <div class="power-node-label">SCC</div>
                <div class="power-node-value">Charge Controller</div>
            </div>
            
            <div class="power-arrow ${acActive ? '' : 'inactive'}">
                <i class="fas fa-arrow-right"></i>
            </div>
            
            <div class="power-node">
                <div class="power-node-icon">🔄</div>
                <div class="power-node-label">Inverter</div>
                <div class="power-node-value">DC→AC</div>
            </div>
            
            <div class="power-arrow ${acActive ? '' : 'inactive'}">
                <i class="fas fa-arrow-right"></i>
            </div>
            
            <div class="power-node">
                <div class="power-node-icon">💡</div>
                <div class="power-node-label">AC Load</div>
                <div class="power-node-value">${acPower.toFixed(1)}W</div>
                <div class="power-node-detail">${acVoltage.toFixed(1)}V</div>
            </div>
        </div>
        
        <div class="efficiency-display">
            <div class="efficiency-value">${solarPower > 0 ? Math.round((acPower / solarPower) * 100) : 0}%</div>
            <div class="efficiency-label">System Efficiency</div>
        </div>
    `;
}

function updateStatusBar(summary) {
    const totalRecordsEl = getEl('totalRecords');
    if (totalRecordsEl && summary.total_records) {
        totalRecordsEl.textContent = summary.total_records.toLocaleString();
    }
}

// --- Chart Updates ---
async function updateCharts() {
    try {
        console.log('Updating charts...');

        // Update DHT22 chart
        if (dht22Chart) {
            const dht22Data = await fetchJson(`${API_BASE}/timeseries/dht22?hours=6`);
            if (dht22Data?.success && dht22Data.data.length > 0) {
                const validData = dht22Data.data.filter(d => d.status === 'success' && d.temperature != null);
                dht22Chart.data.labels = validData.map(d => formatTime(d.timestamp));
                dht22Chart.data.datasets[0].data = validData.map(d => d.temperature);
                dht22Chart.data.datasets[1].data = validData.map(d => d.humidity);
                dht22Chart.update('none');
            }
        }

        // Update System chart
        if (systemChart) {
            const systemData = await fetchJson(`${API_BASE}/timeseries/system?hours=6`);
            if (systemData?.success && systemData.data.length > 0) {
                const validData = systemData.data.filter(d => d.status === 'success');
                systemChart.data.labels = validData.map(d => formatTime(d.timestamp));
                systemChart.data.datasets[0].data = validData.map(d => d.ram_usage_percent || 0);
                systemChart.data.datasets[1].data = validData.map(d => d.cpu_usage_percent || 0);
                systemChart.data.datasets[2].data = validData.map(d => d.storage_usage_percent || 0);
                systemChart.update('none');
            }
        }

        // Update RACK chart
        if (rackChart) {
            const rackData = await fetchJson(`${API_BASE}/timeseries/rack?hours=6`);
            if (rackData?.success && rackData.data.length > 0) {
                const validData = rackData.data.filter(d => d.temperature != null && d.humidity != null);
                rackChart.data.labels = validData.map(d => formatTime(d.timestamp));
                rackChart.data.datasets[0].data = validData.map(d => d.temperature);
                rackChart.data.datasets[1].data = validData.map(d => d.humidity);
                rackChart.update('none');
            }
        }

        console.log('Charts updated successfully');

    } catch (error) {
        console.error('Error updating charts:', error);
    }
}

// --- Auto Refresh Controls ---
function toggleAutoRefresh() {
    autoRefreshEnabled = !autoRefreshEnabled;
    const btn = getEl('autoRefreshBtn');
    
    if (!btn) return;

    if (autoRefreshEnabled) {
        btn.innerHTML = '<i class="fas fa-pause"></i> Pause Auto';
        startAutoRefresh();
    } else {
        btn.innerHTML = '<i class="fas fa-play"></i> Resume Auto';
        if (refreshTimer) {
            clearInterval(refreshTimer);
            refreshTimer = null;
        }
    }
}

function startAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
    }

    const intervalEl = getEl('refreshInterval');
    const interval = parseInt(intervalEl?.value || '10000');
    
    console.log(`Starting auto-refresh with ${interval}ms interval`);
    
    refreshTimer = setInterval(() => {
        if (autoRefreshEnabled) {
            refreshData();
        }
    }, interval);
}

// --- Event Listeners ---
function setupEventListeners() {
    // Auto refresh toggle
    const autoRefreshBtn = getEl('autoRefreshBtn');
    if (autoRefreshBtn) {
        autoRefreshBtn.addEventListener('click', toggleAutoRefresh);
    }

    // Refresh interval change
    const refreshInterval = getEl('refreshInterval');
    if (refreshInterval) {
        refreshInterval.addEventListener('change', () => {
            if (autoRefreshEnabled) {
                startAutoRefresh();
            }
        });
    }

    // Manual refresh button (assuming it exists in HTML)
    const refreshBtn = document.querySelector('[onclick="refreshData()"]');
    if (refreshBtn) {
        refreshBtn.removeAttribute('onclick');
        refreshBtn.addEventListener('click', refreshData);
    }
}

// --- Analysis Update ---
function updateAnalysisSection() {
    const statusEl = getEl('analysisStatus');
    const analysisEl = getEl('analysisData');

    if (!statusEl || !analysisEl) return;

    statusEl.className = 'status-badge status-success';
    statusEl.textContent = 'Updated';

    // Basic analysis placeholder
    analysisEl.innerHTML = `
        <div class="analysis-section">
            <div class="analysis-card">
                <div class="analysis-title">
                    <i class="fas fa-info-circle"></i> System Status
                </div>
                <p>System monitoring is active. All sensors are being tracked.</p>
            </div>
        </div>
    `;
}

// --- Initialization ---
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing dashboard...');
    
    // Initialize charts
    initCharts();
    
    // Setup event listeners
    setupEventListeners();
    
    // Update analysis section
    updateAnalysisSection();
    
    // Initial data load
    console.log('Starting initial data load...');
    refreshData();
    
    // Start auto refresh
    startAutoRefresh();
    
    console.log('Dashboard initialization completed');
});

// --- Additional Utility Functions ---

// Health check function
async function checkAPIHealth() {
    try {
        const health = await fetchJson(`${API_BASE}/health`);
        return health.status === 'ok';
    } catch (error) {
        console.error('API health check failed:', error);
        return false;
    }
}

// Connection status indicator
function updateConnectionStatus(isConnected) {
    // You can add a connection status indicator to the UI if needed
    console.log('Connection status:', isConnected ? 'Connected' : 'Disconnected');
}

// Periodic health check
setInterval(async () => {
    const isHealthy = await checkAPIHealth();
    updateConnectionStatus(isHealthy);
    
    if (!isHealthy) {
        showError('API connection lost. Retrying...');
    }
}, 30000); // Check every 30 seconds

// Export functions for global access (if needed)
window.refreshData = refreshData;
window.toggleAutoRefresh = toggleAutoRefresh;