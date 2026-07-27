/* bfl.js — BFL Filo Araç Tahmin + B2C/B2B + Valör Fiyatlandırma */

const fmt = (n) =>
  new Intl.NumberFormat('tr-TR').format(Math.round(Number(n) || 0));

const NAVY = '#112247';
const ACCENT = '#E8622A';
const GREEN = '#1A9F6E';
const RED = '#D63B3B';
const GRAY = '#8A91A3';

let karChart;
let compareChart;
let valorChart;
let currentVehicles = [];


document.addEventListener('DOMContentLoaded', () => {
  loadOptions();
  setupCascade();

  document
    .getElementById('bfl-list-btn')
    .addEventListener('click', listVehicles);

  document
    .getElementById('bfl-batch-btn')
    .addEventListener('click', predictBatch);
});


// ── Yardımcı fonksiyonlar ────────────────────────────────────────────────────

function getFaizOrani() {
  return parseFloat(document.getElementById('bfl-faiz')?.value) || 0;
}

function getKarColor(value) {
  if (value == null) return GRAY;
  return Number(value) >= 0 ? GREEN : RED;
}

function formatKar(value) {
  if (value == null) return '—';

  const number = Number(value);
  const prefix = number >= 0 ? '+' : '-';

  return `${prefix}₺${fmt(Math.abs(number))}`;
}

function formatKarPct(value) {
  if (value == null) return '—';

  const number = Number(value);
  const prefix = number >= 0 ? '+' : '';

  return `${prefix}${number}%`;
}


// ── Seçenekler ────────────────────────────────────────────────────────────────

async function loadOptions() {
  try {
    const response = await fetch('/api/bfl/options');
    const data = await response.json();

    if (!response.ok || data.error) {
      throw new Error(data.error || 'Filtre seçenekleri alınamadı');
    }

    const markaEl = document.getElementById('bfl-marka');

    (data.markas || []).forEach(marka => {
      const option = document.createElement('option');
      option.value = marka;
      option.textContent = marka;
      markaEl.appendChild(option);
    });

    const durumEl = document.getElementById('bfl-durum');

    (data.durumlar || []).forEach(durum => {
      const option = document.createElement('option');
      option.value = durum;
      option.textContent = durum;
      durumEl.appendChild(option);
    });
  } catch (error) {
    console.error(error);
    showToast('Filtre seçenekleri yüklenemedi', 'error');
  }
}


function setupCascade() {
  const markaEl = document.getElementById('bfl-marka');
  const seriEl = document.getElementById('bfl-seri');

  markaEl.addEventListener('change', async () => {
    const marka = markaEl.value;

    seriEl.innerHTML = '<option value="">Tümü</option>';
    seriEl.disabled = !marka;

    if (!marka) return;

    try {
      const response = await fetch(
        `/api/bfl/series?marka=${encodeURIComponent(marka)}`
      );

      const data = await response.json();

      if (!response.ok || data.error) {
        throw new Error(data.error || 'Seri seçenekleri alınamadı');
      }

      (data.series || []).forEach(seri => {
        const option = document.createElement('option');
        option.value = seri;
        option.textContent = seri;
        seriEl.appendChild(option);
      });
    } catch (error) {
      console.error(error);
      showToast('Seri seçenekleri yüklenemedi', 'error');
    }
  });
}


// ── Araç listeleme ────────────────────────────────────────────────────────────

