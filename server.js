#!/usr/bin/env node
/**
 * DesiTV — free, official live Indian TV in the browser.
 *
 * A single-file, dependency-free Node server that:
 *   1. serves the static web app (public/),
 *   2. exposes the channel catalogue (data/channels.json),
 *   3. resolves the *current* YouTube live video for a channel (server-side,
 *      because YouTube killed the `embed/live_stream?channel=` endpoint),
 *   4. proxies HLS playlists/segments for broadcasters whose CDNs do not send
 *      permissive CORS headers.
 *
 * Nothing here hosts or restreams video: playback always happens in the
 * viewer's browser, straight from the broadcaster's own YouTube channel or
 * their own public CDN.
 */

'use strict';

const http = require('node:http');
const https = require('node:https');
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const path = require('node:path');
const zlib = require('node:zlib');
const { URL } = require('node:url');

const ROOT = __dirname;
const PUBLIC_DIR = path.join(ROOT, 'public');
const DATA_FILE = path.join(ROOT, 'data', 'channels.json');
const CACHE_DIR = path.join(ROOT, '.cache');
const CACHE_FILE = path.join(CACHE_DIR, 'live-resolutions.json');

const PORT = Number(process.env.PORT || 3000);
const HOST = process.env.HOST || '0.0.0.0';

const UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
  '(KHTML, like Gecko) Chrome/125.0 Safari/537.36';

// How long a successful resolution stays warm.
const TTL_LIVE = 5 * 60 * 1000;
const TTL_MISS = 2 * 60 * 1000;
const TTL_ERROR = 45 * 1000;

const RESOLVE_TIMEOUT = 9000;
const PROXY_TIMEOUT = 15000;
const MAX_HTML_BYTES = 3 * 1024 * 1024;
const MAX_PROXY_BYTES = 24 * 1024 * 1024;

/* ------------------------------------------------------------------ *
 * Catalogue
 * ------------------------------------------------------------------ */

let CATALOG = { channels: [] };
let CHANNELS_BY_ID = new Map();

function loadCatalog() {
  const raw = fs.readFileSync(DATA_FILE, 'utf8');
  CATALOG = JSON.parse(raw);
  CATALOG.channels = CATALOG.channels || [];
  CHANNELS_BY_ID = new Map(CATALOG.channels.map((c) => [c.id, c]));
  return CATALOG;
}

/** Hosts we are willing to proxy. Derived from the catalogue itself. */
function buildProxyAllowlist() {
  const hosts = new Set();
  const cdnSuffixes = [
    'akamaized.net',
    'cloudfront.net',
    'amagi.tv',
    'vidgyor.com',
    'jio.com',
    'intoday.in',
    'abplive.in',
    'zeenews.india.com',
    '5centscdn.com',
    'cloudfront.net',
  ];
  for (const ch of CATALOG.channels || []) {
    for (const url of ch.hls || []) {
      try {
        hosts.add(new URL(url).hostname);
      } catch {
        /* ignore malformed */
      }
    }
    if (ch.web) {
      try {
        const h = new URL(ch.web).hostname;
        hosts.add(h);
        const parts = h.split('.');
        if (parts.length > 2) hosts.add(parts.slice(-2).join('.'));
      } catch {
        /* ignore */
      }
    }
  }
  return { hosts, cdnSuffixes };
}

let ALLOWLIST = { hosts: new Set(), cdnSuffixes: [] };

function hostAllowed(hostname) {
  const h = hostname.toLowerCase();
  if (ALLOWLIST.hosts.has(h)) return true;
  if (ALLOWLIST.cdnSuffixes.some((s) => h === s || h.endsWith('.' + s))) return true;
  return false;
}

function isPrivateAddress(hostname) {
  if (/^(localhost|\[?::1\]?)$/i.test(hostname)) return true;
  const m = hostname.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (!m) return false;
  const [a, b] = [Number(m[1]), Number(m[2])];
  if (a === 10 || a === 127 || a === 0) return true;
  if (a === 192 && b === 168) return true;
  if (a === 172 && b >= 16 && b <= 31) return true;
  if (a === 169 && b === 254) return true;
  return false;
}

