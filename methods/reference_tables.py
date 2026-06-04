"""
Reference Probability Tables — Milkov (2015), Malvić (2009), CCOP (2000)

These tables are reproduced for EDUCATIONAL and CALIBRATION purposes only.
No calculations are performed here. Values are displayed as published.

NOTE on geological terminology:
  The published reference tables below use the historical term "Trap" freely
  (e.g. "Position of Trap", "Trap timing", "Structural Trap Style") because
  that is the language of the source literature. These are geological
  *concepts* in the reference text — they are NOT pillar identifiers.
  The E-POS app uses the pillar id "Closure" (matching its display name) for
  the equivalent risk pillar. The two terms refer to the same underlying
  geology; only the in-app symbol differs.

Sources:
  Milkov, A.V. (2015). Risk tables for less biased and more consistent geologic
    risk assessment in petroleum exploration. Earth-Science Reviews, 150, 453-476.
    DOI: 10.1016/j.earscirev.2015.08.006
    https://www.sciencedirect.com/science/article/abs/pii/S0012825215300301

  Malvić, T. (2009). Stochastical approach in deterministic calculation of
    geological risk. Geologia Croatica, 62(2), 67-78.
    Full text: https://hrcak.srce.hr/file/71373

  CCOP (2000). CCOP Guideline for Risk Assessment of Petroleum Prospects.
    Coordinating Committee for Coastal and Offshore Geoscience Programmes in
    East and Southeast Asia (CCOP), Technical Bulletin 33.
    Full text: https://www.scribd.com/document/327676318/2912004-4-pdf
"""

from __future__ import annotations
import streamlit as st

# ── DHI / geophysical evidence row marker ───────────────────────────────────
_DHI_FLAG = "⚠️DHI"   # sentinel string present in condition text for DHI rows

# ── Colour scale (shared single source of truth in components.colors) ────────
from components.colors import COS_SCALE as _COS_SCALE, cos_color as _cos_color  # noqa: F401


def _pct(v: float) -> str:
    return f"{v*100:.0f}%"


# ────────────────────────────────────────────────────────────────────────────
# DATA TABLES
# ────────────────────────────────────────────────────────────────────────────

# Each row: (sub_category, condition, cos_value_or_range, is_dhi, notes)
# cos_value_or_range: float for single value; tuple(lo,hi) for range
# is_dhi: bool — True if row embeds DHI / seismic amplitude evidence

