import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
from scipy.interpolate import PchipInterpolator
import plotly.graph_objects as go
import requests

# ════════════════════════════════════════════════════════════════════
# 1. PAGE CONFIG & GLOBAL CSS
# ════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="SHAPE — Soil Health Assessment", page_icon="🌱", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Color+Emoji&display=swap');

/* Reset container padding to stable heights and fix top black space */
.block-container {
    padding-top: 2rem !important;
    padding-bottom: 2rem !important;
    margin-top: 0px !important;
}

/* Enhanced title banner: centered, fully visible corners, and flanking soil graphics */
.fl-header {
    background: linear-gradient(135deg, #0a3d1f 0%, #1a6b35 60%, #0f5132 100%);
    border-radius: 12px !important;
    padding: 36px 24px; 
    margin-top: 16px !important; 
    margin-bottom: 12px;
    display: block !important;
    text-align: center !important;
    position: relative !important;
    overflow: hidden !important; 
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

/* Left Side Graphic: Soil & Diagnostics Microscope Symbol */
.fl-header::before {
    content: "🔬" !important;
    position: absolute !important;
    left: 40px !important;
    top: 50% !important;
    transform: translateY(-50%) !important;
    font-size: 54px !important;
    opacity: 0.25 !important;
    pointer-events: none !important;
}

/* Right Side Graphic: Regenerative Sprout Symbol */
.fl-header::after {
    content: "🌱" !important;
    position: absolute !important;
    right: 40px !important;
    top: 50% !important;
    transform: translateY(-50%) !important;
    font-size: 54px !important;
    opacity: 0.25 !important;
    pointer-events: none !important;
}

/* Styled for the prominent main tool acronym */
.fl-header .main-title {
    color: #ffffff;
    font-size: 44px;
    font-weight: 800;
    margin: 0 0 6px 0;
    letter-spacing: 1px;
    line-height: 1.1;
    position: relative !important;
    z-index: 2 !important;
}

/* Styled for the clear descriptive name below the acronym */
.fl-header .sub-title {
    color: #e8f5e9;
    font-size: 19px;
    font-weight: 400;
    margin: 0 0 8px 0;
    opacity: 0.95;
    letter-spacing: 0.5px;
    position: relative !important;
    z-index: 2 !important;
}

/* Styled for the engineering lab tagline to balance empty space */
.fl-header .tagline {
    color: #a5d6a7;
    font-size: 13px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin: 0;
    position: relative !important;
    z-index: 2 !important;
}

/* Make info box text smaller and clean */
.info-box {
    background: var(--color-background-info);
    border-left: 3px solid #1565c0;
    border-radius: 0 8px 8px 0;
    padding: 8px 14px;
    margin: 10px 0 18px 0;
    font-size: 12px;
    color: var(--color-text-info);
    line-height: 1.4;
}
.coming-soon-box {
    border: 1.5px dashed var(--color-border-tertiary);
    border-radius: 12px;
    padding: 40px 30px;
    text-align: center;
    margin: 20px 0;
}
.coming-soon-box h3 { font-size: 18px; margin-bottom: 8px; color: var(--color-text-primary); }
.coming-soon-box p { font-size: 14px; color: var(--color-text-secondary); max-width: 480px; margin: 0 auto; }

.pg-card {
    border: 0.5px solid var(--color-border-tertiary);
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 10px;
}
.pg-card h4 { font-size: 15px; font-weight: 600; margin: 0 0 6px 0; color: var(--color-text-primary); }
.pg-card p  { font-size: 13px; color: var(--color-text-secondary); margin: 0; line-height: 1.5; }

.region-pill {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 14px;
    font-size: 12px;
    font-weight: 600;
    background: rgba(26,150,65,0.15);
    color: #1a9641;
    margin-bottom: 8px;
}

/* Subtle shadows for clean containers */
div[data-testid="stExpander"] {
    background-color: rgba(255,255,255,0.01);
    border-radius: 12px !important;
}

/* ─── ENHANCED REGION SELECTION TABS LAYOUT ─── */
/* Targets the master tab row container */
div[data-testid="stTabs"] [data-baseweb="tab-list"] {
    display: flex !important;
    width: 100% !important;
    justify-content: center !important;
    gap: 0px !important; 
    margin-bottom: 20px;
    border-bottom: 2px solid var(--color-border-tertiary);
}

/* Forces each individual region tab item */
div[data-testid="stTabs"] [data-baseweb="tab"] {
    flex-grow: 1 !important;
    text-align: center !important;
    justify-content: center !important;
    font-size: 32px !important; 
    font-weight: 700 !important;
    padding: 20px 24px !important; 
    transition: all 0.2s ease;
    font-family: inherit, "Noto Color Emoji" !important; 
}

/* Assign a specific green background tint and underline to active region tab panels */
div[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
    background-color: rgba(26, 150, 65, 0.20) !important;
    color: #1a9641 !important;
    border-bottom: 3px solid #1a9641 !important;
}

/* Keeps the inner sub-tabs (Single Sample, Batch, How to Use) normal size and localized */
div[data-testid="stTabs"] div[data-testid="stTabs"] [data-baseweb="tab-list"] {
    display: inline-flex !important;
    width: auto !important;
    gap: 24px !important;
    border-bottom: none !important;
}

div[data-testid="stTabs"] div[data-testid="stTabs"] [data-baseweb="tab"] {
    flex-grow: 0 !important;
    font-size: 15px !important;
    font-weight: 600 !important;
    padding: 6px 12px !important;
    background-color: transparent !important;
    border-bottom: none !important;
}

/* Give tabs a subtle hover change so users know they are click options */
.stTabs [data-baseweb="tab"]:hover {
    background-color: rgba(26,150,65,0.04) !important;
}

/* Keeps the inner sub-tabs (Single Sample, Batch Scoring, How to Use) normal size and localized */
.stTabs [data-baseweb="tab-panel"] .stTabs [data-baseweb="tab-list"] {
    display: inline-flex !important;
    width: auto !important;
    gap: 24px !important;
    border-bottom: none !important;
}

.stTabs [data-baseweb="tab-panel"] .stTabs [data-baseweb="tab"] {
    flex-grow: 0 !important;
    flex-basis: auto !important;
    font-size: 15px !important;
    font-weight: 600 !important;
    padding: 6px 12px !important;
    border-radius: 0px !important;
    background-color: transparent !important;
    border-bottom: none !important;
}
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════
# 2. PEER GROUP DEFINITIONS PER REGION
# ════════════════════════════════════════════════════════════════════

def make_display(lst, code):
    return [f"{n} ({code})" for n in lst]

# ---- FLORIDA (USDA Soil Taxonomy suborders) ----
FL_S1_LIST = ["Fribists","Folists","Hemists","Histels","Saprists","Wassists"]   # Histosols — hidden from dropdown, still scoreable via backend/batch
FL_S2_LIST = ["Aquands","Aquents","Aquepts","Aquods","Aquoxs","Cryods","Humods","Orthels",
              "Peroxs","Torrands","Tropepts","Turbels","Udands","Udoxs","Ustands","Albolls",
              "Andepts","Aquolls","Aquults","Cryands","Cryepts","Cryolls","Gelepts","Gelolls",
              "Humults","Rendolls","Umbrepts","Ustoxs","Vitrands","Wassents","Xerands"]
FL_S3_LIST = ["Aqualfs","Aquerts","Boralfs","Borolls","Cryalfs","Ochrepts","Orthods","Orthoxs",
              "Udalfs","Udepts","Uderts","Udolls","Usterts","Ustolls","Xeralfs","Xerepts",
              "Xerolls","Xerults"]
FL_S4_LIST = ["Arents","Argids","Calcids","Cambids","Cryerts","Cryids","Durids","Fluvents",
              "Gypsids","Orthents","Orthids","Psamments","Salids","Torrerts","Torroxs",
              "Udults","Ustalfs","Ustepts","Ustults","Xererts"]

# Dropdown excludes S1 (Histosols) — kept in backend for batch scoring, just hidden from the picker
FL_TAXON_DISPLAY = sorted(
    make_display(FL_S2_LIST, "S2") + make_display(FL_S3_LIST, "S3") + make_display(FL_S4_LIST, "S4")
)

# Dropdown excludes T1 (Sand) — kept in backend for batch scoring, just hidden from the picker
FL_TEXTURE_MAP = {
    "Loamy Sand (T2)": "T2", "Sandy Loam (T3)": "T3",
    "Loam (T4)": "T4", "Silt Loam (T4)": "T4", "Silt (T4)": "T4",
    "Sandy Clay Loam (T4)": "T4", "Clay Loam (T4)": "T4", "Silty Clay Loam (T4)": "T4",
    "Sandy Clay (T4)": "T4", "Silty Clay (T4)": "T4", "Clay (T4)": "T4",
}
# Full texture map (used by batch scoring / backend so T1 still works if present in uploaded data)
FL_TEXTURE_MAP_FULL = dict(FL_TEXTURE_MAP)
FL_TEXTURE_MAP_FULL["Sand (T1)"] = "T1"
FL_TEXTURE_MAP_FULL["Muck (T5)"] = "T5"
FL_TEXTURE_MAP_FULL["Mucky Peat (T5)"] = "T5"
FL_TEXTURE_MAP_FULL["Peat (T5)"] = "T5"

FL_PG_TAXON_DESC = {
    "S1 — Histosols": "Organic soils (mucks, peats). Scored using a separate intercept-only model due to fundamentally different carbon dynamics.",
    "S2 — Moderately weathered": "Spodosols, Entisols, Inceptisols and similar. Common across Florida's flatwoods and low-lying areas.",
    "S3 — Well-structured mineral": "Alfisols, Vertisols and related orders. Better-developed structure, moderate carbon retention.",
    "S4 — Highly weathered / sandy": "Ultisols, Aridisols, Psamment Entisols. Highly leached soils with lower inherent carbon-holding capacity.",
}
FL_PG_TEXTURE_DESC = {
    "T1 — Sand": "Coarse sands. Lowest carbon retention.",
    "T2 — Loamy Sand": "Slightly finer; marginally higher carbon capacity.",
    "T3 — Sandy Loam": "Moderate texture, improved retention.",
    "T4 — Loam to Clay": "Highest carbon-holding capacity among mineral soils.",
    "T5 — Organic (Muck/Peat)": "Used only with the Histosol (S1) peer group.",
}

# ---- BRAZIL (WRB Reference Soil Groups) ----
BR_R1 = ["Acrisols","Fluvisols","Technosols","Anthrosols","Durisols","Gypsisols","Calcisols",
         "Solonchaks","Solonetz","Leptosols","Alisols","Regosols","Arenosols","Cryosols"]
BR_R2 = ["Ferralsols","Nitisols","Stagnosols","Plinthosols","Luvisols","Lixisols","Retisols",
         "Planosols","Vertisols","Gleysols"]
BR_R3 = ["Histosols","Umbrisols","Phaeozems","Chernozems","Kastanozems","Podzols","Andosols","Cambisols"]

BR_TAXON_DISPLAY = sorted(
    make_display(BR_R1, "R1") + make_display(BR_R2, "R2") + make_display(BR_R3, "R3")
)

BR_TEXTURE_MAP = {
    "Sand (T1)": "T1", "Loamy Sand (T1)": "T1", "Sandy Loam (T1)": "T1",
    "Silt (T2)": "T2", "Sandy Clay Loam (T2)": "T2", "Loam (T2)": "T2", "Silt Loam (T2)": "T2",
    "Sandy Clay (T3)": "T3", "Clay Loam (T3)": "T3", "Silty Clay Loam (T3)": "T3", "Silty Clay (T3)": "T3",
    "Clay (T4)": "T4",
}
BR_PG_TAXON_DESC = {
    "R1": "Acrisols, Fluvisols, Technosols, Anthrosols, Durisols, Gypsisols, Calcisols, Solonchaks, Solonetz, Leptosols, Alisols, Regosols, Arenosols, Cryosols",
    "R2": "Ferralsols, Nitisols, Stagnosols, Plinthosols, Luvisols, Lixisols, Retisols, Planosols, Vertisols, Gleysols",
    "R3": "Histosols, Umbrisols, Phaeozems, Chernozems, Kastanozems, Podzols, Andosols, Cambisols",
}
BR_PG_TEXTURE_DESC = {
    "T1": "Sand, Loamy Sand, Sandy Loam",
    "T2": "Silt, Sandy Clay Loam, Loam, Silt Loam",
    "T3": "Sandy Clay, Clay Loam, Silty Clay Loam, Silty Clay",
    "T4": "Clay",
}

# ---- BRAZIL (SiBC - Sistema Brasileiro de Classificação de Solos) ----
BR_R1_SIBC = [
    "Argissolos Vermelho-Amarelos", "Argissolos Vermelhos", "Neossolos Quartzarênicos", 
    "Argissolos Amarelos", "Neossolos Litólicos", "Argissolos Acinzentados"
]
BR_R2_SIBC = [
    "Latossolos Vermelho-Amarelos", "Latossolos Vermelhos", "Gleissolos Háplicos", 
    "Gleissolos Melânicos", "Plintossolos Pétricos", "Plintossolos Háplicos", 
    "Nitossolos Vermelhos", "Latossolos Amarelos", "Planossolos Háplicos", 
    "Luvissolos Crômicos", "Vertissolos Hidromórficos", "Plintossolos Argilúvicos", 
    "Planossolos Nátricos"
]
BR_R3_SIBC = [
    "Cambissolos Háplicos", "Latossolos Brunos", "Nitossolos Háplicos", 
    "Chernossolos Argilúvicos", "Chernossolos Ebânicos"
]

# Map the SiBC names to the identical R1, R2, R3 backend keys
BR_TAXON_DISPLAY_SIBC = sorted(
    make_display(BR_R1_SIBC, "R1") + make_display(BR_R2_SIBC, "R2") + make_display(BR_R3_SIBC, "R3")
)

# ---- SUB-SAHARAN AFRICA (Ethiopia-calibrated, WRB Reference Soil Groups) ----
ET_OR2 = ["Andosols","Chernozems","Gleysols","Kastanozems","Phaeozems","Podzols","Stagnosols"]
ET_OR3 = ["Acrisols","Alisols","Cambisols","Fluvisols","Planosols","Vertisols","Nitisols","Umbrisols"]
ET_OR4 = ["Ferralsols","Leptosols","Lixisols","Luvisols","Plinthosols","Retisols","Regosols"]
ET_OR5 = ["Arenosols","Calcisols","Durisols","Gypsisols","Solonchaks","Solonetz"]

ET_TAXON_DISPLAY = sorted(
    make_display(ET_OR2, "Or2") + make_display(ET_OR3, "Or3") +
    make_display(ET_OR4, "Or4") + make_display(ET_OR5, "Or5")
)

ET_TEXTURE_MAP = {
    "Sand (T1)": "T1", "Loamy Sand (T1)": "T1", "Sandy Loam (T1)": "T1",
    "Loam (T2)": "T2", "Silt Loam (T2)": "T2", "Silt (T2)": "T2",
    "Sandy Clay Loam (T2)": "T2", "Clay Loam (T2)": "T2", "Silty Clay Loam (T2)": "T2",
    "Sandy Clay (T3)": "T3", "Silty Clay (T3)": "T3", "Clay (T3)": "T3",
}
ET_PG_TAXON_DESC = {
    "Or2": "Andosols, Chernozems, Gleysols, Kastanozems, Phaeozems, Podzols, Stagnosols",
    "Or3": "Acrisols, Alisols, Cambisols, Fluvisols, Planosols, Vertisols, Nitisols, Umbrisols",
    "Or4": "Ferralsols, Leptosols, Lixisols, Luvisols, Plinthosols, Retisols, Regosols",
    "Or5": "Arenosols, Calcisols, Durisols, Gypsisols, Solonchaks, Solonetz",
}
ET_PG_TEXTURE_DESC = {
    "T1": "Sand, Loamy Sand, Sandy Loam",
    "T2": "Loam, Silt Loam, Silt, Sandy Clay Loam, Clay Loam, Silty Clay Loam",
    "T3": "Sandy Clay, Silty Clay, Clay",
}

# ════════════════════════════════════════════════════════════════════
# 3. REGION CONFIGURATION
# ════════════════════════════════════════════════════════════════════
REGIONS = {
    "Florida": {
        "key": "FL",
        "flag": "🇺🇸",
        "csv": "model_parameters.csv",
        "csv_hist": "histosol_parameters.csv",
        "has_histosol": True,
        "predictors": ["temp"],
        "taxon_display": FL_TAXON_DISPLAY,
        "texture_map": FL_TEXTURE_MAP,
        "texture_map_full": FL_TEXTURE_MAP_FULL,
        "s1_list": FL_S1_LIST,
        "pg_taxon_desc": FL_PG_TAXON_DESC,
        "pg_texture_desc": FL_PG_TEXTURE_DESC,
        "temp_range": (18.0, 26.0), "temp_default": 22.0,
        "precip_range": None, "precip_default": None,
        "lat_bounds": (24.5, 31.1), "lon_bounds": (-87.6, -80.0),
        "default_latlon": (29.65, -82.32),
        "model_note": "Logit-Gaussian Bayesian model fit on USDA-NRCS Florida soil survey data. Predictor: Mean Annual Temperature.",
        "col_map": {} 
    },
    "Brazil": {
        "key": "BR",
        "flag": "🇧🇷",
        "csv": "model_parameters_brazil.csv",
        "csv_hist": None,
        "has_histosol": False,
        "predictors": ["temp", "precip"],
        "taxon_display": BR_TAXON_DISPLAY,
        "taxon_display_sibc": BR_TAXON_DISPLAY_SIBC,
        "texture_map": BR_TEXTURE_MAP,
        "texture_map_full": BR_TEXTURE_MAP,
        "s1_list": [],
        "pg_taxon_desc": BR_PG_TAXON_DESC,
        "pg_texture_desc": BR_PG_TEXTURE_DESC,
        "temp_range": (16.0, 28.0), "temp_default": 23.0,
        "precip_range": (680.0, 2900.0), "precip_default": 1500.0,
        "lat_bounds": (-33.75, 5.27), "lon_bounds": (-73.99, -28.85),
        "default_latlon": (-15.78, -47.93),
        "model_note": "SHAPE-BR: Logit-Gaussian Bayesian model. Predictors: Mean Annual Temperature (MAT) and Mean Annual Precipitation (MAP).",
        "col_map": {
            "RSG_Group": "peer_group_taxon",
            "Texture_Group": "peer_group_texture",
            "MAT": "PRISM_tmea",
            "MAP": "PRISM_ppt"
        }
    },
    "Sub-Saharan Africa": {
        "key": "SSA",
        "flag": "🌍",
        "csv": "model_parameters_ethiopia.csv",
        "csv_hist": None,
        "has_histosol": False,
        "predictors": ["temp", "precip"],
        "taxon_display": ET_TAXON_DISPLAY,
        "texture_map": ET_TEXTURE_MAP,
        "texture_map_full": ET_TEXTURE_MAP,
        "s1_list": [],
        "pg_taxon_desc": ET_PG_TAXON_DESC,
        "pg_texture_desc": ET_PG_TEXTURE_DESC,
        "temp_range": (10.0, 29.0), "temp_default": 18.0,
        "precip_range": (400.0, 1800.0), "precip_default": 1100.0,
        "lat_bounds": (3.4, 14.9), "lon_bounds": (32.9, 48.0),
        "default_latlon": (9.03, 38.74),
        "model_note": "Bayesian model currently calibrated on Ethiopian soil survey data (MAT/MAP grid). Coverage will expand to additional Sub-Saharan African countries as data becomes available.",
        "col_map": {
            "Order_Cluster": "peer_group_taxon",
            "Texture_Cluster": "peer_group_texture",
            "MAT": "PRISM_tmea",
            "MAP": "PRISM_ppt"
        }
    },
}
TAXON_LABEL = {"Florida": "Soil Taxonomy Suborder", "Brazil": "Reference Soil Group (WRB)", "Sub-Saharan Africa": "Reference Soil Group (WRB)"}

# ════════════════════════════════════════════════════════════════════
# 4. DATA LOADING & DYNAMIC MASTER LOOKUP
# ════════════════════════════════════════════════════════════════════
@st.cache_data
def load_csv_safe(path, col_map=None):
    try:
        d = pd.read_csv(path)
        d.columns = d.columns.str.strip()
        if col_map:
            d = d.rename(columns=col_map)
        return d
    except FileNotFoundError:
        return None

def load_region_data(cfg):
    mineral = load_csv_safe(cfg["csv"], col_map=cfg.get("col_map"))
    hist = load_csv_safe(cfg["csv_hist"], col_map=cfg.get("col_map")) if cfg["csv_hist"] else None
    return mineral, hist

@st.cache_data
def load_smaf_lookup_dynamic(path):
    """Reads the master lookup workbook and maps indicators dynamically."""
    try:
        sh = pd.read_excel(path, sheet_name=None, dtype=str)
        
        def rows(name):
            df = sh[name].copy()
            df.columns = [str(c).strip() for c in df.columns]
            return df

        def num(x):
            try:
                v = float(x)
                return None if np.isnan(v) else v
            except (ValueError, TypeError):
                return None

        # 1. Parse constants
        K = {}
        for _, r in rows("constants").iterrows():
            v = num(r["value"])
            if r["param_name"] and v is not None:
                K[str(r["param_name"]).strip()] = v

        # 2. Parse Phosphorus Crop Factors
        crops = {}
        crop_ui_map = {}
        for _, r in rows("crop_factors").iterrows():
            code = num(r["crop_code"])
            if code is None: continue
            c_id = int(code)
            c_name = str(r["crop_name"]).strip()
            
            crops[c_id] = {
                "name": c_name,
                "popt": num(r["popt"]), "pmax": num(r["pmax"]), "b1": num(r["b1"])
            }
            crop_ui_map[c_name] = c_id

        # 3. Parse Dynamic pH Crop Benchmarks from min/max columns
        ph_benchmarks = {}
        if "ph_factors" in sh:
            for _, r in rows("ph_factors").iterrows():
                c_name = str(r["Clean crop name"]).strip()
                pmin = num(r["pH_min"])
                pmax = num(r["pH_max"])
                
                if pmin is not None and pmax is not None:
                    # Compute opt as midpoint, and sigma width tolerance dynamically
                    popt_val = (pmin + pmax) / 2.0
                    psigma_val = max(0.1, (pmax - pmin) / 4.0)
                    ph_benchmarks[c_name] = {"opt": popt_val, "sigma": psigma_val}
        else:
            # Fallback array if sheet isn't loaded yet
            ph_benchmarks = {c: {"opt": 6.0, "sigma": 0.5} for c in crop_ui_map.keys()}

        # 4. Parse method factors
        method = {}
        for _, r in rows("method_factors").iterrows():
            mc, wc = num(r["method_code"]), num(r["weathering_class"])
            if mc is not None and wc is not None:
                method[(int(mc), int(wc))] = num(r["method_factor"])

        # 5. Parse textures
        texture = {}
        for _, r in rows("texture_factors").iterrows():
            tc = num(r["texture_code"])
            if tc is not None:
                texture[int(tc)] = {"b3": num(r["txt_fp1_b3"]), "c3": num(r["txt_fp2_c3"])}

        # 6. Parse slopes
        slope = {}
        for _, r in rows("slope_factors").iterrows():
            sc = num(r["slope_class"])
            if sc is not None:
                slope[int(sc)] = {"envprotect": num(r["slope_fp1_envprotect"]), "c1": num(r["slope_fp2_c1"])}

        # 7. Parse organic matter
        om = {}
        for _, r in rows("om_factors").iterrows():
            oc = num(r["om_class"])
            if oc is not None:
                om[int(oc)] = {"b2": num(r["om_fp1_b2"]), "c2": num(r["om_fp2_c2"])}

        return {
            "crops": crops, "method": method, "texture": texture, "slope": slope, "om": om, "K": K,
            "crop_ui_map": crop_ui_map, "ph_benchmarks": ph_benchmarks
        }
    except Exception as e:
        st.error(f"⚠️ Could not dynamically process SMAF_lookup.xlsx: {e}")
        return None

# Initial database processing build
SMAF_DATA = load_smaf_lookup_dynamic("SMAF_lookup.xlsx")

# ── CONSTRAINT: Use only verified pH crops as the master list to prevent missing values ──
if SMAF_DATA and "ph_benchmarks" in SMAF_DATA and SMAF_DATA["ph_benchmarks"]:
    # Capitalize each crop name here
    MASTER_CROP_OPTIONS = sorted([c.capitalize() for c in list(SMAF_DATA["ph_benchmarks"].keys())])
elif SMAF_DATA and "crop_ui_map" in SMAF_DATA:
    MASTER_CROP_OPTIONS = sorted([c.capitalize() for c in list(SMAF_DATA["crop_ui_map"].keys())])
else:
    MASTER_CROP_OPTIONS = ["Apple", "Blueberry", "Corn / maize / sweet corn", "Orange", "Soybean"]

# Standardized descriptive selection boxes
SMAF_METHOD_MAP = {"Mehlich-3": 2, "Olsen": 1}
SMAF_WEATHERING_MAP = {"Highly Weathered": 1, "Slightly/Moderately Weathered": 2}
SMAF_TEXTURE_MAP = {"Coarse / Sandy": 1, "Medium / Loamy": 2, "Fine / Clayey": 3}
SMAF_SLOPE_MAP = {"0–2% Level Slope": 1, "2–5% Gentle Slope": 2, "5%+ Steep Slope": 3}

# ════════════════════════════════════════════════════════════════════
# 5. HELPER FUNCTIONS (Now with 5 Scoring Zones)
# ════════════════════════════════════════════════════════════════════
def run_smaf_p_score(soil_p, crop, method, weathering, texture, slope, toc):
    if not SMAF_DATA: return 0.0
    K = SMAF_DATA["K"]
    xc = soil_p * SMAF_DATA["method"].get((method, weathering), 1.0)
    pmax = SMAF_DATA["crops"].get(crop, {"pmax": 30.0})["pmax"]
    env = SMAF_DATA["slope"].get(slope, {"envprotect": 120.0})["envprotect"]

    b2, c2 = toc / 200.0, toc / 100.0
    b1 = SMAF_DATA["crops"].get(crop, {"b1": 1.0})["b1"]
    b3 = SMAF_DATA["texture"].get(texture, {"b3": 0.0})["b3"]
    c3 = SMAF_DATA["texture"].get(texture, {"c3": 1.0})["c3"]
    c1 = SMAF_DATA["slope"].get(slope, {"c1": 0.0})["c1"]

    b = b1 + (b1 * b2 * b3)
    c = (c1 + (c1 * c2)) * c3

    if xc <= pmax:
        y = (K["mmf_a"] * b + K["mmf_c"] * xc**K["mmf_d"]) / (b + xc**K["mmf_d"])
    elif xc >= env:
        y = K["weibull_a"] - K["weibull_b"] * np.exp(-c * xc**K["weibull_d"])
    else:
        y = 1.0
    return float(max(K["score_min"], min(K["score_max"], y)) * 100.0)

def fetch_climate(lat, lon, need_precip=False):
    """Fetch MAT (and optionally MAP) from NASA POWER climatology."""
    try:
        params = "T2M,PRECTOTCORR" if need_precip else "T2M"
        url = (f"https://power.larc.nasa.gov/api/temporal/climatology/point"
               f"?parameters={params}&community=AG&longitude={lon}&latitude={lat}&format=JSON")
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return None
        p = r.json().get("properties", {}).get("parameter", {})
        t2m = p.get("T2M", {})
        mat = t2m.get("ann") or t2m.get("annual") or t2m.get("ANN")
        result = {"temp": float(mat)} if mat is not None else {}
        if need_precip:
            precip = p.get("PRECTOTCORR", {})
            map_v = precip.get("ann") or precip.get("annual") or precip.get("ANN")
            if map_v is not None:
                result["precip"] = float(map_v) * 365.25
        return result if result else None
    except Exception:
        return None

def in_bounds(lat, lon, cfg):
    la0, la1 = cfg["lat_bounds"]
    lo0, lo1 = cfg["lon_bounds"]
    return (la0 <= lat <= la1) and (lo0 <= lon <= lo1)

def get_params_1d(df, tax, tex, target_temp):
    sub = df[(df["peer_group_taxon"] == tax) & (df["peer_group_texture"] == tex)
             ].sort_values("PRISM_tmea").reset_index(drop=True)
    if sub.empty:
        return None
    tc = float(np.clip(target_temp, sub["PRISM_tmea"].min(), sub["PRISM_tmea"].max()))
    exact = sub[sub["PRISM_tmea"] == tc]
    if not exact.empty:
        return exact.iloc[0]
    lo = sub[sub["PRISM_tmea"] <= tc].tail(1)
    hi = sub[sub["PRISM_tmea"] >= tc].head(1)
    if lo.empty or hi.empty:
        return sub.iloc[(sub["PRISM_tmea"] - tc).abs().argsort().iloc[0]]
    t0, t1 = lo.iloc[0]["PRISM_tmea"], hi.iloc[0]["PRISM_tmea"]
    w = (tc - t0) / (t1 - t0) if t1 != t0 else 0.0
    res = lo.iloc[0].copy()
    for col in ["mean_lp", "lcl_lp", "ucl_lp", "mean_sigma"]:
        res[col] = lo.iloc[0][col] * (1 - w) + hi.iloc[0][col] * w
    return res

def get_params_2d(df, tax, tex, target_temp, target_precip):
    sub = df[(df["peer_group_taxon"] == tax) & (df["peer_group_texture"] == tex)].reset_index(drop=True)
    if sub.empty:
        return None

    temps = sorted(sub["PRISM_tmea"].unique())
    precs = sorted(sub["PRISM_ppt"].unique())

    t = float(np.clip(target_temp, min(temps), max(temps)))
    p = float(np.clip(target_precip, min(precs), max(precs)))

    t0 = max([x for x in temps if x <= t], default=temps[0])
    t1 = min([x for x in temps if x >= t], default=temps[-1])
    p0 = max([x for x in precs if x <= p], default=precs[0])
    p1 = min([x for x in precs if x >= p], default=precs[-1])

    def get_row(tt, pp):
        r = sub[(sub["PRISM_tmea"] == tt) & (sub["PRISM_ppt"] == pp)]
        return r.iloc[0] if not r.empty else None

    Q11, Q21 = get_row(t0, p0), get_row(t1, p0)
    Q12, Q22 = get_row(t0, p1), get_row(t1, p1)

    if any(q is None for q in [Q11, Q21, Q12, Q22]):
        sub_d = sub.copy()
        sub_d["_dist"] = (sub_d["PRISM_tmea"] - t) ** 2 + (sub_d["PRISM_ppt"] - p) ** 2
        return sub_d.sort_values("_dist").iloc[0]

    wt = (t - t0) / (t1 - t0) if t1 != t0 else 0.0
    wp = (p - p0) / (p1 - p0) if p1 != p0 else 0.0

    result = Q11.copy()
    for col in ["mean_lp", "lcl_lp", "ucl_lp", "mean_sigma"]:
        top = Q11[col] * (1 - wt) + Q21[col] * wt
        bot = Q12[col] * (1 - wt) + Q22[col] * wt
        result[col] = top * (1 - wp) + bot * wp
    return result

def get_params_any(cfg, df, tax, tex, temp, precip=None):
    if "precip" in cfg["predictors"]:
        return get_params_2d(df, tax, tex, temp, precip)
    return get_params_1d(df, tax, tex, temp)

def logit(x):
    return np.log(np.clip(x, 0.0001, 0.9999) / (1 - np.clip(x, 0.0001, 0.9999)))

def invlogit(x):
    return 1 / (1 + np.exp(-x))

def compute_score(oc, lp_mean, sigma_val):
    return float(norm.cdf(logit(np.array(oc) / 100), loc=lp_mean, scale=sigma_val) * 100)

# Updates for 5-zone logic (20-point intervals)
def score_color(s):
    if s >= 80: return "#1a9641" # Dark Green
    if s >= 60: return "#77c35c" # Green
    if s >= 40: return "#ffc107" # Yellow
    if s >= 20: return "#f46d43" # Light Red
    return "#d73027"             # Dark Red

def score_label(s):
    if s >= 80: return "Very High"
    if s >= 60: return "High"
    if s >= 40: return "Medium"
    if s >= 20: return "Low"
    return "Very Low"

def percentile_to_oc(pct, lp_mean, sigma_val):
    return invlogit(norm.ppf(pct / 100, loc=lp_mean, scale=sigma_val)) * 100

def parse_code(display_str):
    return display_str.split("(")[1].replace(")", "")

def strip_code(display_str):
    return display_str.split(" (")[0]

# ════════════════════════════════════════════════════════════════════
# 6. DEMO BATCH DATA GENERATOR
# ════════════════════════════════════════════════════════════════════
def build_demo_batch(region_name, cfg, include_hidden=True):
    rng = np.random.default_rng(7)
    rows = []

    taxa = sorted(set(parse_code(t) for t in cfg["taxon_display"]))
    textures = sorted(set(cfg["texture_map"].values()))

    if region_name == "Florida" and include_hidden:
        taxa = taxa + ["S1"]
        textures = textures + ["T1"]

    oc_cycle = [0.5, 1.2, 1.8, 2.2, 2.8, 3.5, 4.5, 6.0]  # spans red → yellow → green
    lat_mid, lon_mid = cfg["default_latlon"]
    i = 1
    for tax in taxa:
        for tex in textures:
            if region_name == "Florida" and tax == "S1" and tex != "T5":
                continue 
            if region_name == "Florida" and tax != "S1" and tex == "T5":
                continue
            oc = oc_cycle[(i - 1) % len(oc_cycle)]
            row = {
                "sample_id": f"{cfg['key']}_{i:03d}",
                "oc": oc,
                "peer_group_taxon": tax,
                "peer_group_texture": tex,
                "PRISM_tmea": round(float(cfg["temp_default"] + rng.uniform(-2, 2)), 1),
            }
            if "precip" in cfg["predictors"]:
                row["PRISM_ppt"] = round(float(cfg["precip_default"] + rng.uniform(-150, 150)), 0)
            row["lat"] = round(float(lat_mid + rng.uniform(-1.2, 1.2)), 3)
            row["lon"] = round(float(lon_mid + rng.uniform(-1.2, 1.2)), 3)
            rows.append(row)
            i += 1
    return pd.DataFrame(rows)

# ════════════════════════════════════════════════════════════════════
# 7. HEADER
# ════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="fl-header">
    <div class="main-title">gSHAPE</div>
    <div class="sub-title">Soil Health Assessment Protocol and Evaluation</div>
    <div class="tagline">Sustainable Management of Tropical Soils Lab</div>
</div>
""", unsafe_allow_html=True)
# ════════════════════════════════════════════════════════════════════
# 8. RENDER FUNCTIONS
# ════════════════════════════════════════════════════════════════════

def render_bulk_density_placeholder(region_name):
    st.markdown(f"""
    <div class="coming-soon-box">
      <h3>⚖️ Bulk Density Scoring — Coming Soon</h3>
      <p>
        A peer-group-calibrated Bulk Density indicator for <b>{region_name}</b> is in development,
        following the same Bayesian scoring framework used for Soil Organic Carbon.
        It will help assess soil compaction and structural health alongside carbon stocks.
      </p>
    </div>
    """, unsafe_allow_html=True)
    with st.expander("Preview: what this tab will look like"):
        pc1, pc2 = st.columns(2)
        with pc1:
            # Added unique keys using region_name to prevent DuplicateElementId error
            st.selectbox("Soil Taxonomy / Reference Group", ["— available once launched —"], disabled=True, key=f"bd_tax_{region_name}")
            st.selectbox("Soil Texture", ["— available once launched —"], disabled=True, key=f"bd_tex_{region_name}")
        with pc2:
            st.number_input("Measured Bulk Density (g/cm³)", value=1.45, disabled=True, key=f"bd_val_{region_name}")
            st.slider("", 50, 99, 90, disabled=True, key=f"bd_pct_{region_name}")
        st.button("Calculate Bulk Density Score", disabled=True, key=f"bd_btn_{region_name}")

def render_single_sample(region_name, cfg, df, df_hist):
    k = cfg["key"]
    has_precip = "precip" in cfg["predictors"]

    # ── INITIALIZE MASTER KEYS (Prevents KeyErrors) ──
    if f"{k}_sm_crop" not in st.session_state: st.session_state[f"{k}_sm_crop"] = MASTER_CROP_OPTIONS[0]
    if f"{k}_oc" not in st.session_state: st.session_state[f"{k}_oc"] = 2.00
    if f"{k}_sm_p_input" not in st.session_state: st.session_state[f"{k}_sm_p_input"] = 25.0
    if f"{k}_ph_measured_input" not in st.session_state: st.session_state[f"{k}_ph_measured_input"] = 6.0
    if f"{k}_sm_method" not in st.session_state: st.session_state[f"{k}_sm_method"] = list(SMAF_METHOD_MAP.keys())[0]
    if f"{k}_sm_weather" not in st.session_state: st.session_state[f"{k}_sm_weather"] = list(SMAF_WEATHERING_MAP.keys())[0]
    if f"{k}_sm_tex" not in st.session_state: st.session_state[f"{k}_sm_tex"] = list(SMAF_TEXTURE_MAP.keys())[0]
    if f"{k}_sm_slope" not in st.session_state: st.session_state[f"{k}_sm_slope"] = list(SMAF_SLOPE_MAP.keys())[0]

    # ── MASTER SITE INPUTS (Always Visible) ──
    with st.expander("⚙️Site Inputs", expanded=True):
        c1, c2, c3 = st.columns(3)
        
        with c1:
            # Taxonomy & Landscape
            taxon_label = TAXON_LABEL[region_name]
            if region_name == "Brazil":
                br_tax_system = st.selectbox(
                    "Taxonomy System", 
                    ["World Reference Base (WRB)", "Sistema Brasileiro de Classificação (SiBC)"],
                    key=f"{k}_tax_system"
                )
                if "SiBC" in br_tax_system:
                    active_taxon_display = cfg["taxon_display_sibc"]
                    taxon_label = "Ordem / Subordem (SiBC)"
                else:
                    active_taxon_display = cfg["taxon_display"]
            else:
                active_taxon_display = cfg["taxon_display"]

            selected_sub = st.selectbox(taxon_label, active_taxon_display, format_func=strip_code, key=f"{k}_sub")
            selected_tex = st.selectbox("Texture", list(cfg["texture_map"].keys()), format_func=strip_code, key=f"{k}_tex")
            selected_sm_tex = st.selectbox("Texture Profile", list(SMAF_TEXTURE_MAP.keys()), key=f"{k}_sm_tex")
            selected_sm_slope = st.selectbox("Landscape Slope Profile", list(SMAF_SLOPE_MAP.keys()), key=f"{k}_sm_slope")
            chosen_crop = st.selectbox("Target Field Crop", MASTER_CROP_OPTIONS, key=f"{k}_sm_crop")
            
        with c2:
            # Management & Climate
            selected_method = st.selectbox("P Extraction Method", list(SMAF_METHOD_MAP.keys()), key=f"{k}_sm_method")
            selected_weath = st.selectbox("Soil Weathering Class", list(SMAF_WEATHERING_MAP.keys()), key=f"{k}_sm_weather")
            
            use_geo = st.checkbox("Fetch climate from coordinates", key=f"{k}_geo")
            lat_in, lon_in = cfg["default_latlon"]
            if use_geo:
                lat_in = st.number_input("Latitude", value=cfg["default_latlon"][0], format="%.4f", key=f"{k}_lat")
                lon_in = st.number_input("Longitude", value=cfg["default_latlon"][1], format="%.4f", key=f"{k}_lon")
                if st.button("🌐 Fetch Climate Data", key=f"{k}_fetch"):
                    if not in_bounds(lat_in, lon_in, cfg):
                        st.error(f"📍 Outside area of interest for {region_name}. Valid range: lat {cfg['lat_bounds'][0]}–{cfg['lat_bounds'][1]}, lon {cfg['lon_bounds'][0]}–{cfg['lon_bounds'][1]}.")
                    else:
                        res = fetch_climate(lat_in, lon_in, need_precip=has_precip)
                        if res:
                            if "temp" in res:
                                st.session_state[f"{k}_temp"] = float(np.clip(res["temp"], *cfg["temp_range"]))
                            if has_precip and "precip" in res:
                                st.session_state[f"{k}_precip"] = float(np.clip(res["precip"], *cfg["precip_range"]))
                            st.success(f"Climate fetched: {res.get('temp', '—'):.1f}°C" + (f", {res.get('precip', 0):.0f}mm/yr" if has_precip and "precip" in res else ""))
                        else:
                            st.warning("Could not fetch climate data. Enter manually below.")
            
            target_temp = st.slider("Mean Annual Temperature (°C)", cfg["temp_range"][0], cfg["temp_range"][1], value=float(st.session_state.get(f"{k}_temp", cfg["temp_default"])), step=0.1, key=f"{k}_temp")
            if has_precip:
                target_precip = st.slider("Mean Annual Precipitation (mm)", cfg["precip_range"][0], cfg["precip_range"][1], value=float(st.session_state.get(f"{k}_precip", cfg["precip_default"])), step=10.0, key=f"{k}_precip")
            else:
                target_precip = None
                
            if cfg["has_histosol"]:
                hist_toggle = st.checkbox("📌 This is an organic / Histosol soil (Muck, Peat)", key=f"{k}_hist")
            else:
                hist_toggle = False

        with c3:
            # Core Lab Measurements
            oc_val = st.number_input("Measured SOC (%)", 0.01, 80.0, key=f"{k}_oc")
            p_val = st.number_input("Measured Extractable P (mg/kg)", 0.0, 500.0, key=f"{k}_sm_p_input")
            ph_val = st.number_input("Measured Soil pH", 0.0, 14.0, key=f"{k}_ph_measured_input")
            target_pct = st.slider("Benchmark Percentile (SOC)", 50, 99, 90, key=f"{k}_pct")

    # ── GLOBAL SOC PEER GROUP RESOLUTION ──
    tax = parse_code(selected_sub)
    tex = cfg["texture_map"][selected_tex]

    if hist_toggle and cfg["has_histosol"] and df_hist is not None:
        lp_mean   = float(df_hist["mean_lp"].iloc[0])
        lp_lcl    = float(df_hist["lcl_lp"].iloc[0])
        lp_ucl    = float(df_hist["ucl_lp"].iloc[0])
        sigma_val = float(np.exp(df_hist["mean_sigma"].iloc[0]))
        plot_max  = 80.0
    else:
        if df is None:
            st.error(f"Parameter file '{cfg['csv']}' not found for {region_name}.")
            return
        row = get_params_any(cfg, df, tax, tex, target_temp, target_precip)
        if row is not None:
            lp_mean   = float(row["mean_lp"])
            lp_lcl    = float(row["lcl_lp"])
            lp_ucl    = float(row["ucl_lp"])
            sigma_val = float(np.exp(row["mean_sigma"]))
            plot_max  = max(15.0, oc_val + 5)
        else:
            lp_mean, lp_lcl, lp_ucl, sigma_val, plot_max = 0.0, 0.0, 0.0, 1.0, 15.0

    # ── INDICATOR SELECTION ──
    indicator_options = ["Soil Organic Carbon", "Soil Phosphorus", "pH"]
    chosen_indicator = st.selectbox(
        "Soil Health Indicators:",
        indicator_options,
        key=f"{cfg['key']}_indicator_shared"
    )
    st.divider()

    col_l, col_r = st.columns([1, 2])

    # ── CONDITIONAL SCORING LOGIC ──
    if chosen_indicator == "Soil Phosphorus":
        if not SMAF_DATA:
            st.error("Missing `SMAF_lookup.xlsx` file dashboard linkage.")
            return
            
        selected_crop_input = st.session_state[f"{k}_sm_crop"].lower()
        crop_id = SMAF_DATA["crop_ui_map"].get(selected_crop_input, 0)
        
        if crop_id not in SMAF_DATA["crops"]:
            st.error(f"⚠️ **Phosphorus Parameters Missing:** '{st.session_state[f'{k}_sm_crop']}' has valid pH metrics but is missing from the `crop_factors` sheet tab. Please check your Excel spreadsheet.")
            return

        method_id = SMAF_METHOD_MAP[st.session_state[f"{k}_sm_method"]]
        weather_id = SMAF_WEATHERING_MAP[st.session_state[f"{k}_sm_weather"]]
        texture_id = SMAF_TEXTURE_MAP[st.session_state[f"{k}_sm_tex"]]
        slope_id = SMAF_SLOPE_MAP[st.session_state[f"{k}_sm_slope"]]

        # Unified SOC value feeds into Phosphorus scoring
        score_p = run_smaf_p_score(p_val, crop_id, method_id, weather_id, texture_id, slope_id, oc_val)
        color_p = score_color(score_p)
        label_p = score_label(score_p)

        with col_l:
            gauge_title = f"<b style='font-size:17px'>{label_p}</b><br><span style='font-size:11px;color:gray'>SMAF Index · {p_val} mg/kg P</span>"
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=round(score_p, 1),
                title={"text": gauge_title, "font": {"size": 13}},
                number={"suffix": "/100", "font": {"size": 38, "color": color_p}},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "gray"},
                    "bar": {"color": color_p, "thickness": 0.28},
                    "bgcolor": "rgba(0,0,0,0)",
                    "steps": [
                        {"range": [0, 20], "color": "rgba(215,48,39,0.35)"},
                        {"range": [20, 40], "color": "rgba(244,109,67,0.35)"},
                        {"range": [40, 60], "color": "rgba(255,193,7,0.35)"},
                        {"range": [60, 80], "color": "rgba(119,195,92,0.35)"},
                        {"range": [80, 100], "color": "rgba(26,150,65,0.35)"}
                    ]
                }
            ))
            fig_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=260, margin=dict(l=20, r=20, t=80, b=10))
            st.plotly_chart(fig_gauge, use_container_width=True, key=f"{k}_p_gauge")

            st.divider()
            pmax_lim = SMAF_DATA["crops"][crop_id]["pmax"]
            corrected_p = p_val * SMAF_DATA["method"][(method_id, weather_id)]
            st.metric("Corrected Value", f"{corrected_p:.1f} mg/kg", f"Threshold: {pmax_lim:.1f}")

        with col_r:
            st.markdown("#### Scoring Curve")
            grid = np.array([5, 10, 15, 20, 30, 50, 60, 90, 120, 150, 180, 210, 300.0])
            gy = np.array([run_smaf_p_score(x, crop_id, method_id, weather_id, texture_id, slope_id, oc_val) for x in grid])
            
            spl = PchipInterpolator(grid, gy / 100.0)
            xs = np.linspace(grid.min(), grid.max(), 300)
            ys = np.clip(spl(xs), 0.0, 1.0)

            fig_p = go.Figure()
            fig_p.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="#1F4E5F", width=3), name="SMAF Function", hovertemplate="P: %{x:.1f}<br>Score: %{y:.2f}<extra></extra>"))
            fig_p.add_trace(go.Scatter(x=[p_val], y=[score_p / 100.0], mode="markers", marker=dict(color=color_p, size=14, line=dict(color="white", width=2)), name="Your Site"))
            
            fig_p.update_layout(
                xaxis_title="Extractable P (mg/kg)", yaxis_title="Performance Rating",
                yaxis=dict(range=[0, 1.05], tickformat=".2f"), xaxis=dict(range=[0, 300]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=400, margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig_p, width='stretch', key=f"{k}_p_curve_plot")

            st.markdown("##### Agronomic Interpretation")
            if corrected_p < pmax_lim:
                st.error("📉 **Deficient Zone:** Available phosphorus constraints restrict agronomic production potential.")
            elif score_p > 99.0:
                st.success("🎯 **Optimum sufficiency plateau:** Maximum vegetative performance profile verified.")
            else:
                st.warning("⚠️ **Environmental Hazard Threshold:** Runoff risk flagged due to high baseline matrix saturation.")
                
    elif chosen_indicator == "pH":
        # Global definition prevents NameError
        crop_selected_name = st.session_state[f"{k}_sm_crop"]
        ph_benchmarks = SMAF_DATA.get("ph_benchmarks", {}) if SMAF_DATA else {}
        
        # Case insensitive lookup
        ph_benchmarks_lower = {key.lower(): val for key, val in ph_benchmarks.items()}
        benchmarks = ph_benchmarks_lower.get(crop_selected_name.lower())
        
        if not benchmarks:
            st.warning(f"ℹ️ **pH Target Data:** Optimum thresholds for **{crop_selected_name}** are being calibrated.")
            st.metric("Soil pH", ph_val)
        else:
            ph_opt = benchmarks["opt"]
            ph_sigma = benchmarks["sigma"]
            score_ph = float(100.0 * np.exp(-((ph_val - ph_opt) / (2.0 * ph_sigma)) ** 2))
            color_ph = score_color(score_ph)
            label_ph = score_label(score_ph)

            with col_l:
                gauge_title = f"<b style='font-size:17px'>{label_ph}</b><br><span style='font-size:11px;color:gray'>{crop_selected_name} · pH {ph_val}</span>"
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number", value=round(score_ph, 1),
                    title={"text": gauge_title, "font": {"size": 13}},
                    number={"suffix": "/100", "font": {"size": 38, "color": color_ph}},
                    gauge={
                        "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "gray", "tickvals": [0, 20, 40, 60, 80, 100]},
                        "bar": {"color": color_ph, "thickness": 0.28},
                        "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
                        "steps": [
                            {"range": [0, 20], "color": "rgba(215,48,39,0.35)"},
                            {"range": [20, 40], "color": "rgba(244,109,67,0.35)"},
                            {"range": [40, 60], "color": "rgba(255,193,7,0.35)"},
                            {"range": [60, 80], "color": "rgba(119,195,92,0.35)"},
                            {"range": [80, 100], "color": "rgba(26,150,65,0.35)"}
                        ],
                        "threshold": {"line": {"color": color_ph, "width": 5}, "thickness": 0.8, "value": score_ph}
                    }
                ))
                fig_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=260, margin=dict(l=20, r=20, t=80, b=10), autosize=True)
                st.plotly_chart(fig_gauge, use_container_width=True, key=f"{k}_gauge_chart_ph")

                st.divider()
                gap = ph_val - ph_opt
                st.metric("Variance from Optimum", f"{gap:+.2f} pH", "Target Achieved" if abs(gap) < 0.2 else "Needs Adjustment")

            with col_r:
                st.markdown("#### Scoring Curve")
                x_axis = np.linspace(3.0, 9.0, 300) 
                y_axis = 100.0 * np.exp(-((x_axis - ph_opt) / (2.0 * ph_sigma)) ** 2)
                
                fig_cdf = go.Figure()
                fig_cdf.add_trace(go.Scatter(x=x_axis, y=y_axis / 100, mode="lines", line=dict(color="#1a9641", width=3), name="Crop Tolerance Curve", hovertemplate="pH: %{x:.1f}<br>Score: %{y:.1%}<extra></extra>"))
                fig_cdf.add_trace(go.Scatter(x=[ph_val], y=[score_ph / 100], mode="markers", marker=dict(color=color_ph, size=14, symbol="circle", line=dict(color="white", width=2)), name="Your Field pH"))
                fig_cdf.add_trace(go.Scatter(x=[ph_opt], y=[1.0], mode="markers", marker=dict(color="#0072B2", size=13, symbol="x-thin", line=dict(color="#0072B2", width=3)), name=f"Optimum ({ph_opt})"))
                
                fig_cdf.update_layout(
                    xaxis_title="Soil pH", yaxis_title="SHAPE Score",
                    yaxis=dict(range=[0, 1.1], tickformat=".0%"), xaxis=dict(range=[3.0, 9.0]),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=400, margin=dict(l=10, r=10, t=40, b=10)
                )
                st.plotly_chart(fig_cdf, width='stretch', key=f"{k}_cdf_chart_ph")
                
                if use_geo and f"{k}_lat" in st.session_state and in_bounds(lat_in, lon_in, cfg):
                    st.markdown("#### Site Location")
                    st.map(pd.DataFrame({"lat": [lat_in], "lon": [lon_in]}), zoom=6)

    elif chosen_indicator == "Soil Organic Carbon":
        score  = compute_score(oc_val, lp_mean, sigma_val)
        color  = score_color(score)
        label  = score_label(score)
        tgt_oc = percentile_to_oc(target_pct, lp_mean, sigma_val)

        with col_l:
            climate_str = f"{target_temp:.1f}°C"
            if has_precip and target_precip is not None:
                climate_str += f" · {target_precip:.0f}mm"
            gauge_title = (f"<b style='font-size:17px'>{label}</b><br>"
                           f"<span style='font-size:11px;color:gray'>{strip_code(selected_sub)} · {strip_code(selected_tex)} · {climate_str} · SOC {oc_val}%</span>")
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=round(score, 1),
                title={"text": gauge_title, "font": {"size": 13}},
                number={"suffix": "/100", "font": {"size": 38, "color": color}},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "gray", "tickvals": [0, 20, 40, 60, 80, 100]},
                    "bar": {"color": color, "thickness": 0.28},
                    "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
                    "steps": [
                        {"range": [0, 20], "color": "rgba(215,48,39,0.35)"},
                        {"range": [20, 40], "color": "rgba(244,109,67,0.35)"},
                        {"range": [40, 60], "color": "rgba(255,193,7,0.35)"},
                        {"range": [60, 80], "color": "rgba(119,195,92,0.35)"},
                        {"range": [80, 100], "color": "rgba(26,150,65,0.35)"}
                    ],
                    "threshold": {"line": {"color": color, "width": 5}, "thickness": 0.8, "value": score}
                }
            ))
            fig_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                    height=260, margin=dict(l=20, r=20, t=80, b=10),
                                    autosize=True)
            st.plotly_chart(fig_gauge, use_container_width=True, key=f"{k}_gauge_chart")

            st.divider()
            gap = tgt_oc - oc_val
            m1, m2 = st.columns(2)
            with m1:
                st.metric("Above peer median", f"{score - 50:+.1f} pts",
                          f"{'↑ above' if score >= 50 else '↓ below'} 50th pct")
            with m2:
                st.metric(f"Gap to {target_pct}th pct", f"{abs(gap):.2f}% SOC",
                          "✅ Exceeds target" if gap <= 0 else f"+{gap:.2f}% needed")

            st.divider()
            st.markdown("**SOC targets by percentile**")
            bench = pd.DataFrame({
                "Percentile": ["80th", "90th", "95th", "99th"],
                "Target SOC (%)": [f"{percentile_to_oc(p, lp_mean, sigma_val):.2f}" for p in [80, 90, 95, 99]]
            })
            st.dataframe(bench, hide_index=True, width='stretch')

            st.divider()
            st.markdown("**📥 Export result**")
            result_df = pd.DataFrame([{
                "Region": region_name, "Suborder": strip_code(selected_sub), "Texture": strip_code(selected_tex),
                "Temperature_C": target_temp,
                **({"Precipitation_mm": target_precip} if has_precip else {}),
                "SOC_pct": oc_val, "SHAPE_Score": round(score, 2), "Zone": label,
                "Target_SOC_pct": round(tgt_oc, 3)
            }])
            st.download_button("⬇️ Download as CSV", data=result_df.to_csv(index=False).encode("utf-8"),
                               file_name=f"SHAPE_{cfg['key']}_{tax}_{tex}_{oc_val}pct.csv",
                               mime="text/csv", width='stretch', key=f"{k}_export_btn")

        with col_r:
            st.markdown("#### Scoring Curve")
            x = np.linspace(0.01, plot_max, 400)
            lx = logit(x / 100)
            y_mean = norm.cdf(lx, lp_mean, sigma_val)
            y_lcl  = norm.cdf(lx, lp_lcl, sigma_val)
            y_ucl  = norm.cdf(lx, lp_ucl, sigma_val)

            fig_cdf = go.Figure()
            fig_cdf.add_trace(go.Scatter(
                x=np.concatenate([x, x[::-1]]), y=np.concatenate([y_ucl, y_lcl[::-1]]),
                fill="toself", fillcolor="rgba(26,150,65,0.18)", line=dict(color="rgba(0,0,0,0)"),
                name="95% Credible Interval", hoverinfo="skip"
            ))
            fig_cdf.add_trace(go.Scatter(
                x=x, y=y_mean, mode="lines", line=dict(color="#1a9641", width=2.5), name="Score Curve",
                hovertemplate="SOC: %{x:.2f}%<br>Score: %{y:.3f}<extra></extra>"
            ))
            for zy, zl in [(0.20, "V.Low | Low"), (0.40, "Low | Med"), (0.60, "Med | High"), (0.80, "High | V.High")]:
                fig_cdf.add_hline(y=zy, line_dash="dot", line_color="rgba(150,150,150,0.5)",
                                  annotation_text=zl, annotation_position="right")
            fig_cdf.add_trace(go.Scatter(
                x=[oc_val], y=[score / 100], mode="markers",
                marker=dict(color=color, size=14, symbol="circle", line=dict(color="white", width=2)),
                name="Your Site", hovertemplate=f"Your site<br>SOC: {oc_val}%<br>Score: {score:.1f}/100<extra></extra>"
            ))
            fig_cdf.add_trace(go.Scatter(
                x=[tgt_oc], y=[target_pct / 100], mode="markers",
                marker=dict(color="#0072B2", size=13, symbol="x-thin", line=dict(color="#0072B2", width=3)),
                name=f"Target ({target_pct}th)", hovertemplate=f"Target<br>SOC: {tgt_oc:.2f}%<br>{target_pct}th pct<extra></extra>"
            ))
            fig_cdf.update_layout(
                xaxis_title="Soil Organic Carbon (%)", yaxis_title="SHAPE Score",
                yaxis=dict(range=[0, 1], tickformat=".0%"), xaxis=dict(range=[0, plot_max]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                height=400, margin=dict(l=10, r=10, t=40, b=10)
            )
            fig_cdf.update_xaxes(gridcolor="rgba(150,150,150,0.1)")
            fig_cdf.update_yaxes(gridcolor="rgba(150,150,150,0.1)")
            st.plotly_chart(fig_cdf, width='stretch', key=f"{k}_cdf_chart")

            if use_geo and f"{k}_lat" in st.session_state and in_bounds(lat_in, lon_in, cfg):
                st.markdown("#### Site Location")
                st.map(pd.DataFrame({"lat": [lat_in], "lon": [lon_in]}), zoom=6)

        st.divider()
        st.markdown("#### Management Recommendations")
        if score < 20:
            st.error("🔴 **Red Zone — Very Low Function**")
            st.markdown("""
**Priority: Critical intervention to rebuild baseline carbon stocks**
- Integrate high-biomass cover crops to feed soil biology
- Apply compost or biochar to jumpstart microbial activity
- Avoid bare soil periods — armor the surface at all times
""")
        elif score < 40:
            st.warning("🟠 **Orange Zone — Low Function**")
            st.markdown("""
**Priority: Stabilize and begin expanding carbon pools**
- Maintain living roots year-round
- Reduce physical soil disturbance significantly
- Introduce diverse crop rotations
""")
        elif score < 60:
            st.warning("🟡 **Yellow Zone — Medium Function**")
            st.markdown("""
**Priority: Optimize biological cycling**
- Transition to continuous No-Till or strip-till systems
- Integrate perennial cover or sod-based rotations
- Track SOC trajectory annually
""")
        elif score < 80:
            st.success("🟢 **Light Green Zone — High Function**")
            st.markdown("""
**Priority: Stewardship and expansion**
- Maintain full soil cover to prevent erosion and oxidation
- Focus on biological monitoring of existing carbon sinks
- Protect elite stocks while monitoring for drought stress
""")
        else:
            st.success("🌟 **Dark Green Zone — Very High Function**")
            st.markdown("""
**Priority: Maximum resilience and monetization**
- Maintain current elite regenerative practices
- Focus on deep biological mapping of stable carbon stocks
- Consider exploring premium carbon market participation
""")

        # ── Carbon Sequestration Calculator ──
        st.divider()
        st.markdown("### 🌍 Carbon Sequestration Calculator")
        st.markdown("Estimate carbon stock, sequestration gap, credit value, and time to target based on the benchmark above.")

        with st.expander("⚙️ Field & Market Parameters", expanded=True):
            cc1, cc2, cc3, cc4, cc5 = st.columns(5)
            with cc1:
                field_area = st.number_input("Field area (acres)", 1.0, 100000.0, 100.0, 10.0, key=f"{k}_area")
            with cc2:
                bulk_density = st.number_input("Bulk density (g/cm³)", 0.8, 2.0, 1.45, 0.05, key=f"{k}_bd")
            with cc3:
                depth_cm = st.number_input("Sampling depth (cm)", 5, 100, 30, 5, key=f"{k}_depth")
            with cc4:
                carbon_price = st.number_input("Carbon price ($/t CO₂e)", 1.0, 500.0, 25.0, 5.0, key=f"{k}_price")
            with cc5:
                annual_rate = st.number_input("Annual SOC gain (%/yr)", 0.01, 2.0, 0.20, 0.05, key=f"{k}_rate")

        def soc_to_tc_per_acre(soc_pct, bd, depth):
            return (soc_pct / 100.0) * bd * depth * 10.0 * 0.4047

        C_RATIO = 3.667
        soc_target_90 = percentile_to_oc(90, lp_mean, sigma_val)
        curr_tc_acre = soc_to_tc_per_acre(oc_val, bulk_density, depth_cm)
        tgt_tc_acre  = soc_to_tc_per_acre(soc_target_90, bulk_density, depth_cm)
        curr_tc_field = curr_tc_acre * field_area
        tgt_tc_field  = tgt_tc_acre * field_area
        gap_tc_field  = max(0.0, tgt_tc_field - curr_tc_field)
        gap_co2_field = gap_tc_field * C_RATIO
        credit_value  = gap_co2_field * carbon_price
        years_to_tgt  = (max(0.0, soc_target_90 - oc_val) / annual_rate) if annual_rate > 0 else 0

        sc1, sc2, sc3, sc4, sc5 = st.columns(5)
        sc1.metric("Current C stock", f"{curr_tc_field:,.1f} t C", f"{curr_tc_acre:.2f} t C/acre")
        sc2.metric("Target C stock (90th pct)", f"{tgt_tc_field:,.1f} t C", f"{tgt_tc_acre:.2f} t C/acre")
        sc3.metric("Sequestration gap", f"{gap_tc_field:,.1f} t C", f"{gap_co2_field:,.1f} t CO₂e")
        sc4.metric("Potential credit value", f"${credit_value:,.0f}", f"@ ${carbon_price}/t CO₂e")
        sc5.metric("Years to 90th pct", f"{years_to_tgt:.1f} yrs", f"@ {annual_rate}%/yr gain")

        st.divider()
        chart_col, table_col = st.columns([3, 2])
        with chart_col:
            st.markdown("**Projected SOC trajectory to 90th percentile benchmark**")
            max_yrs = max(int(np.ceil(years_to_tgt)) + 5, 20)
            yr_axis = np.arange(0, max_yrs + 1, 1.0)
            soc_traj = np.minimum(oc_val + annual_rate * yr_axis, soc_target_90)
            tc_traj  = soc_to_tc_per_acre(soc_traj, bulk_density, depth_cm) * field_area
            val_traj = (tc_traj - curr_tc_field) * C_RATIO * carbon_price

            fig_traj = go.Figure()
            fig_traj.add_trace(go.Scatter(x=yr_axis, y=soc_traj, mode="lines", name="SOC (%)",
                                          line=dict(color="#1a9641", width=2.5),
                                          hovertemplate="Year %{x:.0f}<br>SOC: %{y:.2f}%<extra></extra>"))
            fig_traj.add_hline(y=soc_target_90, line_dash="dash", line_color="rgba(0,114,178,0.6)",
                               annotation_text=f"90th pct target ({soc_target_90:.2f}%)", annotation_position="right")
            fig_traj.add_hline(y=oc_val, line_dash="dot", line_color="rgba(200,100,0,0.5)",
                               annotation_text=f"Current ({oc_val}%)", annotation_position="right")
            if years_to_tgt > 0:
                fig_traj.add_trace(go.Scatter(
                    x=[years_to_tgt], y=[soc_target_90], mode="markers+text",
                    marker=dict(color="#0072B2", size=12, line=dict(color="white", width=2)),
                    text=[f"  Yr {years_to_tgt:.1f}"], textposition="middle right", name="Target reached"
                ))
            fig_traj.add_trace(go.Scatter(x=yr_axis, y=val_traj, mode="lines", name="Cumulative credit value ($)",
                                          line=dict(color="#E69F00", width=2, dash="dot"), yaxis="y2",
                                          hovertemplate="Year %{x:.0f}<br>Value: $%{y:,.0f}<extra></extra>"))
            fig_traj.update_layout(
                xaxis_title="Years from now",
                yaxis=dict(title="SOC (%)", gridcolor="rgba(150,150,150,0.1)"),
                yaxis2=dict(title="Cumulative credit value ($)", overlaying="y", side="right",
                            showgrid=False, tickformat="$,.0f"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                height=360, margin=dict(l=10, r=60, t=40, b=10)
            )
            st.plotly_chart(fig_traj, width='stretch', key=f"{k}_traj_chart")

        with table_col:
            st.markdown("**Credit value sensitivity ($/t CO₂e)**")
            price_scenarios = [10, 25, 50, 100, 200]
            milestone_years = sorted(set([5, 10, 20, int(np.ceil(years_to_tgt))] if years_to_tgt > 0 else [5, 10, 20]))
            rows = []
            for yr in milestone_years:
                soc_at_yr = min(oc_val + annual_rate * yr, soc_target_90)
                tc_at_yr = soc_to_tc_per_acre(soc_at_yr, bulk_density, depth_cm) * field_area
                co2_at_yr = max(0.0, tc_at_yr - curr_tc_field) * C_RATIO
                row_vals = {"Year": f"Yr {yr}"}
                for p in price_scenarios:
                    row_vals[f"${p}"] = f"${co2_at_yr * p:,.0f}"
                rows.append(row_vals)
            st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')

            ann_tc = soc_to_tc_per_acre(annual_rate, bulk_density, depth_cm) * field_area
            ann_co2 = ann_tc * C_RATIO
            ann_value = ann_co2 * carbon_price
            st.markdown(f"""
| Metric | Value |
|---|---|
| Annual C gain | {ann_tc:.2f} t C/yr |
| Annual CO₂e | {ann_co2:.2f} t CO₂e/yr |
| Annual credit value | ${ann_value:,.0f}/yr |
""")
            st.caption("⚠️ Estimates assume linear SOC accumulation. Actual sequestration is nonlinear "
                       "and depends on management, soil type, and climate. Consult a certified carbon "
                       "project developer before trading.")

    st.divider()
    st.markdown("#### 📚 Resources")
    rc1, rc2, rc3 = st.columns(3)
    with rc1:
        st.link_button("UF IFAS — Cover Crops for Soil Health",
                       "https://ask.ifas.ufl.edu/publication/AG277", width='stretch')
    with rc2:
        st.link_button("USDA-NRCS Soil Health Principles",
                       "https://www.nrcs.usda.gov/conservation-basics/natural-resource-concerns/soils/soil-health",
                       width='stretch')
    with rc3:
        st.link_button("Related Research (Google Scholar)",
                       "https://scholar.google.com/scholar?q=soil+organic+carbon+soil+health",
                       width='stretch')

def render_batch_scoring(region_name, cfg, df, df_hist):
    k = cfg["key"]
    has_precip = "precip" in cfg["predictors"]

    st.markdown("#### Upload a CSV to score multiple samples at once")

    template_cols = {
        "sample_id": ["Site_A", "Site_B", "Site_C"],
        "oc": [1.8, 2.5, 4.1],
        "peer_group_taxon": [parse_code(cfg["taxon_display"][0]), parse_code(cfg["taxon_display"][1]), parse_code(cfg["taxon_display"][2])],
        "peer_group_texture": list(set(cfg["texture_map"].values()))[:3] if len(set(cfg["texture_map"].values())) >= 3 else list(set(cfg["texture_map"].values())),
        "PRISM_tmea": [cfg["temp_default"]] * 3,
    }
    if has_precip:
        template_cols["PRISM_ppt"] = [cfg["precip_default"]] * 3
    template_cols["lat"] = [cfg["default_latlon"][0]] * 3
    template_cols["lon"] = [cfg["default_latlon"][1]] * 3
    template = pd.DataFrame(template_cols)

    bcol1, bcol2 = st.columns(2)
    with bcol1:
        st.download_button("⬇️ Download CSV Template", data=template.to_csv(index=False).encode("utf-8"),
                           file_name=f"SHAPE_{cfg['key']}_batch_template.csv", mime="text/csv",
                           width='stretch', key=f"{k}_template_btn")
    with bcol2:
        if st.button("✨ Try Demo Data", width='stretch', key=f"{k}_demo_btn"):
            st.session_state[f"{k}_batch_df"] = build_demo_batch(region_name, cfg)

    uploaded = st.file_uploader("Upload your CSV", type="csv", key=f"{k}_uploader")
    if uploaded is not None:
        try:
            up_df = pd.read_csv(uploaded)
            up_df.columns = up_df.columns.str.strip()
            st.session_state[f"{k}_batch_df"] = up_df
        except Exception as e:
            st.error(f"Error reading file: {e}")

    batch = st.session_state.get(f"{k}_batch_df")

    if batch is not None:
        required = {"sample_id", "oc", "peer_group_taxon", "peer_group_texture", "PRISM_tmea"}
        missing_cols = required - set(batch.columns)
        if missing_cols:
            st.error(f"Missing columns: {missing_cols}")
            return

        scores, labels, tgt_ocs = [], [], []
        for _, r in batch.iterrows():
            tax_b = str(r["peer_group_taxon"]).strip()
            tex_b = str(r["peer_group_texture"]).strip()
            oc_b  = float(r["oc"])
            tmp_b = float(r["PRISM_tmea"])
            precip_b = float(r["PRISM_ppt"]) if (has_precip and "PRISM_ppt" in r) else None

            is_hist = cfg["has_histosol"] and tax_b == "S1" and tex_b == "T5"
            if is_hist and df_hist is not None:
                lp_b = float(df_hist["mean_lp"].iloc[0])
                sig_b = float(np.exp(df_hist["mean_sigma"].iloc[0]))
            else:
                row_b = get_params_any(cfg, df, tax_b, tex_b, tmp_b, precip_b)
                if row_b is None:
                    scores.append(np.nan); labels.append("No data"); tgt_ocs.append(np.nan)
                    continue
                lp_b = float(row_b["mean_lp"])
                sig_b = float(np.exp(row_b["mean_sigma"]))

            s = compute_score(oc_b, lp_b, sig_b)
            scores.append(round(s, 2))
            labels.append(score_label(s))
            tgt_ocs.append(round(percentile_to_oc(90, lp_b, sig_b), 3))

        batch = batch.copy()
        batch["SHAPE_Score"] = scores
        batch["Zone"] = labels
        batch["SOC_target_90th"] = tgt_ocs
        batch["Gap_to_90th"] = (batch["SOC_target_90th"] - batch["oc"]).round(3)

        valid = batch["SHAPE_Score"].dropna()
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Samples scored", len(valid))
        mc2.metric("Mean score", f"{valid.mean():.1f}/100" if len(valid) else "—")
        mc3.metric("High / V. High", f"{(valid >= 60).sum()} ({100*(valid>=60).mean():.0f}%)" if len(valid) else "—")
        mc4.metric("Low / V. Low", f"{(valid < 40).sum()} ({100*(valid<40).mean():.0f}%)" if len(valid) else "—")

        st.divider()
        fig_dist = go.Figure()
        fig_dist.add_trace(go.Histogram(x=valid, nbinsx=20, marker_color="#1a9641", opacity=0.75))
        for xv, lbl, clr in [(20, "V.Low|Low", "#f46d43"), (40, "Low|Med", "#ffc107"), (60, "Med|High", "#77c35c"), (80, "High|V.High", "#1a9641")]:
            fig_dist.add_vline(x=xv, line_dash="dash", line_color=clr, annotation_text=lbl, annotation_position="top right")
        fig_dist.update_layout(xaxis_title="SHAPE Score", yaxis_title="Count",
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               height=280, margin=dict(l=10, r=10, t=20, b=10), showlegend=False)
        st.plotly_chart(fig_dist, width='stretch', key=f"{k}_dist_chart")

        st.markdown("#### Scored Results")
        def highlight_zone(row):
            s = row.get("SHAPE_Score", np.nan)
            if pd.isna(s): return [""] * len(row)
            if s >= 80: bg = "background-color: rgba(26,150,65,0.25)"
            elif s >= 60: bg = "background-color: rgba(119,195,92,0.25)"
            elif s >= 40: bg = "background-color: rgba(255,193,7,0.25)"
            elif s >= 20: bg = "background-color: rgba(244,109,67,0.25)"
            else: bg = "background-color: rgba(215,48,39,0.25)"
            return [bg] * len(row)
            
        display_cols = ["sample_id", "oc", "peer_group_taxon", "peer_group_texture", "PRISM_tmea"]
        if has_precip and "PRISM_ppt" in batch.columns:
            display_cols.append("PRISM_ppt")
        display_cols += ["SHAPE_Score", "Zone", "SOC_target_90th", "Gap_to_90th"]
        display_cols = [c for c in display_cols if c in batch.columns]
        st.dataframe(batch[display_cols].style.apply(highlight_zone, axis=1),
                    width='stretch', hide_index=True)

        if "lat" in batch.columns and "lon" in batch.columns:
            map_data = batch[["lat", "lon"]].dropna()
            if not map_data.empty:
                st.markdown("#### Site Map")
                st.map(map_data, zoom=4)

        st.divider()
        st.download_button("⬇️ Download Scored Results as CSV", data=batch.to_csv(index=False).encode("utf-8"),
                           file_name=f"SHAPE_{cfg['key']}_batch_results.csv", mime="text/csv",
                           width='stretch', key=f"{k}_results_dl")
    else:
        cols_needed = "sample_id, oc, peer_group_taxon, peer_group_texture, PRISM_tmea"
        if has_precip:
            cols_needed += ", PRISM_ppt"
        st.markdown(f"""
        <div class="info-box">
        Upload a CSV with columns: <code>{cols_needed}</code>.
        Optionally include <code>lat</code> and <code>lon</code> for map display.
        Or click <b>Try Demo Data</b> above to see the full batch workflow with synthetic samples
        covering every peer group and score zone for {region_name}.
        </div>
        """, unsafe_allow_html=True)


def render_how_to_use(region_name, cfg):
    has_precip = "precip" in cfg["predictors"]
    col_m1, col_m2 = st.columns([1, 1])
    
    with col_m1:
        st.markdown("### 📋 Step-by-Step Guide")
        st.markdown(f"""
        1. **Identify Your Soil Type**: Determine the classification group and texture profile of your target field using local soil survey data or soil cores.
        2. **Enter Soil Characteristics**: Input your site metrics into the **Site Inputs** card using the selection dropdowns.
        3. **Set Climate Values**: Adjust the mean temperature slider to map your environment. {"Also adjust the mean annual precipitation slider to account for regional rainfall distribution." if has_precip else "Precipitation modeling is handled natively in the background parameters."}
        4. **Provide Lab Diagnostics**: Input your verified laboratory **Soil Organic Carbon (SOC)** percentage directly into the numeric field.
        5. **Run the Carbon Calculator**: Open the lower configuration module and insert your field dimensions alongside management target vectors to generate tailored sequestration metrics.
        """)
        
        st.markdown("### 📊 Interpreting Your Score")
        st.markdown("""
        Scores are calculated relative to an environmental peer group under identical baseline conditions. A rating of 70 indicates the sample outranks 70% of comparable regional profiles.
        
        - 🔴 **0 to 20 — Very Low Function Zone**: Critical intervention needed. Soil is significantly underperforming its environmental threshold limits.
        - 🟠 **21 to 40 — Low Function Zone**: Active stabilization required to reverse degradation trends.
        - 🟡 **41 to 60 — Medium Function Zone**: Soil performance is near median benchmarks. Active adjustments can optimize retention trends.
        - 🟢 **61 to 80 — High Function Zone**: Active management techniques are driving strong performance.
        - 🌟 **81 to 100 — Very High Function Zone**: Elite structural health. Maximizing inherent soil performance thresholds.
        
        #### Graph Mechanics:
        - **Axes**: The horizontal axis maps raw **Soil Organic Carbon (%)**, while the vertical axis registers your final **SHAPE Score**.
        - **Shaded Band**: The green shaded margin defines the **95% posterior credible interval**, plotting our baseline structural model confidence margin.
        """)

    with col_m2:
        st.markdown("### 📦 Batch Scoring Guide")
        st.markdown("""
        To process multiple field logs simultaneously, compile an upload ledger matching these strict format requirements:
        
        - **Required Column Name Headers**: Your spreadsheet data fields must read exactly: `sample_id`, `oc`, `peer_group_taxon`, `peer_group_texture`, and `PRISM_tmea`. Ledgers tracking multi-variable regions must include a `PRISM_ppt` header column.
        - **Formatting Note**: The `peer_group_taxon` and `peer_group_texture` columns must be populated with their alphanumeric shorthand keys (e.g., *S2*, *T2*, *R1*) rather than full descriptive names.
        - **Quick Testing**: Click **Try Demo Data** inside the batch window to run our synthetic processing simulation and inspect file configurations.
        """)
        
        st.markdown("### 🗂️ Peer Group Reference")
        st.markdown("#### Taxonomic / Reference Soil Groups")
        for title, desc in cfg["pg_taxon_desc"].items():
            st.markdown(f"<div class='pg-card'><h4>{title}</h4><p>{desc}</p></div>", unsafe_allow_html=True)
        st.markdown("#### Texture Groups")
        for title, desc in cfg["pg_texture_desc"].items():
            st.markdown(f"<div class='pg-card'><h4>{title}</h4><p>{desc}</p></div>", unsafe_allow_html=True)


def render_region(region_name, cfg):
    mineral_df, hist_df = load_region_data(cfg)

    if mineral_df is None:
        st.error(f"⚠️ Parameter file '{cfg['csv']}' not found. Upload it to your deployment "
                 f"to activate scoring for {region_name}.")
        return

    # 1. Standard sub-tabs setup
    tab_single, tab_batch, tab_use = st.tabs(["🔬 Single Sample", "📊 Batch Scoring", "📖 How to Use"])

    # 2. Render Single Sample View
    with tab_single:
        render_single_sample(region_name, cfg, mineral_df, hist_df)

    # 3. Render Batch View
    with tab_batch:
        current_selection = st.session_state.get(f"{cfg['key']}_indicator_shared", "Soil Organic Carbon")
        st.markdown(f"**Selected Indicator:** `{current_selection}`")
        
        render_batch_scoring(region_name, cfg, mineral_df, hist_df)

    # 4. Render How to Use View
    with tab_use:
        render_how_to_use(region_name, cfg)

# ════════════════════════════════════════════════════════════════════
# 9. REGION TABS (TOP LEVEL)
# ════════════════════════════════════════════════════════════════════
region_tabs = st.tabs([f"{cfg['flag']} {name}" for name, cfg in REGIONS.items()])
for tab, (name, cfg) in zip(region_tabs, REGIONS.items()):
    with tab:
        render_region(name, cfg)

# ════════════════════════════════════════════════════════════════════
# FOOTER
# ════════════════════════════════════════════════════════════════════
st.divider()
st.markdown("""
<div style="text-align:center; color:gray; font-size:13px; padding: 8px 0 16px 0;">
  <strong>Mohkam Singh &amp; Marcio R. Nunes</strong> &nbsp;·&nbsp;
  Sustainable Management of Tropical Soils Lab &nbsp;·&nbsp;
  University of Florida — Department of Soil, Water, and Ecosystem Sciences<br>
  All rights reserved.
</div>
""", unsafe_allow_html=True)
