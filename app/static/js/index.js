/* index.js — Ana tahmin formu ve sonuç render */

const fmt = (n) => new Intl.NumberFormat('tr-TR').format(Math.round(n));

// ── Sayfa yüklenince ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadOptions();
  loadStats();
  setupDamageParts();
  setupForm();
  document.getElementById('reset-btn').addEventListener('click', resetForm);
  document.getElementById('new-query-btn')?.addEventListener('click', resetForm);
});

// ── Dropdown seçenekleri ──────────────────────────────────────────────────────
async function loadOptions() {
  try {
    const res = await fetch('/api/options');
    const data = await res.json();

    const markaEl = document.getElementById('f-marka');
    data.markas?.forEach(m => {
      const o = document.createElement('option'); o.value = m; o.textContent = m;
      markaEl.appendChild(o);
    });

    const fuelEl = document.getElementById('f-fueloil');
    data.fueloils?.forEach(f => {
      const o = document.createElement('option'); o.value = f; o.textContent = f;
      fuelEl.appendChild(o);
    });

    const gearEl = document.getElementById('f-gear');
    data.gears?.forEach(g => {
      const o = document.createElement('option'); o.value = g; o.textContent = g;
      gearEl.appendChild(o);
    });

    const ctEl = document.getElementById('f-cartype');
    data.car_types?.forEach(ct => {
      const o = document.createElement('option'); o.value = ct; o.textContent = ct;
      ctEl.appendChild(o);
    });

    const yearEl = document.getElementById('f-year');
    data.years?.forEach(y => {
      const o = document.createElement('option'); o.value = y; o.textContent = y;
      yearEl.appendChild(o);
    });

    // Marka → seri/model cascade
    markaEl.addEventListener('change', onMarkaChange);

  } catch (e) {
    showToast('Seçenekler yüklenemedi', 'error');
  }
}

async function onMarkaChange() {
  const marka = document.getElementById('f-marka').value;
  const seriEl = document.getElementById('f-seri');
  const modelEl = document.getElementById('f-model');

  seriEl.innerHTML = '<option value="">Yükleniyor...</option>';
  seriEl.disabled = true;
  modelEl.innerHTML = '<option value="">Önce seri seçin</option>';
  modelEl.disabled = true;

  if (!marka) { seriEl.innerHTML = '<option value="">Önce marka seçin</option>'; return; }

  const res = await fetch(`/api/options/models?marka=${encodeURIComponent(marka)}`);
  const data = await res.json();

  const seris = [...new Set(data.models?.map(m => m.seri).filter(Boolean))].sort();
  seriEl.innerHTML = '<option value="">Seçiniz...</option>';
  seris.forEach(s => {
    const o = document.createElement('option'); o.value = s; o.textContent = s;
    seriEl.appendChild(o);
  });
  seriEl.disabled = false;

  seriEl.addEventListener('change', () => {
    const seri = seriEl.value;
    const models = data.models?.filter(m => m.seri === seri).map(m => m.model).filter(Boolean).sort();
    modelEl.innerHTML = '<option value="">Seçiniz...</option>';
    models?.forEach(m => {
      const o = document.createElement('option'); o.value = m; o.textContent = m;
      modelEl.appendChild(o);
    });
    modelEl.disabled = false;
  }, { once: false });
}

// ── Stats ─────────────────────────────────────────────────────────────────────
async function loadStats() {
  try {
    const res = await fetch('/api/analytics/stats');
    const d = await res.json();
    document.getElementById('stat-total').textContent = fmt(d.total_vehicles);
    document.getElementById('stat-avg').textContent = '₺' + fmt(d.avg_price);
    document.getElementById('stat-model').textContent = d.active_model || 'Henüz yok';
    document.getElementById('stat-r2').textContent = d.model_r2 ? (d.model_r2 * 100).toFixed(1) + '%' : '–';
    document.getElementById('stats-loading').style.display = 'none';
    document.getElementById('stats-content').style.display = 'block';
  } catch { }
}

