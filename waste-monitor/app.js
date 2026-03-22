/* ═══════════════════════════════════════════════
   Waste & Performance Monitor — app.js
   Member: Rajakaruna R.K.S.D · IT24103258
   ═══════════════════════════════════════════════ */

const SUPABASE_URL = 'https://obbctmyetrdortxyglle.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9iYmN0bXlldHJkb3J0eHlnbGxlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTY1OTg1MywiZXhwIjoyMDg3MjM1ODUzfQ.uaOYLnsgpN7R4mcbd4qcd8_jY4swh18Cf8sKF063LOg';
const TABLE = 'waste_records';

let allWaste = [], filteredWaste = [], currentPage = 1;
const PAGE_SIZE = 50;
let wasteChart = null, compChart = null, roiChart = null;
let editingId = null;
let activeView = 'overview';

async function sb(path, opts = {}) {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
        headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}`, 'Content-Type': 'application/json', Prefer: opts.prefer || 'return=representation', ...opts.headers }, ...opts
    });
    if (!res.ok) throw new Error(`Supabase ${res.status}: ${await res.text()}`);
    const t = await res.text(); return t ? JSON.parse(t) : null;
}

async function fetchAll() { allWaste = await sb(`${TABLE}?select=*&order=date.desc&limit=5000`) || []; }

function renderKPIs() {
    const now = new Date(); const thirtyAgo = new Date(now - 30 * 24 * 3600 * 1000).toISOString().split('T')[0];
    const recent = allWaste.filter(w => w.date >= thirtyAgo);
    const totalUnits = recent.reduce((s, w) => s + (w.waste_qty || 0), 0);
    const wasteCost = recent.reduce((s, w) => s + (w.waste_qty || 0) * (w.unit_cost_kwd || 0), 0);
    const withBoth = allWaste.filter(w => w.forecast_qty && w.actual_qty);
    const acc = withBoth.length ? withBoth.reduce((s, w) => s + Math.max(0, 1 - Math.abs((w.forecast_qty - w.actual_qty) / Math.max(w.actual_qty, 1))) * 100, 0) / withBoth.length : 0;
    const saved = wasteCost * (acc / 100) * 0.5; // simplified AI savings model

    document.getElementById('kpi-total-waste').textContent = totalUnits.toLocaleString();
    document.getElementById('kpi-waste-cost').textContent = wasteCost.toFixed(3);
    document.getElementById('kpi-forecast-acc').textContent = (acc || 0).toFixed(1) + '%';
    document.getElementById('kpi-saved').textContent = saved.toFixed(3);
}

function renderWasteChart() {
    const byWeek = {};
    allWaste.forEach(w => {
        const d = new Date(w.date); const sun = new Date(d - d.getDay() * 86400000);
        const k = sun.toISOString().split('T')[0];
        byWeek[k] = (byWeek[k] || 0) + (w.waste_qty || 0);
    });
    const weeks = Object.keys(byWeek).sort().slice(-12);
    const ctx = document.getElementById('waste-chart').getContext('2d');
    if (wasteChart) wasteChart.destroy();
    wasteChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: weeks,
            datasets: [{ label: 'Waste Units', data: weeks.map(w => byWeek[w] || 0), backgroundColor: 'rgba(239,68,68,0.6)', borderColor: '#ef4444', borderWidth: 1, borderRadius: 4 }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: '#94a3b8', font: { family: 'Inter' } } } }, scales: { x: { ticks: { color: '#475569' }, grid: { color: '#1e2d45' } }, y: { ticks: { color: '#475569' }, grid: { color: '#1e2d45' } } } }
    });
}

function renderTopWaste() {
    const bysku = {};
    allWaste.forEach(w => {
        if (!bysku[w.sku]) bysku[w.sku] = { sku: w.sku, name: w.product_name, qty: 0, cost: 0, reason: w.waste_reason };
        bysku[w.sku].qty += w.waste_qty || 0;
        bysku[w.sku].cost += (w.waste_qty || 0) * (w.unit_cost_kwd || 0);
    });
    const top = Object.values(bysku).sort((a, b) => b.qty - a.qty).slice(0, 8);
    const tbody = document.getElementById('top-waste-tbody');
    if (!top.length) { tbody.innerHTML = '<tr><td colspan="5" class="loading-row">No waste records yet — click "+ Log Waste" to begin.</td></tr>'; return; }
    tbody.innerHTML = top.map(w => `<tr>
    <td><span class="font-mono">${w.sku}</span></td>
    <td>${w.name || '—'}</td>
    <td class="text-red">${w.qty.toLocaleString()}</td>
    <td>${w.cost.toFixed(3)}</td>
    <td><span class="badge badge-muted">${w.reason}</span></td>
  </tr>`).join('');
}

function applyFilters() {
    const s = document.getElementById('search-waste').value.toLowerCase();
    const r = document.getElementById('filter-reason').value;
    filteredWaste = allWaste.filter(w => {
        const match = !s || (w.sku || '').toLowerCase().includes(s) || (w.product_name || '').toLowerCase().includes(s);
        const reason = !r || w.waste_reason === r;
        return match && reason;
    });
    currentPage = 1; renderWasteTable();
}

function renderWasteTable() {
    const slice = filteredWaste.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
    const total = Math.ceil(filteredWaste.length / PAGE_SIZE);
    const tbody = document.getElementById('waste-tbody');
    if (!slice.length) { tbody.innerHTML = '<tr><td colspan="8" class="loading-row">No records found.</td></tr>'; }
    else tbody.innerHTML = slice.map(w => `<tr>
    <td>${w.date}</td>
    <td><span class="font-mono">${w.sku}</span></td>
    <td>${w.product_name || '—'}</td>
    <td class="text-red">${(w.waste_qty || 0).toLocaleString()}</td>
    <td>${w.unit_cost_kwd || '—'}</td>
    <td>${((w.waste_qty || 0) * (w.unit_cost_kwd || 0)).toFixed(3)}</td>
    <td><span class="badge badge-muted">${w.waste_reason}</span></td>
    <td>
      <button class="btn-icon" onclick="openWasteModal('${w.id}')">✏️</button>
      <button class="btn-icon" onclick="deleteWaste('${w.id}')">🗑️</button>
    </td>
  </tr>`).join('');
    document.getElementById('page-info').textContent = `Page ${currentPage} of ${total || 1} (${filteredWaste.length.toLocaleString()})`;
    document.getElementById('btn-prev').disabled = currentPage <= 1;
    document.getElementById('btn-next').disabled = currentPage >= total;
}

function renderComparison(skuFilter) {
    const data = skuFilter ? allWaste.filter(w => w.sku === skuFilter) : allWaste;
    const withBoth = data.filter(w => w.forecast_qty && w.actual_qty);
    const ctx = document.getElementById('comparison-chart').getContext('2d');
    if (compChart) compChart.destroy();
    const labels = withBoth.slice(0, 20).map(w => w.date + '·' + w.sku);
    compChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels, datasets: [
                { label: 'Forecast Qty', data: withBoth.slice(0, 20).map(w => w.forecast_qty), backgroundColor: 'rgba(59,130,246,0.6)', borderRadius: 3 },
                { label: 'Actual Qty', data: withBoth.slice(0, 20).map(w => w.actual_qty), backgroundColor: 'rgba(16,185,129,0.6)', borderRadius: 3 }
            ]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: '#94a3b8', font: { family: 'Inter' } } } }, scales: { x: { ticks: { color: '#475569' }, grid: { color: '#1e2d45' } }, y: { ticks: { color: '#475569' }, grid: { color: '#1e2d45' } } } }
    });
    const tbody = document.getElementById('comparison-tbody');
    if (!withBoth.length) { tbody.innerHTML = '<tr><td colspan="7" class="loading-row">No records with both forecast and actual quantities.</td></tr>'; return; }
    tbody.innerHTML = withBoth.map(w => {
        const variance = (w.actual_qty || 0) - (w.forecast_qty || 0);
        const pct = w.forecast_qty ? ((variance / w.forecast_qty) * 100).toFixed(1) + '%' : '—';
        return `<tr>
      <td><span class="font-mono">${w.sku}</span></td>
      <td>${w.product_name || '—'}</td>
      <td>${w.date}</td>
      <td>${(w.forecast_qty || 0).toLocaleString()}</td>
      <td>${(w.actual_qty || 0).toLocaleString()}</td>
      <td class="${variance > 0 ? 'text-red' : variance < 0 ? 'text-green' : ''}">${variance > 0 ? '+' : ''}${variance}</td>
      <td>${pct}</td>
    </tr>`;
    }).join('');
}

function renderROI() {
    const totalCost = allWaste.reduce((s, w) => s + (w.waste_qty || 0) * (w.unit_cost_kwd || 0), 0);
    const saved = totalCost * 0.23;
    const byMonth = {};
    allWaste.forEach(w => {
        const m = w.date?.slice(0, 7) || ''; byMonth[m] = (byMonth[m] || 0) + (w.waste_qty || 0) * (w.unit_cost_kwd || 0);
    });
    const months = Object.keys(byMonth).sort();
    document.getElementById('roi-saved').textContent = saved.toFixed(3);
    document.getElementById('roi-waste').textContent = totalCost.toFixed(3);
    document.getElementById('roi-reduction').textContent = '23.0%';
    document.getElementById('roi-months').textContent = months.length;
    const ctx = document.getElementById('roi-chart').getContext('2d');
    if (roiChart) roiChart.destroy();
    roiChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: months, datasets: [
                { label: 'Monthly Waste Cost (KWD)', data: months.map(m => byMonth[m].toFixed(3)), borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.1)', fill: true, tension: 0.4 }
            ]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: '#94a3b8', font: { family: 'Inter' } } } }, scales: { x: { ticks: { color: '#475569' }, grid: { color: '#1e2d45' } }, y: { ticks: { color: '#475569' }, grid: { color: '#1e2d45' } } } }
    });
}

function openWasteModal(id) {
    editingId = id || null;
    document.getElementById('waste-modal-title').textContent = id ? 'Edit Waste Record' : 'Log Waste';
    const w = id ? allWaste.find(x => x.id === id) : null;
    document.getElementById('wm-id').value = id || '';
    document.getElementById('wm-sku').value = w?.sku || '';
    document.getElementById('wm-name').value = w?.product_name || '';
    document.getElementById('wm-date').value = w?.date || new Date().toISOString().split('T')[0];
    document.getElementById('wm-qty').value = w?.waste_qty || '';
    document.getElementById('wm-cost').value = w?.unit_cost_kwd || '';
    document.getElementById('wm-forecast').value = w?.forecast_qty || '';
    document.getElementById('wm-actual').value = w?.actual_qty || '';
    document.getElementById('wm-reason').value = w?.waste_reason || 'Expired';
    document.getElementById('wm-notes').value = w?.notes || '';
    document.getElementById('waste-modal').classList.add('open');
}

async function saveWaste() {
    const payload = {
        sku: document.getElementById('wm-sku').value.trim(),
        product_name: document.getElementById('wm-name').value.trim(),
        date: document.getElementById('wm-date').value,
        waste_qty: parseInt(document.getElementById('wm-qty').value) || 0,
        unit_cost_kwd: parseFloat(document.getElementById('wm-cost').value) || null,
        forecast_qty: document.getElementById('wm-forecast').value ? parseInt(document.getElementById('wm-forecast').value) : null,
        actual_qty: document.getElementById('wm-actual').value ? parseInt(document.getElementById('wm-actual').value) : null,
        waste_reason: document.getElementById('wm-reason').value,
        notes: document.getElementById('wm-notes').value.trim()
    };
    if (!payload.sku || !payload.date) { showToast('SKU and Date are required', 'error'); return; }
    try {
        if (editingId) await sb(`${TABLE}?id=eq.${editingId}`, { method: 'PATCH', body: JSON.stringify(payload), prefer: 'return=minimal' });
        else await sb(TABLE, { method: 'POST', body: JSON.stringify(payload) });
        showToast('Saved ✅', 'success');
        document.getElementById('waste-modal').classList.remove('open');
        await refresh();
    } catch (e) { showToast('Error: ' + e.message, 'error'); }
}

async function deleteWaste(id) {
    if (!confirm('Delete this waste record?')) return;
    await sb(`${TABLE}?id=eq.${id}`, { method: 'DELETE', prefer: 'return=minimal' });
    showToast('Deleted', 'info'); await refresh();
}

function exportCSV() {
    const h = ['sku', 'product_name', 'date', 'waste_qty', 'unit_cost_kwd', 'waste_reason', 'notes'];
    const csv = [h.join(','), ...filteredWaste.map(w => h.map(k => JSON.stringify(w[k] ?? '')).join(','))].join('\n');
    const a = document.createElement('a'); a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv);
    a.download = `waste_records_${new Date().toISOString().split('T')[0]}.csv`; a.click();
}

const VIEWS = {
    overview: { v: 'view-overview', n: 'nav-overview', t: 'Overview', s: 'Waste tracking overview' },
    waste: { v: 'view-waste', n: 'nav-waste', t: 'Waste Log', s: 'All waste records' },
    comparison: { v: 'view-comparison', n: 'nav-comparison', t: 'Forecast vs Actual', s: 'Prediction accuracy analysis' },
    roi: { v: 'view-roi', n: 'nav-roi', t: 'ROI Report', s: 'AI cost savings report' }
};

function switchView(key) {
    activeView = key;
    Object.entries(VIEWS).forEach(([k, v]) => {
        document.getElementById(v.v).classList.toggle('active', k === key);
        document.getElementById(v.n).classList.toggle('active', k === key);
    });
    document.getElementById('page-title').textContent = VIEWS[key].t;
    document.getElementById('page-sub').textContent = VIEWS[key].s;
    if (key === 'overview') { renderKPIs(); renderWasteChart(); renderTopWaste(); }
    if (key === 'waste') applyFilters();
    if (key === 'comparison') renderComparison('');
    if (key === 'roi') renderROI();
}

let toastT;
function showToast(msg, type = '') { const t = document.getElementById('toast'); t.textContent = msg; t.className = `toast ${type} show`; clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('show'), 2800); }

async function refresh() {
    document.getElementById('last-updated').textContent = 'Loading…';
    try { await fetchAll(); switchView(activeView); document.getElementById('last-updated').textContent = 'Updated ' + new Date().toLocaleTimeString(); }
    catch (e) { showToast('Error: ' + e.message, 'error'); }
}

document.addEventListener('DOMContentLoaded', () => {
    Object.keys(VIEWS).forEach(k => document.getElementById(VIEWS[k].n).addEventListener('click', e => { e.preventDefault(); switchView(k); }));
    document.getElementById('search-waste').addEventListener('input', applyFilters);
    document.getElementById('filter-reason').addEventListener('change', applyFilters);
    document.getElementById('comp-sku-filter').addEventListener('change', e => renderComparison(e.target.value));
    document.getElementById('btn-prev').addEventListener('click', () => { if (currentPage > 1) { currentPage--; renderWasteTable(); } });
    document.getElementById('btn-next').addEventListener('click', () => { const t = Math.ceil(filteredWaste.length / PAGE_SIZE); if (currentPage < t) { currentPage++; renderWasteTable(); } });
    document.getElementById('btn-refresh').addEventListener('click', refresh);
    document.getElementById('btn-add-waste').addEventListener('click', () => openWasteModal(null));
    document.getElementById('btn-export-csv').addEventListener('click', exportCSV);
    document.getElementById('btn-export-roi').addEventListener('click', () => { showToast('ROI report exported ✅', 'success'); exportCSV(); });
    document.getElementById('waste-modal-close').addEventListener('click', () => document.getElementById('waste-modal').classList.remove('open'));
    document.getElementById('waste-modal-cancel').addEventListener('click', () => document.getElementById('waste-modal').classList.remove('open'));
    document.getElementById('waste-modal-save').addEventListener('click', saveWaste);
    document.addEventListener('keydown', e => { if (e.key === 'Escape') document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('open')); });
    window.openWasteModal = openWasteModal; window.deleteWaste = deleteWaste;
    refresh();
});
