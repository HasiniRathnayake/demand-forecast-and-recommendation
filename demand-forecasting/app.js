/* ═══════════════════════════════════════════════
   Demand Forecasting Dashboard — app.js
   Member: Rathnayake R.M.H.T · IT24100510
   ═══════════════════════════════════════════════ */

const SUPABASE_URL = 'https://obbctmyetrdortxyglle.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9iYmN0bXlldHJkb3J0eHlnbGxlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTY1OTg1MywiZXhwIjoyMDg3MjM1ODUzfQ.uaOYLnsgpN7R4mcbd4qcd8_jY4swh18Cf8sKF063LOg';

const FORECASTS_TABLE = 'demand_forecasts';
const HOLIDAYS_TABLE = 'demand_holidays';

let allForecasts = [];
let allHolidays = [];
let filteredForecasts = [];
let currentPage = 1;
const PAGE_SIZE = 50;
let forecastChart = null;
let editingForecastId = null;
let editingHolidayId = null;

/* ── Supabase helper ─────────────────────────────────────── */
async function sb(path, opts = {}) {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
        headers: {
            apikey: SUPABASE_KEY,
            Authorization: `Bearer ${SUPABASE_KEY}`,
            'Content-Type': 'application/json',
            Prefer: opts.prefer || 'return=representation',
            ...opts.headers
        }, ...opts
    });
    if (!res.ok) throw new Error(`Supabase ${res.status}: ${await res.text()}`);
    const t = await res.text();
    return t ? JSON.parse(t) : null;
}

/* ── Fetch all data ──────────────────────────────────────── */
async function fetchAll() {
    const [f, h] = await Promise.all([
        sb(`${FORECASTS_TABLE}?select=*&order=week_start.desc&limit=2000`),
        sb(`${HOLIDAYS_TABLE}?select=*&order=date.asc&limit=500`)
    ]);
    allForecasts = f || [];
    allHolidays = h || [];
}

/* ── KPIs ────────────────────────────────────────────────── */
function renderKPIs() {
    const total = allForecasts.length;
    const withAct = allForecasts.filter(f => f.actual_qty != null && f.actual_qty > 0);
    const accuracy = withAct.length
        ? (withAct.reduce((s, f) => {
            const acc = 1 - Math.abs((f.predicted_qty - f.actual_qty) / Math.max(f.actual_qty, 1));
            return s + Math.max(0, acc * 100);
        }, 0) / withAct.length)
        : null;
    const today = new Date().toISOString().split('T')[0];
    const upcoming = allHolidays.filter(h => h.date >= today).length;

    document.getElementById('kpi-total').textContent = total.toLocaleString();
    document.getElementById('kpi-accuracy').textContent = accuracy != null ? accuracy.toFixed(1) + '%' : 'N/A';
    document.getElementById('kpi-actuals').textContent = withAct.length.toLocaleString();
    document.getElementById('kpi-holidays').textContent = upcoming;
}

/* ── Chart ───────────────────────────────────────────────── */
function buildChartData(skuFilter) {
    let data = skuFilter ? allForecasts.filter(f => f.sku === skuFilter) : allForecasts;
    // Group by week
    const byWeek = {};
    data.forEach(f => {
        if (!byWeek[f.week_start]) byWeek[f.week_start] = { pred: 0, act: 0 };
        byWeek[f.week_start].pred += f.predicted_qty || 0;
        byWeek[f.week_start].act += f.actual_qty || 0;
    });
    const weeks = Object.keys(byWeek).sort().slice(-12);
    return {
        labels: weeks,
        predicted: weeks.map(w => byWeek[w].pred),
        actual: weeks.map(w => byWeek[w].act)
    };
}

function renderChart(skuFilter) {
    const { labels, predicted, actual } = buildChartData(skuFilter);
    const ctx = document.getElementById('forecast-chart').getContext('2d');
    if (forecastChart) forecastChart.destroy();
    forecastChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Predicted Qty',
                    data: predicted,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59,130,246,0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointHoverRadius: 6
                },
                {
                    label: 'Actual Qty',
                    data: actual,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16,185,129,0.08)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    borderDash: [5, 4]
                }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { labels: { color: '#94a3b8', font: { family: 'Inter', size: 12 } } } },
            scales: {
                x: { ticks: { color: '#475569' }, grid: { color: '#1e2d45' } },
                y: { ticks: { color: '#475569' }, grid: { color: '#1e2d45' } }
            }
        }
    });
}

