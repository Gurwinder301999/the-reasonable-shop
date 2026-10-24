# the-reasonable-shop

## Reports

| Report | Output | Build |
|---|---|---|
| Wi-Fi Signal Strength Assessment | `reports/wifi-signal-assessment/wifi-signal-strength-assessment.pdf` | `python3 tools/build_wifi_report.py` |

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
