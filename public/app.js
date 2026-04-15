/* global app reference for inline handlers */
window.app = null;

(function () {
  'use strict';

  const DATA_URL = 'data.json';

  // ── State ────────────────────────────────────────────
  let articles = [];
  let currentType = 'all';
  let searchQuery = '';

  // ── Type helpers ─────────────────────────────────────
  const TYPE_LABELS = {
    'reseña':      'Reseña',
    'crónica':     'Crónica',
    'entrevista':  'Entrevista',
  };

  const TYPE_CLASSES = {
    'reseña':     'resena',
    'crónica':    'cronica',
    'entrevista': 'entrevista',
  };

  function typeClass(type) {
    return TYPE_CLASSES[type] || 'resena';
  }

  function typeLabel(type) {
    return TYPE_LABELS[type] || type;
  }

  // ── Data loading ─────────────────────────────────────
  async function loadData() {
    showSkeletons();
    const res = await fetch(DATA_URL);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    articles = await res.json();
  }

  // ── Filtering ─────────────────────────────────────────
  function getFiltered() {
    const q = searchQuery;
    return articles.filter(a => {
      const matchType = currentType === 'all' || a.type === currentType ||
        (currentType === 'rockzone' && a.source === 'rockzone');
      if (!matchType) return false;
      if (!q) return true;
      const haystack = (a.title + ' ' + a.subtitle + ' ' + a.excerpt).toLowerCase();
      // Support multi-word: all words must match
      return q.split(/\s+/).every(word => haystack.includes(word));
    });
  }

  // ── Sorting ───────────────────────────────────────────
  function getSorted(filtered) {
    if (currentType !== 'all' || searchQuery) return filtered;
    // In "all" view: RockZone articles first (sorted by date desc), then the rest
    const rz = filtered.filter(a => a.source === 'rockzone')
      .sort((a, b) => (b.date || '').localeCompare(a.date || ''));
    const rest = filtered.filter(a => a.source !== 'rockzone');
    return [...rz, ...rest];
  }

  // ── Rendering: counts ─────────────────────────────────
  function updateCounts() {
    document.getElementById('count-all').textContent    = articles.length;
    document.getElementById('count-reseña').textContent =
      articles.filter(a => a.type === 'reseña').length;
    document.getElementById('count-crónica').textContent =
      articles.filter(a => a.type === 'crónica').length;
    document.getElementById('count-entrevista').textContent =
      articles.filter(a => a.type === 'entrevista').length;
    document.getElementById('count-rockzone').textContent =
      articles.filter(a => a.source === 'rockzone').length;
  }

  // ── Rendering: results label ──────────────────────────
  function updateResultsLabel(count) {
    const el = document.getElementById('results-label');
    if (searchQuery || currentType !== 'all') {
      el.textContent = `${count} ${count === 1 ? 'resultado' : 'resultados'}`;
    } else {
      el.textContent = '';
    }
  }

  // ── Rendering: cards ──────────────────────────────────
  function escapeHtml(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function highlight(text, query) {
    if (!query) return escapeHtml(text);
    const escaped = escapeHtml(text);
    const words = query.trim().split(/\s+/).filter(Boolean);
    let result = escaped;
    words.forEach(word => {
      const re = new RegExp(`(${word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
      result = result.replace(re, '<mark>$1</mark>');
    });
    return result;
  }

  function placeholderInner(tc, tl, initial) {
    return `<span class="ph-initial">${initial}</span><span class="ph-label">${tl}</span>`;
  }

  // exposed for onerror inline handler
  window.placeholderHTML = function(tc, tl, initial) {
    return `<div class="card-art-placeholder ph-${tc}">${placeholderInner(tc, tl, initial)}</div>`;
  };

  function coverArtHTML(article) {
    const tc = typeClass(article.type);
    const tl = typeLabel(article.type);
    const initial = (article.title.replace(/[^A-Z0-9]/gi, '')[0] || '♦').toUpperCase();

    if (article.cover_url) {
      const safeUrl = escapeHtml(article.cover_url);
      const fallback = `this.parentElement.innerHTML=placeholderHTML('${tc}','${tl}','${initial}')`;
      return `<div class="card-art"><img src="${safeUrl}" alt="" loading="lazy" onerror="${fallback}"></div>`;
    }
    return `<div class="card-art"><div class="card-art-placeholder ph-${tc}">${placeholderInner(tc, tl, initial)}</div></div>`;
  }

  function createCardHTML(article) {
    const tc = typeClass(article.type);
    const tl = typeLabel(article.type);
    const titleH = highlight(article.title, searchQuery);
    const subtitleH = highlight(article.subtitle, searchQuery);
    const excerptH = highlight(article.excerpt, searchQuery);
    const rzBadge = article.source === 'rockzone'
      ? '<span class="rz-badge">RockZone</span>'
      : '';

    return `<article class="card card-${tc}" data-slug="${escapeHtml(article.slug)}" tabindex="0" role="button" aria-label="Leer ${escapeHtml(article.title)}">
  ${coverArtHTML(article)}
  <div class="card-info">
    <div class="card-pills">
      <span class="type-pill pill-${tc}">${tl}</span>${rzBadge}
    </div>
    <h2 class="card-title">${titleH}</h2>
    <p class="card-subtitle">${subtitleH}</p>
    <p class="card-excerpt">${excerptH}</p>
    <div class="card-footer">
      <span class="card-cta">Leer &nbsp;→</span>
    </div>
  </div>
</article>`;
  }

  function renderArticles() {
    const grid = document.getElementById('articles-grid');
    const noResults = document.getElementById('no-results');
    const filtered = getFiltered();

    updateResultsLabel(filtered.length);

    if (filtered.length === 0) {
      grid.innerHTML = '';
      noResults.classList.remove('hidden');
      return;
    }

    noResults.classList.add('hidden');
    grid.innerHTML = getSorted(filtered).map(createCardHTML).join('\n');

    grid.querySelectorAll('.card').forEach(card => {
      card.addEventListener('click', () => openModalBySlug(card.dataset.slug));
      card.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          openModalBySlug(card.dataset.slug);
        }
      });
    });
  }

  // ── Skeleton loader ───────────────────────────────────
  function showSkeletons() {
    const grid = document.getElementById('articles-grid');
    grid.innerHTML = Array.from({ length: 12 }, () => `
      <div class="skeleton-card">
        <div class="skeleton-art"></div>
        <div class="skeleton-body">
          <div class="skeleton-line" style="height:10px;width:55px;margin-bottom:.8rem"></div>
          <div class="skeleton-line" style="height:16px;width:90%"></div>
          <div class="skeleton-line" style="height:11px;width:60%;margin-bottom:.8rem"></div>
          <div class="skeleton-line" style="height:10px;width:100%"></div>
          <div class="skeleton-line" style="height:10px;width:85%"></div>
          <div class="skeleton-line" style="height:10px;width:70%"></div>
        </div>
      </div>
    `).join('');
  }

  // ── Modal ─────────────────────────────────────────────
  function openModalBySlug(slug) {
    const article = articles.find(a => a.slug === slug);
    if (!article) return;
    openModal(article);
  }

  function openModal(article) {
    const overlay = document.getElementById('modal-overlay');
    const content = document.getElementById('modal-content');
    const tc = typeClass(article.type);
    const tl = typeLabel(article.type);

    // Unwrap hard-wrapped lines: source files are wrapped at ~70 chars.
    // Detect real paragraph breaks (sentence-ending punctuation followed by
    // a new sentence), then join remaining mid-sentence wraps with a space.
    function normalizeBody(text) {
      const SEP = '\x00';
      return text
        // Preserve existing double-newline paragraph breaks
        .replace(/\n\n/g, SEP)
        // Also detect paragraph breaks: punctuation (optionally followed by
        // closing markdown markers like ** or _) then newline + new sentence
        .replace(/([.?!"][*_]{0,3})\n(\*{0,2}[A-ZÁÉÍÓÚÑÜ"(¡¿])/g, '$1' + SEP + '$2')
        .replace(/\n/g, ' ')
        .replace(/\x00/g, '\n\n')
        .trim();
    }

    marked.setOptions({ breaks: false, gfm: true });

    const bodyHtml = marked.parse(normalizeBody(article.body));
    const shareUrl = `${location.origin}${location.pathname}#${article.slug}`;
    const initial = (article.title.replace(/[^A-Z0-9]/gi, '')[0] || '♦').toUpperCase();

    let coverHtml = '';
    if (article.cover_url) {
      const fallback = `this.parentElement.className='modal-cover-placeholder ph-${tc}'; this.remove()`;
      coverHtml = `<div class="modal-cover"><img src="${escapeHtml(article.cover_url)}" alt="" onerror="${fallback}"></div>`;
    } else {
      coverHtml = `<div class="modal-cover modal-cover-placeholder ph-${tc}" style="display:flex;align-items:center;justify-content:center;gap:.5rem">
        <span class="ph-initial">${initial}</span><span class="ph-label">${tl}</span>
      </div>`;
    }

    content.innerHTML = `
      ${coverHtml}
      <div class="modal-header modal-${tc}">
        <span class="modal-type pill-${tc}">${tl}</span>
        <h1 class="modal-title" id="modal-title">${escapeHtml(article.title)}</h1>
        <p class="modal-subtitle">${escapeHtml(article.subtitle)}</p>
      </div>
      <div class="modal-body">${bodyHtml}</div>
      <div class="modal-share">
        <button class="modal-share-btn" id="copy-link-btn">Copiar enlace</button>
        <span class="modal-share-url">${escapeHtml(shareUrl)}</span>
      </div>
    `;

    // Copy link button
    content.querySelector('#copy-link-btn').addEventListener('click', () => {
      navigator.clipboard.writeText(shareUrl).then(() => {
        const btn = content.querySelector('#copy-link-btn');
        btn.textContent = '¡Copiado!';
        setTimeout(() => { btn.textContent = 'Copiar enlace'; }, 2000);
      });
    });

    overlay.classList.remove('hidden');
    document.body.style.overflow = 'hidden';

    // Scroll modal to top
    overlay.scrollTop = 0;

    // Update URL hash
    history.replaceState(null, '', `#${article.slug}`);
  }

  function closeModal() {
    document.getElementById('modal-overlay').classList.add('hidden');
    document.body.style.overflow = '';
    history.replaceState(null, '', location.pathname + location.search);
  }

  // ── Search ────────────────────────────────────────────
  function setupSearch() {
    const input = document.getElementById('search');
    const clearBtn = document.getElementById('search-clear');
    let timer;

    input.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        searchQuery = input.value.toLowerCase().trim();
        clearBtn.classList.toggle('hidden', !input.value);
        renderArticles();
      }, 200);
    });

    clearBtn.addEventListener('click', () => {
      input.value = '';
      clearBtn.classList.add('hidden');
      searchQuery = '';
      renderArticles();
      input.focus();
    });
  }

  // ── Filters ────────────────────────────────────────────
  function setupFilters() {
    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentType = btn.dataset.type;
        renderArticles();
      });
    });
  }

  // ── Modal events ──────────────────────────────────────
  function setupModal() {
    document.getElementById('modal-close').addEventListener('click', closeModal);

    document.getElementById('modal-overlay').addEventListener('click', e => {
      if (e.target === e.currentTarget) closeModal();
    });

    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') closeModal();
    });
  }

  // ── URL hash handling ─────────────────────────────────
  function handleHash() {
    const slug = location.hash.slice(1);
    if (slug && articles.length) {
      const article = articles.find(a => a.slug === slug);
      if (article) openModal(article);
    }
  }

  window.addEventListener('hashchange', handleHash);

  // ── Public API for inline handlers ───────────────────
  window.app = {
    resetSearch() {
      document.getElementById('search').value = '';
      document.getElementById('search-clear').classList.add('hidden');
      searchQuery = '';
      renderArticles();
    }
  };

  // ── Init ─────────────────────────────────────────────
  async function init() {
    setupSearch();
    setupFilters();
    setupModal();

    try {
      await loadData();
      updateCounts();
      renderArticles();
      handleHash();
    } catch (err) {
      console.error('Error loading data:', err);
      document.getElementById('articles-grid').innerHTML = `
        <div style="grid-column:1/-1;padding:3rem;text-align:center;color:#666;font-family:var(--font-ui);font-size:.9rem;letter-spacing:.1em">
          ERROR CARGANDO DATOS · ${err.message}
        </div>`;
    }
  }

  init();
})();
