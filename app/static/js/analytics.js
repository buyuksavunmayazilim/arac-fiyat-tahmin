/* analytics.js — Dashboard grafikleri */

const fmt = (n) => new Intl.NumberFormat('tr-TR').format(Math.round(n));
const NAVY = '#112247', ACCENT = '#E8622A', GREEN = '#1A9F6E';
const PALETTE = ['#112247','#1A3360','#234180','#2E5299','#5B7FC0','#A0B8DC',
                 '#E8622A','#1A9F6E','#C78F1A','#D63B3B'];

let trendChart, brandChart, fuelChart, phChart;

document.addEventListener('DOMContentLoaded', () => {
  loadStats();
  loadAllBrands();   // Tüm markaları yükle (trend + ph cascade için)
  loadTrend();
  loadBrands();
  setupTrendCascade();
  setupPhCascade();
  document.getElementById('trend-btn').addEventListener('click', loadTrend);
  document.getElementById('ph-btn').addEventListener('click', loadVehicleList);
});

// ── Tüm markaları yükle ───────────────────────────────────────────────────────
async function loadAllBrands() {
  const d = await fetch('/api/options').then(r => r.json());
  const markas = d.markas || [];
  ['trend-marka', 'ph-marka'].forEach(id => {
    const el = document.getElementById(id);
    const firstOpt = el.querySelector('option');
    el.innerHTML = '';
    el.appendChild(firstOpt);
    markas.forEach(m => {
      const o = document.createElement('option'); o.value = m; o.textContent = m;
      el.appendChild(o);
    });
  });

  // Yıl dropdown (trend)
  const years = d.years || [];
  const yearEl = document.getElementById('trend-year');
  years.forEach(y => {
    const o = document.createElement('option'); o.value = y; o.textContent = y;
    yearEl.appendChild(o);
  });
}

// ── Trend cascade: marka → seri → model ───────────────────────────────────────
function setupTrendCascade() {
  const markaEl = document.getElementById('trend-marka');
  const seriEl  = document.getElementById('trend-seri');
  const modelEl = document.getElementById('trend-model');
  let modelsData = [];

  markaEl.addEventListener('change', async () => {
    const marka = markaEl.value;
    seriEl.innerHTML = '<option value="">Tümü</option>';
    modelEl.innerHTML = '<option value="">Tümü</option>';
    seriEl.disabled = !marka;
    modelEl.disabled = true;
    if (!marka) return;
    const d = await fetch(`/api/options/models?marka=${encodeURIComponent(marka)}`).then(r => r.json());
    modelsData = d.models || [];
    [...new Set(modelsData.map(m => m.seri).filter(Boolean))].sort().forEach(s => {
      const o = document.createElement('option'); o.value = s; o.textContent = s;
      seriEl.appendChild(o);
    });
  });

  seriEl.addEventListener('change', () => {
    const seri = seriEl.value;
    modelEl.innerHTML = '<option value="">Tümü</option>';
    modelEl.disabled = !seri;
    if (!seri) return;
    modelsData.filter(m => m.seri === seri).map(m => m.model).filter(Boolean).sort().forEach(m => {
      const o = document.createElement('option'); o.value = m; o.textContent = m;
      modelEl.appendChild(o);
    });
  });
}

// ── PH cascade: marka → seri → model ──────────────────────────────────────────
function setupPhCascade() {
  const markaEl = document.getElementById('ph-marka');
  const seriEl  = document.getElementById('ph-seri');
  const modelEl = document.getElementById('ph-model');
  let modelsData = [];

  markaEl.addEventListener('change', async () => {
    const marka = markaEl.value;
    seriEl.innerHTML = '<option value="">Seçiniz...</option>';
    modelEl.innerHTML = '<option value="">Önce seri</option>';
    seriEl.disabled = !marka;
    modelEl.disabled = true;
    if (!marka) return;
    const d = await fetch(`/api/options/models?marka=${encodeURIComponent(marka)}`).then(r => r.json());
    modelsData = d.models || [];
    [...new Set(modelsData.map(m => m.seri).filter(Boolean))].sort().forEach(s => {
      const o = document.createElement('option'); o.value = s; o.textContent = s;
      seriEl.appendChild(o);
    });
  });

  seriEl.addEventListener('change', () => {
    const seri = seriEl.value;
    modelEl.innerHTML = '<option value="">Seçiniz...</option>';
    modelEl.disabled = !seri;
    if (!seri) return;
    modelsData.filter(m => m.seri === seri).map(m => m.model).filter(Boolean).sort().forEach(m => {
      const o = document.createElement('option'); o.value = m; o.textContent = m;
      modelEl.appendChild(o);
    });
  });
}