// ── Hasar parça dropdown'ları ─────────────────────────────────────────────────
const DAMAGE_PARTS = [
  {key:'front_bumper',     label:'Ön Tampon'},
  {key:'front_hood',       label:'Ön Kaput'},
  {key:'roof',             label:'Tavan'},
  {key:'front_right_mudguard', label:'Sağ Ön Çamurluk'},
  {key:'front_right_door', label:'Sağ Ön Kapı'},
  {key:'rear_right_door',  label:'Sağ Arka Kapı'},
  {key:'rear_right_mudguard',  label:'Sağ Arka Çamurluk'},
  {key:'front_left_mudguard',  label:'Sol Ön Çamurluk'},
  {key:'front_left_door',  label:'Sol Ön Kapı'},
  {key:'rear_left_door',   label:'Sol Arka Kapı'},
  {key:'rear_left_mudguard',   label:'Sol Arka Çamurluk'},
  {key:'rear_hood',        label:'Arka Kaput'},
  {key:'rear_bumper',      label:'Arka Tampon'},
];

const DAMAGE_OPTIONS = [
  {value:'original-new',     label:'Orijinal',     color:'var(--green)'},
  {value:'localpainted-new', label:'Lokal Boyalı', color:'var(--amber)'},
  {value:'painted-new',      label:'Boyalı',       color:'#C78F1A'},
  {value:'changed-new',      label:'Değişen',      color:'var(--red)'},
];

function setupDamageParts() {
  const grid = document.getElementById('damage-parts-grid');
  grid.innerHTML = '';
  DAMAGE_PARTS.forEach(p => {
    const wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex;flex-direction:column;gap:4px;';

    const lbl = document.createElement('label');
    lbl.style.cssText = 'font-size:11.5px;font-weight:600;color:var(--gray-600);letter-spacing:0.03em;text-transform:uppercase;';
    lbl.textContent = p.label;

    const sel = document.createElement('select');
    sel.className = 'form-control';
    sel.id = `dp-${p.key}`;
    sel.name = p.key;
    sel.style.fontSize = '13px';

    DAMAGE_OPTIONS.forEach(opt => {
      const o = document.createElement('option');
      o.value = opt.value;
      o.textContent = opt.label;
      sel.appendChild(o);
    });

    // Seçim değişince renk güncelle
    sel.addEventListener('change', () => updateSelectColor(sel));
    updateSelectColor(sel);

    wrap.appendChild(lbl);
    wrap.appendChild(sel);
    grid.appendChild(wrap);
  });
}

function updateSelectColor(sel) {
  const opt = DAMAGE_OPTIONS.find(o => o.value === sel.value);
  if (opt) {
    sel.style.borderColor = opt.value === 'O' ? 'var(--gray-200)' : opt.color;
    sel.style.color = opt.value === 'O' ? 'var(--gray-800)' : opt.color;
    sel.style.fontWeight = opt.value === 'O' ? '400' : '600';
  }
}

