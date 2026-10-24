#!/usr/bin/env python3
"""Build the Wi-Fi Signal Strength Assessment report as a typeset PDF.

Source of truth for the report content is this file; the PDF is generated:

    python3 tools/build_wifi_report.py [output.pdf]

Requirements: reportlab, plus the DejaVu Sans fonts shipped with most Linux
distributions (/usr/share/fonts/truetype/dejavu).
"""

from __future__ import annotations

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
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# --------------------------------------------------------------------------- #
# Fonts
# --------------------------------------------------------------------------- #

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
pdfmetrics.registerFont(TTFont("Body", str(FONT_DIR / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("Body-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold",
                              italic="Body", boldItalic="Body-Bold")

# --------------------------------------------------------------------------- #
# Palette
# --------------------------------------------------------------------------- #

INK = colors.HexColor("#16212B")
NAVY = colors.HexColor("#132A3E")
SLATE = colors.HexColor("#5A6B7B")
RULE = colors.HexColor("#D8DEE5")
ZEBRA = colors.HexColor("#F5F7F9")
ACCENT = colors.HexColor("#0E7C86")
PAPER_TINT = colors.HexColor("#F2F6F8")

RATINGS = {
    "Excellent": (colors.HexColor("#1B7F5A"), colors.HexColor("#E5F3EC")),
    "Good": (colors.HexColor("#1F6FA8"), colors.HexColor("#E4EEF6")),
    "Fair": (colors.HexColor("#9A6A05"), colors.HexColor("#FBF1DA")),
    "Weak": (colors.HexColor("#B45410"), colors.HexColor("#FBE9DC")),
    "Poor": (colors.HexColor("#A93226"), colors.HexColor("#F7E3E1")),
}

# --------------------------------------------------------------------------- #
# Report content
# --------------------------------------------------------------------------- #

REPORT_DATE = "24 October 2026"
DOC_VERSION = "1.0"
REPORT_TITLE = "Wi-Fi Signal Strength Assessment"
REPORT_SUBTITLE = "Residential coverage review \u2014 preliminary assessment"

METADATA = [
    ("Prepared", REPORT_DATE),
    ("Coverage area", "Four rooms, one washroom, hallway and kitchen (seven locations)"),
    ("Metric", "Received Signal Strength Indicator (RSSI), in dBm"),
    ("Measurement app", "WiFiman"),
    ("Document status", "Preliminary \u2014 illustrative estimates, not field measurements"),
]

# (area, rssi in dBm, rating, interpretation)
AREAS = [
    ("Room 1", -45, "Excellent", "Strong signal expected throughout the room."),
    ("Room 2", -48, "Excellent", "Strong signal expected throughout the room."),
    ("Room 3", -50, "Excellent", "Strong signal expected throughout the room."),
    ("Room 4", -68, "Fair", "Usable, but likely to be slower or less stable."),
    ("Washroom", -58, "Good", "Reliable for everyday use; some speed loss possible."),
    ("Hallway", -46, "Excellent", "Strong signal expected along the full length."),
    ("Kitchen", -83, "Poor", "Unreliable connectivity expected; dropouts likely."),
]


def areas_by_strength():
    """Same locations, ordered strongest first, for the chart."""
    return sorted(AREAS, key=lambda row: row[1], reverse=True)

RATING_GUIDE = [
    ("Excellent", "\u221230 to \u221250 dBm",
     "Full-speed connectivity for streaming, video calls and file transfer."),
    ("Good", "\u221251 to \u221260 dBm",
     "Reliable everyday performance; throughput begins to tail off at range."),
    ("Fair", "\u221261 to \u221270 dBm",
     "Browsing and messaging fine; video calls and large transfers may stutter."),
    ("Weak", "\u221271 to \u221279 dBm",
     "Unstable connection; dropouts likely, particularly on the 5 GHz band."),
    ("Poor", "\u2264\u00a0\u221280 dBm",
     "Frequent disconnections; some devices may fail to stay connected."),
]

ACTIONS = [
    ("01", "Relocate the router", "High priority",
     "Place the router in a central, elevated and open position, clear of masonry, "
     "metal surfaces and large appliances such as the refrigerator and microwave. "
     "Router placement is the most common cause of a weak signal at the far end of a property."),
    ("02", "Re-test the kitchen and Room 4", "High priority",
     "Measure signal where devices are actually used, not at the doorway. Record the reading "
     "at seated or standing height in each location and repeat the test at two different times "
     "of day to account for network load."),
    ("03", "Extend coverage if required", "Conditional",
     "If a verified kitchen reading remains at or below \u221280 dBm after relocation, add a mesh "
     "node or access point positioned roughly midway between the router and the kitchen. "
     "A wired (Ethernet-backhaul) access point is preferable where cabling is practical."),
    ("04", "Capture verified readings in WiFiman", "High priority",
     "Log RSSI for every location together with the device, the Wi-Fi band (2.4 GHz or 5 GHz) "
     "and the date and time. Repeat the survey after any change to router placement or equipment "
     "so that before-and-after results can be compared directly."),
]


# --------------------------------------------------------------------------- #
# Styles
# --------------------------------------------------------------------------- #

def style(name, **kw):
    base = dict(fontName="Body", fontSize=9.5, leading=14, textColor=INK,
                alignment=TA_LEFT, spaceBefore=0, spaceAfter=0)
    base.update(kw)
    return ParagraphStyle(name, **base)


S = {
    "title": style("title", fontName="Body-Bold", fontSize=25, leading=29,
                   textColor=colors.white),
    "subtitle": style("subtitle", fontSize=10.5, leading=14,
                      textColor=colors.HexColor("#B9CBD8")),
    "kicker": style("kicker", fontName="Body-Bold", fontSize=7.6, leading=10,
                    textColor=colors.HexColor("#8FB3C4")),
    "hero_meta": style("hero_meta", fontSize=8.4, leading=12,
                       textColor=colors.HexColor("#C9D8E2")),
    "h2": style("h2", fontName="Body-Bold", fontSize=12.5, leading=16,
                textColor=NAVY),
    "h3": style("h3", fontName="Body-Bold", fontSize=9.5, leading=13, textColor=NAVY),
    "body": style("body", fontSize=9.5, leading=14.4),
    "body_small": style("body_small", fontSize=8.6, leading=13, textColor=SLATE),
    "meta_key": style("meta_key", fontName="Body-Bold", fontSize=7.6, leading=11,
                      textColor=SLATE),
    "meta_val": style("meta_val", fontSize=9, leading=13),
    "kpi_value": style("kpi_value", fontName="Body-Bold", fontSize=17, leading=19,
                       textColor=NAVY),
    "kpi_label": style("kpi_label", fontSize=7.6, leading=10, textColor=SLATE),
    "th": style("th", fontName="Body-Bold", fontSize=7.8, leading=10,
                textColor=colors.white),
    "th_right": style("th_right", fontName="Body-Bold", fontSize=7.8, leading=10,
                      textColor=colors.white, alignment=TA_RIGHT),
    "cell": style("cell", fontSize=9, leading=12),
    "cell_bold": style("cell_bold", fontName="Body-Bold", fontSize=9, leading=12),
    "cell_right": style("cell_right", fontName="Body-Bold", fontSize=9.5, leading=12,
                        alignment=TA_RIGHT),
    "cell_small": style("cell_small", fontSize=8.2, leading=11.5, textColor=SLATE),
    "cell_rating": style("cell_rating", fontName="Body-Bold", fontSize=8.6, leading=11),
    "bullet": style("bullet", fontSize=8.6, leading=13, textColor=SLATE,
                    leftIndent=11, firstLineIndent=-11, bulletIndent=1,
                    spaceAfter=1.8 * mm),
    "note": style("note", fontSize=8.6, leading=13.5, textColor=colors.HexColor("#3D4E5C")),
    "note_bold": style("note_bold", fontName="Body-Bold", fontSize=8.8, leading=13.5,
                       textColor=NAVY),
    "action_title": style("action_title", fontName="Body-Bold", fontSize=10, leading=13,
                          textColor=NAVY),
    "action_num": style("action_num", fontName="Body-Bold", fontSize=13, leading=15,
                        textColor=ACCENT, alignment=TA_RIGHT),
    "action_body": style("action_body", fontSize=8.8, leading=13),
    "tag": style("tag", fontName="Body-Bold", fontSize=6.8, leading=9,
                 textColor=colors.white),
    "footnote": style("footnote", fontSize=7.6, leading=10.5, textColor=SLATE),
}

CONTENT_W = A4[0] - 40 * mm


# --------------------------------------------------------------------------- #
# Custom flowables
# --------------------------------------------------------------------------- #

class Rule(Flowable):
    """A thin horizontal rule."""

    def __init__(self, width, thickness=0.6, color=RULE, space_before=0, space_after=0):
        super().__init__()
        self.width, self.thickness, self.color = width, thickness, color
        self.sb, self.sa = space_before, space_after
        self.height = thickness + self.sb + self.sa

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        y = self.sa + self.thickness / 2
        self.canv.line(0, y, self.width, y)


class SignalBar(Flowable):
    """Small horizontal bar visualising RSSI on a -30..-90 dBm scale."""

    SCALE_MIN, SCALE_MAX = -90.0, -30.0

    def __init__(self, dbm, width, height=5.0, color=ACCENT):
        super().__init__()
        self.dbm, self.width, self.height, self.color = dbm, width, height, color
        self._height = height

    @property
    def height(self):
        return self._height

    @height.setter
    def height(self, value):
        self._height = value

    def draw(self):
        frac = (self.dbm - self.SCALE_MIN) / (self.SCALE_MAX - self.SCALE_MIN)
        frac = max(0.02, min(1.0, frac))
        r = self.height / 2
        c = self.canv
        c.setFillColor(colors.HexColor("#E7ECF0"))
        c.roundRect(0, 0, self.width, self.height, r, stroke=0, fill=1)
        c.setFillColor(self.color)
        c.roundRect(0, 0, max(self.height, self.width * frac), self.height, r,
                    stroke=0, fill=1)


class SectionHeading(Flowable):
    """Section heading with a numbered accent tab."""

    def __init__(self, number, title, width=CONTENT_W):
        super().__init__()
        self.number, self.title, self.width = number, title, width
        self.height = 17

    def draw(self):
        c = self.canv
        c.setFillColor(ACCENT)
        c.rect(0, 10.5, 2.4, 6.5, stroke=0, fill=1)
        c.setFillColor(NAVY)
        c.setFont("Body-Bold", 12)
        label = f"{self.number}.  {self.title}" if self.number else self.title
        c.drawString(8, 10.5, label)



class CoverageChart(Flowable):
    """Horizontal bar chart of RSSI by area with service thresholds."""

    SCALE_MIN, SCALE_MAX = -90.0, -30.0

    def __init__(self, areas, width=CONTENT_W, label_w=22 * mm, value_w=18 * mm,
                 row_h=6.1 * mm, top_pad=5.5 * mm, bottom_pad=8.5 * mm):
        super().__init__()
        self.areas = areas
        self.w = width
        self.label_w = label_w
        self.value_w = value_w
        self.row_h = row_h
        self.top_pad = top_pad
        self.bottom_pad = bottom_pad
        self.height = top_pad + row_h * len(areas) + bottom_pad

    def draw(self):
        c = self.canv
        plot_x = self.label_w
        plot_w = self.w - self.label_w - self.value_w
        bar_h = 3.6 * mm
        top = self.height - self.top_pad

        def x_for(dbm):
            frac = (dbm - self.SCALE_MIN) / (self.SCALE_MAX - self.SCALE_MIN)
            return plot_x + plot_w * max(0.0, min(1.0, frac))

        # threshold guides
        for dbm, label, dash in ((-60, "\u221260", (2, 2)), (-70, "\u221270", (2, 2)),
                                 (-80, "\u221280", (1, 1.6))):
            x = x_for(dbm)
            c.setStrokeColor(colors.HexColor("#C3CDD6") if dbm != -80
                             else RATINGS["Poor"][0])
            c.setLineWidth(0.6)
            c.setDash(dash)
            c.line(x, top - self.row_h * len(self.areas) - 1,
                   x, top + 2.5)
            c.setDash()
            c.setFont("Body", 6.2)
            c.setFillColor(SLATE if dbm != -80 else RATINGS["Poor"][0])
            anchor = "right" if dbm == -80 else "center"
            txt = f"{label} dBm"
            if anchor == "center":
                c.drawCentredString(x, top + 5, txt)
            else:
                c.drawRightString(x + 1, top + 5, txt)

        for i, (area, dbm, rating, _note) in enumerate(self.areas):
            color, _tint = RATINGS[rating]
            y_top = top - self.row_h * i
            cy = y_top - self.row_h / 2 + 0.6 * mm

            if i % 2 == 0:
                c.setFillColor(colors.HexColor("#FAFBFC"))
                c.rect(0, y_top - self.row_h, self.w, self.row_h, stroke=0, fill=1)

            c.setFont("Body", 8.2)
            c.setFillColor(INK)
            c.drawString(2, cy - 1.1, area)

            c.setFillColor(colors.HexColor("#E9EEF2"))
            c.roundRect(plot_x, cy - bar_h / 2, plot_w, bar_h, bar_h / 2, stroke=0, fill=1)
            end = x_for(dbm)
            c.setFillColor(color)
            c.roundRect(plot_x, cy - bar_h / 2, max(bar_h, end - plot_x), bar_h,
                        bar_h / 2, stroke=0, fill=1)

            c.setFont("Body-Bold", 8.2)
            c.setFillColor(color)
            c.drawRightString(self.w - 2, cy - 1.1, f"\u2212{abs(dbm)} dBm")

        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
        c.line(0, self.bottom_pad - 3.5 * mm, self.w, self.bottom_pad - 3.5 * mm)
        c.setFont("Body", 6.6)
        c.setFillColor(SLATE)
        c.drawString(2, self.bottom_pad - 7.2 * mm,
                     "Scale: \u221290 dBm (weak, left) to \u221230 dBm (strong, right). "
                     "Dashed guides mark the \u221260, \u221270 and \u221280 dBm rating thresholds.")


# --------------------------------------------------------------------------- #
# Page furniture
# --------------------------------------------------------------------------- #

def page_furniture(canv, doc):
    canv.saveState()
    width, height = A4
    page_no = canv.getPageNumber()
    total = getattr(doc, "_total_pages", None)

    if page_no == 1:
        band_h = 54 * mm
        canv.setFillColor(NAVY)
        canv.rect(0, height - band_h, width, band_h, stroke=0, fill=1)
        canv.setFillColor(ACCENT)
        canv.rect(0, height - band_h, width, 2.2, stroke=0, fill=1)

        left = 20 * mm
        canv.setFillColor(colors.HexColor("#8FB3C4"))
        canv.setFont("Body-Bold", 7.4)
        canv.drawString(left, height - 16 * mm, "WIRELESS NETWORK  \u00b7  SITE ASSESSMENT")
        canv.setFillColor(colors.white)
        canv.setFont("Body-Bold", 24)
        canv.drawString(left, height - 28 * mm, REPORT_TITLE)
        canv.setFillColor(colors.HexColor("#B9CBD8"))
        canv.setFont("Body", 10.2)
        canv.drawString(left, height - 36.5 * mm, REPORT_SUBTITLE)

        canv.setFillColor(colors.HexColor("#C9D8E2"))
        canv.setFont("Body", 8.2)
        canv.drawString(
            left, height - 45.5 * mm,
            f"Prepared {REPORT_DATE}   \u00b7   Version {DOC_VERSION}   \u00b7   Prepared with WiFiman")

        # status badge
        bw, bh = 30 * mm, 6.6 * mm
        bx, by = width - 20 * mm - bw, height - 45.5 * mm - 2.2 * mm
        canv.setFillColor(colors.HexColor("#F0B429"))
        canv.roundRect(bx, by, bw, bh, 3, stroke=0, fill=1)
        canv.setFillColor(NAVY)
        canv.setFont("Body-Bold", 6.8)
        canv.drawCentredString(bx + bw / 2, by + 2.3 * mm, "PRELIMINARY")
    else:
        band_h = 17 * mm
        canv.setFillColor(NAVY)
        canv.rect(0, height - band_h, width, band_h, stroke=0, fill=1)
        canv.setFillColor(ACCENT)
        canv.rect(0, height - band_h, width, 1.6, stroke=0, fill=1)
        canv.setFillColor(colors.white)
        canv.setFont("Body-Bold", 9.6)
        canv.drawString(20 * mm, height - 11 * mm, REPORT_TITLE)
        canv.setFillColor(colors.HexColor("#B9CBD8"))
        canv.setFont("Body", 7.8)
        canv.drawRightString(width - 20 * mm, height - 11 * mm,
                             f"Preliminary assessment \u00b7 {REPORT_DATE}")

    # footer
    canv.setStrokeColor(RULE)
    canv.setLineWidth(0.6)
    canv.line(20 * mm, 16 * mm, width - 20 * mm, 16 * mm)
    canv.setFont("Body", 7.4)
    canv.setFillColor(SLATE)
    canv.drawString(20 * mm, 11.5 * mm,
                    "Illustrative estimates only \u2014 not verified field measurements.")
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

def kpi_strip():
    items = [
        ("7", "locations assessed", NAVY),
        ("4", "rated excellent", RATINGS["Excellent"][0]),
        ("1", "rated poor \u2014 kitchen", RATINGS["Poor"][0]),
        ("38 dB", "spread across areas", NAVY),
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


def metadata_block():
    """Compact two-column report details grid."""
    rows = [
        [Paragraph("PREPARED", S["meta_key"]), Paragraph(REPORT_DATE, S["meta_val"]),
         Paragraph("MEASUREMENT APP", S["meta_key"]), Paragraph("WiFiman", S["meta_val"])],
        [Paragraph("COVERAGE AREA", S["meta_key"]),
         Paragraph("Seven locations: 4 rooms, washroom, hallway, kitchen", S["meta_val"]),
         Paragraph("METRIC", S["meta_key"]),
         Paragraph("RSSI, in dBm", S["meta_val"])],
        [Paragraph("DOCUMENT STATUS", S["meta_key"]),
         Paragraph("Preliminary \u2014 illustrative estimates only",
                   S["meta_val"]),
         Paragraph("", S["meta_key"]), Paragraph("", S["meta_val"])],
    ]
    col = CONTENT_W / 4
    t = Table(rows, colWidths=[col * 0.72, col * 1.28, col * 0.85, col * 1.15])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 3.4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.4),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#E7ECF0")),
    ]))
    return t


