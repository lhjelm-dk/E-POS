"""Comparison view: side-by-side POS from ESL and Classic POS."""

from __future__ import annotations

import streamlit as st

from logic.pos_logic import classic_pos_product


def render_comparison(
    classic_pos: float | None = None,
    esl_pos: float | None = None,
    classic_bel: float | None = None,
    classic_pl: float | None = None,
    prospect_title: str = "Prospect",
    meta_basin: str = "",
    meta_analyst: str = "",
    meta_date: str = "",
) -> None:
    """Render side-by-side POS from Classic POS and ESL.

    classic_bel / classic_pl: ESL-derived Bel/Pl products for the range bar.
    Pass None for both when Classic POS is a ROSE override (point estimate only).
    """
    if classic_pos is None:
        probs = [
            st.session_state.get("classic_charge", 0.5),
            st.session_state.get("classic_closure", 0.5),
            st.session_state.get("classic_reservoir", 0.5),
            st.session_state.get("classic_retention", 0.5),
        ]
        classic_pos = classic_pos_product(probs)

    # ESL Italian flag masses — available after ESL rollup runs
    esl_sf = st.session_state.get("comparison_esl_total_for")
    esl_sa = st.session_state.get("comparison_esl_total_against")

    # Choose Classic POS bar type based on whether range data is available
    if classic_bel is not None and classic_pl is not None and classic_pos is not None:
        classic_entry = ("P(G, Classic)", "∏ pillar Policy P  [Bel — point — Pl]",
                         classic_pos, classic_bel, classic_pl, "classic_range")
    else:
        classic_entry = ("P(G, Classic)", "∏ pillar Policy P  (ROSE override — point estimate)",
                         classic_pos, None, None, "classic_point")

    from components.overview_table import render_overview_table

    render_overview_table(
        "comparison",
        {
            "methods": [
                # ESL: 6-tuple (name, formula, pos, sf, sa, render_type)
                ("P(G, ESL)", "S_for + w × White  [Italian Flag]", esl_pos, esl_sf, esl_sa, "esl"),
                classic_entry,
            ],
            "classic_pos": classic_pos,
            "esl_pos": esl_pos,
            "prospect_title": prospect_title,
            "meta_basin": meta_basin,
            "meta_analyst": meta_analyst,
            "meta_date": meta_date,
        },
    )
    st.caption(
        "**P(G, ESL)** is the primary method — it preserves the uncertainty structure of the "
        "evidence through aggregation and is fully traceable. "
        "**P(G, Classic)** is shown alongside for reporting continuity with peers familiar with "
        "Rose/GeoX — both numbers are valid for sign-off, and reporting both with the "
        "spread between them documents your data-quality signal."
    )


