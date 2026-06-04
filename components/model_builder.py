"""Risk Model Builder — UI component for viewing and editing risk model templates.

Renders as a compact banner above the Prospect Hub.  Expanding it reveals the
full model editor which uses pandas DataFrames + st.data_editor for tabular
editing of groups and elements.

Session state keys used by this module:
  _mb_active_model_path   Path str of the currently loaded model JSON
  _mb_draft_json          JSON str of the model being edited (draft)
  _mb_edit_open           bool — whether the edit expander is open
  _mb_import_error        str — last import error message
"""

from __future__ import annotations

import io
import json
import re
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from data.risk_model import (
    MODELS_DIR,
    ESL_OPERATOR_DOCS,
    ESL_OPERATOR_OPTIONS,
    CLASSIC_POS_OPERATOR_OPTIONS,
    ESL_TO_CLASSIC_RECOMMENDATION,
    PILLAR_COLORS_DEFAULT,
    ElementGroup,
    PillarDef,
    PlayElement,
    RiskElement,
    RiskModel,
    build_runtime_models,
    ensure_default_model,
    extract_assessment_data,
    from_xlsx,
    initialize_operators_from_model,
    initialize_classic_operators_from_model,
    list_saved_models,
    to_xlsx,
)


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def render_model_section() -> None:
    """Render the Risk Model section.  Call this before render_prospect_hub()."""
    _ensure_model_initialized()
    active: RiskModel = st.session_state["active_risk_model"]

    n_pillars = len(active.pillars)
    n_cond = sum(
        sum(len(g.elements) for g in p.conditional_groups)
        for p in active.pillars
    )

    with st.container(border=True):
        # ── Header row ────────────────────────────────────────────────────
        hc1, hc2 = st.columns([5, 1])
        with hc1:
            pill_badges = " ".join(
                f"<span style='display:inline-block;padding:1px 7px;border-radius:10px;"
                f"background:{p.color};color:#1e293b;font-size:0.72rem;font-weight:600;"
                f"margin-right:3px;'>{p.display_name}</span>"
                for p in active.pillars
            )
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:10px;flex-wrap:wrap;'>"
                f"<span style='font-size:0.8rem;font-weight:700;color:#374151;"
                f"text-transform:uppercase;letter-spacing:0.07em;white-space:nowrap;'>⚙ RISK MODEL</span>"
                f"<span style='font-size:0.8rem;color:#374151;font-weight:600;'>{active.model_name}</span>"
                f"<span style='font-size:0.72rem;color:#9CA3AF;'>v{active.version} "
                f"· {n_pillars} pillars · {n_cond} cond. elements</span>"
                f"{pill_badges}</div>",
                unsafe_allow_html=True,
            )
        with hc2:
            st.caption("")  # spacing

        # ── Editor expander ───────────────────────────────────────────────
        with st.expander("View / Edit Risk Model", expanded=False):
            _render_model_editor(active)


# ─────────────────────────────────────────────────────────────────────────────
# Initialization
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_model_initialized() -> None:
    """Load the active model into session state if not already there."""
    if "active_risk_model" not in st.session_state:
        try:
            model = ensure_default_model()
        except FileNotFoundError as exc:
            st.error(f"Risk model not found: {exc}")
            st.stop()
        st.session_state["active_risk_model"] = model
        st.session_state["_mb_active_model_path"] = str(
            MODELS_DIR / f"{model.model_id}.json"
        )


def _get_draft() -> dict:
    """Return the current draft model dict, initializing from active model if needed."""
    if "_mb_draft_json" not in st.session_state:
        active: RiskModel = st.session_state["active_risk_model"]
        st.session_state["_mb_draft_json"] = json.dumps(active.to_dict())
    return json.loads(st.session_state["_mb_draft_json"])


def _save_draft(d: dict) -> None:
    st.session_state["_mb_draft_json"] = json.dumps(d)


