# the-reasonable-shop

## Reports

| Report | Output | Build |
|---|---|---|
| Wi-Fi Signal Strength Assessment | `reports/wifi-signal-assessment/wifi-signal-strength-assessment.pdf` | `python3 tools/build_wifi_report.py` |
| Swing Strategy Backtest | `reports/trading/swing-strategy-backtest.pdf` | `python3 tools/trade_engine.py` |

## Vendored skills

| Skill | Source | Pinned at | Verify |
|---|---|---|---|
| `trade-skills` — options trading knowledge base (38 pitfalls, 15 case studies, 6 frameworks) | [himself65/trade-skills](https://github.com/himself65/trade-skills), MIT | `aa764fb` (plugin v2.20.0) | `python3 tools/check_skill.py` |

A pinned snapshot, not a submodule: `vendor/trade-skills/`. Provenance, update steps, the missing
data tiers and the US-options-versus-Indian-cash-equities scope gap are documented in
[`vendor/trade-skills/VENDORED.md`](vendor/trade-skills/VENDORED.md). The snapshot is reference
material only — its agent instructions are inert unless a task explicitly invokes the skill.

### Wi-Fi Signal Strength Assessment

A typeset, four-page client-facing report covering seven locations in a single dwelling:

1. Executive summary and headline figures
2. Coverage profile chart (RSSI by location, with rating thresholds)
3. Area-by-area assessment table
4. Rating guide and priority grouping
5. Recommended actions
6. Measurement note and limitations
7. Appendix A — blank survey record template and sign-off

The report is generated, not hand-edited. The authoritative content lives in
`tools/build_wifi_report.py` (the `METADATA`, `AREAS`, `RATING_GUIDE` and `ACTIONS` constants);
edit those and rebuild.

#### Build requirements

```bash
pip install reportlab
python3 tools/build_wifi_report.py [optional/output/path.pdf]
```

DejaVu Sans fonts are expected at `/usr/share/fonts/truetype/dejavu` (standard on Debian/Ubuntu
and available in the `fonts-dejavu` package).

#### Note on the figures

The dBm values are **illustrative estimates**, not verified WiFiman measurements. This is stated on
the cover, in the running footer and in Section 6. Replace the estimates in `AREAS` with recorded
readings — and remove or amend the "Preliminary" status text — once a measured survey has been
carried out. Appendix A provides the capture sheet for that survey.

---

### Swing Strategy Backtest

A rules-based swing-trading engine with a cost-aware backtest and a six-page client-facing report.
It is **not** a broker connection, a signal service or a trading bot: it places no orders, holds no
funds, and cannot trade on your behalf. What it does is turn one fully specified strategy into
evidence you can argue with.

#### Strategy under test — "Trend Pullback" (long only, delivery/CNC)

| Element | Rule |
|---|---|
| Regime | `close > SMA200` and `SMA50 > SMA200` |
| Entry trigger | `RSI(2) ≤ 12` (next bar's open) |
| Stop | `entry − 2.5 × ATR(14)` |
| Target | `entry + 4.0 × ATR(14)` |
| Exits | stop, target, `RSI(2) ≥ 80`, `close < SMA200`, or 40 bars |
| Sizing | risk 1% of equity per trade, capped at 20% of equity |
| Limits | 4 concurrent positions, one per symbol |

Costs are charged per leg using NSE delivery rates (STT, exchange, SEBI, stamp duty, GST, DP);
slippage and income tax are deliberately excluded, and the report says so.

#### Build

```bash
python3 tools/make_sample_data.py          # write synthetic bars to data/ (see the warning below)
python3 tools/trade_engine.py              # backtest + CSV/JSON artefacts + PDF
python3 tools/trade_engine.py --signals    # also print signals on the latest bar
```

Options: `--data DIR`, `--out DIR`, `--capital N`, `--risk 0.01`, `--no-pdf`.
Only the PDF needs `reportlab`; the engine itself is standard library.

Artefacts written to `reports/trading/`:

| File | Contents |
|---|---|
| `swing-strategy-backtest.pdf` | The report: rules, equity curve, costs, distribution of trades, caveats |
| `backtest-trades.csv` | Every round trip — entry, exit, stop, costs, net P&L, R-multiple |
| `backtest-equity.csv` | Daily equity curve |
| `backtest-metrics.json` | All summary figures, machine-readable |

#### Using real data

`tools/make_sample_data.py` generates **synthetic** prices with a regime-switching random walk. They
have no relationship to any real security, and the report is labelled "SIMULATED" throughout for
that reason. To test the rules on reality, export daily bars and drop them in `data/` as
`SYMBOL.csv` with a header of `date,open,high,low,close,volume` (date as `YYYY-MM-DD`), then rerun.
Free sources: your broker's historical export, or NSE bhavcopy archives.

#### What the included run shows

On the synthetic universe the strategy returned **+9.3% total over 8.7 years (+1.0% CAGR)** against
**+105.8%** for equal-weight buy-and-hold of the same six symbols, with a −5.1% maximum drawdown,
261 round trips and ₹33,223 paid in charges. Average trade: **+0.04R** — after costs, effectively
nothing. The report's verdict is "Not yet an edge", and readers are told to replace the data and
add slippage before believing it.

That result is the point of the exercise: a plausible-looking set of rules, sized properly and
costed honestly, does not automatically beat doing nothing. Any strategy worth risking money on has
to clear that bar first.
