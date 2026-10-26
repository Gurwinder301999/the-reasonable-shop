---
type: Trading Pitfall
title: Compute the subject's share of the corpus before framing a conclusion around it
description: The ticker that started the inquiry is a convenience sample, not a finding; measure its share of mentions / premium / positions / P&L before letting it frame the picture, and re-derive the corpus boundary instead of inheriting it from the question.
severity: HIGH
appliesTo: research, kol-backtest, post-mortem, flow, fundamental
tags: [scope-bias, anchoring, denominator, base-rate, sampling]
timestamp: 2026-08-15T02:20:00Z
---

## Compute the subject's share of the corpus before framing a conclusion around it

**Severity: HIGH (does not lose money directly — it produces a confident, wrong picture that then sizes positions)**

When you hold a full corpus — a KOL's entire post history, a session's whole tape, your own complete book, a chat archive — the subject that brought you in is a **convenience sample**, not a finding. Before building any thesis around it, compute what share of the corpus it actually occupies. If the share is small, the headline is somewhere else.

The failure is **not** answering the question you were asked. It is letting the question's scope silently become the conclusion's scope when you move from *"what about X?"* to *"here is what this whole system looks like."* Anchoring on X while answering about X is correct; still anchoring on X while characterising the system is the error.

**Why it matters**: A subscriber chat was crawled to read sentiment on one short position (NBIS). NBIS was **171 of 84,601 comments — 0.20%**, ranked 36th by mention count. The corpus's actual centre of mass was a 16-part war-and-markets series: **21,765 comments across 41 threads = 27.4%**, versus **8.3%** for the AI-bubble thread family the whole analysis had been built around. Worse, the trade ledger assembled to score the author inherited its start date from the inquiry's frame, so his **largest and best position was missing entirely** — a holding he had sized at "over 16% of my portfolio" on 2026-02-18 and which ran **+49.0%** (142.61 → 212.43) sat outside the window and was never scored. Three deliverables were produced on the 0.2% slice before anyone computed the denominator.

**How to apply**:
- Before writing a single-name conclusion from a corpus you already hold, compute that name's share of: (a) mentions, (b) premium / notional, (c) position count, (d) P&L contribution. **Write the number down in the output.**
- Threshold: under **~5%** on the relevant measure, the subject is an anecdote. Either state the denominator explicitly in the conclusion, or re-frame around what the ranking actually surfaced.
- **Rank first, read second.** Sort the corpus by raw count *and* by a weighting proxy (reaction count, premium, position size, P&L). Read the top of **both** lists before reading your subject — the two orderings disagree often, and the disagreement is itself the finding.
- Re-derive the corpus boundary from the subject matter, never from the question. Ask what the *earliest possible* start of the real record is; a start date inherited from a format change, a data-source cutover, or the day the user first asked is a silent truncation.
- Treat a handed-to-you entry point (a user's question, a KOL's shout, a headline, one block print) as sampling bias with a **known direction**: it over-weights whatever was salient to whoever handed it over.
- Fires on: KOL backtests (score the full history, not the calls being cited), post-mortems (score the whole book, not the losing position), flow reads (one ticker's premium against its sector), and any "why did X happen" framing.

Related: [`14-channel-check-sample-bias.md`](14-channel-check-sample-bias.md) is the inverse failure — too few sources rather than the wrong slice of enough sources. [`02-single-flow-not-smart-money.md`](02-single-flow-not-smart-money.md) and [`32-multi-leg-share-before-block-direction.md`](32-multi-leg-share-before-block-direction.md) are downstream instances of the same "measure the share before reading the signal" discipline.
