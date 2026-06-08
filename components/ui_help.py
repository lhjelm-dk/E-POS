"""Small UI helpers for on-demand help (progressive disclosure).

The app carries a lot of genuinely useful explanation. Rather than pushing it at
the user in always-on ``st.info`` boxes (which makes every screen read as a wall
of text), surface it **on demand**: a compact "ⓘ" button that opens the same words
only when the user wants them. Same content — pulled, not pushed.
"""
from __future__ import annotations

import streamlit as st


def help_popover(label: str, body_md: str, *, icon: str = "ⓘ") -> None:
    """Render a compact ``ⓘ label`` popover containing ``body_md``.

    Drop-in replacement for an always-on educational ``st.info(long_text)``:

        help_popover("What the curves mean", "...long markdown...")

    Keep ``st.warning`` / ``st.error`` for operational or critical messages that
    must stay visible (e.g. the Modified-DHI warning, override-active, validation).
    """
    with st.popover(f"{icon} {label}"):
        st.markdown(body_md)
