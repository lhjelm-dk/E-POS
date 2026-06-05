"""Shared overview table component for Classic POS, ESL, Bayesian Network, and Comparison.

Rendered via st.components.v1.html() for pixel-precise control over colours, fonts,
flag widths, and pillar colour bands. All variants share the dark navy (#111827) design.
"""

from __future__ import annotations

import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Flag segment helpers
# ─────────────────────────────────────────────────────────────────────────────

def _flag_segments_esl(s_for: float, s_against: float) -> dict:
    """Return rounded integer percentages for ESL Italian flag segments."""
    sf = max(0.0, min(1.0, float(s_for)))
    sa = max(0.0, min(1.0, float(s_against)))
    total = sf + sa
    if total > 1.0:
        overlap = total - 1.0
        g = round((sf - overlap) * 100)
        r = round((sa - overlap) * 100)
        y = round(overlap * 100)
        w = 0
    else:
        g = round(sf * 100)
        r = round(sa * 100)
        y = 0
        w = round(max(0.0, 1.0 - sf - sa) * 100)
    diff = 100 - g - w - y - r
    g += diff
    return {"g": g, "w": w, "y": y, "r": r}


def _flag_segments_classic(probability: float) -> dict:
    """Return rounded integer percentages for Classic POS / BN confidence bar."""
    p = round(max(0.0, min(1.0, float(probability))) * 100)
    return {"g": p, "w": 100 - p, "y": 0, "r": 0}


def _flag_html(segs: dict, label: str, dark_label: bool = False) -> str:
    """Build the complete flag HTML (bar + label text) from segment dict."""
    lbl_class = "flag-lbl-dark" if dark_label else "flag-lbl"
    return (
        "<div class='flag-cell-wrap'>"
        "<div class='flag-bar'>"
        f"<div style='width:{segs['g']}%;background:#2e9d5b;height:100%;'></div>"
        f"<div style='width:{segs['w']}%;background:#f3f4f6;height:100%;'></div>"
        f"<div style='width:{segs['y']}%;background:#f6c343;height:100%;'></div>"
        f"<div style='width:{segs['r']}%;background:#b3261e;height:100%;'></div>"
        "</div>"
        f"<div class='{lbl_class}'>{label}</div>"
        "</div>"
    )


def _esl_flag(sf: float, sa: float, dark: bool = False) -> str:
    segs = _flag_segments_esl(sf, sa)
    label = f"G {segs['g']}% W {segs['w']}% R {segs['r']}%"
    if segs["y"] > 0:
        label += " ⚠"
    return _flag_html(segs, label, dark)


def _classic_flag(probability: float, dark: bool = False) -> str:
    segs = _flag_segments_classic(probability)
    label = f"P {segs['g']}%"
    return _flag_html(segs, label, dark)


def _classic_range_flag(bel: float, point: float, pl: float, dark: bool = False,
                        decimals: int = 0, show_point: bool = True) -> str:
    """4-segment bar showing the ESL-derived Classic POS confidence range.

    Segments (left to right):
      Dark green  — Bel (∏ S_for): committed minimum POS regardless of stance
      Light green — stance contribution: how much w lifts POS above Bel
      Light grey  — remaining white: further potential gain if w → 1
      Dark red    — certain failure (1 − Pl = ∏ S_against contribution): lost even at w=1
    """
    bel_pct   = max(0, min(100, round(bel   * 100)))
    point_pct = max(0, min(100, round(point * 100)))
    pl_pct    = max(0, min(100, round(pl    * 100)))
    seg1 = bel_pct                           # committed success floor
    seg2 = max(0, point_pct - bel_pct)       # stance contribution above Bel
    seg3 = max(0, pl_pct    - point_pct)     # remaining white above point
    seg4 = max(0, 100       - pl_pct)        # committed failure ceiling
    total = seg1 + seg2 + seg3 + seg4
    if total != 100:
        seg1 = max(0, seg1 + (100 - total))  # absorb rounding into floor
    lbl_class = "flag-lbl-dark" if dark else "flag-lbl"
    # Labels can carry decimals (e.g. the DFI prior/posterior envelopes use 1 dp
    # to match the posterior headline number); the bar widths stay integer.
    # show_point=False drops the POS term when the point value is already shown
    # as the big number above the flag (the DFI before/after rows).
    if show_point:
        label = (f"Bel {bel*100:.{decimals}f}% · POS {point*100:.{decimals}f}% "
                 f"· Pl {pl*100:.{decimals}f}%")
    else:
        label = f"Bel {bel*100:.{decimals}f}% · Pl {pl*100:.{decimals}f}%"
    return (
        "<div class='flag-cell-wrap'>"
        "<div class='flag-bar'>"
        f"<div style='width:{seg1}%;background:#15803d;height:100%;'></div>"
        f"<div style='width:{seg2}%;background:#86efac;height:100%;'></div>"
        f"<div style='width:{seg3}%;background:#f3f4f6;height:100%;'></div>"
        f"<div style='width:{seg4}%;background:#b3261e;height:100%;'></div>"
        "</div>"
        f"<div class='{lbl_class}'>{label}</div>"
        "</div>"
    )


