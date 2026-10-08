/* DesiTV — client app.
 * Vanilla JS, no build step: browse channels, resolve what is live right now,
 * and play from the broadcaster's own source (YouTube live embed or public HLS).
 */
(() => {
  'use strict';

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const initials = (name) =>
    name
      .replace(/[^\p{L}\p{N} ]/gu, ' ')
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((w) => w[0])
      .join('')
      .toUpperCase();

  const LS = {
    favs: 'desitv.favs',
    recents: 'desitv.recents',
    theme: 'desitv.theme',
  };
  const readLS = (k, fb) => {
    try {
      const v = JSON.parse(localStorage.getItem(k) ?? 'null');
      return v ?? fb;
    } catch {
      return fb;
    }
  };
  const writeLS = (k, v) => {
    try {
      localStorage.setItem(k, JSON.stringify(v));
    } catch {
      /* storage disabled */
    }
  };

  /* ---------------- state ---------------- */

  const state = {
    channels: [],
    resolver: null,
    ready: false,
    filters: { q: '', category: 'all', language: 'all', region: 'all', favsOnly: false, sort: 'featured' },
    favs: new Set(readLS(LS.favs, [])),
    recents: readLS(LS.recents, []),
    live: new Map(), // id -> {state, videoId, title, thumb, at}
    resolving: new Set(),
    route: { name: 'browse', id: null },
    player: null, // { kind:'yt'|'hls', cleanup() }
  };

  const CATEGORY_LABELS = {
    all: 'All',
    news: 'News',
    business: 'Business',
    public: 'Doordarshan & Govt',
    devotional: 'Devotional',
    sports: 'Sports',
    entertainment: 'Entertainment',
    music: 'Music',
    kids: 'Kids',
  };

  /* ---------------- boot ---------------- */

  async function boot() {
    applyTheme(readLS(LS.theme, 'dark'));
    bindUI();
    renderSkeletons();
    try {
      const res = await fetch('/api/channels', { headers: { accept: 'application/json' } });
      const data = await res.json();
      state.channels = data.channels || [];
      state.resolver = data.resolver || null;
      state.ready = true;
      buildFilters();
      render();
      paintResolverStatus();
      routeFromHash();
      warmLiveRail();
      reportFootnote(data);
      if (data.resolver && data.resolver.outbound === false && data.resolver.caveat) {
        showNotice(
          `<strong>Heads up:</strong> ${esc(data.resolver.caveat)}`,
        );
      }
    } catch (err) {
      showNotice(`<strong>Could not load the channel list.</strong> ${esc(err.message)}`);
    }
  }

  function reportFootnote(data) {
    const verified = state.channels.filter((c) => c.youtube && c.youtube.verified).length;
    const when =
      typeof data.updated === 'number'
        ? new Date(data.updated).toISOString().slice(0, 10)
        : data.updated || 'recently';
    $('#footnote').textContent =
      `${state.channels.length} channels · ${verified} with an officially verified YouTube channel ID · catalogue updated ${when} · ` +
      'Streams may be geo-restricted, ad-supported and can go offline without notice — each channel links back to its official page.';
  }

  /* ---------------- theme & UI wiring ---------------- */

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme === 'light' ? 'light' : 'dark';
    writeLS(LS.theme, theme);
    const meta = $('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', theme === 'light' ? '#ffffff' : '#0b1020');
  }

  function bindUI() {
    $('#theme-toggle').addEventListener('click', () => {
      applyTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light');
    });

    const search = $('#search');
    $('#search-form').addEventListener('submit', (e) => e.preventDefault());
    search.addEventListener('input', debounce(() => {
      state.filters.q = search.value.trim();
      $('#search-clear').hidden = !state.filters.q;
      renderGrid();
    }, 120));
    $('#search-clear').addEventListener('click', () => {
      search.value = '';
      state.filters.q = '';
      $('#search-clear').hidden = true;
      renderGrid();
      search.focus();
    });

    $('#fav-toggle').addEventListener('click', () => {
      state.filters.favsOnly = !state.filters.favsOnly;
      $('#fav-toggle').setAttribute('aria-pressed', String(state.filters.favsOnly));
      renderGrid();
      if (state.filters.favsOnly) toast(state.favs.size ? 'Showing your favourites' : 'No favourites yet — tap the ☆ on a channel');
    });

    $('#sort-select').addEventListener('change', (e) => {
      state.filters.sort = e.target.value;
      renderGrid();
    });

    $('#clear-filters').addEventListener('click', clearFilters);
    $('#refresh-live').addEventListener('click', () => {
      warmLiveRail(true);
      toast('Re-checking which channels are live…');
    });

    $('#watch-close').addEventListener('click', () => closeWatch());
    $('#player-reload').addEventListener('click', () => {
      const id = state.route.id;
      if (id) openWatch(id, { force: true });
    });
    $('#watch-share').addEventListener('click', async () => {
      const url = location.href;
      try {
        await navigator.clipboard.writeText(url);
        toast('Link copied');
      } catch {
        toast(url);
      }
    });
    $('#watch-fav').addEventListener('click', () => toggleFav(state.route.id));
    $('#watch-fullscreen').addEventListener('click', () => toggleFullscreen());

    window.addEventListener('hashchange', routeFromHash);

    document.addEventListener('keydown', (e) => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || '');
      if (e.key === '/' && !typing) {
        e.preventDefault();
        $('#search').focus();
        return;
      }
      if (e.key === 'Escape') {
        if (state.route.name === 'watch') closeWatch();
        else if (document.activeElement === $('#search')) $('#search').blur();
        return;
      }
      if (typing) return;
      if (state.route.name === 'watch') {
        if (e.key === 'ArrowRight') zap(1);
        else if (e.key === 'ArrowLeft') zap(-1);
        else if (e.key.toLowerCase() === 'r') $('#player-reload').click();
      }
      if (e.key.toLowerCase() === 'f') {
        if (state.route.name === 'watch') toggleFullscreen();
        else $('#fav-toggle').click();
      }
      if (e.key.toLowerCase() === 't') $('#theme-toggle').click();
    });

    // YouTube iframe → parent messages (readiness / errors)
    window.addEventListener('message', onYouTubeMessage);
  }

  function showNotice(html) {
    const el = $('#notice');
    el.innerHTML = html;
    el.hidden = false;
  }

  function clearFilters() {
    state.filters = { ...state.filters, q: '', category: 'all', language: 'all', region: 'all', favsOnly: false };
    $('#search').value = '';
    $('#search-clear').hidden = true;
    $('#fav-toggle').setAttribute('aria-pressed', 'false');
    buildFilters();
    renderGrid();
  }

  function paintResolverStatus() {
    const el = $('#resolver-status');
    const text = $('.status-text', el);
    el.classList.remove('ok', 'warn', 'down');
    if (!state.resolver) return;
    if (state.resolver.outbound === true) {
      el.classList.add('ok');
      text.textContent = 'live resolver online';
      el.title = 'The server can reach YouTube, so live channels are resolved automatically.';
    } else if (state.resolver.outbound === false) {
      el.classList.add('warn');
      text.textContent = 'resolver offline';
      el.title = 'This server has no outbound internet: players still work, but the "live now" list uses last-known streams.';
    } else {
      el.classList.add('warn');
      text.textContent = 'resolver idle';
      el.title = 'The resolver has not run yet.';
    }
  }

  /* ---------------- filters ---------------- */

  function buildFilters() {
    const count = (key) => {
      const m = new Map();
      for (const c of state.channels) m.set(c[key], (m.get(c[key]) || 0) + 1);
      return [...m.entries()].sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(b[0]));
    };

    renderChips(
      $('#category-chips'),
      [['all', state.channels.length], ...count('category').map(([k, n]) => [k, n])],
      'category',
      (k) => CATEGORY_LABELS[k] || k,
    );
    renderChips($('#language-chips'), [['all', state.channels.length], ...count('language')], 'language', (k) => k);
    renderChips($('#region-chips'), [['all', state.channels.length], ...count('region')], 'region', (k) => k);
    renderRecents();
  }

  function renderChips(host, entries, key, label) {
    host.innerHTML = '';
    for (const [value, n] of entries) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'chip';
      b.setAttribute('aria-pressed', String(state.filters[key] === value));
      b.innerHTML = `${esc(label(value))}<span class="n">${n}</span>`;
      b.addEventListener('click', () => {
        state.filters[key] = value;
        $$('.chip', host).forEach((c) => c.setAttribute('aria-pressed', 'false'));
        b.setAttribute('aria-pressed', 'true');
        renderGrid();
      });
      host.appendChild(b);
    }
  }

  function renderRecents() {
    const list = $('#recent-list');
    const block = $('#recent-block');
    const items = state.recents.map((id) => state.channels.find((c) => c.id === id)).filter(Boolean).slice(0, 6);
    block.hidden = !items.length;
    list.innerHTML = '';
    for (const c of items) {
      const li = document.createElement('li');
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = c.name;
      b.addEventListener('click', () => openWatch(c.id));
      li.appendChild(b);
      list.appendChild(li);
    }
  }

  /* ---------------- filtering & grid ---------------- */

  function visibleChannels() {
    const { q, category, language, region, favsOnly, sort } = state.filters;
    const needle = q.toLowerCase();
    let list = state.channels.filter((c) => {
      if (favsOnly && !state.favs.has(c.id)) return false;
      if (category !== 'all' && c.category !== category) return false;
      if (language !== 'all' && c.language !== language) return false;
      if (region !== 'all' && c.region !== region) return false;
      if (!needle) return true;
      const hay = [c.name, c.native, c.language, c.region, c.category, ...(c.tags || []), c.youtube?.handle]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return hay.includes(needle);
    });
    if (sort === 'name') list = list.slice().sort((a, b) => a.name.localeCompare(b.name));
    else if (sort === 'language') list = list.slice().sort((a, b) => a.language.localeCompare(b.language) || a.name.localeCompare(b.name));
    else if (sort === 'region') list = list.slice().sort((a, b) => a.region.localeCompare(b.region) || a.name.localeCompare(b.name));
    else
      list = list
        .slice()
        .sort((a, b) => (liveRank(b) - liveRank(a)) || (favRank(b) - favRank(a)) || a.name.localeCompare(b.name));
    return list;
  }

  const liveRank = (c) => (state.live.get(c.id)?.state === 'live' ? 2 : 0);
  const favRank = (c) => (state.favs.has(c.id) ? 1 : 0);

  function renderSkeletons() {
    const grid = $('#grid');
    grid.innerHTML = '';
    for (let i = 0; i < 12; i++) {
      const d = document.createElement('div');
      d.className = 'skeleton';
      d.innerHTML = '<div class="sk-thumb"></div><div class="sk-line"></div><div class="sk-line short"></div>';
      grid.appendChild(d);
    }
  }

  function render() {
    renderGrid();
    renderLiveRail();
  }

  function renderGrid() {
    const grid = $('#grid');
    const list = visibleChannels();
    $('#result-count').textContent = `${list.length} channel${list.length === 1 ? '' : 's'}`;
    $('#grid-title').textContent = state.filters.favsOnly
      ? 'Your favourites'
      : state.filters.q
        ? `Results for “${state.filters.q}”`
        : 'All channels';
    $('#empty-state').hidden = list.length > 0;
    grid.innerHTML = '';
    const frag = document.createDocumentFragment();
    for (const c of list) frag.appendChild(channelCard(c));
    grid.appendChild(frag);
    observeCards();
    resolveVisible();
  }

  function channelCard(c) {
    const node = $('#channel-card').content.firstElementChild.cloneNode(true);
    const live = state.live.get(c.id);
    node.dataset.id = c.id;
    node.dataset.live = live?.state === 'live' ? '1' : '0';
    node.setAttribute('aria-label', `Watch ${c.name} — ${c.language}, ${c.region}`);
    node.style.setProperty('--brand', c.color || '#334155');

    const img = $('.thumb-img', node);
    const thumb = live?.thumb || null;
    if (thumb) {
      img.src = thumb;
      img.hidden = false;
      img.addEventListener('error', () => {
        img.hidden = true;
      });
    }
    $('.initials', node).textContent = initials(c.name);
    $('.live-flag', node).hidden = live?.state !== 'live';
    $('.card-name', node).innerHTML = `${esc(c.name)}${c.native ? `<span class="native">${esc(c.native)}</span>` : ''}`;
    $('.pill.lang', node).textContent = c.language;
    $('.pill.region', node).textContent = c.region;
    const v = $('.verified', node);
    v.hidden = !c.youtube?.verified;
    const titleEl = $('.card-title', node);
    if (live?.title) {
      titleEl.textContent = live.title;
      titleEl.hidden = false;
    }
    node.addEventListener('click', () => openWatch(c.id));
    return node;
  }

  /* ---------------- live status ---------------- */

  function liveLabel(entry) {
    switch (entry?.state) {
      case 'live':
        return { text: 'LIVE', cls: 'ok' };
      case 'offline':
        return { text: 'offline', cls: 'warn' };
      case 'unreachable':
        return { text: 'last known', cls: 'warn' };
      default:
        return { text: 'unknown', cls: '' };
    }
  }

  let observer = null;
  function observeCards() {
    if (observer) observer.disconnect();
    if (!('IntersectionObserver' in window)) return;
    observer = new IntersectionObserver(
      (entries) => {
        const ids = entries.filter((e) => e.isIntersecting).map((e) => e.target.dataset.id);
        if (ids.length) queueResolve(ids);
      },
      { rootMargin: '200px' },
    );
    $$('.card').forEach((card) => observer.observe(card));
  }

  function resolveVisible() {
    if (!state.ready) return;
    queueResolve(visibleChannels().slice(0, 12).map((c) => c.id));
  }

  const resolveQueue = new Set();
  let resolveTimer = null;
  function queueResolve(ids) {
    const fresh = ids.filter((id) => {
      const hit = state.live.get(id);
      return !state.resolving.has(id) && (!hit || Date.now() - hit.at > 4 * 60 * 1000);
    });
    fresh.forEach((id) => resolveQueue.add(id));
    if (!resolveQueue.size) return;
    clearTimeout(resolveTimer);
    resolveTimer = setTimeout(flushResolve, 350);
  }

  async function flushResolve(force = false) {
    const ids = [...resolveQueue].slice(0, 24);
    resolveQueue.clear();
    if (!ids.length) return;
    ids.forEach((id) => state.resolving.add(id));
    try {
      const res = await fetch(`/api/live?ids=${encodeURIComponent(ids.join(','))}${force ? '&force=1' : ''}`);
      const data = await res.json();
      for (const [id, entry] of Object.entries(data.results || {})) {
        state.live.set(id, { ...entry, at: Date.now() });
      }
      if (typeof data.outbound === 'boolean' && state.resolver) {
        if (state.resolver.outbound !== data.outbound) {
          state.resolver.outbound = data.outbound;
          paintResolverStatus();
        }
      }
      renderGrid();
      renderLiveRail();
    } catch {
      /* offline server: keep whatever we had */
    } finally {
      ids.forEach((id) => state.resolving.delete(id));
    }
  }

  function warmLiveRail(force = false) {
    const ids = state.channels
      .filter((c) => c.youtube)
      .sort((a, b) => favRank(b) - favRank(a))
      .map((c) => c.id)
      .slice(0, 24);
    resolveQueue.clear();
    ids.forEach((id) => resolveQueue.add(id));
    flushResolve(force);
  }

  function railCandidates() {
    const resolverOffline = state.resolver?.outbound === false;
    return state.channels
      .map((c) => {
        const entry = state.live.get(c.id);
        if (entry?.state === 'live') return { channel: c, entry, kind: 'live' };
        // When this server cannot reach YouTube, fall back to the last-known
        // stream from the catalogue so the rail is still useful — clearly
        // labelled as "recent" rather than "live".
        if (resolverOffline && c.youtube?.seed) {
          return {
            channel: c,
            entry: { state: 'seed', videoId: c.youtube.seed, at: 0 },
            kind: 'recent',
          };
        }
        return null;
      })
      .filter(Boolean);
  }

  function renderLiveRail() {
    const rail = $('#live-rail');
    const block = $('#live-rail-block');
    const candidates = railCandidates();
    const ordered = [
      ...candidates.filter((x) => x.kind === 'live'),
      ...candidates.filter((x) => x.kind === 'recent'),
    ].slice(0, 18);

    const anyResolved = state.channels.some((c) => state.live.has(c.id));
    const resolverOffline = state.resolver?.outbound === false;

    if (!ordered.length) {
      block.hidden = false;
      rail.innerHTML = anyResolved
        ? `<p class="rail-empty footnote">Nothing resolved as live right now. Every channel below is still playable — open any of them to load its current stream.</p>`
        : `<p class="rail-empty footnote">Checking which channels are broadcasting…</p>`;
      return;
    }

    const heading = $('.section-head h2', block);
    if (heading) {
      heading.innerHTML = resolverOffline
        ? '<span class="live-dot" aria-hidden="true"></span> Recently live (resolver offline)'
        : '<span class="live-dot" aria-hidden="true"></span> Live right now';
    }

    rail.innerHTML = '';
    for (const { channel: c, entry, kind } of ordered) {
      const card = document.createElement('button');
      card.type = 'button';
      card.className = 'rail-card';
      card.style.setProperty('--brand', c.color || '#334155');
      const badge =
        kind === 'live'
          ? '<span class="badge-live">LIVE</span>'
          : '<span class="badge-live badge-recent">RECENT</span>';
      card.innerHTML = `
        <span class="rail-thumb">
          ${
            entry?.thumb
              ? `<img src="${esc(entry.thumb)}" alt="" loading="lazy" />`
              : `<span class="initials" style="background:linear-gradient(140deg,${esc(c.color || '#334155')},#0b1020)">${esc(initials(c.name))}</span>`
          }
          ${badge}
          <span class="badge-lang">${esc(c.language)}</span>
        </span>
        <span class="rail-head"><span class="rail-name">${esc(c.name)}</span></span>
        <span class="rail-title">${esc(
          entry?.title ||
            (kind === 'live' ? `${c.name} — live stream` : `Last known live stream — open to reload`),
        )}</span>`;
      card.addEventListener('click', () => openWatch(c.id));
      rail.appendChild(card);
    }
  }

  /* ---------------- routing ---------------- */

  function routeFromHash() {
    const hash = location.hash.replace(/^#\/?/, '');
    const parts = hash.split('/').filter(Boolean);
    if (parts[0] === 'watch' && parts[1]) {
      openWatch(parts[1], { fromHash: true });
    } else {
      closeWatch({ fromHash: true });
    }
  }

  function pushHash(hash) {
    if (location.hash !== hash) history.pushState(null, '', hash);
  }

  window.addEventListener('popstate', routeFromHash);

  /* ---------------- watch ---------------- */

  function openWatch(id, { force = false, fromHash = false } = {}) {
    const channel = state.channels.find((c) => c.id === id);
    if (!channel) {
      toast('Channel not found');
      return;
    }
    state.route = { name: 'watch', id };
    document.body.style.overflow = 'hidden';
    $('#watch').hidden = false;

    // remember
    state.recents = [id, ...state.recents.filter((r) => r !== id)].slice(0, 12);
    writeLS(LS.recents, state.recents);
    renderRecents();

    paintWatchHeader(channel);
    renderSideList(channel);
    if (!fromHash) pushHash(`#/watch/${id}`);

    const cached = state.live.get(channel.id);
    const fresh = cached && Date.now() - cached.at < 4 * 60 * 1000;
    const seeded = channel.youtube?.seed
      ? { state: 'seed', videoId: channel.youtube.seed, at: 0, note: 'Last known live stream — the broadcaster may have rotated it.' }
      : null;
    // Prefer a fresh resolution, then anything we already resolved, then the
    // catalogue's last-known stream so playback starts instantly.
    const start = force ? null : fresh && cached.videoId ? cached : cached?.videoId ? cached : seeded;

    mountPlayer(channel, start, { force });
  }

  function closeWatch({ fromHash = false } = {}) {
    destroyPlayer();
    $('#watch').hidden = true;
    document.body.style.overflow = '';
    state.route = { name: 'browse', id: null };
    if (!fromHash && location.hash) pushHash('#/');
  }

  function paintWatchHeader(channel) {
    $('#watch-badge').style.setProperty('--brand', channel.color || '#334155');
    $('#watch-badge').textContent = initials(channel.name);
    $('#watch-title').textContent = channel.name;
    const bits = [
      CATEGORY_LABELS[channel.category] || channel.category,
      channel.language,
      channel.region,
      channel.youtube?.verified ? 'verified official channel' : null,
    ].filter(Boolean);
    $('#watch-sub').innerHTML =
      bits.map((b) => `<span class="pill">${esc(b)}</span>`).join('') +
      (channel.native ? `<span class="pill">${esc(channel.native)}</span>` : '');

    $('#watch-fav').setAttribute('aria-pressed', String(state.favs.has(channel.id)));
    const ytUrl = channel.youtube?.channelId
      ? `https://www.youtube.com/channel/${channel.youtube.channelId}/live`
      : channel.youtube?.handle
        ? `https://www.youtube.com/${channel.youtube.handle}/live`
        : channel.web || '#';
    $('#watch-youtube').href = ytUrl;
    $('#watch-youtube').style.display = channel.youtube ? '' : 'none';
    renderSourceBar(channel);
  }

  function renderSourceBar(channel, active) {
    const bar = $('#source-bar');
    const sources = [];
    if (channel.youtube) sources.push({ kind: 'youtube', label: 'YouTube live' });
    (channel.hls || []).forEach((url, i) =>
      sources.push({ kind: 'hls', label: `Direct HLS${(channel.hls.length > 1 ? ' ' + (i + 1) : '')}`, url }),
    );
    if (channel.web) sources.push({ kind: 'web', label: 'Official site' });

    if (sources.length > 1) {
      bar.innerHTML = `<span class="label">Sources</span>`;
      sources.forEach((s) => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'source-chip';
        b.textContent = s.label;
        const isActive = active ? s.kind === active.kind && (s.url || '') === (active.url || '') : s.kind === 'youtube' || s.kind === (state.player?.kind || 'youtube');
        b.setAttribute('aria-pressed', String(isActive));
        b.addEventListener('click', () => {
          if (s.kind === 'web') {
            window.open(channel.web, '_blank', 'noopener');
            return;
          }
          if (s.kind === 'hls') mountPlayer(channel, { state: 'hls', url: s.url }, {});
          else {
            const entry = state.live.get(channel.id);
            mountPlayer(channel, entry?.videoId ? { ...entry } : channel.youtube?.seed ? { state: 'seed', videoId: channel.youtube.seed } : null, {});
          }
        });
        bar.appendChild(b);
      });
    } else {
      bar.innerHTML = '';
    }
  }

  function setPlayerStatus(text, { spinner = true, actions = [] } = {}) {
    const host = $('#player');
    let overlay = $('#player-empty');
    if (!overlay || overlay.__mount !== host.__mountId) {
      // player DOM was replaced; rebuild overlay
      host.insertAdjacentHTML(
        'afterbegin',
        `<div class="player-empty" id="player-empty">${spinner ? '<span class="spinner" aria-hidden="true"></span>' : ''}<p id="player-empty-text"></p></div>`,
      );
      overlay = $('#player-empty');
      overlay.__mount = host.__mountId;
    }
    overlay.hidden = false;
    $('#player-empty-text').textContent = text;
    const spin = $('.spinner', overlay);
    if (spin) spin.hidden = !spinner;
    overlay.querySelectorAll('a.btn, button.btn').forEach((b) => b.remove());
    for (const a of actions) {
      const b = document.createElement(a.href ? 'a' : 'button');
      b.className = 'btn primary';
      b.textContent = a.label;
      if (a.href) {
        b.href = a.href;
        b.target = '_blank';
        b.rel = 'noopener';
      } else {
        b.type = 'button';
        b.addEventListener('click', a.onClick);
      }
      overlay.appendChild(b);
    }
  }

  function hidePlayerStatus() {
    const overlay = $('#player-empty');
    if (overlay) overlay.hidden = true;
  }

  function destroyPlayer() {
    if (state.player?.cleanup) {
      try {
        state.player.cleanup();
      } catch {
        /* ignore */
      }
    }
    state.player = null;
    const player = $('#player');
    player.__mountId = (player.__mountId || 0) + 1;
    player.innerHTML = `<div class="player-empty" id="player-empty"><span class="spinner" aria-hidden="true"></span><p id="player-empty-text">Loading stream…</p></div>`;
    $('#watch-note').textContent = '';
  }

  function mountPlayer(channel, entry, { force = false } = {}) {
    destroyPlayer();
    const wantsHls = entry?.state === 'hls';
    renderSourceBar(channel, wantsHls ? { kind: 'hls', url: entry.url } : { kind: 'youtube' });

    if (wantsHls) {
      return playHls(channel, entry.url);
    }
    if (entry?.videoId) {
      return playYouTube(channel, entry.videoId, entry);
    }

    // Nothing cached: resolve, then fall back to HLS or an explicit prompt.
    setPlayerStatus('Looking up the current live stream…');
    const id = channel.id;
    state.resolving.add(id);
    fetch(`/api/live?ids=${encodeURIComponent(id)}${force ? '&force=1' : ''}`)
      .then((r) => r.json())
      .then((data) => {
        const result = data.results?.[id];
        if (result) state.live.set(id, { ...result, at: Date.now() });
        const goodState = result?.state === 'live' || result?.state === 'seed' || result?.state === 'stale';
        // A resolved live stream wins; otherwise fall back to the last-known
        // video only when the channel has no HLS source of its own.
        if (result?.videoId && (goodState || !(channel.hls || []).length)) {
          playYouTube(channel, result.videoId, result);
        } else if ((channel.hls || []).length) {
          playHls(channel, channel.hls[0]);
        } else {
          offerFallback(channel, result);
        }
      })
      .catch(() => {
        if ((channel.hls || []).length) playHls(channel, channel.hls[0]);
        else offerFallback(channel, null);
      })
      .finally(() => state.resolving.delete(id));
  }

  function offerFallback(channel, result) {
    const yt = channel.youtube?.channelId
      ? `https://www.youtube.com/channel/${channel.youtube.channelId}/live`
      : channel.youtube?.handle
        ? `https://www.youtube.com/${channel.youtube.handle}/live`
        : null;
    const why = result?.state === 'offline' ? 'This channel is not broadcasting on YouTube right now.'
      : result?.state === 'unreachable' ? 'The server could not reach YouTube to resolve the current stream.'
      : 'No playable source was resolved for this channel.';
    setPlayerStatus(`${why} You can still open it at the source:`, {
      spinner: false,
      actions: [
        yt && { label: 'Open on YouTube', href: yt },
        channel.web && { label: 'Open official site', href: channel.web },
        { label: 'Retry', onClick: () => mountPlayer(channel, null, { force: true }) },
      ].filter(Boolean),
    });
    $('#watch-note').textContent = 'Tip: most broadcasters also run a 24×7 live page on their own website.';
  }

  /* ---------- YouTube player ---------- */

  let ytWatchdog = null;
  function playYouTube(channel, videoId, entry) {
    const player = $('#player');
    const origin = encodeURIComponent(location.origin);
    const frameId = `yt-${videoId}-${Date.now()}`;
    const src =
      `https://www.youtube-nocookie.com/embed/${encodeURIComponent(videoId)}` +
      `?autoplay=1&mute=1&playsinline=1&rel=0&modestbranding=1&enablejsapi=1&origin=${origin}&widget_referrer=${origin}`;
    player.innerHTML = `<iframe id="${frameId}" src="${src}" title="${esc(channel.name)} live stream" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>`;
    player.__mountId = (player.__mountId || 0) + 1;

    const iframe = document.getElementById(frameId);
    state.player = {
      kind: 'yt',
      videoId,
      iframe,
      ready: false,
      unmuted: false,
      cleanup() {
        clearTimeout(ytWatchdog);
      },
    };

    setPlayerStatus('Starting live stream…');
    ytWatchdog = setTimeout(() => {
      if (!state.player || state.player.videoId !== videoId || state.player.ready) return;
      setPlayerStatus(
        'The stream is taking a while to start. Broadcasters occasionally rotate their live video — try again or use another source.',
        {
          spinner: false,
          actions: [
            { label: 'Reload stream', onClick: () => mountPlayer(channel, null, { force: true }) },
            ...(channel.hls || []).map((url, i) => ({ label: `Try direct HLS${i ? ' ' + (i + 1) : ''}`, onClick: () => playHls(channel, url) })),
            { label: 'Open on YouTube', href: `https://www.youtube.com/watch?v=${videoId}` },
          ],
        },
      );
    }, 13000);

    const lastKnown = entry?.state === 'seed' || entry?.fallback === 'last-known';
    const note = lastKnown
      ? 'Playing the last known live stream for this channel. Broadcasters rotate stream IDs, so hit reload (R) if this one has ended.'
      : entry?.title
        ? `Now playing: ${entry.title}`
        : channel.youtube?.verified
          ? 'Verified official broadcaster channel.'
          : 'Source: official YouTube live stream.';
    $('#watch-note').innerHTML = `${esc(note)} <button class="btn link" id="unmute-btn" hidden>🔊 Unmute</button>`;
    const unmute = $('#unmute-btn');
    unmute.hidden = false;
    unmute.addEventListener('click', () => sendYouTube(iframe, 'unMute') || sendYouTube(iframe, 'setVolume', [70]), { once: false });
    unmute.addEventListener('click', () => {
      unmute.hidden = true;
      if (state.player) state.player.unmuted = true;
    });
    setTimeout(() => sendYouTube(iframe, 'addEventListener', ['onReady', 'onStateChange', 'onError']), 900);
  }

  function sendYouTube(iframe, func, args = []) {
    if (!iframe?.contentWindow) return false;
    try {
      iframe.contentWindow.postMessage(JSON.stringify({ event: 'command', func, args }), '*');
      return true;
    } catch {
      return false;
    }
  }

  function onYouTubeMessage(event) {
    if (!state.player || state.player.kind !== 'yt') return;
    if (!/^https:\/\/(www\.)?youtube(-nocookie)?\.com$/.test(event.origin)) return;
    let data = event.data;
    if (typeof data === 'string') {
      try {
        data = JSON.parse(data);
      } catch {
        return;
      }
    }
    if (!data || typeof data !== 'object') return;

    if (data.event === 'onReady') {
      state.player.ready = true;
      hidePlayerStatus();
    } else if (data.event === 'onStateChange') {
      if (data.info === 1 || data.info === 3) {
        state.player.ready = true;
        hidePlayerStatus();
      }
    } else if (data.event === 'onError') {
      const code = data.info;
      const msg =
        code === 101 || code === 150
          ? 'The broadcaster has disabled playback of this stream outside YouTube.'
          : code === 100
            ? 'This live video has ended or was removed by the broadcaster.'
            : 'YouTube reported a playback error.';
      const channel = state.channels.find((c) => c.id === state.route.id);
      setPlayerStatus(msg, {
        spinner: false,
        actions: [
          { label: 'Reload stream', onClick: () => channel && mountPlayer(channel, null, { force: true }) },
          ...((channel?.hls || []).map((url, i) => ({ label: `Try direct HLS${i ? ' ' + (i + 1) : ''}`, onClick: () => channel && playHls(channel, url) }))),
          channel?.web && { label: 'Open official site', href: channel.web },
        ].filter(Boolean),
      });
    }
  }

  /* ---------- HLS player ---------- */

  function playHls(channel, url) {
    const player = $('#player');
    player.innerHTML = `<video id="hls-video" playsinline controls autoplay></video>`;
    player.__mountId = (player.__mountId || 0) + 1;
    const video = $('#hls-video');
    setPlayerStatus('Connecting to the broadcaster’s stream…');

    const hls = window.Hls;
    const nativeHls = !!video.canPlayType('application/vnd.apple.mpegurl');
    const useHlsJs = !!(hls && hls.isSupported());
    const proxied = `/api/hls?u=${encodeURIComponent(url)}`;
    // hls.js fetches the playlist with XHR, so a broadcaster feed without CORS
    // headers will fail — go through our own proxy first and only fall back to
    // the origin if this deployment has no proxy. Native-HLS engines (Safari,
    // iOS) are not subject to that restriction, so they try the origin first.
    const sources = nativeHls && !useHlsJs ? [url, proxied] : [proxied, url];
    let index = 0;

    const attach = () => {
      const src = sources[index];
      const isProxied = src.startsWith('/api/hls');
      const engine = useHlsJs && (isProxied || !nativeHls) ? 'hls' : nativeHls ? 'native' : 'hls';

      const fail = (reason) => {
        index += 1;
        if (index < sources.length) {
          setPlayerStatus(
            index === 1 ? 'Local proxy unavailable — trying the broadcaster directly…' : 'Retrying…',
          );
          return attach();
        }
        offerFallback(channel, { state: 'error', error: reason });
      };

      if (engine === 'hls' && useHlsJs && hls) {
        destroyHls();
        const instance = new hls({
          lowLatencyMode: true,
          backBufferLength: 30,
          maxBufferLength: 20,
          manifestLoadingTimeOut: 9000,
          manifestLoadingMaxRetry: 1,
          fragLoadingMaxRetry: 2,
        });
        state.hlsInstance = instance;
        instance.on(hls.Events.MANIFEST_PARSED, () => {
          hidePlayerStatus();
          const p = video.play();
          if (p && p.catch) p.catch(() => {});
        });
        instance.on(hls.Events.ERROR, (_evt, data) => {
          if (data.fatal) {
            try {
              instance.destroy();
            } catch {
              /* ignore */
            }
            fail(data.details);
          }
        });
        instance.loadSource(src);
        instance.attachMedia(video);
      } else {
        video.src = src;
        video.addEventListener('loadedmetadata', () => {
          hidePlayerStatus();
          const p = video.play();
          if (p && p.catch) p.catch(() => {});
        });
        video.addEventListener('error', () => fail('media error'), { once: true });
      }
    };

    attach();
    state.player = {
      kind: 'hls',
      url,
      cleanup() {
        destroyHls();
      },
    };
    $('#watch-note').innerHTML =
      'Playing the broadcaster’s public HLS stream directly. <span class="footnote">If it stalls, switch to the YouTube source.</span>';
    renderSourceBar(channel, { kind: 'hls', url });
  }

  function destroyHls() {
    if (state.hlsInstance) {
      try {
        state.hlsInstance.destroy();
      } catch {
        /* ignore */
      }
      state.hlsInstance = null;
    }
  }

  function toggleFullscreen() {
    const shell = $('.player-shell');
    if (!document.fullscreenElement) {
      (shell.requestFullscreen || shell.webkitRequestFullscreen || (() => {})).call(shell);
    } else {
      document.exitFullscreen();
    }
  }

  /* ---------- side list / zapping ---------- */

  function renderSideList(current) {
    const host = $('#side-list');
    const list = state.channels
      .filter((c) => c.id !== current.id && (c.language === current.language || c.category === current.category))
      .sort((a, b) => liveRank(b) - liveRank(a) || a.name.localeCompare(b.name))
      .slice(0, 10);
    host.innerHTML = '';
    for (const c of list) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'side-item';
      b.dataset.id = c.id;
      b.style.setProperty('--brand', c.color || '#334155');
      const live = state.live.get(c.id)?.state === 'live';
      b.innerHTML = `
        <span class="side-badge">${esc(initials(c.name))}</span>
        <span class="side-text">
          <span class="side-name">${esc(c.name)}</span>
          <span class="side-meta">${esc(c.language)} · ${esc(c.region)}</span>
        </span>
        ${live ? '<span class="side-live">LIVE</span>' : ''}`;
      b.addEventListener('click', () => openWatch(c.id));
      host.appendChild(b);
    }
    queueResolve(list.map((c) => c.id));
  }

  function zap(direction) {
    const current = state.route.id;
    const order = visibleChannels();
    let idx = order.findIndex((c) => c.id === current);
    if (idx === -1) idx = 0;
    const next = order[(idx + direction + order.length) % order.length];
    if (next && next.id !== current) openWatch(next.id);
  }

  /* ---------- favourites ---------- */

  function toggleFav(id) {
    if (!id) return;
    if (state.favs.has(id)) state.favs.delete(id);
    else state.favs.add(id);
    writeLS(LS.favs, [...state.favs]);
    $('#watch-fav').setAttribute('aria-pressed', String(state.favs.has(id)));
    renderGrid();
    if (state.route.name === 'watch') renderSideList(state.channels.find((c) => c.id === id));
    toast(state.favs.has(id) ? 'Added to favourites' : 'Removed from favourites');
  }

  /* ---------- misc ---------- */

  let toastTimer = null;
  function toast(message) {
    const el = $('#toast');
    el.textContent = message;
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      el.hidden = true;
    }, 2600);
  }

  function debounce(fn, ms) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), ms);
    };
  }

  boot();
})();
