"""Smoke tests: render the Streamlit app headlessly and assert no exceptions.

These do not check content. They guard against the class of breakage that only
shows up at render time (a widget ``value=``/``key=`` conflict, a NameError in a
tab, a missing session-state default) and that the pure-logic unit tests cannot
catch. If the app raises while rendering, these fail.
"""
import os

from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.py")
TIMEOUT = 60


def _assert_clean(at):
    assert not at.exception, "App raised while rendering:\n" + "\n".join(
        str(e) for e in at.exception
    )


def test_app_renders_without_exception():
    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    _assert_clean(at)


def test_app_renders_with_dfi_enabled():
    # Force the DFI master toggle on from the start; the dashboard re-seeds the
    # DFI session defaults on every run while it is enabled, so all three DFI
    # sub-pages (Setup / Results / Summary) render their widgets.
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.session_state["dfi_enabled"] = True
    at.run()
    _assert_clean(at)
