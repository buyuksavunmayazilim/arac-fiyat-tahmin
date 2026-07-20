/* history.js */
const fmt = (n) => new Intl.NumberFormat('tr-TR').format(Math.round(n));

let currentPage = 1;

document.addEventListener('DOMContentLoaded', () => loadHistory(1));

async function loadHistory(page) {
  currentPage = page;
  document.getElementById('history-loading').style.display = 'flex';
  document.getElementById('history-list').innerHTML = '';

  const res = await fetch(`/api/history?page=${page}&per_page=10`);
  const data = await res.json();

  document.getElementById('history-loading').style.display = 'none';

  if (!data.queries?.length) {
    document.getElementById('history-empty').style.display = 'block';
    return;
  }

  document.getElementById('history-count').textContent = `${data.total} sorgu bulundu`;

  const list = document.getElementById('history-list');
  data.queries.forEach((q, i) => {
    const el = document.createElement('div');
    el.className = 'history-item';
    const date = new Date(q.created_at).toLocaleDateString('tr-TR', {
      day:'2-digit', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit'
    });
    el.innerHTML = `
      <div class="history-number">${(page - 1) * 10 + i + 1}</div>
      <div class="history-main">
        <div class="history-title">
          ${[q.marka, q.seri, q.model].filter(Boolean).join(' ') || 'Araç'}
          ${q.model_year ? `(${q.model_year})` : ''}
          ${q.km ? `· ${fmt(q.km)} km` : ''}
        </div>
        <div class="history-meta">
          ${[q.fueloil, q.gear].filter(Boolean).join(' · ')}
          · ${date}
        </div>
      </div>
      <div>
        <div class="history-price">₺${fmt(q.predicted_price)}</div>
        ${q.price_lower ? `<div class="history-range">₺${fmt(q.price_lower)} – ₺${fmt(q.price_upper)}</div>` : ''}
      </div>`;
    list.appendChild(el);
  });

  // Sayfalama
  renderPagination(data.page, data.pages);
}

function renderPagination(current, total) {
  const container = document.getElementById('pagination');
  container.innerHTML = '';
  if (total <= 1) return;

  const prev = document.createElement('button');
  prev.className = 'btn btn-outline btn-sm';
  prev.textContent = '← Önceki';
  prev.disabled = current === 1;
  prev.addEventListener('click', () => loadHistory(current - 1));
  container.appendChild(prev);

  for (let i = 1; i <= total; i++) {
    if (i === 1 || i === total || (i >= current - 1 && i <= current + 1)) {
      const btn = document.createElement('button');
      btn.className = `btn btn-sm ${i === current ? 'btn-primary' : 'btn-outline'}`;
      btn.textContent = i;
      btn.addEventListener('click', () => loadHistory(i));
      container.appendChild(btn);
    } else if (i === current - 2 || i === current + 2) {
      const dots = document.createElement('span');
      dots.textContent = '...';
      dots.style.cssText = 'padding:0 4px;color:var(--gray-400);line-height:36px;';
      container.appendChild(dots);
    }
  }

  const next = document.createElement('button');
  next.className = 'btn btn-outline btn-sm';
  next.textContent = 'Sonraki →';
  next.disabled = current === total;
  next.addEventListener('click', () => loadHistory(current + 1));
  container.appendChild(next);
}
