"""Session-state key registry for E-POS.

All Streamlit ``st.session_state`` key patterns used across the app are
documented and generated here.  Import from this module instead of embedding
raw f-string literals in UI code — this is the single source of truth for
the key namespace.

Usage::

    from logic.session_keys import SK
    st.session_state[SK.esl_mode(category)] = "ESL-ALL (min/min)"
    mode = st.session_state.get(SK.esl_mode(category), DEFAULT_ESL_MODE)

Design note — three separate naming families
--------------------------------------------
1. **ESL operators** — ``mode_cond_{pid}`` / ``mode_group_cond_{pid}_{group}``
   - Operate on (S_for, S_against) mass pairs.
   - Written by the Conditional tab Operator Settings UI.

2. **Classic POS operators** — ``classic_mode_cond_{pid}`` / ``classic_mode_group_cond_{pid}_{group}``
   - Operate on Policy POS probability values.
   - Written by the Conditional tab Operator Settings UI (Classic section).
   - Round-tripped through CSV export/import.

3. **CAM / element stance** — ``{key_prefix}_w_slider`` / ``element["_cam_w"]``
   - Per-element effective stance w ∈ [0,1].
   - Written by element_detail_cam.py.
"""

from __future__ import annotations


class SK:  # noqa: N801 — short name is intentional for ergonomics at call-sites
    """Namespace of session-state key generators.

    All methods are static and return plain strings so they can be used
    directly as ``key=SK.xxx(...)`` in ``st.session_state`` or widget calls.
    """

    # ── ESL operators (operate on mass pairs) ────────────────────────────────

    @staticmethod
    def esl_mode(pillar_id: str) -> str:
        """Pillar-level ESL combination operator.  Key: ``mode_cond_{pid}``."""
        return f"mode_cond_{pillar_id}"

    @staticmethod
    def esl_group_mode(pillar_id: str, group_label: str) -> str:
        """Group-level ESL combination operator.  Key: ``mode_group_cond_{pid}_{group}``."""
        return f"mode_group_cond_{pillar_id}_{group_label}"

    @staticmethod
    def esl_dependency(pillar_id: str) -> str:
        """Pillar-level ESL dependency ρ.  Key: ``dep_cond_{pid}``."""
        return f"dep_cond_{pillar_id}"

    @staticmethod
    def esl_group_dependency(pillar_id: str, group_label: str) -> str:
        """Group-level ESL dependency ρ.  Key: ``dep_group_cond_{pid}_{group}``."""
        return f"dep_group_cond_{pillar_id}_{group_label}"

    # ── Classic POS operators (operate on probability values) ────────────────

    @staticmethod
    def classic_mode(pillar_id: str) -> str:
        """Pillar-level Classic POS operator.  Key: ``classic_mode_cond_{pid}``."""
        return f"classic_mode_cond_{pillar_id}"

    @staticmethod
    def classic_group_mode(pillar_id: str, group_label: str) -> str:
        """Group-level Classic POS operator.  Key: ``classic_mode_group_cond_{pid}_{group}``."""
        return f"classic_mode_group_cond_{pillar_id}_{group_label}"

    # ── Comparison / cross-method results (Dashboard) ───────────────────────

    COMPARISON_ESL_POS          = "comparison_esl_pos"
    COMPARISON_ESL_TOTAL_FOR    = "comparison_esl_total_for"
    COMPARISON_ESL_TOTAL_AGAINST = "comparison_esl_total_against"
    COMPARISON_CLASSIC_POS      = "comparison_classic_pos"

    # ── Sign-off / audit ─────────────────────────────────────────────────────

    @staticmethod
    def locked(method: str) -> str:
        """Sign-off record for *method*.  Key: ``locked_{method}``."""
        return f"locked_{method}"

    # ── Meta / prospect identity ─────────────────────────────────────────────

    META_TITLE   = "meta_title"
    META_ANALYST = "meta_analyst"
    META_BASIN   = "meta_basin"
    META_DATE    = "meta_date"
    META_VERSION = "meta_version"

    # ── Policy stance ────────────────────────────────────────────────────────

    USE_POLICY_WEIGHT     = "use_policy_weight"
    UNCERTAINTY_WEIGHT_SLIDER = "uncertainty_weight_slider"

    # ── CAM / element editing ─────────────────────────────────────────────────

    ACTIVE_CAM_KEY_PREFIX = "active_cam_key_prefix"
    ACTIVE_CAM_SCOPE      = "active_cam_scope"
    ACTIVE_CAM_CATEGORY   = "active_cam_category"

    @staticmethod
    def element_w_slider(key_prefix: str) -> str:
        """Per-element stance slider.  Key: ``{key_prefix}_w_slider``."""
        return f"{key_prefix}_w_slider"

    # ── Risk model ────────────────────────────────────────────────────────────

    ACTIVE_RISK_MODEL    = "active_risk_model"
    CURRENT_PROSPECT_FILE = "current_prospect_file"
