/* bfl.js — BFL Filo Araç Tahmin + Valör Fiyatlandırma */

const fmt = (n) => new Intl.NumberFormat('tr-TR').format(Math.round(n || 0));
const NAVY = '#112247', ACCENT = '#E8622A', GREEN = '#1A9F6E', RED = '#D63B3B';

let karChart, compareChart, valorChart;
let currentVehicles = [];

document.addEventListener('DOMContentLoaded', () => {
  loadOptions();
  setupCascade();
  document.getElementById('bfl-list-btn').addEventListener('click', listVehicles);
  document.getElementById('bfl-batch-btn').addEventListener('click', predictBatch);
});

// ── Seçenekler ────────────────────────────────────────────────────────────────
async function loadOptions() {
  const d = await fetch('/api/bfl/options').then(r => r.json());
  const markaEl = document.getElementById('bfl-marka');
  (d.markas || []).forEach(m => {
    const o = document.createElement('option'); o.value = m; o.textContent = m;
    markaEl.appendChild(o);
  });
  const durumEl = document.getElementById('bfl-durum');
  (d.durumlar || []).forEach(dr => {
    const o = document.createElement('option'); o.value = dr; o.textContent = dr;
    durumEl.appendChild(o);
  });
}

function setupCascade() {
  const markaEl = document.getElementById('bfl-marka');
  const seriEl  = document.getElementById('bfl-seri');
  markaEl.addEventListener('change', async () => {
    const marka = markaEl.value;
    seriEl.innerHTML = '<option value="">Tümü</option>';
    seriEl.disabled = !marka;
    if (!marka) return;
    const d = await fetch(`/api/bfl/series?marka=${encodeURIComponent(marka)}`).then(r => r.json());
    (d.series || []).forEach(s => {
      const o = document.createElement('option'); o.value = s; o.textContent = s;
      seriEl.appendChild(o);
    });
  });
}

// ── Araç listele ──────────────────────────────────────────────────────────────
async function listVehicles() {
  const marka = document.getElementById('bfl-marka').value;
  const seri  = document.getElementById('bfl-seri').value;
  const durum = document.getElementById('bfl-durum').value;

  if (!marka) { showToast('En az marka seçiniz', 'error'); return; }

  const params = new URLSearchParams();
  params.append('marka', marka);
  if (seri)  params.append('seri', seri);
  if (durum) params.append('durum', durum);

  const d = await fetch('/api/bfl/vehicles?' + params).then(r => r.json());
  currentVehicles = d.vehicles || [];

  const listCard = document.getElementById('bfl-vehicle-list');
  const list = document.getElementById('bfl-vehicles');
  document.getElementById('bfl-count').textContent = currentVehicles.length;
  list.innerHTML = '';

  // Sonuç alanlarını gizle
  ['bfl-summary','bfl-charts','bfl-table-card'].forEach(id => document.getElementById(id).style.display = 'none');
  const vc = document.getElementById('bfl-valor-card');
  if (vc) vc.style.display = 'none';

  if (!currentVehicles.length) {
    listCard.style.display = 'block';
    list.innerHTML = '<div style="color:var(--gray-500);font-size:13px;">Bu kritere uygun araç bulunamadı.</div>';
    document.getElementById('bfl-batch-btn').style.display = 'none';
    return;
  }

  listCard.style.display = 'block';
  document.getElementById('bfl-batch-btn').style.display = 'inline-flex';

  currentVehicles.forEach(v => {
    const el = document.createElement('div');
    el.className = 'bfl-vehicle-card';
    el.dataset.plaka = (v.plaka || '').toLowerCase();
    el.style.cssText = 'padding:12px 14px;border:1.5px solid var(--gray-200);border-radius:var(--radius);cursor:pointer;transition:var(--transition);display:flex;justify-content:space-between;align-items:center;';
    el.innerHTML = `
      <div>
        <div style="font-weight:600;font-size:13.5px;color:var(--navy-800);">
          <span style="font-family:var(--font-number);background:var(--navy-50);padding:2px 8px;border-radius:4px;margin-right:8px;">${v.plaka || '—'}</span>
          ${v.marka} ${v.seri || ''} ${v.model_yili || ''}
        </div>
        <div style="font-size:12px;color:var(--gray-500);margin-top:3px;">
          ${v.model || ''} ${v.son_km ? '· '+fmt(v.son_km)+' km' : ''} ${v.yakit_tipi ? '· '+v.yakit_tipi : ''}
          <span style="background:var(--gray-100);padding:1px 7px;border-radius:8px;margin-left:4px;">${v.plaka_durum}</span>
        </div>
      </div>
      <div style="text-align:right;">
        <div style="font-size:11px;color:var(--gray-500);">Alış</div>
        <div style="font-family:var(--font-number);font-weight:700;font-size:14px;color:var(--navy-700);">₺${fmt(v.alis_fiyati)}</div>
        <button class="btn btn-sm btn-outline" style="margin-top:6px;" onclick="event.stopPropagation();predictSingle(${v.id}, this)">Tahmin Et</button>
      </div>`;
    list.appendChild(el);
  });

  // Plaka arama
  const searchEl = document.getElementById('bfl-search');
  if (searchEl) {
    searchEl.value = '';
    searchEl.oninput = () => {
      const term = searchEl.value.toLowerCase().trim();
      let visible = 0;
      document.querySelectorAll('.bfl-vehicle-card').forEach(card => {
        const match = card.dataset.plaka.includes(term);
        card.style.display = match ? 'flex' : 'none';
        if (match) visible++;
      });
      document.getElementById('bfl-count').textContent = visible;
    };
  }
}


