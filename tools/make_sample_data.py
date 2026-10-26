#!/usr/bin/env python3
"""Generate SYNTHETIC daily OHLCV data so the trade engine can be demonstrated.

THIS IS NOT MARKET DATA. No price here corresponds to any real security. The
series are simulated with a regime-switching random walk so that the engine has
something realistic in shape (trends, drawdowns, fat tails, volatility
clustering) to chew on. Replace these files with real NSE/BSE daily bars before
drawing any conclusion about the strategy.

Real data, free and legal, comes from:
  * NSE bhavcopy archives  -> https://www.nseindia.com/all-reports
  * Your broker's historical data export (Zerodha Kite, Upstox, etc.)
  * Yahoo Finance CSV download per symbol

Expected CSV columns (header required, order irrelevant):
    date,open,high,low,close,volume
    date must be YYYY-MM-DD.

Usage:
    python3 tools/make_sample_data.py [output_dir]
"""

from __future__ import annotations

import csv
import math
import os
import random
import sys
from datetime import date, timedelta

# symbol -> (seed, start_price, annual drift, annual vol, trend persistence)
UNIVERSE = {
    "ALPHA": (11, 480.0, 0.16, 0.30, 0.985),
    "BRAVO": (23, 1220.0, 0.11, 0.24, 0.990),
    "CHARLIE": (37, 96.0, 0.20, 0.42, 0.980),
    "DELTA": (41, 2450.0, 0.06, 0.20, 0.993),
    "ECHO": (53, 310.0, 0.13, 0.34, 0.986),
    "FOXTROT": (67, 745.0, 0.02, 0.28, 0.988),
}

START = date(2017, 1, 2)
END = date(2025, 9, 30)
TRADING_DAYS_PER_YEAR = 252


def trading_days(start: date, end: date) -> list[date]:
    """Weekdays only. Real calendars also skip exchange holidays; a handful of
    missing days does not change the shape of a simulation."""
    days, d = [], start
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def simulate(symbol: str, seed: int, start_price: float, drift: float,
             vol: float, persistence: float, days: list[date]) -> list[dict]:
    rng = random.Random(seed)
    dt = 1.0 / TRADING_DAYS_PER_YEAR
    daily_vol = vol * math.sqrt(dt)

    # Slowly-moving expected return: creates multi-month trends and the
    # occasional long flat/declining stretch, like a real equity series.
    regime = 0.0
    price = start_price
    rows = []

    for d in days:
        regime = persistence * regime + (1.0 - persistence) * rng.gauss(0.0, 1.0) * 2.5

        # Student-t style fat tail: blend of a normal draw and a rare shock.
        shock = rng.gauss(0.0, 1.0)
        if rng.random() < 0.012:
            shock *= rng.uniform(2.5, 5.0)

        # Mild volatility clustering: vol expands after large moves.
        vol_mult = 1.0 + min(1.8, abs(regime) * 0.35)

        ret = (drift + regime * 0.55) * dt + daily_vol * vol_mult * shock
        ret = max(ret, -0.28)  # no single-day collapse beyond circuit-ish limits

        prev_close = price
        price = prev_close * math.exp(ret)

        spread = abs(rng.gauss(0.0, daily_vol * 0.65)) + 0.002
        open_px = prev_close * math.exp(rng.gauss(0.0, daily_vol * 0.30))
        high_px = max(open_px, price) * (1.0 + spread)
        low_px = min(open_px, price) * (1.0 - spread)

        base_vol = 900_000 * (start_price / max(price, 1.0)) ** 0.5
        volume = int(base_vol * math.exp(rng.gauss(0.0, 0.45)) * (1.0 + abs(ret) * 12))

        rows.append({
            "date": d.isoformat(),
            "open": round(open_px, 2),
            "high": round(high_px, 2),
            "low": round(low_px, 2),
            "close": round(price, 2),
            "volume": max(volume, 10_000),
        })

    return rows


def write_csv(path: str, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["date", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(out_dir, exist_ok=True)
    days = trading_days(START, END)

    for symbol, (seed, px, drift, vol, pers) in UNIVERSE.items():
        rows = simulate(symbol, seed, px, drift, vol, pers, days)
        write_csv(os.path.join(out_dir, f"{symbol}.csv"), rows)
        print(f"{symbol:8s} {len(rows):5d} bars  "
              f"{rows[0]['close']:9.2f} -> {rows[-1]['close']:9.2f}  -> {symbol}.csv")

    print(f"\n{len(UNIVERSE)} synthetic series written to {out_dir}/")
    print("SYNTHETIC DATA - simulated, not real market prices.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