MILKOV_2015: dict[str, list[tuple]] = {
    "1. Structure": [
        ("Model: Relief & Complexity",
         "High relief structure / Low structural complexity", 0.90, False,
         "Well-defined 3-way or 4-way closure; minimal depth-conversion uncertainty"),
        ("Model: Relief & Complexity",
         "Medium relief structure / High structural complexity", 0.65, False,
         "Moderate closure; some uncertainty in lateral extent"),
        ("Model: Relief & Complexity",
         "Low relief structure / High uncertainty of depth conversion / Rapidly changing lateral velocities", 0.35, False,
         "Poor depth-to-time conversion; closure difficult to confirm"),
        ("Model: Relief & Complexity",
         "Low relief + BOTH high depth-conversion uncertainty AND rapidly changing velocities", 0.15, False,
         "Very uncertain closure; may not exist post-depth conversion"),
        ("Model: Interpretation Ability",
         "Easy to interpret — correlation based on nearby wells (<50 km)", 0.90, False,
         "Well-calibrated seismic ties; stratigraphic correlations certain"),
        ("Model: Interpretation Ability",
         "Uncertain correlation — based on remote wells (>50 km)", 0.60, False,
         "Analogue ties only; interpretation has meaningful ambiguity"),
        ("Model: Interpretation Ability",
         "Difficult to interpret — horizons interrupted by thrust faults / salt diapirs", 0.30, False,
         "Complex structural environment; dip and fault geometry poorly constrained"),
        ("Data: Seismic Type",
         "3D Seismic Data available", 0.90, False,
         "Full 3D imaging; supports detailed structure mapping"),
        ("Data: Seismic Type",
         "2D Seismic Data only", 0.55, False,
         "Sparse coverage; lateral interpolation required between lines"),
        ("Data: 2D Line Density",
         "Dense 2D grid — 7 lines or more", 0.80, False,
         "Dense enough for reliable structural mapping"),
        ("Data: 2D Line Density",
         "Sparse 2D grid — 3–6 lines", 0.55, False,
         "Adequate but requires interpolation"),
        ("Data: 2D Line Density",
         "Very sparse 2D — only 2 lines (Lead-level)", 0.25, False,
         "Insufficient data; structural definition is speculative"),
    ],
    "2. Reservoir Facies": [
        ("Model: Depositional Env. — Marine",
         "Shallow marine blanket deposit / Carbonates", 0.85, False,
         "Laterally extensive, predictable reservoirs; high presence probability"),
        ("Model: Depositional Env. — Marine",
         "Coastal / Fluvio-deltaic / Deltaic / Tidal", 0.75, False,
         "Good continuity but some lateral heterogeneity expected"),
        ("Model: Depositional Env. — Marine",
         "Deep-water turbidites (channels, fans)", 0.65, False,
         "Variable geometry; channels can be highly localised"),
        ("Model: Depositional Env. — Continental",
         "Eolian", 0.80, False,
         "Excellent reservoir quality but geographically restricted"),
        ("Model: Depositional Env. — Continental",
         "Lacustrine", 0.55, False,
         "Moderate quality; dependent on lake-system maturity"),
        ("Model: Depositional Env. — Continental",
         "Alluvial fan / Braided stream", 0.50, False,
         "Heterogeneous; interconnectivity uncertain"),
        ("Model: Depositional Env. — Continental",
         "Meandering channels", 0.45, False,
         "Poor lateral continuity; highly compartmentalised"),
        ("Model: Special",
         "Fractured basement or porous lava", 0.40, False,
         "Reservoir presence depends on fracture density; difficult to predict"),
        ("Data: Well Distance",
         "All wells within 50 km have reservoir", 0.90, False,
         "Proximal well control confirms reservoir presence in trend"),
        ("Data: Well Distance",
         "All wells 50–100 km away have reservoir", 0.75, False,
         "Distal but positive analogue"),
        ("Data: Well Distance",
         "Not all wells within 100 km have reservoir", 0.50, False,
         "Inconsistent data; reservoir presence uncertain"),
        ("Data: Well Distance",
         "All wells within 100 km LACK reservoir", 0.10, False,
         "Strong negative evidence; reservoir absence likely"),
        ("Data: Well Distance",
         "No wells closer than 100 km in the play", 0.45, False,
         "No direct data; relies entirely on depositional model"),
        ("Data: Seismic Visibility",
         "Reservoir facies appear on seismic data", 0.85, False,
         "Seismic facies support reservoir presence in prospect area"),
        ("Data: Seismic Visibility",
         "Reservoir presence not visible on seismic data", 0.40, False,
         "Absence of seismic facies response; reservoir inferred only"),
    ],
    "3. Reservoir Deliverability": [
        ("Model: Burial Temp. — Clastics",
         "35–100°C for oil OR <120°C for gas (optimal window)", 0.85, False,
         "Porosity well-preserved; diagenesis limited"),
        ("Model: Burial Temp. — Clastics",
         "100–130°C for oil OR 120–150°C for gas (moderate)", 0.60, False,
         "Partial cementation expected; porosity reduced but often commercial"),
        ("Model: Burial Temp. — Clastics",
         ">130°C for oil OR >150°C for gas OR oil at <35°C (unfavourable)", 0.25, False,
         "Significant cementation/biodegradation likely; deliverability poor"),
        ("Model: Reservoir Facies Quality — Clastics",
         "Homogeneous, clean, quartz-dominated reservoir", 0.85, False,
         "Best-quality clastic reservoir; high perm/porosity expected"),
        ("Model: Reservoir Facies Quality — Clastics",
         "Homogeneous reservoir dominated by arkoses / graywackes", 0.65, False,
         "Good quality but more susceptible to diagenetic cementation"),
        ("Model: Diagenesis Modifier — Clastics",
         "Early petroleum migration (before burial to >130–150°C) OR significant overpressure", 0.80, False,
         "Pore-filling cements inhibited by early HC or overpressure"),
        ("Model: Diagenesis Modifier — Clastics",
         "Quartz-dominated OR product is oil (biodegradation at shallow depth)", 0.75, False,
         "Either resistant to cementation OR biodegraded but still porous"),
        ("Model: Burial Temp. — Carbonates",
         "35–80°C for oil OR <100°C for gas", 0.80, False,
         "Carbonate porosity in favourable window"),
        ("Model: Burial Temp. — Carbonates",
         "80–130°C for oil OR 100–150°C for gas", 0.55, False,
         "Moderate burial; dolomitisation may enhance or reduce porosity"),
        ("Model: Burial Temp. — Carbonates",
         ">130°C for oil OR >150°C for gas OR oil at <35°C", 0.25, False,
         "Deep burial anneals porosity; carbonate typically tight"),
        ("Model: Reservoir Facies Quality — Carbonates",
         "Carbonate mud / Chalk / Core-reef facies", 0.50, False,
         "Tight matrix; relies on secondary porosity and fractures"),
        ("Model: Reservoir Facies Quality — Carbonates",
         "Grainstone (packstone, oolite, skeletal) or fore-reef facies", 0.75, False,
         "Good primary porosity; grain-supported fabric"),
        ("Model: Diagenesis Modifier — Carbonates",
         "Early petroleum migration (before burial to >80–130°C)", 0.80, False,
         "Early HC charge inhibits cementation"),
        ("Model: Diagenesis Modifier — Carbonates",
         "Grainstone / fore-reef AND product is oil (biodegradation)", 0.70, False,
         "Best facies, some porosity loss from biodegradation"),
        ("Data: Well Deliverability Evidence",
         "All wells within 50 km have GOOD reservoir deliverability", 0.90, False,
         "Proximal well-control proves deliverability in trend"),
        ("Data: Well Deliverability Evidence",
         "All wells 50–100 km away have GOOD reservoir deliverability", 0.75, False,
         "Distal positive analogue"),
        ("Data: Well Deliverability Evidence",
         "Not all wells within 100 km have good deliverability", 0.45, False,
         "Mixed results; uncertainty on deliverability"),
        ("Data: Well Deliverability Evidence",
         "All wells within 100 km have POOR deliverability", 0.10, False,
         "Strong negative evidence; poor deliverability expected"),
        ("Data: Well Deliverability Evidence",
         "No wells in play — seismic data only", 0.40, False,
         "No calibration; deliverability inferred from model only"),
    ],
    "4. Seal": [
        ("Model: Seal Type",
         "One seal traps (simple)", 0.75, False,
         "Simpler geometry; single failure mode"),
        ("Model: Seal Type",
         "Poly-seal traps (multiple independent seals)", 0.85, False,
         "Redundancy improves overall seal probability"),
        ("Model: Top Seal Geometry",
         "Conformable or unconformable (non-erosional)", 0.80, False,
         "Continuous seal; low risk of breach by erosion"),
        ("Model: Top Seal Geometry",
         "Unconformable with fault plane as part of top seal", 0.55, False,
         "Fault seal adds a failure mode; dependent on fault transmissibility"),
        ("Model: Top Seal Geometry (2nd criterion)",
         "Conformable contact", 0.85, False,
         "Best case; seal undisturbed by structural events"),
        ("Model: Top Seal Geometry (2nd criterion)",
         "Unconformable — erosional contact", 0.50, False,
         "Possible seal truncation; integrity depends on post-unconformity cover"),
        ("Model: Lateral / Bottom Seal",
         "Salt or shale diapirism provides lateral seal", 0.90, False,
         "Excellent ductile seal; very low permeability"),
        ("Model: Lateral / Bottom Seal",
         "Facies change / Cataclasis / Pore-fluid change (tar, hydrate)", 0.65, False,
         "Good but depends on lateral continuity of facies"),
        ("Model: Lateral / Bottom Seal",
         "Onlap / Lowstand wedge", 0.55, False,
         "Stratigraphic seal; effectiveness tied to shale content"),
        ("Model: Fault Seal Style",
         "Juxtaposition seal (reservoir against seal lithology)", 0.70, False,
         "Common; requires accurate fault displacement mapping"),
        ("Model: Fault Seal Style",
         "Clay-shale smear", 0.65, False,
         "Good but discontinuous if clay fraction low"),
        ("Model: Fault Seal Style",
         "No juxtaposition issue / Smear analysis confirms seal", 0.80, False,
         "Quantitative analysis supports seal integrity"),
        ("Model: Fault Seal Style",
         "More than 1 fault plane OR leak windows due to sand-sand juxtaposition", 0.30, False,
         "Multiple failure modes; high leakage risk"),
        ("Model: Fault Seal Style",
         "Self-juxtaposed reservoir at depth <2.5 km (mechanical failure risk)", 0.40, False,
         "Shallow reservoir may not sustain pressure; brittle failure possible"),
        ("Data: Sealing Quality",
         "Very good — Salt / Anhydrite", 0.95, False,
         "Evaporite seals: near-perfect capillary entry pressure"),
        ("Data: Sealing Quality",
         "Good — Thick shale >10 m / Basalt / Carbonates", 0.80, False,
         "Thick, low-permeability seal; reliable"),
        ("Data: Sealing Quality",
         "Acceptable — Average shale 5–10 m OR faults cut top surface", 0.60, False,
         "Moderate confidence; some risk of localised breach"),
        ("Data: Sealing Quality",
         "Poor — Seal thinner than 5 m OR sand-rich OR brittle shale", 0.30, False,
         "High risk of leakage or capillary failure"),
        ("Data: Sealing Quality",
         "Top seal inferred from seismic data only — no well calibration", 0.45, False,
         "Seismic inference; lithology and thickness uncertain"),
    ],
    "5. Source Rock (Presence & Maturity)": [
        ("Model: Basin Model Availability",
         "1D–3D numerical basin model available (e.g. PetroMod, Trinity)", 0.90, False,
         "Quantitative maturity, expulsion, and timing confirmed by modelling"),
        ("Model: Basin Model Availability",
         "No numerical basin model available", 0.50, False,
         "Relies on regional understanding and analogues only"),
        ("Model: Maturity Level",
         "Drainage area in late maturity window (peak oil/gas generation)", 0.90, False,
         "Maximum HC generation; significant expulsion volumes expected"),
        ("Model: Maturity Level",
         "Drainage area in early maturity window (oil onset)", 0.70, False,
         "Generation underway but not at peak; some charge expected"),
        ("Model: Maturity Level",
         "Drainage area immature", 0.15, False,
         "Little or no HC generation; charge very unlikely"),
        ("Model: Kerogen Type",
         "Type I–II / Max. burial T >140°C", 0.90, False,
         "Oil-prone kerogen at sufficient maturity; good generation expected"),
        ("Model: Kerogen Type",
         "Type III–IV / Max. burial T >200°C", 0.75, False,
         "Gas-prone kerogen at high maturity; wet gas / condensate"),
        ("Model: Kerogen Type",
         "Type I–II / 140°C > Max. T > 115°C", 0.70, False,
         "Oil-prone in early-to-peak oil window"),
        ("Model: Kerogen Type",
         "Type III–IV / 200°C > Max. T > 160°C", 0.60, False,
         "Gas-prone at moderate-high maturity"),
        ("Model: Kerogen Type",
         "Type I–II / Max. T <115°C (immature to early oil)", 0.35, False,
         "Below peak generation; charge limited"),
        ("Model: Kerogen Type",
         "Type III–IV / Max. T <160°C (immature gas-prone)", 0.25, False,
         "Insufficient maturity for significant gas generation"),
        ("Data: Direct Evidence",
         "Oil pools, seeps, OR penetrated source rock proven in basin", 0.90, False,
         "Direct evidence of active petroleum system"),
        ("Data: Direct Evidence",
         "HC shows in drilled basin + valid DHI on seismic", 0.80, True,
         "Combination of direct and geophysical (DHI) evidence — see DHI caveat"),
        ("Data: Direct Evidence",
         "Lack of pools, seeps and shows in drilled basin", 0.20, False,
         "No direct evidence despite drilling; system may be inactive"),
        ("Data: Direct Evidence",
         "Source rock intervals outcrop on basin margins", 0.65, False,
         "Source proven by outcrop; subsurface presence inferred"),
        ("Data: Direct Evidence",
         "Inferred source rock — GDE maps based on seismic data only", 0.35, False,
         "Speculative; no direct geochemical confirmation"),
    ],
    "6. Migration (Charge & Timing)": [
        ("Model: Basin Model",
         "3D numerical model (PetroMod/Temis/Trinity) CONFIRMS migration to prospect", 0.90, False,
         "Quantitative migration pathways and timing confirmed"),
        ("Model: Basin Model",
         "3D numerical model SUGGESTS LACK of migration to prospect", 0.10, False,
         "Model indicates prospect is in migration shadow or unfavourable position"),
        ("Model: Basin Model",
         "No numerical migration model available", 0.45, False,
         "Migration inferred qualitatively from structural position only"),
        ("Model: Migration Distance",
         "Short vertical (<2 km) AND short lateral (<50 km) migration", 0.90, False,
         "Minimal migration losses; efficient charge expected"),
        ("Model: Migration Distance",
         "Short vertical (<2 km) AND long lateral (>50 km) migration", 0.65, False,
         "Lateral losses possible; carrier-bed continuity important"),
        ("Model: Migration Distance",
         "Long vertical (>2 km) AND short lateral (<50 km) migration", 0.60, False,
         "Vertical migration through faults or fractures; some losses"),
        ("Model: Migration Distance",
         "Long vertical (>2 km) AND long lateral (>50 km) migration", 0.35, False,
         "Highest migration losses; complex pathway; charge uncertain"),
        ("Data: Direct Evidence in Migration Pathway",
         "Oil/gas pools, shows, or thermogenic front within migration pathway", 0.90, False,
         "HC confirmed en-route; migration pathway proven active"),
        ("Data: Direct Evidence in Migration Pathway",
         "Lack of pools, shows, or thermogenic front in migration pathway", 0.25, False,
         "No HC detected along expected pathway; possible migration barrier"),
        ("Data: DHI on Seismic",
         "DHI present on seismic within prospect area", 0.80, True,
         "Seismic amplitude anomaly consistent with HC charge — DHI embedded directly "
         "in Migration factor (NOT a separate Bayesian likelihood update)"),
        ("Data: DHI on Seismic",
         "DHI absent — no anomaly detected", 0.40, True,
         "Absence of DHI; does not preclude HC but reduces confidence"),
        ("Data: DHI on Seismic",
         "'Should not see' DHI environment (wrong rock-physics setting for DHI)", 0.50, True,
         "DHI cannot be expected regardless of HC presence; factor is neutral"),
    ],
}

