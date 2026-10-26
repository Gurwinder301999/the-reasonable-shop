---
type: Trade Case Study
title: "TICKER — <short event> — <concise key-lesson hook>"
description: One-line key lesson — what an agent reads to decide whether to load this file.
ticker: TICKER
event: e.g., Q1 2026 earnings, Investor Day, FDA decision
date: YYYY-MM-DD
status: open | closed
result: profit | loss | breakeven
structures: comma-separated structure names (e.g., bull-put-spread, jade-lizard)
tags: [comma, separated, trade, tags]
timestamp: YYYY-MM-DDTHH:MM:SSZ
---

# {Ticker} {Event} Trade Case Study ({Month YYYY})

One-paragraph trade arc summary including net result and the key structural lesson.

<!--
Canonical section skeleton. H2 order is fixed; separate every H2 section with a
`---` rule. Sections marked (optional) are included only when content exists,
in the order shown. "What Worked" / "What I Got Wrong (Analyst Side)" are
required whenever there is an executed trade or an analyst-error record; a pure
method / analysis-only study (no trade, no error post-mortem) omits both.
-->

---

## Setup

- **Ticker**: TICKER
- **Entry window**: dates
- **Event**: date + AMC/BMO
- **Starting context**:
  - Stock state (price, recent move, technicals)
  - IV state (IV Rank, HV)
  - Sentiment state (sell-side, channel checks, sector mood)

---

## Strategy Evolution

### Stage 1: <name> (date, $price)

**Thesis**: ...
**Structure**: ...
**Flaw in hindsight**: ...

### Stage 2 ... etc.

---

## Outcome

<!-- Heading stays exactly "Outcome" — put any as-of qualifier in a bold first
     line, e.g. **As of 6/24 AH (T+1 unconfirmed).** -->

- Print result
- Stock reaction
- P&L by leg
- Net result vs plan

---

## What Worked

1. ...

## What I Got Wrong (Analyst Side)

1. ...

### Meta-insight

<!-- The cross-cutting takeaway, if any, always lives here — at the end of the
     What I Got Wrong section. -->

---

## Lessons / Updates to Framework

- New rules added to `../pitfalls/` (link by file name)
- Updates to `../strategies.md`

---

## Reusable Framework: <Setup-Type> Plays

(optional) Step-by-step framework for similar future setups.

---

## Specific Data Points (For Reference)

(optional) Raw flow / IV / tape numbers worth keeping but too heavy for the narrative sections.

---

## Open Questions / Followups

(optional) Unresolved hypotheses, planned structures, forward catalyst dates.

---

## Cross-References

(optional) Links to related pitfalls, frameworks, and sibling case studies.

---

## Updates Log

(optional) Dated post-hoc amendments once the file is otherwise frozen.