/* ── Urgent table ────────────────────────────────────────── */
function renderUrgent() {
    const withAct = allForecasts.filter(f => f.actual_qty != null && f.actual_qty > 0);
    const gaps = withAct.map(f => ({ ...f, gap: f.actual_qty - f.predicted_qty }))
        .filter(f => f.gap > 0)
        .sort((a, b) => b.gap - a.gap)
        .slice(0, 10);
    const tbody = document.getElementById('urgent-tbody');
    if (!gaps.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="loading-row">No gaps detected yet — add actual quantities to forecasts.</td></tr>';
        return;
    }
    tbody.innerHTML = gaps.map(f => `
    <tr>
      <td><span class="font-mono">${f.sku}</span></td>
      <td>${f.week_start}</td>
      <td>${(f.predicted_qty || 0).toLocaleString()}</td>
      <td>${(f.actual_qty || 0).toLocaleString()}</td>
      <td class="text-red">+${f.gap.toLocaleString()} units</td>
      <td>${f.holiday_flag ? '<span class="badge badge-pending">🏮 Holiday</span>' : '—'}</td>
    </tr>`).join('');
}

/* ── Forecast table ──────────────────────────────────────── */
function applyFilters() {
    const search = document.getElementById('search-forecast').value.toLowerCase();
    const week = document.getElementById('filter-week').value;
    let data = [...allForecasts];
    if (search) data = data.filter(f => (f.sku || '').toLowerCase().includes(search) || (f.product_name || '').toLowerCase().includes(search));
    if (week) data = data.filter(f => f.week_start === week);
    filteredForecasts = data;
    currentPage = 1;
    renderForecastTable();
}

function renderForecastTable() {
    const start = (currentPage - 1) * PAGE_SIZE;
    const slice = filteredForecasts.slice(start, start + PAGE_SIZE);
    const total = Math.ceil(filteredForecasts.length / PAGE_SIZE);
    const tbody = document.getElementById('forecast-tbody');

    if (!slice.length) {
        tbody.innerHTML = '<tr><td colspan="8" class="loading-row">No forecast records yet. Click "+ Add Forecast" to get started.</td></tr>';
    } else {
        tbody.innerHTML = slice.map(f => {
            const acc = (f.actual_qty != null && f.actual_qty > 0)
                ? Math.max(0, (1 - Math.abs((f.predicted_qty - f.actual_qty) / Math.max(f.actual_qty, 1))) * 100).toFixed(1) + '%'
                : '—';
            return `<tr>
        <td><span class="font-mono">${f.sku}</span></td>
        <td>${f.product_name || '—'}</td>
        <td>${f.week_start}</td>
        <td>${(f.predicted_qty || 0).toLocaleString()}</td>
        <td>${f.actual_qty != null ? f.actual_qty.toLocaleString() : '—'}</td>
        <td>${acc}</td>
        <td>${f.holiday_flag ? '<span class="badge badge-pending">🏮 Yes</span>' : '<span class="badge badge-muted">No</span>'}</td>
        <td>
          <button class="btn-icon" onclick="openForecastModal('${f.id}')">✏️</button>
          <button class="btn-icon" onclick="deleteForecast('${f.id}')">🗑️</button>
        </td>
      </tr>`;
        }).join('');
    }
    document.getElementById('page-info').textContent = `Page ${currentPage} of ${total || 1} (${filteredForecasts.length.toLocaleString()} records)`;
    document.getElementById('btn-prev').disabled = currentPage <= 1;
    document.getElementById('btn-next').disabled = currentPage >= total;
}

/* ── Holidays table ──────────────────────────────────────── */
function renderHolidays() {
    const tbody = document.getElementById('holiday-tbody');
    if (!allHolidays.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="loading-row">No holidays added yet.</td></tr>';
        return;
    }
    const today = new Date().toISOString().split('T')[0];
    tbody.innerHTML = allHolidays.map(h => {
        const upcoming = h.date >= today;
        return `<tr>
      <td>${h.name}</td>
      <td>${h.date}</td>
      <td><span class="badge ${h.impact === 'HIGH' ? 'badge-danger' : h.impact === 'MEDIUM' ? 'badge-pending' : 'badge-info'}">${h.impact}</span></td>
      <td class="text-muted">${h.notes || '—'}</td>
      <td>
        <button class="btn-icon" onclick="openHolidayModal('${h.id}')">✏️</button>
        <button class="btn-icon" onclick="deleteHoliday('${h.id}')">🗑️</button>
      </td>
    </tr>`;
    }).join('');
}

/* ── Week filter options ─────────────────────────────────── */
function populateWeekFilter() {
    const weeks = [...new Set(allForecasts.map(f => f.week_start))].sort().reverse();
    const sel = document.getElementById('filter-week');
    sel.innerHTML = '<option value="">All Weeks</option>' +
        weeks.map(w => `<option value="${w}">${w}</option>`).join('');
}