MALVIC_2009: dict[str, list[tuple]] = {
    "1. Source Rock": [
        ("Source Rock Facies",
         "Kerogen Type I and/or II (oil-prone)", 0.90, False,
         "Best kerogen for oil generation; marine or lacustrine origin"),
        ("Source Rock Facies",
         "Kerogen Type III (gas-prone; terrestrial/humic)", 0.70, False,
         "Good for gas; less oil potential"),
        ("Source Rock Facies",
         "Favourable palaeo-facies organic matter sedimentation (inferred)", 0.55, False,
         "Geological setting supports source rock deposition; not proven"),
        ("Source Rock Facies",
         "Regionally known source rock — not proven at observed locality", 0.40, False,
         "Regional play concept only; local confirmation absent"),
        ("Source Rock Facies",
         "Undefined source rock type", 0.20, False,
         "No data to characterise source; speculative"),
        ("Source Rock Maturity",
         "Sediments in catagenesis phase (oil or wet gas generation)", 0.90, False,
         "Main generation window; high HC expulsion expected"),
        ("Source Rock Maturity",
         "Sediments in metagenesis phase (dry gas / overmature)", 0.70, False,
         "Dry gas only; oil cracked"),
        ("Source Rock Maturity",
         "Sediments in early catagenesis phase (onset of oil)", 0.60, False,
         "Generation beginning; moderate charge"),
        ("Source Rock Maturity",
         "Sediments in late diagenesis phase (sub-mature)", 0.30, False,
         "Insufficient maturity; little charge expected"),
        ("Source Rock Maturity",
         "Undefined maturity level", 0.20, False,
         "No maturity data available"),
        ("Data Source Quality",
         "Geochemical analysis on core and/or formation fluids", 0.95, False,
         "Best direct data: TOC, Tmax, Rock-Eval directly measured"),
        ("Data Source Quality",
         "Analogy with nearby geochemical analyses (<50 km)", 0.75, False,
         "Good proxy if basin is geologically uniform"),
        ("Data Source Quality",
         "Thermal modelling and calculation (1D/2D)", 0.65, False,
         "Modelled maturity; quality depends on calibration data"),
        ("Data Source Quality",
         "Thermal modelling at very few locations only", 0.45, False,
         "Limited calibration; model uncertainty high"),
        ("Data Source Quality",
         "Undefined data sources", 0.20, False,
         "No supporting data"),
    ],
    "2. Migration": [
        ("Hydrocarbon Shows",
         "Production of hydrocarbons from wells in basin / area", 0.95, False,
         "Proven active petroleum system; migration confirmed"),
        ("Hydrocarbon Shows",
         "HC in traces; new gas detected >10% in mud log", 0.75, False,
         "Weak shows suggest migration active but limited charge"),
        ("Hydrocarbon Shows",
         "Oil determined in cores (luminescent analysis / core test)", 0.85, False,
         "Direct oil residue; migration pathway confirmed"),
        ("Hydrocarbon Shows",
         "Oil determined in traces (luminescent / core test)", 0.60, False,
         "Residual oil suggests past migration; possibly flushed"),
        ("Hydrocarbon Shows",
         "Hydrocarbons not observed in any wells or cores", 0.20, False,
         "No evidence of migration; system possibly dead"),
        ("Position of Trap",
         "Trap located in proven migration distance from kitchen", 0.90, False,
         "Structural position confirmed within active migration fairway"),
        ("Position of Trap",
         "Trap located between two source-rock depocentres", 0.80, False,
         "Flanked by kitchens; good charge probability"),
        ("Position of Trap",
         "Short migration pathway (≤10 km from kitchen)", 0.85, False,
         "Minimal migration losses"),
        ("Position of Trap",
         "Long migration pathway (>10 km from kitchen)", 0.50, False,
         "Greater losses; carrier bed continuity critical"),
        ("Position of Trap",
         "Undefined source rocks / migration pathway unknown", 0.15, False,
         "No basis for migration assessment"),
        ("Timing of Trap Formation",
         "Trap is OLDER than matured source rocks (ideal timing)", 0.90, False,
         "Trap ready to receive HC at time of migration"),
        ("Timing of Trap Formation",
         "Trap is YOUNGER than matured source rocks", 0.40, False,
         "Trap formed after main migration; charge likely bypassed"),
        ("Timing of Trap Formation",
         "Relationship between trap and source rock timing UNKNOWN", 0.45, False,
         "Cannot assess timing; uncertainty high"),
    ],
    "3. Reservoir": [
        ("Reservoir Type",
         "Clean sandstone (laterally extended) / Granite basement / Dolomite with secondary porosity / Algae reef with significant secondary porosity", 0.90, False,
         "Excellent reservoir types; proven globally for high deliverability"),
        ("Reservoir Type",
         "Silt/clay-rich sandstone / Basement with limited secondary porosity / Algae reef with skeletal debris and marine cement infill", 0.60, False,
         "Moderate quality; heterogeneity limits deliverability"),
        ("Reservoir Type",
         "Sandstone with significant silt/clay fraction, limited lateral extent", 0.35, False,
         "Poor quality; tight or highly compartmentalised"),
        ("Reservoir Type",
         "Basement rocks with low secondary porosity, limited extent", 0.20, False,
         "Very poor; fracture-dependent only"),
        ("Reservoir Type",
         "Undefined reservoir type", 0.15, False,
         "No data; speculative"),
        ("Porosity Features",
         "Primary porosity >15% AND Secondary porosity >5%", 0.95, False,
         "Excellent pore system; very high deliverability expected"),
        ("Porosity Features",
         "Primary porosity 5–15% AND Secondary porosity 1–5%", 0.65, False,
         "Moderate pore system; commercial if sufficient thickness"),
        ("Porosity Features",
         "Primary porosity <10% AND Permeability <0.01 mD (tight)", 0.20, False,
         "Tight reservoir; unconventional completion may be needed"),
        ("Porosity Features",
         "Secondary porosity <1% (near-zero effective porosity)", 0.10, False,
         "Non-commercial; reservoir likely absent or cemented"),
        ("Porosity Features",
         "Undefined porosity values", 0.20, False,
         "No porosity data available"),
    ],
    "4. Trap": [
        ("Structural Trap Style",
         "Anticline / Buried hill linked to basement high", 0.90, False,
         "Classic, well-understood trapping geometry; low complexity"),
        ("Structural Trap Style",
         "Faulted anticline", 0.70, False,
         "Good but fault seal adds risk"),
        ("Structural Trap Style",
         "Structural nose closed by faults", 0.55, False,
         "Partial closure; dependent on fault transmissibility"),
        ("Structural Trap Style",
         "Any positive faulted structure with poorly defined margins", 0.35, False,
         "Marginal; closure uncertain"),
        ("Structural Trap Style",
         "Undefined structural framework", 0.15, False,
         "No trap defined"),
        ("Stratigraphic / Combined Trap Style",
         "Algae reef form (bioherm)", 0.80, False,
         "Known trapping geometry; good lateral sealing"),
        ("Stratigraphic / Combined Trap Style",
         "Sandstone pinchout", 0.70, False,
         "Stratigraphic trap; effective if shale seals are continuous"),
        ("Stratigraphic / Combined Trap Style",
         "Sediments changed by diagenesis (diagenetic trap)", 0.55, False,
         "Requires diagenetic model; less predictable"),
        ("Stratigraphic / Combined Trap Style",
         "Abrupt changes in petrophysical properties (clay / facies change)", 0.45, False,
         "Lateral heterogeneity creates trap; difficult to map"),
        ("Stratigraphic / Combined Trap Style",
         "Undefined stratigraphic framework", 0.15, False,
         "No trap basis"),
        ("Quality of Cap Rock",
         "Regional proven cap rock (evaporite seals / regionally extensive shale)", 0.95, False,
         "Best seal; thick, continuous, proven by drilling"),
        ("Quality of Cap Rock",
         "Rocks without reservoir properties (non-porous shale / dense carbonate)", 0.75, False,
         "Good seal but not independently proven across area"),
        ("Quality of Cap Rock",
         "Rocks permeable to gas (thin / heterolithic shale — possible gas leakage)", 0.35, False,
         "Risk of gas leakage; may not retain gas column"),
        ("Quality of Cap Rock",
         "Permeable rocks with locally higher silt/clay content (variable seal)", 0.25, False,
         "Poor, discontinuous seal"),
        ("Quality of Cap Rock",
         "Undefined cap rock", 0.10, False,
         "No seal data; assumed absent"),
    ],
    "5. Preservation": [
        ("Formation Pressure",
         "Higher than hydrostatic (overpressured reservoir)", 0.85, False,
         "Overpressure indicates active system and good sealing"),
        ("Formation Pressure",
         "Approximately hydrostatic", 0.65, False,
         "Normal pressure; no pressure support or leak indicator"),
        ("Formation Pressure",
         "Lower than hydrostatic (underpressured / depleted)", 0.30, False,
         "Possible leakage or depletion; poor preservation"),
        ("Formation Water",
         "Stagnant / connate formation water (still aquifer)", 0.90, False,
         "No active water flushing; HC preserved"),
        ("Formation Water",
         "Active aquifer of formation waters (artesian-type)", 0.60, False,
         "Water movement may flush HC; preservation uncertain"),
        ("Formation Water",
         "Infiltrated aquifer from adjacent formations", 0.40, False,
         "Lateral water influx risk; degradation possible"),
        ("Formation Water",
         "Infiltrated aquifer from surface (meteoric water)", 0.15, False,
         "Biodegradation and water-washing likely; severe degradation"),
    ],
}