/* ------------------------------------------------------------------ *
 * Live resolution (YouTube)
 * ------------------------------------------------------------------ */

/** @type {Map<string, {state:string, videoId?:string, title?:string, thumb?:string, channelTitle?:string, error?:string, resolvedAt:number, ttl:number}>} */
const liveCache = new Map();
let outboundOk = null; // tri-state: unknown / true / false
let outboundCheckedAt = 0;

function cacheGet(id) {
  const hit = liveCache.get(id);
  if (!hit) return null;
  if (Date.now() - hit.resolvedAt > hit.ttl) return null;
  return hit;
}

function cacheSet(id, value) {
  liveCache.set(id, value);
  scheduleCacheFlush();
}

let flushTimer = null;
let dirty = false;
function scheduleCacheFlush() {
  dirty = true;
  if (flushTimer) return;
  flushTimer = setTimeout(() => {
    flushTimer = null;
    if (!dirty) return;
    dirty = false;
    const obj = {};
    for (const [k, v] of liveCache) {
      if (v.state === 'live') obj[k] = v; // only persist successful resolutions
    }
    fsp
      .mkdir(CACHE_DIR, { recursive: true })
      .then(() => fsp.writeFile(CACHE_FILE, JSON.stringify(obj, null, 2)))
      .catch(() => {});
  }, 4000);
  if (flushTimer.unref) flushTimer.unref();
}

async function restoreCache() {
  try {
    const txt = await fsp.readFile(CACHE_FILE, 'utf8');
    const obj = JSON.parse(txt);
    const now = Date.now();
    for (const [id, v] of Object.entries(obj)) {
      if (!v || !v.videoId) continue;
      liveCache.set(id, {
        ...v,
        // restored entries are treated as "stale but usable": the client shows
        // them immediately and asks for a refresh in the background.
        state: 'stale',
        resolvedAt: v.resolvedAt || now,
        ttl: Number.MAX_SAFE_INTEGER,
      });
    }
  } catch {
    /* first run */
  }
}

function httpGet(url, { timeout = RESOLVE_TIMEOUT, maxBytes = MAX_HTML_BYTES, redirects = 5 } = {}) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const done = (fn, arg) => {
      if (settled) return;
      settled = true;
      fn(arg);
    };
    const go = (target, left) => {
      let u;
      try {
        u = new URL(target);
      } catch (err) {
        return done(reject, err);
      }
      const mod = u.protocol === 'http:' ? http : https;
      const req = mod.request(
        u,
        {
          method: 'GET',
          headers: {
            'user-agent': UA,
            accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'accept-language': 'en-IN,en;q=0.9,hi;q=0.8',
            'cache-control': 'no-cache',
          },
          timeout,
        },
        (res) => {
          if ([301, 302, 303, 307, 308].includes(res.statusCode) && res.headers.location && left > 0) {
            res.resume();
            const next = new URL(res.headers.location, u).toString();
            return go(next, left - 1);
          }
          const chunks = [];
          let size = 0;
          res.on('data', (chunk) => {
            size += chunk.length;
            if (size > maxBytes) {
              req.destroy();
              return done(resolve, { status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks).toString('utf8') });
            }
            chunks.push(chunk);
          });
          res.on('end', () =>
            done(resolve, { status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks).toString('utf8') }),
          );
        },
      );
      req.on('timeout', () => {
        req.destroy(new Error('timeout'));
      });
      req.on('error', (err) => done(reject, err));
      req.end();
    };
    go(url, redirects);
  });
}