def _classic_point_flag(probability: float, dark: bool = False) -> str:
    """Plain Classic POS bar for ROSE override values — no ESL uncertainty decomposition."""
    p = max(0, min(100, round(probability * 100)))
    lbl_class = "flag-lbl-dark" if dark else "flag-lbl"
    return (
        "<div class='flag-cell-wrap'>"
        "<div class='flag-bar'>"
        f"<div style='width:{p}%;background:#16a34a;height:100%;'></div>"
        f"<div style='width:{100-p}%;background:#f3f4f6;height:100%;'></div>"
        "</div>"
        f"<div class='{lbl_class}'>POS {p}% · point estimate only</div>"
        "</div>"
    )



# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Shared table styles (dark navy #111827 design)
# ─────────────────────────────────────────────────────────────────────────────

def _shared_table_styles() -> str:
    """Shared CSS for all overview table variants. Single dark navy design."""
    return """
  .ov-wrap {
    font-family: "Segoe UI", Tahoma, Arial, sans-serif;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid #111827;
  }
  .ov-prospect-header {
    background: #111827;
    padding: 14px 18px;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
  }
  .ov-prospect-name {
    font-size: 32px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.01em;
  }
  .ov-meta-block {
    font-size: 14px;
    color: #cbd5e1;
    text-align: right;
    line-height: 1.6;
  }
  .ov-table {
    width: 100%;
    border-collapse: collapse;
    font-size: clamp(13px, 1.1vw, 16px);
  }
  .ov-table .hdr-group th {
    background: #111827;
    color: #ffffff;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    padding: 8px 12px;
    text-align: center;
    border-bottom: 1px solid #374151;
  }
  .ov-table .hdr-group th.col-label {
    text-align: left;
    font-size: 11px;
    letter-spacing: 0.05em;
    color: #9ca3af;
    border-bottom: 2px solid #374151;
  }
  .ov-table .hdr-sub th {
    background: #111827;
    color: #d1d5db;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 6px 12px;
    text-align: center;
    border-bottom: 2px solid #374151;
  }
  .ov-table .sep-col {
    width: 8px;
    padding: 0;
  }
  .ov-table thead .sep-col,
  .ov-table .result-row .sep-col,
  .ov-table .summary-row .sep-col {
    background: #111827;
  }
  /* Match the 2px header underline so there is no 1px notch at the divider. */
  .ov-table thead .sep-col {
    border-bottom: 2px solid #374151;
  }
  .ov-table .data-row .sep-col {
    background: #ffffff;
  }
  .ov-table .data-row td {
    padding: 10px 12px;
    border-bottom: 1px solid #e5e7eb;
    background: #ffffff;
    vertical-align: middle;
  }
  .ov-table .data-row td.pillar-name {
    font-weight: 600;
    font-size: 14px;
    color: #111827;
    min-width: 120px;
  }
  .ov-table .data-row td.prob-cell {
    text-align: center;
    font-size: 15px;
    color: #111827;
    font-weight: 500;
    white-space: nowrap;
  }
  .ov-table .data-row td.flag-cell {
    text-align: center;
    vertical-align: middle;
    padding: 8px 12px;
  }
  .ov-table .result-row td,
  .ov-table .summary-row td {
    background: #111827;
    color: #ffffff;
    font-weight: 700;
    padding: 10px 14px;
    border-bottom: none;
    vertical-align: middle;
  }
  .ov-table .result-row td.row-label,
  .ov-table .summary-row td.row-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #9ca3af;
    vertical-align: middle;
    min-width: 80px;
  }
  .ov-table .result-row td.result-value,
  .ov-table .summary-row td.result-value {
    text-align: center;
    vertical-align: middle;
  }
  .ov-table .result-row td .result-label-text,
  .ov-table .summary-row td .result-label-text {
    font-size: 12px;
    font-weight: 600;
    color: #d1d5db;
    display: block;
  }
  .ov-table .result-row td .result-number,
  .ov-table .summary-row td .result-number {
    font-size: 20px;
    font-weight: 700;
    color: #ffffff;
    display: block;
    margin: 2px 0;
  }
  .ov-table .sep-row td {
    height: 2px;
    background: #374151;
    padding: 0;
  }
  .flag-bar {
    display: flex;
    height: 12px;
    width: 110px;
    border: 1px solid #555555;
    border-radius: 3px;
    overflow: hidden;
    margin: 0 auto;
  }
  .flag-lbl {
    font-size: 11px;
    color: #9ca3af;
    margin-top: 3px;
    text-align: center;
    white-space: nowrap;
  }
  .flag-lbl-dark {
    font-size: 11px;
    color: #cbd5e1;
    margin-top: 3px;
    text-align: center;
    white-space: nowrap;
  }
  .flag-cell-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
  }
"""


