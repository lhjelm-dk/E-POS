"""Reference Tables tab render function."""
from __future__ import annotations

import streamlit as st


def _render_reference_tab(ctx) -> None:
    """Render the Reference tab.  Called by _render_tabs."""

    models = ctx.models
    play = ctx.play
    conditional = ctx.conditional
    r = ctx.rollup
    total_for = ctx.total_for
    total_against = ctx.total_against
    play_for = ctx.play_for
    play_against = ctx.play_against
    conditional_for = ctx.conditional_for
    conditional_against = ctx.conditional_against
    conditional_results = ctx.conditional_results
    uncertainty_weight = ctx.uncertainty_weight
    prospect_title = ctx.prospect_title
    _active_model_ref = ctx.active_model
    _pillar_colors = ctx.pillar_colors
    _pillar_display = ctx.pillar_display
    ESL_OPTIONS = MODE_OPTIONS = ctx.esl_options

    from methods.reference_tables import render_reference_tables
    render_reference_tables()