// ── Form submit ───────────────────────────────────────────────────────────────
function setupForm() {
  // Zorunlu alanlara Türkçe uyarı mesajı
  const requiredMsgs = {
    'f-marka':   'Lütfen marka seçin',
    'f-seri':    'Lütfen seri seçin',
    'f-model':   'Lütfen model seçin',
    'f-year':    'Lütfen model yılı seçin',
    'f-km':      'Lütfen kilometre girin',
    'f-fueloil': 'Lütfen yakıt tipi seçin',
    'f-gear':    'Lütfen vites seçin',
  };
  Object.entries(requiredMsgs).forEach(([id, msg]) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('invalid', () => el.setCustomValidity(msg));
    el.addEventListener('input',  () => el.setCustomValidity(''));
    el.addEventListener('change', () => el.setCustomValidity(''));
  });

  document.getElementById('predict-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('predict-btn');
    const loading = document.getElementById('form-loading');
    btn.disabled = true;
    loading.style.display = 'inline-block';

    const fd = new FormData(e.target);
    const payload = {};

    // Standart alanlar
    for (const [k, v] of fd.entries()) {
      if (v === '') continue;
      if (['model_year','km'].includes(k)) payload[k] = Number(v);
      else if (['damage_registered','swap'].includes(k)) payload[k] = true;
      else if (DAMAGE_PARTS.map(p => p.key).includes(k)) continue; // dropdown'lar aşağıda
      else payload[k] = v;
    }

    // Boolean'lar işaretlenmemişse false
    ['damage_registered'].forEach(k => { if (!payload[k]) payload[k] = false; });

    // Hasar dropdown değerleri — seçilmemişse 'original-new'
    DAMAGE_PARTS.forEach(p => {
      const el = document.getElementById(`dp-${p.key}`);
      payload[p.key] = el ? el.value : 'original-new';
    });
    // damage_registered sadece checkbox'tan gelir — parça seçimi etkilemez

    try {
      const res = await fetch('/api/predict', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Tahmin başarısız');
      renderResult(data);
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      btn.disabled = false;
      loading.style.display = 'none';
    }
  });
}

