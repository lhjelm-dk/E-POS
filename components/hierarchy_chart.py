"""Hierarchy diagram — dynamically reflects the active RiskModel.

Layout strategy: centroid-of-leaves.
  1. All element (leaf) nodes are spread evenly across the conditional half.
  2. Every parent is placed at the mean-x of its children.
  This guarantees zero crossing edges at any level.

Rows (top → bottom):
  y=1.00  Total result node
  y=0.82  Play Chance (Π)  ×  Cond Prospect (Π)
  y=0.62  Individual pillars (play side and conditional side)
  y=0.38  Conditional groups
  y=0.10  Individual elements  ← new row
"""

from __future__ import annotations

import streamlit as st

from logic.session_keys import SK
import plotly.graph_objects as go


# ── Model helpers ─────────────────────────────────────────────────────────────

def _get_model_pillars() -> list[dict]:
    """Return [{pillar_id, display_name, color}] from the active model."""
    model = st.session_state.get("active_risk_model")
    if model is not None:
        return [
            {"pillar_id": p.pillar_id, "display_name": p.display_name, "color": p.color}
            for p in model.pillars
        ]
    return [
        {"pillar_id": "Charge",    "display_name": "Charge",    "color": "#F69292"},
        {"pillar_id": "Closure",   "display_name": "Closure",   "color": "#8CB7FC"},
        {"pillar_id": "Reservoir", "display_name": "Reservoir", "color": "#FFD44B"},
        {"pillar_id": "Retention", "display_name": "Retention", "color": "#B5E6A2"},
    ]


def _get_cond_operator(pillar_id: str) -> str:
    raw = st.session_state.get(SK.esl_mode(pillar_id), "ESL-ALL (min/min)")
    if "ANY" in raw or "max" in raw.lower():   return "ANY"
    if "IPT" in raw or "suff" in raw.lower():  return "IPT"
    if "Product" in raw or "Π" in raw:         return "Π"
    if "Mean" in raw:                           return "μ"
    return "ALL"


def _get_grp_operator(pillar_id: str, group_label: str) -> str:
    raw = st.session_state.get(SK.esl_group_mode(pillar_id, group_label), "ESL-ALL (min/min)")
    if "ANY" in raw or "max" in raw.lower():   return "ANY"
    if "IPT" in raw or "suff" in raw.lower():  return "IPT"
    if "Product" in raw or "Π" in raw:         return "Π"
    if "Mean" in raw:                           return "μ"
    return "ALL"