// ── Stats ─────────────────────────────────────────────────────────────────────
async function loadStats() {
  const d = await fetch('/api/analytics/stats').then(r => r.json());
  document.getElementById('s-total').textContent = fmt(d.total_vehicles);
  document.getElementById('s-avg').textContent = '₺' + fmt(d.avg_price);
  document.getElementById('s-r2').textContent = d.model_r2 ? (d.model_r2*100).toFixed(1)+'%' : '–';
  document.getElementById('s-model').textContent = d.active_model || '–';

  // Yakıt grafiği
  await loadFuelChart();
}

// ── Fiyat trendi ──────────────────────────────────────────────────────────────
async function loadTrend() {
  const marka = document.getElementById('trend-marka').value;
  const seri  = document.getElementById('trend-seri').value;
  const model = document.getElementById('trend-model').value;
  const year  = document.getElementById('trend-year').value;
  const days  = document.getElementById('trend-days').value;

  const params = new URLSearchParams({ days });
  if (marka) params.append('marka', marka);
  if (seri)  params.append('seri', seri);
  if (model) params.append('model', model);
  if (year)  params.append('model_year', year);

  const data = await fetch('/api/analytics/price-trend?' + params).then(r => r.json());
  const trend = data.trend || [];

  const labels = trend.map(t => t.date);
  const avgs   = trend.map(t => t.avg_price);
  const mins   = trend.map(t => t.min_price);
  const maxs   = trend.map(t => t.max_price);

  const ctx = document.getElementById('trend-chart').getContext('2d');
  if (trendChart) trendChart.destroy();
  trendChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Ortalama',
          data: avgs,
          borderColor: NAVY, backgroundColor: 'rgba(17,34,71,0.08)',
          borderWidth: 2, fill: true, tension: 0.4, pointRadius: 3,
        },
        {
          label: 'Min',
          data: mins,
          borderColor: GREEN, borderWidth: 1.5, borderDash: [4,3],
          fill: false, tension: 0.4, pointRadius: 0,
        },
        {
          label: 'Max',
          data: maxs,
          borderColor: ACCENT, borderWidth: 1.5, borderDash: [4,3],
          fill: false, tension: 0.4, pointRadius: 0,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top' } },
      scales: {
        y: {
          ticks: { callback: v => '₺' + fmt(v) },
          grid: { color: 'rgba(0,0,0,0.05)' },
        },
        x: { grid: { display: false } },
      },
    },
  });
}

// ── Marka bar ─────────────────────────────────────────────────────────────────
async function loadBrands() {
  const data = await fetch('/api/analytics/stats').then(r => r.json());
  const brands = data.top_brands || [];
  const ctx = document.getElementById('brand-chart').getContext('2d');
  if (brandChart) brandChart.destroy();
  brandChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: brands.map(b => b.marka),
      datasets: [{
        label: 'İlan Sayısı',
        data: brands.map(b => b.count),
        backgroundColor: PALETTE.slice(0, brands.length),
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { grid: { color: 'rgba(0,0,0,0.05)' } },
        x: { grid: { display: false } },
      },
    },
  });
}

// ── Yakıt doughnut ────────────────────────────────────────────────────────────
async function loadFuelChart() {
  // Yakıt dağılımı için arama endpoint'i kullan
  const data = await fetch('/api/search?per_page=1').then(r => r.json()).catch(() => null);
  // Temsili demo data (gerçekte ayrı bir endpoint daha iyi olur)
  const ctx = document.getElementById('fuel-chart').getContext('2d');
  if (fuelChart) fuelChart.destroy();
  fuelChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Dizel', 'Benzin', 'Hibrit', 'Elektrik', 'LPG'],
      datasets: [{
        data: [38, 34, 15, 8, 5],
        backgroundColor: PALETTE,
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right', labels: { boxWidth: 12, font: { size: 12 } } },
      },
      cutout: '60%',
    },
  });
}