# ─────────────────────────────────────────────────────────────────────────────
# Main editor
# ─────────────────────────────────────────────────────────────────────────────

def _render_model_editor(active: RiskModel) -> None:
    draft = _get_draft()

    # ── Model picker + IO ─────────────────────────────────────────────────
    saved_paths = list_saved_models()
    saved_names = [p.stem for p in saved_paths]
    saved_labels = [f"{p.stem} {'(active)' if str(p) == st.session_state.get('_mb_active_model_path','') else ''}" for p in saved_paths]

    io_c1, io_c2, io_c3, io_c4 = st.columns([3, 1, 1, 1])
    with io_c1:
        if saved_labels:
            chosen = st.selectbox(
                "Saved models", options=saved_labels,
                index=0, label_visibility="collapsed",
                key="_mb_model_select",
            )
            chosen_idx = saved_labels.index(chosen) if chosen in saved_labels else 0
            if st.button("📂 Load selected", key="_mb_load_btn", use_container_width=True):
                model = RiskModel.load(saved_paths[chosen_idx])
                st.session_state["active_risk_model"] = model
                st.session_state["_mb_active_model_path"] = str(saved_paths[chosen_idx])
                _apply_model_to_session(model)
                st.rerun()
        else:
            st.caption("No saved models found.")

    with io_c2:
        if st.button("➕ New blank", key="_mb_new_btn", use_container_width=True):
            blank = _blank_model()
            _save_draft(blank.to_dict())
            st.rerun()

    with io_c3:
        # Import
        st.markdown("**Import**")
        uploaded = st.file_uploader(
            "Import model", type=["json", "xlsx"],
            key="_mb_upload", label_visibility="collapsed",
        )
        if uploaded is not None:
            try:
                if uploaded.name.endswith(".json"):
                    imported = RiskModel.from_dict(json.loads(uploaded.read()))
                else:
                    tmp = Path(tempfile.gettempdir()) / uploaded.name
                    tmp.write_bytes(uploaded.read())
                    imported = from_xlsx(tmp, "imported", "Imported Model")
                _save_draft(imported.to_dict())
                st.session_state.pop("_mb_import_error", None)
                st.success("Model imported into draft — review and Apply.")
            except Exception as exc:
                st.session_state["_mb_import_error"] = str(exc)

        if "_mb_import_error" in st.session_state:
            st.error(st.session_state["_mb_import_error"])

    with io_c4:
        # Export active model
        st.markdown("**Export**")
        ec1, ec2 = st.columns(2)
        with ec1:
            json_bytes = json.dumps(active.to_dict(), indent=2, ensure_ascii=False).encode()
            st.download_button(
                "⬇ JSON", data=json_bytes,
                file_name=f"{active.model_id}.json", mime="application/json",
                key="_mb_export_json", use_container_width=True,
            )
        with ec2:
            buf = io.BytesIO()
            try:
                to_xlsx(active, buf)
                buf.seek(0)
                st.download_button(
                    "⬇ XLSX", data=buf.read(),
                    file_name=f"{active.model_id}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="_mb_export_xlsx", use_container_width=True,
                )
            except ImportError:
                st.caption("openpyxl needed for XLSX export")

    st.divider()

    # ── Edit form ──────────────────────────────────────────────────────────
    st.markdown("#### ✏️ Edit Model Draft")
    st.caption(
        "Changes here are staged in the draft and do **not** affect the current "
        "assessment until you click **Apply to Assessment**."
    )

    # Model-level fields
    mc1, mc2, mc3 = st.columns([3, 1, 1])
    with mc1:
        draft["model_name"] = st.text_input(
            "Model name", value=draft.get("model_name", ""),
            key="_mb_f_model_name",
        )
    with mc2:
        draft["model_id"] = st.text_input(
            "Model ID (filename)", value=draft.get("model_id", ""),
            key="_mb_f_model_id",
        )
    with mc3:
        draft["version"] = st.text_input(
            "Version", value=draft.get("version", "1.0"),
            key="_mb_f_version",
        )

    draft["description"] = st.text_area(
        "Description", value=draft.get("description", ""),
        height=60, key="_mb_f_description",
    )
    _save_draft(draft)

    st.divider()

    # ── Pillar overview table ───────────────────────────────────────────────
    st.markdown("**Pillars** (add / remove rows to add / remove pillars)")

    pillar_df = _pillars_to_df(draft.get("pillars", []))
    edited_pillar_df = st.data_editor(
        pillar_df,
        key="_mb_pillar_table",
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "pillar_id": st.column_config.TextColumn(
                "Pillar ID", help="Internal key (e.g. 'Charge'). No spaces.", width="small",
            ),
            "display_name": st.column_config.TextColumn("Display Name", width="small"),
            "color": st.column_config.TextColumn(
                "Color (hex)", help="e.g. #F69292", width="small",
            ),
            "conditional_operator": st.column_config.SelectboxColumn(
                "ESL Cond. Op.",
                options=ESL_OPERATOR_OPTIONS,
                help="ESL operator for combining conditional groups within this pillar.",
                width="medium",
            ),
            "classic_pos_operator": st.column_config.SelectboxColumn(
                "Classic POS Op.",
                options=CLASSIC_POS_OPERATOR_OPTIONS,
                help="Classic POS operator for this pillar. Applies to probability values, not ESL masses.",
                width="medium",
            ),
        },
        hide_index=True,
    )

    # Sync pillar table back into draft (preserving existing groups/play for unchanged pillars)
    if edited_pillar_df is not None:
        _sync_pillar_table_to_draft(draft, edited_pillar_df)
        _save_draft(draft)

    st.divider()

    # ── Per-pillar element editors ──────────────────────────────────────────
    pillars_list = draft.get("pillars", [])
    if not pillars_list:
        st.info("Add pillars in the table above to start building your model.")
    else:
        pillar_names = [p.get("display_name") or p.get("pillar_id") or f"Pillar {i+1}"
                        for i, p in enumerate(pillars_list)]
        pillar_tabs = st.tabs([f"{n}" for n in pillar_names])

        for tab, pdict in zip(pillar_tabs, pillars_list):
            with tab:
                _render_pillar_editor(pdict, draft)

        _save_draft(draft)

    st.divider()

    # ── Operator documentation ──────────────────────────────────────────────
    if st.toggle("📖 Show operator reference", key="_mb_op_ref_tog", value=False):
        with st.container(border=True):
            for op, doc in ESL_OPERATOR_DOCS.items():
                st.markdown(f"**{op}** — {doc}\n")

    # ── Apply / Save buttons ────────────────────────────────────────────────
    act_c1, act_c2, act_c3 = st.columns([2, 2, 1])
    with act_c1:
        if st.button(
            "✅ Apply to Assessment", type="primary",
            key="_mb_apply_btn", use_container_width=True,
            help="Rebuild the assessment with this model. Values for elements whose "
                 "node_id matches will be preserved; others reset to defaults.",
        ):
            _apply_draft_to_session(draft)
            st.success("Model applied. The assessment has been updated.")
            st.rerun()

    with act_c2:
        if st.button(
            "💾 Save Model", key="_mb_save_btn", use_container_width=True,
            help="Save this model to data/models/ as a JSON template (does not apply it).",
        ):
            try:
                new_model = RiskModel.from_dict(draft)
                saved_path = new_model.save()
                st.success(f"Saved to {saved_path.name}")
            except Exception as exc:
                st.error(f"Save failed: {exc}")

    with act_c3:
        if st.button(
            "↩ Reset draft", key="_mb_reset_btn", use_container_width=True,
            help="Discard draft edits and reload from the active model.",
        ):
            st.session_state.pop("_mb_draft_json", None)
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Pillar editor
# ─────────────────────────────────────────────────────────────────────────────