def areas_table():
    head = [
        Paragraph("AREA", S["th"]),
        Paragraph("RSSI", S["th_right"]),
        Paragraph("RATING", S["th"]),
        Paragraph("RELATIVE STRENGTH", S["th"]),
        Paragraph("INTERPRETATION", S["th"]),
    ]
    rows = [head]
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("TOPPADDING", (0, 1), (-1, -1), 5.5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, colors.HexColor("#E3E8ED")),
        ("BOX", (0, 1), (-1, -1), 0.6, colors.HexColor("#DCE5EB")),
    ]
    for i, (area, dbm, rating, note) in enumerate(AREAS, start=1):
        color, tint = RATINGS[rating]
        rows.append([
            Paragraph(area, S["cell_bold"]),
            Paragraph(f"\u2212{abs(dbm)}\u00a0dBm", S["cell_right"]),
            Paragraph(f'<font color="{color.hexval()}">{rating}</font>', S["cell_rating"]),
            SignalBar(dbm, 34 * mm, height=5, color=color),
            Paragraph(note, S["cell_small"]),
        ])
        cmds.append(("BACKGROUND", (2, i), (2, i), tint))
        if i % 2 == 1:
            cmds.append(("BACKGROUND", (0, i), (0, i), ZEBRA))
            cmds.append(("BACKGROUND", (1, i), (1, i), ZEBRA))
            cmds.append(("BACKGROUND", (3, i), (3, i), ZEBRA))
            cmds.append(("BACKGROUND", (4, i), (4, i), ZEBRA))

    t = Table(rows, colWidths=[26 * mm, 24 * mm, 23 * mm, 37 * mm, CONTENT_W - 110 * mm],
              repeatRows=1)
    t.setStyle(TableStyle(cmds))
    return t


