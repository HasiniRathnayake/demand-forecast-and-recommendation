/* ═══════════════════════════════════════════════
   Smart Inventory Intake — app.js
   Member: Rathnayake R.M.T.S · IT24100012
   ═══════════════════════════════════════════════ */

const SUPABASE_URL = 'https://obbctmyetrdortxyglle.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9iYmN0bXlldHJkb3J0eHlnbGxlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTY1OTg1MywiZXhwIjoyMDg3MjM1ODUzfQ.uaOYLnsgpN7R4mcbd4qcd8_jY4swh18Cf8sKF063LOg';
const TABLE = 'intake_records';

let allRecords = [], filteredRecords = [], currentPage = 1;
const PAGE_SIZE = 50;
let accuracyChart = null;
let activeView = 'overview';

async function sb(path, opts = {}) {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}`, 'Content-Type': 'application/json', Prefer: opts.prefer || 'return=representation', ...opts.headers }, ...opts });
    if (!res.ok) throw new Error(`Supabase ${res.status}: ${await res.text()}`);
    const t = await res.text(); return t ? JSON.parse(t) : null;
}

async function fetchAll() { allRecords = await sb(`${TABLE}?select=*&order=intake_date.desc&limit=5000`) || []; }

/* ── Anomaly detection ───────────────────────────────────── */
const ANOMALY_THRESHOLD = 0.1; // > 10% variance = anomaly
function isAnomaly(expected, received) {
    if (!expected || expected === 0) return false;
    return Math.abs((received - expected) / expected) > ANOMALY_THRESHOLD;
}
function variancePct(expected, received) {
    if (!expected) return 0;
    return ((received - expected) / expected * 100).toFixed(1);
}

/* ── Live anomaly check on form ──────────────────────────── */
function checkAnomaly() {
    const expected = parseInt(document.getElementById('if-expected').value) || 0;
    const received = parseInt(document.getElementById('if-received').value) || 0;
    const disp = document.getElementById('anomaly-display');
    if (!expected || !received) { disp.style.display = 'none'; return; }
    const anomaly = isAnomaly(expected, received);
    const pct = variancePct(expected, received);
    disp.style.display = 'block';
    if (anomaly) {
        disp.innerHTML = `<div class="anomaly-flag">⚠️ <strong>Anomaly Detected:</strong> Variance ${pct > 0 ? '+' : ''}${pct}% (±10% threshold). This will be flagged for investigation.</div>`;
    } else {
        disp.innerHTML = `<div class="ok-flag">✅ <strong>Within tolerance.</strong> Variance ${pct > 0 ? '+' : ''}${pct}% — looks good!</div>`;
    }
}

/* ── KPIs ────────────────────────────────────────────────── */
function renderKPIs() {
    const today = new Date().toISOString().split('T')[0];
    const todayRecs = allRecords.filter(r => r.intake_date === today);
    const anomalyCount = allRecords.filter(r => r.is_anomaly).length;
    const clean = allRecords.filter(r => !r.is_anomaly).length;
    const accuracyRate = allRecords.length ? (clean / allRecords.length * 100) : 0;
    document.getElementById('kpi-today').textContent = todayRecs.length;
    document.getElementById('kpi-anomalies').textContent = anomalyCount;
    document.getElementById('kpi-accuracy').textContent = accuracyRate.toFixed(1) + '%';
    document.getElementById('kpi-total').textContent = allRecords.length;
}

function renderAccuracyChart() {
    const byDay = {};
    allRecords.forEach(r => {
        if (!byDay[r.intake_date]) byDay[r.intake_date] = { clean: 0, total: 0 };
        byDay[r.intake_date].total++;
        if (!r.is_anomaly) byDay[r.intake_date].clean++;
    });
    const days = Object.keys(byDay).sort().slice(-14);
    const ctx = document.getElementById('accuracy-chart').getContext('2d');
    if (accuracyChart) accuracyChart.destroy();
    accuracyChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: days,
            datasets: [{ label: 'Intake Accuracy %', data: days.map(d => byDay[d].total ? (byDay[d].clean / byDay[d].total * 100).toFixed(1) : 100), borderColor: '#06b6d4', backgroundColor: 'rgba(6,182,212,0.1)', fill: true, tension: 0.4, pointRadius: 4 }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: '#94a3b8', font: { family: 'Inter' } } } }, scales: { x: { ticks: { color: '#475569' }, grid: { color: '#1e2d45' } }, y: { ticks: { color: '#475569' }, grid: { color: '#1e2d45' }, min: 0, max: 100, title: { display: true, text: 'Accuracy %', color: '#475569' } } } }
    });
}

function renderLatestAnomalies() {
    const anomalies = allRecords.filter(r => r.is_anomaly).slice(0, 8);
    const tbody = document.getElementById('latest-anomalies-tbody');
    if (!anomalies.length) { tbody.innerHTML = '<tr><td colspan="7" class="loading-row">No anomalies detected — all intakes within tolerance ✅</td></tr>'; return; }
    tbody.innerHTML = anomalies.map(r => {
        const pct = variancePct(r.expected_qty, r.received_qty);
        return `<tr>
      <td>${r.intake_date}</td>
      <td><span class="font-mono">${r.sku}</span></td>
      <td>${r.product_name || '—'}</td>
      <td>${r.expected_qty}</td>
      <td class="text-red">${r.received_qty}</td>
      <td class="text-red">${pct > 0 ? '+' : ''}${pct}%</td>
      <td><span class="badge ${r.investigation_status === 'RESOLVED' ? 'badge-success' : 'badge-danger'}">${r.investigation_status || 'OPEN'}</span></td>
    </tr>`;
    }).join('');
}

/* ── Records table ───────────────────────────────────────── */
function applyFilters() {
    const s = document.getElementById('search-rec').value.toLowerCase();
    const a = document.getElementById('filter-anomaly').value;
    filteredRecords = allRecords.filter(r => {
        const m = !s || (r.sku || '').toLowerCase().includes(s) || (r.product_name || '').toLowerCase().includes(s);
        const an = a === '' ? true : a === 'true' ? r.is_anomaly : !r.is_anomaly;
        return m && an;
    });
    currentPage = 1; renderRecordsTable();
}

function renderRecordsTable() {
    const slice = filteredRecords.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
    const total = Math.ceil(filteredRecords.length / PAGE_SIZE);
    const tbody = document.getElementById('records-tbody');
    if (!slice.length) { tbody.innerHTML = '<tr><td colspan="10" class="loading-row">No records found.</td></tr>'; }
    else tbody.innerHTML = slice.map(r => {
        const pct = variancePct(r.expected_qty, r.received_qty);
        return `<tr>
      <td>${r.intake_date}</td>
      <td><span class="font-mono">${r.sku}</span></td>
      <td>${r.product_name || '—'}</td>
      <td>${r.supplier || '—'}</td>
      <td>${r.expected_qty}</td>
      <td>${r.received_qty}</td>
      <td class="${r.is_anomaly ? 'text-red' : ''}">${pct > 0 ? '+' : ''}${pct}%</td>
      <td>${r.is_anomaly ? '<span class="badge badge-danger">⚠️ YES</span>' : '<span class="badge badge-success">✅ OK</span>'}</td>
      <td>${r.recorded_by || '—'}</td>
      <td><button class="btn-icon" onclick="deleteRecord('${r.id}')">🗑️</button></td>
    </tr>`;
    }).join('');
    document.getElementById('page-info').textContent = `Page ${currentPage} of ${total || 1} (${filteredRecords.length.toLocaleString()})`;
    document.getElementById('btn-prev').disabled = currentPage <= 1;
    document.getElementById('btn-next').disabled = currentPage >= total;
}

function renderAnomalies() {
    const anomalies = allRecords.filter(r => r.is_anomaly);
    const tbody = document.getElementById('anomalies-tbody');
    if (!anomalies.length) { tbody.innerHTML = '<tr><td colspan="8" class="loading-row">No anomalies detected. All intakes are within tolerance ✅</td></tr>'; return; }
    tbody.innerHTML = anomalies.map(r => {
        const pct = variancePct(r.expected_qty, r.received_qty);
        return `<tr>
      <td>${r.intake_date}</td>
      <td><span class="font-mono">${r.sku}</span></td>
      <td>${r.product_name || '—'}</td>
      <td>${r.expected_qty}</td>
      <td class="text-red">${r.received_qty}</td>
      <td class="text-red">${pct > 0 ? '+' : ''}${pct}%</td>
      <td><span class="badge ${r.investigation_status === 'RESOLVED' ? 'badge-success' : 'badge-danger'}">${r.investigation_status || 'OPEN'}</span></td>
      <td><button class="btn btn-success btn-sm" onclick="markResolved('${r.id}')">✅ Resolved</button></td>
    </tr>`;
    }).join('');
}

/* ── Form submit ─────────────────────────────────────────── */
async function submitIntake() {
    const expected = parseInt(document.getElementById('if-expected').value) || 0;
    const received = parseInt(document.getElementById('if-received').value) || 0;
    const payload = {
        sku: document.getElementById('if-sku').value.trim(),
        product_name: document.getElementById('if-name').value.trim(),
        supplier: document.getElementById('if-supplier').value.trim(),
        po_number: document.getElementById('if-po').value.trim(),
        intake_date: new Date().toISOString().split('T')[0],
        expected_qty: expected,
        received_qty: received,
        is_anomaly: isAnomaly(expected, received),
        investigation_status: 'OPEN',
        recorded_by: document.getElementById('if-recorded-by').value.trim(),
        notes: document.getElementById('if-notes').value.trim()
    };
    if (!payload.sku || !expected || !received) { showToast('SKU, Expected Qty and Received Qty are required', 'error'); return; }
    try {
        await sb(TABLE, { method: 'POST', body: JSON.stringify(payload) });
        const msg = payload.is_anomaly ? '⚠️ Intake submitted — anomaly flagged!' : '✅ Intake submitted successfully!';
        showToast(msg, payload.is_anomaly ? 'error' : 'success');
        clearForm();
        await refresh();
        switchView('records');
    } catch (e) { showToast('Error: ' + e.message, 'error'); }
}

function clearForm() {
    ['if-sku', 'if-name', 'if-supplier', 'if-po', 'if-expected', 'if-received', 'if-recorded-by', 'if-notes'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('anomaly-display').style.display = 'none';
}

async function markResolved(id) {
    await sb(`${TABLE}?id=eq.${id}`, { method: 'PATCH', body: JSON.stringify({ investigation_status: 'RESOLVED' }), prefer: 'return=minimal' });
    showToast('Marked as resolved ✅', 'success'); await refresh();
}

async function markAllResolved() {
    const anomalies = allRecords.filter(r => r.is_anomaly && (!r.investigation_status || r.investigation_status === 'OPEN'));
    await Promise.all(anomalies.map(r => sb(`${TABLE}?id=eq.${r.id}`, { method: 'PATCH', body: JSON.stringify({ investigation_status: 'RESOLVED' }), prefer: 'return=minimal' })));
    showToast(`${anomalies.length} anomalies marked as resolved ✅`, 'success'); await refresh();
}

async function deleteRecord(id) {
    if (!confirm('Delete this intake record?')) return;
    await sb(`${TABLE}?id=eq.${id}`, { method: 'DELETE', prefer: 'return=minimal' });
    showToast('Deleted', 'info'); await refresh();
}

function exportCSV() {
    const h = ['intake_date', 'sku', 'product_name', 'supplier', 'po_number', 'expected_qty', 'received_qty', 'is_anomaly', 'recorded_by', 'notes'];
    const csv = [h.join(','), ...filteredRecords.map(r => h.map(k => JSON.stringify(r[k] ?? '')).join(','))].join('\n');
    const a = document.createElement('a'); a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv); a.download = `intake_records_${new Date().toISOString().split('T')[0]}.csv`; a.click();
}

/* ── Navigation ──────────────────────────────────────────── */
const VIEWS = {
    overview: { v: 'view-overview', n: 'nav-overview', t: 'Overview', s: 'Intake and anomaly overview' },
    intake: { v: 'view-intake', n: 'nav-intake', t: 'Intake Form', s: 'Submit new delivery intake' },
    records: { v: 'view-records', n: 'nav-records', t: 'Records', s: 'All intake records' },
    anomalies: { v: 'view-anomalies', n: 'nav-anomalies', t: 'Anomaly Alerts', s: 'Flagged discrepancies' }
};

function switchView(key) {
    activeView = key;
    Object.entries(VIEWS).forEach(([k, v]) => { document.getElementById(v.v).classList.toggle('active', k === key); document.getElementById(v.n).classList.toggle('active', k === key); });
    document.getElementById('page-title').textContent = VIEWS[key].t;
    document.getElementById('page-sub').textContent = VIEWS[key].s;
    if (key === 'overview') { renderKPIs(); renderAccuracyChart(); renderLatestAnomalies(); }
    if (key === 'records') applyFilters();
    if (key === 'anomalies') renderAnomalies();
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
    document.getElementById('search-rec').addEventListener('input', applyFilters);
    document.getElementById('filter-anomaly').addEventListener('change', applyFilters);
    document.getElementById('btn-prev').addEventListener('click', () => { if (currentPage > 1) { currentPage--; renderRecordsTable(); } });
    document.getElementById('btn-next').addEventListener('click', () => { const t = Math.ceil(filteredRecords.length / PAGE_SIZE); if (currentPage < t) { currentPage++; renderRecordsTable(); } });
    document.getElementById('btn-refresh').addEventListener('click', refresh);
    document.getElementById('btn-go-intake').addEventListener('click', () => switchView('intake'));
    document.getElementById('btn-clear-all').addEventListener('click', markAllResolved);
    document.getElementById('btn-export').addEventListener('click', exportCSV);
    document.getElementById('if-submit').addEventListener('click', submitIntake);
    document.getElementById('if-clear').addEventListener('click', clearForm);
    window.deleteRecord = deleteRecord; window.markResolved = markResolved; window.checkAnomaly = checkAnomaly;
    refresh();
});