def _render_pillar_editor(pdict: dict, draft: dict) -> None:
    pid = pdict.get("pillar_id", "")
    dn = pdict.get("display_name", pid)

    # ── Play element ───────────────────────────────────────────────────────
    st.markdown(f"**🌍 Play element — {dn}**")
    with st.container(border=True):
        play = pdict.get("play") or {}
        if isinstance(play, dict):
            pc1, pc2, pc3, pc4 = st.columns([2, 1, 1, 1])
            with pc1:
                play["name"] = st.text_input(
                    "Play element name", value=play.get("name", dn),
                    key=f"_mb_play_{pid}_name",
                )
            with pc2:
                play["default_s_n"] = st.number_input(
                    "Default S_for", value=float(play.get("default_s_n", 0.5)),
                    min_value=0.0, max_value=1.0, step=0.05,
                    key=f"_mb_play_{pid}_sn",
                )
            with pc3:
                play["default_s_neg"] = st.number_input(
                    "Default S_against", value=float(play.get("default_s_neg", 0.1)),
                    min_value=0.0, max_value=1.0, step=0.05,
                    key=f"_mb_play_{pid}_sneg",
                )
            with pc4:
                play["default_w"] = st.number_input(
                    "Default stance (w)", value=float(play.get("default_w", 0.5)),
                    min_value=0.0, max_value=1.0, step=0.05,
                    key=f"_mb_play_{pid}_w",
                )

            play["node_id"] = st.text_input(
                "Node ID", value=play.get("node_id", f"{pid.upper()}_PLAY"),
                key=f"_mb_play_{pid}_nid",
                help="Unique identifier. Preserve existing IDs to retain assessment data.",
            )
            play["success_criteria"] = st.text_input(
                "Success criteria", value=play.get("success_criteria", ""),
                key=f"_mb_play_{pid}_sc",
            )

            # Advanced guidance fields — collapsed by default using a toggle
            if st.toggle("Show description / guidance fields", key=f"_mb_play_{pid}_show_adv",
                         value=False):
                play["description"] = st.text_area(
                    "Description / guidance", value=play.get("description", ""),
                    height=80, key=f"_mb_play_{pid}_desc",
                )
                play["considerations"] = st.text_area(
                    "Considerations (bullet points)", value=play.get("considerations", ""),
                    height=100, key=f"_mb_play_{pid}_cons",
                )
            pdict["play"] = play

        # Multi-element play (sub-groups) — using a toggle to avoid nested expanders
        if st.toggle("➕ Multi-element play (advanced)", key=f"_mb_play_sub_tog_{pid}",
                     value=False):
            st.caption(
                "By default, each play pillar is a single element. "
                "Add sub-groups here to split the play assessment into multiple elements. "
                "If sub-groups are present, the play element above becomes the aggregated result."
            )
            sub_groups = play.get("sub_groups") or []
            sub_df = _subgroups_to_df(sub_groups)
            edited_sub_df = st.data_editor(
                sub_df,
                key=f"_mb_play_sub_{pid}",
                use_container_width=True,
                num_rows="dynamic",
                column_config=_elem_column_config(),
                hide_index=True,
            )
            if edited_sub_df is not None:
                play["sub_groups"] = _df_to_subgroups(edited_sub_df)
                play["aggregation_rule"] = st.selectbox(
                    "Sub-element aggregation", options=ESL_OPERATOR_OPTIONS,
                    index=_op_idx(play.get("aggregation_rule", "ESL-ALL (min/min)")),
                    key=f"_mb_play_sub_op_{pid}",
                )

    st.markdown("")

    # ── Conditional elements ───────────────────────────────────────────────
    st.markdown(f"**🔍 Conditional elements — {dn}**")
    with st.container(border=True):
        cond_groups: list[dict] = pdict.get("conditional_groups") or []

        # Groups table (label + operator)
        st.markdown("**Groups** — each group aggregates its elements with its own operator")
        groups_df = _groups_meta_to_df(cond_groups)
        edited_groups_df = st.data_editor(
            groups_df,
            key=f"_mb_cond_groups_{pid}",
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "group_id": st.column_config.TextColumn(
                    "Group ID", help="Internal ID (auto-generated if blank)", width="small",
                ),
                "group_label": st.column_config.TextColumn("Group label", width="medium"),
                "aggregation_rule": st.column_config.SelectboxColumn(
                    "ESL Op. (within group)",
                    options=ESL_OPERATOR_OPTIONS,
                    help="ESL operator combining element evidence masses within this group.",
                    width="medium",
                ),
                "classic_pos_aggregation_rule": st.column_config.SelectboxColumn(
                    "Classic POS Op. (within group)",
                    options=CLASSIC_POS_OPERATOR_OPTIONS,
                    help="Classic POS operator combining element Policy POS values within this group.",
                    width="medium",
                ),
            },
            hide_index=True,
        )

        st.caption(
            "All group results are then combined at the pillar level with the "
            f"**pillar operator** set in the Pillars table above "
            f"(*current: {pdict.get('conditional_operator','ESL-ALL (min/min)')}*)."
        )

        st.markdown("**Elements** — assign each element to a group via the *Group label* column")
        elems_df = _cond_elements_to_df(cond_groups)
        edited_elems_df = st.data_editor(
            elems_df,
            key=f"_mb_cond_elems_{pid}",
            use_container_width=True,
            num_rows="dynamic",
            column_config=_elem_column_config(include_group_label=True),
            hide_index=True,
        )

        if edited_groups_df is not None and edited_elems_df is not None:
            pdict["conditional_groups"] = _merge_groups_and_elems(
                edited_groups_df, edited_elems_df
            )


