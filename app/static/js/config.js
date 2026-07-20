/* config.js — Yeni yapı: part_max_pct + status_factor */

const BASE = 1_883_000;
let cfg = {};

const PARTS = [
  "roof","front_hood","rear_hood","front_right_door","front_left_door",
  "rear_right_door","rear_left_door","front_right_mudguard","front_left_mudguard",
  "rear_right_mudguard","rear_left_mudguard","front_bumper","rear_bumper"
];

const PREVIEW = [
  { label:"✅ Hasar yok", parts:{} },
  { label:"🟡 Tavan lokal boyalı", parts:{roof:"localpainted-new"} },
  { label:"🟠 Tavan boyalı", parts:{roof:"painted-new"} },
  { label:"🔴 Tavan değişen", parts:{roof:"changed-new"} },
  { label:"🔴 Kaput değişen", parts:{front_hood:"changed-new"} },
  { label:"🔴 Ön tampon değişen", parts:{front_bumper:"changed-new"} },
  { label:"🔴 Tavan+kaput değişen", parts:{roof:"changed-new",front_hood:"changed-new"} },
  { label:"💀 Tavan+kaput+kapı değişen", parts:{roof:"changed-new",front_hood:"changed-new",front_left_door:"changed-new"} },
  { label:"☑️ Ağır hasar kaydı", parts:{}, heavy:true },
];

document.addEventListener("DOMContentLoaded", async () => {
  await loadCfg();
  renderAll();
  setupButtons();
  updatePreview();
});

async function loadCfg() {
  const res = await fetch("/api/config/damage");
  cfg = await res.json();
  if (!cfg.part_max_pct) cfg.part_max_pct = {};
  if (!cfg.status_factor) cfg.status_factor = {"changed-new":1.0,"painted-new":0.6,"localpainted-new":0.35,"original-new":0.0};
}

function renderAll() {
  // Parça yüzdeleri
  document.querySelectorAll(".cfg-part[data-key]").forEach(el => {
    const key = el.dataset.key, label = el.dataset.label;
    const val = cfg.part_max_pct[key] ?? 0;
    el.className = "cfg-row";
    el.innerHTML = `
      <span class="cfg-row-label">${label}</span>
      <span><input class="cfg-input" type="number" step="0.5" min="0" max="50"
             value="${val}" onchange="onPart('${key}', this.value)"><span class="cfg-suffix">%</span></span>`;
  });

  // Genel ayarlar
  document.querySelectorAll(".cfg-general[data-key]").forEach(el => {
    const key = el.dataset.key, label = el.dataset.label;
    const step = el.dataset.step || "0.5", hint = el.dataset.hint || "";
    const val = cfg[key] ?? 0;
    el.className = "cfg-row";
    el.innerHTML = `
      <div><div class="cfg-row-label">${label}</div>${hint?`<div class="cfg-row-hint">${hint}</div>`:""}</div>
      <input class="cfg-input" type="number" step="${step}" min="0"
             value="${val}" onchange="onGeneral('${key}', this.value)">`;
  });

  // Durum çarpanları
  document.querySelectorAll(".cfg-factor[data-key]").forEach(el => {
    const key = el.dataset.key, label = el.dataset.label, color = el.dataset.color;
    const val = cfg.status_factor[key] ?? 0;
    el.className = "cfg-row";
    el.innerHTML = `
      <span class="cfg-row-label" style="color:${color}">${label}</span>
      <span><input class="cfg-input" type="number" step="0.05" min="0" max="1"
             value="${val}" onchange="onFactor('${key}', this.value)"><span class="cfg-suffix">×</span></span>`;
  });
}

function onPart(key, val)    { cfg.part_max_pct[key] = parseFloat(val)||0; updatePreview(); }
function onGeneral(key, val) { cfg[key] = parseFloat(val)||0; updatePreview(); }
function onFactor(key, val)  { cfg.status_factor[key] = parseFloat(val)||0; updatePreview(); }

function calcDrop(parts, heavy) {
  const maxDrop = (cfg.max_drop_pct||18)/100;
  const heavyPct = (cfg.heavy_damage_pct||15)/100;
  const sf = cfg.status_factor;
  const topN = cfg.top_n_parts||3;

  let scored = [];
  PARTS.forEach(p => {
    const code = parts[p];
    if (!code) return;
    const f = sf[code]||0;
    if (f===0) return;
    scored.push((cfg.part_max_pct[p]||0) * f);
  });
  scored.sort((a,b)=>b-a);
  const partsDrop = scored.slice(0,topN).reduce((s,v)=>s+v,0)/100;
  const heavyFloor = heavy ? heavyPct : 0;
  return Math.min(Math.max(partsDrop, heavyFloor), maxDrop);
}

function updatePreview() {
  const t = document.getElementById("preview-table");
  t.innerHTML = "";
  PREVIEW.forEach(c => {
    const drop = calcDrop(c.parts, c.heavy||false);
    const price = Math.round(BASE*(1-drop)/1000)*1000;
    const pct = (-drop*100).toFixed(1);
    const clr = drop>0 ? "var(--red)" : "var(--green)";
    const row = document.createElement("div");
    row.className = "preview-row";
    row.innerHTML = `
      <span style="font-size:12.5px;">${c.label}</span>
      <span style="font-family:var(--font-display);font-weight:600;font-size:13px;">
        ₺${price.toLocaleString("tr-TR")}
        <span style="color:${clr};font-size:11.5px;"> (${pct}%)</span>
      </span>`;
    t.appendChild(row);
  });
}

function setupButtons() {
  document.getElementById("save-btn").addEventListener("click", save);
  document.getElementById("reset-btn").addEventListener("click", reset);
}

async function save() {
  const payload = {
    part_max_pct: cfg.part_max_pct,
    status_factor: cfg.status_factor,
    top_n_parts: cfg.top_n_parts,
    max_drop_pct: cfg.max_drop_pct,
    heavy_damage_pct: cfg.heavy_damage_pct,
  };
  const res = await fetch("/api/config/damage", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body:JSON.stringify(payload),
  });
  const d = await res.json();
  if (d.success) {
    const s = document.getElementById("save-status");
    s.style.display = "inline";
    setTimeout(()=>{s.style.display="none";}, 3000);
    showToast("Config kaydedildi — tahminler artık yeni değerlerle çalışır", "success");
  } else {
    showToast("Kaydetme hatası: " + (d.error||""), "error");
  }
}

async function reset() {
  if (!confirm("Varsayılanlara sıfırlansın mı?")) return;
  const res = await fetch("/api/config/damage/reset", { method:"POST" });
  if ((await res.json()).success) {
    await loadCfg(); renderAll(); updatePreview();
    showToast("Sıfırlandı");
  }
}