def render_comparison_dfi(
    *,
    prior_esl:     float | None,
    prior_classic: float | None,
    post_esl:      float | None,
    post_classic:  float | None,
    esl_sf:        float | None = None,
    esl_sa:        float | None = None,
    classic_bel:   float | None = None,
    classic_pl:    float | None = None,
    dhi_index:     float | None = None,
    dhi_strength:  float | None = None,
    dhi_volume:    float | None = None,
    prospect_title: str = "Prospect",
) -> None:
    """2×2 comparison table — rows = ESL / Classic, columns = Prior / Posterior.

    Renders when the DFI Update toggle is ON. Each cell shows the value with a
    visual cue (Italian Flag for ESL, range bar for Classic — same convention
    as the prior-only comparison table). Posterior cells additionally show the
    Δ vs the prior in the cell.
    """
    from components.overview_table import _esl_flag, _classic_range_flag, _classic_point_flag

    def _val(v: float | None) -> str:
        return f"{v*100:.1f}%" if v is not None else "—"

    def _delta_html(prior: float | None, post: float | None) -> str:
        if prior is None or post is None:
            return ""
        d = (post - prior) * 100
        color = "#16a34a" if d >= 0 else "#dc2626"
        sign  = "+" if d >= 0 else ""
        return (f"<div style='font-size:0.78rem;color:{color};margin-top:2px;'>"
                f"Δ {sign}{d:.1f}pp vs prior</div>")

    # Build the 4 visual flags / bars
    esl_prior_flag = (_esl_flag(esl_sf, esl_sa, dark=False)
                      if esl_sf is not None and esl_sa is not None else "—")
    if classic_bel is not None and classic_pl is not None and prior_classic is not None:
        classic_prior_bar = _classic_range_flag(classic_bel, prior_classic, classic_pl, dark=False)
    elif prior_classic is not None:
        classic_prior_bar = _classic_point_flag(prior_classic, dark=False)
    else:
        classic_prior_bar = "—"
    # Posterior cells use point-only bars (no range info available for the posterior)
    esl_post_bar     = _classic_point_flag(post_esl,     dark=False) if post_esl     is not None else "—"
    classic_post_bar = _classic_point_flag(post_classic, dark=False) if post_classic is not None else "—"

    # Build the 2×2 table HTML inline so we get tight visual control
    dhi_strip = ""
    if dhi_index is not None:
        # SAAM / DHI Index pathway
        dhi_strip = (
            f"<div style='background:#eff6ff;border:1px solid #bfdbfe;border-radius:6px;"
            f"padding:6px 10px;margin-bottom:8px;font-size:0.82rem;color:#1e3a8a;'>"
            f"<b>DFI update active</b> &nbsp;·&nbsp; DHI Index = <b>{dhi_index:+.0f}</b>"
        )
        if dhi_strength is not None:
            dhi_strip += f" &nbsp;·&nbsp; R_SAAM = <b>{dhi_strength:.2f}</b>"
        if dhi_volume is not None:
            dhi_strip += f" &nbsp;·&nbsp; DHI Volume Weight V = <b>{dhi_volume:.2f}</b>"
        dhi_strip += "</div>"
    elif dhi_strength is not None:
        # Characteristic-scoring pathway — show R_eff and DHI Score
        score_pct = (dhi_volume * 100) if dhi_volume is not None else None
        dhi_strip = (
            f"<div style='background:#eff6ff;border:1px solid #bfdbfe;border-radius:6px;"
            f"padding:6px 10px;margin-bottom:8px;font-size:0.82rem;color:#1e3a8a;'>"
            f"<b>DFI update active</b> &nbsp;·&nbsp; Source: <b>Characteristic scoring</b> "
            f"&nbsp;·&nbsp; R_eff = <b>{dhi_strength:.2f}</b>"
            + (f" &nbsp;·&nbsp; DHI Score = <b>{score_pct:.0f}%</b>" if score_pct is not None else "")
            + "</div>"
        )

    html = f"""
    <style>
      .cmp2x2 {{ width:100%; border-collapse:collapse; font-family:'Segoe UI',sans-serif; font-size:0.86rem; margin-top:4px; }}
      .cmp2x2 th, .cmp2x2 td {{ padding:10px 14px; border:1px solid #e5e7eb; vertical-align:middle; }}
      .cmp2x2 th {{ background:#111827; color:#fff; text-align:left; font-weight:600; }}
      .cmp2x2 td.rowlbl {{ background:#f9fafb; font-weight:700; }}
      .cmp2x2 td.val   {{ font-weight:600; font-size:0.96rem; }}
      .cmp-flagrow     {{ display:flex; align-items:center; gap:10px; }}
    </style>
    {dhi_strip}
    <table class='cmp2x2'>
      <thead>
        <tr>
          <th style='width:18%;'>Method</th>
          <th style='width:41%;'>Prior  <small style='font-weight:400;opacity:0.7;'>(before DFI)</small></th>
          <th style='width:41%;'>Posterior  <small style='font-weight:400;opacity:0.7;'>(P(G | DFI, …))</small></th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td class='rowlbl'>🟢 P(G, <b>ESL</b>)</td>
          <td>
            <div class='cmp-flagrow'>
              <span class='val'>{_val(prior_esl)}</span>
              {esl_prior_flag}
            </div>
          </td>
          <td>
            <div class='cmp-flagrow'>
              <span class='val'>{_val(post_esl)}</span>
              {esl_post_bar}
            </div>
            {_delta_html(prior_esl, post_esl)}
          </td>
        </tr>
        <tr>
          <td class='rowlbl'>📊 P(G, <b>Classic</b>)</td>
          <td>
            <div class='cmp-flagrow'>
              <span class='val'>{_val(prior_classic)}</span>
              {classic_prior_bar}
            </div>
          </td>
          <td>
            <div class='cmp-flagrow'>
              <span class='val'>{_val(post_classic)}</span>
              {classic_post_bar}
            </div>
            {_delta_html(prior_classic, post_classic)}
          </td>
        </tr>
      </tbody>
    </table>
    """
    st.markdown(html, unsafe_allow_html=True)
    st.caption(
        "Rows: ESL (primary method) and Classic (Rose-style multiplicative). "
        "Columns: prior (current geological assessment) vs posterior (after Bayesian "
        "DFI update). The Δ per cell is the change in percentage points. Posterior "
        "bars show only the point estimate — the Bel/Pl envelope is not defined "
        "after the DFI update."
    )


