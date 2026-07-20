/* compare.js — İkili araç karşılaştırma */

const fmt = (n) => new Intl.NumberFormat('tr-TR').format(Math.round(n));

const FIELDS = [
  { id:'marka', label:'Marka', type:'select', required:true, src:'markas' },
  { id:'model', label:'Model', type:'text', placeholder:'ör: Corolla' },
  { id:'model_year', label:'Model Yılı', type:'number', placeholder:'ör: 2020' },
  { id:'km', label:'Kilometre', type:'number', placeholder:'ör: 75000' },
  { id:'fueloil', label:'Yakıt', type:'select', src:'fueloils' },
  { id:'gear', label:'Vites', type:'select', src:'gears' },
  { id:'engine_power', label:'Motor Gücü (HP)', type:'number', placeholder:'ör: 110' },
  { id:'damage_registered', label:'Hasar Kaydı', type:'checkbox' },
];

const DAMAGE_OPT_MAP = {
  'original-new':     'Orijinal',
  'localpainted-new': 'Lokal Boyalı',
  'painted-new':      'Boyalı',
  'changed-new':      'Değişen',
};

let OPTIONS = {};

document.addEventListener('DOMContentLoaded', async () => {
  const res = await fetch('/api/options');
  OPTIONS = await res.json();
  renderForm('a');
  renderForm('b');
  document.getElementById('compare-btn').addEventListener('click', doCompare);
});

function renderForm(side) {
  const container = document.getElementById(`car-${side}-fields`);
  container.innerHTML = '';
  const grid = document.createElement('div');
  grid.className = 'form-grid';

  FIELDS.forEach(f => {
    const group = document.createElement('div');
    group.className = 'form-group';
    const label = document.createElement('label');
    label.className = 'form-label';
    label.textContent = f.label;
    group.appendChild(label);

    if (f.type === 'select') {
      const sel = document.createElement('select');
      sel.className = 'form-control';
      sel.id = `${side}-${f.id}`;
      sel.innerHTML = '<option value="">Seçiniz...</option>';
      (OPTIONS[f.src] || []).forEach(v => {
        const o = document.createElement('option'); o.value = v; o.textContent = v;
        sel.appendChild(o);
      });
      group.appendChild(sel);
    } else if (f.type === 'checkbox') {
      const lbl = document.createElement('label');
      lbl.className = 'checkbox-label';
      lbl.innerHTML = `<input type="checkbox" id="${side}-${f.id}"><span>Hasar kaydı var</span>`;
      group.appendChild(lbl);
    } else {
      const inp = document.createElement('input');
      inp.className = 'form-control';
      inp.type = f.type; inp.id = `${side}-${f.id}`;
      inp.placeholder = f.placeholder || '';
      group.appendChild(inp);
    }
    grid.appendChild(group);
  });
  container.appendChild(grid);
}

function collectForm(side) {
  const data = {};
  FIELDS.forEach(f => {
    const el = document.getElementById(`${side}-${f.id}`);
    if (!el) return;
    if (f.type === 'checkbox') {
      data[f.id] = el.checked;
    } else if (f.type === 'number') {
      if (el.value) data[f.id] = Number(el.value);
    } else {
      if (el.value) data[f.id] = el.value;
    }
  });
  return data;
}

async function doCompare() {
  const a = collectForm('a');
  const b = collectForm('b');

  document.getElementById('compare-loading').style.display = 'flex';
  document.getElementById('compare-btn').disabled = true;

  try {
    const res = await fetch('/api/compare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ vehicles: [a, b] }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);
    renderCompare(data.comparison);
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    document.getElementById('compare-loading').style.display = 'none';
    document.getElementById('compare-btn').disabled = false;
  }
}

function renderCompare([resA, resB]) {
  document.getElementById('cr-a-price').textContent = fmt(resA.predicted_price);
  document.getElementById('cr-a-range').textContent = `₺${fmt(resA.price_lower)} – ₺${fmt(resA.price_upper)}`;
  document.getElementById('cr-b-price').textContent = fmt(resB.predicted_price);
  document.getElementById('cr-b-range').textContent = `₺${fmt(resB.price_lower)} – ₺${fmt(resB.price_upper)}`;

  renderShap(resA.shap_values, 'shap-a', '#112247');
  renderShap(resB.shap_values, 'shap-b', '#1A9F6E');

  const diff = resB.predicted_price - resA.predicted_price;
  const diffPct = (diff / Math.max(resA.predicted_price, 1) * 100).toFixed(1);
  const cheaper = diff > 0 ? '1. araç' : '2. araç';
  document.getElementById('compare-diff').innerHTML = `
    <div style="display:flex;gap:24px;flex-wrap:wrap;">
      <div class="stat-card" style="padding:14px 20px;">
        <div class="stat-label">Fiyat Farkı</div>
        <div class="stat-value" style="font-size:22px;color:var(--accent);">₺${fmt(Math.abs(diff))}</div>
        <div class="stat-sub">%${Math.abs(diffPct)} fark</div>
      </div>
      <div class="stat-card" style="padding:14px 20px;">
        <div class="stat-label">Daha Uygun</div>
        <div class="stat-value" style="font-size:18px;">${cheaper}</div>
        <div class="stat-sub">₺${fmt(Math.min(resA.predicted_price, resB.predicted_price))}</div>
      </div>
    </div>`;

  document.getElementById('compare-result').style.display = 'block';
  document.getElementById('compare-result').scrollIntoView({ behavior: 'smooth' });
}

function renderShap(shaps, containerId, color) {
  const container = document.getElementById(containerId);
  container.innerHTML = '';
  const maxAbs = Math.max(...shaps.map(s => Math.abs(s.impact_tl)), 1);
  shaps.slice(0, 8).forEach(s => {
    const pct = (Math.abs(s.impact_tl) / maxAbs) * 100;
    const isPos = s.direction === 'positive';
    const div = document.createElement('div');
    div.className = 'shap-item';
    div.style.marginBottom = '10px';
    div.innerHTML = `
      <div class="shap-header">
        <span class="shap-name">${s.feature}</span>
        <span class="shap-val ${isPos?'pos':'neg'}">${isPos?'+':''}₺${fmt(s.impact_tl)}</span>
      </div>
      <div class="shap-track">
        <div class="shap-fill ${isPos?'pos':'neg'}" style="width:${pct}%;background:${isPos?color:'var(--red)'}"></div>
      </div>`;
    container.appendChild(div);
  });
}