async function listVehicles() {
  const marka = document.getElementById('bfl-marka').value;
  const seri = document.getElementById('bfl-seri').value;
  const durum = document.getElementById('bfl-durum').value;

  if (!marka) {
    showToast('En az marka seçiniz', 'error');
    return;
  }

  const params = new URLSearchParams();
  params.append('marka', marka);

  if (seri) params.append('seri', seri);
  if (durum) params.append('durum', durum);

  try {
    const response = await fetch(`/api/bfl/vehicles?${params.toString()}`);
    const data = await response.json();

    if (!response.ok || data.error) {
      throw new Error(data.error || 'Araçlar alınamadı');
    }

    currentVehicles = data.vehicles || [];

    const listCard = document.getElementById('bfl-vehicle-list');
    const list = document.getElementById('bfl-vehicles');
    const batchButton = document.getElementById('bfl-batch-btn');

    document.getElementById('bfl-count').textContent =
      currentVehicles.length;

    list.innerHTML = '';

    // Önceki sonuçları gizle
    [
      'bfl-summary',
      'bfl-charts',
      'bfl-table-card',
    ].forEach(id => {
      const element = document.getElementById(id);
      if (element) element.style.display = 'none';
    });

    const valorCard = document.getElementById('bfl-valor-card');
    if (valorCard) valorCard.style.display = 'none';

    if (!currentVehicles.length) {
      listCard.style.display = 'block';

      list.innerHTML = `
        <div style="color:var(--gray-500);font-size:13px;">
          Bu kritere uygun araç bulunamadı.
        </div>
      `;

      batchButton.style.display = 'none';
      return;
    }

    listCard.style.display = 'block';
    batchButton.style.display = 'inline-flex';

    currentVehicles.forEach(vehicle => {
      const element = document.createElement('div');

      element.className = 'bfl-vehicle-card';
      element.dataset.plaka = (vehicle.plaka || '').toLowerCase();

      element.style.cssText = `
        padding:12px 14px;
        border:1.5px solid var(--gray-200);
        border-radius:var(--radius);
        cursor:pointer;
        transition:var(--transition);
        display:flex;
        justify-content:space-between;
        align-items:center;
        gap:16px;
      `;

      element.innerHTML = `
        <div style="min-width:0;">
          <div style="
            font-weight:600;
            font-size:13.5px;
            color:var(--navy-800);
          ">
            <span style="
              font-family:var(--font-number);
              background:var(--navy-50);
              padding:2px 8px;
              border-radius:4px;
              margin-right:8px;
            ">
              ${vehicle.plaka || '—'}
            </span>

            ${vehicle.marka || ''}
            ${vehicle.seri || ''}
            ${vehicle.model_yili || ''}
          </div>

          <div style="
            font-size:12px;
            color:var(--gray-500);
            margin-top:3px;
          ">
            ${vehicle.model || ''}

            ${
              vehicle.son_km
                ? ` · ${fmt(vehicle.son_km)} km`
                : ''
            }

            ${
              vehicle.yakit_tipi
                ? ` · ${vehicle.yakit_tipi}`
                : ''
            }

            <span style="
              background:var(--gray-100);
              padding:1px 7px;
              border-radius:8px;
              margin-left:4px;
            ">
              ${vehicle.plaka_durum || '—'}
            </span>
          </div>
        </div>

        <div style="text-align:right;flex-shrink:0;">
          <div style="font-size:11px;color:var(--gray-500);">
            Alış
          </div>

          <div style="
            font-family:var(--font-number);
            font-weight:700;
            font-size:14px;
            color:var(--navy-700);
          ">
            ₺${fmt(vehicle.alis_fiyati)}
          </div>

          <button
            class="btn btn-sm btn-outline"
            style="margin-top:6px;"
            onclick="
              event.stopPropagation();
              predictSingle(${vehicle.id}, this)
            "
          >
            Tahmin Et
          </button>
        </div>
      `;

      list.appendChild(element);
    });

    setupPlateSearch();
  } catch (error) {
    console.error(error);
    showToast(error.message || 'Araçlar listelenemedi', 'error');
  }
}


function setupPlateSearch() {
  const searchEl = document.getElementById('bfl-search');

  if (!searchEl) return;

  searchEl.value = '';

  searchEl.oninput = () => {
    const term = searchEl.value.toLowerCase().trim();
    let visibleCount = 0;

    document
      .querySelectorAll('.bfl-vehicle-card')
      .forEach(card => {
        const isMatch = card.dataset.plaka.includes(term);

        card.style.display = isMatch ? 'flex' : 'none';

        if (isMatch) visibleCount += 1;
      });

    document.getElementById('bfl-count').textContent = visibleCount;
  };
}


// ── Tekil tahmin ──────────────────────────────────────────────────────────────