function extractLiveVideoId(html) {
  // 1. Most reliable: the canonical URL YouTube renders for /channel/<id>/live
  const canonical = html.match(
    /<link rel="canonical" href="https:\/\/www\.youtube\.com\/watch\?v=([A-Za-z0-9_-]{11})"/,
  );
  const candidates = [];
  if (canonical) candidates.push(canonical[1]);
  const re = /"videoId":"([A-Za-z0-9_-]{11})"/g;
  let m;
  while ((m = re.exec(html)) !== null && candidates.length < 25) {
    if (!candidates.includes(m[1])) candidates.push(m[1]);
  }
  // A live stream page carries one of these markers around the live video.
  const liveish =
    /"isLiveNow":true|"isLive":true|"isLiveContent":true|"isLiveBroadcast":true|Watch live stream|"LIVE"/i.test(
      html,
    );
  const isOfflinePage = /This live stream recording is not available|"status":"LIVE_STREAM_OFFLINE"|Video unavailable/i.test(
    html,
  );
  if (isOfflinePage && !liveish) return { videoId: candidates[0] || null, live: false };
  if (liveish && candidates.length) return { videoId: candidates[0], live: true };
  if (candidates.length && html.includes('"style":"LIVE"')) return { videoId: candidates[0], live: true };
  return { videoId: candidates[0] || null, live: false };
}

async function fetchOEmbed(videoId) {
  try {
    const url = `https://www.youtube.com/oembed?url=${encodeURIComponent(
      `https://www.youtube.com/watch?v=${videoId}`,
    )}&format=json`;
    const res = await httpGet(url, { timeout: 6000, maxBytes: 64 * 1024 });
    if (res.status !== 200) return null;
    const json = JSON.parse(res.body);
    return {
      title: json.title,
      channelTitle: json.author_name,
      thumb: json.thumbnail_url,
    };
  } catch {
    return null;
  }
}

async function resolveChannel(channel, { force = false } = {}) {
  const id = channel.id;
  if (!force) {
    const hit = cacheGet(id);
    if (hit) return hit;
  }

  const yt = channel.youtube || {};
  const target = yt.channelId
    ? `https://www.youtube.com/channel/${yt.channelId}/live`
    : yt.handle
      ? `https://www.youtube.com/@${String(yt.handle).replace(/^@/, '')}/live`
      : null;

  if (!target) {
    const seed = yt.seed;
    if (seed) {
      const entry = {
        state: 'seed',
        videoId: seed,
        resolvedAt: Date.now(),
        ttl: TTL_LIVE,
        note: 'No channel URL configured — using last known live video.',
      };
      cacheSet(id, entry);
      return entry;
    }
    const entry = { state: 'unavailable', error: 'no source', resolvedAt: Date.now(), ttl: TTL_ERROR };
    cacheSet(id, entry);
    return entry;
  }

  try {
    const res = await httpGet(target);
    outboundOk = true;
    outboundCheckedAt = Date.now();
    if (res.status !== 200) throw new Error('http ' + res.status);
    const { videoId, live } = extractLiveVideoId(res.body);
    if (videoId && live) {
      const meta = await fetchOEmbed(videoId);
      const entry = {
        state: 'live',
        videoId,
        title: meta?.title || null,
        channelTitle: meta?.channelTitle || channel.name,
        thumb: meta?.thumb || `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`,
        resolvedAt: Date.now(),
        ttl: TTL_LIVE,
        source: yt.channelId ? 'channel' : 'handle',
      };
      cacheSet(id, entry);
      return entry;
    }
    const entry = {
      state: 'offline',
      videoId: videoId || null,
      resolvedAt: Date.now(),
      ttl: TTL_MISS,
      note: 'Channel has no public live stream right now.',
    };
    cacheSet(id, entry);
    return entry;
  } catch (err) {
    outboundOk = false;
    outboundCheckedAt = Date.now();
    // Fall back to the last known good (or seeded) video so the UI still
    // has something to play while the network is unavailable.
    const staleEntry = liveCache.get(id);
    const callable = yt.seed || staleEntry?.videoId || null;
    const entry = {
      state: 'unreachable',
      videoId: callable,
      title: staleEntry?.title || null,
      thumb: staleEntry?.thumb || (callable ? `https://i.ytimg.com/vi/${callable}/hqdefault.jpg` : null),
      fallback: yt.seed ? 'last-known' : undefined,
      resolvedAt: Date.now(),
      ttl: TTL_ERROR,
      error: String(err.message || err),
    };
    cacheSet(id, entry);
    return entry;
  }
}