# ─────────────────────────────────────────────────────────────────────────────
# DataFrame helpers
# ─────────────────────────────────────────────────────────────────────────────

def _pillars_to_df(pillars: list[dict]) -> pd.DataFrame:
    rows = []
    for p in pillars:
        esl_op = p.get("conditional_operator", "ESL-ALL (min/min)")
        rows.append({
            "pillar_id":            p.get("pillar_id", ""),
            "display_name":         p.get("display_name", ""),
            "color":                p.get("color", "#e5e7eb"),
            "conditional_operator": esl_op,
            "classic_pos_operator": p.get(
                "classic_pos_operator",
                ESL_TO_CLASSIC_RECOMMENDATION.get(esl_op, "Min (weakest link)"),
            ),
        })
    if not rows:
        rows = [{
            "pillar_id": "", "display_name": "", "color": "#e5e7eb",
            "conditional_operator": "ESL-ALL (min/min)",
            "classic_pos_operator": "Min (weakest link)",
        }]
    return pd.DataFrame(rows)


def _groups_meta_to_df(cond_groups: list[dict]) -> pd.DataFrame:
    seen: dict[str, dict] = {}
    for g in cond_groups:
        label = g.get("group_label", "")
        if label not in seen:
            esl_op = g.get("aggregation_rule", "ESL-ALL (min/min)")
            seen[label] = {
                "group_id": g.get("group_id", ""),
                "group_label": label,
                "aggregation_rule": esl_op,
                "classic_pos_aggregation_rule": g.get(
                    "classic_pos_aggregation_rule",
                    ESL_TO_CLASSIC_RECOMMENDATION.get(esl_op, "Min (weakest link)"),
                ),
            }
    rows = list(seen.values())
    if not rows:
        rows = [{
            "group_id": "", "group_label": "Group 1",
            "aggregation_rule": "ESL-ALL (min/min)",
            "classic_pos_aggregation_rule": "Min (weakest link)",
        }]
    return pd.DataFrame(rows)