def _group_by_label(elements: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for el in elements:
        groups.setdefault(el.get("label", "?"), []).append(el)
    return groups


def _shorten(text: str, maxlen: int) -> str:
    if len(text) <= maxlen:
        return text
    return text[:maxlen - 1] + "…"


# ── Centroid-leaf layout ──────────────────────────────────────────────────────

def _build_layout(pillars: list[dict], conditional: dict) -> dict:
    """Compute x-coordinates for every tree node using the centroid-of-leaves method.

    Returns a dict with keys:
      root_x, play_x, cond_x,
      play_pil  : {pid: x},
      cond_pil  : {pid: x},
      grp       : {(pid, grp_label): x},
      elem      : {(pid, grp_label, elem_idx): x},
      has_groups, has_elements,
    """
    PX0, PX1 = 0.01, 0.47   # play half x range
    CX0, CX1 = 0.53, 0.99   # cond half x range

    # Build pillar structures
    pil_structs = []
    for pdef in pillars:
        pid   = pdef["pillar_id"]
        elems = conditional.get(pid, [])
        grps  = _group_by_label(elems)
        pil_structs.append({
            "pid":    pid,
            "color":  pdef["color"],
            "groups": [
                {"label": lbl, "elements": grp_elems, "key": f"cond_{pid}_{lbl}"}
                for lbl, grp_elems in grps.items()
            ],
        })

    has_groups   = any(ps["groups"] for ps in pil_structs)
    has_elements = any(e for ps in pil_structs for g in ps["groups"] for e in g["elements"])

    # ── Cond side: leaf nodes ──────────────────────────────────────────────
    # Leaves are: elements (if present) → groups (if no elements) → pillar itself
    cond_leaves: list[tuple] = []   # (pid, grp_label | None, elem_idx | None)
    for ps in pil_structs:
        pid = ps["pid"]
        if not ps["groups"]:
            cond_leaves.append((pid, None, None))
        else:
            for grp in ps["groups"]:
                gl = grp["label"]
                if not grp["elements"]:
                    cond_leaves.append((pid, gl, None))
                else:
                    for ei in range(len(grp["elements"])):
                        cond_leaves.append((pid, gl, ei))

    nl = len(cond_leaves)
    if nl == 0:
        cond_leaf_xs = []
    elif nl == 1:
        cond_leaf_xs = [(CX0 + CX1) / 2]
    else:
        cond_leaf_xs = [CX0 + i * (CX1 - CX0) / (nl - 1) for i in range(nl)]

    leaf_x: dict[tuple, float] = {
        (pid, gl, ei): cond_leaf_xs[i]
        for i, (pid, gl, ei) in enumerate(cond_leaves)
    }

    # Group x = mean of its element leaves
    grp_x: dict[tuple, float] = {}
    for ps in pil_structs:
        pid = ps["pid"]
        for grp in ps["groups"]:
            gl = grp["label"]
            if grp["elements"]:
                xs = [leaf_x[(pid, gl, ei)] for ei in range(len(grp["elements"]))]
                grp_x[(pid, gl)] = sum(xs) / len(xs)
            else:
                grp_x[(pid, gl)] = leaf_x.get((pid, gl, None), (CX0 + CX1) / 2)

    # Cond pillar x = mean of its group x's
    cond_pil_x: dict[str, float] = {}
    for ps in pil_structs:
        pid = ps["pid"]
        if ps["groups"]:
            gxs = [grp_x[(pid, g["label"])] for g in ps["groups"]]
            cond_pil_x[pid] = sum(gxs) / len(gxs)
        else:
            cond_pil_x[pid] = leaf_x.get((pid, None, None), (CX0 + CX1) / 2)

    # Cond prospect x = mean of all cond pillar x's
    cpxs = list(cond_pil_x.values())
    cond_x = sum(cpxs) / len(cpxs) if cpxs else (CX0 + CX1) / 2

    # ── Play side: mirror cond pillar positions into play half ─────────────
    if len(cpxs) > 1:
        cx_min, cx_rng = min(cpxs), max(cpxs) - min(cpxs)
        play_pil_x = {
            pid: PX0 + (cx - cx_min) / cx_rng * (PX1 - PX0)
            for pid, cx in cond_pil_x.items()
        }
    else:
        play_pil_x = {ps["pid"]: (PX0 + PX1) / 2 for ps in pil_structs}

    ppxs = list(play_pil_x.values())
    play_x = sum(ppxs) / len(ppxs) if ppxs else (PX0 + PX1) / 2

    root_x = (play_x + cond_x) / 2

    return {
        "pil_structs":   pil_structs,
        "has_groups":    has_groups,
        "has_elements":  has_elements,
        "root_x":        root_x,
        "play_x":        play_x,
        "cond_x":        cond_x,
        "play_pil_x":    play_pil_x,
        "cond_pil_x":    cond_pil_x,
        "grp_x":         grp_x,
        "elem_x":        leaf_x,
    }


# ── Main diagram ──────────────────────────────────────────────────────────────

def _build_esl_tree_figure(
    pillars: list[dict],
    conditional: dict | None,
    result_label: str,
    title: str,
    method_note: str,
    height: int | None = None,
) -> go.Figure:
    """Build the hierarchy Plotly figure using centroid-of-leaves layout."""
    fig  = go.Figure()
    cond = conditional or {}
    L    = _build_layout(pillars, cond)

    has_grp  = L["has_groups"]
    has_elem = L["has_elements"]

    # Row y positions
    if has_elem:
        Y = {"root": 1.00, "l1": 0.82, "pil": 0.62, "grp": 0.38, "elem": 0.10}
        y_min    = -0.22
        fig_h    = height or 680
    elif has_grp:
        Y = {"root": 1.00, "l1": 0.82, "pil": 0.58, "grp": 0.28, "elem": None}
        y_min    = -0.10
        fig_h    = height or 520
    else:
        Y = {"root": 1.00, "l1": 0.78, "pil": 0.48, "grp": None, "elem": None}
        y_min    = 0.18
        fig_h    = height or 420

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _edge(x0, y0, x1, y1, color="#9ca3af", width=1.3, dash="solid"):
        fig.add_trace(go.Scatter(
            x=[x0, x1], y=[y0, y1], mode="lines",
            line=dict(color=color, width=width, dash=dash),
            showlegend=False, hoverinfo="skip",
        ))

    def _node(x, y, size, color, label, tpos="top center", tsize=9,
              opacity=1.0, hover="", symbol="circle"):
        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode="markers+text",
            marker=dict(size=size, color=color, symbol=symbol, opacity=opacity,
                        line=dict(width=1.5, color="white")),
            text=[label], textposition=tpos,
            textfont=dict(size=tsize, color="#1f2937"),
            showlegend=False,
            hovertemplate=(hover or f"<b>{label}</b>") + "<extra></extra>",
        ))

    rx   = L["root_x"]
    px   = L["play_x"]
    cx   = L["cond_x"]

    # ── Edges (drawn first so nodes sit on top) ───────────────────────────────

    # Root → Play/Cond
    _edge(rx, Y["root"], px, Y["l1"], "#6b7280", 2.0)
    _edge(rx, Y["root"], cx, Y["l1"], "#6b7280", 2.0)

    # Pillars
    for ps in L["pil_structs"]:
        pid  = ps["pid"]
        col  = ps["color"]
        ppx  = L["play_pil_x"][pid]
        cpx  = L["cond_pil_x"][pid]

        _edge(px,  Y["l1"], ppx, Y["pil"], col, 1.0)
        _edge(cx,  Y["l1"], cpx, Y["pil"], col, 1.0)

        if Y["grp"] is None:
            continue
        for grp in ps["groups"]:
            gx = L["grp_x"][(pid, grp["label"])]
            _edge(cpx, Y["pil"], gx, Y["grp"], col, 0.75, "dot")

            if Y["elem"] is None:
                continue
            for ei in range(len(grp["elements"])):
                ex = L["elem_x"][(pid, grp["label"], ei)]
                _edge(gx, Y["grp"], ex, Y["elem"], col, 0.5, "dot")

    # ── Root node ─────────────────────────────────────────────────────────────
    _node(rx, Y["root"], 56, "#1e40af", result_label,
          tsize=13, tpos="top center",
          hover=f"<b>{result_label}</b><br>Product of Play × Conditional")

    # × annotation
    mid_y = (Y["root"] + Y["l1"]) / 2
    fig.add_annotation(
        x=(px + cx) / 2, y=mid_y,
        text="×", showarrow=False,
        font=dict(size=22, color="#374151"),
        xref="x", yref="y",
    )

    # ── Play / Cond Prospect nodes ────────────────────────────────────────────
    for xp, lbl in [(px, "Play Chance (Π)"), (cx, "Cond Prospect (Π)")]:
        _node(xp, Y["l1"], 44, "#374151", lbl,
              tsize=10, tpos="top center",
              hover=f"<b>{lbl}</b><br>Product (Π) of pillar probabilities")

    # ── Pillar nodes ──────────────────────────────────────────────────────────
    for ps in L["pil_structs"]:
        pid  = ps["pid"]
        col  = ps["color"]
        lbl  = next(p["display_name"] for p in pillars if p["pillar_id"] == pid)
        ppx  = L["play_pil_x"][pid]
        cpx  = L["cond_pil_x"][pid]
        op   = _get_cond_operator(pid)

        _node(ppx, Y["pil"], 30, col, lbl, tsize=8,
              hover=f"<b>{lbl} (Play)</b><br>Single play-level assessment")
        _node(cpx, Y["pil"], 30, col, lbl, tsize=8,
              hover=f"<b>{lbl} (Conditional)</b><br>Operator: {op}")

        if Y["grp"] is None:
            continue

        # ── Group nodes ───────────────────────────────────────────────────
        for grp in ps["groups"]:
            gl    = grp["label"]
            gx    = L["grp_x"][(pid, gl)]
            g_op  = _get_grp_operator(pid, gl)
            n_el  = len(grp["elements"])
            short = _shorten(gl, 13)
            _node(gx, Y["grp"], 15, col, short,
                  tpos="bottom center", tsize=7, opacity=0.75,
                  hover=(f"<b>{gl}</b><br>{n_el} element(s)<br>"
                         f"Operator: {g_op}"))

            if Y["elem"] is None:
                continue

            # ── Element nodes ─────────────────────────────────────────────
            for ei, elem in enumerate(grp["elements"]):
                ex  = L["elem_x"][(pid, gl, ei)]
                sc  = (elem.get("success_criteria") or elem.get("label", "?"))
                short_sc = _shorten(sc, 14)
                _node(ex, Y["elem"], 7, col, short_sc,
                      tpos="bottom center", tsize=6, opacity=0.6,
                      hover=(f"<b>{elem.get('label', '?')}</b><br>"
                             f"{sc[:90]}"))

    # ── Level row labels (left margin annotations) ────────────────────────────
    row_labels = [
        (Y["root"], "Total"),
        (Y["l1"],   "Play / Cond"),
        (Y["pil"],  "Pillar"),
    ]
    if Y["grp"] is not None:
        row_labels.append((Y["grp"], "Groups"))
    if Y["elem"] is not None:
        row_labels.append((Y["elem"], "Elements"))

    for ry, rlbl in row_labels:
        fig.add_annotation(
            x=-0.01, y=ry, text=f"<i>{rlbl}</i>",
            showarrow=False, xanchor="right",
            font=dict(size=7.5, color="#9ca3af"),
            xref="x", yref="y",
        )

    # ── Layout ────────────────────────────────────────────────────────────────
    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", font=dict(size=12)),
        xaxis=dict(visible=False, range=[-0.08, 1.04]),
        yaxis=dict(visible=False, range=[y_min, 1.22]),
        height=fig_h,
        margin=dict(l=10, r=10, t=42, b=20),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        annotations=fig.layout.annotations + (
            dict(
                x=0.5, y=y_min + 0.03,
                text=method_note,
                showarrow=False,
                font=dict(size=8, color="#9ca3af"),
                xref="paper", yref="paper",
            ),
        ),
    )
    return fig