def render_overview_table(method: str, data: dict) -> None:
    """Render method-specific overview table with shared visual style.

    Args:
        method: One of "classic_pos", "esl", "comparison"
        data: Method-specific data dict (see docstrings in each _render_* function)
    """
    if method == "classic_pos":
        _render_classic_pos_table(data)
    elif method == "esl":
        _render_esl_table(data)
    elif method == "comparison":
        _render_comparison_table(data)
    else:
        st.warning(f"Unknown method: {method}")


# ─────────────────────────────────────────────────────────────────────────────
# ESL variant — Italian flags (G/W/Y/R)
# ─────────────────────────────────────────────────────────────────────────────

def _render_esl_table(data: dict) -> None:
    """ESL overview table — full Italian flags from support_for/support_against.

    Data: pillars=[{name, play_pos, cond_pos, play_support_for?, play_support_against?,
                   cond_support_for?, cond_support_against?} or precomputed play_flag/label],
         play_for, play_against, cond_for, cond_against, total_for, total_against,
         play_pos_pct, cond_pos_pct, total_pos_pct, interval_text, method_label,
         prospect_title, meta_basin, meta_analyst, meta_date
    """
    from components.colors import PILLAR_COLORS

    pillars = data.get("pillars", [])
    method_label = data.get("method_label", "Evidence Support Logic")
    play_pos_pct = data.get("play_pos_pct", 0.0)
    cond_pos_pct = data.get("cond_pos_pct", 0.0)
    total_pos_pct = data.get("total_pos_pct", 0.0)
    interval_txt = data.get("interval_text", "")
    prospect_title = data.get("prospect_title", "Prospect")
    meta_basin = data.get("meta_basin", "")
    meta_analyst = data.get("meta_analyst", "")
    meta_date = data.get("meta_date", "")

    play_for = data.get("play_for")
    play_against = data.get("play_against")
    cond_for = data.get("cond_for")
    cond_against = data.get("cond_against")
    total_for = data.get("total_for")
    total_against = data.get("total_against")

    def pillar_flag(p: dict, col: str) -> str:
        sf = p.get(f"{col}_support_for")
        sa = p.get(f"{col}_support_against")
        if sf is not None and sa is not None:
            return _esl_flag(sf, sa, dark=False)
        flag = p.get(f"{col}_flag", "")
        label = p.get(f"{col}_label", "")
        if flag and label:
            return f"<div class='flag-cell-wrap'>{flag}<div class='flag-lbl'>{label}</div></div>"
        return "—"

    def result_flag(sf: float | None, sa: float | None) -> str:
        if sf is not None and sa is not None:
            return _esl_flag(sf, sa, dark=True)
        return ""

    rows_html = ""
    for p in pillars:
        name = p.get("name", "?")
        pkey = name
        pcolor = PILLAR_COLORS.get(pkey, "#e5e7eb")
        play_pct = p.get("play_pos", 0) * 100 if isinstance(p.get("play_pos"), (int, float)) else 0
        cond_pct = p.get("cond_pos", 0) * 100 if isinstance(p.get("cond_pos"), (int, float)) else 0
        play_flag_html = pillar_flag(p, "play")
        cond_flag_html = pillar_flag(p, "cond")
        rows_html += (
            f"<tr class='data-row' style='background-color:{pcolor}14;'>"
            f"<td class='pillar-name' style='border-left:5px solid {pcolor};'>{name}</td>"
            f"<td class='prob-cell'>{play_pct:.0f}%</td>"
            f"<td class='flag-cell'>{play_flag_html}</td>"
            f"<td class='sep-col'></td>"
            f"<td class='prob-cell'>{cond_pct:.0f}%</td>"
            f"<td class='flag-cell'>{cond_flag_html}</td>"
            f"</tr>"
        )

    play_flag_result = result_flag(play_for, play_against) if play_for is not None else ""
    cond_flag_result = result_flag(cond_for, cond_against) if cond_for is not None else ""
    total_flag_result = result_flag(total_for, total_against) if total_for is not None else ""

    if play_flag_result and play_for is not None and play_against is not None:
        segs_pc = _flag_segments_esl(play_for, play_against)
        g_pc, w_pc, r_pc = segs_pc["g"], segs_pc["w"], segs_pc["r"]
    else:
        g_pc, w_pc, r_pc = 0, 100, 0
    if cond_flag_result and cond_for is not None and cond_against is not None:
        segs_cp = _flag_segments_esl(cond_for, cond_against)
        g_cp, w_cp, r_cp = segs_cp["g"], segs_cp["w"], segs_cp["r"]
    else:
        g_cp, w_cp, r_cp = 0, 100, 0
    if total_flag_result and total_for is not None and total_against is not None:
        segs_tot = _flag_segments_esl(total_for, total_against)
        g_tot, w_tot, r_tot = segs_tot["g"], segs_tot["w"], segs_tot["r"]
    else:
        g_tot, w_tot, r_tot = 0, 100, 0

    # ── Optional DFI-update section (appended only when caller supplies `dfi`) ──
    # dfi = {method_label, esl_prior, esl_post, esl_delta_pp, classic_prior,
    #        classic_post, classic_delta_pp, bel?, pl?, diagnostics?}
    dfi = data.get("dfi")
    dfi_rows_html = ""
    if dfi:
        m_label = dfi.get("method_label", "DFI update")
        diag = dfi.get("diagnostics", "")

        def _dfi_row(emoji: str, name: str, prior: float, post: float,
                     dpp: float, prior_env=None, post_env=None) -> str:
            # prior_env / post_env = (bel, pl) → render a Bel·POS·Pl range flag so the
            # posterior gets the *same* envelope representation as the prior.
            dc = "#22c55e" if dpp >= 0 else "#f87171"   # brighter for the dark row
            has_env = bool(prior_env and prior_env[0] is not None and prior_env[1] is not None)
            # Prior — the "before"; muted via lighter-grey text only (NO opacity,
            # so the cell keeps the same dark navy as the rest of the row).
            if has_env:
                # Big muted-grey POS number above the flag, mirroring the
                # posterior layout (white number above its flag).
                flag_html = _classic_range_flag(prior_env[0], prior, prior_env[1],
                                                decimals=1, show_point=False)
                prior_inner = (
                    f"<div style='font-size:20px;font-weight:700;color:#ffffff;"
                    f"line-height:1.1;'>{prior*100:.1f}%</div>{flag_html}"
                )
            else:
                prior_inner = (f"<span style='color:#9ca3af;font-size:18px;"
                               f"font-weight:700;'>{prior*100:.1f}%</span>")
            prior_cell = (f"<td colspan='2' style='text-align:center;'>"
                          f"{prior_inner}</td>")
            # Posterior — for the flag-bearing P(G, ESL) row it is the headline
            # (large WHITE number). For the point-only P(G, Classic) row it is a
            # secondary read-out, so it matches the prior's muted grey.
            if post_env and post_env[0] is not None and post_env[1] is not None:
                post_flag = _classic_range_flag(post_env[0], post, post_env[1],
                                                decimals=1, show_point=False)
                post_color = "#ffffff"
            else:
                post_flag = ""
                post_color = "#9ca3af"
            post_cell = (
                "<td style='text-align:center;'>"
                f"<div style='font-size:20px;font-weight:800;color:{post_color};"
                f"line-height:1.1;'>{post*100:.1f}%</div>"
                f"{post_flag}</td>"
            )
            # Dark navy row, matching the RESULT / SUMMARY rows. The Δ uses only a
            # signed +/- value (the sign already carries direction — no arrow).
            return (
                "<tr class='result-row'>"
                f"<td class='row-label'>{emoji} {name}</td>"
                + prior_cell
                + "<td class='sep-col'></td>"
                + post_cell
                + f"<td style='text-align:center;color:{dc};font-weight:800;font-size:15px;'>"
                f"{dpp:+.1f}</td>"
                "</tr>"
            )

        diag_html = (f"<span style='font-weight:400;color:#9ca3af;'> &nbsp;·&nbsp; {diag}</span>"
                     if diag else "")
        dfi_rows_html = (
            "<tr class='sep-row'><td colspan='6'></td></tr>"
            f"<tr class='hdr-group'><th class='col-label' colspan='6' "
            f"style='text-align:left;color:#ffffff;'>DFI UPDATE — {m_label}{diag_html}</th></tr>"
            "<tr class='hdr-sub'>"
            "<th style='text-align:left;'>Method</th>"
            "<th colspan='2'>Prior P(G) · before DFI</th>"
            "<th class='sep-col'></th>"
            "<th>Posterior P(G | DFI) · after</th>"
            "<th>Δ (pp)</th>"
            "</tr>"
            + _dfi_row("🟢", "P(G, ESL)", dfi.get("esl_prior", 0.0),
                       dfi.get("esl_post", 0.0), dfi.get("esl_delta_pp", 0.0),
                       prior_env=(dfi.get("bel"), dfi.get("pl")),
                       post_env=(dfi.get("esl_post_bel"), dfi.get("esl_post_pl")))
            + _dfi_row("📊", "P(G, Classic)", dfi.get("classic_prior", 0.0),
                       dfi.get("classic_post", 0.0), dfi.get("classic_delta_pp", 0.0))
        )

    html = f"""<style>{_shared_table_styles()}</style>
<div class="ov-wrap">
  <div class="ov-prospect-header">
    <div class="ov-prospect-name">{prospect_title}</div>
    <div class="ov-meta-block">
      <div>Method: {method_label}</div>
      <div>{meta_basin}</div>
      <div>{meta_analyst}</div>
      <div>{meta_date}</div>
    </div>
  </div>
  <table class="ov-table">
    <thead>
      <tr class="hdr-group">
        <th class="col-label" rowspan="2">Chance Element</th>
        <th colspan="2">Play</th>
        <th class="sep-col" rowspan="2"></th>
        <th colspan="2">Prospect Given Play</th>
      </tr>
      <tr class="hdr-sub">
        <th>Probability</th>
        <th>ESL flag</th>
        <th>Probability</th>
        <th>ESL flag</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
      <tr class="result-row">
        <td class="row-label">Result</td>
        <td class="result-value" colspan="2">
          <span class="result-label-text">Play Chance</span>
          <span class="result-number">{play_pos_pct:.0f}%</span>
          {play_flag_result if play_flag_result else f'<div class="flag-cell-wrap"><div class="flag-bar"><div style="width:{g_pc}%;background:#2e9d5b;height:100%;"></div><div style="width:{w_pc}%;background:#f3f4f6;height:100%;"></div><div style="width:0%;background:#f6c343;height:100%;"></div><div style="width:{r_pc}%;background:#b3261e;height:100%;"></div></div><div class="flag-lbl-dark">G {g_pc}% W {w_pc}% R {r_pc}%</div></div>'}
        </td>
        <td class="sep-col"></td>
        <td class="result-value" colspan="2">
          <span class="result-label-text">Conditional Prospect</span>
          <span class="result-number">{cond_pos_pct:.0f}%</span>
          {cond_flag_result if cond_flag_result else f'<div class="flag-cell-wrap"><div class="flag-bar"><div style="width:{g_cp}%;background:#2e9d5b;height:100%;"></div><div style="width:{w_cp}%;background:#f3f4f6;height:100%;"></div><div style="width:0%;background:#f6c343;height:100%;"></div><div style="width:{r_cp}%;background:#b3261e;height:100%;"></div></div><div class="flag-lbl-dark">G {g_cp}% W {w_cp}% R {r_cp}%</div></div>'}
        </td>
      </tr>
      <tr class="sep-row"><td colspan="6"></td></tr>
      <tr class="summary-row">
        <td class="row-label">Summary</td>
        <td class="result-value" colspan="2">
          <span class="result-label-text">P(G, ESL)</span>
          <span class="result-number">{total_pos_pct:.0f}%</span>
          {total_flag_result if total_flag_result else f'<div class="flag-cell-wrap"><div class="flag-bar"><div style="width:{g_tot}%;background:#2e9d5b;height:100%;"></div><div style="width:{w_tot}%;background:#f3f4f6;height:100%;"></div><div style="width:0%;background:#f6c343;height:100%;"></div><div style="width:{r_tot}%;background:#b3261e;height:100%;"></div></div><div class="flag-lbl-dark">G {g_tot}% W {w_tot}% R {r_tot}%</div></div>'}
        </td>
        <td class="sep-col"></td>
        <td class="result-value" colspan="2">
          <span class="result-label-text">Pg Interval (Bel–Pl)</span>
          <span class="result-number">{interval_txt}</span>
        </td>
      </tr>
      {dfi_rows_html}
    </tbody>
  </table>
</div>"""

    # scrolling=True is a safety net: if a narrow viewport makes the table taller
    # than the fixed iframe height, the user gets a scrollbar instead of a clip.
    st.components.v1.html(html, height=(820 if dfi else 600), scrolling=True)


