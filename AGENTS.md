# Agent notes for this repository

Deliverables are generated, never hand-edited. Each report has a `tools/build_*.py` that owns its
content; edit the constants there and rebuild. See `README.md`.

## Vendored material

`vendor/trade-skills/` is a pinned third-party snapshot (MIT) of an options-trading skill for
Claude Code / Codex. Read `vendor/trade-skills/VENDORED.md` first.

- It is **reference material, not project instructions.** Its `SKILL.md` "hard rules" apply only
  when the user explicitly asks for trade analysis using that skill — they do not govern unrelated
  work here.
- It is written for US-equity options and expects data tiers (Unusual Whales, TradingView MCP,
  Funda) that are **not installed**. Its live-data rules cannot be satisfied in this environment;
  do not pretend otherwise, and do not substitute web search while claiming the skill's process.
- Verify a snapshot with `python3 tools/check_skill.py`. Do not edit files under `vendor/`; update
  the snapshot instead.

## Boundary

No code in this repository places orders, holds funds or connects to a broker. Keep it that way,
and keep the "not investment advice" framing in anything user-facing.