def _cond_elements_to_df(cond_groups: list[dict]) -> pd.DataFrame:
    rows = []
    for g in cond_groups:
        for e in g.get("elements", []):
            rows.append({
                "group_label":      g.get("group_label", ""),
                "node_id":          e.get("node_id", ""),
                "name":             e.get("name", ""),
                "success_criteria": e.get("success_criteria", ""),
                "description":      e.get("description", ""),
                "default_s_n":      float(e.get("default_s_n", 0.5)),
                "default_s_neg":    float(e.get("default_s_neg", 0.1)),
                "default_w":        float(e.get("default_w", 0.5)),
                "notes":            e.get("notes", ""),
            })
    if not rows:
        rows = [{
            "group_label": "Group 1", "node_id": "", "name": "",
            "success_criteria": "", "description": "",
            "default_s_n": 0.5, "default_s_neg": 0.1, "default_w": 0.5, "notes": "",
        }]
    return pd.DataFrame(rows)


def _subgroups_to_df(sub_groups: list[dict]) -> pd.DataFrame:
    rows = []
    for g in sub_groups:
        for e in g.get("elements", []):
            rows.append({
                "group_label":      g.get("group_label", ""),
                "node_id":          e.get("node_id", ""),
                "name":             e.get("name", ""),
                "success_criteria": e.get("success_criteria", ""),
                "default_s_n":      float(e.get("default_s_n", 0.5)),
                "default_s_neg":    float(e.get("default_s_neg", 0.1)),
                "default_w":        float(e.get("default_w", 0.5)),
            })
    if not rows:
        rows = [{"group_label": "", "node_id": "", "name": "", "success_criteria": "",
                 "default_s_n": 0.5, "default_s_neg": 0.1, "default_w": 0.5}]
    return pd.DataFrame(rows)


