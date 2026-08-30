/* ============================================================
   Multi-Hub — hub_engine.js
   Lógica compartida del frontend: API, tarjetas, iconos,
   animaciones de aparición y navegación.
   ============================================================ */
'use strict';

const api = '/api/v1';
const WA_LINK = 'https://wa.me/50600000000';

/* ---------- Escape HTML ---------- */
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));

/* ---------- Tipos de producto ---------- */
const TYPES = {
  hotel:      { label: 'Hotel',       emoji: '🏨', grad: 'linear-gradient(135deg,#1e1b4b,#4c1d95)' },
  tour:       { label: 'Tour',        emoji: '🧭', grad: 'linear-gradient(135deg,#164e63,#0e7490)' },
  restaurant: { label: 'Restaurante', emoji: '🍽️', grad: 'linear-gradient(135deg,#451a03,#b45309)' },
  event:      { label: 'Evento',      emoji: '🎭', grad: 'linear-gradient(135deg,#2e1065,#7c3aed)' },
  service:    { label: 'Servicio',    emoji: '✨', grad: 'linear-gradient(135deg,#0f172a,#4338ca)' },
  custom:     { label: 'Experiencia', emoji: '🌟', grad: 'linear-gradient(135deg,#172554,#7c3aed)' },
};
const typeInfo = (t) => TYPES[t] || TYPES.custom;

/* ---------- Iconos de categoría por slug/nombre ---------- */
const CAT_EMOJI = {
  hotel: '🏨', hoteles: '🏨', hospedaje: '🏨',
  restaurante: '🍽️', restaurantes: '🍽️', gastronomia: '🍽️', gastronomía: '🍽️',
  tour: '🧭', tours: '🧭', 'tours-y-aventura': '🧭', aventura: '🧭',
  spa: '💆', 'spa-y-bienestar': '💆', bienestar: '💆',
  evento: '🎭', eventos: '🎭',
};
const catEmoji = (c) => CAT_EMOJI[String((c && (c.slug || c.name)) || '').toLowerCase()] || '✨';

/* ---------- Moneda ---------- */
const money = (n, currency) => {
  const v = Number(n) || 0;
  const cur = currency || 'USD';
  try { return new Intl.NumberFormat('en-US', { style: 'currency', currency: cur }).format(v); }
  catch { return `${cur} ${v.toFixed(2)}`; }
};

/* ---------- API ---------- */
async function products(opts = {}) {
  const params = new URLSearchParams({ status: 'active' });
  if (opts.q) params.set('search', opts.q);
  if (opts.category) params.set('category', opts.category);
  if (opts.type) params.set('type', opts.type);
  const r = await fetch(`${api}/products?${params}`);
  return r.ok ? r.json() : [];
}
async function categories() {
  const r = await fetch(`${api}/categories`);
  return r.ok ? r.json() : [];
}
async function product(id) {
  const r = await fetch(`${api}/products/${encodeURIComponent(id)}`);
  if (!r.ok) throw new Error('No se pudo cargar la experiencia.');
  return r.json();
}

/* ---------- Imágenes con fallback ---------- */
const phHTML = (type) => {
  const t = typeInfo(type);
  return `<div class="ph" style="background:${t.grad}" aria-hidden="true"><span>${t.emoji}</span></div>`;
};
const imgHTML = (p, extraClass = '') => {
  const src = (p.images && p.images[0]) || '';
  if (!src) return phHTML(p.product_type);
  return `<img class="ph-img ${extraClass}" src="${esc(src)}" alt="${esc(p.name)}" loading="lazy" onerror="imgFail(this)" data-type="${esc(p.product_type)}">`;
};
window.imgFail = function (el) {
  const d = document.createElement('div');
  d.className = 'ph';
  d.setAttribute('aria-hidden', 'true');
  const t = typeInfo(el.dataset.type);
  d.style.background = t.grad;
  d.innerHTML = `<span>${t.emoji}</span>`;
  el.replaceWith(d);
};

/* ---------- Tarjeta de producto premium ---------- */
const card = (p, opts = {}) => {
  const t = typeInfo(p.product_type);
  const venue = p.metadata && p.metadata.venue;
  const typeBadge = `<span class="badge card-type">${t.emoji} ${t.label}</span>`;
  return `
  <a class="card reveal ${opts.cls || ''}" href="product.html?id=${esc(p.id)}" aria-label="Ver ${esc(p.name)}">
    <div class="card-media">
      ${imgHTML(p)}
      ${typeBadge}
    </div>
    <div class="card-body">
      ${venue ? `<p class="card-venue"><svg class="ic" aria-hidden="true"><use href="#i-pin"/></svg> ${esc(venue)}</p>` : ''}
      <h3 class="card-name">${esc(p.name)}</h3>
      ${p.description_short || p.description ? `<p class="card-desc">${esc(p.description_short || p.description)}</p>` : ''}
      <div class="card-foot">
        <span class="card-price">${money(p.base_price, p.currency)}</span>
        <span class="card-link">Reservar <svg class="ic" aria-hidden="true"><use href="#i-arrow"/></svg></span>
      </div>
    </div>
  </a>`;
};

/* ---------- Animación de aparición (IntersectionObserver) ---------- */
function reveal(scope = document) {
  const els = scope.querySelectorAll('.reveal:not(.in)');
  if (!('IntersectionObserver' in window)) {
    els.forEach((el) => el.classList.add('in'));
    return;
  }
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) {
        e.target.classList.add('in');
        io.unobserve(e.target);
      }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -40px' });
  els.forEach((el, i) => {
    el.style.transitionDelay = `${Math.min(i * 55, 320)}ms`;
    io.observe(el);
  });
}

/* ---------- Navegación (scroll + menú móvil) ---------- */
function initNav() {
  const nav = document.querySelector('.nav');
  const toggle = document.querySelector('.nav-toggle');
  const mobile = document.querySelector('.nav-mobile');
  if (nav) {
    const onScroll = () => nav.classList.toggle('scrolled', window.scrollY > 12);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
  }
  if (toggle && mobile) {
    toggle.addEventListener('click', () => {
      const open = mobile.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(open));
      toggle.querySelector('.ic-open').style.display = open ? 'none' : '';
      toggle.querySelector('.ic-close').style.display = open ? '' : 'none';
    });
    mobile.querySelectorAll('a').forEach((a) => a.addEventListener('click', () => {
      mobile.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
      toggle.querySelector('.ic-open').style.display = '';
      toggle.querySelector('.ic-close').style.display = 'none';
    }));
  }
}

/* ---------- Año en footer ---------- */
function initYear() {
  document.querySelectorAll('.year').forEach((el) => { el.textContent = new Date().getFullYear(); });
}

/* ---------- Newsletter (solo UI: "Próximamente") ---------- */
function initNewsletter() {
  document.querySelectorAll('.news-form').forEach((form) => {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const note = form.parentElement.querySelector('.news-note');
      if (note) {
        note.innerHTML = '<span class="news-ok">Próximamente — estamos preparando algo especial.</span>';
      }
    });
  });
}