# ─────────────────────────────────────────────────────────────────────────────
# Classic POS variant — confidence bars (green/white only)
# ─────────────────────────────────────────────────────────────────────────────

def _render_classic_pos_table(data: dict) -> None:
    """Classic POS: Play | Prospect Given Play layout, confidence bars (green/white)."""
    from components.colors import PILLAR_COLORS

    pillars = data.get("pillars", [])
    total_pos = data.get("total_pos", 0.0)
    play_pos_pct = data.get("play_pos_pct")
    cond_pos_pct = data.get("cond_pos_pct")
    prospect_title = data.get("prospect_title", "Prospect")
    meta_basin = data.get("meta_basin", "")
    meta_analyst = data.get("meta_analyst", "")
    meta_date = data.get("meta_date", "")

    has_play_cond = pillars and "play_pos" in pillars[0]
    play_chance = (play_pos_pct / 100.0) if play_pos_pct is not None else None
    cond_chance = (cond_pos_pct / 100.0) if cond_pos_pct is not None else None

    rows_html = ""
    for p in pillars:
        name = p.get("name", "?")
        pkey = name
        pcolor = PILLAR_COLORS.get(pkey, "#e5e7eb")
        if has_play_cond:
            play_v   = p.get("play_pos", 0.5)
            cond_v   = p.get("cond_pos", 0.5)
            play_bel = p.get("play_bel")
            play_pl  = p.get("play_pl")
            cond_bel = p.get("cond_bel")
            cond_pl  = p.get("cond_pl")
            play_flag_html = (
                _classic_range_flag(play_bel, play_v, play_pl, dark=False)
                if play_bel is not None and play_pl is not None
                else _classic_flag(play_v, dark=False)
            )
            cond_flag_html = (
                _classic_range_flag(cond_bel, cond_v, cond_pl, dark=False)
                if cond_bel is not None and cond_pl is not None
                else _classic_flag(cond_v, dark=False)
            )
        else:
            play_v = p.get("p_pct", 0.5)
            cond_v = None
            play_flag_html = _classic_flag(play_v, dark=False)
            cond_flag_html = "—"
        play_pct = play_v * 100
        cond_pct = cond_v * 100 if cond_v is not None else "—"
        cond_pct_str = f"{cond_pct:.0f}%" if isinstance(cond_pct, (int, float)) else cond_pct
        rows_html += (
            f"<tr class='data-row' style='background-color:{pcolor}14;'>"
            f"<td class='pillar-name' style='border-left:5px solid {pcolor};'>{name}</td>"
            f"<td class='prob-cell'>{play_pct:.0f}%</td>"
            f"<td class='flag-cell'>{play_flag_html}</td>"
            f"<td class='sep-col'></td>"
            f"<td class='prob-cell'>{cond_pct_str}</td>"
            f"<td class='flag-cell'>{cond_flag_html}</td>"
            f"</tr>"
        )

    play_flag_res  = _classic_flag(play_chance,  dark=True) if play_chance  is not None else ""
    cond_flag_res  = _classic_flag(cond_chance,  dark=True) if cond_chance  is not None else ""
    total_flag_res = _classic_flag(total_pos, dark=True)

    play_str = f"{play_pos_pct:.0f}%" if play_pos_pct is not None else "—"
    cond_str = f"{cond_pos_pct:.0f}%" if cond_pos_pct is not None else "—"

    html = f"""<style>{_shared_table_styles()}</style>
<div class="ov-wrap">
  <div class="ov-prospect-header">
    <div class="ov-prospect-name">{prospect_title}</div>
    <div class="ov-meta-block">
      <div>Method: Classic POS (product)</div>
      <div>{meta_basin}</div>
      <div>{meta_analyst}</div>
      <div>{meta_date}</div>
    </div>
  </div>
  <table class="ov-table">
    <thead>
      <tr class="hdr-group">
        <th class="col-label" rowspan="2">Chance Element</th>
        <th colspan="2">Play</th>
        <th class="sep-col" rowspan="2"></th>
        <th colspan="2">Prospect Given Play</th>
      </tr>
      <tr class="hdr-sub">
        <th>Probability</th>
        <th>Confidence</th>
        <th>Probability</th>
        <th>Confidence</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
      <tr class="result-row">
        <td class="row-label">Result</td>
        <td class="result-value" colspan="2">
          <span class="result-label-text">Play Chance</span>
          <span class="result-number">{play_str}</span>
          {play_flag_res}
        </td>
        <td class="sep-col"></td>
        <td class="result-value" colspan="2">
          <span class="result-label-text">Conditional Prospect</span>
          <span class="result-number">{cond_str}</span>
          {cond_flag_res}
        </td>
      </tr>
      <tr class="sep-row"><td colspan="6"></td></tr>
      <tr class="summary-row">
        <td class="row-label">Summary</td>
        <td class="result-value" colspan="2">
          <span class="result-label-text">P(G, Classic)</span>
          <span class="result-number">{total_pos*100:.1f}%</span>
          {total_flag_res}
        </td>
        <td class="sep-col"></td>
        <td class="result-value" colspan="2">
          <span class="result-label-text">Combination</span>
          <span class="result-number">Play × Conditional</span>
        </td>
      </tr>
    </tbody>
  </table>
</div>"""

    st.components.v1.html(html, height=600, scrolling=False)


