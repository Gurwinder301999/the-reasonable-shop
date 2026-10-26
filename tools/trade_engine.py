#!/usr/bin/env python3
"""Rules-based swing-trading engine: signals, position sizing, cost-aware
backtest, and a client-facing PDF report.

What this is
------------
A complete, auditable implementation of one fully-specified strategy, evaluated
with realistic Indian delivery-equity costs. It produces:

  reports/trading/backtest-trades.csv   every round trip, with R-multiples
  reports/trading/backtest-equity.csv   daily equity curve
  reports/trading/backtest-metrics.json summary statistics / API-friendly
  reports/trading/swing-strategy-backtest.pdf   the report

What this is NOT
----------------
It does not connect to a broker, hold funds, or place orders. Nobody - human or
software - should trade a strategy it has not seen lose money in simulation
first. Treat the output as evidence about a *process*, never as a forecast.

Strategy under test: "Trend Pullback" (long only, delivery/CNC)
---------------------------------------------------------------
  Regime   : close > SMA200 and SMA50 > SMA200     (uptrend only)
  Setup    : RSI(2) <= 12                          (short-term washout)
  Entry    : next bar's open
  Stop     : entry - 2.5 x ATR(14)
  Target   : entry + 4.0 x ATR(14)                 (1.6R at the stop distance)
  Exits    : stop hit / target hit / RSI(2) >= 80 at close (next open) /
             close < SMA200 (next open) / 40 bars held (next open)
  Sizing   : risk 1% of equity per trade; position capped at 20% of equity
  Limits   : 4 concurrent positions, 1 position per symbol

Backtest conventions
--------------------
  * Indicators use data up to and including bar t; orders fill at bar t+1's
    open. No same-bar lookahead.
  * Stops and targets are checked against the bar's low/high. If the bar opens
    through the stop, the fill is at the open (gap risk is real).
  * When both stop and target are touched in one bar, the stop is assumed to
    fill first. That is the pessimistic, and the only defensible, assumption.

Usage
-----
    python3 tools/trade_engine.py [--data DIR] [--out DIR] [--capital N]
                                 [--risk 0.01] [--no-pdf]

Requires reportlab for the PDF only; the engine itself is standard library.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import sys
from datetime import date

# --------------------------------------------------------------------------
# Strategy parameters
# --------------------------------------------------------------------------

PARAMS = {
    "sma_fast": 50,
    "sma_slow": 200,
    "rsi_period": 2,
    "rsi_entry": 12.0,
    "rsi_exit": 80.0,
    "atr_period": 14,
    "stop_atr": 2.5,
    "target_atr": 4.0,
    "max_hold_bars": 40,
    "max_positions": 4,
    "max_position_pct": 0.20,
    "risk_per_trade": 0.01,
}

# --------------------------------------------------------------------------
# Indian delivery-equity cost model (NSE, as of 2025)
# --------------------------------------------------------------------------

COSTS = {
    "stt_buy": 0.001,          # 0.1% securities transaction tax
    "stt_sell": 0.001,
    "exchange": 0.0000325,     # NSE transaction charge
    "sebi": 0.000001,          # SEBI turnover fee
    "stamp_buy": 0.00015,      # stamp duty, buy side only
    "gst": 0.18,               # GST on brokerage + exchange + SEBI
    "brokerage": 0.0,          # delivery brokerage assumed zero (discount broker)
    "dp_per_sell": 15.93,      # depository participant charge, per sell per scrip
}


def buy_costs(value: float) -> float:
    base = COSTS["brokerage"] + value * COSTS["exchange"] + value * COSTS["sebi"]
    return (value * COSTS["stt_buy"] + value * COSTS["exchange"]
            + value * COSTS["sebi"] + value * COSTS["stamp_buy"]
            + COSTS["gst"] * base)


def sell_costs(value: float) -> float:
    base = COSTS["brokerage"] + value * COSTS["exchange"] + value * COSTS["sebi"]
    return (value * COSTS["stt_sell"] + value * COSTS["exchange"]
            + value * COSTS["sebi"] + COSTS["dp_per_sell"]
            + COSTS["gst"] * base)


# --------------------------------------------------------------------------
# Indicators (Wilder-smoothed where applicable)
# --------------------------------------------------------------------------

def sma(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= period:
            running -= values[i - period]
        if i >= period - 1:
            out[i] = running / period
    return out


def rsi(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        delta = values[i] - values[i - 1]
        gains += max(delta, 0.0)
        losses += max(-delta, 0.0)
    avg_gain, avg_loss = gains / period, losses / period
    out[period] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    for i in range(period + 1, len(values)):
        delta = values[i] - values[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(delta, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-delta, 0.0)) / period
        out[i] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return out


def atr(highs: list[float], lows: list[float], closes: list[float],
        period: int) -> list[float | None]:
    trs: list[float] = []
    for i in range(len(closes)):
        if i == 0:
            trs.append(highs[0] - lows[0])
        else:
            trs.append(max(highs[i] - lows[i],
                           abs(highs[i] - closes[i - 1]),
                           abs(lows[i] - closes[i - 1])))
    out: list[float | None] = [None] * len(closes)
    if len(trs) < period:
        return out
    first = sum(trs[:period]) / period
    out[period - 1] = first
    prev = first
    for i in range(period, len(trs)):
        prev = (prev * (period - 1) + trs[i]) / period
        out[i] = prev
    return out


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------

def load_series(path: str) -> dict[str, list[dict]]:
    """Return {'rows': [...], 'idx': {date: i}} for one symbol CSV."""
    rows: list[dict] = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        required = {"date", "open", "high", "low", "close"}
        if not required.issubset({(c or "").strip().lower() for c in reader.fieldnames or []}):
            raise ValueError(f"{path}: need columns {sorted(required)}")
        reader.fieldnames = [(c or "").strip().lower() for c in reader.fieldnames]
        for raw in reader:
            try:
                rows.append({
                    "date": raw["date"].strip()[:10],
                    "open": float(raw["open"]),
                    "high": float(raw["high"]),
                    "low": float(raw["low"]),
                    "close": float(raw["close"]),
                    "volume": float(raw.get("volume") or 0),
                })
            except (TypeError, ValueError, KeyError):
                continue
    rows.sort(key=lambda r: r["date"])
    deduped: list[dict] = []
    for r in rows:
        if deduped and deduped[-1]["date"] == r["date"]:
            deduped[-1] = r
        else:
            deduped.append(r)
    return {"rows": deduped, "idx": {r["date"]: i for i, r in enumerate(deduped)}}


def load_universe(data_dir: str) -> dict[str, dict]:
    universe: dict[str, dict] = {}
    for name in sorted(os.listdir(data_dir)):
        if not name.lower().endswith(".csv"):
            continue
        symbol = os.path.splitext(name)[0].upper()
        series = load_series(os.path.join(data_dir, name))
        if len(series["rows"]) < PARAMS["sma_slow"] + 20:
            print(f"  skip {symbol}: only {len(series['rows'])} bars, "
                  f"need > {PARAMS['sma_slow']}", file=sys.stderr)
            continue
        rows = series["rows"]
        closes = [r["close"] for r in rows]
        highs = [r["high"] for r in rows]
        lows = [r["low"] for r in rows]
        series["sma_fast"] = sma(closes, PARAMS["sma_fast"])
        series["sma_slow"] = sma(closes, PARAMS["sma_slow"])
        series["rsi"] = rsi(closes, PARAMS["rsi_period"])
        series["atr"] = atr(highs, lows, closes, PARAMS["atr_period"])
        series["closes"] = closes
        universe[symbol] = series
    return universe


# --------------------------------------------------------------------------
# Backtest
# --------------------------------------------------------------------------

def backtest(universe: dict[str, dict], capital: float,
             params: dict) -> dict:
    dates = sorted({r["date"] for s in universe.values() for r in s["rows"]})
    position_pct = params["max_position_pct"]
    max_positions = params["max_positions"]

    cash = capital
    positions: dict[str, dict] = {}
    pending_entries: list[dict] = []
    pending_exits: list[tuple[str, str]] = []
    trades: list[dict] = []
    equity_curve: list[tuple[str, float]] = []

    def mark(day: str) -> float:
        total = cash
        for sym, pos in positions.items():
            series = universe[sym]
            i = series["idx"].get(day)
            if i is None:  # symbol has no bar today: carry last known close
                total += pos["qty"] * pos["last_price"]
            else:
                total += pos["qty"] * series["rows"][i]["close"]
        return total

    for day in dates:
        # 1. exits scheduled at yesterday's close, filled at today's open
        for symbol, reason in pending_exits:
            pos = positions.get(symbol)
            series = universe[symbol]
            i = series["idx"].get(day)
            if pos is None or i is None:
                continue
            bar = series["rows"][i]
            cash += _close(cash, positions, trades, symbol, bar["open"], day,
                           reason, params)
        pending_exits = []

        # 2. entries scheduled at yesterday's close, filled at today's open
        for order in pending_entries:
            symbol = order["symbol"]
            if symbol in positions or len(positions) >= max_positions:
                continue
            series = universe[symbol]
            i = series["idx"].get(day)
            if i is None:
                continue
            bar = series["rows"][i]
            entry = bar["open"]
            stop = entry - params["stop_atr"] * order["atr"]
            if stop <= 0 or entry <= stop:
                continue
            qty = int((mark(day) * params["risk_per_trade"]) / (entry - stop))
            qty = min(qty, int((mark(day) * position_pct) // entry))
            if qty < 1:
                continue
            gross = qty * entry
            fees = buy_costs(gross)
            if gross + fees > cash:
                qty = int((cash / (entry * (1 + 0.002))) // 1)
                if qty < 1:
                    continue
                gross = qty * entry
                fees = buy_costs(gross)
                if gross + fees > cash:
                    continue
            cash -= gross + fees
            positions[symbol] = {
                "symbol": symbol,
                "entry_date": day,
                "entry_price": entry,
                "qty": qty,
                "stop": stop,
                "target": entry + params["target_atr"] * order["atr"],
                "risk_per_share": entry - stop,
                "risk_amount": qty * (entry - stop),
                "entry_costs": fees,
                "bars_held": 0,
                "last_price": bar["close"],
                "entry_idx": i,
            }
        pending_entries = []

        # 3. intrabar stop / target checks (stop first: pessimistic)
        for symbol in list(positions):
            pos = positions[symbol]
            series = universe[symbol]
            i = series["idx"].get(day)
            if i is None:
                continue
            bar = series["rows"][i]
            pos["bars_held"] += 1
            pos["last_price"] = bar["close"]
            if bar["open"] <= pos["stop"]:
                cash += _close(cash, positions, trades, symbol, bar["open"], day,
                               "gap through stop", params)
            elif bar["low"] <= pos["stop"]:
                cash += _close(cash, positions, trades, symbol, pos["stop"], day,
                               "stop", params)
            elif bar["high"] >= pos["target"]:
                cash += _close(cash, positions, trades, symbol, pos["target"], day,
                               "target", params)

        # 4. at the close: decide tomorrow's actions
        for symbol in list(positions):
            pos = positions[symbol]
            series = universe[symbol]
            i = series["idx"].get(day)
            if i is None:
                continue
            r = series["rsi"][i]
            slow = series["sma_slow"][i]
            close = series["rows"][i]["close"]
            reason = None
            if pos["bars_held"] >= params["max_hold_bars"]:
                reason = "time stop"
            elif r is not None and r >= params["rsi_exit"]:
                reason = "overbought"
            elif slow is not None and close < slow:
                reason = "trend break"
            if reason:
                pending_exits.append((symbol, reason))

        for symbol, series in universe.items():
            if symbol in positions or any(o["symbol"] == symbol for o in pending_entries):
                continue
            if len(positions) + len(pending_entries) >= max_positions:
                break
            i = series["idx"].get(day)
            if i is None:
                continue
            r = series["rsi"][i]
            fast, slow = series["sma_fast"][i], series["sma_slow"][i]
            a = series["atr"][i]
            close = series["rows"][i]["close"]
            if None in (r, fast, slow, a) or a <= 0:
                continue
            if close > slow and fast > slow and r <= params["rsi_entry"]:
                pending_entries.append({"symbol": symbol, "atr": a, "signal_date": day})

        equity_curve.append((day, mark(day)))

    # liquidate anything still open on the final bar at its close
    last_day = dates[-1]
    for symbol in list(positions):
        series = universe[symbol]
        i = series["idx"].get(last_day, len(series["rows"]) - 1)
        cash += _close(cash, positions, trades, symbol,
                       series["rows"][i]["close"], last_day, "end of test", params)
    if equity_curve:
        equity_curve[-1] = (last_day, cash)

    return {"trades": trades, "equity": equity_curve, "final_cash": cash,
            "dates": dates}


# `_close` keeps exit bookkeeping in one place: it removes the position, charges
# sell-side costs, records the trade and returns the cash proceeds.

def _close(cash: float, positions: dict, trades: list, symbol: str,
           price: float, day: str, reason: str, params: dict) -> float:
    pos = positions.pop(symbol)
    gross = pos["qty"] * price
    fees = sell_costs(gross)
    proceeds = gross - fees
    net = proceeds - (pos["qty"] * pos["entry_price"] + pos["entry_costs"])
    r_mult = net / pos["risk_amount"] if pos["risk_amount"] else 0.0
    trades.append({
        "symbol": symbol,
        "entry_date": pos["entry_date"],
        "exit_date": day,
        "entry_price": round(pos["entry_price"], 2),
        "exit_price": round(price, 2),
        "qty": pos["qty"],
        "stop": round(pos["stop"], 2),
        "target": round(pos["target"], 2),
        "risk_per_share": round(pos["risk_per_share"], 2),
        "risk_amount": round(pos["risk_amount"], 2),
        "gross_pnl": round(pos["qty"] * (price - pos["entry_price"]), 2),
        "costs": round(pos["entry_costs"] + fees, 2),
        "net_pnl": round(net, 2),
        "r_multiple": round(r_mult, 2),
        "bars_held": pos["bars_held"],
        "exit_reason": reason,
    })
    return proceeds


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------

def compute_metrics(result: dict, capital: float, universe: dict) -> dict:
    trades = result["trades"]
    equity = result["equity"]
    values = [v for _, v in equity]
    final = values[-1] if values else capital
    peak, max_dd, dd_start, worst_dd_at = capital, 0.0, None, None
    for day, v in equity:
        peak = max(peak, v)
        dd = (v - peak) / peak if peak else 0.0
        if dd < max_dd:
            max_dd, worst_dd_at = dd, day

    daily = [(values[i] / values[i - 1] - 1.0) for i in range(1, len(values))
             if values[i - 1] > 0]
    sharpe = 0.0
    if len(daily) > 2:
        sd = statistics.pstdev(daily)
        if sd > 0:
            sharpe = statistics.mean(daily) / sd * math.sqrt(252)

    years = 1.0
    if len(equity) > 1:
        d0 = date.fromisoformat(equity[0][0])
        d1 = date.fromisoformat(equity[-1][0])
        years = max((d1 - d0).days / 365.25, 1e-9)
    cagr = (final / capital) ** (1 / years) - 1 if final > 0 and years > 0 else -1.0

    wins = [t for t in trades if t["net_pnl"] > 0]
    losses = [t for t in trades if t["net_pnl"] <= 0]
    win_rate = len(wins) / len(trades) if trades else 0.0
    avg_win = statistics.mean([t["net_pnl"] for t in wins]) if wins else 0.0
    avg_loss = statistics.mean([t["net_pnl"] for t in losses]) if losses else 0.0
    gross_win = sum(t["net_pnl"] for t in wins)
    gross_loss = -sum(t["net_pnl"] for t in losses)
    profit_factor = gross_win / gross_loss if gross_loss > 0 else float("inf")
    expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss

    by_symbol: dict[str, dict] = {}
    for t in trades:
        s = by_symbol.setdefault(t["symbol"], {"trades": 0, "net": 0.0, "wins": 0})
        s["trades"] += 1
        s["net"] += t["net_pnl"]
        s["wins"] += 1 if t["net_pnl"] > 0 else 0

    bars_in_market = sum(t["bars_held"] for t in trades)
    exposure = bars_in_market / (len(result["dates"]) * PARAMS["max_positions"]) \
        if result["dates"] else 0.0

    # Equal-weight buy & hold of the same universe, for contrast
    first_day, last_day = result["dates"][0], result["dates"][-1]
    rets = []
    for series in universe.values():
        idx = series["idx"]
        if first_day not in idx or last_day not in idx:
            continue
        rets.append(series["rows"][idx[last_day]]["close"]
                    / series["rows"][idx[first_day]]["close"] - 1)
    bh = statistics.mean(rets) if rets else 0.0

    return {
        "start": first_day,
        "end": last_day,
        "years": round(years, 2),
        "capital": capital,
        "final_equity": round(final, 2),
        "total_return_pct": round((final / capital - 1) * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "drawdown_trough": worst_dd_at,
        "sharpe": round(sharpe, 2),
        "trades": len(trades),
        "win_rate_pct": round(win_rate * 100, 1),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": (round(profit_factor, 2) if profit_factor != float("inf")
                          else None),
        "expectancy_per_trade": round(expectancy, 2),
        "avg_r": round(statistics.mean([t["r_multiple"] for t in trades]), 2) if trades else 0.0,
        "avg_bars_held": round(bars_in_market / len(trades), 1) if trades else 0.0,
        "total_costs": round(sum(t["costs"] for t in trades), 2),
        "exposure_pct": round(exposure * 100, 1),
        "buy_and_hold_return_pct": round(bh * 100, 2),
        "by_symbol": {k: {"trades": v["trades"],
                          "net": round(v["net"], 2),
                          "win_rate": round(v["wins"] / v["trades"] * 100, 1)}
                      for k, v in sorted(by_symbol.items())},
    }


# --------------------------------------------------------------------------
# Outputs
# --------------------------------------------------------------------------

def write_csv_outputs(out_dir: str, trades: list[dict],
                      equity: list[tuple[str, float]]) -> None:
    os.makedirs(out_dir, exist_ok=True)
    if trades:
        with open(os.path.join(out_dir, "backtest-trades.csv"), "w", newline="",
                  encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(trades[0].keys()))
            writer.writeheader()
            writer.writerows(trades)
    with open(os.path.join(out_dir, "backtest-equity.csv"), "w", newline="",
              encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date", "equity"])
        for day, value in equity:
            writer.writerow([day, round(value, 2)])


def latest_signals(universe: dict[str, dict], params: dict) -> list[dict]:
    """Signals on the most recent bar of each series.

    This is what a screener would show you tonight. It is not a recommendation
    and it is not a forecast: the backtest above is the evidence about whether
    signals of this shape have paid, and on this data it says barely.
    """
    out = []
    for symbol, series in universe.items():
        i = len(series["rows"]) - 1
        r, fast, slow = series["rsi"][i], series["sma_fast"][i], series["sma_slow"][i]
        a, close = series["atr"][i], series["closes"][i]
        if None in (r, fast, slow, a) or a <= 0:
            continue
        in_uptrend = close > slow and fast > slow
        out.append({
            "symbol": symbol,
            "date": series["rows"][i]["date"],
            "close": round(close, 2),
            "rsi2": round(r, 1),
            "in_uptrend": in_uptrend,
            "signal": in_uptrend and r <= params["rsi_entry"],
            "atr": round(a, 2),
            "stop_if_entered": round(close - params["stop_atr"] * a, 2),
            "target_if_entered": round(close + params["target_atr"] * a, 2),
        })
    return out


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=os.path.join(root, "data"))
    ap.add_argument("--out", default=os.path.join(root, "reports", "trading"))
    ap.add_argument("--capital", type=float, default=500_000.0)
    ap.add_argument("--risk", type=float, default=0.01)
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--signals", action="store_true",
                    help="print entry signals on the latest bar of each series")
    args = ap.parse_args()

    params = dict(PARAMS)
    params["risk_per_trade"] = args.risk

    print(f"Loading bars from {args.data}")
    universe = load_universe(args.data)
    if not universe:
        print("No usable CSVs found. Run tools/make_sample_data.py first.",
              file=sys.stderr)
        return 1
    print(f"  {len(universe)} symbols: {', '.join(universe)}")

    print("Running backtest...")
    result = backtest(universe, args.capital, params)
    metrics = compute_metrics(result, args.capital, universe)

    write_csv_outputs(args.out, result["trades"], result["equity"])
    with open(os.path.join(args.out, "backtest-metrics.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"params": params, "costs": COSTS, "metrics": metrics}, fh, indent=2)

    print(f"  trades            {metrics['trades']}")
    print(f"  final equity      {metrics['final_equity']:,.0f} "
          f"({metrics['total_return_pct']:+.1f}%)")
    print(f"  CAGR              {metrics['cagr_pct']:+.2f}%")
    print(f"  max drawdown      {metrics['max_drawdown_pct']:.2f}%")
    print(f"  win rate          {metrics['win_rate_pct']:.1f}%")
    print(f"  avg R             {metrics['avg_r']:+.2f}")
    print(f"  costs paid        {metrics['total_costs']:,.0f}")
    print(f"  buy & hold        {metrics['buy_and_hold_return_pct']:+.2f}%")

    if args.signals:
        rows = latest_signals(universe, params)
        print("\nSignals on the latest bar (not advice, not a forecast):")
        print(f"  {'SYMBOL':8s} {'DATE':12s} {'CLOSE':>9s} {'RSI2':>6s} "
              f"{'TREND':>7s}  ENTRY?")
        for row in rows:
            print(f"  {row['symbol']:8s} {row['date']:12s} {row['close']:9.2f} "
                  f"{row['rsi2']:6.1f} {'up' if row['in_uptrend'] else 'down':>7s}  "
                  f"{'YES  stop %.2f / target %.2f' % (row['stop_if_entered'], row['target_if_entered']) if row['signal'] else 'no'}")
        if not any(r["signal"] for r in rows):
            print("  no entry signals on the latest bar")

    if not args.no_pdf:
        try:
            from build_backtest_report import build_pdf
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from build_backtest_report import build_pdf
        path = build_pdf(os.path.join(args.out, "swing-strategy-backtest.pdf"),
                         metrics, result["trades"], result["equity"], params,
                         synthetic=_looks_synthetic(args.data))
        print(f"  report            {path}")

    return 0


def _looks_synthetic(data_dir: str) -> bool:
    for name in os.listdir(data_dir):
        if name.lower().endswith(".csv"):
            with open(os.path.join(data_dir, name), encoding="utf-8") as fh:
                if "SYNTHETIC" in fh.read(600).upper():
                    return True
    return not any(os.path.exists(os.path.join(data_dir, f"{s}.csv"))
                   for s in ("RELIANCE", "TCS", "INFY", "HDFCBANK"))


if __name__ == "__main__":
    raise SystemExit(main())
