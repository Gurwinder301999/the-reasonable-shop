---
type: Trading Pitfall
title: Check the multi-leg share before reading direction off an options block — spread legs print full premium and fake the tape
description: Ranking options blocks by premium without filtering spread legs and stock-combo legs manufactures a directional signal that isn't there; filter to outright prints before calling flow bullish or bearish.
severity: HIGH
appliesTo: flow-analysis, block-flow, options-flow, earnings, parent-order, report
tags: [multi-leg, spread-legs, block-flow, options-flow, aggressor-side, buy-write, false-signal, 大单]
timestamp: 2026-08-07T17:05:00Z
---

## Check the multi-leg share before reading direction off an options block

A "$43M put sale" and a "$14M call buy" are not directional bets if 99% of that volume printed as **legs of a spread**. Options flow feeds report **each leg at its full premium with its own aggressor side**, so a single risk-defined spread shows up in a naive premium tally as two large, oppositely-signed "bets." Rank blocks by premium without filtering, and the biggest number on the screen is usually the leg of a structure whose *net* direction is the opposite — or zero.

**Why it matters**: This is not a rounding error, it is a **sign flip**. The tally is dominated by the largest prints, and the largest prints are disproportionately spreads — institutions express size through defined-risk structures, not naked singles. So the naive ranking systematically over-weights exactly the trades whose individual legs mean nothing. Pitfall 2 says *one big order isn't smart money*; this is the stricter statement: **one big order may not even be an order in the direction it appears to be.**

Two distinct contaminants, two distinct fields:

| Field | What a high value means | How it fakes you out |
|---|---|---|
| `multi_leg_volume / volume` | Printed as part of an options spread | A bull put spread reads as "huge put selling" on the short leg **and** "huge put buying" on the long leg; whichever leg is larger sets a false net direction |
| `stock_multi_leg_volume / volume` | Printed against stock (buy-write, married put, conversion, delta-hedged block) | A $25M "call sale" at 100% stock-leg is a **covered call** — someone *bought stock*. Reading it as bearish inverts the trade |

Concrete failure (NBIS, 2026-08-07). Reconstructing nine sessions of block flow (`options/stock?type=oi-change`, which carries `prev_multi_leg_volume` and `prev_stock_multi_leg_volume`), the naive premium tally versus the outright-only tally:

| Session | Naive net direction (all prints) | Outright-only (multi-leg <30%, stock-leg <30%) |
|---|---|---|
| 2026-07-28 (−9.7%) | **+$68.9M** — "massive bullish flow" | **$0.0M** |
| 2026-08-05 (−3.0%) | **+$35.8M** — "massive bullish flow" | **−$2.7M** |

The top prints driving those numbers: Aug-14 P220 **$43.28M at 99% multi-leg**; Sep-18 P210 $26.44M at 95%; Aug-21 C190 $13.47M at **100%**; Jan-2028 C400 **$24.61M at 100% stock-multi-leg** (a buy-write — the largest single print in the window and the one most likely to be misread as a bearish call dump).

After filtering, only **three** signals survived — and all three were multi-day and direction-consistent, which is the standard the parent-order framework actually requires: persistent outright long-dated **put buying** (the best-timed trades in the window — one bought the day before a two-day −21% break, another bought on a +11.6% up day), persistent outright far-OTM long-dated **call selling**, and a single clean **15,924-contract deep-OTM put sale at 1% multi-leg** executed on a −13.3% day. The composite read — a holder collaring the book, not accumulating or distributing — is unobtainable from the unfiltered tally.

**How to apply**:

1. **Never rank blocks by `total_premium` alone.** Pull the multi-leg fields in the same request and compute both shares before sorting. If your feed does not expose them, you cannot read direction off block size — say so instead of guessing.
2. **Filter thresholds**: treat a print as *outright* only when `multi_leg_volume / volume < 30%` **and** `stock_multi_leg_volume / volume < 30%`. Report the outright-only net as the direction, and the unfiltered net alongside it as the activity signal. Publishing only the unfiltered number is the error.
3. **Reconstruct, don't discard.** Spread legs are informative *as structures*: same session + same expiry + opposite strikes + high multi-leg share usually reassembles into one package. Price the package, not the leg. State explicitly that same-account ownership is an inference — the multi-leg flag proves spread *execution*, not a single book. **With an Unusual Whales key this step stops being inference**: `/api/option-trades/multi-leg` returns the package (`net_premium`, `net_side`, `leg_count`, `all_opening_legs`) and `/api/option-trades/multi-leg/{id}/legs` returns its legs, and every flow alert carries `has_multileg` / `has_singleleg` directly — see [`../unusual-whales.md`](../unusual-whales.md). Reassemble from those endpoints rather than from a same-session heuristic whenever they are reachable.
4. **A 100% `stock_multi_leg` call sale is bullish-to-neutral, not bearish.** Check whether the strike sits above the holder's plausible basis before labeling it a cap.
5. **Require multi-day, direction-consistent persistence** after filtering (parent-order framework, caveat 1). A single outright print, however large, is still pitfall 2.
6. **Aggressor side ≠ position side.** Bid-side = seller-initiated, not "bearish"; passive institutional accumulation prints as selling and *understates* real buying.
7. **Say what you filtered.** If the feed truncates (`flow-alerts` caps at `limit`, and a busy session hits it), your counts and premium sums are bounded — take direction from the complete aggregate (`options-volume`, `oi-change`) and flag the truncation.

**Cross-references**:
- Pitfall 2 — a single large options trade isn't smart money (this rule is the stricter, mechanical precondition)
- Pitfall 17 — options flow is dealer positioning, not retail direction
- [`../parent-order-flow-framework.md`](../parent-order-flow-framework.md) — the state matrix this feeds; its measurement caveats assume the flow input is already de-contaminated
- [`../commands/report.md`](../commands/report.md) — the daily 资金流向 read that produces the flow numbers
- [`../unusual-whales.md`](../unusual-whales.md) — the dedicated multi-leg endpoints that make the filter exact instead of a share estimate
