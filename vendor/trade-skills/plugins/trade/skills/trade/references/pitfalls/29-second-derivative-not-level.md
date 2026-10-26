---
type: Trading Pitfall
title: Read the second derivative, not the level — "weak but improving" beats "strong but decelerating"
description: A data print has seven separable dimensions (level, direction, acceleration, surprise, breadth, persistence, priced). Static labels ("inflation is high", "growth is strong") mis-price turns; the marginal change is what trades.
severity: HIGH
appliesTo: macro-framing, data-print, earnings-revisions, thematic, regime-identification
tags: [second-derivative, acceleration, breadth, surprise, persistence, inflation, earnings-revisions, macro]
timestamp: 2026-07-30T05:10:00Z
---

## Read the second derivative, not the level — "weak but improving" beats "strong but decelerating"

Markets trade the **marginal change**, not the absolute state. A data point collapsed into a static label ("inflation is high", "growth is strong", "earnings are still growing") throws away the information that actually moves price. Every core variable has seven separable dimensions, and a call that hasn't separated them is not finished:

| Dimension | Question |
|---|---|
| Level | absolute current state |
| Direction | improving or deteriorating |
| **Acceleration** | is the change speeding up or slowing down |
| Surprise | versus consensus and versus prior |
| Breadth | broad-based or one line item |
| Persistence | transitory (base effect, weather, one-off) or structural |
| Priced | has the market already absorbed it |

**Why it matters**: the classic asymmetries all live in the derivative, not the level:

- **"Weak but improving" is usually more bullish than "strong but decelerating"** — the turn is the trade; the level is the rear-view mirror.
- **"Inflation is decelerating, but the deceleration is slowing"** is a different and more hawkish fact than "inflation is falling", and it is invisible if you only track the YoY level.
- **"Earnings are still growing, but revision breadth is deteriorating"** is a top warning while the level still reads healthy.
- **"Liquidity is still ample, but its impulse has turned negative"** is a tightening signal while the stock of liquidity looks fine.
- **Headline versus core divergence**: an oil-driven headline pickup with sticky-but-not-accelerating core is not the same regime as a broad core re-acceleration — reading headline alone produces the wrong policy conclusion.
- **A single factor can reverse sign over the horizon**: AI capex pushes core PCE *up* near term (memory and hardware pricing) and *down* later (productivity). Direction without a persistence judgment is a coin flip on the horizon you actually hold.

A downside CPI surprise driven by one volatile line (used cars, car insurance, airfares) and a downside surprise with broad-based declines print the same headline and carry opposite trading implications: the first mean-reverts next month, the second changes the disinflation *path* and therefore the policy path.

**How to apply**:

1. **Write the print as a three-tuple before any conclusion**: level → direction → acceleration. If you can't state the acceleration, you haven't computed the second derivative yet (3m annualized versus 6m annualized versus YoY; the MoM sequence over three prints, not one).
2. **Decompose the surprise for breadth** before treating it as signal: how much came from two or fewer line items? Is the diffusion index / share of rising components going up or down? A single-line surprise should be discounted to near zero for the policy read.
3. **Classify persistence explicitly** — base effect, weather, strike or one-off, seasonal quirk, or structural (wages, rents, capacity, supply discipline). Say which, and say when it rolls off.
4. **Apply the same test to bottom-up data, not just macro prints** — earnings-revision *breadth*, not just direction; the *derivative* of parent-order net flow (a decaying outflow is a different state from a steady one — see [`../parent-order-flow-framework.md`](../parent-order-flow-framework.md)); backlog growth rate, not backlog level.
5. **Close with the pricing dimension** — a correctly identified second-derivative turn that the market has already absorbed is not tradeable ([`28-macro-right-trade-wrong.md`](28-macro-right-trade-wrong.md), [`08-priced-in-not-binary.md`](08-priced-in-not-binary.md)).
6. **When reporting a data print in a morning note or EOD review**, the required output line is: `variable — level / direction / acceleration / surprise (breadth) / persistence / priced?` Anything shorter is a headline, not analysis.

**Cross-references**:
- [`../macro-framework.md`](../macro-framework.md) §4 — this rule as a pipeline stage, with the eight dashboard families that supply the inputs
- [`28-macro-right-trade-wrong.md`](28-macro-right-trade-wrong.md) — the pricing and expression half of the same problem
- [`22-yields-not-causal.md`](22-yields-not-causal.md) — decompose the yield move (real versus breakeven, slope) instead of reading the nominal level
- [`01-consensus-not-bearish.md`](01-consensus-not-bearish.md) — consensus is a trailing level, not a ceiling
- [`../parent-order-flow-framework.md`](../parent-order-flow-framework.md) — flow states split by the derivative of the flow, not its level