def guide_table():
    head = [
        Paragraph("RATING", S["th"]),
        Paragraph("RSSI RANGE", S["th"]),
        Paragraph("TYPICAL EXPERIENCE", S["th"]),
    ]
    rows = [head]
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, colors.HexColor("#E3E8ED")),
        ("BOX", (0, 1), (-1, -1), 0.6, colors.HexColor("#DCE5EB")),
    ]
    for i, (rating, rng, text) in enumerate(RATING_GUIDE, start=1):
        color, tint = RATINGS[rating]
        rows.append([
            Paragraph(f'<font color="{color.hexval()}">{rating}</font>', S["cell_rating"]),
            Paragraph(rng, S["cell"]),
            Paragraph(text, S["cell_small"]),
        ])
        if i % 2 == 0:
            cmds.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
        cmds.append(("LINEBEFORE", (0, i), (0, i), 2.4, color))

    t = Table(rows, colWidths=[26 * mm, 33 * mm, CONTENT_W - 59 * mm], repeatRows=1)
    t.setStyle(TableStyle(cmds))
    return t


def actions_block():
    rows, cmds = [], []
    for idx, (num, title, tag, body) in enumerate(ACTIONS):
        tag_color = RATINGS["Poor"][0] if tag == "High priority" else RATINGS["Fair"][0]
        tag_tint = RATINGS["Poor"][1] if tag == "High priority" else RATINGS["Fair"][1]

        badge = Table([[Paragraph(tag.upper(), S["tag"])]], colWidths=[len(tag) * 5.2 + 8])
        badge.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), tag_color),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]))

        header = Table(
            [[Paragraph(title, S["action_title"]), badge]],
            colWidths=[CONTENT_W - 40 * mm - 44 * mm, 44 * mm],
        )
        header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

        rows.append([Paragraph(num, S["action_num"]), [header, Paragraph(body, S["action_body"])]])
        r = len(rows) - 1
        cmds += [
            ("VALIGN", (0, r), (0, r), "TOP"),
            ("VALIGN", (1, r), (1, r), "TOP"),
            ("TOPPADDING", (0, r), (-1, r), 7),
            ("BOTTOMPADDING", (0, r), (-1, r), 7),
            ("LEFTPADDING", (0, r), (0, r), 0),
            ("RIGHTPADDING", (0, r), (0, r), 8),
            ("LEFTPADDING", (1, r), (1, r), 0),
            ("LINEBELOW", (0, r), (-1, r), 0.4,
             colors.HexColor("#E3E8ED") if r < len(ACTIONS) - 1 else colors.white),
        ]

    t = Table(rows, colWidths=[12 * mm, CONTENT_W - 12 * mm])
    t.setStyle(TableStyle(cmds))
    return t