async function resolveMany(ids, { force = false, concurrency = 4 } = {}) {
  const out = {};
  const queue = [...ids];
  const workers = new Array(Math.min(concurrency, queue.length)).fill(0).map(async () => {
    while (queue.length) {
      const id = queue.shift();
      const channel = CHANNELS_BY_ID.get(id);
      if (!channel) {
        out[id] = { state: 'unknown', error: 'unknown channel' };
        continue;
      }
      try {
        out[id] = await resolveChannel(channel, { force });
      } catch (err) {
        out[id] = { state: 'error', error: String(err.message || err) };
      }
    }
  });
  await Promise.all(workers);
  return out;
}

/* ------------------------------------------------------------------ *
 * Static file serving
 * ------------------------------------------------------------------ */

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
  '.webmanifest': 'application/manifest+json',
  '.txt': 'text/plain; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
};

const COMPRESSIBLE = /^(text\/|application\/(json|manifest\+json|javascript)|image\/svg)/;

function send(res, status, body, headers = {}) {
  const buf = Buffer.isBuffer(body) ? body : Buffer.from(String(body));
  const type = headers['content-type'] || 'text/plain; charset=utf-8';
  const wantsGzip = COMPRESSIBLE.test(type) && buf.length > 1024;
  if (wantsGzip) {
    zlib.gzip(buf, (err, gz) => {
      if (err) {
        res.writeHead(status, { 'content-type': type, 'content-length': buf.length, ...headers });
        return res.end(buf);
      }
      res.writeHead(status, {
        'content-type': type,
        'content-encoding': 'gzip',
        'content-length': gz.length,
        vary: 'accept-encoding',
        ...headers,
      });
      res.end(gz);
    });
    return;
  }
  res.writeHead(status, { 'content-type': type, 'content-length': buf.length, ...headers });
  res.end(buf);
}

function sendJson(res, status, obj, headers = {}) {
  send(res, status, JSON.stringify(obj), {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
    ...headers,
  });
}

async function serveStatic(req, res, pathname) {
  let rel = decodeURIComponent(pathname);
  if (rel.endsWith('/')) rel += 'index.html';
  const filePath = path.join(PUBLIC_DIR, path.normalize(rel));
  if (!filePath.startsWith(PUBLIC_DIR)) {
    return send(res, 403, 'Forbidden');
  }
  let stat;
  try {
    stat = await fsp.stat(filePath);
  } catch {
    // SPA fallback: /watch/<id> and friends are rendered client-side.
    if (!path.extname(rel)) return serveStatic(req, res, '/index.html');
    return send(res, 404, 'Not found');
  }
  if (stat.isDirectory()) return serveStatic(req, res, path.join(rel, '/'));
  const ext = path.extname(filePath).toLowerCase();
  const type = MIME[ext] || 'application/octet-stream';
  const etag = `W/"${stat.size}-${Number(stat.mtimeMs).toString(36)}"`;
  const cacheControl = /vendor\//.test(rel) ? 'public, max-age=604800, immutable' : 'public, max-age=60';
  if (req.headers['if-none-match'] === etag) {
    res.writeHead(304, { etag, 'cache-control': cacheControl });
    return res.end();
  }
  const body = await fsp.readFile(filePath);
  send(res, 200, body, { 'content-type': type, etag, 'cache-control': cacheControl });
}

/* ------------------------------------------------------------------ *
 * HLS proxy
 * ------------------------------------------------------------------ */