def _elem_column_config(include_group_label: bool = False) -> dict:
    cfg: dict[str, Any] = {}
    if include_group_label:
        cfg["group_label"] = st.column_config.TextColumn(
            "Group label", help="Must match a group_label in the Groups table above.", width="small",
        )
    cfg.update({
        "node_id": st.column_config.TextColumn(
            "Node ID",
            help="Unique identifier — preserve to retain assessment data across model changes.",
            width="small",
        ),
        "name": st.column_config.TextColumn("Element name", width="medium"),
        "success_criteria": st.column_config.TextColumn("Success criteria", width="large"),
        "description": st.column_config.TextColumn("Description / notes", width="large"),
        "default_s_n": st.column_config.NumberColumn(
            "S_for", min_value=0.0, max_value=1.0, step=0.05, format="%.2f",
            help="Default ESL S_for (support for success).",
        ),
        "default_s_neg": st.column_config.NumberColumn(
            "S_against", min_value=0.0, max_value=1.0, step=0.05, format="%.2f",
            help="Default ESL S_against (support against success).",
        ),
        "default_w": st.column_config.NumberColumn(
            "w (stance)", min_value=0.0, max_value=1.0, step=0.05, format="%.2f",
            help="Default element stance. 0=pessimistic, 0.5=neutral, 1=optimistic.",
        ),
        "notes": st.column_config.TextColumn("Notes", width="medium"),
    })
    return cfg


# ─────────────────────────────────────────────────────────────────────────────
# Draft ↔ structured data conversion
# ─────────────────────────────────────────────────────────────────────────────

def _sync_pillar_table_to_draft(draft: dict, df: pd.DataFrame) -> None:
    """Update draft['pillars'] list from the edited pillar DataFrame.

    Pillars that already exist in the draft (matched by pillar_id) have their
    groups/play preserved.  New rows get blank groups/play.
    """
    existing: dict[str, dict] = {p["pillar_id"]: p for p in draft.get("pillars", []) if p.get("pillar_id")}
    new_pillars = []
    for _, row in df.iterrows():
        pid = str(row.get("pillar_id") or "").strip()
        dn = str(row.get("display_name") or pid).strip()
        if not pid and not dn:
            continue
        if not pid:
            pid = _to_pillar_id(dn)
        base = existing.get(pid, {})
        _esl_op_new = str(row.get("conditional_operator") or "ESL-ALL (min/min)")
        new_pillars.append({
            "pillar_id":            pid,
            "display_name":         dn or pid,
            "color":                str(row.get("color") or PILLAR_COLORS_DEFAULT.get(pid, "#e5e7eb")),
            "conditional_operator": _esl_op_new,
            "classic_pos_operator": str(
                row.get("classic_pos_operator")
                or ESL_TO_CLASSIC_RECOMMENDATION.get(_esl_op_new, "Min (weakest link)")
            ),
            "play":                 base.get("play") or _default_play(pid, dn),
            "conditional_groups":   base.get("conditional_groups") or [],
        })
    draft["pillars"] = new_pillars