class RuleLines(Flowable):
    """Light ruled lines for handwritten notes."""

    def __init__(self, width=CONTENT_W, lines=5, gap=7.6 * mm):
        super().__init__()
        self.w, self.n, self.gap = width, lines, gap
        self.height = gap * lines

    def draw(self):
        c = self.canv
        c.setStrokeColor(colors.HexColor("#C8D2DA"))
        c.setLineWidth(0.5)
        for i in range(self.n):
            y = self.height - self.gap * (i + 1) + 2
            c.line(0, y, self.w, y)


def priority_panel():
    """Three-tier priority grouping of the assessed locations."""
    tiers = [
        ("ACT NOW", RATINGS["Poor"][0], RATINGS["Poor"][1], "Kitchen",
         "Below the reliable-service threshold; remedial action required."),
        ("MONITOR", RATINGS["Fair"][0], RATINGS["Fair"][1], "Room 4",
         "Serviceable, but close to the weak boundary. Re-test after changes."),
        ("NO ACTION", RATINGS["Excellent"][0], RATINGS["Excellent"][1],
         "Rooms 1\u20133, washroom, hallway",
         "Expected to meet normal household requirements without changes."),
    ]
    cells = []
    for label, color, tint, areas, note in tiers:
        inner = [
            Paragraph(f'<font color="{color.hexval()}"><b>{label}</b></font>', S["meta_key"]),
            Spacer(1, 2.5),
            Paragraph(areas, S["cell_bold"]),
            Spacer(1, 1.5),
            Paragraph(note, S["cell_small"]),
        ]
        w = (CONTENT_W - 12 * mm) / 3
        cells.append(inner)

    t = Table([cells], colWidths=[CONTENT_W / 3] * 3)
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#DCE5EB")),
        ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#DCE5EB")),
    ]
    for i, (_l, _c, tint, _a, _n) in enumerate(tiers):
        cmds.append(("BACKGROUND", (i, 0), (i, 0), tint))
        cmds.append(("LINEABOVE", (i, 0), (i, 0), 2.6, _c))
    t.setStyle(TableStyle(cmds))
    return t