# CCOP rows: (sub_category, condition, cos_lo, cos_hi, is_dhi, notes)
CCOP_2000: dict[str, list[tuple]] = {
    "1. Source Rock": [
        ("Source Rock Presence",
         "Proven source rock (wells, geochemistry)", 0.90, 1.00, False,
         "Direct evidence of source; highly certain"),
        ("Source Rock Presence",
         "Quality-reduced source rock (partial evidence)", 0.60, 0.80, False,
         "Source present but below optimal; charge limited"),
        ("Source Rock Presence",
         "Hypothetical source rock (basin modelling only)", 0.30, 0.60, False,
         "Modelled; no direct well confirmation"),
        ("Source Rock Presence",
         "Speculative source rock (no data)", 0.05, 0.30, False,
         "No supporting data; highly uncertain"),
        ("Maturity / Volume",
         "Sufficient volume AND adequate maturity", 0.80, 1.00, False,
         "Kitchen large and mature enough for commercial charge"),
        ("Maturity / Volume",
         "Marginal volume (kitchen small)", 0.40, 0.70, False,
         "Small kitchen; charge may be limited"),
        ("Maturity / Volume",
         "Marginally mature (at onset of generation)", 0.30, 0.60, False,
         "Early stage; generation incomplete"),
        ("Depositional Environment",
         "Restricted marine or lacustrine — sapropelic organic matter (Type I/II)", 0.80, 1.00, False,
         "Best source facies; high HI; oil-prone"),
        ("Depositional Environment",
         "Mixed marine/lacustrine — dispersed sapropelic organic matter", 0.50, 0.80, False,
         "Moderate source quality; mixed kerogen"),
        ("Depositional Environment",
         "Deltaic — predominantly humic organic matter (Type III; gas-prone)", 0.30, 0.60, False,
         "Gas-prone; limited oil potential"),
    ],
    "2. Migration": [
        ("Migration Type",
         "Local migration (short distance; <5 km from kitchen)", 0.80, 1.00, False,
         "Minimal losses; efficient charge"),
        ("Migration Type",
         "Lateral migration WITHOUT barriers (open carrier bed)", 0.60, 0.85, False,
         "Good efficiency if carrier bed continuous"),
        ("Migration Type",
         "Lateral migration WITH barriers (faults / permeability baffles)", 0.30, 0.65, False,
         "Barriers may deflect or stop migration"),
        ("Migration Type",
         "Vertical migration WITHOUT barriers (fracture / fault conduit)", 0.50, 0.80, False,
         "Efficient if fault zone is connected"),
        ("Migration Type",
         "Vertical migration WITH barriers (tight intervals)", 0.20, 0.55, False,
         "Potential for migration arrest at tight horizons"),
        ("Migration Type",
         "Long-distance 'fill-and-spill' migration (>50 km)", 0.20, 0.50, False,
         "High losses; dependent on multiple relay traps"),
        ("Migration Type",
         "Trap in SHADOW of migration (behind kitchen relative to prospect)", 0.05, 0.20, False,
         "Unfavourable position; migration likely to bypass"),
        ("Timing",
         "Trap formed BEFORE onset of HC migration", 0.75, 1.00, False,
         "Ideal; trap ready when hydrocarbons arrive"),
        ("Timing",
         "Trap formation and migration OVERLAPPING in time", 0.40, 0.75, False,
         "Partial charge; timing partially favourable"),
        ("Timing",
         "Trap formed when source rock is 'overcooked' (post-generation)", 0.05, 0.25, False,
         "Trap formed too late; missed main migration pulse"),
    ],
    "3a. Reservoir Facies": [
        ("Marine Facies",
         "Shallow marine blanket deposit", 0.80, 1.00, False,
         "Laterally continuous; high presence probability"),
        ("Marine Facies",
         "Coastal / Deltaic / Tidal", 0.60, 0.90, False,
         "Good but heterogeneous"),
        ("Marine Facies",
         "Submarine fan (turbidite)", 0.40, 0.80, False,
         "Variable; channel vs lobe geometry critical"),
        ("Marine Facies",
         "Carbonates (marine)", 0.50, 0.85, False,
         "Depends heavily on diagenesis and secondary porosity"),
        ("Continental Facies",
         "Lacustrine / Deltaic (continental)", 0.50, 0.80, False,
         "Good lacustrine systems exist; lateral extent limited"),
        ("Continental Facies",
         "Alluvial fan / Braided stream / Meandering channel", 0.30, 0.65, False,
         "Highly heterogeneous; compartmentalisation common"),
        ("Continental Facies",
         "Eolian", 0.60, 0.90, False,
         "Excellent quality but geographically restricted"),
        ("Special / Other",
         "Fractured basement", 0.20, 0.60, False,
         "Highly localised; fracture prediction difficult"),
        ("Special / Other",
         "Fractured / Porous lava", 0.15, 0.50, False,
         "Very localised; difficult to predict"),
        ("Data Reliability — Facies",
         "Direct data: proximal deposits (<20 km)", 0.80, 1.00, False,
         "Well-calibrated; high confidence"),
        ("Data Reliability — Facies",
         "Direct data: more distal deposits (20–50 km)", 0.60, 0.85, False,
         "Good analogue; some uncertainty on local variations"),
        ("Data Reliability — Facies",
         "Limited data: discontinuous deposits (50–100 km)", 0.35, 0.65, False,
         "Analogue only; significant extrapolation required"),
        ("Data Reliability — Facies",
         "Indirect data: seismic sequence analysis only", 0.15, 0.45, False,
         "No direct facies control; inferred from seismic only"),
    ],
    "3b. Reservoir Quality": [
        ("Reservoir Depth",
         "1–3 km depth (optimal window for clastics)", 0.75, 1.00, False,
         "Best porosity/permeability preservation window"),
        ("Reservoir Depth",
         "3–4 km depth (moderate compaction)", 0.45, 0.75, False,
         "Moderate compaction; porosity reduced but often commercial"),
        ("Reservoir Depth",
         "Deeper than 4 km (high compaction risk)", 0.15, 0.50, False,
         "High overburden; tight reservoir likely"),
        ("Reservoir Quality",
         "Homogeneous, clean reservoir (>20% porosity)", 0.75, 1.00, False,
         "Excellent deliverability expected"),
        ("Reservoir Quality",
         "Mixed / unclean reservoir (10–20% porosity; clay content)", 0.35, 0.70, False,
         "Moderate; clay content reduces flow capacity"),
        ("Data Reliability — Quality",
         "Direct data: proximal deposits", 0.75, 1.00, False,
         "Well-tested analogues"),
        ("Data Reliability — Quality",
         "Direct data: more distal deposits", 0.55, 0.80, False,
         "Good proxy"),
        ("Data Reliability — Quality",
         "Limited data: discontinuous deposits", 0.30, 0.60, False,
         "Extrapolation required"),
        ("Data Reliability — Quality",
         "Indirect data: seismic sequence analysis only", 0.10, 0.40, False,
         "No well calibration"),
    ],
    "4a. Seismic Interpretation": [
        ("Correlation & Mapping",
         "Good correlation — nearby wells (<30 km)", 0.80, 1.00, False,
         "Well-calibrated seismic interpretation"),
        ("Correlation & Mapping",
         "Uncertain correlation — distant wells (30–80 km)", 0.45, 0.75, False,
         "Extrapolation risk; structural validity uncertain"),
        ("Correlation & Mapping",
         "Unreliable correlation — analogue model only (no wells)", 0.15, 0.45, False,
         "Pure model; no well calibration"),
        ("Seismic Mapping",
         "Low structural complexity (simple 4-way dip closure)", 0.75, 1.00, False,
         "Well-defined; low risk of structural busts"),
        ("Seismic Mapping",
         "High structural complexity (faulted / inverted)", 0.40, 0.75, False,
         "Complex; structural integrity uncertain"),
        ("Seismic Mapping",
         "Low relief with uncertain depth conversion", 0.15, 0.45, False,
         "Closure may not exist after depth conversion"),
        ("Data Type",
         "3D Seismic (full 3D coverage)", 0.80, 1.00, False,
         "Best imaging; reliable structural definition"),
        ("Data Type",
         "2D Seismic (line coverage)", 0.40, 0.75, False,
         "Adequate but lateral interpolation required"),
        ("2D Line Density",
         "Dense grid (spacing > 5× fault wavelength)", 0.70, 0.95, False,
         "Dense enough for reliable structural maps"),
        ("2D Line Density",
         "Open grid (spacing 2–5× fault wavelength)", 0.40, 0.70, False,
         "Moderate confidence; significant aliasing possible"),
        ("2D Line Density",
         "Very open grid (<2× fault wavelength)", 0.10, 0.35, False,
         "Insufficient to define structure reliably"),
    ],
    "4b. Seal Mechanism": [
        ("Seal Type",
         "Simple seal (single top seal)", 0.65, 0.90, False,
         "Straightforward; one failure mode"),
        ("Seal Type",
         "Combined / Multiple seal (top + lateral + fault)", 0.75, 1.00, False,
         "Redundancy improves reliability"),
        ("Top Surface",
         "Conformable seal (undisturbed stratigraphy)", 0.75, 1.00, False,
         "Continuous; low breach risk"),
        ("Top Surface",
         "Unconformable seal (erosional surface)", 0.40, 0.75, False,
         "Possible truncation; integrity uncertain"),
        ("Structural Style",
         "Onlap / Low-stand wedge (stratigraphic seal)", 0.50, 0.80, False,
         "Effectiveness tied to shale content and continuity"),
        ("Structural Style",
         "Down-faulted structures (fault seal)", 0.40, 0.75, False,
         "Depends on juxtaposition and clay smear"),
        ("Structural Style",
         "'Shale-out' (lateral facies seal)", 0.55, 0.85, False,
         "Good if shale is laterally continuous"),
        ("Structural Style",
         "Subcrop structures (stratigraphic truncation)", 0.35, 0.65, False,
         "Complex; requires unconformity mapping"),
        ("Seal Quality",
         "Very good (evaporite / thick clean shale >20 m)", 0.85, 1.00, False,
         "Near-perfect seal"),
        ("Seal Quality",
         "Good (shale 10–20 m)", 0.65, 0.85, False,
         "Reliable; low breach probability"),
        ("Seal Quality",
         "Acceptable (shale 5–10 m OR faults cut top)", 0.40, 0.65, False,
         "Moderate confidence"),
        ("Seal Quality",
         "Poor (shale <5 m OR sandy / brittle)", 0.10, 0.35, False,
         "High risk of leakage"),
    ],
    "5. Preservation": [
        ("Post-accumulation Processes",
         "No late tectonic / erosional activity after accumulation", 0.80, 1.00, False,
         "Stable tectonic setting; preservation excellent"),
        ("Post-accumulation Processes",
         "Erosion affecting trap geometry", 0.40, 0.70, False,
         "Column may have been reduced by erosion"),
        ("Post-accumulation Processes",
         "Uplift and tilting (spill-point lowered)", 0.35, 0.65, False,
         "Reservoir may have spilled on tilting"),
        ("Post-accumulation Processes",
         "Reactivated faults (post-accumulation leakage risk)", 0.20, 0.55, False,
         "Fault reactivation creates migration pathway"),
        ("Process Type 1 — Biodegradation",
         "No late tectonic activity AND depth precludes biodegradation", 0.80, 1.00, False,
         "Ideal preservation"),
        ("Process Type 1 — Biodegradation",
         "Shallow trap — possible biodegradation (<600 m)", 0.35, 0.65, False,
         "Biodegradation risk reduces oil quality"),
        ("Process Type 2 — Connectivity",
         "Trap in connection to ACTIVE generating source", 0.75, 0.95, False,
         "Ongoing charge compensates for any leakage"),
        ("Process Type 2 — Connectivity",
         "Trap NOT connected to generating source (isolated)", 0.45, 0.75, False,
         "Static reservoir; no top-up if leakage occurs"),
        ("Process Type 3 — Trap Integrity",
         "Form, volume, and top point NOT changed since accumulation", 0.80, 1.00, False,
         "Structural integrity maintained"),
        ("Process Type 3 — Trap Integrity",
         "Form, volume, or top point CHANGED (inversion / erosion)", 0.25, 0.60, False,
         "Trap modified; possible spill or partial preservation"),
        ("Process Type 4 — Tectonic Regime",
         "Compression and/or transpression (tight faults; good seal)", 0.65, 0.90, False,
         "Compressional regime usually maintains seal integrity"),
        ("Process Type 4 — Tectonic Regime",
         "Tension / Extension (normal faults; seal breach risk)", 0.30, 0.65, False,
         "Extensional faults may reactivate and leak"),
        ("Data Control",
         "Positive, unambiguous data (seismic + wells confirm preservation)", 0.80, 1.00, False,
         "High confidence in preservation"),
        ("Data Control",
         "Data control and interpretation are poor to fair", 0.35, 0.65, False,
         "Uncertain; significant range"),
        ("Data Control",
         "Negative, unambiguous data (seismic + wells indicate breach)", 0.05, 0.20, False,
         "Evidence of leakage or trap failure"),
    ],
}


