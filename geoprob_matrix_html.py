"""Canvas-based GeoProb adequacy matrix for Streamlit components.html."""

def make_geoprob_matrix_html(
    s_n: float,
    s_neg_n: float,
    w: float,
    pos: float,
    eci: float,
    y_esl_commitment: float,
    bel: float,
    pl: float,
    uncertainty: float,
    conflict: float,
    element_name: str,
    r_ev: float,
    g_ev: float,
    sens_b: float,
    y_mode: str,
    y_axis_value: float,
    esl_label: str,
    eci_label: str,
    prms_label: str,
    y_axis_label: str,
) -> str:
    """
    Generate a canvas-based HTML chart replacing the Plotly adequacy matrix.

    All data is baked in as JS variables. The chart renders entirely client-side.
    Returns an HTML string suitable for components.html(...).
    """
    # Determine zone verdict for the primary dot
    # At the dot's position (pos, eci), classify against iso-Pg thresholds
    # at the commitment level C:
    if y_esl_commitment > 1e-9:
        pg_at_dot = (pos - w * (1.0 - y_esl_commitment)) / y_esl_commitment
    else:
        pg_at_dot = 0.5
    pg_at_dot = float(max(0.0, min(1.0, pg_at_dot)))

    if pg_at_dot >= g_ev:
        zone_verdict = "Positive"
        zone_color = "#007a30"
    elif pg_at_dot <= r_ev:
        zone_verdict = "Negative"
        zone_color = "#a30000"
    else:
        zone_verdict = "Uncertain / white"
        zone_color = "#7a6000"

    esl_lbl_safe  = esl_label.replace("'", "\\'").replace('"', '\\"')
    eci_lbl_safe  = eci_label.replace("'", "\\'").replace('"', '\\"')
    prms_lbl_safe = prms_label.replace("'", "\\'").replace('"', '\\"')
    elem_safe     = element_name.replace("'", "\\'").replace('"', '\\"')[:40]
    y_axis_lbl_safe = (
        y_axis_label.replace("'", "\\'").replace('"', '\\"').replace("\n", " ")[:120]
    )

    if y_mode == "eci":
        y_primary = float(eci)
        y_secondary_plot = float(y_esl_commitment)
    elif y_mode == "commitment":
        y_primary = float(y_esl_commitment)
        y_secondary_plot = float(eci)
    else:
        y_primary = float(y_axis_value)
        y_secondary_plot = float(eci)

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body{{margin:0;padding:0;background:transparent;font-family:system-ui,sans-serif}}
  canvas{{display:block;width:100%!important;border-radius:6px}}
  .ctrl-bar{{display:flex;flex-wrap:wrap;gap:5px;margin:8px 0 4px;padding:0 2px}}
  .cb-pill{{font-size:11px;display:inline-flex;align-items:center;gap:5px;cursor:pointer;
    padding:3px 10px;border-radius:12px;border:0.5px solid #ccc;
    background:#fafaf8;user-select:none;white-space:nowrap}}
  .cb-pill input{{margin:0;cursor:pointer;accent-color:#1a50c0}}
  .legend{{display:flex;flex-wrap:wrap;gap:8px 18px;margin:8px 2px 0;
    font-size:10.5px;color:#666;line-height:1.5}}
  .li{{display:flex;align-items:center;gap:5px}}
  .ls{{width:24px;height:3px;border-radius:2px;flex-shrink:0}}
  .lc{{width:11px;height:11px;border-radius:50%;flex-shrink:0}}
  .exp-toggle{{font-size:10.5px;color:#5a82c4;cursor:pointer;margin:6px 2px 0;display:block}}
  .explain{{font-size:11px;color:#555;line-height:1.55;margin:6px 2px 0;
    border-top:0.5px solid #ddd;padding-top:6px}}
</style>
</head>
<body>
<canvas id="gc"></canvas>

<div class="ctrl-bar">
  <label class="cb-pill"><input type="checkbox" id="cbG" checked> ECI gradient field</label>
  <label class="cb-pill"><input type="checkbox" id="cbW" checked> w-intensity</label>
  <label class="cb-pill"><input type="checkbox" id="cbF" checked> Stance fan lines</label>
  <label class="cb-pill"><input type="checkbox" id="cbS"> Sensitivity zones</label>
  <label class="cb-pill"><input type="checkbox" id="cbN"> Risking-V no-go</label>
  <label class="cb-pill"><input type="checkbox" id="cbLog"> Log Y axis</label>
</div>

<div class="legend" id="legendBox"></div>

<span class="exp-toggle" id="expBtn" onclick="toggleExplain()">+ Show chart explanation</span>
<div class="explain" id="explainBox" style="display:none"></div>

<script>
const GC = document.getElementById('gc');
const CTX = GC.getContext('2d');

// ── Data from Python ─────────────────────────────────────────────────────────
const SN   = {float(s_n):.4f};
const SNEG = {float(s_neg_n):.4f};
const W    = {float(w):.4f};
const POS  = {float(pos):.4f};
const ECI  = {float(eci):.4f};
const C    = {float(y_esl_commitment):.4f};
const BEL  = {float(bel):.4f};
const PL   = {float(pl):.4f};
const U    = {float(uncertainty):.4f};
const R_TH = {float(r_ev):.4f};
const G_TH = {float(g_ev):.4f};
const SENS_B = {float(sens_b):.4f};
const CONFLICT = {float(conflict):.4f};
const YVAL = {float(y_axis_value):.4f};
const ELEM = '{elem_safe}';
const ESL_LBL  = '{esl_lbl_safe}';
const ECI_LBL  = '{eci_lbl_safe}';
const PRMS_LBL = '{prms_lbl_safe}';
const ZONE_V   = '{zone_verdict}';
const ZONE_C   = '{zone_color}';
const YPRIM    = {float(y_primary):.4f};
const YSEC2    = {float(y_secondary_plot):.4f};
const YAXLBL   = '{y_axis_lbl_safe}';

// ── Layout ────────────────────────────────────────────────────────────────────
let CW, CH, ML, MR, MT, MB, PW, PH;
function setup() {{
  CW = GC.parentElement.clientWidth || 550;
  CH = Math.round(CW * 0.52);
  GC.width  = CW * devicePixelRatio;
  GC.height = CH * devicePixelRatio;
  GC.style.width  = CW + 'px';
  GC.style.height = CH + 'px';
  CTX.scale(devicePixelRatio, devicePixelRatio);
  ML=52; MR=14; MT=28; MB=44;
  PW = CW - ML - MR;
  PH = CH - MT - MB;
}}

// ── Coordinate transforms (POS axis reversed: 100% on left, 0% on right) ────
const cxP = p => ML + (1 - p) * PW;   // POS → canvas X
// cyE: ECI/Y → canvas Y; log mode maps 1%→100% on a log scale (values below 1% clip to bottom)
function cyE(e) {{
  if (document.getElementById('cbLog').checked) {{
    // Log scale: 100% (e=1) at top, 1% (e=0.01) at bottom → 2 decades
    return MT + (-Math.log10(Math.max(e, 0.01)) / 2) * PH;
  }}
  return MT + (1 - e) * PH;
}}

// ── Feasible envelope (parametric in C) ─────────────────────────────────────
const posMin = C => W * (1 - C);
const posMax = C => C + W * (1 - C);

// ── Color helpers ─────────────────────────────────────────────────────────────
function pgToRgb(Pg) {{
  // Pg ∈ [0,1]: 0=fully negative (red), 0.5=balanced (amber), 1=fully positive (green)
  const RED  = [206, 43, 55];
  const AMB  = [200, 145, 10];
  const GRN  = [0, 146, 70];
  let r, g, b;
  if (Pg >= 0.5) {{
    const t = (Pg - 0.5) * 2;
    r = AMB[0] + (GRN[0]-AMB[0])*t | 0;
    g = AMB[1] + (GRN[1]-AMB[1])*t | 0;
    b = AMB[2] + (GRN[2]-AMB[2])*t | 0;
  }} else {{
    const t = Pg * 2;
    r = RED[0] + (AMB[0]-RED[0])*t | 0;
    g = RED[1] + (AMB[1]-RED[1])*t | 0;
    b = RED[2] + (AMB[2]-RED[2])*t | 0;
  }}
  return [r, g, b];
}}

// ── DRAW ─────────────────────────────────────────────────────────────────────
function draw() {{
  CTX.clearRect(0, 0, CW, CH);

  const dark   = matchMedia('(prefers-color-scheme:dark)').matches;
  const bg     = dark ? '#1c1b18' : '#f4f3f0';
  const tc     = dark ? 'rgba(160,158,148,0.45)' : 'rgba(40,38,30,0.35)';
  const tc2    = dark ? 'rgba(140,138,128,0.25)' : 'rgba(50,48,40,0.15)';
  const tfill  = dark ? '#c8c6be' : '#1e1c18';
  const tMuted = dark ? '#888680' : '#686460';

  const showG = document.getElementById('cbG').checked;
  const showW = document.getElementById('cbW').checked;
  const showF = document.getElementById('cbF').checked;
  const showS = document.getElementById('cbS').checked;
  const showN = document.getElementById('cbN').checked;

  CTX.fillStyle = bg;
  CTX.fillRect(0, 0, CW, CH);

  const logY = document.getElementById('cbLog').checked;

  // ── Grid ──────────────────────────────────────────────────────────────────
  CTX.strokeStyle = tc2;
  CTX.lineWidth = 0.5;
  const yGridTicks = logY
    ? [0.01, 0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 0.70, 1.00]
    : [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0];
  for (let i = 0; i <= 10; i++) {{
    const xg = cxP(i/10);
    CTX.beginPath(); CTX.moveTo(xg, MT); CTX.lineTo(xg, MT+PH); CTX.stroke();
  }}
  yGridTicks.forEach(v => {{
    const yg = cyE(v);
    CTX.beginPath(); CTX.moveTo(ML, yg); CTX.lineTo(ML+PW, yg); CTX.stroke();
  }});

  // ── ECI gradient field ────────────────────────────────────────────────────
  // Colors every point in the feasible region by its implied Pg.
  // Saturation = C (commitment level), so low-C areas are pastel.
  // w-intensity modifier: when showW, desaturate when w deviates from 0.5.
  const wMod = showW ? (1 - 0.45 * Math.abs(2*W - 1)) : 1.0;

  if (showG) {{
    const N_rows = Math.ceil(PH);
    const N_cols = Math.ceil(PW);
    const imgData = CTX.createImageData(N_cols, N_rows);

    for (let row = 0; row < N_rows; row++) {{
      // In log mode canvas rows map to C values on a log scale (1% at bottom, 100% at top)
      const frac = row / N_rows;
      const Cval = logY ? Math.pow(10, -2 * frac) : 1 - frac;
      if (Cval < 0.002) continue;
      const pmin = posMin(Cval);
      const pmax = posMax(Cval);
      const col0 = Math.max(0, Math.floor((1 - pmax) * N_cols));
      const col1 = Math.min(N_cols - 1, Math.ceil((1 - pmin) * N_cols));

      for (let col = col0; col <= col1; col++) {{
        const posH = 1 - col / N_cols;
        if (posH < pmin - 0.003 || posH > pmax + 0.003) continue;

        // Implied Pg at this (POS, C) point
        const Pg = (posH - W * (1 - Cval)) / Cval;
        if (Pg < -0.02 || Pg > 1.02) continue;
        const Pgc = Math.max(0, Math.min(1, Pg));

        // Saturation: scales with C (more committed = more saturated)
        // Floor at 0.12 so even ECI=0 is visibly amber (not white void)
        const sat = Math.min(1, 0.12 + Cval * 0.88) * wMod;

        const [r, g, b] = pgToRgb(Pgc);
        // Blend toward white at low saturation
        const rr = (255 + (r - 255) * sat) | 0;
        const gg = (255 + (g - 255) * sat) | 0;
        const bb = (255 + (b - 255) * sat) | 0;
        const alpha = Math.round(sat * 195 + 30);

        const idx = (row * N_cols + col) * 4;
        imgData.data[idx]   = rr;
        imgData.data[idx+1] = gg;
        imgData.data[idx+2] = bb;
        imgData.data[idx+3] = alpha;
      }}
    }}
    CTX.putImageData(imgData, ML, MT);
  }} else {{
    // No gradient: draw simple green/white/red triangle zones
    const wF = wMod * 0.50;
    // Positive zone
    CTX.beginPath();
    CTX.moveTo(cxP(W), cyE(0));
    for (let i = 0; i <= 120; i++) {{
      const Cv = i/120;
      const pp = Math.min(posMax(Cv), G_TH*Cv + W*(1-Cv));
      CTX.lineTo(cxP(pp), cyE(Cv));
    }}
    for (let i = 120; i >= 0; i--) {{
      const Cv = i/120;
      CTX.lineTo(cxP(posMax(Cv)), cyE(Cv));
    }}
    CTX.closePath();
    CTX.fillStyle = `rgba(0,146,70,${{wF.toFixed(2)}})`;
    CTX.fill();
    // Negative zone
    CTX.beginPath();
    CTX.moveTo(cxP(W), cyE(0));
    for (let i = 0; i <= 120; i++) {{
      const Cv = i/120;
      const pp = Math.max(posMin(Cv), R_TH*Cv + W*(1-Cv));
      CTX.lineTo(cxP(pp), cyE(Cv));
    }}
    for (let i = 120; i >= 0; i--) {{
      const Cv = i/120;
      CTX.lineTo(cxP(posMin(Cv)), cyE(Cv));
    }}
    CTX.closePath();
    CTX.fillStyle = `rgba(206,43,55,${{wF.toFixed(2)}})`;
    CTX.fill();
  }}

  // ── Sensitivity zones (faint tint ±b around boundary lines) ──────────────
  if (showS && SENS_B > 0.003) {{
    const b = SENS_B;
    // Positive sensitivity (between g and g-b)
    CTX.beginPath();
    CTX.moveTo(cxP(W), cyE(0));
    for (let i = 0; i <= 120; i++) {{
      const Cv = i/120;
      const p0 = G_TH*Cv + W*(1-Cv);
      const p1 = Math.min(posMax(Cv), (G_TH-b)*Cv + W*(1-Cv));
      CTX.lineTo(cxP(Math.min(p0, posMax(Cv))), cyE(Cv));
    }}
    for (let i = 120; i >= 0; i--) {{
      const Cv = i/120;
      const p1 = Math.min(posMax(Cv), (G_TH-b)*Cv + W*(1-Cv));
      CTX.lineTo(cxP(Math.max(p1, W*(1-Cv))), cyE(Cv));
    }}
    CTX.closePath();
    CTX.fillStyle = 'rgba(0,146,70,0.13)';
    CTX.fill();
    // Negative sensitivity (between r and r+b)
    CTX.beginPath();
    CTX.moveTo(cxP(W), cyE(0));
    for (let i = 0; i <= 120; i++) {{
      const Cv = i/120;
      const p0 = R_TH*Cv + W*(1-Cv);
      const p1 = Math.max(posMin(Cv), (R_TH+b)*Cv + W*(1-Cv));
      CTX.lineTo(cxP(Math.max(p0, posMin(Cv))), cyE(Cv));
    }}
    for (let i = 120; i >= 0; i--) {{
      const Cv = i/120;
      const p1 = Math.max(posMin(Cv), (R_TH+b)*Cv + W*(1-Cv));
      CTX.lineTo(cxP(Math.min(p1, C+W*(1-Cv))), cyE(Cv));
    }}
    CTX.closePath();
    CTX.fillStyle = 'rgba(206,43,55,0.13)';
    CTX.fill();
  }}

  // ── Risking-V "legacy no-go" (high commitment + middling POS) ──────────────
  // Rose / ExxonMobil's original forbidden upper-centre. Drawn only as a faint,
  // labelled REFERENCE — it applies to a BINARY state of nature (0 or 1), not to a
  // probability, so it is superseded for E-POS's P(G) (ExxonMobil 2018). The Bel/Pl
  // envelope already carries this information continuously. See Theory & Guide.
  if (showN) {{
    const Cs = 0.55;                    // "high confidence" threshold
    CTX.beginPath();
    let started = false;
    for (let i = 0; i <= 120; i++) {{
      const Cv = Cs + (1 - Cs) * (i / 120);
      const pr = Math.max(posMin(Cv), R_TH * Cv + W * (1 - Cv));   // red boundary
      const X = cxP(pr), Y = cyE(Cv);
      if (!started) {{ CTX.moveTo(X, Y); started = true; }} else {{ CTX.lineTo(X, Y); }}
    }}
    for (let i = 120; i >= 0; i--) {{
      const Cv = Cs + (1 - Cs) * (i / 120);
      const pg = Math.min(posMax(Cv), G_TH * Cv + W * (1 - Cv));   // green boundary
      CTX.lineTo(cxP(pg), cyE(Cv));
    }}
    CTX.closePath();
    CTX.fillStyle = 'rgba(124,92,160,0.15)';
    CTX.fill();
    CTX.strokeStyle = 'rgba(124,92,160,0.55)';
    CTX.setLineDash([4, 3]); CTX.lineWidth = 1; CTX.stroke(); CTX.setLineDash([]);
    CTX.fillStyle = 'rgba(95,65,135,0.92)';
    CTX.font = '10px -apple-system,system-ui,sans-serif';
    CTX.textAlign = 'center';
    const Clab = 0.9;
    const xlab = cxP(((R_TH + G_TH) / 2) * Clab + W * (1 - Clab));
    CTX.fillText('legacy no-go', xlab, cyE(0.84));
    CTX.fillText('(binary-state only)', xlab, cyE(0.84) + 11);
    CTX.textAlign = 'left';
  }}

  // ── Stance fan lines ───────────────────────────────────────────────────────
  // Each line = where the dot would move if w changed (iso-w curves).
  // Solid = POS_min(w); dashed = POS_max(w).
  // Color = direction implied by the current evidence at each w.
  if (showF) {{
    for (let fi = 1; fi <= 9; fi++) {{
      const wi = fi / 10;
      if (Math.abs(wi - W) < 0.04) continue;
      const dist = Math.abs(wi - W);
      const alpha = (0.12 + 0.22 * Math.max(0, 1 - dist / 0.45)).toFixed(2);
      // Color based on Pg at this w with current evidence:
      const Cesl = SN + SNEG;
      const posAtW = Math.min(1, Math.max(0, SN + wi * Math.max(0, 1 - Cesl)));
      const Pgw = Cesl > 0.01 ? (posAtW - wi * Math.max(0, 1-Cesl)) / Cesl : 0.5;
      const Pgwc = Math.max(0, Math.min(1, Pgw));
      const [rr, gg, bb] = pgToRgb(Pgwc);
      const lineColor = showG
        ? `rgba(${{rr}},${{gg}},${{bb}},${{alpha}})`
        : `rgba(100,100,110,${{alpha}})`;

      // Min line (S_n=0, all mass on negative side)
      CTX.beginPath();
      CTX.moveTo(cxP(wi), cyE(0));
      for (let i = 1; i <= 100; i++) {{
        const Cv = i/100;
        CTX.lineTo(cxP(wi*(1-Cv)), cyE(Cv));
      }}
      CTX.strokeStyle = dark ? `rgba(200,80,80,${{alpha}})` : lineColor;
      CTX.lineWidth = 0.65;
      CTX.setLineDash([]);
      CTX.stroke();

      // Max line (S_n=C, all mass on positive side)
      CTX.beginPath();
      CTX.moveTo(cxP(wi), cyE(0));
      for (let i = 1; i <= 100; i++) {{
        const Cv = i/100;
        CTX.lineTo(cxP(Cv + wi*(1-Cv)), cyE(Cv));
      }}
      CTX.strokeStyle = dark ? `rgba(0,140,60,${{alpha}})` : lineColor;
      CTX.lineWidth = 0.65;
      CTX.setLineDash([3, 3]);
      CTX.stroke();
    }}
    CTX.setLineDash([]);
  }}

  // ── Zone boundary lines (iso-Pg diagonals) ──────────────────────────────
  // Color gradients from gray at apex (low C) to full color at top (high C).
  function drawBoundary(Pg_th, isPos) {{
    const pts = [];
    for (let i = 0; i <= 200; i++) {{
      const Cv = i / 200;
      const pp = Pg_th * Cv + W * (1 - Cv);
      const inBand = pp >= posMin(Cv) - 0.003 && pp <= posMax(Cv) + 0.003;
      if (inBand) pts.push({{ x: cxP(pp), y: cyE(Cv), C: Cv }});
    }}
    if (pts.length < 2) return;
    for (let i = 0; i < pts.length - 1; i++) {{
      const avgC = (pts[i].C + pts[i+1].C) / 2;
      const sat = Math.min(1, avgC * 2.0);
      const alpha = (0.25 + 0.70 * sat).toFixed(2);
      CTX.beginPath();
      CTX.moveTo(pts[i].x, pts[i].y);
      CTX.lineTo(pts[i+1].x, pts[i+1].y);
      // Fade from gray (low C) to full color (high C)
      if (isPos) {{
        const g_comp = Math.round(90 + 56 * sat);
        CTX.strokeStyle = `rgba(0,${{g_comp}},40,${{alpha}})`;
      }} else {{
        const r_comp = Math.round(100 + 106 * sat);
        CTX.strokeStyle = `rgba(${{r_comp}},0,20,${{alpha}})`;
      }}
      CTX.lineWidth = 1.8;
      CTX.setLineDash([]);
      CTX.stroke();
    }}
  }}
  drawBoundary(R_TH, false);
  drawBoundary(G_TH, true);

  // Sensitivity boundary lines (dashed, if shown)
  if (showS && SENS_B > 0.003) {{
    function drawSensBnd(Pg_th, isPos) {{
      const pts = [];
      for (let i = 0; i <= 200; i++) {{
        const Cv = i / 200;
        const pp = Pg_th * Cv + W * (1 - Cv);
        if (pp >= posMin(Cv) - 0.003 && pp <= posMax(Cv) + 0.003)
          pts.push({{ x: cxP(pp), y: cyE(Cv) }});
      }}
      if (pts.length < 2) return;
      CTX.beginPath();
      pts.forEach((p, i) => i === 0 ? CTX.moveTo(p.x, p.y) : CTX.lineTo(p.x, p.y));
      CTX.strokeStyle = isPos ? 'rgba(0,120,50,0.38)' : 'rgba(180,20,30,0.38)';
      CTX.lineWidth = 1.0;
      CTX.setLineDash([4, 4]);
      CTX.stroke();
      CTX.setLineDash([]);
    }}
    drawSensBnd(Math.max(0, G_TH - SENS_B), true);
    drawSensBnd(Math.min(1, R_TH + SENS_B), false);
  }}

  // ── Feasible band boundary (envelope min/max POS curves) ─────────────────
  CTX.beginPath();
  CTX.moveTo(cxP(posMin(0)), cyE(0));
  for (let i = 1; i <= 120; i++) {{
    const Cv = i/120;
    CTX.lineTo(cxP(posMin(Cv)), cyE(Cv));
  }}
  CTX.strokeStyle = dark ? 'rgba(100,150,220,0.40)' : 'rgba(25,55,140,0.40)';
  CTX.lineWidth = 1.2;
  CTX.setLineDash([4, 3]);
  CTX.stroke();
  CTX.beginPath();
  CTX.moveTo(cxP(posMax(0)), cyE(0));
  for (let i = 1; i <= 120; i++) {{
    const Cv = i/120;
    CTX.lineTo(cxP(posMax(Cv)), cyE(Cv));
  }}
  CTX.strokeStyle = dark ? 'rgba(100,150,220,0.40)' : 'rgba(25,55,140,0.40)';
  CTX.lineWidth = 1.2;
  CTX.setLineDash([2, 4]);
  CTX.stroke();
  CTX.setLineDash([]);

  // ── Bel/Pl interval band at primary Y height ─────────────────────────────
  const yMain = cyE(YPRIM);
  const belX = cxP(BEL), plX = cxP(PL);
  CTX.fillStyle = 'rgba(26,80,192,0.08)';
  CTX.fillRect(Math.min(belX, plX), yMain - 5, Math.abs(plX - belX), 10);
  CTX.beginPath();
  CTX.moveTo(plX, yMain);
  CTX.lineTo(belX, yMain);
  CTX.strokeStyle = 'rgba(26,80,192,0.65)';
  CTX.lineWidth = 2;
  CTX.stroke();
  // Bel marker (red)
  CTX.beginPath(); CTX.moveTo(belX, yMain-5); CTX.lineTo(belX, yMain+5);
  CTX.strokeStyle = 'rgba(190,30,40,0.70)'; CTX.lineWidth = 1.8; CTX.stroke();
  // Pl marker (green)
  CTX.beginPath(); CTX.moveTo(plX, yMain-5); CTX.lineTo(plX, yMain+5);
  CTX.strokeStyle = 'rgba(0,110,50,0.70)'; CTX.lineWidth = 1.8; CTX.stroke();

  // ── Secondary reference dot (gray) when Y_primary differs from alternate ─
  if (Math.abs(YPRIM - YSEC2) > 0.015) {{
    const posX = cxP(POS), y2 = cyE(YSEC2);
    CTX.beginPath(); CTX.moveTo(posX, yMain); CTX.lineTo(posX, y2);
    CTX.strokeStyle = 'rgba(110,110,130,0.22)';
    CTX.lineWidth = 1; CTX.setLineDash([3,3]); CTX.stroke();
    CTX.setLineDash([]);
    CTX.beginPath(); CTX.arc(posX, y2, 7, 0, Math.PI*2);
    CTX.fillStyle = 'rgba(110,110,130,0.28)'; CTX.fill();
    CTX.strokeStyle = 'rgba(110,110,130,0.55)'; CTX.lineWidth = 1.5; CTX.stroke();
  }}

  // ── Primary dot ───────────────────────────────────────────────────────────
  const posX = cxP(POS);
  CTX.beginPath(); CTX.arc(posX, yMain, 9, 0, Math.PI*2);
  CTX.fillStyle = CONFLICT > 0.01 ? '#c8a000' : '#1a50c0';
  CTX.fill();
  CTX.strokeStyle = '#fff'; CTX.lineWidth = 2; CTX.stroke();

  // ── Axes ──────────────────────────────────────────────────────────────────
  CTX.strokeStyle = tc;
  CTX.lineWidth = 0.8;
  CTX.beginPath();
  CTX.moveTo(ML, MT); CTX.lineTo(ML, MT+PH); CTX.lineTo(ML+PW, MT+PH);
  CTX.stroke();

  CTX.font = '10.5px system-ui,sans-serif';
  CTX.fillStyle = tMuted;
  for (let i = 0; i <= 10; i++) {{
    const p = i/10;
    CTX.textAlign = 'center';
    CTX.fillText(Math.round(p*100)+'%', cxP(p), MT+PH+13);
  }}
  yGridTicks.forEach(v => {{
    CTX.textAlign = 'right';
    const lbl = v < 0.095 ? (v*100).toFixed(0)+'%' : Math.round(v*100)+'%';
    CTX.fillText(lbl, ML-4, cyE(v)+3.5);
  }});
  CTX.textAlign = 'center';
  CTX.fillStyle = tMuted;
  CTX.font = '11px system-ui,sans-serif';
  CTX.fillText('Probability of Success (POS)', ML + PW/2, CH - 8);
  CTX.save();
  CTX.translate(11, MT + PH/2);
  CTX.rotate(-Math.PI/2);
  CTX.fillText(YAXLBL.length > 42 ? YAXLBL.slice(0, 40) + '…' : YAXLBL, 0, 0);
  CTX.restore();

  // ── Overlay readout ───────────────────────────────────────────────────────
  const oBg = dark ? 'rgba(28,27,24,0.85)' : 'rgba(246,244,240,0.90)';
  const oBd = dark ? 'rgba(100,98,90,0.40)' : 'rgba(150,148,140,0.35)';
  const ow = 228, oh = 70;
  const ox = ML + PW - ow - 5, oy = MT + PH - oh - 5;
  CTX.fillStyle = oBg;
  CTX.strokeStyle = oBd;
  CTX.lineWidth = 0.5;
  CTX.fillRect(ox, oy, ow, oh);
  CTX.strokeRect(ox, oy, ow, oh);

  CTX.font = '500 11px system-ui,sans-serif';
  CTX.fillStyle = tfill;
  CTX.textAlign = 'left';
  CTX.fillText(`POS=${{(POS*100).toFixed(0)}}%  ECI=${{(ECI*100).toFixed(0)}}%  C=${{(C*100).toFixed(0)}}%`, ox+7, oy+16);
  CTX.font = '500 11px system-ui,sans-serif';
  CTX.fillStyle = ZONE_C;
  CTX.textAlign = 'right';
  CTX.fillText(ZONE_V, ox+ow-7, oy+16);

  CTX.font = '10px system-ui,sans-serif';
  CTX.fillStyle = tMuted;
  CTX.textAlign = 'left';
  CTX.fillText(`Bel=${{(BEL*100).toFixed(0)}}%  Pl=${{(PL*100).toFixed(0)}}%  U=${{(U*100).toFixed(0)}}%`, ox+7, oy+31);
  CTX.fillText(`S_for=${{(SN*100).toFixed(0)}}%  S_against=${{(SNEG*100).toFixed(0)}}%  w=${{(W*100).toFixed(0)}}%`, ox+7, oy+45);
  CTX.fillText(`${{PRMS_LBL}}  |  ECI: ${{ECI_LBL.slice(0,30)}}`, ox+7, oy+59);
}}

// ── Legend ────────────────────────────────────────────────────────────────────
function buildLegend() {{
  const el = document.getElementById('legendBox');
  const items = [
    ['#1a50c0', 'circle', 'Current assessment (POS, primary Y)'],
    ['rgba(110,110,130,0.45)', 'circle', 'Reference (POS, alternate Y: ECI or C)'],
    ['rgba(0,110,50,0.7)', 'line-solid', 'Positive zone boundary (Pg = g = 1−S_for)'],
    ['rgba(180,20,30,0.7)', 'line-solid', 'Negative zone boundary (Pg = r = S_against)'],
    ['rgba(26,80,192,0.6)', 'line-horiz', 'Defensible POS range [Bel, Pl]'],
    ['rgba(25,55,140,0.4)', 'line-dashed', 'Min/max POS envelope (S_for=0 / S_for=C)'],
    ['rgba(124,92,160,0.6)', 'line-dashed', 'Risking-V legacy no-go (binary-state only; superseded)'],
  ];
  el.innerHTML = items.map(([col, type, lbl]) => {{
    let shape = '';
    if (type === 'circle')
      shape = `<div class="lc" style="background:${{col}};border:1.5px solid ${{col}}"></div>`;
    else if (type === 'line-solid')
      shape = `<div class="ls" style="background:${{col}};height:2.5px"></div>`;
    else if (type === 'line-horiz')
      shape = `<div class="ls" style="background:${{col}};height:2.5px;width:22px"></div>`;
    else
      shape = `<div class="ls" style="background:repeating-linear-gradient(90deg,${{col}} 0,${{col}} 3px,transparent 3px,transparent 6px);height:2px"></div>`;
    return `<div class="li">${{shape}}<span>${{lbl}}</span></div>`;
  }}).join('');
}}

// ── Explain panel ─────────────────────────────────────────────────────────────
function toggleExplain() {{
  const box = document.getElementById('explainBox');
  const btn = document.getElementById('expBtn');
  const hidden = box.style.display === 'none';
  box.style.display = hidden ? 'block' : 'none';
  btn.textContent = hidden ? '− Hide explanation' : '+ Show chart explanation';
  if (hidden) {{
    box.innerHTML = `
<strong>How to read this chart</strong><br>
<b>X-axis:</b> Probability of Success (POS), reversed — high POS on left, low on right.<br>
<b>Y-axis:</b> Evidence Clarity Index (ECI = |S_for − S_against|) by default, or ESL Commitment C = S_for + S_against in C-mode.<br>
<br>
<b>ECI gradient field:</b> Colors every point in the feasible region by its implied evidence direction.
Green = positive Pg (more green than red), amber = balanced (indeterminate), red = negative.
Saturation increases with commitment C — pale colors near the apex mean low evidence commitment,
even if the direction looks clear. With w-intensity ON, the saturation also washes out when your
stance w is extreme (0% or 100%), signalling that the zone classification depends partly on your
risk attitude, not just the evidence.<br>
<br>
<b>Feasible region:</b> Bounded by the min-POS (dotted line, S_for=0) and max-POS (dashed line, S_for=C) curves.
Every assessment must lie within this band. The apex — where both lines converge at POS=w, C=0 —
is the total-ignorance point: with no evidence committed, POS equals your stance regardless of direction.<br>
<br>
<b>Zone boundary lines (green/red diagonals):</b> Iso-Pg lines where Pg = g = 1−S_for (green) and
Pg = r = S_against (red). Points to the left of the green line are in the positive zone;
points to the right of the red line are in the negative zone. These fade from gray at the apex
(zone membership means nothing when C≈0) to full color at the top (unambiguous zone classification).<br>
<br>
<b>Stance fan lines:</b> Show where your dot would move if you changed w while keeping S_for and S_against fixed.
Solid fan lines = POS_min (w votes against, S_for=0 scenario); dashed = POS_max.
These are NOT commitment lines — they are sensitivity-to-stance lines. Your dot lies between them.<br>
<br>
<b>Blue dot:</b> Your current assessment at (POS, ECI). In ECI mode, this is always inside the gradient field.
<b>Gray dot:</b> Where the same assessment would plot if Y = C (ESL commitment mode). When these are far apart,
the ESL–ROSE tension is high: you have lots of committed evidence (high C) but low directional clarity (low ECI).<br>
<br>
<b>Bel/Pl bar:</b> The defensible POS range. Bel = S_for (pessimistic bound, w=0); Pl = 1−S_against (optimistic bound, w=1).
The blue tick is your current POS at stance w. Any POS within this range is mathematically defensible
given your evidence masses.<br>
<br>
<b>Risking-V no-go (toggle):</b> The faint violet region is Rose / ExxonMobil's original "no-go" — high
confidence (high commitment) with a middling chance. It only applies when the state of nature is BINARY
(0 or 1); for a probability / success-ratio it is superseded (ExxonMobil 2018), so E-POS shows it as a
labelled reference, never a forbidden zone. The Bel/Pl envelope already carries this continuously.
See <b>Theory &amp; Guide → "The Risking V & the no-go zone"</b>.<br>
<br>
<b>Log Y axis toggle:</b> Switches the Y axis from linear (0%–100%) to a two-decade log scale (1%–100%).
Useful when ECI or C is small (&lt;20%): the log scale stretches the low-evidence region so you can
see where your dot sits relative to the zone boundaries. The gradient field and all curves redraw
consistently in log space.`;
  }}
}}

// ── Wiring ────────────────────────────────────────────────────────────────────
['cbG','cbW','cbF','cbS','cbN','cbLog'].forEach(id => {{
  document.getElementById(id).addEventListener('change', draw);
}});
window.addEventListener('resize', () => {{ setup(); draw(); }});
matchMedia('(prefers-color-scheme:dark)').addEventListener('change', draw);

setup();
draw();
buildLegend();
</script>
</body>
</html>
"""