/* ── SKU chart filter ────────────────────────────────────── */
function populateSkuFilter() {
    const skus = [...new Set(allForecasts.map(f => f.sku))].sort();
    const sel = document.getElementById('chart-sku-filter');
    sel.innerHTML = '<option value="">All SKUs (Aggregated)</option>' +
        skus.map(s => `<option value="${s}">${s}</option>`).join('');
}

/* ── CRUD — Forecast ─────────────────────────────────────── */
function openForecastModal(id) {
    editingForecastId = id || null;
    document.getElementById('forecast-modal-title').textContent = id ? 'Edit Forecast' : 'Add Forecast';
    const f = id ? allForecasts.find(x => x.id === id) : null;
    document.getElementById('fm-id').value = id || '';
    document.getElementById('fm-sku').value = f?.sku || '';
    document.getElementById('fm-name').value = f?.product_name || '';
    document.getElementById('fm-week').value = f?.week_start || new Date().toISOString().split('T')[0];
    document.getElementById('fm-predicted').value = f?.predicted_qty || '';
    document.getElementById('fm-actual').value = f?.actual_qty || '';
    document.getElementById('fm-holiday').value = f?.holiday_flag ? 'true' : 'false';
    document.getElementById('fm-notes').value = f?.notes || '';
    document.getElementById('forecast-modal').classList.add('open');
}

async function saveForecast() {
    const payload = {
        sku: document.getElementById('fm-sku').value.trim(),
        product_name: document.getElementById('fm-name').value.trim(),
        week_start: document.getElementById('fm-week').value,
        predicted_qty: parseInt(document.getElementById('fm-predicted').value) || 0,
        actual_qty: document.getElementById('fm-actual').value ? parseInt(document.getElementById('fm-actual').value) : null,
        holiday_flag: document.getElementById('fm-holiday').value === 'true',
        notes: document.getElementById('fm-notes').value.trim()
    };
    if (!payload.sku || !payload.week_start) { showToast('SKU and Week are required', 'error'); return; }
    try {
        if (editingForecastId) {
            await sb(`${FORECASTS_TABLE}?id=eq.${editingForecastId}`, { method: 'PATCH', body: JSON.stringify(payload), prefer: 'return=minimal' });
            showToast('Forecast updated ✅', 'success');
        } else {
            await sb(FORECASTS_TABLE, { method: 'POST', body: JSON.stringify(payload) });
            showToast('Forecast added ✅', 'success');
        }
        document.getElementById('forecast-modal').classList.remove('open');
        await refresh();
    } catch (e) { showToast('Error: ' + e.message, 'error'); }
}

async function deleteForecast(id) {
    if (!confirm('Delete this forecast?')) return;
    await sb(`${FORECASTS_TABLE}?id=eq.${id}`, { method: 'DELETE', prefer: 'return=minimal' });
    showToast('Deleted', 'info');
    await refresh();
}

/* ── CRUD — Holidays ─────────────────────────────────────── */
function openHolidayModal(id) {
    editingHolidayId = id || null;
    document.getElementById('holiday-modal-title').textContent = id ? 'Edit Holiday' : 'Add Holiday';
    const h = id ? allHolidays.find(x => x.id === id) : null;
    document.getElementById('hm-id').value = id || '';
    document.getElementById('hm-name').value = h?.name || '';
    document.getElementById('hm-date').value = h?.date || '';
    document.getElementById('hm-impact').value = h?.impact || 'HIGH';
    document.getElementById('hm-notes').value = h?.notes || '';
    document.getElementById('holiday-modal').classList.add('open');
}

async function saveHoliday() {
    const payload = {
        name: document.getElementById('hm-name').value.trim(),
        date: document.getElementById('hm-date').value,
        impact: document.getElementById('hm-impact').value,
        notes: document.getElementById('hm-notes').value.trim()
    };
    if (!payload.name || !payload.date) { showToast('Name and Date are required', 'error'); return; }
    try {
        if (editingHolidayId) {
            await sb(`${HOLIDAYS_TABLE}?id=eq.${editingHolidayId}`, { method: 'PATCH', body: JSON.stringify(payload), prefer: 'return=minimal' });
        } else {
            await sb(HOLIDAYS_TABLE, { method: 'POST', body: JSON.stringify(payload) });
        }
        showToast('Holiday saved ✅', 'success');
        document.getElementById('holiday-modal').classList.remove('open');
        await refresh();
    } catch (e) { showToast('Error: ' + e.message, 'error'); }
}

async function deleteHoliday(id) {
    if (!confirm('Delete this holiday?')) return;
    await sb(`${HOLIDAYS_TABLE}?id=eq.${id}`, { method: 'DELETE', prefer: 'return=minimal' });
    showToast('Deleted', 'info');
    await refresh();
}