# ─────────────────────────────────────────────────────────────────────────────
# Comparison variant — method rows (Section 11)
# ─────────────────────────────────────────────────────────────────────────────

def _render_comparison_table(data: dict) -> None:
    """Comparison tab: one row per method, POS + confidence bar.

    Data: methods=[(name, formula, pos)], prospect_title, meta_basin, meta_analyst, meta_date
    """
    methods = data.get("methods", [
        ("P(G, Classic)", "Play × Conditional (product of Policy P)", data.get("classic_pos")),
        ("P(G, ESL)", "S_for + w × White on combined masses", data.get("esl_pos")),
    ])
    prospect_title = data.get("prospect_title", "Prospect")
    meta_basin = data.get("meta_basin", "")
    meta_analyst = data.get("meta_analyst", "")
    meta_date = data.get("meta_date", "")

    emoji_map = {
        "P(G, Classic)": "📊", "P(G, ESL)": "🟢",
        "Classic POS": "📊", "ESL": "🟢",  # legacy aliases
    }
    rows_html = ""
    for i, item in enumerate(methods):
        if isinstance(item, (list, tuple)) and len(item) >= 5:
            # ESL extended tuple: (name, formula, pos, support_for, support_against)
            name, formula, pos_val, sf, sa = item[0], item[1], item[2], item[3], item[4]
        elif isinstance(item, (list, tuple)) and len(item) >= 3:
            name, formula, pos_val = item[0], item[1], item[2]
            sf, sa = None, None
        else:
            name = item.get("name", "?")
            formula = item.get("formula", "")
            pos_val = item.get("pos")
            sf, sa = None, None
        emoji = emoji_map.get(name, "•")
        val_str = f"{pos_val*100:.1f}%" if pos_val is not None else "—"
        render_type = item[5] if isinstance(item, (list, tuple)) and len(item) >= 6 else (
            "esl" if (sf is not None and sa is not None) else "classic_point"
        )
        if render_type == "esl" and sf is not None and sa is not None:
            bar = _esl_flag(sf, sa, dark=False)
        elif render_type == "classic_range" and sf is not None and sa is not None and pos_val is not None:
            # sf=bel, sa=pl in the classic_range tuple layout
            bar = _classic_range_flag(sf, pos_val, sa, dark=False)
        elif pos_val is not None:
            bar = _classic_point_flag(pos_val, dark=False)
        else:
            bar = "—"
        bg = "#f9fafb" if i % 2 == 1 else "#ffffff"
        rows_html += (
            f"<tr class='data-row' style='background:{bg};'>"
            f"<td style='font-weight:600;'>{emoji} {name}</td>"
            f"<td style='font-size:12px;color:#6b7280;'>{formula}</td>"
            f"<td class='prob-cell' style='font-size:17px;font-weight:700;'>{val_str}</td>"
            f"<td class='flag-cell'>{bar}</td>"
            f"</tr>"
        )

    html = f"""<style>{_shared_table_styles()}</style>
<div class="ov-wrap">
  <div class="ov-prospect-header">
    <div class="ov-prospect-name">{prospect_title}</div>
    <div class="ov-meta-block">
      <div>Cross-method comparison</div>
      <div>{meta_basin}</div>
      <div>{meta_analyst}</div>
      <div>{meta_date}</div>
    </div>
  </div>
  <table class="ov-table">
    <thead>
      <tr class="hdr-group">
        <th class="col-label">Method</th>
        <th>Combination</th>
        <th>POS</th>
        <th>Uncertainty profile  <span style="font-weight:400;font-size:10px;">(ESL: G/W/R Italian Flag · Classic: Bel–POS–Pl range)</span></th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
      <tr class="result-row">
        <td class="row-label">Summary</td>
        <td colspan="3" class="result-value">
          <span class="result-label-text">See Reporting Recommendation below</span>
        </td>
      </tr>
    </tbody>
  </table>
</div>"""

    st.components.v1.html(html, height=600, scrolling=False)