// ── Sonuç render ──────────────────────────────────────────────────────────────
function renderResult(data) {
  document.getElementById('res-price').textContent = fmt(data.predicted_price);
  document.getElementById('res-range').textContent =
    `₺${fmt(data.price_lower)} – ₺${fmt(data.price_upper)}`;
  const conf = data.confidence_pct || 0;
  document.getElementById('res-confidence').style.width = conf + '%';
  document.getElementById('res-conf-text').textContent = `Model güveni: %${conf}`;

  // Hasar etkisi
  const priceGrid = document.querySelector('.result-grid-price');
  if (data.damage_effect) {
    document.getElementById('damage-effect-wrap').style.display = 'block';
    if (priceGrid) priceGrid.classList.remove('no-damage');
    document.getElementById('de-with').textContent    = '₺' + fmt(data.damage_effect.with_damage);
    document.getElementById('de-without').textContent = '₺' + fmt(data.damage_effect.without_damage);
    const impact = data.damage_effect.price_impact_tl;
    const pct    = data.damage_effect.price_impact_pct;
    document.getElementById('de-impact').textContent  = `+₺${fmt(impact)} (+%${pct})`;

    // Top hasarlı parçalar
    const topParts = data.damage_effect.top_damaged_parts || [];
    const isHeavy  = data.damage_effect.is_heavy_damage;

    document.getElementById('de-heavy-msg').style.display = isHeavy ? 'block' : 'none';

    if (topParts.length > 0) {
      document.getElementById('de-top-parts').style.display = 'block';
      const list = document.getElementById('de-parts-list');
      list.innerHTML = '';
      const valColors = {
        'Değişen':      'var(--red)',
        'Boyalı':       '#C78F1A',
        'Lokal Boyalı': 'var(--amber)',
      };
      topParts.forEach(p => {
        const clr = valColors[p.value] || 'var(--gray-600)';
        const el  = document.createElement('div');
        el.style.cssText = 'display:flex;justify-content:space-between;align-items:center;font-size:12.5px;';
        el.innerHTML = `
          <span style="color:var(--gray-700);">${p.part}</span>
          <span style="font-weight:600;color:${clr};background:rgba(0,0,0,0.04);padding:2px 8px;border-radius:4px;">${p.value}</span>`;
        list.appendChild(el);
      });
    } else {
      document.getElementById('de-top-parts').style.display = 'none';
    }
  } else {
    document.getElementById('damage-effect-wrap').style.display = 'none';
    if (priceGrid) priceGrid.classList.add('no-damage');
  }

  // SHAP
  renderShap(data.shap_values || []);

  // Benzer araçlar
  renderSimilar(data.similar_vehicles || []);

  // Sonucu göster
  const resultSection = document.getElementById('result-section');
  resultSection.style.display = 'block';
  resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderShap(shaps) {
  const container = document.getElementById('shap-bars');
  container.innerHTML = '';
  const maxAbs = Math.max(...shaps.map(s => Math.abs(s.impact_tl)), 1);

  const labels = {
    marka_enc:'Marka', model_enc:'Model', seri_enc:'Seri', model_year:'Model Yılı',
    km:'Kilometre', vehicle_age:'Araç Yaşı', log_km:'KM (log)',
    engine_power:'Motor Gücü', engine_size:'Motor Hacmi', damage_count:'Hasar Parça Sayısı',
    damage_ratio:'Hasar Oranı', damage_registered_int:'Hasar Kaydı',
    fueloil_enc:'Yakıt Tipi', gear_enc:'Vites', car_type_enc:'Kasa Tipi',
    is_automatic:'Otomatik Vites', is_electric:'Elektrikli', is_4x4:'4x4',
    km_per_year:'Yıllık KM', guarantee_int:'Garanti',
  };

  shaps.forEach(s => {
    const label = labels[s.feature] || s.feature;
    const pct = (Math.abs(s.impact_tl) / maxAbs) * 100;
    const isPos = s.direction === 'positive';
    const div = document.createElement('div');
    div.className = 'shap-item';
    div.innerHTML = `
      <div class="shap-header">
        <span class="shap-name">${label}</span>
        <span class="shap-val ${isPos?'pos':'neg'}">${isPos?'+':''}₺${fmt(s.impact_tl)}</span>
      </div>
      <div class="shap-track">
        <div class="shap-fill ${isPos?'pos':'neg'}" style="width:${pct}%"></div>
      </div>`;
    container.appendChild(div);
  });
}

function renderSimilar(vehicles) {
  const container = document.getElementById('similar-list');
  container.innerHTML = '';
  if (!vehicles.length) {
    container.innerHTML = '<div style="color:var(--gray-500);font-size:13px;">Benzer ilan bulunamadı.</div>';
    return;
  }
  vehicles.forEach(v => {
    const el = document.createElement('div');
    el.style.cssText = 'padding:12px;border:1.5px solid var(--gray-200);border-radius:var(--radius);cursor:pointer;transition:var(--transition);';
    el.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;">
        <div>
          <div style="font-weight:600;font-size:13.5px;color:var(--navy-800);">${v.marka||''} ${v.model||''}</div>
          <div style="font-size:12px;color:var(--gray-500);">${v.model_year||''} · ${v.km?fmt(v.km)+' km':''}</div>
        </div>
        <div style="font-family:var(--font-number);font-weight:700;font-size:15px;color:var(--navy-700);white-space:nowrap;">
          ₺${fmt(v.price)}
        </div>
      </div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;">
        ${v.fueloil?`<span class="spec-tag">${v.fueloil}</span>`:''}
        ${v.gear?`<span class="spec-tag">${v.gear}</span>`:''}
        <span class="sim-score">%${Math.round(v.similarity_score*100)} benzer</span>
        ${v.damage_registered
          ? '<span class="damage-badge yes">Hasarlı</span>'
          : '<span class="damage-badge no">Hasarsız</span>'}
      </div>`;
    el.addEventListener('mouseenter', () => el.style.borderColor = 'var(--navy-300)');
    el.addEventListener('mouseleave', () => el.style.borderColor = 'var(--gray-200)');
    container.appendChild(el);
  });
}

// ── Reset ─────────────────────────────────────────────────────────────────────
function resetForm() {
  document.getElementById('predict-form').reset();
  document.getElementById('result-section').style.display = 'none';
  document.getElementById('f-seri').disabled = true;
  document.getElementById('f-model').disabled = true;
  // Hasar dropdown'larını sıfırla ve renklerini güncelle
  DAMAGE_PARTS.forEach(p => {
    const el = document.getElementById(`dp-${p.key}`);
    if (el) { el.value = 'original-new'; updateSelectColor(el); }
  });
  window.scrollTo({ top: 0, behavior: 'smooth' });
}