def render_comparison_agreement(
    classic_pos: float | None = None,
    esl_pos: float | None = None,
) -> None:
    """Render Agreement Analysis (commentary, divergence diagnosis, reporting recommendation)."""
    st.subheader("Agreement Analysis")
    available = {k: v for k, v in [("P(G, Classic)", classic_pos), ("P(G, ESL)", esl_pos)] if v is not None}
    if len(available) < 2:
        st.info("Complete at least two method tabs to compare. One method is sufficient for sign-off.")
        return

    vals = list(available.values())
    spread_pct = (max(vals) - min(vals)) * 100
    low_method = min(available, key=available.get)
    high_method = max(available, key=available.get)

    if spread_pct < 2:
        st.success(f"Excellent agreement — all methods within {spread_pct:.1f}%. Risk assessment is robust to methodological choice.")
    elif spread_pct < 5:
        st.info(f"Good agreement — methods diverge by {spread_pct:.1f}%. Minor differences likely from operator choice or evidence weighting.")
    elif spread_pct < 10:
        st.warning(f"Moderate divergence — {spread_pct:.1f}% spread. {low_method} is more conservative than {high_method}. Investigate which risk element drives the difference (use Tornado charts).")
    else:
        st.error(f"SIGNIFICANT DIVERGENCE — {spread_pct:.1f}% spread between methods. Do not report without investigation. Common causes: (1) ESL capturing conflicting evidence Classic POS ignores; (2) Different operator choices (min vs product) in ESL vs Classic; (3) Over-committed evidence (S_for + S_against > 1) on a key pillar.")

    if low_method != high_method:
        st.markdown(
            f"**{low_method}** gives the lowest estimate; **{high_method}** gives the highest. "
            f"This typically means {low_method} is capturing a risk or dependency that {high_method} does not model."
        )

    # Divergence diagnosis
    if "P(G, Classic)" in available and "P(G, ESL)" in available:
        delta_esl_vs_classic = (available["P(G, ESL)"] - available["P(G, Classic)"]) * 100
        if delta_esl_vs_classic < -3:
            st.markdown(
                f"**P(G, ESL) lower than P(G, Classic) by {abs(delta_esl_vs_classic):.1f}%:** "
                "ESL is capturing conflicting or ambiguous evidence that Classic averages out. "
                "Check for overcommitted (yellow overlap) elements in the ESL tab — these represent "
                "genuine conflicts that Classic POS cannot represent."
            )
        elif delta_esl_vs_classic > 3:
            st.markdown(
                f"**P(G, ESL) higher than P(G, Classic) by {delta_esl_vs_classic:.1f}%:** "
                "ESL white space (uncertainty) is being partially counted as support. "
                "Check the stance weight setting — is it calibrated against analogues?"
            )
    st.divider()
    st.subheader("Reporting Recommendation")
    classic_val = available.get("P(G, Classic)")
    if spread_pct < 5:
        if classic_val is not None:
            st.success(
                f"Good agreement — methods within {spread_pct:.1f}%. "
                f"Report P(G, Classic) ({classic_val*100:.1f}%) for booking. Document stance w used."
            )
        else:
            st.success("Methods agree. Report P(G, ESL) as the Policy P estimate. Document stance w used.")
    else:
        rec = f"report P(G, Classic) ({classic_val*100:.1f}%)" if classic_val is not None else "report the most conservative estimate"
        st.warning(
            f"Methods diverge by {spread_pct:.1f}%. Do not report a single number until divergence is explained. "
            f"Recommended: {rec} as primary, P(G, ESL) interval as secondary. "
            f"State which elements drive the spread in the risk narrative (use Tornado chart)."
        )