// ── Araç listesi (marka/seri/model'e göre) ────────────────────────────────────
async function loadVehicleList() {
  const marka = document.getElementById('ph-marka').value;
  const seri  = document.getElementById('ph-seri').value;
  const model = document.getElementById('ph-model').value;

  if (!marka) { showToast('En az marka seçiniz', 'error'); return; }

  const params = new URLSearchParams();
  params.append('marka', marka);
  if (seri)  params.append('seri', seri);
  if (model) params.append('model', model);

  const data = await fetch('/api/vehicles/by-model?' + params).then(r => r.json());
  const vehicles = data.vehicles || [];

  document.getElementById('ph-empty').style.display = 'none';
  document.getElementById('ph-result').style.display = 'none';

  const listWrap = document.getElementById('ph-vehicle-list');
  const list = document.getElementById('ph-vehicles');
  list.innerHTML = '';

  if (!vehicles.length) {
    listWrap.style.display = 'none';
    document.getElementById('ph-empty').style.display = 'block';
    document.getElementById('ph-empty').textContent = 'Bu kritere uygun araç bulunamadı.';
    return;
  }

  listWrap.style.display = 'block';
  vehicles.forEach(v => {
    const el = document.createElement('div');
    el.style.cssText = 'padding:12px 14px;border:1.5px solid var(--gray-200);border-radius:var(--radius);cursor:pointer;transition:var(--transition);display:flex;justify-content:space-between;align-items:center;';
    const histBadge = v.history_count > 0
      ? `<span style="font-size:11px;background:var(--navy-50);color:var(--navy-600);padding:2px 8px;border-radius:10px;">${v.history_count} fiyat kaydı</span>`
      : `<span style="font-size:11px;background:var(--gray-100);color:var(--gray-500);padding:2px 8px;border-radius:10px;">Tek fiyat</span>`;
    el.innerHTML = `
      <div>
        <div style="font-weight:600;font-size:13.5px;color:var(--navy-800);">
          ${v.marka} ${v.seri||''} ${v.model||''} ${v.model_year||''}
        </div>
        <div style="font-size:12px;color:var(--gray-500);margin-top:2px;">
          ${v.km?fmt(v.km)+' km':''} ${v.fueloil?'· '+v.fueloil:''} ${v.color?'· '+v.color:''}
        </div>
      </div>
      <div style="text-align:right;">
        <div style="font-family:var(--font-number);font-weight:700;font-size:15px;color:var(--navy-700);">₺${fmt(v.price)}</div>
        <div style="margin-top:4px;">${histBadge}</div>
      </div>`;
    el.addEventListener('mouseenter', () => el.style.borderColor = 'var(--navy-300)');
    el.addEventListener('mouseleave', () => el.style.borderColor = 'var(--gray-200)');
    el.addEventListener('click', () => {
      document.querySelectorAll('#ph-vehicles > div').forEach(d => d.style.borderColor = 'var(--gray-200)');
      el.style.borderColor = 'var(--accent)';
      showVehicleHistory(v.no);
    });
    list.appendChild(el);
  });
}

// ── Seçilen aracın fiyat geçmişi ──────────────────────────────────────────────
async function showVehicleHistory(no) {
  const data = await fetch(`/api/vehicle/${no}/price-history`).then(r => r.json());
  const history = data.history || [];

  document.getElementById('ph-result').style.display = 'block';
  document.getElementById('ph-result').scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  if (history.length < 2) {
    document.getElementById('ph-summary').innerHTML = `
      <div class="stat-card" style="padding:14px 18px;">
        <div class="stat-label">Güncel Fiyat</div>
        <div class="stat-value" style="font-size:20px;">₺${fmt(data.last_price || (history[0] && history[0].price) || 0)}</div>
      </div>
      <div class="stat-card" style="padding:14px 18px;">
        <div class="stat-label">Durum</div>
        <div class="stat-value" style="font-size:15px;color:var(--gray-500);">Tek fiyat kaydı</div>
      </div>`;
    if (phChart) phChart.destroy();
    return;
  }

  const changePct = data.price_change_pct?.toFixed(1);
  const dir = changePct >= 0 ? '▲' : '▼';
  const clr = changePct >= 0 ? 'var(--red)' : 'var(--green)';
  document.getElementById('ph-summary').innerHTML = `
    <div class="stat-card" style="padding:14px 18px;">
      <div class="stat-label">İlk Fiyat</div>
      <div class="stat-value" style="font-size:20px;">₺${fmt(data.first_price)}</div>
    </div>
    <div class="stat-card" style="padding:14px 18px;">
      <div class="stat-label">Son Fiyat</div>
      <div class="stat-value" style="font-size:20px;">₺${fmt(data.last_price)}</div>
    </div>
    <div class="stat-card" style="padding:14px 18px;">
      <div class="stat-label">Değişim</div>
      <div class="stat-value" style="font-size:20px;color:${clr};">${dir} %${Math.abs(changePct)}</div>
    </div>
    <div class="stat-card" style="padding:14px 18px;">
      <div class="stat-label">Kaç Kez Değişti</div>
      <div class="stat-value" style="font-size:20px;">${data.changes} kez</div>
    </div>`;

  const ctx = document.getElementById('ph-chart').getContext('2d');
  if (phChart) phChart.destroy();
  phChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: history.map(h => h.create_date.slice(0,10)),
      datasets: [{
        label: 'Fiyat (₺)',
        data: history.map(h => h.price),
        borderColor: NAVY, backgroundColor: 'rgba(17,34,71,0.07)',
        borderWidth: 2, fill: true, tension: 0.3,
        pointBackgroundColor: NAVY, pointRadius: 5, pointHoverRadius: 7,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { ticks: { callback: v => '₺' + fmt(v) }, grid: { color: 'rgba(0,0,0,0.05)' } },
        x: { grid: { display: false } },
      },
    },
  });
}
