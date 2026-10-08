#!/usr/bin/env node
/**
 * Channel catalogue maintainer.
 *
 *   npm run verify                 # check every channel with a YouTube source
 *   npm run verify -- --only=news  # check a category
 *   npm run verify -- --json       # machine-readable output
 *
 * For each channel it asks YouTube two cheap questions:
 *   1. does the configured channel id / handle resolve to a real channel?
 *      (via the RSS feed, which echoes the channel title)
 *   2. is there a live stream on it right now?
 *      (via <channel>/live, the same trick server.js uses at runtime)
 *
 * It never writes to the catalogue: it prints what it found so a human can
 * decide whether an ID should be added, corrected or retired.
 */

import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const CATALOG = path.join(ROOT, 'data', 'channels.json');

const args = process.argv.slice(2);
const only = args.find((a) => a.startsWith('--only='))?.split('=')[1];
const asJson = args.includes('--json');
const concurrency = Number(args.find((a) => a.startsWith('--jobs='))?.split('=')[1] || 4);

const UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36';

const COLOR = process.stdout.isTTY && !asJson;
const c = (code, s) => (COLOR ? `\x1b[${code}m${s}\x1b[0m` : s);
const ok = (s) => c(32, s);
const bad = (s) => c(31, s);
const warn = (s) => c(33, s);
const dim = (s) => c(90, s);

async function get(url, { timeout = 12000, accept = 'text/html' } = {}) {
  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(), timeout);
  try {
    const res = await fetch(url, {
      redirect: 'follow',
      headers: { 'user-agent': UA, accept, 'accept-language': 'en-IN,en;q=0.9' },
      signal: ac.signal,
    });
    if (!res.ok) return { status: res.status, body: '' };
    const body = (await res.text()).slice(0, 400_000);
    return { status: res.status, body, url: res.url };
  } catch (err) {
    return { status: 0, body: '', error: String(err.message || err) };
  } finally {
    clearTimeout(t);
  }
}

async function checkChannel(channel) {
  const yt = channel.youtube || {};
  const report = { id: channel.id, name: channel.name, channelId: yt.channelId || null, handle: yt.handle || null, catalogVerified: !!yt.verified };

  if (!yt.channelId && !yt.handle) {
    report.skip = 'no YouTube source';
    return report;
  }

  // 1. Channel identity via the RSS feed (first line contains the channel title).
  if (yt.channelId) {
    const feed = await get(`https://www.youtube.com/feeds/videos.xml?channel_id=${yt.channelId}`, {
      accept: 'application/xml',
    });
    const title = feed.body?.match(/<title>([^<]+)<\/title>/)?.[1] || null;
    report.rssTitle = title;
    report.rssOk = Boolean(title);
    // A network failure must not be mistaken for a wrong channel ID.
    if (!title && feed.status === 0) report.rssError = feed.error || 'network error';
  }

  // 2. Is it live right now?
  const liveUrl = yt.channelId
    ? `https://www.youtube.com/channel/${yt.channelId}/live`
    : `https://www.youtube.com/@${String(yt.handle).replace(/^@/, '')}/live`;
  const live = await get(liveUrl);
  if (live.status === 0) {
    report.live = 'unreachable';
    report.error = live.error;
  } else {
    const videoId =
      live.body.match(/<link rel="canonical" href="https:\/\/www\.youtube\.com\/watch\?v=([A-Za-z0-9_-]{11})"/)?.[1] ||
      live.body.match(/"videoId":"([A-Za-z0-9_-]{11})"/)?.[1] ||
      null;
    const isLive = /"isLiveNow":true|"isLive":true|"isLiveContent":true/.test(live.body);
    report.live = isLive ? 'live' : 'not-live';
    report.liveVideoId = isLive ? videoId : null;
    report.seedMatches = isLive && yt.seed ? yt.seed === videoId : null;
  }
  return report;
}

async function pool(items, worker, size) {
  const out = [];
  const queue = items.map((item, i) => [item, i]);
  await Promise.all(
    new Array(Math.min(size, queue.length)).fill(0).map(async () => {
      while (queue.length) {
        const [item, i] = queue.shift();
        out[i] = await worker(item);
      }
    }),
  );
  return out;
}

const catalog = JSON.parse(await readFile(CATALOG, 'utf8'));
let channels = catalog.channels;
if (only) channels = channels.filter((ch) => ch.category === only || ch.language === only);
if (!channels.length) {
  console.error(`No channels matched "${only}".`);
  process.exit(1);
}

if (!asJson) {
  console.log(`\n${c('1', 'DesiTV catalogue check')} — ${channels.length} channels\n`);
}

const reports = await pool(channels, checkChannel, concurrency);

if (asJson) {
  console.log(JSON.stringify({ checkedAt: new Date().toISOString(), reports }, null, 2));
} else {
  for (const r of reports) {
    if (r.skip) {
      console.log(`${dim('–')} ${r.name.padEnd(28)} ${dim(r.skip)}`);
      continue;
    }
    const idState = r.channelId
      ? r.rssOk
        ? ok('id ok') + dim(`  (${r.rssTitle?.slice(0, 42) || ''})`)
        : r.rssError
          ? warn('id unverified (no network)')
          : bad('id BAD')
      : warn('handle only');
    const liveState =
      r.live === 'live' ? ok('LIVE') : r.live === 'not-live' ? dim('off air') : bad(String(r.live));
    const seedNote =
      r.live === 'live' && r.seedMatches === false ? warn('  seed stale → update') : '';
    console.log(
      `${liveState.padEnd(COLOR ? 18 : 10)} ${String(r.name).padEnd(28)} ${idState}${seedNote}`,
    );
  }

  const live = reports.filter((r) => r.live === 'live').length;
  const idBad = reports.filter((r) => r.channelId && r.rssOk === false && !r.rssError).length;
  const staleSeeds = reports.filter((r) => r.seedMatches === false).length;
  const netDown = reports.filter((r) => r.rssError || r.live === 'unreachable').length;
  console.log(
    `\n${live}/${reports.length} live now · ${idBad} broken channel ids · ${staleSeeds} stale seeds\n` +
      dim('Update data/channels.json for anything flagged, then re-run.'),
  );
  if (netDown > reports.length / 2) {
    console.log(
      warn(
        `\nNote: ${netDown}/${reports.length} channels could not be reached at all — this machine` +
          ' appears to have no route to youtube.com, so the results above say nothing about the\n' +
          'catalogue. Re-run somewhere with internet access for a meaningful check.',
      ),
    );
  }
}