# ────────────────────────────────────────────────────────────────────────────
# RENDERING
# ────────────────────────────────────────────────────────────────────────────

def _bar_html(value: float, width_px: int = 120) -> str:
    """Horizontal bar coloured by CoS band."""
    col = _cos_color(value)
    bar_w = int(value * width_px)
    return (
        f"<div style='display:flex;align-items:center;gap:6px;'>"
        f"<div style='width:{width_px}px;background:#e5e7eb;border-radius:4px;height:14px;'>"
        f"<div style='width:{bar_w}px;background:{col};border-radius:4px;height:14px;'></div>"
        f"</div>"
        f"<span style='font-size:0.85rem;font-weight:600;color:{col};'>{_pct(value)}</span>"
        f"</div>"
    )


def _range_bar_html(lo: float, hi: float, width_px: int = 120) -> str:
    """Range bar (CCOP) with midpoint marker."""
    mid = (lo + hi) / 2
    col = _cos_color(mid)
    left = int(lo * width_px)
    w = max(int((hi - lo) * width_px), 2)
    mid_px = int(mid * width_px)
    return (
        f"<div style='display:flex;align-items:center;gap:6px;'>"
        f"<div style='width:{width_px}px;background:#e5e7eb;border-radius:4px;height:14px;position:relative;'>"
        f"<div style='position:absolute;left:{left}px;width:{w}px;background:{col};opacity:0.55;"
        f"border-radius:4px;height:14px;'></div>"
        f"<div style='position:absolute;left:{mid_px-2}px;width:4px;background:{col};"
        f"border-radius:2px;height:14px;'></div>"
        f"</div>"
        f"<span style='font-size:0.82rem;font-weight:600;color:{col};'>"
        f"{_pct(lo)}–{_pct(hi)}"
        f"<span style='font-weight:400;color:#6b7280;'> (mid {_pct(mid)})</span>"
        f"</span>"
        f"</div>"
    )