function rewritePlaylist(body, playlistUrl, proxyBase) {
  const base = new URL(playlistUrl);
  const absolutize = (uri) => {
    try {
      return new URL(uri, base).toString();
    } catch {
      return null;
    }
  };
  const proxied = (uri) => {
    const abs = absolutize(uri);
    if (!abs) return uri;
    return `${proxyBase}${encodeURIComponent(abs)}`;
  };

  return body
    .split('\n')
    .map((line) => {
      const trimmed = line.trim();
      if (!trimmed) return line;
      if (trimmed.startsWith('#')) {
        // URI="..." attributes (keys, media renditions, maps)
        return line.replace(/URI="([^"]+)"/g, (_, uri) => `URI="${proxied(uri)}"`);
      }
      // segment / variant / key URI line
      return line.replace(/^(\s*)(\S+)(\s*)$/, (_, pre, uri, post) => `${pre}${proxied(uri)}${post}`);
    })
    .join('\n');
}

function proxyRequest(target, res, { rewrite }) {
  let u;
  try {
    u = new URL(target);
  } catch {
    return sendJson(res, 400, { error: 'bad url' });
  }
  if (!/^https?:$/.test(u.protocol)) return sendJson(res, 400, { error: 'unsupported protocol' });
  if (isPrivateAddress(u.hostname) || !hostAllowed(u.hostname)) {
    return sendJson(res, 403, { error: 'host not allowed', host: u.hostname });
  }

  const mod = u.protocol === 'http:' ? http : https;
  const req = mod.request(
    u,
    {
      method: 'GET',
      headers: {
        'user-agent': UA,
        accept: '*/*',
        'accept-language': 'en-IN,en;q=0.9',
        ...(u.hostname.endsWith('akamaized.net') ? {} : { referer: `${u.protocol}//${u.hostname}/` }),
      },
      timeout: PROXY_TIMEOUT,
    },
    (upstream) => {
      if ([301, 302, 303, 307, 308].includes(upstream.statusCode) && upstream.headers.location) {
        upstream.resume();
        const next = new URL(upstream.headers.location, u).toString();
        return proxyRequest(next, res, { rewrite });
      }
      if (upstream.statusCode >= 400) {
        upstream.resume();
        return sendJson(res, upstream.statusCode === 404 ? 404 : 502, { error: 'upstream ' + upstream.statusCode });
      }
      const type = upstream.headers['content-type'] || '';
      const isPlaylist =
        rewrite ||
        /mpegurl/i.test(type) ||
        u.pathname.endsWith('.m3u8') ||
        /\.m3u8(\?|$)/.test(u.pathname);
      const headers = {
        'access-control-allow-origin': '*',
        'cache-control': isPlaylist ? 'no-store' : 'public, max-age=30',
      };

      if (!isPlaylist) {
        res.writeHead(200, { ...headers, 'content-type': type || 'application/octet-stream' });
        let bytes = 0;
        upstream.on('data', (chunk) => {
          bytes += chunk.length;
          if (bytes > MAX_PROXY_BYTES) return upstream.destroy();
        });
        upstream.pipe(res);
        return;
      }

      const chunks = [];
      let size = 0;
      upstream.on('data', (c) => {
        size += c.length;
        if (size < 8 * 1024 * 1024) chunks.push(c);
      });
      upstream.on('end', () => {
        const body = Buffer.concat(chunks).toString('utf8');
        if (/^#EXTM3U/.test(body.trim())) {
          const rewritten = rewritePlaylist(body, target, '/api/hls?u=');
          send(res, 200, rewritten, {
            'content-type': 'application/vnd.apple.mpegurl',
            ...headers,
          });
        } else {
          send(res, 200, body, { 'content-type': type || 'application/octet-stream', ...headers });
        }
      });
    },
  );
  req.on('timeout', () => req.destroy(new Error('upstream timeout')));
  req.on('error', (err) => {
    if (!res.headersSent) sendJson(res, 504, { error: 'upstream error', detail: String(err.message || err) });
    else res.end();
  });
  req.end();
}

/* ------------------------------------------------------------------ *
 * Router
 * ------------------------------------------------------------------ */