/* ── CSV Export ──────────────────────────────────────────── */
function exportCSV() {
    const headers = ['sku', 'product_name', 'week_start', 'predicted_qty', 'actual_qty', 'holiday_flag', 'notes'];
    const csv = [headers.join(','), ...filteredForecasts.map(f => headers.map(h => JSON.stringify(f[h] ?? '')).join(','))].join('\n');
    const a = document.createElement('a');
    a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv);
    a.download = `demand_forecasts_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
}

/* ── Navigation ──────────────────────────────────────────── */
const VIEWS = {
    overview: { view: 'view-overview', nav: 'nav-overview', title: 'Overview', sub: 'Weekly demand forecasting overview' },
    forecasts: { view: 'view-forecasts', nav: 'nav-forecasts', title: 'Forecast Records', sub: 'All weekly SKU forecasts' },
    holidays: { view: 'view-holidays', nav: 'nav-holidays', title: 'Holiday Calendar', sub: 'Holidays impacting demand' }
};
let activeView = 'overview';

function switchView(key) {
    activeView = key;
    Object.entries(VIEWS).forEach(([k, v]) => {
        document.getElementById(v.view).classList.toggle('active', k === key);
        document.getElementById(v.nav).classList.toggle('active', k === key);
    });
    document.getElementById('page-title').textContent = VIEWS[key].title;
    document.getElementById('page-sub').textContent = VIEWS[key].sub;
    if (key === 'overview') { renderKPIs(); renderChart(''); renderUrgent(); }
    if (key === 'forecasts') applyFilters();
    if (key === 'holidays') renderHolidays();
}

/* ── Toast ───────────────────────────────────────────────── */
let toastT;
function showToast(msg, type = '') {
    const t = document.getElementById('toast');
    t.textContent = msg; t.className = `toast ${type} show`;
    clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('show'), 2800);
}

/* ── Refresh ─────────────────────────────────────────────── */
async function refresh() {
    document.getElementById('last-updated').textContent = 'Loading…';
    try {
        await fetchAll();
        populateWeekFilter();
        populateSkuFilter();
        switchView(activeView);
        document.getElementById('last-updated').textContent = 'Updated ' + new Date().toLocaleTimeString();
    } catch (e) { showToast('Error: ' + e.message, 'error'); }
}

/* ── Init ────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
    // Nav
    document.getElementById('nav-overview').addEventListener('click', e => { e.preventDefault(); switchView('overview'); });
    document.getElementById('nav-forecasts').addEventListener('click', e => { e.preventDefault(); switchView('forecasts'); });
    document.getElementById('nav-holidays').addEventListener('click', e => { e.preventDefault(); switchView('holidays'); });

    // Filters
    document.getElementById('search-forecast').addEventListener('input', applyFilters);
    document.getElementById('filter-week').addEventListener('change', applyFilters);
    document.getElementById('chart-sku-filter').addEventListener('change', e => renderChart(e.target.value));

    // Pagination
    document.getElementById('btn-prev').addEventListener('click', () => { if (currentPage > 1) { currentPage--; renderForecastTable(); } });
    document.getElementById('btn-next').addEventListener('click', () => {
        const total = Math.ceil(filteredForecasts.length / PAGE_SIZE);
        if (currentPage < total) { currentPage++; renderForecastTable(); }
    });

    // Buttons
    document.getElementById('btn-refresh').addEventListener('click', refresh);
    document.getElementById('btn-add-forecast').addEventListener('click', () => openForecastModal(null));
    document.getElementById('btn-add-holiday').addEventListener('click', () => openHolidayModal(null));
    document.getElementById('btn-export-csv').addEventListener('click', exportCSV);

    // Forecast modal
    document.getElementById('forecast-modal-close').addEventListener('click', () => document.getElementById('forecast-modal').classList.remove('open'));
    document.getElementById('forecast-modal-cancel').addEventListener('click', () => document.getElementById('forecast-modal').classList.remove('open'));
    document.getElementById('forecast-modal-save').addEventListener('click', saveForecast);

    // Holiday modal
    document.getElementById('holiday-modal-close').addEventListener('click', () => document.getElementById('holiday-modal').classList.remove('open'));
    document.getElementById('holiday-modal-cancel').addEventListener('click', () => document.getElementById('holiday-modal').classList.remove('open'));
    document.getElementById('holiday-modal-save').addEventListener('click', saveHoliday);

    // Keyboard
    document.addEventListener('keydown', e => { if (e.key === 'Escape') { document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('open')); } });

    // Globals for inline onclick
    window.openForecastModal = openForecastModal;
    window.deleteForecast = deleteForecast;
    window.openHolidayModal = openHolidayModal;
    window.deleteHoliday = deleteHoliday;

    refresh();
});
