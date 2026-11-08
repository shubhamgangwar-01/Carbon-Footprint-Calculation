"""PDF report generation (ReportLab + matplotlib charts).

The report is built ONLY from a stored calculation (input snapshot + result +
scenarios + recommendations); it never recalculates. Its numbers therefore always
match the dashboard for the same calculation id.

Structure follows the GHG Protocol / ISO 14064-1 reporting elements: organisation
& event description, reporting boundary and period, methodology, results by
category, activity-level detail, emission-factor sources and versions,
assumptions & exclusions, data quality & uncertainty, reduction opportunities,
scenario analysis and offsets reported separately from gross emissions.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,  # noqa: E402
                                TableStyle)

GREEN = colors.HexColor("#166534")
MINT = colors.HexColor("#ecfdf3")
GREY = colors.HexColor("#4b5563")
LINE = colors.HexColor("#d1d5db")
CAT_COLORS = {"transportation": "#2a78d6", "accommodation": "#eb6834", "energy": "#1baf7a", "food": "#eda100",
              "waste": "#e87ba4", "materials": "#008300"}
CAT_LABEL = {"transportation": "Transportation", "accommodation": "Accommodation", "energy": "Venue & energy",
             "food": "Food & beverages", "waste": "Waste", "materials": "Materials & procurement"}

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], textColor=GREEN, fontSize=16, spaceBefore=6, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], textColor=GREEN, fontSize=12.5, spaceBefore=8, spaceAfter=4)
P = ParagraphStyle("P", parent=ss["BodyText"], fontSize=9, leading=12.5)
SMALL = ParagraphStyle("S", parent=P, fontSize=7.5, leading=9.5, textColor=GREY)
CELL = ParagraphStyle("C", parent=P, fontSize=7.3, leading=9)
CELLB = ParagraphStyle("CB", parent=CELL, fontName="Helvetica-Bold")


def fmt(v, d=1):
    if v is None:
        return "–"
    return f"{v:,.{d}f}"


def _table(rows, widths, header=True, zebra=True, font=7.3):
    data = [[Paragraph(str(c), CELLB if (header and i == 0) else CELL) if not isinstance(c, Paragraph) else c for c in r]
            for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.25, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
          ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), MINT)]
    if zebra:
        for i in range(2 if header else 1, len(rows), 2):
            st.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f9fafb")))
    t.setStyle(TableStyle(st))
    return t


def _img(buf: io.BytesIO, width: float, max_height: float | None = None) -> Image:
    """ReportLab Image scaled to `width`, preserving the PNG aspect ratio."""
    from reportlab.lib.utils import ImageReader
    iw, ih = ImageReader(buf).getSize()
    buf.seek(0)
    h = width * ih / iw
    if max_height and h > max_height:
        width, h = max_height * iw / ih, max_height
    return Image(buf, width=width, height=h)


def _png(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _donut(result) -> io.BytesIO | None:
    cats = [c for c in result["by_category"] if c["emissions_kg"] > 0]
    if not cats:
        return None
    fig, ax = plt.subplots(figsize=(4.2, 3.2))
    vals = [c["emissions_kg"] / 1000 for c in cats]
    ax.pie(vals, colors=[CAT_COLORS[c["category"]] for c in cats], startangle=90, counterclock=False,
           wedgeprops={"width": 0.38, "edgecolor": "white", "linewidth": 1.5})
    ax.text(0, 0, f"{result['total_tonnes']:,.1f}\nt CO₂e", ha="center", va="center", fontsize=11, fontweight="bold", color="#14532d")
    ax.legend([f"{CAT_LABEL[c['category']]} ({c['share_pct']:.1f}%)" for c in cats], loc="center left", bbox_to_anchor=(1, 0.5),
              frameon=False, fontsize=8)
    ax.set_aspect("equal")
    return _png(fig)


def _hbar(items, title, value_key="emissions_kg", label_key="activity") -> io.BytesIO | None:
    items = [i for i in items if i[value_key] > 0][:8]
    if not items:
        return None
    fig, ax = plt.subplots(figsize=(6.6, 0.42 * len(items) + 0.8))
    labels = [(i[label_key][:48] + "…") if len(i[label_key]) > 49 else i[label_key] for i in items][::-1]
    vals = [i[value_key] / 1000 for i in items][::-1]
    cols = [CAT_COLORS.get(i.get("category"), "#166534") for i in items][::-1]
    ax.barh(labels, vals, color=cols, height=0.6)
    for y, v in enumerate(vals):
        ax.text(v, y, f" {v:,.2f}", va="center", fontsize=7.5)
    ax.set_xlabel("t CO₂e", fontsize=8)
    ax.set_title(title, fontsize=9, loc="left", color="#14532d")
    ax.tick_params(labelsize=7.5)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    return _png(fig)


def _scenario_chart(scen) -> io.BytesIO | None:
    rows = [s for s in scen if s.get("applicable") and s.get("reduction_kg", 0) > 0]
    rows.sort(key=lambda s: -s["reduction_kg"])
    rows = rows[:8]
    if not rows:
        return None
    return _hbar([{"activity": s["title"], "emissions_kg": s["reduction_kg"], "category": None} for s in rows],
                 "Estimated reduction by scenario (t CO₂e, location-based)")


def build_pdf(conf_input: dict, result: dict, scenarios: list[dict], recommendations: list[dict], calc_id: int,
              factor_details: dict | None = None) -> bytes:
    buf = io.BytesIO()
    b = conf_input["basic"]
    generated = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GREY)
        canvas.drawString(18 * mm, 10 * mm, f"{b['name']} – Conference Carbon Footprint Report  |  Calculation #{calc_id}  |  "
                                            f"Factor set {result['factor_set_version']}")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.setStrokeColor(GREEN)
        canvas.setLineWidth(1.2)
        canvas.line(18 * mm, A4[1] - 12 * mm, A4[0] - 18 * mm, A4[1] - 12 * mm)
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
                            title=f"{b['name']} - Carbon Footprint Report", author="Conference Carbon Footprint Calculator")
    W = A4[0] - 36 * mm
    s: list = []

    # ------------------------------------------------------------------ cover / summary
    s.append(Paragraph("Conference Carbon Footprint Report", ParagraphStyle("T", parent=H1, fontSize=22, spaceAfter=2)))
    s.append(Paragraph(f"<b>{b['name']}</b>", ParagraphStyle("T2", parent=P, fontSize=13, leading=16)))
    loc = ", ".join(x for x in [b.get("venue_name"), b.get("state_city"), b.get("country")] if x)
    dates = f"{b.get('start_date') or ''} – {b.get('end_date') or ''}" if b.get("start_date") else f"{result['days']} day(s)"
    s.append(Paragraph(f"{loc}  ·  {dates}  ·  Report generated {generated}", SMALL))
    s.append(Spacer(1, 8))
    kpi = [["Total footprint", "Per participant", "Per conference day", "Data quality"],
           [f"{result['total_tonnes']:,.2f} t CO<sub>2</sub>e", f"{fmt(result['per_participant_kg'])} kg CO<sub>2</sub>e",
            f"{fmt(result['per_day_kg'] / 1000 if result['per_day_kg'] else None, 2)} t CO<sub>2</sub>e",
            f"{(result['data_quality'].get('label') or 'n/a').title()} (score {result['data_quality'].get('weighted_score') or '–'})"],
           [f"{result['total_kg']:,.0f} kg CO<sub>2</sub>e (gross, location-based)", f"{result['participants']:,} in-person participants",
            f"{result['days']} day(s)", f"Uncertainty: {result['data_quality'].get('uncertainty_rating')}"]]
    KH = ParagraphStyle("KH", parent=SMALL, fontSize=7.5)
    KV = ParagraphStyle("KV", parent=P, fontName="Helvetica-Bold", fontSize=11.5, leading=14, textColor=GREEN)
    KS = ParagraphStyle("KS", parent=SMALL, fontSize=6.8, leading=8.5)
    kpi = [[Paragraph(c, st) for c in row] for row, st in zip(kpi, (KH, KV, KS))]
    t = Table(kpi, colWidths=[W / 4] * 4)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), MINT), ("TEXTCOLOR", (0, 0), (-1, 0), GREY),
                           ("FONTSIZE", (0, 0), (-1, 0), 7.5), ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                           ("FONTSIZE", (0, 1), (-1, 1), 11.5), ("TEXTCOLOR", (0, 1), (-1, 1), GREEN),
                           ("FONTSIZE", (0, 2), (-1, 2), 6.8), ("TEXTCOLOR", (0, 2), (-1, 2), GREY),
                           ("LINEAFTER", (0, 0), (-2, -1), 0.5, colors.white), ("TOPPADDING", (0, 0), (-1, -1), 5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    s.append(t)
    s.append(Spacer(1, 6))
    comp = result["completeness"]
    if not comp["is_complete"]:
        missing = ", ".join(CAT_LABEL[c] for c in comp["categories_not_reported"] + comp["categories_incomplete"])
        s.append(Paragraph(f"<font color='#b45309'><b>Completeness note:</b> the following categories are not reported or "
                           f"incomplete and are not included in the total: {missing or 'see data issues'}. "
                           f"{comp['entries_not_counted']} entr(y/ies) could not be counted.</font>", P))
    s.append(Paragraph(
        f"<b>Gross vs. net.</b> Gross emissions: <b>{result['total_tonnes']:,.2f} t CO<sub>2</sub>e</b> (location-based electricity). "
        f"Market-based total: {result['total_market_based_kg'] / 1000:,.2f} t CO<sub>2</sub>e. Offsets/credits retired: "
        f"{result['offsets_tonnes']:,.2f} t CO<sub>2</sub>e (reported separately; they do not reduce gross emissions). "
        f"Gross minus offsets: {result['net_tonnes_after_offsets']:,.2f} t CO<sub>2</sub>e.", P))
    donut = _donut(result)
    if donut:
        s.append(_img(donut, 125 * mm))

    # ------------------------------------------------------------------ 1 conference information
    s.append(Paragraph("1. Conference information and reporting boundary", H1))
    info = [["Item", "Value"],
            ["Conference", b["name"]], ["Type / format", f"{b['conference_type'].title()} / {b['format'].title()}"],
            ["Location", loc or "–"], ["Dates / duration", f"{dates} ({result['days']} days)"],
            ["Participants (in person)", f"{b['attendees']:,} attendees, {b['speakers']:,} speakers, {b['organisers_staff']:,} organisers/staff, "
                                         f"{b['volunteers']:,} volunteers = {result['participants']:,}"],
            ["Virtual attendees", f"{b.get('virtual_attendees', 0):,}"],
            ["Venue area", f"{fmt(b.get('venue_area_m2'), 0)} m²" if b.get("venue_area_m2") else "–"],
            ["Reporting boundary", "Event-based operational boundary: delegate, speaker and staff travel; accommodation; venue "
                                   "energy; catering; waste; purchased event materials (GHG Protocol Scope 1, 2 and relevant Scope 3 "
                                   "categories 1, 3*, 5, 6, 7 for the organiser). *T&D/WTT excluded."],
            ["Reporting period", dates]]
    s.append(_table(info, [45 * mm, W - 45 * mm]))

    # ------------------------------------------------------------------ 2 methodology
    s.append(Paragraph("2. Methodology", H1))
    s.append(Paragraph(
        "Emissions are calculated as <b>activity data × emission factor</b> for each activity, summed by category. "
        "The approach follows the GHG Protocol Corporate Standard, Scope 2 Guidance (dual reporting of location- and "
        "market-based electricity) and Scope 3 Standard, and ISO 14064-1 principles of relevance, completeness, "
        "consistency, accuracy and transparency. Results are expressed in CO<sub>2</sub>-equivalent using IPCC AR5 100-year GWPs. "
        "Missing data is never treated as zero: categories without data are flagged 'not reported'. India-specific factors "
        "are prioritised (CEA grid factor, India GHG Program road and rail factors, CHSB India hotel benchmark); documented "
        "international proxies are used and flagged where no Indian factor is published.", P))
    meth = [["Category", "Calculation", "Primary factor source"],
            ["Transportation", "Public modes: passengers × km × legs × trips × kg/passenger-km. Vehicle modes: (passengers ÷ occupancy) × km × legs × trips × kg/vehicle-km. Flights by haul and cabin class, optional radiative forcing.",
             "India GHG Program (2015) road & rail; DESNZ 2026 (aviation, coach, UK proxies)"],
            ["Accommodation", "Room-nights × country benchmark (or hotel-specific factor, or actual hotel energy)", "Cornell CHSB 2021 via DESNZ 2026"],
            ["Venue energy", "Metered kWh × grid factor (location-based); market-based nets certified renewables; fuels × combustion factors", "CEA CO<sub>2</sub> Baseline v22.0 (FY2025-26); DESNZ 2026 fuels"],
            ["Food & beverages", "Meals × modelled per-meal factor, or kg ingredient × kg CO<sub>2</sub>e/kg; bottles × PET mass × factor", "Poore & Nemecek (2018) via OWID; ICMR-NIN My Plate (2024)"],
            ["Waste", "kg by material and disposal route × route factor (cut-off method)", "DESNZ 2026 waste disposal"],
            ["Materials", "kg material (incl. pages → kg via ISO 216 × gsm) × cradle-to-gate factor; reusable items ÷ expected uses", "DESNZ 2026 material use"]]
    s.append(_table(meth, [28 * mm, 88 * mm, W - 116 * mm]))

    # ------------------------------------------------------------------ 3 results
    s.append(PageBreak())
    s.append(Paragraph("3. Results by category", H1))
    rows = [["Category", "Status", "Emissions (kg CO<sub>2</sub>e)", "Emissions (t CO<sub>2</sub>e)", "Share"]]
    for c in result["by_category"]:
        rows.append([c["label"], c["status"].replace("_", " "), fmt(c["emissions_kg"], 1), fmt(c["emissions_kg"] / 1000, 3),
                     f"{c['share_pct']:.1f}%"])
    rows.append(["<b>Total (gross)</b>", "", f"<b>{fmt(result['total_kg'], 1)}</b>", f"<b>{fmt(result['total_tonnes'], 3)}</b>", "100%"])
    s.append(_table(rows, [50 * mm, 30 * mm, 35 * mm, 35 * mm, W - 150 * mm]))
    s.append(Spacer(1, 4))
    s.append(Paragraph(f"Electricity: location-based {fmt(result['location_based_electricity_kg'])} kg CO<sub>2</sub>e; market-based "
                       f"{fmt(result['market_based_electricity_kg'])} kg CO<sub>2</sub>e. Per participant per day: "
                       f"{fmt(result['per_participant_day_kg'], 2)} kg CO<sub>2</sub>e.", P))
    hb = _hbar(result["top_activities"], "Highest-emission activities (t CO₂e)")
    if hb:
        s.append(_img(hb, W, 100 * mm))

    # ------------------------------------------------------------------ 4 activity table
    s.append(Paragraph("4. Activity-level calculation table", H1))
    s.append(Paragraph("Every reported number is traceable to its activity data and emission factor (factor id = key@dataset version).", SMALL))
    rows = [["#", "Category / activity", "Quantity", "Factor", "Source / factor id", "kg CO<sub>2</sub>e", "Data"]]
    for l in result["lines"]:
        rows.append([l["line_id"], f"<b>{CAT_LABEL.get(l['category'], l['category'])}</b><br/>{l['description']}<br/>"
                                   f"<font size=6 color='#6b7280'>{l['formula']}</font>",
                     f"{fmt(l['quantity'], 2)} {l['quantity_unit']}",
                     f"{l['factor_value']:.5g} {l['factor_unit']}" if l["factor_value"] is not None else "custom",
                     f"<font size=6>{l['factor_id'] or 'user-supplied'}</font>",
                     fmt(l["emissions_kg"], 2), f"{l['data_type']}<br/>{l['data_quality']}{' · proxy' if l['is_proxy'] else ''}"])
    s.append(_table(rows, [11 * mm, 52 * mm, 22 * mm, 24 * mm, 30 * mm, 16 * mm, W - 155 * mm]))

    # ------------------------------------------------------------------ 5 sources
    s.append(PageBreak())
    s.append(Paragraph("5. Emission factor sources and dataset versions", H1))
    rows = [["Factor id", "Value", "Source", "Year / geography", "Boundary"]]
    for f in result["factors_used"]:
        rows.append([f"<font size=6>{f['factor_id']}</font>", f"{f['value']:.5g} {f['unit']}", f["source"],
                     f"{f['reporting_year']}<br/>{f['geography']}", f"<font size=6>{f['system_boundary']}</font>"])
    s.append(_table(rows, [38 * mm, 22 * mm, 42 * mm, 30 * mm, W - 132 * mm]))
    versions = sorted({f["dataset_version"] for f in result["factors_used"]})
    s.append(Spacer(1, 3))
    s.append(Paragraph(f"<b>Dataset versions used:</b> {', '.join(versions)}. Factor set {result['factor_set_version']}, "
                       f"engine {result['engine_version']}, calculated {result['calculated_at']}.", P))

    # ------------------------------------------------------------------ 6 assumptions & exclusions
    s.append(Paragraph("6. Assumptions and exclusions", H1))
    s.append(Paragraph("<b>Assumptions</b>", P))
    for a in result["assumptions"]:
        s.append(Paragraph(f"• {a}", P))
    line_notes = sorted({n for l in result["lines"] for n in l["notes"]})
    if line_notes:
        s.append(Paragraph("<b>Entry-specific notes</b>", P))
        for n in line_notes[:25]:
            s.append(Paragraph(f"• {n}", SMALL))
    s.append(Paragraph("<b>Exclusions</b>", P))
    for e in result["exclusions"]:
        s.append(Paragraph(f"• {e}", P))

    # ------------------------------------------------------------------ 7 data quality
    s.append(Paragraph("7. Actual vs. estimated data, data quality and uncertainty", H1))
    dtb = result["data_type_breakdown"]
    rows = [["Activity data type", "Emissions (kg CO<sub>2</sub>e)", "Share", "Lines"]] + \
           [[k.title(), fmt(v["emissions_kg"]), f"{v['share_pct']:.1f}%", int(v["lines"])] for k, v in dtb.items()]
    s.append(_table(rows, [50 * mm, 40 * mm, 30 * mm, 25 * mm]))
    dq = result["data_quality"]
    s.append(Spacer(1, 3))
    s.append(Paragraph(
        f"Emissions-weighted factor data-quality score: <b>{dq.get('weighted_score') or '–'}</b> ({(dq.get('label') or 'n/a')}; "
        f"{dq.get('scale')}). Share of emissions calculated with international proxy factors: {dq.get('proxy_factor_share_pct')}%. "
        f"Qualitative uncertainty rating: <b>{dq.get('uncertainty_rating')}</b>. Scores follow a pedigree approach "
        "(geographical, temporal and technological representativeness and source reliability, 1 = best, 5 = worst). "
        "Most sources do not publish statistical uncertainty ranges, so no numerical confidence interval is claimed.", P))
    errs = [i for i in result["issues"] if i["level"] in ("error", "warning")]
    if errs:
        s.append(Paragraph("<b>Data issues</b>", P))
        for i in errs[:20]:
            s.append(Paragraph(f"• [{i['level']}] {CAT_LABEL.get(i['category'], i['category'])}: {i['message']}", SMALL))

    # ------------------------------------------------------------------ 8 recommendations
    s.append(PageBreak())
    s.append(Paragraph("8. Sustainability recommendations", H1))
    s.append(Paragraph("Recommendations are generated from this conference's emission breakdown and quantified with the "
                       "scenario engine using the same factors.", SMALL))
    for r in recommendations:
        pot = (f" — estimated reduction up to <b>{r['potential_reduction_kg'] / 1000:,.2f} t CO<sub>2</sub>e "
               f"({r['potential_reduction_pct']:.1f}%, {r.get('potential_basis') or 'location-based'})</b> "
               f"[{r['scenario_title']}]") if r.get("potential_reduction_kg") else ""
        block = [Paragraph(f"<b>{r['rank']}. {r['title']}</b> <font color='#6b7280'>({r['category_label']})</font>{pot}", P),
                 Paragraph(f"<i>Why:</i> {r['evidence']}", SMALL)]
        block += [Paragraph(f"• {a}", P) for a in r["actions"]]
        block.append(Spacer(1, 4))
        s.append(KeepTogether(block))

    # ------------------------------------------------------------------ 9 scenarios
    s.append(Paragraph("9. Scenario comparison (what-if analysis)", H1))
    rows = [["Scenario", "Baseline (t)", "Scenario (t)", "Reduction (t)", "Reduction", "Description"]]
    for sc in scenarios:
        if sc.get("error"):
            continue
        rows.append([sc["title"], fmt(sc["baseline_kg"] / 1000, 2), fmt(sc["scenario_kg"] / 1000, 2), fmt(sc["reduction_kg"] / 1000, 2),
                     f"{sc['reduction_pct']:.1f}%" + (f"<br/><font size=6>market: {sc['market_reduction_pct']:.1f}%</font>"
                                                      if sc.get("market_reduction_kg") and abs(sc["market_reduction_kg"] - sc["reduction_kg"]) > 0.5 else ""),
                     f"<font size=6>{sc['description']}</font>"])
    s.append(_table(rows, [40 * mm, 18 * mm, 18 * mm, 18 * mm, 18 * mm, W - 112 * mm]))
    sch = _scenario_chart(scenarios)
    if sch:
        s.append(Spacer(1, 4))
        s.append(_img(sch, W * 0.9, 90 * mm))

    # ------------------------------------------------------------------ 10 statement
    s.append(Paragraph("10. Reporting statement", H1))
    s.append(Paragraph(
        f"This report was generated on {generated} from calculation #{calc_id}. The stored calculation retains the exact "
        "input data and the identifier and value of every emission factor used, so the results are reproducible even after "
        "the factor database is updated. This is a self-declared, unverified estimate; third-party verification (e.g. to "
        "ISO 14064-3) is recommended before public claims. Offsets, if any, are reported separately and are not deducted from "
        "gross emissions.", P))
    doc.build(s, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()