def _dhi_badge() -> str:
    return (
        "<span style='background:#FEF3C7;color:#92400E;border:1px solid #F59E0B;"
        "border-radius:4px;padding:1px 6px;font-size:0.72rem;font-weight:600;"
        "margin-left:4px;'>⚠️ DHI / Geophysical</span>"
    )


def _render_milkov_factor(factor_name: str, rows: list[tuple]) -> None:
    """Render one Milkov factor as a styled HTML table inside an expander."""
    dhi_rows = [r for r in rows if r[3]]
    has_dhi = bool(dhi_rows)

    with st.expander(f"{'⚠️ ' if has_dhi else ''}{factor_name}", expanded=False):
        if has_dhi:
            st.warning(
                "⚠️ **DHI / geophysical evidence rows detected** — "
                "One or more rows in this factor embed DHI (seismic amplitude) evidence "
                "directly into the probability value. This conflates geological and "
                "geophysical evidence. For rigorous assessment, DHI should be handled "
                "via a formal Bayesian likelihood update (e.g. ExxonMobil iCOS / "
                "Rose DHI Consortium SAAM approach), not absorbed into a single CoS "
                "factor. These rows are marked ⚠️ DHI / Geophysical below.",
                icon=None,
            )

        # Build HTML table
        rows_html = ""
        prev_sub = None
        for sub, cond, cos, is_dhi, note in rows:
            sub_cell = (
                f"<td style='font-size:0.78rem;color:#6B7280;vertical-align:top;"
                f"white-space:nowrap;padding:4px 8px;border-bottom:1px solid #F3F4F6;'>"
                f"{sub if sub != prev_sub else ''}</td>"
            )
            prev_sub = sub
            cond_text = (
                f"<span>{cond}</span>"
                + (_dhi_badge() if is_dhi else "")
            )
            rows_html += (
                f"<tr>"
                f"{sub_cell}"
                f"<td style='font-size:0.82rem;padding:4px 8px;"
                f"border-bottom:1px solid #F3F4F6;'>{cond_text}</td>"
                f"<td style='padding:4px 8px;border-bottom:1px solid #F3F4F6;'>"
                f"{_bar_html(cos)}</td>"
                f"<td style='font-size:0.75rem;color:#6B7280;padding:4px 8px;"
                f"border-bottom:1px solid #F3F4F6;'>{note}</td>"
                f"</tr>"
            )

        st.markdown(
            f"<table style='width:100%;border-collapse:collapse;'>"
            f"<thead><tr>"
            f"<th style='text-align:left;font-size:0.78rem;color:#374151;"
            f"padding:6px 8px;border-bottom:2px solid #D1D5DB;width:18%;'>Sub-category</th>"
            f"<th style='text-align:left;font-size:0.78rem;color:#374151;"
            f"padding:6px 8px;border-bottom:2px solid #D1D5DB;width:42%;'>Condition / Criterion</th>"
            f"<th style='text-align:left;font-size:0.78rem;color:#374151;"
            f"padding:6px 8px;border-bottom:2px solid #D1D5DB;width:20%;'>CoS</th>"
            f"<th style='text-align:left;font-size:0.78rem;color:#374151;"
            f"padding:6px 8px;border-bottom:2px solid #D1D5DB;width:20%;'>Notes</th>"
            f"</tr></thead>"
            f"<tbody>{rows_html}</tbody>"
            f"</table>",
            unsafe_allow_html=True,
        )