# ── Element tree (text list) ──────────────────────────────────────────────────

def render_element_tree(play: dict, conditional: dict) -> None:
    """Text tree: pillar → group → elements. Uses the active model for display names."""
    st.markdown("**Element hierarchy** (pillar → group → element)")
    pillars = _get_model_pillars()
    for pdef in pillars:
        pid   = pdef["pillar_id"]
        lbl   = pdef["display_name"]
        color = pdef["color"]
        with st.container(border=True):
            st.markdown(
                f"<span style='background:{color};padding:2px 10px;border-radius:10px;"
                f"font-weight:700;font-size:0.85rem;'>{lbl}</span>",
                unsafe_allow_html=True,
            )
            el = play.get(pid, {})
            if isinstance(el, dict) and el.get("description"):
                st.caption(el["description"][:130] + ("…" if len(el["description"]) > 130 else ""))
            elems = conditional.get(pid, [])
            if not elems:
                st.caption("No conditional sub-elements.")
                continue
            grouped = _group_by_label(elems)
            for grp_lbl, grp_elems in grouped.items():
                grp_op  = st.session_state.get(SK.esl_group_mode(pid, grp_lbl), "ESL-ALL (min/min)")
                st.markdown(
                    f"&nbsp;&nbsp;**{grp_lbl}** "
                    f"<span style='font-size:0.75rem;color:#6b7280;'>({grp_op})</span>",
                    unsafe_allow_html=True,
                )
                for e in grp_elems:
                    sc = (e.get("success_criteria") or "")[:80]
                    st.markdown(
                        f"&nbsp;&nbsp;&nbsp;&nbsp;· *{e.get('label', '?')}*"
                        + (f" — {sc}" if sc else ""),
                        unsafe_allow_html=True,
                    )


