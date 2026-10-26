---
type: Trading Pitfall
title: A per-trade risk cap is not risk management — without a daily loss limit, a consecutive-loss halt, and drawdown-tiered de-gearing, N perfectly disciplined stops in a row still ruin the account
description: A "max 2% per trade" rule bounds one trade, not one day, week, or drawdown; intraday trades on one instrument are correlated re-expressions of one bet, not independent draws, so losses cluster. Add three governors — day stop (~2–3× per-trade risk), consecutive-loss halt, and size reduction tiered on equity drawdown — and respect the recovery asymmetry (−30% needs +43%).
severity: HIGH
appliesTo: risk-management, position-sizing, futures, day-trading, intraday, drawdown, tilt, portfolio-heat
tags: [daily-loss-limit, drawdown, de-gearing, consecutive-losses, correlation, portfolio-heat, tilt, revenge-trading, risk-of-ruin, recovery-asymmetry, futures]
timestamp: 2026-07-30T12:00:00Z
---

## A per-trade risk cap is not risk management — it bounds one trade, not one day

"Never lose more than 2% on a trade" is necessary and nowhere near sufficient. It says nothing about how many times per day that 2% may be spent. Eight consecutive stop-outs, each executed flawlessly, is **−15%** (compounded) with a perfect discipline record. Most blown day-trading accounts are not killed by one oversized trade; they are killed by a **cluster** of correctly-sized ones. A risk framework with a per-trade cap and no day-level, streak-level, or drawdown-level governor is one-third of a framework.

**Why it matters**: The per-trade cap implicitly models trades as independent draws. Intraday trades in one instrument are not independent — they are **the same bet re-expressed**. Same instrument, same session, same regime, same reasoning, and usually the same directional bias: when the read is wrong, it is wrong for all of them, and the losses arrive consecutively by construction. Worse, the sequence is self-reinforcing: each loss degrades execution quality (tilt, revenge sizing, chasing, abandoning the entry criteria to "make it back"), so realized win rate *falls* precisely as the trader takes more trades. And recovery is arithmetically asymmetric — the deeper the hole, the more the *next* trade has to earn on a *smaller* base:

| drawdown | gain needed to recover |
|---|---|
| −10% | +11% |
| −20% | +25% |
| −30% | **+43%** |
| −50% | **+100%** |

So the day stop is not a comfort measure; it is what keeps the required recovery inside the range your edge can actually produce.

**How to apply**:

### 1. Three governors, all mandatory

| governor | rule of thumb | what it protects against |
|---|---|---|
| **Daily loss limit** | stop trading for the day at **2–3× the per-trade risk** (e.g. per-trade 1% → day stop 2–3%) | correlated clustering + tilt within one session |
| **Consecutive-loss halt** | **3 stops in a row → flat and done**, regardless of dollars lost | a broken read or a regime the setup doesn't work in |
| **Drawdown-tiered de-gearing** | −5% from equity high → size ×0.75; −10% → ×0.5; −15% → simulator / paper until a written review is done | slow bleed becoming terminal; forces diagnosis before re-risking |

"Stop trading for the day" means **flat and platform closed** — not "smaller size", which is how the limit gets negotiated away.

### 2. Budget the day before the first trade, not after the third loss

Convert the day stop into a **trade count**: day stop ÷ per-trade risk = the number of full-risk attempts the session allows. At 1% per trade and a 3% day stop, the answer is **three**. Knowing "I have three bullets" before the open changes selection quality more than any entry rule — it is the mechanism behind "good traders take few trades, each at a key level". If you are on your third attempt of the day, the correct question is not "where's the entry" but "why were the first two wrong".

### 3. Count heat across positions, not per position

Concurrent positions in correlated instruments (MNQ + MES, NVDA + SOXL, two AI-infra names) are **one bet with multiple tickets**. Sum the risk across all open trades and cap the total (portfolio heat) at the same per-trade limit, discounted only for genuinely independent theses. Two "2% risk" positions in the same complex is a 4% bet, not two 2% bets.

### 4. Escalate the review with the drawdown

- **Day stop hit**: log it, no trading until next session. No post-mortem required beyond the log.
- **Two day stops in a week** or a **consecutive-loss halt**: written review before re-risking — was the setup absent, the level wrong, the size wrong, or the regime unsuitable? De-gear one tier.
- **−15% from equity high**: stop live trading. Re-derive the edge on paper with a recorded sample before returning; scale back up only on demonstrated results, not on feeling recovered.

### 5. Log fields that make any of this auditable

A framework claiming to be "reviewable" needs a per-trade record, otherwise the review is memory-based and therefore flattering. Minimum fields: **date/session, instrument, direction, entry, stop (points and ÷ ATR), size, target, exit, R multiple, MAE, MFE, setup name, followed-plan Y/N, cumulative day P/L, day-stop status.** MAE (max adverse excursion) is the load-bearing one — it is the only field that tells you whether your stops are too tight (winners repeatedly show MAE close to the stop) or your targets are too far (MFE clusters short of target).

### 6. Withdrawal / equity-extraction discipline is a governor too

Periodically moving profits out of the trading account is the sizing rule's ally: it caps the absolute dollar amount at risk from a single bad streak and prevents unplanned position-size inflation as equity drifts up. The reverse is also true — **size must follow equity down**, which is §1's de-gearing tier. A withdrawal rule without a de-gearing rule only ratchets one direction.

### 7. Mechanical checklist

1. Write down per-trade risk %, day stop, consecutive-loss halt, and de-gearing tiers **before** the session.
2. Compute the day's bullet count = day stop ÷ per-trade risk.
3. Sum open risk across correlated positions; treat the complex as one bet.
4. On day stop or 3 straight losses: flat, close the platform, log.
5. Mark equity high-water; de-gear on −5 / −10 / −15%.
6. Log every trade with MAE/MFE; review the MAE distribution against the stop (feeds pitfall 30 — persistently tight stops show up here first).
7. Never widen a stop, add size, or lift the day stop to recover a loss.

### 8. Cross-references

- Pitfall 30 — stop distance determines size (the per-trade layer; this pitfall is the session/streak/drawdown layer above it. Both are required: correct per-trade sizing with no day stop still ruins; a day stop with noise-band stops just loses more slowly)
- Pitfall 13 — take-profit discipline (the symmetric rule on the winning side)
- Pitfall 23 — hazard-rate discounting (drawdown raises the termination hazard, which lowers optimal hold and argues for de-gearing)
- Pitfall 4 — flip on invalidation (a losing streak is often one wrong regime read, not five wrong trades)
- Pitfall 28 — macro-right/trade-wrong (kill switch 4: vol-inappropriate size)
- [`../overnight-futures-framework.md`](../overnight-futures-framework.md) — session clock; the "day" boundary for a 23-hour instrument needs defining explicitly
