"""Capture README screenshots from the live E-POS app (Playwright).

Drives the real Streamlit app and saves PNGs to ``docs/img/``. To regenerate the
README gallery after a UI change::

    python scripts/capture_readme_shots.py

IP safety: the real ``data/dhi_calibration.json`` (if present) is temporarily
moved aside so the synthetic *placeholder* calibration is used for every shot —
no proprietary numbers ever land in a committed image. The default synthetic
``AlphaGammaFoxtrot`` prospect supplies all the evidence.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "img"
PORT = 8765
OVERRIDE_CALIB = ROOT / "data" / "dhi_calibration.json"
HIDDEN_CALIB = ROOT / "data" / "_dhi_calibration.hidden"


def _free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def main() -> int:
    from playwright.sync_api import sync_playwright

    IMG.mkdir(parents=True, exist_ok=True)
    moved = False
    proc = None
    try:
        if OVERRIDE_CALIB.exists():
            OVERRIDE_CALIB.rename(HIDDEN_CALIB)
            moved = True
            print("- moved local calibration override aside; placeholder will be used")

        proc = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "app.py",
             "--server.port", str(PORT), "--server.headless", "true",
             "--browser.gatherUsageStats", "false"],
            cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(60):
            if not _free(PORT):
                break
            time.sleep(1)
        time.sleep(4)  # let the first script run settle

        with sync_playwright() as p:
            br = p.chromium.launch()
            pg = br.new_page(viewport={"width": 1480, "height": 1280},
                             device_scale_factor=2)
            pg.goto(f"http://localhost:{PORT}", wait_until="networkidle")
            pg.wait_for_timeout(5000)

            def _running():
                return pg.evaluate(
                    "()=>{const w=document.querySelector('[data-testid=\"stStatusWidget\"]');"
                    " return !!(w && /run/i.test(w.innerText||''));}")

            def settle(ms=1400):
                # 1) give the rerun a beat to START, 2) wait for it to FINISH.
                pg.wait_for_timeout(900)
                for _ in range(60):                 # up to ~18 s
                    if not _running():
                        break
                    pg.wait_for_timeout(300)
                try:
                    pg.wait_for_load_state("networkidle", timeout=6000)
                except Exception:
                    pass
                pg.wait_for_timeout(ms)

            def tab(text):
                pg.evaluate(
                    "(t)=>{const b=[...document.querySelectorAll('button[role=tab]')]"
                    ".find(x=>x.innerText.trim()===t); if(b)b.click();}", text)
                settle()

            def scroll_to(needle):
                # Prefer headings; match by `includes` so emoji/prefix don't matter.
                found = pg.evaluate(
                    "(t)=>{const tags=['h1','h2','h3','h4','h5','summary','label','p','div'];"
                    " for(const tag of tags){const e=[...document.querySelectorAll(tag)]"
                    ".find(x=>x.innerText && x.innerText.includes(t) && x.innerText.length<200);"
                    " if(e){e.scrollIntoView({block:'start'}); return true;}} return false;}", needle)
                if not found:
                    print("    (scroll target not found:", needle, ")")
                pg.wait_for_timeout(900)
                # Anti-crop nudge: if the first plot below the viewport top is cut off
                # at the bottom, scroll just enough to bring its bottom edge into view.
                pg.evaluate(
                    "()=>{const plots=[...document.querySelectorAll("
                    "'.js-plotly-plot, canvas, [data-testid=\"stImage\"] img')];"
                    " const vh=window.innerHeight;"
                    " const p=plots.map(e=>e.getBoundingClientRect())"
                    ".find(r=>r.height>120 && r.top>=-10 && r.top<vh && r.bottom>vh);"
                    " if(p){window.scrollBy(0, Math.min(p.bottom-vh+24, Math.max(p.top-90,0)));}}")
                pg.wait_for_timeout(600)

            def open_expander(substr):
                pg.evaluate(
                    "(t)=>{document.querySelectorAll('details').forEach(d=>{"
                    "const s=(d.querySelector('summary')||{}).innerText||'';"
                    " if(s.includes(t)) d.open=true;});}", substr)
                pg.wait_for_timeout(700)

            def click_label(substr):
                pg.evaluate(
                    "(t)=>{const l=[...document.querySelectorAll('label')]"
                    ".find(x=>x.innerText && x.innerText.includes(t));"
                    " if(l){(l.querySelector('input')||l).click();}}", substr)
                settle()

            def set_dfi(on=True):
                pg.evaluate(
                    "(want)=>{const d=[...document.querySelectorAll('label')]"
                    ".find(l=>/DFI-capable/i.test(l.innerText));"
                    " const b=d&&d.querySelector('input[type=checkbox]');"
                    " if(b && b.checked!==want) b.click();}", on)
                settle()

            def shot(name):
                pg.screenshot(path=str(IMG / f"{name}.png"))
                print("  ok", name)

            # ── Dashboard ──
            scroll_to("E-POS"); shot("02_app_overview")
            scroll_to("Direct Fluid Indicator"); shot("24_dashboard_dfi_toggle")
            open_expander("Classic POS — source"); scroll_to("Classic POS — source")
            shot("25_dashboard_classic_rose")
            # Stance modes (neutral / custom / base rate) — select base rate to show it
            click_label("Base rate (revert")
            scroll_to("Stance on unknowns"); shot("26_dashboard_stance_modes")
            click_label("Neutral")    # reset so later shots use the neutral stance

            # ── Play / Conditional ──
            tab("Play"); pg.evaluate("window.scrollTo(0,0)"); settle(); shot("27_play_tab")
            tab("Conditional"); pg.evaluate("window.scrollTo(0,0)"); settle(); shot("28_conditional_tab")

            # ── Geological POS sub-tabs ──
            tab("Geological POS")
            tab("Result"); scroll_to("Risk Overview"); shot("07_overview_flags")
            scroll_to("Headline geological POS"); shot("08_esl_vs_classic")
            tab("Diagnostics")
            scroll_to("Pillar fan"); shot("29_geo_pillar_fan")
            scroll_to("Evidence Support Logic Ratio"); shot("30_geo_ratio_plot")
            scroll_to("Chance Adequacy Matrix"); shot("11_cam")
            tab("Detail")
            scroll_to("Risk Element Hierarchy"); shot("31_geo_hierarchy")

            # ── Enable DFI, capture each evidence source ──
            tab("Dashboard"); set_dfi(True)
            tab("Bayesian DFI Update"); settle()

            # Custom R tool (default first option)
            click_label("Custom R tool")
            click_label("Multi-case")  # turn on multi-case if present
            scroll_to("Custom R tool"); shot("12_dfi_custom_setup")
            scroll_to("GeoX hand-off"); shot("35_dfi_custom_geox_src")

            # Pillar-resolved attribution (Custom multi-case, DFI Results)
            tab("DFI Results")
            scroll_to("DFI pillar attribution"); shot("36_dfi_pillar_attribution_full")
            tab("DFI Setup")

            # Characteristic scoring
            click_label("Characteristic scoring")
            scroll_to("Where this prospect sits"); shot("14_dfi_char_density")
            scroll_to("Per-attribute LR"); shot("32_dfi_char_lr_radar")

            # Conceptual DHI Index (experimental)
            click_label("Modified DHI Index")
            scroll_to("Modified DHI Index"); shot("33_dfi_modified_dhi")

            # ── Final Prospect POS ──
            tab("Final Prospect POS"); settle()
            scroll_to("Risk Overview"); shot("19_final_pos")

            # ── CAM with the post-DFI headline-shift overlay (DFI still active) ──
            tab("Geological POS"); tab("Diagnostics")
            scroll_to("Chance Adequacy Matrix"); shot("20_cam_post_dfi")

            # ── Theory ──
            tab("Theory & Guide"); pg.evaluate("window.scrollTo(0,0)"); settle()
            shot("23_theory_overview")
            # Risking-V schematic in the Concepts sub-tab
            tab("Concepts"); settle()
            open_expander("Risking V"); scroll_to("The Risking V")
            shot("22_theory_risking_v")

            br.close()
        print("done - images in", IMG)
        return 0
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
        if moved and HIDDEN_CALIB.exists():
            HIDDEN_CALIB.rename(OVERRIDE_CALIB)
            print("- restored local calibration override")


if __name__ == "__main__":
    raise SystemExit(main())