def _merge_groups_and_elems(groups_df: pd.DataFrame, elems_df: pd.DataFrame) -> list[dict]:
    """Build a conditional_groups list from the two data_editor DataFrames."""
    # Build group meta dict keyed by group_label
    group_meta: dict[str, dict] = {}
    for _, row in groups_df.iterrows():
        label = str(row.get("group_label") or "").strip()
        if not label:
            continue
        gid = str(row.get("group_id") or "").strip() or _slug(label)
        op = str(row.get("aggregation_rule") or "ESL-ALL (min/min)")
        cl_op = str(
            row.get("classic_pos_aggregation_rule")
            or ESL_TO_CLASSIC_RECOMMENDATION.get(op, "Min (weakest link)")
        )
        group_meta[label] = {
            "group_id": gid,
            "aggregation_rule": op,
            "classic_pos_aggregation_rule": cl_op,
        }

    # Bucket elements by group_label
    buckets: dict[str, list[dict]] = {}
    for _, row in elems_df.iterrows():
        label = str(row.get("group_label") or "").strip()
        if not label:
            label = "Ungrouped"
        nid = str(row.get("node_id") or "").strip()
        name = str(row.get("name") or "").strip()
        if not name and not nid:
            continue
        if not nid:
            nid = _slug(name or label)
        elem = {
            "node_id":          nid,
            "name":             name,
            "success_criteria": str(row.get("success_criteria") or ""),
            "description":      str(row.get("description") or ""),
            "considerations":   "",
            "default_s_n":      _fsafe(row.get("default_s_n"), 0.5),
            "default_s_neg":    _fsafe(row.get("default_s_neg"), 0.1),
            "default_w":        _fsafe(row.get("default_w"), 0.5),
            "notes":            str(row.get("notes") or ""),
        }
        buckets.setdefault(label, []).append(elem)

    # Assemble final groups list, respecting order from groups_df
    result: list[dict] = []
    seen_labels: set[str] = set()
    for label in group_meta:
        seen_labels.add(label)
        result.append({
            "group_id":                    group_meta[label]["group_id"],
            "group_label":                 label,
            "aggregation_rule":            group_meta[label]["aggregation_rule"],
            "classic_pos_aggregation_rule": group_meta[label]["classic_pos_aggregation_rule"],
            "elements":                    buckets.get(label, []),
        })
    # Append elements whose group_label wasn't in the groups table
    for label, elems in buckets.items():
        if label not in seen_labels:
            result.append({
                "group_id":                    _slug(label),
                "group_label":                 label,
                "aggregation_rule":            "ESL-ALL (min/min)",
                "classic_pos_aggregation_rule": "Min (weakest link)",
                "elements":                    elems,
            })
    return result


