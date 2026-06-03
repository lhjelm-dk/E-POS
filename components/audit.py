"""Audit trail and sign-off component — assessment lock, summary report export."""

from __future__ import annotations

import datetime
import streamlit as st

from logic.pos_policy import policy_pos as _pos_fn, resolve_stance


def render_audit_panel(pos: float, method: str, prospect_title: str) -> None:
    """Render assessment sign-off panel with lock mechanism."""
    st.subheader("Assessment Sign-off")
    st.caption(
        "Complete this section before submitting for peer review.",
        help=("Locked sign-off records are held in the current session only. "
              "To preserve permanently, export via Dashboard → Prospect Risk Data → "
              "Download Full Assessment CSV before closing the browser tab. "
              "The CSV contains the sign-off block alongside the full ESL state."),
    )

    col1, col2 = st.columns(2)
    with col1:
        reviewer = st.text_input("Reviewer name", key=f"audit_reviewer_{method}")
        review_date = st.date_input(
            "Review date",
            value=datetime.date.today(),
            key=f"audit_date_{method}",
        )
    with col2:
        confidence = st.select_slider(
            "Analyst confidence in this assessment",
            options=["Low", "Medium", "High"],
            value="Medium",
            key=f"audit_confidence_{method}",
        )
        peer_reviewed = st.checkbox("Peer reviewed", key=f"audit_peer_{method}")

    key_uncertainties = st.text_area(
        "Key uncertainties (top 3)",
        key=f"audit_uncertainties_{method}",
        placeholder=(
            "1. Source maturity uncertain — no calibration wells within 50km\n"
            "2. Fault seal unproven — no fault gouge data\n"
            "3. Closure depth uncertain — velocity model constrained by 2D only"
        ),
    )
    data_gaps = st.text_area(
        "Data gaps that would most change this assessment",
        key=f"audit_gaps_{method}",
        placeholder="1D seismic reprocessing; source rock geochemistry from nearest well",
    )

    if st.button(f"Lock assessment — {method} = {pos*100:.1f}%", key=f"audit_lock_{method}"):
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        st.session_state[f"locked_{method}"] = {
            "pos": pos,
            "reviewer": reviewer,
            "date": str(review_date),
            "timestamp": timestamp,
            "confidence": confidence,
            "peer_reviewed": peer_reviewed,
            "uncertainties": key_uncertainties,
            "data_gaps": data_gaps,
        }
        st.success(f"Assessment locked at {pos*100:.1f}% on {timestamp}. This record cannot be changed retroactively.")

    locked = st.session_state.get(f"locked_{method}")
    if locked:
        st.info(
            f"LOCKED: {locked['reviewer']} on {locked['date']} "
            f"at {locked['pos']*100:.1f}% ({locked['timestamp']})"
        )


def render_summary_report(
    prospect_title: str,
    models: dict | None,
    classic_pos: float | None = None,
    esl_pos: float | None = None,
    uw: float | None = None,
) -> None:
    """Render one-page summary report for export.

    Args:
        uw: stance weight for per-element POS display. Defaults to resolve_stance().
    """
    if uw is None:
        uw = resolve_stance()

    st.subheader("One-Page Summary Report")
    st.markdown("**Export this summary for peer review or investment committee.**")

    lines = [
        f"# E-POS Assessment: {prospect_title}",
        "# Evidence-supported probability of success for geological prospects.",
        "# By Lars Hjelm",
        f"Date: {datetime.date.today()}",
        "",
        "## Results",
        f"- P(G, Classic): {classic_pos*100:.1f}%" if classic_pos is not None else "",
        f"- P(G, ESL): {esl_pos*100:.1f}%" if esl_pos is not None else "",
        "",
        f"## Top risk elements (lowest Policy P at w = {uw:.2f})",
        "## — same Policy P values feed both P(G, ESL) and P(G, Classic) at element level",
    ]

    if models and models.get("conditional"):
        leaves = []
        for cat, elems in models["conditional"].items():
            for e in elems:
                p = _pos_fn(e["support_for"], e["support_against"], uw)
                leaves.append((p, cat, e.get("label", "?"), e.get("success_criteria", "")))
        leaves.sort(key=lambda x: x[0])
        for pos_v, cat, lbl, sc in leaves[:5]:
            lines.append(f"- {cat}/{lbl}: Policy P = {pos_v*100:.0f}% ({str(sc)[:60]})")

    summary_text = "\n".join(l for l in lines if l)
    st.text_area("Summary (copy for reporting)", value=summary_text, height=300, key="summary_report_text")
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in prospect_title)
    st.download_button(
        "Download summary (.txt)",
        data=summary_text,
        file_name=f"{safe_title}_risk_summary.txt",
        mime="text/plain",
    )
