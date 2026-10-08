# DesiTV — free live Indian TV

A small, dependency-light website for watching **free, legal, live Indian television**: national and
regional news, Doordarshan, business, sports and live darshan. Browse or search the catalogue, filter
by category / language / region, then watch in place — HLS streams play directly, YouTube-based
channels play through the official YouTube player.

```
npm start          # http://localhost:3000
```

That's it — Node 18+ and nothing else. (No build step, no framework, no database.)

## What's in the box

| Path | What it does |
| --- | --- |
| `server.js` | Static file server + JSON API + HLS proxy. No dependencies. |
| `data/channels.json` | The curated catalogue: 82 channels across 13 languages and 17 regions. |
| `public/index.html`, `public/styles.css` | UI shell and styling (light/dark, responsive). |
| `public/app.js` | The whole client: filtering, search, favourites, recents, routing, player. |
| `public/vendor/hls.min.js` | Vendored [hls.js](https://github.com/video-dev/hls.js) 1.7.3 (Apache-2.0 — see `hls.js.LICENSE`). |
| `tools/verify-channels.mjs` | `npm run verify` — checks every channel's source is still alive. |

## How playback works

Each channel carries up to three sources, and the player tries them in order of reliability:

1. **Direct HLS** — the broadcaster's own published `.m3u8` feed, played by hls.js. Streams are
   pulled through `GET /api/hls?u=<encoded>`, a small proxy that rewrites playlist URIs so
   CORS- and relative-path-hostile feeds still play in the browser. The proxy is restricted to an
   allowlist of broadcaster/CDN hosts.
2. **YouTube live** — the official live stream of the broadcaster's verified channel, embedded via
   `https://www.youtube-nocookie.com/embed/<videoId>`. Because broadcasters rotate stream IDs every
   few hours, the server resolves the *current* live video ID on demand through `GET /api/live`
   (5-minute cache; `state` is one of `live`, `offline`, `unreachable`, `seed`, `stale`).
3. **Last-known stream** — the catalogue stores the video ID that was live when it was last built
   (`youtube.seed`), so a channel always has something to play even when the resolver is unreachable
   or the broadcaster is briefly off air.

The status pill next to the logo tells you which mode the server is in. If it reads *resolver
offline*, this server has no outbound network (common in a sandbox, or behind a firewall) — the
site still works, it just plays last-known streams and labels them *recent* instead of *live*.

## API

| Endpoint | Response |
| --- | --- |
| `GET /api/channels` | `{ version, updated, about, sources, channels[], resolver }` |
| `GET /api/live?ids=a,b,c&force=1` | `{ results: { id: { state, videoId, title, thumb, ttl, error } }, outbound, at }` |
| `GET /api/hls?u=<encoded>` | Rewritten HLS playlist / segment (allowlisted hosts only) |
| `GET /api/health` | `{ ok, channels, outbound, resolvedLive, uptime, node }` |

## Keyboard shortcuts

`/` search · `Esc` close player · `←` / `→` previous / next channel · `r` reload stream ·
`f` favourite (or fullscreen while watching) · `t` toggle theme.

## Verifying the catalogue

```bash
npm run verify                       # every channel
npm run verify -- --only=news        # one category…
npm run verify -- --only=Bengali     # …or one language
npm run verify -- --json --jobs=8    # machine-readable, 8 at a time
```

For each channel the tool fetches the official RSS feed to confirm the YouTube channel ID is real,
then probes the channel's `/live` page to see if a stream is actually broadcasting, and reports when
the catalogue's `seed` has gone stale. It is read-only — it never edits `data/channels.json`.

## Sources and legality

DesiTV only lists streams the broadcaster itself publishes: official YouTube live streams and
publicly documented HLS feeds. It does **not** proxy, decrypt, or re-host pay-TV or unauthorised
restreams, and every channel links back to its official website or YouTube page. Streams are
ad-supported, may be geo-restricted, and can go offline or move at any time — that's a property of
free broadcasting, not a bug. Copyright in each stream remains with its broadcaster.

Catalogue data was assembled and cross-checked against broadcaster websites, official YouTube
channels, and [iptv-org](https://github.com/iptv-org/iptv); provenance notes live in the `about` and
`sources` fields of `data/channels.json`.

## Adding a channel

Append an entry to `channels` in `data/channels.json` and reload — the server reads the file on
startup, so there is no build step:

```json
{
  "id": "my-channel",
  "name": "My Channel",
  "native": "माय चैनल",
  "category": "news",
  "language": "Hindi",
  "region": "National",
  "color": "#c2410c",
  "tags": ["news"],
  "youtube": { "channelId": "UCxxxxxxxxxxxxxxxxxxxxxx", "verified": true, "seed": "videoIdHere" },
  "hls": ["https://example.com/live/master.m3u8"],
  "web": "https://example.com/live"
}
```

`category` is one of `news`, `business`, `public`, `sports`, `devotional` (the UI also has labels
ready for `entertainment`, `music` and `kids`). `language` and `region` are free-form strings and
become filter chips automatically.

## Licence

Application code: MIT. hls.js: Apache-2.0 (see `public/vendor/`). Channel streams, names and logos
belong to their respective broadcasters.