def _df_to_subgroups(df: pd.DataFrame) -> list[dict]:
    """Convert a flat sub-elements DataFrame to sub_groups list."""
    buckets: dict[str, list[dict]] = {}
    for _, row in df.iterrows():
        label = str(row.get("group_label") or "").strip() or "Sub-elements"
        nid = str(row.get("node_id") or "").strip()
        name = str(row.get("name") or "").strip()
        if not name and not nid:
            continue
        if not nid:
            nid = _slug(name)
        buckets.setdefault(label, []).append({
            "node_id": nid, "name": name,
            "success_criteria": str(row.get("success_criteria") or ""),
            "default_s_n":  _fsafe(row.get("default_s_n"), 0.5),
            "default_s_neg": _fsafe(row.get("default_s_neg"), 0.1),
            "default_w":    _fsafe(row.get("default_w"), 0.5),
            "description": "", "considerations": "", "notes": "",
        })
    return [
        {"group_id": _slug(lbl), "group_label": lbl,
         "aggregation_rule": "ESL-ALL (min/min)", "elements": elems}
        for lbl, elems in buckets.items()
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Apply helpers
# ─────────────────────────────────────────────────────────────────────────────

def _apply_draft_to_session(draft: dict) -> None:
    """Convert the draft dict into a RiskModel and rebuild the session models dict."""
    new_model = RiskModel.from_dict(draft)
    current_models = st.session_state.get("models", {})
    assessment_data = extract_assessment_data(current_models)
    new_runtime = build_runtime_models(new_model, assessment_data)
    st.session_state["models"] = new_runtime
    st.session_state["active_risk_model"] = new_model
    st.session_state["_mb_active_model_path"] = str(MODELS_DIR / f"{new_model.model_id}.json")
    initialize_operators_from_model(new_model, st.session_state)
    initialize_classic_operators_from_model(new_model, st.session_state)
    st.session_state.pop("active_cam_key", None)
    st.session_state.pop("_mb_draft_json", None)


def _apply_model_to_session(model: RiskModel) -> None:
    """Apply a loaded model to the session (same logic as _apply_draft_to_session)."""
    current_models = st.session_state.get("models", {})
    assessment_data = extract_assessment_data(current_models)
    new_runtime = build_runtime_models(model, assessment_data)
    st.session_state["models"] = new_runtime
    initialize_operators_from_model(model, st.session_state)
    initialize_classic_operators_from_model(model, st.session_state)
    st.session_state.pop("active_cam_key", None)
    st.session_state.pop("_mb_draft_json", None)


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

def _blank_model() -> RiskModel:
    return RiskModel(
        model_id="custom_model",
        model_name="Custom Model",
        version="1.0",
        description="",
        pillars=[
            PillarDef(
                pillar_id="Charge",
                display_name="Charge",
                color=PILLAR_COLORS_DEFAULT["Charge"],
                play=PlayElement(node_id="CHARGE_PLAY", name="Charge"),
                conditional_operator="ESL-ALL (min/min)",
                conditional_groups=[
                    ElementGroup(
                        group_id="CHARGE_GRP1",
                        group_label="Group 1",
                        aggregation_rule="ESL-ALL (min/min)",
                        elements=[
                            RiskElement(node_id="CHARGE_E1", name="Element 1"),
                        ],
                    )
                ],
            )
        ],
    )


def _default_play(pillar_id: str, display_name: str) -> dict:
    from data.risk_model import _PLAY_GUIDANCE
    g = _PLAY_GUIDANCE.get(pillar_id, {})
    return {
        "node_id": f"{pillar_id.upper()}_PLAY",
        "name": display_name,
        "success_criteria": "",
        "description": g.get("description", ""),
        "considerations": g.get("considerations", ""),
        "default_s_n": 0.5,
        "default_s_neg": 0.1,
        "default_w": 0.5,
        "aggregation_rule": "ESL-ALL (min/min)",
        "sub_groups": [],
    }


def _to_pillar_id(name: str) -> str:
    """Convert a display name to a valid pillar_id."""
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_")
    return s[:24] if s else "Pillar"


def _slug(s: str, maxlen: int = 24) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").upper()
    return s[:maxlen] if s else "NODE"


def _op_idx(op: str) -> int:
    try:
        return ESL_OPERATOR_OPTIONS.index(op)
    except ValueError:
        return 0


def _fsafe(v: Any, default: float = 0.5) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default