def note_box(flowables, tint=colors.HexColor("#FFF8E5"),
             border=colors.HexColor("#E2C87A")):
    t = Table([[flowables]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), tint),
        ("BOX", (0, 0), (-1, -1), 0.7, border),
        ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor("#D9A21B")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    return t


def signoff_table():
    rows = [
        [Paragraph("Surveyed by", S["cell_small"]), "",
         Paragraph("Signature", S["cell_small"]), ""],
        [Paragraph("Date of survey", S["cell_small"]), "",
         Paragraph("Readings attached", S["cell_small"]), ""],
    ]
    t = Table(rows, colWidths=[32 * mm, CONTENT_W / 2 - 32 * mm, 36 * mm,
                               CONTENT_W / 2 - 36 * mm],
              rowHeights=[11 * mm, 11 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("BACKGROUND", (0, 0), (-1, -1), PAPER_TINT),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#DCE5EB")),
        ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#DCE5EB")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def survey_template():
    """Blank capture sheet so the client can record verified WiFiman readings."""
    head = [
        Paragraph("LOCATION", S["th"]),
        Paragraph("RSSI (dBm)", S["th"]),
        Paragraph("BAND", S["th"]),
        Paragraph("TEST DEVICE", S["th"]),
        Paragraph("DATE / TIME", S["th"]),
    ]
    widths = [34 * mm, 26 * mm, 22 * mm, 40 * mm, CONTENT_W - 122 * mm]
    rows = [head]
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 5.5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D5DDE4")),
        ("TOPPADDING", (0, 1), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
    ]
    for i, (area, _dbm, _rating, _note) in enumerate(AREAS, start=1):
        rows.append([Paragraph(area, S["cell_bold"]), "", "", "", ""])
        if i % 2 == 0:
            cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FAFBFC")))
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle(cmds))
    return t


# --------------------------------------------------------------------------- #
# Story
# --------------------------------------------------------------------------- #

def build_story():
    story = []

    # --- metadata + summary ------------------------------------------------
    story.append(Paragraph("REPORT DETAILS", S["meta_key"]))
    story.append(Spacer(1, 4))
    story.append(metadata_block())
    story.append(Spacer(1, 7 * mm))

    story.append(SectionHeading(1, "Executive summary"))
    story.append(Spacer(1, 3.5 * mm))
    story.append(Paragraph(
        "This report sets out the expected Wi-Fi signal strength at seven locations within a single "
        "dwelling. Reception is expected to be <b>excellent</b> in Rooms&nbsp;1\u20133 and the hallway "
        "(\u221245 to \u221250&nbsp;dBm), <b>good</b> in the washroom (\u221258&nbsp;dBm) and "
        "<b>fair</b> in Room&nbsp;4 (\u221268&nbsp;dBm). The <b>kitchen is the exception</b>, at an "
        "estimated \u221283&nbsp;dBm, which is below the threshold for dependable connectivity.",
        S["body"]))
    story.append(Spacer(1, 2.5 * mm))
    story.append(Paragraph(
        "The kitchen is therefore the highest-priority location for remedial work, and Room&nbsp;4 "
        "should be re-checked once any router relocation has been completed. Because the figures are "
        "estimates rather than measured readings, Section&nbsp;6 sets out how to convert them into a "
        "verified survey.",
        S["body"]))
    story.append(Spacer(1, 5 * mm))
    story.append(kpi_strip())
    story.append(Spacer(1, 8 * mm))
    story.append(SectionHeading(2, "Coverage profile"))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "Estimated signal strength by location, ordered from strongest to weakest. The kitchen "
        "sits below the \u221280&nbsp;dBm threshold at which connections typically become unreliable.",
        S["body_small"]))
    story.append(Spacer(1, 4 * mm))
    story.append(CoverageChart(areas_by_strength()))
    story.append(NextPageTemplate("later"))
    story.append(PageBreak())

    # --- area table --------------------------------------------------------
    story.append(SectionHeading(3, "Area-by-area assessment"))
    story.append(Spacer(1, 3 * mm))
    story.append(areas_table())
    story.append(Spacer(1, 2.5 * mm))
    story.append(Paragraph(
        "RSSI is expressed in dBm; values closer to zero indicate a stronger signal, so "
        "\u221245&nbsp;dBm is stronger than \u221283&nbsp;dBm. The bars above are scaled across the "
        "\u221230 to \u221290&nbsp;dBm range and are intended for comparison only.",
        S["footnote"]))

    story.append(Spacer(1, 8 * mm))

    # --- rating guide ------------------------------------------------------
    story.append(SectionHeading(4, "Rating guide"))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "The following practical ranges are used throughout this report. They describe the expected "
        "end-user experience at the stated signal level.",
        S["body"]))
    story.append(Spacer(1, 3.5 * mm))
    story.append(guide_table())
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "Actual throughput is also influenced by interference, the Wi-Fi band in use (2.4&nbsp;GHz "
        "reaches further; 5&nbsp;GHz is faster), the capability of the router and client device, "
        "building materials and the number of connected devices.",
        S["footnote"]))
    story.append(Spacer(1, 5 * mm))
    story.append(KeepTogether([
        Paragraph("PRIORITY GROUPING", S["meta_key"]),
        Spacer(1, 3),
        priority_panel(),
    ]))

    # --- recommendations ---------------------------------------------------
    story.append(PageBreak())
    story.append(SectionHeading(5, "Recommended actions"))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "The actions below are listed in the order in which they should be carried out. Steps 1, 2 "
        "and 4 can be completed at no cost; step 3 may require additional hardware.",
        S["body"]))
    story.append(Spacer(1, 2 * mm))
    story.append(actions_block())
    story.append(Spacer(1, 8 * mm))

    # --- limitations -------------------------------------------------------
    story.append(SectionHeading(6, "Measurement note and limitations"))
    story.append(Spacer(1, 3 * mm))
    story.append(note_box([
        Paragraph("Basis of the figures", S["note_bold"]),
        Spacer(1, 2.5),
        Paragraph(
            "No on-site RSSI readings were supplied for this assessment. WiFiman is the application "
            "identified for the survey, and the dBm values in Section&nbsp;3 are representative "
            "estimates chosen to reflect the reported signal category for each location. They are "
            "<b>not</b> readings exported from WiFiman and should not be relied upon as measured data "
            "or used as the basis for a contractual commitment.",
            S["note"]),
    ]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("To convert this into a verified survey:", S["note_bold"]))
    story.append(Spacer(1, 2 * mm))
    for bullet in [
        "In WiFiman, record RSSI at each location and note the Wi-Fi band, the test device and the "
        "date and time of each reading.",
        "Take readings at the height and position where devices are normally used, and repeat each "
        "measurement at least twice to identify variation.",
        "Note any household appliances, mirrors, metal surfaces or thick walls between the router "
        "and each location; these commonly explain a localised drop in signal.",
        "Repeat the survey after any change to router placement or equipment and compare the "
        "results against the baseline in Section&nbsp;3.",
    ]:
        story.append(Paragraph(bullet, S["bullet"], bulletText="\u2022"))

    story.append(NextPageTemplate("later"))
    story.append(PageBreak())

    # --- appendix ----------------------------------------------------------
    story.append(SectionHeading(None, "Appendix A \u2014 survey record template"))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "Use this sheet to record verified WiFiman readings during the follow-up survey. Complete one "
        "row per location, then compare the results against the estimates in Section&nbsp;3. Retain "
        "the completed sheet with this report so that any change to router placement or equipment can "
        "be evaluated against a documented baseline.",
        S["body"]))
    story.append(Spacer(1, 4 * mm))
    story.append(survey_template())
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("ADDITIONAL OBSERVATIONS", S["meta_key"]))
    story.append(Spacer(1, 3))
    story.append(RuleLines(lines=5))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "Record the band in use (2.4&nbsp;GHz or 5&nbsp;GHz) separately where both are broadcast \u2014 "
        "a location may read well on 2.4&nbsp;GHz and poorly on 5&nbsp;GHz. Note the test device as well, "
        "since antenna design and Wi-Fi generation vary considerably between phones and laptops.",
        S["footnote"]))
    story.append(Spacer(1, 8 * mm))
    story.append(KeepTogether([
        Paragraph("SURVEY SIGN-OFF", S["meta_key"]),
        Spacer(1, 3),
        signoff_table(),
    ]))

    return story


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #

def build(path: Path) -> None:
    doc = BaseDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=40 * mm,
        bottomMargin=22 * mm,
        title=REPORT_TITLE,
        author="Site assessment",
        subject="Preliminary Wi-Fi coverage assessment (RSSI, dBm)",
        creator="tools/build_wifi_report.py",
        keywords="Wi-Fi, RSSI, dBm, WiFiman, coverage assessment",
    )

    first_frame = Frame(20 * mm, 22 * mm, CONTENT_W, A4[1] - 80 * mm,
                        id="first", showBoundary=0,
                        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    later_frame = Frame(20 * mm, 22 * mm, CONTENT_W, A4[1] - 55 * mm,
                        id="later", showBoundary=0,
                        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    doc.addPageTemplates([
        PageTemplate(id="first", frames=[first_frame]),
        PageTemplate(id="later", frames=[later_frame]),
    ])

    doc.build(build_story(), canvasmaker=NumberedCanvas)


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "reports/wifi-signal-assessment/wifi-signal-strength-assessment.pdf")
    out.parent.mkdir(parents=True, exist_ok=True)
    build(out)
    print(f"wrote {out}")
