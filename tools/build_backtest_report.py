#!/usr/bin/env python3
"""Render the backtest results as a typeset PDF report.

Called by tools/trade_engine.py, but can be run standalone against the JSON/CSV
artefacts the engine writes:

    python3 tools/build_backtest_report.py [reports/trading]

Requirements: reportlab, plus DejaVu Sans at /usr/share/fonts/truetype/dejavu.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, KeepTogether, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)

# --------------------------------------------------------------------------- #
# Fonts and palette
# --------------------------------------------------------------------------- #

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
pdfmetrics.registerFont(TTFont("Body", str(FONT_DIR / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("Body-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold",
                              italic="Body", boldItalic="Body-Bold")

INK = colors.HexColor("#16212B")
NAVY = colors.HexColor("#132A3E")
SLATE = colors.HexColor("#5A6B7B")
RULE = colors.HexColor("#D8DEE5")
ZEBRA = colors.HexColor("#F5F7F9")
ACCENT = colors.HexColor("#0E7C86")
PAPER_TINT = colors.HexColor("#F2F6F8")
GAIN = colors.HexColor("#1B7F5A")
LOSS = colors.HexColor("#A93226")
AMBER = colors.HexColor("#9A6A05")
AMBER_TINT = colors.HexColor("#FBF1DA")

REPORT_TITLE = "Swing Strategy Backtest"
REPORT_SUBTITLE = "Trend Pullback \u2014 rules, Indian costs, and the evidence"
REPORT_DATE = "26 October 2026"
DOC_VERSION = "1.0"

CONTENT_W = A4[0] - 40 * mm

# --------------------------------------------------------------------------- #
# Styles
# --------------------------------------------------------------------------- #

def style(name, **kw):
    base = dict(fontName="Body", fontSize=9.5, leading=14, textColor=INK,
                alignment=TA_LEFT, spaceBefore=0, spaceAfter=0)
    base.update(kw)
    return ParagraphStyle(name, **base)


S = {
    "title": style("title", fontName="Body-Bold", fontSize=24, leading=28,
                   textColor=colors.white),
    "kicker": style("kicker", fontName="Body-Bold", fontSize=7.4, leading=10,
                    textColor=colors.HexColor("#8FB3C4")),
    "subtitle": style("subtitle", fontSize=10.2, leading=14,
                      textColor=colors.HexColor("#B9CBD8")),
    "hero_meta": style("hero_meta", fontSize=8.2, leading=12,
                       textColor=colors.HexColor("#C9D8E2")),
    "h2": style("h2", fontName="Body-Bold", fontSize=12.5, leading=16, textColor=NAVY),
    "h3": style("h3", fontName="Body-Bold", fontSize=9.4, leading=13, textColor=NAVY),
    "body": style("body", fontSize=9.4, leading=14.2),
    "body_small": style("body_small", fontSize=8.5, leading=13, textColor=SLATE),
    "meta_key": style("meta_key", fontName="Body-Bold", fontSize=7.4, leading=11,
                      textColor=SLATE),
    "meta_val": style("meta_val", fontSize=8.8, leading=12.5),
    "kpi_value": style("kpi_value", fontName="Body-Bold", fontSize=16.5, leading=19,
                       textColor=NAVY),
    "kpi_label": style("kpi_label", fontSize=7.4, leading=10, textColor=SLATE),
    "th": style("th", fontName="Body-Bold", fontSize=7.6, leading=10, textColor=colors.white),
    "th_right": style("th_right", fontName="Body-Bold", fontSize=7.6, leading=10,
                      textColor=colors.white, alignment=TA_RIGHT),
    "cell": style("cell", fontSize=8.8, leading=12),
    "cell_bold": style("cell_bold", fontName="Body-Bold", fontSize=8.8, leading=12),
    "cell_right": style("cell_right", fontSize=8.8, leading=12, alignment=TA_RIGHT),
    "cell_right_bold": style("cell_right_bold", fontName="Body-Bold", fontSize=8.8,
                             leading=12, alignment=TA_RIGHT),
    "cell_small": style("cell_small", fontSize=8.0, leading=11.4, textColor=SLATE),
    "cell_tiny": style("cell_tiny", fontSize=7.4, leading=10.4, textColor=SLATE),
    "cell_mono": style("cell_mono", fontName="Body", fontSize=7.6, leading=10.4),
    "note": style("note", fontSize=8.5, leading=13.2, textColor=colors.HexColor("#3D4E5C")),
    "note_bold": style("note_bold", fontName="Body-Bold", fontSize=8.6, leading=13.2,
                       textColor=NAVY),
    "bullet": style("bullet", fontSize=8.7, leading=13.6,
                    textColor=colors.HexColor("#3D4E5C"), leftIndent=11,
                    firstLineIndent=-11, bulletIndent=1, spaceAfter=2.8 * mm),
    "footnote": style("footnote", fontSize=7.4, leading=10.4, textColor=SLATE),
    "action_num": style("action_num", fontName="Body-Bold", fontSize=12.5, leading=15,
                        textColor=ACCENT, alignment=TA_RIGHT),
    "action_title": style("action_title", fontName="Body-Bold", fontSize=9.8, leading=13,
                          textColor=NAVY),
}

# --------------------------------------------------------------------------- #
# Flowables
# --------------------------------------------------------------------------- #

class Rule(Flowable):
    def __init__(self, width=CONTENT_W, thickness=0.6, color=RULE,
                 space_before=0, space_after=0):
        super().__init__()
        self.w, self.t, self.c = width, thickness, color
        self.sb, self.sa = space_before, space_after
        self.height = thickness + self.sb + self.sa

    def draw(self):
        self.canv.setStrokeColor(self.c)
        self.canv.setLineWidth(self.t)
        self.canv.line(0, self.sa + self.t / 2, self.w, self.sa + self.t / 2)


class SectionHeading(Flowable):
    def __init__(self, number, title, width=CONTENT_W):
        super().__init__()
        self.number, self.title, self.w = number, title, width
        self.height = 17

    def draw(self):
        c = self.canv
        c.setFillColor(ACCENT)
        c.rect(0, 10.5, 2.4, 6.5, stroke=0, fill=1)
        c.setFillColor(NAVY)
        c.setFont("Body-Bold", 12)
        label = f"{self.number}.  {self.title}" if self.number else self.title
        c.drawString(8, 10.5, label)


class EquityChart(Flowable):
    """Equity curve with an underwater (drawdown) band beneath it."""

    def __init__(self, equity, width=CONTENT_W, height=62 * mm):
        super().__init__()
        self.equity = equity
        # NB: reportlab reads self.width/self.height to reserve space in the
        # frame. Aliasing these to self.w/self.h silently reserves zero height
        # and the flowable then draws over whatever precedes it.
        self.width, self.height = width, height
        self.w, self.h = width, height

    def draw(self):
        c = self.canv
        if len(self.equity) < 2:
            return

        # Layout, measured from the bottom of the declared box upward.
        label_h = 9.0
        gap = 4.0
        dd_h = self.h * 0.28
        eq_h = self.h - label_h * 2 - gap - dd_h
        dd_y0 = label_h
        eq_y0 = dd_y0 + dd_h + gap
        pad_l, pad_r = 13 * mm, 15 * mm
        plot_w = self.w - pad_l - pad_r

        values = [v for _, v in self.equity]
        base = values[0]
        norm = [v / base * 100.0 for v in values]
        lo, hi = min(norm), max(norm)
        span = max(hi - lo, 1e-6)
        lo -= span * 0.08
        hi += span * 0.08

        def xy(i, v):
            return (pad_l + plot_w * (i / (len(norm) - 1)),
                    eq_y0 + (v - lo) / (hi - lo) * eq_h)

        # horizontal gridlines with axis labels
        c.setFont("Body", 6.0)
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            val = lo + (hi - lo) * frac
            _, y = xy(0, val)
            c.setStrokeColor(colors.HexColor("#E7ECF0"))
            c.setLineWidth(0.4)
            c.line(pad_l, y, pad_l + plot_w, y)
            c.setFillColor(SLATE)
            c.drawRightString(pad_l - 2, y - 2, f"{val:.0f}")

        # 100 reference line
        _, y100 = xy(0, 100.0)
        c.setStrokeColor(colors.HexColor("#B0BCC6"))
        c.setLineWidth(0.6)
        c.setDash(2, 2)
        c.line(pad_l, y100, pad_l + plot_w, y100)
        c.setDash()

        # equity line
        c.setStrokeColor(ACCENT)
        c.setLineWidth(1.1)
        path = c.beginPath()
        path.moveTo(*xy(0, norm[0]))
        for i in range(1, len(norm)):
            path.lineTo(*xy(i, norm[i]))
        c.drawPath(path)

        # underwater band
        peak, dds = values[0], []
        for v in values:
            peak = max(peak, v)
            dds.append(min(0.0, (v - peak) / peak * 100.0))
        worst = min(dds) if dds else 0.0
        scale = dd_h / abs(worst) if worst < 0 else 0.0
        bar_w = max(plot_w / len(dds), 0.7)
        c.setFillColor(colors.HexColor("#DCE8EA"))
        for i, dd in enumerate(dds):
            x = pad_l + plot_w * (i / (len(dds) - 1))
            c.rect(x, dd_y0, bar_w, -dd * scale, stroke=0, fill=1)
        c.setStrokeColor(colors.HexColor("#C3D3D6"))
        c.setLineWidth(0.5)
        c.line(pad_l, dd_y0, pad_l + plot_w, dd_y0)

        # captions
        c.setFont("Body", 6.2)
        c.setFillColor(SLATE)
        c.drawString(pad_l, 1.0, f"Underwater: distance below the running peak "
                                 f"(worst {worst:.1f}%)")
        c.drawRightString(pad_l + plot_w, 1.0,
                          f"Equity indexed to 100 at start \u00b7 ends {norm[-1]:.0f}")
        c.drawString(pad_l, eq_y0 + eq_h + 3.0, self.equity[0][0])
        c.drawRightString(pad_l + plot_w, eq_y0 + eq_h + 3.0, self.equity[-1][0])


class RHistogram(Flowable):
    """Distribution of per-trade R-multiples."""

    BINS = [("<-1R", -99, -1), ("-1 to 0", -1, 0), ("0 to 1", 0, 1),
            ("1 to 2", 1, 2), ("2 to 3", 2, 3), (">3R", 3, 99)]

    def __init__(self, trades, width=CONTENT_W, height=48 * mm):
        super().__init__()
        self.trades = trades
        self.width, self.height = width, height
        self.w, self.h = width, height

    def draw(self):
        c = self.canv
        counts = []
        for _, lo, hi in self.BINS:
            counts.append(sum(1 for t in self.trades if lo <= t["r_multiple"] < hi))
        peak = max(counts) or 1
        pad_l, pad_b, pad_t = 2 * mm, 9 * mm, 6 * mm
        plot_w = self.w - pad_l - 4 * mm
        bar_w = plot_w / len(self.BINS) * 0.58
        gap = plot_w / len(self.BINS)

        for i, ((label, lo, _hi), n) in enumerate(zip(self.BINS, counts)):
            hgt = (n / peak) * (self.h - pad_b - pad_t)
            x = pad_l + gap * i + (gap - bar_w) / 2
            col = GAIN if lo >= 0 else LOSS
            c.setFillColor(col)
            c.rect(x, pad_b, bar_w, max(hgt, 0.5), stroke=0, fill=1)
            c.setFillColor(SLATE)
            c.setFont("Body", 6.4)
            c.drawCentredString(x + bar_w / 2, pad_b - 6, label)
            c.setFillColor(INK)
            c.setFont("Body-Bold", 6.8)
            c.drawCentredString(x + bar_w / 2, pad_b + hgt + 2.5, str(n))

        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        c.line(pad_l, pad_b, pad_l + plot_w, pad_b)
        c.setFont("Body", 6.2)
        c.setFillColor(SLATE)
        c.drawRightString(self.w, self.h - 3,
                          "R = profit as a multiple of the amount risked on that trade")
        c.drawString(pad_l, self.h - 3, "trades per bucket")


# --------------------------------------------------------------------------- #
# Page furniture
# --------------------------------------------------------------------------- #

def page_furniture(canv, doc):
    canv.saveState()
    width, height = A4
    page_no = canv.getPageNumber()
    total = getattr(doc, "_total_pages", None)

    if page_no == 1:
        band_h = 50 * mm
        canv.setFillColor(NAVY)
        canv.rect(0, height - band_h, width, band_h, stroke=0, fill=1)
        canv.setFillColor(ACCENT)
        canv.rect(0, height - band_h, width, 2.2, stroke=0, fill=1)
        left = 20 * mm
        canv.setFillColor(colors.HexColor("#8FB3C4"))
        canv.setFont("Body-Bold", 7.2)
        canv.drawString(left, height - 15 * mm, "SYSTEMATIC TRADING  \u00b7  BACKTEST REVIEW")
        canv.setFillColor(colors.white)
        canv.setFont("Body-Bold", 23)
        canv.drawString(left, height - 26.5 * mm, REPORT_TITLE)
        canv.setFillColor(colors.HexColor("#B9CBD8"))
        canv.setFont("Body", 9.8)
        canv.drawString(left, height - 34.5 * mm, REPORT_SUBTITLE)
        canv.setFillColor(colors.HexColor("#C9D8E2"))
        canv.setFont("Body", 8.0)
        canv.drawString(left, height - 43 * mm,
                        f"Generated {REPORT_DATE}   \u00b7   Version {DOC_VERSION}   "
                        f"\u00b7   tools/trade_engine.py")

        bw, bh = 34 * mm, 6.6 * mm
        bx, by = width - 20 * mm - bw, height - 44.6 * mm
        canv.setFillColor(AMBER)
        canv.roundRect(bx, by, bw, bh, 3, stroke=0, fill=1)
        canv.setFillColor(colors.white)
        canv.setFont("Body-Bold", 6.8)
        canv.drawCentredString(bx + bw / 2, by + 2.3 * mm, "SIMULATED")
    else:
        band_h = 17 * mm
        canv.setFillColor(NAVY)
        canv.rect(0, height - band_h, width, band_h, stroke=0, fill=1)
        canv.setFillColor(ACCENT)
        canv.rect(0, height - band_h, width, 1.6, stroke=0, fill=1)
        canv.setFillColor(colors.white)
        canv.setFont("Body-Bold", 9.4)
        canv.drawString(20 * mm, height - 11 * mm, REPORT_TITLE)
        canv.setFillColor(colors.HexColor("#B9CBD8"))
        canv.setFont("Body", 7.6)
        canv.drawRightString(width - 20 * mm, height - 11 * mm,
                             f"Simulation only \u00b7 {REPORT_DATE}")

    canv.setStrokeColor(RULE)
    canv.setLineWidth(0.6)
    canv.line(20 * mm, 16 * mm, width - 20 * mm, 16 * mm)
    canv.setFont("Body", 7.2)
    canv.setFillColor(SLATE)
    canv.drawString(20 * mm, 11.5 * mm,
                    "Simulation on synthetic data. Not investment advice, not a "
                    "statement of future returns.")
    right = f"Page {page_no} of {total}" if total else f"Page {page_no}"
    canv.drawRightString(width - 20 * mm, 11.5 * mm, right)
    canv.restoreState()


class NumberedCanvas:
    """Deferred canvas that knows the total page count."""

    def __new__(cls, *args, **kwargs):
        from reportlab.pdfgen import canvas as _canvas

        class _Canvas(_canvas.Canvas):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                self._saved = []

            def showPage(self):
                self._saved.append(dict(self.__dict__))
                self._startPage()

            def save(self):
                total = len(self._saved)
                for state in self._saved:
                    self.__dict__.update(state)
                    self._doc._total_pages = total
                    page_furniture(self, self._doc)
                    super().showPage()
                super().save()

        return _Canvas(*args, **kwargs)


# --------------------------------------------------------------------------- #
# Content blocks
# --------------------------------------------------------------------------- #

def fmt_inr(value: float) -> str:
    return f"{value:,.0f}"


def verdict(metrics: dict) -> tuple[str, colors.Color, colors.Color, str]:
    """A blunt read on whether the strategy earned a second look.

    Deliberately conservative: beating zero is not an edge, and a strategy that
    is merely less bad than buy-and-hold still has to justify the effort of
    running it and the tax bill of trading it.
    """
    cagr = metrics["cagr_pct"]
    pf = metrics["profit_factor"] or 0.0
    bh = metrics["buy_and_hold_return_pct"]
    if cagr <= 0:
        return ("Rejected by its own numbers", LOSS, colors.HexColor("#F7E3E1"),
                f"The rules lost money after costs. Discard this variant rather than "
                f"tuning it until the curve looks good \u2014 that is how backtests "
                f"become expensive fiction.")
    if pf < 1.2 or cagr < 8:
        return ("Not yet an edge", AMBER, AMBER_TINT,
                f"Positive, but thin: a profit factor of {pf:.2f} and {cagr:+.1f}% a "
                f"year would not survive a bad quarter, a slippage assumption or a "
                f"tax bill. Treat this as a hypothesis, not a strategy.")
    if bh > 0 and cagr < bh / max(metrics["years"], 1) * 0.5:
        return ("Beaten by doing nothing", AMBER, AMBER_TINT,
                f"The system made money but far less than simply holding the same "
                f"universe ({bh:+.0f}% versus {metrics['total_return_pct']:+.1f}%), "
                f"while still demanding attention every week. Effort is a cost too.")
    return ("Worth verifying on real data", GAIN, colors.HexColor("#E5F3EC"),
            "The edge is large enough to be worth a harder test on real prices with "
            "slippage added. That is a reason to test more, not a reason to trade it.")


def kpi_strip(metrics: dict):
    items = [
        (f"{metrics['cagr_pct']:+.1f}%", "CAGR after costs",
         GAIN if metrics["cagr_pct"] >= 0 else LOSS),
        (f"{metrics['max_drawdown_pct']:.1f}%", "max drawdown", LOSS),
        (f"{metrics['trades']}", "round trips", NAVY),
        (f"{metrics['avg_r']:+.2f}R", "average trade", NAVY),
    ]
    cells = []
    for value, label, col in items:
        inner = Table(
            [[Paragraph(f'<font color="{col.hexval()}">{value}</font>', S["kpi_value"])],
             [Paragraph(label, S["kpi_label"])]],
            colWidths=[(CONTENT_W / 4) - 12 * mm],
        )
        inner.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        cells.append(inner)

    t = Table([cells], colWidths=[CONTENT_W / 4] * 4)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PAPER_TINT),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#DCE5EB")),
        ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#DCE5EB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def metadata_block(metrics: dict, synthetic: bool):
    rows = [
        [Paragraph("TEST WINDOW", S["meta_key"]),
         Paragraph(f"{metrics['start']} to {metrics['end']} "
                   f"({metrics['years']:.1f} years)", S["meta_val"]),
         Paragraph("STARTING CAPITAL", S["meta_key"]),
         Paragraph(f"\u20b9{fmt_inr(metrics['capital'])}", S["meta_val"])],
        [Paragraph("UNIVERSE", S["meta_key"]),
         Paragraph(f"{len(metrics['by_symbol'])} symbols, daily bars", S["meta_val"]),
         Paragraph("COSTS", S["meta_key"]),
         Paragraph(f"\u20b9{fmt_inr(metrics['total_costs'])} paid", S["meta_val"])],
        [Paragraph("DATA", S["meta_key"]),
         Paragraph("Synthetic simulation \u2014 not market prices" if synthetic
                   else "Supplied historical bars", S["meta_val"]),
         Paragraph("STATUS", S["meta_key"]),
         Paragraph("Backtest \u00b7 no orders were placed", S["meta_val"])],
    ]
    col = CONTENT_W / 4
    t = Table(rows, colWidths=[col * 0.82, col * 1.18, col * 0.92, col * 1.08])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 3.4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.4),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#E7ECF0")),
    ]))
    return t


def warning_box(synthetic: bool):
    title = ("Read this before the numbers" if not synthetic
             else "The data in this report is simulated")
    body = (
        "Every price in this run comes from tools/make_sample_data.py, a random-walk "
        "generator. The results describe how this strategy behaves against a "
        "plausible-looking series, and nothing at all about real NSE or BSE "
        "securities. Replace data/*.csv with real daily bars and rerun before "
        "treating any figure here as evidence."
        if synthetic else
        "These results come from historical bars. Historical performance is not "
        "predictive, the universe was chosen with hindsight, and a single sample "
        "period cannot rule out luck."
    )
    inner = [
        [Paragraph(title, S["note_bold"])],
        [Paragraph(body, S["note"])],
    ]
    t = Table(inner, colWidths=[CONTENT_W - 10 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AMBER_TINT),
        ("LINEBEFORE", (0, 0), (0, -1), 2.4, AMBER),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
    ]))
    return t


def how_to_read_block():
    items = [
        ("What this is",
         "One fully specified long-only swing strategy, run across a fixed universe "
         "with Indian delivery costs charged per leg, and judged on what it did "
         "rather than what it promised."),
        ("What it is not",
         "Not a signal service, not a forecast, and not connected to any broker. "
         "No order was placed to produce it. A backtest is a record of the past "
         "dressed in a suit."),
        ("The one number to look at",
         "Average R \u2014 profit per trade as a multiple of what was risked. It "
         "already includes costs, so it is the closest thing here to an edge."),
    ]
    rows = [[Paragraph(k.upper(), S["meta_key"]), Paragraph(v, S["meta_val"])]
            for k, v in items]
    t = Table(rows, colWidths=[36 * mm, CONTENT_W - 36 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), PAPER_TINT),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#DCE5EB")),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#E1E8ED")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5.5),
    ]))
    return t


def rules_table(params: dict):
    head = [Paragraph("ELEMENT", S["th"]), Paragraph("RULE", S["th"]),
            Paragraph("WHY IT IS THERE", S["th"])]
    rules = [
        ("Regime filter",
         f"close > SMA{params['sma_slow']} and SMA{params['sma_fast']} > "
         f"SMA{params['sma_slow']}",
         "Only buy pullbacks inside an uptrend. Most losing swing trades are "
         "pullbacks in downtrends."),
        ("Entry trigger", f"RSI({params['rsi_period']}) \u2264 {params['rsi_entry']:g}",
         "A short, sharp washout \u2014 not a slow bleed \u2014 is what a healthy "
         "pullback looks like."),
        ("Fill", "next bar's open",
         "Removes lookahead. A signal you cannot act on is not a signal."),
        ("Stop", f"entry \u2212 {params['stop_atr']:g} \u00d7 ATR({params['atr_period']})",
         "Volatility-scaled: a wide, quiet stock gets room; a jumpy one gets a "
         "tighter leash."),
        ("Target", f"entry + {params['target_atr']:g} \u00d7 ATR({params['atr_period']})",
         "A fixed, pre-committed exit. The reward:risk ratio is known before entry."),
        ("Exits", f"stop, target, RSI({params['rsi_period']}) \u2265 "
                  f"{params['rsi_exit']:g}, close < SMA{params['sma_slow']}, or "
                  f"{params['max_hold_bars']} bars",
         "A trade that goes nowhere costs opportunity and attention; time is an exit."),
        ("Sizing", f"risk {params['risk_per_trade'] * 100:.1f}% of equity per trade, "
                   f"capped at {params['max_position_pct'] * 100:.0f}% of equity",
         "Size follows the stop distance, not conviction. This is what keeps "
         "ruin off the table."),
        ("Portfolio", f"{params['max_positions']} concurrent positions, one per symbol",
         "Correlated entries in a falling market is one big position wearing four hats."),
    ]
    rows = [head] + [[Paragraph(f"<b>{a}</b>", S["cell"]), Paragraph(b, S["cell"]),
                      Paragraph(c, S["cell_small"])] for a, b, c in rules]
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("TOPPADDING", (0, 1), (-1, -1), 4.6),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4.6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, colors.HexColor("#E3E8ED")),
        ("BOX", (0, 1), (-1, -1), 0.6, colors.HexColor("#DCE5EB")),
    ]
    for i in range(1, len(rows)):
        if i % 2 == 0:
            cmds.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    t = Table(rows, colWidths=[30 * mm, 54 * mm, CONTENT_W - 84 * mm], repeatRows=1)
    t.setStyle(TableStyle(cmds))
    return t


def cost_table():
    head = [Paragraph("CHARGE", S["th"]), Paragraph("RATE", S["th"]),
            Paragraph("SIDE", S["th"])]
    rows = [
        ("Securities transaction tax", "0.1%", "buy and sell"),
        ("Exchange transaction charge (NSE)", "0.00325%", "buy and sell"),
        ("SEBI turnover fee", "0.0001%", "buy and sell"),
        ("Stamp duty", "0.015%", "buy only"),
        ("GST on brokerage + charges", "18%", "buy and sell"),
        ("DP charge (per sell, per scrip)", "\u20b915.93", "sell only"),
        ("Brokerage (discount broker, delivery)", "\u20b90", "buy and sell"),
    ]
    body = [[Paragraph(f"<b>{a}</b>", S["cell"]), Paragraph(b, S["cell"]),
             Paragraph(c, S["cell_small"])] for a, b, c in rows]
    t = Table([head] + body, colWidths=[CONTENT_W * 0.46, CONTENT_W * 0.20,
                                        CONTENT_W * 0.34], repeatRows=1)
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, colors.HexColor("#E3E8ED")),
        ("BOX", (0, 1), (-1, -1), 0.6, colors.HexColor("#DCE5EB")),
    ]
    for i in range(1, len(body) + 1):
        if i % 2 == 0:
            cmds.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    t.setStyle(TableStyle(cmds))
    return t


def metrics_table(metrics: dict):
    def pct(v):
        col = GAIN if v >= 0 else LOSS
        return f'<font color="{col.hexval()}">{v:+.2f}%</font>'

    def money(v):
        col = GAIN if v >= 0 else LOSS
        return f'<font color="{col.hexval()}">\u20b9{v:,.0f}</font>'

    pairs = [
        ("Total return after costs", pct(metrics["total_return_pct"])),
        ("CAGR", pct(metrics["cagr_pct"])),
        ("Max drawdown", pct(metrics["max_drawdown_pct"])),
        ("Sharpe ratio (daily, annualised)", f"{metrics['sharpe']:+.2f}"),
        ("Round trips", f"{metrics['trades']}"),
        ("Win rate", f"{metrics['win_rate_pct']:.1f}%"),
        ("Profit factor", f"{metrics['profit_factor']}" if metrics["profit_factor"]
         else "n/a"),
        ("Expectancy per trade", money(metrics["expectancy_per_trade"])),
        ("Average trade", f"{metrics['avg_r']:+.2f}R"),
        ("Average win / loss",
         f"\u20b9{metrics['avg_win']:,.0f} / \u20b9{metrics['avg_loss']:,.0f}"),
        ("Average holding period", f"{metrics['avg_bars_held']:.1f} bars"),
        ("Total costs paid", f"\u20b9{metrics['total_costs']:,.0f}"),
        ("Time in the market", f"{metrics['exposure_pct']:.1f}% of capacity"),
        ("Equal-weight buy and hold", pct(metrics["buy_and_hold_return_pct"])),
    ]
    half = (len(pairs) + 1) // 2
    left, right = pairs[:half], pairs[half:]
    rows = []
    for i in range(half):
        a = left[i]
        b = right[i] if i < len(right) else ("", "")
        rows.append([Paragraph(a[0], S["cell_tiny"]), Paragraph(a[1], S["cell_right_bold"]),
                     Paragraph(b[0], S["cell_tiny"]), Paragraph(b[1], S["cell_right_bold"])])
    c = CONTENT_W / 4
    t = Table(rows, colWidths=[c * 1.05, c * 0.62, c * 1.05, c * 0.62])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.2),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#E7ECF0")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#DCE5EB")),
    ]))
    return t


def symbol_table(metrics: dict, trades: list[dict]):
    head = [Paragraph("SYMBOL", S["th"]), Paragraph("TRADES", S["th_right"]),
            Paragraph("WIN RATE", S["th_right"]), Paragraph("NET P&amp;L", S["th_right"]),
            Paragraph("SHARE OF TRADES", S["th"])]
    total = len(trades) or 1
    rows = [head]
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("TOPPADDING", (0, 1), (-1, -1), 4.4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4.4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, colors.HexColor("#E3E8ED")),
        ("BOX", (0, 1), (-1, -1), 0.6, colors.HexColor("#DCE5EB")),
    ]
    for i, (sym, d) in enumerate(metrics["by_symbol"].items(), start=1):
        col = GAIN if d["net"] >= 0 else LOSS
        rows.append([
            Paragraph(f"<b>{sym}</b>", S["cell"]),
            Paragraph(str(d["trades"]), S["cell_right"]),
            Paragraph(f"{d['win_rate']:.1f}%", S["cell_right"]),
            Paragraph(f'<font color="{col.hexval()}">\u20b9{d["net"]:,.0f}</font>',
                      S["cell_right_bold"]),
            Paragraph(f"{d['trades'] / total * 100:.0f}%", S["cell_small"]),
        ])
        if i % 2 == 0:
            cmds.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    t = Table(rows, colWidths=[CONTENT_W * 0.18, CONTENT_W * 0.15, CONTENT_W * 0.17,
                               CONTENT_W * 0.26, CONTENT_W * 0.24], repeatRows=1)
    t.setStyle(TableStyle(cmds))
    return t


def exit_table(trades: list[dict]):
    head = [Paragraph("EXIT", S["th"]), Paragraph("COUNT", S["th_right"]),
            Paragraph("AVG R", S["th_right"]), Paragraph("NET P&amp;L", S["th_right"])]
    buckets: dict[str, list[dict]] = {}
    for t in trades:
        buckets.setdefault(t["exit_reason"], []).append(t)
    rows = [head]
    for reason, group in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        avg_r = sum(t["r_multiple"] for t in group) / len(group)
        net = sum(t["net_pnl"] for t in group)
        col = GAIN if net >= 0 else LOSS
        rows.append([
            Paragraph(reason.capitalize(), S["cell"]),
            Paragraph(str(len(group)), S["cell_right"]),
            Paragraph(f"{avg_r:+.2f}", S["cell_right"]),
            Paragraph(f'<font color="{col.hexval()}">\u20b9{net:,.0f}</font>',
                      S["cell_right_bold"]),
        ])
    t = Table(rows, colWidths=[CONTENT_W * 0.38, CONTENT_W * 0.16,
                               CONTENT_W * 0.20, CONTENT_W * 0.26], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("TOPPADDING", (0, 1), (-1, -1), 4.4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4.4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, colors.HexColor("#E3E8ED")),
        ("BOX", (0, 1), (-1, -1), 0.6, colors.HexColor("#DCE5EB")),
        ("INNERGRID", (0, 1), (-1, -1), 0.0, colors.white),
    ]))
    return t


def worst_trades_table(trades: list[dict], n: int = 6):
    head = [Paragraph("SYMBOL", S["th"]), Paragraph("ENTRY", S["th"]),
            Paragraph("EXIT", S["th"]), Paragraph("BARS", S["th_right"]),
            Paragraph("REASON", S["th"]), Paragraph("NET P&amp;L", S["th_right"])]
    worst = sorted(trades, key=lambda t: t["net_pnl"])[:n]
    rows = [head]
    for t in worst:
        rows.append([
            Paragraph(t["symbol"], S["cell"]),
            Paragraph(t["entry_date"], S["cell_small"]),
            Paragraph(t["exit_date"], S["cell_small"]),
            Paragraph(str(t["bars_held"]), S["cell_right"]),
            Paragraph(t["exit_reason"], S["cell_small"]),
            Paragraph(f'\u20b9{t["net_pnl"]:,.0f}', S["cell_right_bold"]),
        ])
    t = Table(rows, colWidths=[CONTENT_W * 0.16, CONTENT_W * 0.16, CONTENT_W * 0.16,
                               CONTENT_W * 0.10, CONTENT_W * 0.26, CONTENT_W * 0.16],
              repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("TOPPADDING", (0, 1), (-1, -1), 4.2),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, colors.HexColor("#E3E8ED")),
        ("BOX", (0, 1), (-1, -1), 0.6, colors.HexColor("#DCE5EB")),
    ]))
    return t


# --------------------------------------------------------------------------- #
# Story
# --------------------------------------------------------------------------- #

def build_story(metrics, trades, equity, params, synthetic):
    flow = []
    label, colour, tint, reading = verdict(metrics)
    cost_share = (metrics["total_costs"] / metrics["capital"] * 100
                  if metrics["capital"] else 0.0)

    # ---- page 1 ----
    flow.append(Spacer(1, 4 * mm))
    flow.append(Paragraph(
        f'The strategy finished the test period at '
        f'<b>\u20b9{fmt_inr(metrics["final_equity"])}</b> on \u20b9'
        f'{fmt_inr(metrics["capital"])} of starting capital, '
        f'a {metrics["total_return_pct"]:+.1f}% total return '
        f'({metrics["cagr_pct"]:+.1f}% a year) against an equal-weight buy-and-hold '
        f'of the same universe at {metrics["buy_and_hold_return_pct"]:+.1f}%.',
        S["body"]))
    flow.append(Spacer(1, 4 * mm))
    flow.append(kpi_strip(metrics))
    flow.append(Spacer(1, 4.5 * mm))
    flow.append(metadata_block(metrics, synthetic))
    flow.append(Spacer(1, 4 * mm))
    flow.append(warning_box(synthetic))
    flow.append(Spacer(1, 6 * mm))
    flow.append(how_to_read_block())
    flow.append(Spacer(1, 6 * mm))
    flow.append(SectionHeading("1", "The verdict, in one line"))
    flow.append(Spacer(1, 2 * mm))
    verdict_tbl = Table([[Paragraph(f'<font color="{colour.hexval()}"><b>{label}</b>'
                                    f'</font>', S["h3"])],
                         [Paragraph(reading, S["note"])]],
                        colWidths=[CONTENT_W])
    verdict_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), tint),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("TOPPADDING", (0, 1), (-1, 1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
    ]))
    flow.append(verdict_tbl)
    flow.append(Spacer(1, 7 * mm))
    flow.append(Paragraph(
        "The rest of this document does three things: states the rules as code "
        "(section 2), shows what they did and what it cost (sections 3 to 7), and "
        "then argues against itself (section 8). Read section 8 before deciding "
        "the earlier pages mean anything.", S["body_small"]))

    # ---- page 2 ----
    flow.append(PageBreak())
    flow.append(SectionHeading("2", "The rules under test"))
    flow.append(Spacer(1, 2 * mm))
    flow.append(Paragraph(
        "Every rule below is fixed in code before the first trade. Nothing is "
        "discretionary, which is the only way a backtest can mean anything: if you "
        "would have overridden the system in March, you did not test the system you "
        "would have traded.", S["body_small"]))
    flow.append(Spacer(1, 3.5 * mm))
    flow.append(rules_table(params))
    flow.append(Spacer(1, 8 * mm))
    flow.append(SectionHeading("3", "Equity curve and drawdown"))
    flow.append(Spacer(1, 2 * mm))
    flow.append(Paragraph(
        "The upper line is account equity, indexed to 100 at the start. The shaded "
        "band is how far the account sat below its own high-water mark. A curve you "
        "cannot look at during a drawdown is a curve you will abandon at the worst "
        "possible moment.", S["body_small"]))
    flow.append(Spacer(1, 3.5 * mm))
    flow.append(EquityChart(equity))

    # ---- page 3 ----
    flow.append(PageBreak())
    flow.append(SectionHeading("4", "Results, after Indian delivery costs"))
    flow.append(Spacer(1, 2 * mm))
    flow.append(Paragraph(
        f"Charges are modelled trade by trade \u2014 STT, exchange, SEBI, stamp duty, "
        f"GST and DP \u2014 and total \u20b9{fmt_inr(metrics['total_costs'])} across the "
        f"test, which is {cost_share:.1f}% of the starting capital. A gross-profit figure "
        f"without this deduction is fiction.", S["body_small"]))
    flow.append(Spacer(1, 3.5 * mm))
    flow.append(metrics_table(metrics))
    flow.append(Spacer(1, 8 * mm))
    flow.append(SectionHeading("5", "Cost model applied"))
    flow.append(Spacer(1, 2 * mm))
    flow.append(Paragraph(
        "Rates as charged on NSE delivery trades in 2025, applied per leg inside the "
        "backtest rather than as a flat haircut at the end.", S["body_small"]))
    flow.append(Spacer(1, 3.5 * mm))
    flow.append(cost_table())

    # ---- page 4 ----
    flow.append(PageBreak())
    flow.append(SectionHeading("6", "Shape of the trades"))
    flow.append(Spacer(1, 2 * mm))
    flow.append(Paragraph(
        "A strategy is a distribution, not an average. What matters is whether the "
        "right tail is fat enough to pay for the cluster of small losses on the left. "
        "Win rate on its own is close to meaningless.", S["body_small"]))
    flow.append(Spacer(1, 3.5 * mm))
    flow.append(RHistogram(trades))
    flow.append(Spacer(1, 8 * mm))
    flow.append(SectionHeading("7", "Where the money came from"))
    flow.append(Spacer(1, 2 * mm))
    flow.append(Paragraph(
        "Per-symbol results tell you whether one lucky name carried the whole test. "
        "If a single symbol is responsible for most of the profit, you have a "
        "one-stock bet with extra steps.", S["body_small"]))
    flow.append(Spacer(1, 3.5 * mm))
    flow.append(symbol_table(metrics, trades))
    flow.append(Spacer(1, 6 * mm))
    flow.append(KeepTogether([
        Paragraph("How positions were closed", S["h3"]),
        Spacer(1, 2.5 * mm),
        exit_table(trades),
    ]))

    # ---- page 5 ----
    flow.append(PageBreak())
    flow.append(KeepTogether([
        Paragraph("The worst trades \u2014 by design, these exist", S["h3"]),
        Spacer(1, 1.5 * mm),
        Paragraph(
            "A stop is not a guarantee. The loss column shows what each one actually "
            "cost once costs and gaps were included.", S["cell_small"]),
        Spacer(1, 2.5 * mm),
        worst_trades_table(trades),
    ]))
    flow.append(Spacer(1, 8 * mm))

    flow.append(SectionHeading("8", "What this test cannot tell you"))
    flow.append(Spacer(1, 2.5 * mm))
    caveats = [
        ("The data is not real" if synthetic else "One sample period",
         "Synthetic prices have no earnings, no circuits, no news, no illiquidity "
         "and no fat-tailed panic. Real markets are ruder than any generator, so "
         "treat every figure here as an upper bound on how the rules behave."
         if synthetic else
         "A single historical window contains one path. A neighbouring period can "
         "produce a very different curve from identical rules."),
        ("Slippage is assumed away",
         "Fills are at exact open, stop and target prices. In practice a stop in a "
         "fast market fills worse, and thin stocks move against you on entry. Budget "
         "0.1\u20130.3% per side and rerun before believing the result."),
        ("The universe was chosen with hindsight",
         "These six symbols exist because they were available, and a survivor is by "
         "definition a stock that survived. A test on today's index members is "
         "quietly a test of winners."),
        ("Circuits and halts are missing",
         "Indian equities have daily price bands. A stock locked at the lower circuit "
         "cannot be exited at any price, which turns a 1% risk into a much larger one."),
        ("Income tax is not in these numbers",
         "The backtest deducts transaction charges but not tax on the gains. Held "
         "under twelve months, profits are short-term capital gains taxed at 20%; "
         "261 round trips in 8.7 years also means 261 rows to report. A strategy "
         "must clear that hurdle too."),
        ("Overfitting is easy and invisible",
         "Six parameters were chosen by a human who could see the data. That is "
         "already a form of fitting. Walk-forward testing \u2014 parameters tuned on "
         "2017\u20132021, judged on 2022\u20132025 \u2014 is the minimum defence."),
    ]
    for title, body in caveats:
        flow.append(Paragraph(f"<b>{title}.</b> {body}", S["bullet"], bulletText="\u2013"))
    flow.append(Spacer(1, 5 * mm))
    flow.append(PageBreak())
    flow.append(SectionHeading("9", "What would earn this strategy real money"))
    flow.append(Spacer(1, 2.5 * mm))
    steps = [
        ("Replace the data", "Export real daily bars for your actual universe from "
                             "your broker or NSE bhavcopy, drop them in data/ and rerun. "
                             "Nothing above matters until this is done."),
        ("Walk forward", "Tune nothing; simply run the same fixed rules across "
                         "2017\u20132019, 2020\u20132021 and 2022\u20132025 separately. "
                         "Consistency across periods is the only credible signal."),
        ("Add friction", "Charge 0.15% slippage per side and rerun. If the edge "
                         "disappears, it was never an edge \u2014 it was a rounding error."),
        ("Paper trade for 30 signals", "Log every signal the system produces, and "
                                       "every one you were tempted to skip. Compare "
                                       "the two lists at the end. That gap is you."),
        ("Trade the smallest size that is real", "Only after the four steps above, "
                                                 "and only with an amount whose total "
                                                 "loss would change nothing in your life."),
    ]
    for i, (title, body) in enumerate(steps, start=1):
        row = Table([[Paragraph(f"{i:02d}", S["action_num"]),
                      Paragraph(f'<font color="{NAVY.hexval()}"><b>{title}</b></font>'
                                f'<br/><font size="8.5">{body}</font>', S["cell"])]],
                    colWidths=[12 * mm, CONTENT_W - 12 * mm])
        row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (0, 0), 0),
            ("RIGHTPADDING", (0, 0), (0, 0), 6),
            ("LEFTPADDING", (1, 0), (1, 0), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#E7ECF0")),
        ]))
        flow.append(row)
    flow.append(Spacer(1, 6 * mm))
    flow.append(Rule())
    flow.append(Spacer(1, 3 * mm))
    flow.append(Paragraph(
        "<b>Not investment advice.</b> This document is a software artefact: a record "
        "of what a fixed set of rules did on a dataset, produced by "
        "tools/trade_engine.py. It is not a recommendation, an offer, or a solicitation "
        "to buy or sell any security, and it does not account for your circumstances. "
        "No order was placed to produce it, and no broker connection exists in this "
        "repository. Anyone who tells you a backtest is a forecast is selling something.",
        S["footnote"]))
    flow.append(Spacer(1, 4 * mm))
    flow.append(Paragraph(
        f"Artefacts: <b>backtest-trades.csv</b> (every round trip, with R-multiples) "
        f"\u00b7 <b>backtest-equity.csv</b> (daily equity) \u00b7 "
        f"<b>backtest-metrics.json</b> (all figures above, machine-readable).",
        S["footnote"]))
    return flow


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #

def build_pdf(path, metrics, trades, equity, params, synthetic=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(
        str(path), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=40 * mm, bottomMargin=22 * mm,
        title=REPORT_TITLE,
        author="Strategy backtest",
        subject="Trend Pullback \u2014 rules-based backtest with Indian delivery costs",
        creator="tools/trade_engine.py",
        keywords="backtest, swing trading, NSE, position sizing, risk management",
    )
    first_frame = Frame(20 * mm, 22 * mm, CONTENT_W, A4[1] - 72 * mm, id="first",
                        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    later_frame = Frame(20 * mm, 22 * mm, CONTENT_W, A4[1] - 45 * mm, id="later",
                        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="first", frames=[first_frame]),
                          PageTemplate(id="later", frames=[later_frame])])
    doc.build(build_story(metrics, trades, equity, params, synthetic),
              canvasmaker=NumberedCanvas)
    return str(path)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "reports" / "trading"
    with open(out / "backtest-metrics.json", encoding="utf-8") as fh:
        blob = json.load(fh)
    trades = []
    with open(out / "backtest-trades.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            trades.append({k: (float(v) if k not in
                               ("symbol", "entry_date", "exit_date", "exit_reason")
                               else v) for k, v in row.items()})
    equity = []
    with open(out / "backtest-equity.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            equity.append((row["date"], float(row["equity"])))
    path = build_pdf(out / "swing-strategy-backtest.pdf", blob["metrics"], trades,
                     equity, blob["params"], synthetic=True)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
