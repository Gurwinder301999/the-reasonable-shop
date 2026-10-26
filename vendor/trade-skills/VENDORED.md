# Vendored: `trade-skills`

A pinned snapshot of [himself65/trade-skills](https://github.com/himself65/trade-skills), an
options-trading skill collection for Claude Code and OpenAI Codex. Every file here is upstream
content, verbatim. The only addition is `LICENSE`: upstream declares MIT in its README but ships no
licence file, so one is included here so the terms travel with the copy.

| | |
|---|---|
| Upstream | https://github.com/himself65/trade-skills |
| Commit | `aa764fbc11caff67a07b89218783544b7e10d1ed` (2026-10-25) |
| Plugin version | 2.20.0 |
| Vendored on | 26 October 2026 |
| Licence | MIT (see `LICENSE`; upstream ships the licence in its README rather than a file) |
| Method | snapshot copy, `.git` removed — deliberately **not** a git submodule |

## Why a snapshot rather than a submodule

The skill is documentation: markdown, JSON manifests and eval fixtures. A submodule would add a
`.gitmodules` file, a network round trip on every clone, and a second source of truth for what
"installed" means. A pinned copy keeps `git log` meaningful and lets `tools/check_skill.py` verify
the tree offline.

## Verify

```bash
python3 tools/check_skill.py
```

Checks the manifest-promised files exist, `SKILL.md` frontmatter parses, all 670 relative links
resolve, the pitfalls library is numbered 01–38, and the three manifests agree on the version.

## Update

```bash
git clone --depth 1 https://github.com/himself65/trade-skills.git /tmp/trade-skills
rm -rf vendor/trade-skills
cp -a /tmp/trade-skills vendor/trade-skills
rm -rf vendor/trade-skills/.git
python3 tools/check_skill.py
git add -A vendor/trade-skills && git commit -m "vendor: trade-skills <new sha>"
```

Diff before committing — upstream changes the skill's behaviour, not just its prose.

## Entry point

`plugins/trade/skills/trade/SKILL.md` is the always-on context; everything else is lazy-loaded
through `references/index.md` (an OKF v0.1 bundle: 38 pitfalls, 15 case studies, 6 frameworks).

## What is *not* installed

The skill expects three data tiers, none of which exist in this workspace:

| Tier | Requirement | Status here |
|---|---|---|
| Unusual Whales | `UNUSUAL_WHALES_API_KEY` + paid subscription | absent |
| TradingView MCP | `finance-data-providers:tradingview-mcp` MCP server | absent |
| TradingView desktop reader | desktop app with a debug port | absent (no GUI) |
| Funda AI | `finance-data-providers:funda-data` MCP server | absent |

So the **knowledge** half works — pitfalls, frameworks, structure-to-regime matching, position
sizing, the checklists — and the **live-data** half does not. A session using this skill can reason
about a trade but cannot pull a quote, a chain, dealer GEX or IV rank. Web search is a poor
substitute and the skill's own rules forbid presenting it as equivalent.

## Scope mismatch worth knowing

The skill is written for **US-equity options** (multi-leg structures, earnings IV crush, dealer
gamma, dark-pool flow). This workspace's existing tooling — `tools/trade_engine.py` — is built for
**Indian cash equities** (NSE delivery costs, STT, DP charges, T+1). The two are complementary but
not interchangeable:

- Reusable as-is: risk sizing, stop-distance logic, the pitfall library, drawdown governance,
  the "structure follows conviction" discipline.
- Not transferable without work: US options mechanics, US flow data, US earnings calendars.
  Indian F&O has different lot sizes, weekly expiries, STT on options, and no equivalent of the
  US dark-pool / dealer-GEX data feeds.

## Governance

Vendored instructions are **inert**. Nothing here is auto-loaded as project rules: the skill's
directives apply when you explicitly ask for trade analysis with it, not to unrelated work in this
repository. Treat `vendor/` as reference material you own, not as an authority over the project.