def _render_malvic_factor(factor_name: str, rows: list[tuple]) -> None:
    with st.expander(factor_name, expanded=False):
        rows_html = ""
        prev_sub = None
        for sub, cond, cos, is_dhi, note in rows:
            sub_cell = (
                f"<td style='font-size:0.78rem;color:#6B7280;vertical-align:top;"
                f"white-space:nowrap;padding:4px 8px;border-bottom:1px solid #F3F4F6;'>"
                f"{sub if sub != prev_sub else ''}</td>"
            )
            prev_sub = sub
            rows_html += (
                f"<tr>"
                f"{sub_cell}"
                f"<td style='font-size:0.82rem;padding:4px 8px;"
                f"border-bottom:1px solid #F3F4F6;'>{cond}</td>"
                f"<td style='padding:4px 8px;border-bottom:1px solid #F3F4F6;'>"
                f"{_bar_html(cos)}</td>"
                f"<td style='font-size:0.75rem;color:#6B7280;padding:4px 8px;"
                f"border-bottom:1px solid #F3F4F6;'>{note}</td>"
                f"</tr>"
            )

        st.markdown(
            f"<table style='width:100%;border-collapse:collapse;'>"
            f"<thead><tr>"
            f"<th style='text-align:left;font-size:0.78rem;color:#374151;"
            f"padding:6px 8px;border-bottom:2px solid #D1D5DB;width:18%;'>Sub-category</th>"
            f"<th style='text-align:left;font-size:0.78rem;color:#374151;"
            f"padding:6px 8px;border-bottom:2px solid #D1D5DB;width:42%;'>Condition / Criterion</th>"
            f"<th style='text-align:left;font-size:0.78rem;color:#374151;"
            f"padding:6px 8px;border-bottom:2px solid #D1D5DB;width:20%;'>CoS</th>"
            f"<th style='text-align:left;font-size:0.78rem;color:#374151;"
            f"padding:6px 8px;border-bottom:2px solid #D1D5DB;width:20%;'>Notes</th>"
            f"</tr></thead>"
            f"<tbody>{rows_html}</tbody>"
            f"</table>",
            unsafe_allow_html=True,
        )


def _render_ccop_factor(factor_name: str, rows: list[tuple]) -> None:
    with st.expander(factor_name, expanded=False):
        rows_html = ""
        prev_sub = None
        for sub, cond, lo, hi, is_dhi, note in rows:
            sub_cell = (
                f"<td style='font-size:0.78rem;color:#6B7280;vertical-align:top;"
                f"white-space:nowrap;padding:4px 8px;border-bottom:1px solid #F3F4F6;'>"
                f"{sub if sub != prev_sub else ''}</td>"
            )
            prev_sub = sub
            rows_html += (
                f"<tr>"
                f"{sub_cell}"
                f"<td style='font-size:0.82rem;padding:4px 8px;"
                f"border-bottom:1px solid #F3F4F6;'>{cond}</td>"
                f"<td style='padding:4px 8px;border-bottom:1px solid #F3F4F6;'>"
                f"{_range_bar_html(lo, hi)}</td>"
                f"<td style='font-size:0.75rem;color:#6B7280;padding:4px 8px;"
                f"border-bottom:1px solid #F3F4F6;'>{note}</td>"
                f"</tr>"
            )

        st.markdown(
            f"<table style='width:100%;border-collapse:collapse;'>"
            f"<thead><tr>"
            f"<th style='text-align:left;font-size:0.78rem;color:#374151;"
            f"padding:6px 8px;border-bottom:2px solid #D1D5DB;width:18%;'>Sub-category</th>"
            f"<th style='text-align:left;font-size:0.78rem;color:#374151;"
            f"padding:6px 8px;border-bottom:2px solid #D1D5DB;width:42%;'>Condition / Criterion</th>"
            f"<th style='text-align:left;font-size:0.78rem;color:#374151;"
            f"padding:6px 8px;border-bottom:2px solid #D1D5DB;width:20%;'>CoS Range (midpoint)</th>"
            f"<th style='text-align:left;font-size:0.78rem;color:#374151;"
            f"padding:6px 8px;border-bottom:2px solid #D1D5DB;width:20%;'>Notes</th>"
            f"</tr></thead>"
            f"<tbody>{rows_html}</tbody>"
            f"</table>",
            unsafe_allow_html=True,
        )


