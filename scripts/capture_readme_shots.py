"""Capture README screenshots from the live E-POS app (Playwright).

Drives the real Streamlit app and saves PNGs to ``docs/img/``. To regenerate the
README gallery after a UI change::

    python scripts/capture_readme_shots.py

IP safety: the real ``data/saam_calibration.json`` (if present) is temporarily
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
REAL_CALIB = ROOT / "data" / "saam_calibration.json"
HIDDEN_CALIB = ROOT / "data" / "_saam_calibration.hidden"


def _free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def main() -> int:
    from playwright.sync_api import sync_playwright

    IMG.mkdir(parents=True, exist_ok=True)
    moved = False
    proc = None
    try:
        if REAL_CALIB.exists():
            REAL_CALIB.rename(HIDDEN_CALIB)
            moved = True
            print("- hid real calibration; placeholder will be used")

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
            pg = br.new_page(viewport={"width": 1480, "height": 1000},
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
                pg.wait_for_timeout(1200)

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
            scroll_to("E-POS"); shot("01_app_overview")
            scroll_to("Direct Fluid Indicator"); shot("02_dashboard_dfi_toggle")
            open_expander("Classic POS — source"); scroll_to("Classic POS — source")
            shot("03_dashboard_classic_rose")

            # ── Play / Conditional ──
            tab("Play"); pg.evaluate("window.scrollTo(0,0)"); settle(); shot("04_play_tab")
            tab("Conditional"); pg.evaluate("window.scrollTo(0,0)"); settle(); shot("05_conditional_tab")

            # ── Geological POS sub-tabs ──
            tab("Geological POS")
            tab("Result"); scroll_to("Risk Overview"); shot("06_geo_result_overview")
            scroll_to("Headline geological POS"); shot("07_geo_esl_vs_classic")
            tab("Diagnostics")
            scroll_to("Pillar fan"); shot("08_geo_pillar_fan")
            scroll_to("Evidence Support Logic Ratio"); shot("09_geo_ratio_plot")
            scroll_to("Chance Adequacy Matrix"); shot("10_geo_cam")
            tab("Detail")
            scroll_to("Risk Element Hierarchy"); shot("11_geo_hierarchy")

            # ── Enable DFI, capture each evidence source ──
            tab("Dashboard"); set_dfi(True)
            tab("Bayesian DFI Update"); settle()

            # Custom R tool (default first option)
            click_label("Custom R tool")
            click_label("Multi-case")  # turn on multi-case if present
            scroll_to("Custom R tool"); shot("12_dfi_custom_setup")
            scroll_to("GeoX hand-off"); shot("13_dfi_custom_geox")

            # Characteristic scoring
            click_label("Characteristic scoring")
            scroll_to("Where this prospect sits"); shot("14_dfi_char_density")
            scroll_to("Per-attribute LR"); shot("15_dfi_char_lr_radar")

            # Modified DHI Index (SAAM)
            click_label("Modified DHI Index")
            scroll_to("Modified DHI Index"); shot("16_dfi_modified_dhi")

            # ── Final Prospect POS ──
            tab("Final Prospect POS"); settle()
            scroll_to("Risk Overview"); shot("17_final_pos")

            # ── Theory ──
            tab("Theory & Guide"); pg.evaluate("window.scrollTo(0,0)"); settle()
            shot("18_theory_overview")

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
            HIDDEN_CALIB.rename(REAL_CALIB)
            print("- restored real calibration")


if __name__ == "__main__":
    raise SystemExit(main())