// ── Tekil tahmin ──────────────────────────────────────────────────────────────
async function predictSingle(filoId, btn) {
  btn.disabled = true;
  btn.textContent = '...';
  const faiz = parseFloat(document.getElementById('bfl-faiz').value) || 0;
  try {
    const d = await fetch(`/api/bfl/predict/${filoId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ annual_rate_pct: faiz }),
    }).then(r => r.json());
    if (d.error) { showToast(d.error, 'error'); return; }
    renderResults([{
      id: d.arac.id, plaka: d.arac.plaka, plaka_durum: d.arac.plaka_durum,
      marka: d.arac.marka, seri: d.arac.seri, model: d.arac.model,
      model_yili: d.arac.model_yili, son_km: d.arac.son_km,
      yakit_tipi: d.arac.yakit_tipi, vites_tipi: d.arac.vites_tipi,
      alis_fiyati: d.alis_fiyati, tahmini_satis: d.tahmini_satis,
      price_lower: d.price_lower, price_upper: d.price_upper,
      kar: d.kar, kar_pct: d.kar_pct, valor: d.valor,
    }], null, null, faiz);
  } catch (e) {
    showToast('Tahmin hatası', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Tahmin Et';
  }
}

// ── Toplu tahmin ──────────────────────────────────────────────────────────────
async function predictBatch() {
  const marka = document.getElementById('bfl-marka').value;
  const seri  = document.getElementById('bfl-seri').value;
  const durum = document.getElementById('bfl-durum').value;
  const faiz  = parseFloat(document.getElementById('bfl-faiz').value) || 0;

  document.getElementById('bfl-loading').style.display = 'flex';
  document.getElementById('bfl-vehicle-list').style.display = 'none';

  try {
    const d = await fetch('/api/bfl/predict-batch', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ marka, seri, durum, annual_rate_pct: faiz }),
    }).then(r => r.json());

    if (d.error) { showToast(d.error, 'error'); return; }
    renderResults(d.results, d.ozet, d.valor_ozet, faiz);
  } catch (e) {
    showToast('Toplu tahmin hatası', 'error');
  } finally {
    document.getElementById('bfl-loading').style.display = 'none';
  }
}

// ── Sonuçları render et ───────────────────────────────────────────────────────
// valorOzet: batch için tüm araçların ay bazlı valör toplamı
// singleValor: tekil tahmin için o aracın ay bazlı valör listesi
function renderResults(results, ozet, valorOzet, faiz, singleValor) {
  // Özet kartlar
  if (ozet) {
    document.getElementById('bfl-summary').style.display = 'block';
    document.getElementById('sum-count').textContent = ozet.arac_sayisi;
    document.getElementById('sum-alis').textContent = '₺' + fmt(ozet.toplam_alis);
    document.getElementById('sum-tahmin').textContent = '₺' + fmt(ozet.toplam_tahmin);
    const karEl = document.getElementById('sum-kar');
    karEl.textContent = (ozet.toplam_kar >= 0 ? '+' : '') + '₺' + fmt(ozet.toplam_kar);
    karEl.style.color = ozet.toplam_kar >= 0 ? GREEN : RED;
  } else {
    document.getElementById('bfl-summary').style.display = 'none';
  }

  // Tablo
  document.getElementById('bfl-table-card').style.display = 'block';
  const tbody = document.getElementById('bfl-tbody');
  tbody.innerHTML = '';
  results.forEach((r, idx) => {
    const karClr = (r.kar || 0) >= 0 ? GREEN : RED;
    const tr = document.createElement('tr');
    tr.style.cssText = 'border-bottom:1px solid var(--gray-100);';
    const hasValor = r.valor && (r.valor.valorlu || r.valor.satilabilir);
    tr.innerHTML = `
      <td style="padding:9px 8px;font-family:var(--font-number);font-weight:600;">${r.plaka || '—'}</td>
      <td style="padding:9px 8px;">${r.marka} ${r.seri || ''}<div style="font-size:11px;color:var(--gray-500);">${r.model || ''}</div></td>
      <td style="padding:9px 8px;">${r.model_yili || '—'}</td>
      <td style="padding:9px 8px;text-align:right;">${r.son_km ? fmt(r.son_km) : '—'}</td>
      <td style="padding:9px 8px;text-align:right;">₺${fmt(r.alis_fiyati)}</td>
      <td style="padding:9px 8px;text-align:right;font-weight:600;color:var(--navy-700);">₺${fmt(r.tahmini_satis)}</td>
      <td style="padding:9px 8px;text-align:right;font-weight:700;color:${karClr};">${(r.kar||0)>=0?'+':''}₺${fmt(r.kar)}</td>
      <td style="padding:9px 8px;text-align:right;color:${karClr};">${r.kar_pct != null ? (r.kar_pct>=0?'+':'')+r.kar_pct+'%' : '—'}</td>`;
    tbody.appendChild(tr);

    // Valör detay satırı (varsa)
    if (hasValor) {
      const v = r.valor;
      const vtr = document.createElement('tr');
      vtr.style.cssText = 'border-bottom:1px solid var(--gray-100);background:var(--off-white);';

      let content;
      if (v.satilabilir) {
        content = `
          <div style="display:flex;flex-wrap:wrap;align-items:center;gap:12px;font-size:12px;">
            <span style="color:var(--green);font-weight:600;">✓ Bugün Satılabilir</span>
            <span style="color:var(--gray-500);">Alış tarihi: <strong style="color:var(--navy-700);">${v.alis_tarihi || '—'}</strong></span>
            <span style="color:var(--gray-500);">Elde tutma: <strong style="color:var(--navy-700);">${fmt(v.elde_tutma_gun)} gün</strong> (min. ${v.min_hold_days} gün tamamlandı)</span>
          </div>`;
      } else if (v.valorlu) {
        content = `
          <div style="display:flex;flex-wrap:wrap;align-items:center;gap:12px;font-size:12px;">
            <span style="color:var(--accent);font-weight:600;">⏳ İleri Tarihli Satış Analizi</span>
            <span style="color:var(--gray-500);">Alış Tarihi: <strong style="color:var(--navy-700);">${v.alis_tarihi}</strong></span>
            <span style="color:var(--gray-500);">En Erken Satış Tarihi: <strong style="color:var(--navy-700);">${v.en_erken_satis}</strong></span>
            <span style="color:var(--gray-500);">Satışa Kalan Süre: <strong style="color:var(--navy-700);">${fmt(v.kalan_gun)} gün</strong></span>
            <span style="background:var(--accent-lt);color:var(--accent);padding:3px 10px;border-radius:6px;font-weight:600;font-family:var(--font-number);">${fmt(v.kalan_gun)} Gün Sonra Tahmini Satış Değeri: ₺${fmt(v.hedef_satis_fiyati)}</span>
          </div>`;
      } else {
        content = `<span style="font-size:12px;color:var(--gray-500);">Valör hesaplanamadı (alış tarihi yok)</span>`;
      }

      vtr.innerHTML = `<td colspan="8" style="padding:10px 14px;">${content}</td>`;
      tbody.appendChild(vtr);
    }
  });

  // Grafikler (sadece batch'te, >1 araç)
  if (results.length > 1) {
    document.getElementById('bfl-charts').style.display = 'block';
    renderKarChart(results);
    renderCompareChart(results);
  } else {
    document.getElementById('bfl-charts').style.display = 'none';
  }

  // Valör özet + grafik
  const valorCard = document.getElementById('bfl-valor-card');
  if (valorCard) {
    if (valorOzet && valorOzet.valorlu_arac > 0) {
      valorCard.style.display = 'block';
      document.getElementById('valor-rate').textContent = faiz;
      renderValorSummary(valorOzet);
      renderValorChart(results.filter(r => r.valor && r.valor.valorlu));
    } else {
      valorCard.style.display = 'none';
    }
  }

  document.getElementById('bfl-table-card').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function renderKarChart(results) {
  const karli   = results.filter(r => (r.kar || 0) > 0).length;
  const zararli = results.filter(r => (r.kar || 0) < 0).length;
  const notr    = results.length - karli - zararli;

  const ctx = document.getElementById('bfl-kar-chart').getContext('2d');
  if (karChart) karChart.destroy();
  karChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Kârlı', 'Zararlı', 'Nötr/Veri yok'],
      datasets: [{ data: [karli, zararli, notr], backgroundColor: [GREEN, RED, '#D8DAE2'], borderWidth: 0 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'right', labels: { font: { size: 12 } } } },
      cutout: '60%',
    },
  });
}

function renderCompareChart(results) {
  const top = results.slice(0, 15);
  const ctx = document.getElementById('bfl-compare-chart').getContext('2d');
  if (compareChart) compareChart.destroy();
  compareChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: top.map(r => r.plaka || '—'),
      datasets: [
        { label: 'Alış', data: top.map(r => r.alis_fiyati), backgroundColor: NAVY, borderRadius: 4 },
        { label: 'Tahmini Satış', data: top.map(r => r.tahmini_satis), backgroundColor: ACCENT, borderRadius: 4 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top' } },
      scales: {
        y: { ticks: { callback: v => '₺' + fmt(v) }, grid: { color: 'rgba(0,0,0,0.05)' } },
        x: { grid: { display: false } },
      },
    },
  });
}

// ── Valör grafiği ─────────────────────────────────────────────────────────────
// function renderValorChart(valorData, isBatch) {
//   const ctx = document.getElementById('bfl-valor-chart').getContext('2d');
//   if (valorChart) valorChart.destroy();

//   const label1 = isBatch ? 'Bugünden Sunulabilecek Toplam Satış' : 'Bugünden Sunulabilecek Satış';
//   valorChart = new Chart(ctx, {
//     type: 'bar',
//     data: {
//       labels: valorData.map(v => v.ay + ' Ay Valör'),
//       datasets: [
//         {
//           label: label1,
//           data: valorData.map(v => v.toplam_bugunku_satis),
//           backgroundColor: ACCENT, borderRadius: 4,
//         },
//         {
//           label: 'Maks. İndirim',
//           data: valorData.map(v => v.toplam_indirim),
//           backgroundColor: GREEN, borderRadius: 4,
//         },
//       ],
//     },
//     options: {
//       responsive: true, maintainAspectRatio: false,
//       plugins: {
//         legend: { position: 'top' },
//         tooltip: {
//           callbacks: {
//             afterBody: (items) => {
//               const i = items[0].dataIndex;
//               return `İndirim oranı: %${valorData[i].indirim_pct}`;
//             },
//           },
//         },
//       },
//       scales: {
//         y: { ticks: { callback: v => '₺' + fmt(v) }, grid: { color: 'rgba(0,0,0,0.05)' } },
//         x: { grid: { display: false } },
//       },
//     },
//   });
// }

// ── Valör özet kartları ───────────────────────────────────────────────────────
function renderValorSummary(ozet) {
  const wrap = document.getElementById('bfl-valor-summary');
  if (!wrap) return;
  wrap.innerHTML = `
    <div class="stat-card" style="padding:14px 16px;">
      <div class="stat-label">Valörlü Araç</div>
      <div class="stat-value bfl-sum-val">${ozet.valorlu_arac}</div>
    </div>
    <div class="stat-card" style="padding:14px 16px;">
      <div class="stat-label">Bugün Satılabilir</div>
      <div class="stat-value bfl-sum-val">${ozet.satilabilir_arac}</div>
    </div>
    <div class="stat-card" style="padding:14px 16px;">
      <div class="stat-label">Bugünkü Toplam Değer</div>
      <div class="stat-value bfl-sum-val">₺${fmt(ozet.toplam_bugun)}</div>
    </div>
    <div class="stat-card" style="padding:14px 16px;">
      <div class="stat-label">Vade Sonu Toplam Hedef</div>
      <div class="stat-value bfl-sum-val" style="color:var(--accent);">₺${fmt(ozet.toplam_hedef)}</div>
    </div>`;
}

// ── Valör grafiği — araç bazlı bugünkü değer vs hedef ──────────────────────────
function renderValorChart(valorluResults) {
  const ctx = document.getElementById('bfl-valor-chart').getContext('2d');
  if (valorChart) valorChart.destroy();

  // En fazla 15 araç göster
  const top = valorluResults.slice(0, 15);
  valorChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: top.map(r => r.plaka || '—'),
      datasets: [
        {
          label: 'Bugünkü Değer',
          data: top.map(r => r.valor.bugunku_fiyat),
          backgroundColor: NAVY, borderRadius: 4,
        },
        {
          label: 'Hedef Satış (kalan gün sonrası)',
          data: top.map(r => r.valor.hedef_satis_fiyati),
          backgroundColor: ACCENT, borderRadius: 4,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top' },
        tooltip: {
          callbacks: {
            afterBody: (items) => {
              const r = top[items[0].dataIndex];
              return [
                `Alış: ${r.valor.alis_tarihi}`,
                `Satışa kalan: ${fmt(r.valor.kalan_gun)} gün`,
              ];
            },
          },
        },
      },
      scales: {
        y: { ticks: { callback: v => '₺' + fmt(v) }, grid: { color: 'rgba(0,0,0,0.05)' } },
        x: { grid: { display: false } },
      },
    },
  });
}