def render_reference_tables() -> None:
    """Main entry point — renders the Reference Probability Tables tab."""

    # ── Header ──────────────────────────────────────────────────────────────
    st.markdown(
        "<div style='background:linear-gradient(135deg,#1e3a2f,#2d5a3d);color:#fff;"
        "padding:16px 20px;border-radius:10px;margin-bottom:12px;'>"
        "<b style='font-size:1.2rem;'>📋 Reference Probability Tables</b><br>"
        "<span style='font-size:0.85rem;opacity:0.85;'>"
        "Milkov (2015) · Malvić (2009) · CCOP (2000) — for calibration and inspiration only. "
        "No calculations are performed on this page."
        "</span></div>",
        unsafe_allow_html=True,
    )

    # ── Master disclaimer ────────────────────────────────────────────────────
    st.error(
        "**⚠️ Important Disclaimers — please read before using these tables**\n\n"
        "1. **Not empirically calibrated** — The values in Milkov (2015) and CCOP (2000) are "
        "based on **expert judgment**, not statistical calibration against drilled-well "
        "outcomes. They should be treated as **starting-point guidelines**, not ground truth.\n\n"
        "2. **DHI / Geophysical evidence** — Some rows embed DHI (seismic amplitude, "
        "AVO) evidence directly into a probability value. **This is methodologically "
        "problematic**: geophysical evidence is Auxiliary and should be handled via a "
        "formal Bayesian likelihood update (e.g. ExxonMobil iCOS / Rose DHI Consortium "
        "SAAM/SaRA, calibrated from 400+ drilled wells) — not folded into geological "
        "CoS factors. All DHI-related rows are marked with ⚠️ DHI / Geophysical "
        "and highlighted in yellow.\n\n"
        "3. **Final CoS** — All three methods combine factor CoS values by **multiplication** "
        "(product), which assumes full independence between factors. This is the traditional "
        "Rose-style approach and can be conservative or optimistic depending on geological "
        "context. E-POS uses Evidence Support Logic (ESL) as its primary method, which "
        "explicitly tracks uncertainty and allows non-independent combination.\n\n"
        "4. **Regional calibration** — Malvić (2009) was originally developed for the "
        "Drava Depression, Croatia. Values may differ significantly in other basins.\n\n"
        "5. **For inspiration only** — Use these tables to help formulate and calibrate "
        "your ESL evidence masses, not as direct probability inputs.",
    )

    # ── DHI note ─────────────────────────────────────────────────────────────
    st.info(
        "**ℹ️ How DHI evidence should be treated in E-POS**\n\n"
        "DHI / seismic amplitude data is **Auxiliary evidence** that should be "
        "incorporated via Bayesian conditioning, not embedded in direct probability "
        "estimates. In E-POS, capture DHI by adjusting S_for on the relevant Reservoir "
        "or Charge element — quantify the likelihood ratio P(DHI|HC) / P(DHI|no HC) "
        "calibrated from regional drilled-well statistics and translate it to an evidence weight. "
        "The GeoCos reference (geocos-v2-0.onrender.com) discusses the same concern."
    )

    # ── Colour legend ─────────────────────────────────────────────────────────
    with st.expander("🎨 Probability colour scale (shared across all three methods)", expanded=False):
        cols = st.columns(len(_COS_SCALE))
        for col, (lo, hi, hex_col, label) in zip(cols, _COS_SCALE):
            with col:
                st.markdown(
                    f"<div style='background:{hex_col};border-radius:6px;padding:8px 4px;"
                    f"text-align:center;color:white;font-size:0.72rem;font-weight:600;'>"
                    f"{label}<br>{_pct(lo)}–{_pct(hi)}</div>",
                    unsafe_allow_html=True,
                )
        st.markdown(
            "<p style='font-size:0.75rem;color:#6B7280;margin-top:8px;'>"
            "Colour scale follows Milkov (2015) / GeoCos v2.0 convention. "
            "Bar width is proportional to probability value; for CCOP ranges the "
            "filled band shows the range and the solid marker shows the midpoint.</p>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════════════
    # METHOD TABS
    # ════════════════════════════════════════════════════════════════════════
    m_tab, mal_tab, ccop_tab = st.tabs([
        "Milkov (2015) — 6 factors",
        "Malvić (2009) — 5 factors",
        "CCOP (2000) — 5 factors / 7 sections",
    ])

    # ── MILKOV 2015 ──────────────────────────────────────────────────────────
    with m_tab:
        st.markdown(
            "**Milkov, A.V. (2015).** Risk tables for less biased and more consistent "
            "geologic risk assessment in petroleum exploration. "
            "*Earth-Science Reviews*, 150, 453–476. "
            "[DOI: 10.1016/j.earscirev.2015.08.006](https://doi.org/10.1016/j.earscirev.2015.08.006) · "
            "[Full text (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S0012825215300301)\n\n"
            "Six risk factors: **Structure · Reservoir Facies · Reservoir Deliverability · "
            "Seal · Source Rock · Migration**. Each factor lists Model-based criteria "
            "(geological interpretation) and Data-based criteria (evidence quality). "
            "Values are single-point estimates based on expert judgment.\n\n"
            "Final CoS = Product of one selected value from each factor (Rose-style multiplication)."
        )
        st.caption(
            "⚠️ Milkov (2015) acknowledges that values are expert-judgment based "
            "and NOT empirically calibrated from drilled-well statistics."
        )
        for factor_name, rows in MILKOV_2015.items():
            _render_milkov_factor(factor_name, rows)

    # ── MALVIĆ 2009 ──────────────────────────────────────────────────────────
    with mal_tab:
        st.markdown(
            "**Malvić, T. (2009).** Stochastical approach in deterministic calculation "
            "of geological risk. *Geologia Croatica*, 62(2), 67–78. "
            "[Full text (Hrčak — Croatian Scientific Portal)](https://hrcak.srce.hr/file/71373)\n\n"
            "Five risk factors: **Source Rock · Migration · Reservoir · Trap · Preservation**. "
            "Originally developed for the **Drava Depression, Croatia** — adaptable globally. "
            "Each factor covers rock type/quality (facies) and data quality criteria. "
            "Values are single-point estimates.\n\n"
            "Final CoS = Product of one selected value from each factor."
        )
        st.caption(
            "⚠️ Originally calibrated for a specific Croatian basin (Drava Depression). "
            "Values may require adjustment for significantly different geological settings."
        )
        for factor_name, rows in MALVIC_2009.items():
            _render_malvic_factor(factor_name, rows)

    # ── CCOP 2000 ────────────────────────────────────────────────────────────
    with ccop_tab:
        st.markdown(
            "**CCOP (2000).** CCOP Guideline for Risk Assessment of Petroleum Prospects. "
            "Coordinating Committee for Coastal and Offshore Geoscience Programmes in "
            "East and Southeast Asia. Technical Bulletin 33. "
            "[Full text (Scribd)](https://www.scribd.com/document/327676318/2912004-4-pdf)\n\n"
            "Five composite risk factors, each split into sub-elements: "
            "**Source Rock · Migration · Reservoir Facies (3a) · "
            "Reservoir Quality (3b) · Seismic Interpretation (4a) · Seal (4b) · Preservation**. "
            "Reservoir and Trap/Seal are each presented as two sub-sections (a/b), "
            "giving seven themed sections in total. "
            "CCOP provides **probability ranges** (min–max) rather than single values — "
            "bars show the full range with a marker at the midpoint. "
            "Designed for SE Asian basins but widely used globally.\n\n"
            "Final CoS = Product of midpoint values from each composite factor."
        )
        st.caption(
            "ℹ️ CCOP provides ranges, not point estimates. The midpoint is shown for "
            "reference. Use the range to express your uncertainty when calibrating "
            "ESL evidence masses."
        )
        for factor_name, rows in CCOP_2000.items():
            _render_ccop_factor(factor_name, rows)

    # ── Footer references ─────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        "**Further reading & tools**\n\n"
        "- GeoCos v2.0 web application by Ayberk Uyanik: "
        "[geocos-v2-0.onrender.com](https://geocos-v2-0.onrender.com/) / "
        "[GitHub](https://github.com/Ayberk-Uyanik/GeoCos-v2.0)\n"
        "- Rose, P.R. (2001). *Risk Analysis and Management of Petroleum Exploration Ventures*. "
        "AAPG Methods in Exploration 12.\n"
        "- **DHI empirical calibration — Rose & Associates DHI Consortium / SaRA:** "
        "[roseassoc.com/dhi-consortium](https://www.roseassoc.com/dhi-consortium/) — "
        "over 400 drilled prospects in a shared calibration database; "
        "SaRA (Seismic Amplitude Risk Analysis) software applies a formal Bayesian "
        "likelihood ratio P(DHI|HC) / P(DHI|no HC).\n"
        "- Forrest, M., Roden, R., & Holeywell, R. (2010). Risking seismic amplitude "
        "anomaly prospects based on database trends. "
        "*The Leading Edge*, 29(5), 570–574. "
        "[DOI: 10.1190/1.3422455](https://doi.org/10.1190/1.3422455)\n"
        "- Pettingill, H.S. & Roden, R. (2022). Integrated DHI Prospect Evaluation: "
        "Lessons Learned from Three Generations of Explorers. "
        "*2022 SEG-AAPG IMAGE Conference*, Houston, August 2022. "
        "[Video (AAPG)](https://www.aapg.org/video/articleid/64149)",
        unsafe_allow_html=False,
    )