async function handleApi(req, res, url) {
  const { pathname, searchParams } = url;

  if (pathname === '/api/health') {
    return sendJson(res, 200, {
      ok: true,
      channels: CATALOG.channels.length,
      outbound: outboundOk,
      outboundCheckedAt,
      resolvedLive: [...liveCache.values()].filter((v) => v.state === 'live').length,
      uptime: Math.round(process.uptime()),
      node: process.version,
    });
  }

  if (pathname === '/api/channels') {
    return sendJson(res, 200, {
      ...CATALOG,
      resolver: {
        outbound: outboundOk,
        checkedAt: outboundCheckedAt,
        // The sandbox this app is often previewed in has no outbound network.
        caveat:
          outboundOk === false
            ? 'Live resolver could not reach YouTube from this server. Playback in your browser still works; last-known streams are used.'
            : null,
      },
    });
  }

  if (pathname === '/api/live') {
    const idsParam = searchParams.get('ids') || searchParams.get('id') || '';
    const ids = idsParam
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
      .slice(0, 24);
    if (!ids.length) return sendJson(res, 400, { error: 'no channel ids' });
    const force = searchParams.get('force') === '1';
    const results = await resolveMany(ids, { force });
    return sendJson(res, 200, { results, outbound: outboundOk, at: Date.now() });
  }

  if (pathname === '/api/hls') {
    const target = searchParams.get('u');
    if (!target) return sendJson(res, 400, { error: 'missing u' });
    if (req.method !== 'GET' && req.method !== 'HEAD') return sendJson(res, 405, { error: 'method' });
    return proxyRequest(target, res, { rewrite: true });
  }

  return sendJson(res, 404, { error: 'not found' });
}

const server = http.createServer((req, res) => {
  const started = Date.now();
  let url;
  try {
    url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  } catch {
    return sendJson(res, 400, { error: 'bad request' });
  }

  res.on('finish', () => {
    if (process.env.QUIET) return;
    const ms = Date.now() - started;
    if (url.pathname.startsWith('/api/hls')) return; // too noisy
    console.log(`${req.method} ${url.pathname}${url.search ? '?' + url.search : ''} → ${res.statusCode} (${ms}ms)`);
  });

  if (url.pathname.startsWith('/api/')) {
    handleApi(req, res, url).catch((err) => {
      console.error('api error', err);
      if (!res.headersSent) sendJson(res, 500, { error: 'internal', detail: String(err.message || err) });
    });
    return;
  }

  serveStatic(req, res, url.pathname).catch((err) => {
    console.error('static error', err);
    if (!res.headersSent) send(res, 500, 'Internal error');
  });
});

/* ------------------------------------------------------------------ *
 * Boot
 * ------------------------------------------------------------------ */

async function main() {
  loadCatalog();
  ALLOWLIST = buildProxyAllowlist();
  await restoreCache();

  server.listen(PORT, HOST, () => {
    const warn = '\x1b[33m%s\x1b[0m';
    console.log(`\n  \x1b[32mDesiTV\x1b[0m — free live Indian TV`);
    console.log(`  serving ${CATALOG.channels.length} channels on \x1b[36mhttp://${HOST}:${PORT}\x1b[0m`);
    console.log(`  proxy allowlist: ${ALLOWLIST.hosts.size} hosts\n`);
    // Warm the resolver so the first page load already knows what is live.
    const ids = CATALOG.channels.filter((c) => c.youtube).map((c) => c.id).slice(0, 12);
    resolveMany(ids, { concurrency: 3 })
      .then((r) => {
        const live = Object.values(r).filter((v) => v.state === 'live').length;
        console.log(`  resolver warm-up: ${live}/${ids.length} live`);
        if (live === 0) {
          console.log(warn, '  (resolver could not reach YouTube — browser playback + last-known streams still work)');
        }
      })
      .catch(() => {});
  });
}

process.on('unhandledRejection', (err) => console.error('unhandled rejection', err));

if (require.main === module) main();

module.exports = { server, resolveChannel, extractLiveVideoId };