# ── Public render functions ───────────────────────────────────────────────────

def render_esl_hierarchy(play: dict | None = None, conditional: dict | None = None,
                         key_prefix: str = "esl") -> None:
    """ESL hierarchy diagram — always matches the active risk model."""
    pillars = _get_model_pillars()
    n = len(pillars)

    op_parts = []
    if conditional:
        for pdef in pillars:
            op_parts.append(f"{pdef['display_name']}: {_get_cond_operator(pdef['pillar_id'])}")
    method_note = (
        "Pillars: product (Π).  "
        + ("Conditional operators — " + " | ".join(op_parts) if op_parts
           else "Sub-elements: ALL (min/min), ANY (max/max), IPT.")
    )

    has_data = bool(conditional and any(conditional.values()))
    fig = _build_esl_tree_figure(
        pillars=pillars,
        conditional=conditional,
        result_label="P(G, ESL)",
        title=f"ESL: P(G) = P(Play) × P(Cond)  [{n} pillars]",
        method_note=method_note,
        height=680 if has_data else 420,
    )
    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_esl_hierarchy")

    if play and conditional:
        st.divider()
        render_element_tree(play, conditional)


def render_classic_pos_hierarchy(play: dict | None = None, conditional: dict | None = None,
                                 key_prefix: str = "classic") -> None:
    """Classic POS hierarchy diagram — matches the active risk model."""
    pillars = _get_model_pillars()
    n = len(pillars)
    fig = _build_esl_tree_figure(
        pillars=pillars,
        conditional=conditional,
        result_label="POS",
        title=f"Classic POS = Play Chance × Conditional Prospect Chance  [{n} pillars]",
        method_note="Pillars: product (Π).  Sub-elements: min (weakest link).",
        height=None,
    )
    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_classic_hierarchy")
    if play and conditional:
        st.divider()
        render_element_tree(play, conditional)