async function predictSingle(filoId, button) {
  button.disabled = true;
  button.textContent = '...';

  const faiz = getFaizOrani();

  try {
    const response = await fetch(`/api/bfl/predict/${filoId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        annual_rate_pct: faiz,
      }),
    });

    const data = await response.json();

    if (!response.ok || data.error) {
      throw new Error(data.error || 'Tahmin yapılamadı');
    }

    const result = {
      id: data.arac.id,
      plaka: data.arac.plaka,
      plaka_durum: data.arac.plaka_durum,
      marka: data.arac.marka,
      seri: data.arac.seri,
      model: data.arac.model,
      model_yili: data.arac.model_yili,
      son_km: data.arac.son_km,
      yakit_tipi: data.arac.yakit_tipi,
      vites_tipi: data.arac.vites_tipi,
      alis_fiyati: data.alis_fiyati,

      // B2C / B2B fiyatları
      tahmini_satis: data.tahmini_satis,
      b2c_fiyat: data.b2c_fiyat ?? data.tahmini_satis,
      b2b_fiyat:
        data.b2b_fiyat ??
        (Number(data.tahmini_satis || 0) * 0.90),

      price_lower: data.price_lower,
      price_upper: data.price_upper,

      // B2C kâr
      kar: data.kar,
      kar_pct: data.kar_pct,
      b2c_kar: data.b2c_kar ?? data.kar,
      b2c_kar_pct: data.b2c_kar_pct ?? data.kar_pct,

      // B2B kâr
      b2b_kar: data.b2b_kar,
      b2b_kar_pct: data.b2b_kar_pct,

      valor: data.valor,
    };

    renderResults([result], null, null, faiz);
  } catch (error) {
    console.error(error);
    showToast(error.message || 'Tahmin hatası', 'error');
  } finally {
    button.disabled = false;
    button.textContent = 'Tahmin Et';
  }
}


// ── Toplu tahmin ──────────────────────────────────────────────────────────────

async function predictBatch() {
  const marka = document.getElementById('bfl-marka').value;
  const seri = document.getElementById('bfl-seri').value;
  const durum = document.getElementById('bfl-durum').value;
  const faiz = getFaizOrani();

  const loading = document.getElementById('bfl-loading');
  const vehicleList = document.getElementById('bfl-vehicle-list');

  loading.style.display = 'flex';
  vehicleList.style.display = 'none';

  try {
    const response = await fetch('/api/bfl/predict-batch', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        marka,
        seri,
        durum,
        annual_rate_pct: faiz,
      }),
    });

    const data = await response.json();

    if (!response.ok || data.error) {
      throw new Error(data.error || 'Toplu tahmin yapılamadı');
    }

    renderResults(
      data.results || [],
      data.ozet || null,
      data.valor_ozet || null,
      faiz
    );
  } catch (error) {
    console.error(error);
    showToast(error.message || 'Toplu tahmin hatası', 'error');

    vehicleList.style.display = 'block';
  } finally {
    loading.style.display = 'none';
  }
}


// ── Sonuçları render et ───────────────────────────────────────────────────────

function renderResults(results, ozet, valorOzet, faiz) {
  renderSummary(ozet);
  renderResultsTable(results);
  renderCharts(results);
  renderValorArea(results, valorOzet, faiz);

  document
    .getElementById('bfl-table-card')
    .scrollIntoView({
      behavior: 'smooth',
      block: 'nearest',
    });
}


function renderSummary(ozet) {
  const summary = document.getElementById('bfl-summary');

  if (!ozet) {
    summary.style.display = 'none';
    return;
  }

  summary.style.display = 'block';

  document.getElementById('sum-count').textContent =
    ozet.arac_sayisi;

  document.getElementById('sum-alis').textContent =
    `₺${fmt(ozet.toplam_alis)}`;

  // Backend toplam_tahmin alanı B2C toplamı olarak kullanılıyor
  document.getElementById('sum-tahmin').textContent =
    `₺${fmt(ozet.toplam_tahmin)}`;

  const karElement = document.getElementById('sum-kar');
  const toplamKar = Number(ozet.toplam_kar || 0);

  karElement.textContent = formatKar(toplamKar);
  karElement.style.color = getKarColor(toplamKar);
}


function renderResultsTable(results) {
  const tableCard = document.getElementById('bfl-table-card');
  const tbody = document.getElementById('bfl-tbody');

  tableCard.style.display = 'block';
  tbody.innerHTML = '';

  if (!results.length) {
    tbody.innerHTML = `
      <tr>
        <td
          colspan="11"
          style="
            padding:20px;
            text-align:center;
            color:var(--gray-500);
          "
        >
          Tahmin sonucu bulunamadı.
        </td>
      </tr>
    `;

    return;
  }

  results.forEach(result => {
    appendMainResultRow(tbody, result);
    appendValorDetailRow(tbody, result);
  });
}


function appendMainResultRow(tbody, result) {
  const b2cFiyat =
    result.b2c_fiyat ??
    result.tahmini_satis ??
    0;

  const b2bFiyat =
    result.b2b_fiyat ??
    (Number(b2cFiyat) * 0.90);

  const b2cKar =
    result.b2c_kar ??
    result.kar;

  const b2cKarPct =
    result.b2c_kar_pct ??
    result.kar_pct;

  const b2bKar = result.b2b_kar;
  const b2bKarPct = result.b2b_kar_pct;

  const b2cColor = getKarColor(b2cKar);
  const b2bColor = getKarColor(b2bKar);

  const row = document.createElement('tr');

  row.style.cssText = `
    border-bottom:1px solid var(--gray-100);
  `;

  row.innerHTML = `
    <td style="
      padding:10px 8px;
      font-family:var(--font-number);
      font-weight:600;
      white-space:nowrap;
    ">
      ${result.plaka || '—'}
    </td>

    <td style="padding:10px 8px;min-width:180px;">
      ${result.marka || ''} ${result.seri || ''}

      <div style="
        font-size:11px;
        color:var(--gray-500);
        margin-top:2px;
      ">
        ${result.model || ''}
      </div>
    </td>

    <td style="padding:10px 8px;white-space:nowrap;">
      ${result.model_yili || '—'}
    </td>

    <td style="
      padding:10px 8px;
      text-align:right;
      white-space:nowrap;
      font-family:var(--font-number);
    ">
      ${
        result.son_km != null
          ? fmt(result.son_km)
          : '—'
      }
    </td>

    <td style="
      padding:10px 8px;
      text-align:right;
      white-space:nowrap;
      font-family:var(--font-number);
    ">
      ₺${fmt(result.alis_fiyati)}
    </td>

    <td style="
      padding:10px 8px;
      text-align:right;
      white-space:nowrap;
      font-family:var(--font-number);
      font-weight:700;
      color:var(--navy-700);
    ">
      ₺${fmt(b2cFiyat)}
    </td>

    <td style="
      padding:10px 8px;
      text-align:right;
      white-space:nowrap;
      font-family:var(--font-number);
      font-weight:700;
      color:var(--accent);
    ">
      ₺${fmt(b2bFiyat)}
    </td>

    <td style="
      padding:10px 8px;
      text-align:right;
      white-space:nowrap;
      font-family:var(--font-number);
      font-weight:700;
      color:${b2cColor};
    ">
      ${formatKar(b2cKar)}
    </td>

    <td style="
      padding:10px 8px;
      text-align:right;
      white-space:nowrap;
      color:${b2cColor};
    ">
      ${formatKarPct(b2cKarPct)}
    </td>

    <td style="
      padding:10px 8px;
      text-align:right;
      white-space:nowrap;
      font-family:var(--font-number);
      font-weight:700;
      color:${b2bColor};
    ">
      ${formatKar(b2bKar)}
    </td>

    <td style="
      padding:10px 8px;
      text-align:right;
      white-space:nowrap;
      color:${b2bColor};
    ">
      ${formatKarPct(b2bKarPct)}
    </td>
  `;

  tbody.appendChild(row);
}


function appendValorDetailRow(tbody, result) {
  const valor = result.valor;

  if (!valor) return;

  const hasValorState =
    valor.valorlu ||
    valor.satilabilir;

  if (!hasValorState) return;

  const detailRow = document.createElement('tr');

  detailRow.style.cssText = `
    border-bottom:1px solid var(--gray-100);
    background:#fafbff;
  `;

  let content = '';

  if (valor.satilabilir) {
    content = `
      <div style="
        display:grid;
        grid-template-columns:
          minmax(160px, 0.8fr)
          repeat(3, minmax(140px, 1fr));
        gap:14px;
        align-items:center;
        font-size:12px;
      ">
        <div style="
          color:${GREEN};
          font-weight:700;
          white-space:nowrap;
        ">
          ✓ Bugün Satılabilir
        </div>

        <div>
          <span style="color:var(--gray-500);">
            Alış Tarihi
          </span>

          <br>

          <strong style="color:var(--navy-700);">
            ${valor.alis_tarihi || '—'}
          </strong>
        </div>

        <div>
          <span style="color:var(--gray-500);">
            Elde Tutma
          </span>

          <br>

          <strong style="color:var(--navy-700);">
            ${
              valor.elde_tutma_gun != null
                ? `${fmt(valor.elde_tutma_gun)} gün`
                : '—'
            }
          </strong>
        </div>

        <div>
          <span style="color:var(--gray-500);">
            Minimum Süre
          </span>

          <br>

          <strong style="color:var(--navy-700);">
            ${fmt(valor.min_hold_days)} gün tamamlandı
          </strong>
        </div>
      </div>
    `;
  } else if (valor.valorlu) {
    const b2cFiyat =
      result.b2c_fiyat ??
      result.tahmini_satis ??
      valor.bugunku_fiyat ??
      0;

    const b2bFiyat =
      result.b2b_fiyat ??
      (Number(b2cFiyat) * 0.90);

    content = `
      <div style="
        display:grid;
        grid-template-columns:
          minmax(190px, 1.2fr)
          repeat(5, minmax(125px, 1fr))
          minmax(175px, 1.1fr);
        gap:14px;
        align-items:center;
        font-size:12px;
      ">
        <div style="
          color:var(--accent);
          font-weight:700;
          white-space:nowrap;
        ">
          ⏳ İleri Tarihli Satış Analizi
        </div>

        <div>
          <span style="color:var(--gray-500);">
            Alış Tarihi
          </span>

          <br>

          <strong style="color:var(--navy-700);">
            ${valor.alis_tarihi || '—'}
          </strong>
        </div>

        <div>
          <span style="color:var(--gray-500);">
            En Erken Satış
          </span>

          <br>

          <strong style="color:var(--navy-700);">
            ${valor.en_erken_satis || '—'}
          </strong>
        </div>

        <div>
          <span style="color:var(--gray-500);">
            Satışa Kalan
          </span>

          <br>

          <strong style="color:var(--navy-700);">
            ${fmt(valor.kalan_gun)} gün
          </strong>
        </div>

        <div>
          <span style="color:var(--gray-500);">
            Bugünkü B2C
          </span>

          <br>

          <strong style="color:var(--navy-700);">
            ₺${fmt(b2cFiyat)}
          </strong>
        </div>

        <div>
          <span style="color:var(--gray-500);">
            Bugünkü B2B
          </span>

          <br>

          <strong style="color:var(--accent);">
            ₺${fmt(b2bFiyat)}
          </strong>
        </div>

        <div>
          <span style="color:var(--gray-500);">
            Faiz Oranı
          </span>

          <br>

          <strong style="color:var(--navy-700);">
            %${Number(valor.annual_rate_pct ?? getFaizOrani())}
          </strong>
        </div>

        <div style="
          background:var(--accent-lt);
          color:var(--accent);
          padding:8px 12px;
          border-radius:8px;
          font-weight:700;
          text-align:right;
          white-space:nowrap;
          font-family:var(--font-number);
        ">
          ${fmt(valor.kalan_gun)} Gün Sonra

          <br>

          ₺${fmt(valor.hedef_satis_fiyati)}
        </div>
      </div>
    `;
  }

  detailRow.innerHTML = `
    <td colspan="11" style="padding:12px 14px;">
      ${content}
    </td>
  `;

  tbody.appendChild(detailRow);
}


// ── Grafikler ─────────────────────────────────────────────────────────────────

function renderCharts(results) {
  const charts = document.getElementById('bfl-charts');

  if (results.length <= 1) {
    charts.style.display = 'none';
    return;
  }

  charts.style.display = 'block';

  renderKarChart(results);
  renderCompareChart(results);
}


function renderKarChart(results) {
  /*
   * Kâr dağılımı B2C kârına göre oluşturulur.
   */

  const karli = results.filter(result => {
    const value = result.b2c_kar ?? result.kar;
    return value != null && Number(value) > 0;
  }).length;

  const zararli = results.filter(result => {
    const value = result.b2c_kar ?? result.kar;
    return value != null && Number(value) < 0;
  }).length;

  const notr =
    results.length -
    karli -
    zararli;

  const ctx = document
    .getElementById('bfl-kar-chart')
    .getContext('2d');

  if (karChart) karChart.destroy();

  karChart = new Chart(ctx, {
    type: 'doughnut',

    data: {
      labels: [
        'B2C Kârlı',
        'B2C Zararlı',
        'Nötr / Veri Yok',
      ],

      datasets: [{
        data: [
          karli,
          zararli,
          notr,
        ],

        backgroundColor: [
          GREEN,
          RED,
          '#D8DAE2',
        ],

        borderWidth: 0,
      }],
    },

    options: {
      responsive: true,
      maintainAspectRatio: false,

      plugins: {
        legend: {
          position: 'right',

          labels: {
            font: {
              size: 12,
            },
          },
        },
      },

      cutout: '60%',
    },
  });
}


function renderCompareChart(results) {
  const top = results.slice(0, 15);

  const ctx = document
    .getElementById('bfl-compare-chart')
    .getContext('2d');

  if (compareChart) compareChart.destroy();

  compareChart = new Chart(ctx, {
    type: 'bar',

    data: {
      labels: top.map(result =>
        result.plaka || '—'
      ),

      datasets: [
        {
          label: 'Alış',

          data: top.map(result =>
            Number(result.alis_fiyati) || 0
          ),

          backgroundColor: NAVY,
          borderRadius: 4,
        },

        {
          label: 'B2C Tahmini Satış',

          data: top.map(result =>
            Number(
              result.b2c_fiyat ??
              result.tahmini_satis
            ) || 0
          ),

          backgroundColor: ACCENT,
          borderRadius: 4,
        },

        {
          label: 'B2B Tahmini Satış',

          data: top.map(result =>
            Number(
              result.b2b_fiyat ??
              (
                Number(
                  result.b2c_fiyat ??
                  result.tahmini_satis
                ) * 0.90
              )
            ) || 0
          ),

          backgroundColor: GREEN,
          borderRadius: 4,
        },
      ],
    },

    options: {
      responsive: true,
      maintainAspectRatio: false,

      plugins: {
        legend: {
          position: 'top',
        },

        tooltip: {
          callbacks: {
            label: context => {
              const value = context.parsed.y || 0;
              return `${context.dataset.label}: ₺${fmt(value)}`;
            },
          },
        },
      },

      scales: {
        y: {
          ticks: {
            callback: value =>
              `₺${fmt(value)}`,
          },

          grid: {
            color: 'rgba(0,0,0,0.05)',
          },
        },

        x: {
          grid: {
            display: false,
          },
        },
      },
    },
  });
}


// ── Valör alanı ───────────────────────────────────────────────────────────────

function renderValorArea(results, valorOzet, faiz) {
  const valorCard =
    document.getElementById('bfl-valor-card');

  if (!valorCard) return;

  if (
    !valorOzet ||
    Number(valorOzet.valorlu_arac || 0) <= 0
  ) {
    valorCard.style.display = 'none';

    if (valorChart) {
      valorChart.destroy();
      valorChart = null;
    }

    return;
  }

  valorCard.style.display = 'block';

  document.getElementById('valor-rate').textContent =
    faiz;

  renderValorSummary(valorOzet);

  renderValorChart(
    results.filter(result =>
      result.valor &&
      result.valor.valorlu
    )
  );
}


function renderValorSummary(ozet) {
  const wrap =
    document.getElementById('bfl-valor-summary');

  if (!wrap) return;

  wrap.innerHTML = `
    <div class="stat-card" style="padding:14px 16px;">
      <div class="stat-label">
        Valörlü Araç
      </div>

      <div class="stat-value bfl-sum-val">
        ${ozet.valorlu_arac || 0}
      </div>
    </div>

    <div class="stat-card" style="padding:14px 16px;">
      <div class="stat-label">
        Bugün Satılabilir
      </div>

      <div class="stat-value bfl-sum-val">
        ${ozet.satilabilir_arac || 0}
      </div>
    </div>

    <div class="stat-card" style="padding:14px 16px;">
      <div class="stat-label">
        Bugünkü Toplam B2C Değer
      </div>

      <div class="stat-value bfl-sum-val">
        ₺${fmt(ozet.toplam_bugun)}
      </div>
    </div>

    <div class="stat-card" style="padding:14px 16px;">
      <div class="stat-label">
        Vade Sonu Toplam Hedef
      </div>

      <div
        class="stat-value bfl-sum-val"
        style="color:var(--accent);"
      >
        ₺${fmt(ozet.toplam_hedef)}
      </div>
    </div>

    <div class="stat-card" style="padding:14px 16px;">
      <div class="stat-label">
        Toplam Finansal Fark
      </div>

      <div
        class="stat-value bfl-sum-val"
        style="color:var(--green);"
      >
        ₺${fmt(ozet.toplam_max_indirim)}
      </div>
    </div>
  `;
}


function renderValorChart(valorluResults) {
  const ctx = document
    .getElementById('bfl-valor-chart')
    .getContext('2d');

  if (valorChart) valorChart.destroy();

  const top = valorluResults.slice(0, 15);

  valorChart = new Chart(ctx, {
    type: 'bar',

    data: {
      labels: top.map(result =>
        result.plaka || '—'
      ),

      datasets: [
        {
          label: 'Bugünkü B2C Değer',

          data: top.map(result =>
            Number(
              result.valor?.bugunku_fiyat ??
              result.b2c_fiyat ??
              result.tahmini_satis
            ) || 0
          ),

          backgroundColor: NAVY,
          borderRadius: 4,
        },

        {
          label: 'Bugünkü B2B Değer',

          data: top.map(result =>
            Number(
              result.b2b_fiyat ??
              (
                Number(
                  result.b2c_fiyat ??
                  result.tahmini_satis
                ) * 0.90
              )
            ) || 0
          ),

          backgroundColor: GREEN,
          borderRadius: 4,
        },

        {
          label: 'İleri Tarihli Hedef',

          data: top.map(result =>
            Number(
              result.valor?.hedef_satis_fiyati
            ) || 0
          ),

          backgroundColor: ACCENT,
          borderRadius: 4,
        },
      ],
    },

    options: {
      responsive: true,
      maintainAspectRatio: false,

      plugins: {
        legend: {
          position: 'top',
        },

        tooltip: {
          callbacks: {
            label: context => {
              const value = context.parsed.y || 0;
              return `${context.dataset.label}: ₺${fmt(value)}`;
            },

            afterBody: items => {
              if (!items.length) return [];

              const result =
                top[items[0].dataIndex];

              return [
                `Alış tarihi: ${
                  result.valor?.alis_tarihi || '—'
                }`,

                `Satışa kalan: ${
                  fmt(result.valor?.kalan_gun)
                } gün`,
              ];
            },
          },
        },
      },

      scales: {
        y: {
          ticks: {
            callback: value =>
              `₺${fmt(value)}`,
          },

          grid: {
            color: 'rgba(0,0,0,0.05)',
          },
        },

        x: {
          grid: {
            display: false,
          },
        },
      },
    },
  });
}