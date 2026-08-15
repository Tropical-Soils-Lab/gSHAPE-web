import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
from scipy.interpolate import PchipInterpolator
import plotly.graph_objects as go
import requests
from pathlib import Path

from soc_recommendations import load_soc_rules, get_management_questions, get_selected_answers, get_soc_recommendation, get_cropping_systems
# ── EXCEL RECOMMENDATION DATABASE SETUP ──
EXCEL_PATH = Path(__file__).parent / "gSHAPE_SOC_Recommendations.xlsx"

@st.cache_data(show_spinner=False)
def load_recommendation_database():
    try:
        return load_soc_rules(EXCEL_PATH)
    except Exception as e:
        st.error(f"Failed to load recommendation database: {e}")
        return None

soc_rules_df = load_recommendation_database()

def get_score_zone(score):
    """Translates the 0-100 score into a standardized quintile zone."""
    if score < 20: return "Very Low"
    elif score < 40: return "Low"
    elif score < 60: return "Medium"
    elif score < 80: return "High"
    else: return "Very High"

def render_excel_recommendation_engine(region_name, crop, score, key_prefix="rec"):
    """Dynamically builds input section directly from the Excel rules database filtered by region."""
    if soc_rules_df is None or soc_rules_df.empty:
        st.info("Recommendation database is currently unavailable.")
        return
        
   # ✨ 1. REGION FILTER (WITH FLORIDA OVERRIDE & INHERITANCE) ✨
    if "Region" not in soc_rules_df.columns:
        st.error("Missing 'Region' column in the Excel database.")
        return
        
    if region_name in ["Brazil", "Sub-Saharan Africa"]:
        # Brazil & Africa pull exclusively from Tropical rules
        region_rules_df = soc_rules_df[soc_rules_df["Region"] == "Tropical"].copy()
    else:
        # Florida pulls both Florida AND Tropical rules
        combined_df = soc_rules_df[soc_rules_df["Region"].isin(["Florida", "Tropical"])].copy()
        
        # Sort so 'Florida' comes before 'Tropical'
        combined_df["Region"] = pd.Categorical(
            combined_df["Region"], 
            categories=["Florida", "Tropical"], 
            ordered=True
        )
        combined_df = combined_df.sort_values("Region")
        
        # Deduplicate: Keeps the 'Florida' row if it exists; otherwise falls back to 'Tropical'
        dedup_keys = ["Code", "Management question", "Selected answer", "SOC level"]
        valid_keys = [col for col in dedup_keys if col in combined_df.columns]
        
        if valid_keys:
            region_rules_df = combined_df.drop_duplicates(subset=valid_keys, keep="first").copy()
        else:
            region_rules_df = combined_df
            
    if region_rules_df.empty:
        st.info(f"Management recommendations are currently being developed for {region_name}.")
        return

    zone = get_score_zone(score)
    st.markdown("## 📋 Management Recommendations")
    
    # ─── 2. DYNAMIC CROP TO SYSTEM ROUTING (EXCEL-DRIVEN) ───
    sys_df = region_rules_df[['Code', 'Cropping system', 'Crops']].drop_duplicates().dropna(subset=['Crops'])
    
    target_system_name = None
    target_code = None
    
    crop_clean = crop.lower()
    crop_tokens = [c.strip() for c in crop_clean.replace('/', ',').split(',')]
    
    import re # Needed for strict word boundary matching
    
    # PASS 1: Strict match (prevents "Pine" from matching "Pineapple")
    for _, row in sys_df.iterrows():
        excel_crops = str(row['Crops']).lower()
        excel_tokens = [c.strip() for c in excel_crops.replace('/', ',').split(',')]
        
        # Check for exact matches
        if set(crop_tokens).intersection(set(excel_tokens)):
            target_system_name = row['Cropping system']
            target_code = row['Code']
            break
            
        # Check for standalone words (matches "pine" in "pine, slash", ignores "pineapple")
        if any(re.search(rf'\b{re.escape(token)}\b', excel_crops) for token in crop_tokens):
            target_system_name = row['Cropping system']
            target_code = row['Code']
            break
            
    # PASS 2: Loose Fallback (Only runs if Pass 1 finds absolutely nothing)
    if not target_system_name:
        for _, row in sys_df.iterrows():
            excel_crops = str(row['Crops']).lower()
            if any(token in excel_crops for token in crop_tokens):
                target_system_name = row['Cropping system']
                target_code = row['Code']
                break
    
    # Default fallback if crop isn't in database at all
    if not target_system_name:
        target_system_name = sys_df['Cropping system'].iloc[0]
        target_code = sys_df['Code'].iloc[0]
        
    # ✨ Clean, farmer-friendly caption UI
    st.caption(f"Generating custom action plan for: **{crop}** | Current Status: **{zone}** (Score: {score:.1f}/100)")
    
    # ─── 3. Build the UI Dropdowns ───
    with st.expander("🌾 Management Practice Inputs", expanded=True):
        st.markdown("Select your current field practices below to generate your tailored action plan:")
        
        questions = get_management_questions(region_rules_df, target_code)
        
        if not questions:
            st.info("Management recommendations are currently being developed for this system.")
            return
            
        selections = {}
        
        # ✨ NEW: Wrap the dropdowns inside a form to prevent instant popping
        with st.form(key=f"{key_prefix}_form"):
            cols = st.columns(len(questions))
            
            for idx, q in enumerate(questions):
                answers = get_selected_answers(region_rules_df, target_code, q)
                with cols[idx % len(cols)]:
                    options = ["— Select Practice —"] + list(answers) + ["None of the above"]
                    selections[q] = st.selectbox(q, options)
                    
            # ✨ NEW: The button that triggers the generation
            submit_button = st.form_submit_button("Generate Custom Action Plan")
                
    # ✨ THE GATEKEEPER: Check button state and dropdown completion
    if not submit_button:
        # If they haven't clicked the button yet, stop here.
        return
        
    if any(ans == "— Select Practice —" for ans in selections.values()):
        # If they clicked the button but left something blank, warn them and stop.
        st.warning("💡 Please select an option for every management practice above, then click Generate.")
        return
    # ─── 4. Assemble the advice into the unified UI Box ───
    st.markdown("### Your Custom Agronomic Strategy")
    combined_bullets = ""
    
    # USING HEX ENCODING TO PREVENT COPY-PASTE STRIPPING
    li_open = "\x3cli style='margin-bottom: 12px;'\x3e"
    li_close = "\x3c/li\x3e"
    strong_open = "\x3cstrong\x3e"
    strong_close = "\x3c/strong\x3e"
    br_tag = "\x3cbr\x3e"
    em_open = "\x3cem\x3e"
    em_close = "\x3c/em\x3e"
    
    for q, ans in selections.items():
        # ✨ SKIPPER: Skip this category entirely if they select "None of the above"
        if ans == "None of the above":
            continue
            
        try:
            soc_result = get_soc_recommendation(
                rules_df=region_rules_df,
                code=target_code,
                management_question=q,
                selected_answer=ans,
                soc_level=zone
            )
            
            interp = str(soc_result.get("interpretation", "")).strip()
            rec = str(soc_result.get("recommendation", "")).strip()
            
            # Pandas sometimes reads empty Excel cells as the string "nan". Let's clear those out.
            if interp.lower() == "nan": interp = ""
            if rec.lower() == "nan": rec = ""
            
            # ✨ NEW: If both the interpretation and recommendation are completely blank, skip this bullet!
            if not interp and not rec:
                continue
            
            if interp and not interp.endswith('.'):
                interp += "."
            
            full_advice = f"{interp} {br_tag}{em_open}Action: {rec}{em_close}" if rec else interp
            combined_bullets += f"{li_open}{strong_open}{q} ({ans}):{strong_close} {full_advice}{li_close}"
            
        except Exception:
            # ✨ NEW: Do absolutely nothing if there is an error or a missing rule. Just skip it!
            pass
            
    # ─── 5. Color Box Rendering ───
    if score >= 80: bg_color, border_color = "rgba(26, 150, 65, 0.15)", "#1a9641"
    elif score >= 60: bg_color, border_color = "rgba(119, 195, 92, 0.15)", "#77c35c"
    elif score >= 40: bg_color, border_color = "rgba(255, 193, 7, 0.15)", "#ffc107"
    elif score >= 20: bg_color, border_color = "rgba(244, 109, 67, 0.15)", "#f46d43"
    else: bg_color, border_color = "rgba(215, 48, 39, 0.15)", "#d73027"
    
    div_open = f"\x3cdiv style='background-color: {bg_color}; border-left: 5px solid {border_color}; padding: 20px 24px 8px 24px; border-radius: 6px; margin-bottom: 14px; line-height: 1.6;'\x3e"
    div_close = "\x3c/div\x3e"
    ul_open = "\x3cul style='margin: 0; padding-left: 20px;'\x3e"
    ul_close = "\x3c/ul\x3e"
    
    if not combined_bullets:
         combined_bullets = f"{li_open}No exact matching criteria found. Focus on maximizing biomass and minimizing disturbance.{li_close}"
         
    custom_box = f"{div_open}\n{ul_open}\n{combined_bullets}\n{ul_close}\n{div_close}"
    st.markdown(custom_box, unsafe_allow_html=True)
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
/* Targets the master tab row container to stretch across the page full-width */
.stTabs [data-baseweb="tab-list"] {
    display: flex !important;
    width: 100% !important;
    gap: 0px !important; 
    margin-bottom: 20px;
    border-bottom: 2px solid var(--color-border-tertiary);
}

/* Forces each individual region tab item to grow equally and fill the screen space */
.stTabs [data-baseweb="tab"] {
    flex-grow: 1 !important;
    flex-basis: 0 !important;
    text-align: center !important;
    justify-content: center !important;
    font-size: 32px !important; 
    font-weight: 700 !important;
    padding: 20px 24px !important; 
    border-radius: 8px 8px 0px 0px !important;
    transition: all 0.2s ease;
    
    /* THE MAGIC BULLETPROOF FLAG LINE */
    font-family: inherit, "Noto Color Emoji" !important; 
}

/* Assign a specific green background tint to active region tab panels */
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    background-color: rgba(26, 150, 65, 0.20) !important;
    color: #1a9641 !important;
    border-bottom: 3px solid #1a9641 !important;
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
    "Sand (T1)": "T1", "Loamy Sand (T2)": "T2", "Sandy Loam (T3)": "T3",
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

# Expanded UI Maps (Make sure the integer matches your Excel code!)
SMAF_METHOD_MAP = {
    "Mehlich-1": 1, 
    "Mehlich-3": 2,
    "Bray":3,
    "Olsen": 4, 
    "Resin": 5,
    "Iron oxide strip":6
}

SMAF_WEATHERING_MAP = {
    "Calcareous": 1, 
    "Highly Weathered": 2,
    "Slightly Weathered": 3 
}

SMAF_TEXTURE_MAP = {
    "Sand / loamy sand / sandy loam (<8% clay)": 1, 
    "Sandy loam (>8% clay) / sandy clay loam / loam": 2, 
    "Silt loam / silt": 3,
    "Sandy clay / clay loam / silty clay loam / silty clay / clay (<60% clay)": 4, 
    "Clay (>60% clay)": 5          
}

SMAF_SLOPE_MAP = {
    "0–2% Level Slope": 1, 
    "2–5% Gentle Slope": 2, 
    "5–9% Moderate Slope": 3,
    "9–15% Strong Slope": 4,
    "15%+ Very Steep Slope": 5
    }
SMAF_MINERALOGY_MAP = {
    "Smectitic": 1,
    "Glassy": 2,
    "Other": 3
}
# ✨ NEW: Macroaggregate Stability Maps
SMAF_OM_MAP = {
    "Class 1 (Highest OM)": 1, 
    "Class 2 (Med-High OM)": 2, 
    "Class 3 (Med-Low OM)": 3, 
    "Class 4 (Lowest OM)": 4
}

SMAF_FE_MAP = {
    "Ultisols (High Iron-Oxide)": 1,
    "All Other Soil Orders": 2
}
# ✨ NEW: PMN Climate Map
SMAF_CLIMATE_MAP = {
    "Class 1 (Warm/Wet)": 1,
    "Class 2 (Warm/Dry)": 2,
    "Class 3 (Cool/Wet)": 3,
    "Class 4 (Cool/Dry)": 4
}
# ════════════════════════════════════════════════════════════════════
# 5. HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════════
# 5. HELPER FUNCTIONS
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

def run_smaf_bd_score(bd, texture_id, mineralogy_id=0):
    """Calculates the SMAF Bulk Density score using Weibull parameters."""
    if not SMAF_DATA: 
        st.error("Diagnostic: SMAF_DATA is totally empty.")
        return 0.0
    
    # --- AUTO-LOADER: Reads BD sheets and cleans headers ---
    if "bd_constants" not in SMAF_DATA:
        try:
            sh = pd.read_excel("SMAF_lookup.xlsx", sheet_name=None, dtype=str)
            
            def get_clean_df(sheet_name):
                if sheet_name not in sh: 
                    st.error(f"Diagnostic: Could not find '{sheet_name}' in Excel.")
                    return pd.DataFrame()
                df = sh[sheet_name].copy()
                df.columns = [str(c).strip() for c in df.columns]
                return df

            def num(x):
                try:
                    return float(x) if not pd.isna(x) else None
                except: 
                    return None

            # 1. Load Constants
            df_c = get_clean_df("bd_constants")
            K = {}
            if not df_c.empty:
                for _, r in df_c.iterrows():
                    v = num(r.get("value"))
                    p = r.get("param_name")
                    if pd.notna(p) and v is not None: K[str(p).strip()] = v
            SMAF_DATA["bd_constants"] = K

            # 2. Load Texture Factors
            df_t = get_clean_df("bd_texture_factors")
            tex_dict = {}
            if not df_t.empty:
                for _, r in df_t.iterrows():
                    tc = num(r.get("texture_code"))
                    if tc is not None:
                        tex_dict[int(tc)] = {
                            "range_lo": num(r.get("range_lo")), "range_hi": num(r.get("range_hi")),
                            "b1": num(r.get("b1")), "c1": num(r.get("c1")), "d1": num(r.get("d1"))
                        }
            SMAF_DATA["bd_texture_factors"] = tex_dict

            # 3. Load Mineralogy Factors
            df_m = get_clean_df("bd_mineralogy_factors")
            min_dict = {}
            if not df_m.empty:
                for _, r in df_m.iterrows():
                    mc = num(r.get("mineralogy_code"))
                    if mc is not None:
                        min_dict[int(mc)] = {
                            "range_shift": num(r.get("range_shift")), "delta_b": num(r.get("delta_b"))
                        }
            SMAF_DATA["bd_mineralogy_factors"] = min_dict
            
        except Exception as e:
            st.error(f"Diagnostic: Excel loading crashed with error: {e}")
            return 0.0

    # --- MATH EXECUTION ---
    K = SMAF_DATA.get("bd_constants", {})
    if not K: 
        st.error("Diagnostic: 'bd_constants' loaded, but is empty.")
        return 0.0
    
    a = K.get("a")
    t = SMAF_DATA["bd_texture_factors"].get(texture_id)
    if not t: 
        return 0.0
    
    if texture_id < 4:
        b, c, d = t["b1"], t["c1"], t["d1"]
    else:
        m = SMAF_DATA["bd_mineralogy_factors"].get(mineralogy_id, {"range_shift": 0.0, "delta_b": 0.0})
        r = t["range_lo"] + m["range_shift"]
        b = t["b1"] + m["delta_b"]
        c = K["c2_coef_a"] * np.exp(K["c2_coef_b"] * r)
        d = K["d2_coef_a"] + K["d2_coef_b"] * r

    if None in [a, b, c, d]:
        return 0.0

    try:
        y = a - b * np.exp(-c * (bd ** d))
        return float(max(K["score_min"], min(K["score_max"], y)) * 100.0)
    except Exception as e:
        return 0.0

# ----------------------------------------------------------------------
# SMAF ELECTRICAL CONDUCTIVITY (EC) BACKEND ENGINE
# ----------------------------------------------------------------------
def load_ec_data(smaf_data, path="SMAF_lookup.xlsx"):
    """Injects the 4 new EC sheets into the global SMAF_DATA dictionary safely."""
    if "ec_K" in smaf_data: return 
    
    import math
    import pandas as pd
    
    sh = pd.read_excel(path, sheet_name=None, dtype=str)
    def num(x):
        try:
            v = float(x)
            return None if math.isnan(v) else v
        except (ValueError, TypeError): return None

    ec_K = {}
    for _, r in sh["ec_constants"].iterrows():
        v = num(r["value"])
        if str(r["param_name"]) != "nan" and v is not None:
            ec_K[str(r["param_name"]).strip()] = v
            
    ec_crops = {}
    for _, r in sh["ec_crop_factors"].iterrows():
        cc = num(r["crop_code"])
        if cc is not None:
            ec_crops[int(cc)] = {"tsat": num(r["tsat"]), "dt": num(r["dt"])}
            
    ec_texture = {}
    for _, r in sh["ec_texture_factors"].iterrows():
        tc = num(r["texture_code"])
        if tc is not None:
            ec_texture[int(tc)] = num(r["f_txt"])

    smaf_data["ec_K"] = ec_K
    smaf_data["ec_crops"] = ec_crops
    smaf_data["ec_texture"] = ec_texture

def smaf_ec_slope_m(dt, K):
    den = K["m_den_a"] + K["m_den_b"] * dt - K["m_den_c"] * dt ** 2
    return (K["m_num_a"] - K["m_num_b"] * dt) / den

def smaf_ec_threshold(crop_id, method, texture_id, smaf_data, tsat=None):
    K = smaf_data["ec_K"]
    crop_info = smaf_data["ec_crops"].get(crop_id, {"tsat": 4.0, "dt": 0.5}) 
    
    if tsat is None:
        tsat = crop_info["tsat"]
        
    if method == 1: 
        return tsat
    return (tsat / K["dilution_factor"]) * smaf_data["ec_texture"].get(texture_id, 1.0)

def run_smaf_ec_score(ec_val, crop_id, method, texture_id, smaf_data, clamp=True):
    load_ec_data(smaf_data)
    
    K = smaf_data["ec_K"]
    crop_info = smaf_data["ec_crops"].get(crop_id, {"tsat": 4.0, "dt": 0.5}) 
    
    tsat = crop_info["tsat"]
    dt = crop_info["dt"]
    T = smaf_ec_threshold(crop_id, method, texture_id, smaf_data, tsat)

    brk = K["sat_break"] if method == 1 else K["ec11_break"]
    rise = K["sat_rise_slope"] if method == 1 else K["ec11_rise_slope"]

    if ec_val < brk:                                  
        y = rise * ec_val
    elif ec_val > T:                                  
        m = smaf_ec_slope_m(dt, K)
        y = m * ec_val + (K["plateau"] - m * T)
    else:                                             
        y = K["plateau"]

    if clamp:
        y = max(K["score_min"], min(K["score_max"], y))
        
    return y * 100.0
# ----------------------------------------------------------------------
# SMAF MACROAGGREGATE STABILITY (AGG) BACKEND ENGINE
# ----------------------------------------------------------------------
def load_agg_data(smaf_data, path="SMAF_lookup.xlsx"):
    """Injects the 4 new AGG sheets into the global SMAF_DATA dictionary safely."""
    if "agg_K" in smaf_data: return 
    
    import math, pandas as pd
    sh = pd.read_excel(path, sheet_name=None, dtype=str)
    
    def num(x):
        try: return float(x) if not pd.isna(x) else None
        except: return None

    agg_K, agg_om, agg_texture, agg_fe = {}, {}, {}, {}
    
    if "agg_constants" in sh:
        for _, r in sh["agg_constants"].iterrows():
            v = num(r.get("value"))
            p = str(r.get("param_name")).strip()
            if p != "nan" and v is not None: agg_K[p] = v
            
    if "agg_om_factors" in sh:
        for _, r in sh["agg_om_factors"].iterrows():
            oc = num(r.get("om_class"))
            if oc is not None: agg_om[int(oc)] = num(r.get("d1"))
            
    if "agg_texture_factors" in sh:
        for _, r in sh["agg_texture_factors"].iterrows():
            tc = num(r.get("texture_code"))
            if tc is not None: agg_texture[int(tc)] = num(r.get("d2"))
            
    if "agg_fe_factors" in sh:
        for _, r in sh["agg_fe_factors"].iterrows():
            fc = num(r.get("fe_class"))
            if fc is not None: agg_fe[int(fc)] = num(r.get("d3"))

    smaf_data["agg_K"] = agg_K
    smaf_data["agg_om"] = agg_om
    smaf_data["agg_texture"] = agg_texture
    smaf_data["agg_fe"] = agg_fe

def run_smaf_agg_score(agg_val, om_class, texture_id, fe_class, smaf_data, clamp=True):
    load_agg_data(smaf_data)
    K = smaf_data.get("agg_K", {})
    if not K: return 0.0
    
    d1 = smaf_data.get("agg_om", {}).get(om_class, 1.0)
    d2 = smaf_data.get("agg_texture", {}).get(texture_id, 1.0)
    d3 = smaf_data.get("agg_fe", {}).get(fe_class, 1.0)
    d = d1 * d2 * d3
    
    import math
    y = K.get("a", 0.0) + K.get("b", 0.0) * math.cos(K.get("c", 0.0) * agg_val - d)
    
    if agg_val >= K.get("plateau_x", 50.0) and y < K.get("plateau_score", 1.0):
        y = K.get("plateau_score", 1.0)
        
    if clamp:
        y = max(K.get("score_min", 0.0), min(K.get("score_max", 1.0), y))
        
    return y * 100.0
# ----------------------------------------------------------------------
# SMAF SODIUM ADSORPTION RATIO (SAR) BACKEND ENGINE
# ----------------------------------------------------------------------
def load_sar_data(smaf_data, path="SMAF_lookup.xlsx"):
    """Injects the 2 new SAR sheets into the global SMAF_DATA dictionary safely."""
    if "sar_K" in smaf_data: return 
    
    import math, pandas as pd
    sh = pd.read_excel(path, sheet_name=None, dtype=str)
    
    def num(x):
        try: return float(x) if not pd.isna(x) else None
        except: return None
        
    sar_K = {}
    if "sar_constants" in sh:
        for _, r in sh["sar_constants"].iterrows():
            v = num(r.get("value"))
            p = str(r.get("param_name")).strip()
            if p != "nan" and v is not None: sar_K[p] = v
            
    sar_branches = {}
    if "sar_branch_params" in sh:
        for _, r in sh["sar_branch_params"].iterrows():
            b = str(r.get("branch")).strip()
            form = str(r.get("form")).strip()
            if b != "nan" and form != "nan":
                sar_branches[b] = {
                    "form": form,
                    "coef": [num(r.get(k)) for k in "abcdefg"]
                }
                
    smaf_data["sar_K"] = sar_K
    smaf_data["sar_branches"] = sar_branches

def sar_branch_for(ec_sat, K):
    if ec_sat < K.get("ec_break_lo", 0.2): return "lo"
    if ec_sat > K.get("ec_break_hi", 0.55): return "hi"
    return "med"

def run_smaf_sar_score(sar_val, ec_val, method_id, texture_id, smaf_data, clamp=True):
    load_sar_data(smaf_data)
    # Ensure EC data is loaded too, because we need texture/dilution factors!
    load_ec_data(smaf_data) 
    
    K = smaf_data.get("sar_K", {})
    branches = smaf_data.get("sar_branches", {})
    if not K or not branches: return 0.0
    
    # 1. Convert measured EC to ECsat equivalent if 1:1 method was used
    if method_id == 1:
        ec_sat = ec_val
    else:
        f_txt = smaf_data.get("ec_texture", {}).get(texture_id, 1.0)
        dfact = smaf_data.get("ec_K", {}).get("dilution_factor", 1.77)
        ec_sat = (ec_val * dfact) / f_txt if f_txt else (ec_val * 1.77)
        
    # 2. Select the correct formula branch
    branch_key = sar_branch_for(ec_sat, K)
    b = branches.get(branch_key)
    if not b: return 0.0
    
    a, bb, c, d, e, f, g = b["coef"]
    
    # 3. Calculate Score
    if b["form"] == "reciprocal_power":
        # y = 1 / (a + b * SAR^c)
        denominator = a + bb * (sar_val ** c)
        y = 1.0 / denominator if denominator != 0 else 0.0
    elif b["form"] == "polynomial":
        y = 0.0
        for i, coef in enumerate([a, bb, c, d, e, f, g]):
            if coef is not None:
                y += coef * (sar_val ** i)
    else:
        y = 0.0
        
    if clamp:
        y = max(K.get("score_min", 0.0), min(K.get("score_max", 1.0), y))
        
    return y * 100.0

# ----------------------------------------------------------------------
# SMAF POTENTIALLY MINERALIZABLE NITROGEN (PMN) BACKEND ENGINE
# ----------------------------------------------------------------------
def load_pmn_data(smaf_data, path="SMAF_lookup.xlsx"):
    """Injects the 4 new PMN sheets into the global SMAF_DATA dictionary safely."""
    if "pmn_K" in smaf_data: return 
    
    import math, pandas as pd
    sh = pd.read_excel(path, sheet_name=None, dtype=str)
    
    def num(x):
        try: return float(x) if not pd.isna(x) else None
        except: return None
        
    pmn_K, pmn_om, pmn_texture, pmn_climate = {}, {}, {}, {}
    
    if "pmn_constants" in sh:
        for _, r in sh["pmn_constants"].iterrows():
            v = num(r.get("value"))
            p = str(r.get("param_name")).strip()
            if p != "nan" and v is not None: pmn_K[p] = v
            
    if "pmn_om_factors" in sh:
        for _, r in sh["pmn_om_factors"].iterrows():
            oc = num(r.get("om_class"))
            if oc is not None: pmn_om[int(oc)] = num(r.get("max_range"))
            
    if "pmn_texture_factors" in sh:
        for _, r in sh["pmn_texture_factors"].iterrows():
            tc = num(r.get("texture_code"))
            if tc is not None: pmn_texture[int(tc)] = num(r.get("c2"))
            
    if "pmn_climate_factors" in sh:
        for _, r in sh["pmn_climate_factors"].iterrows():
            cc = num(r.get("climate_class"))
            if cc is not None: pmn_climate[int(cc)] = num(r.get("c3"))
            
    smaf_data["pmn_K"] = pmn_K
    smaf_data["pmn_om"] = pmn_om
    smaf_data["pmn_texture"] = pmn_texture
    smaf_data["pmn_climate"] = pmn_climate

def om_c1(om_class, L):
    K, R = L.get("pmn_K", {}), L.get("pmn_om", {}).get(om_class, 1.0)
    return K.get("c1_coef_a", 0.0) + K.get("c1_coef_b", 0.0) * R + K.get("c1_coef_c", 0.0) * (R ** 2)

def rate_c(om_class, texture, climate, L):
    c1 = om_c1(om_class, L)
    c2 = L.get("pmn_texture", {}).get(texture, 1.0)
    c3 = L.get("pmn_climate", {}).get(climate, 1.0)
    return (c1 * c2) + (c1 * c2 * c3)

def run_smaf_pmn_score(pmn_val, om_class, texture, climate, smaf_data, clamp=True):
    load_pmn_data(smaf_data)
    K = smaf_data.get("pmn_K", {})
    if not K: return 0.0
    
    import math
    c = rate_c(om_class, texture, climate, smaf_data)
    
    try:
        y = K.get("a", 1.0) / (1.0 + K.get("b", 1.0) * math.exp(-c * pmn_val))
    except OverflowError:
        y = 0.0  # Failsafe if math.exp overflows on an extreme input
        
    if clamp:
        y = max(K.get("score_min", 0.0), min(K.get("score_max", 1.0), y))
        
    return y * 100.0

# ----------------------------------------------------------------------
# SMAF AVAILABLE WATER CAPACITY (AWC) BACKEND ENGINE
# ----------------------------------------------------------------------
def load_awc_data(smaf_data, path="SMAF_lookup.xlsx"):
    # ✨ FIX: Added length check to force a reload if it previously saved an empty dictionary!
    if "awc_K" in smaf_data and len(smaf_data.get("awc_K", {})) > 0: return 
    
    import math, pandas as pd
    sh = pd.read_excel(path, sheet_name=None, dtype=str)
    
    # ✨ FIX: Added back your original helper function to strip invisible spaces from Excel columns
    def clean_df(name):
        if name not in sh: return pd.DataFrame()
        df = sh[name].copy()
        df.columns = [str(c).strip() for c in df.columns]
        return df
        
    def num(x):
        try: return float(x) if not pd.isna(x) else None
        except: return None
        
    awc_K, awc_texture, awc_om = {}, {}, {}
    
    df_K = clean_df("awc_constants")
    if not df_K.empty:
        for _, r in df_K.iterrows():
            v = num(r.get("value"))
            p = str(r.get("param_name")).strip()
            if p != "nan" and v is not None: awc_K[p] = v
            
    df_tex = clean_df("awc_texture_params")
    if not df_tex.empty:
        for _, r in df_tex.iterrows():
            tc = num(r.get("texture_code"))
            if tc is not None:
                awc_texture[int(tc)] = {
                    "b1_arid": num(r.get("b1_arid")),
                    "d_humid": num(r.get("d_humid"))
                }
                
    df_om = clean_df("awc_om_factors")
    if not df_om.empty:
        for _, r in df_om.iterrows():
            oc = num(r.get("om_class"))
            if oc is not None: awc_om[int(oc)] = num(r.get("b2_arid"))
            
    smaf_data["awc_K"] = awc_K
    smaf_data["awc_texture"] = awc_texture
    smaf_data["awc_om"] = awc_om

def run_smaf_awc_score(awc_val, region, texture, om_class, smaf_data, clamp=True):
    load_awc_data(smaf_data)
    K = smaf_data.get("awc_K", {})
    
    if not K: return 0.0  
    
    import math
    if region == 1:  # Arid
        b1 = smaf_data.get("awc_texture", {}).get(texture, {}).get("b1_arid", 1.0)
        b2 = smaf_data.get("awc_om", {}).get(om_class, 1.0)
        b = b1 * b2
        try:
            xd = awc_val ** K.get("mmf_d", 1.0)
            y = (K.get("mmf_a", 1.0) * b + K.get("mmf_c", 1.0) * xd) / (b + xd)
        except ZeroDivisionError:
            y = 0.0
    else:  # Humid
        d = smaf_data.get("awc_texture", {}).get(texture, {}).get("d_humid", 0.0)
        y = K.get("sin_a", 0.0) + K.get("sin_b", 1.0) * math.cos(K.get("sin_c", 1.0) * awc_val + d)
        
    if clamp:
        y = max(K.get("score_min", 0.0), min(K.get("score_max", 1.0), y))
        
    return y * 100.0

# ----------------------------------------------------------------------
# SMAF WATER-FILLED PORE SPACE (WFPS) BACKEND ENGINE
# ----------------------------------------------------------------------
def load_wfps_data(smaf_data, path="SMAF_lookup.xlsx"):
    """Injects the 4 new WFPS sheets into the global SMAF_DATA dictionary safely."""
    if "wfps_K" in smaf_data and len(smaf_data.get("wfps_K", {})) > 0: return 
    
    import math, pandas as pd
    sh = pd.read_excel(path, sheet_name=None, dtype=str)
    
    def clean_df(name):
        if name not in sh: return pd.DataFrame()
        df = sh[name].copy()
        df.columns = [str(c).strip() for c in df.columns]
        return df
        
    def num(x):
        try: return float(x) if not pd.isna(x) else None
        except: return None
        
    wfps_K, wfps_env, wfps_texture = {}, {}, {}
    
    df_K = clean_df("wfps_constants")
    if not df_K.empty:
        for _, r in df_K.iterrows():
            v = num(r.get("value"))
            p = str(r.get("param_name")).strip()
            if p != "nan" and v is not None: wfps_K[p] = v
            
    df_env = clean_df("wfps_env_constants")
    if not df_env.empty:
        for _, r in df_env.iterrows():
            v = num(r.get("value"))
            p = str(r.get("param_name")).strip()
            if p != "nan" and v is not None: wfps_env[p] = v
            
    df_tex = clean_df("wfps_texture_params")
    if not df_tex.empty:
        for _, r in df_tex.iterrows():
            tc = num(r.get("texture_code"))
            if tc is not None:
                wfps_texture[int(tc)] = {"a": num(r.get("a")), "b": num(r.get("b")), "c": num(r.get("c"))}
                
    smaf_data["wfps_K"] = wfps_K
    smaf_data["wfps_env"] = wfps_env
    smaf_data["wfps_texture"] = wfps_texture

def get_wfps_frac(w_val, bd_val, smaf_data):
    """Calculates the WFPS fraction from lab water content and bulk density."""
    load_wfps_data(smaf_data)
    K = smaf_data.get("wfps_K", {})
    pdens = K.get("particle_density", 2.65)
    if not pdens or pdens == 0: return 0.0
    return (w_val * bd_val) / (1.0 - (bd_val / pdens))

def run_smaf_wfps_score(wfps_frac, texture, smaf_data, clamp=True):
    """Calculates both Bio and Env curves and returns a balanced 50/50 average."""
    load_wfps_data(smaf_data)
    K = smaf_data.get("wfps_K", {})
    E = smaf_data.get("wfps_env", {})
    T = smaf_data.get("wfps_texture", {}).get(texture, {})
    
    if not K or not E or not T: return {"bio": 0.0, "env": 0.0, "combined": 0.0}
    
    # Biological Curve
    bio_y = T.get("a", 0.0) + T.get("b", 0.0) * wfps_frac + T.get("c", 0.0) * (wfps_frac ** 2)
    if clamp: bio_y = max(K.get("score_min", 0.0), min(K.get("score_max", 1.0), bio_y))
        
    # Environmental Curve
    denom = E.get("a", 1.0) + E.get("b", 0.0) * (wfps_frac ** E.get("c", 1.0))
    env_y = 1.0 / denom if denom != 0 else 0.0
    if clamp: env_y = max(K.get("score_min", 0.0), min(K.get("score_max", 1.0), env_y))
        
    # 50/50 Balanced Management Goal
    combined_y = (0.5 * bio_y) + (0.5 * env_y)
    
    return {
        "bio": bio_y * 100.0,
        "env": env_y * 100.0,
        "combined": combined_y * 100.0
    }

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
    if f"{k}_sm_crop" not in st.session_state: 
        default_crop = MASTER_CROP_OPTIONS[0]
        for c in MASTER_CROP_OPTIONS:
            c_lower = c.lower()
            if region_name == "Florida" and "potato" in c_lower: 
                default_crop = c; break
            elif region_name == "Sub-Saharan Africa" and "teff" in c_lower: 
                default_crop = c; break
            elif region_name == "Brazil" and "cassava" in c_lower: 
                default_crop = c; break
        st.session_state[f"{k}_sm_crop"] = default_crop
        
    if f"{k}_oc" not in st.session_state: st.session_state[f"{k}_oc"] = 2.00
    if f"{k}_sm_p_input" not in st.session_state: st.session_state[f"{k}_sm_p_input"] = 25.0
    if f"{k}_ph_measured_input" not in st.session_state: st.session_state[f"{k}_ph_measured_input"] = 6.0
    
    # ✨ NEW: Default all these to the blank state instead of the first list item
    if f"{k}_sm_method" not in st.session_state: st.session_state[f"{k}_sm_method"] = "— Select —"
    if f"{k}_sm_weather" not in st.session_state: st.session_state[f"{k}_sm_weather"] = "— Select —"
    if f"{k}_sm_tex" not in st.session_state: st.session_state[f"{k}_sm_tex"] = "— Select —"
    if f"{k}_sm_slope" not in st.session_state: st.session_state[f"{k}_sm_slope"] = "— Select —"
    if f"{k}_ec_method" not in st.session_state: st.session_state[f"{k}_ec_method"] = "— Select —"
    if f"{k}_sm_om_class" not in st.session_state: st.session_state[f"{k}_sm_om_class"] = "— Select —"
    if f"{k}_sm_fe_class" not in st.session_state: st.session_state[f"{k}_sm_fe_class"] = "— Select —"
    if f"{k}_sm_climate_class" not in st.session_state: st.session_state[f"{k}_sm_climate_class"] = "— Select —"

   # ── MASTER SITE INPUTS (Always Visible) ──
    with st.expander("⚙️ Site & Management Inputs", expanded=True):
        c1, c2 = st.columns(2)
        
        with c1:
            taxon_label = TAXON_LABEL[region_name]
            if region_name == "Brazil":
                br_tax_system = st.selectbox("Taxonomy System", ["World Reference Base (WRB)", "Sistema Brasileiro de Classificação (SiBC)"], key=f"{k}_tax_system")
                if "SiBC" in br_tax_system:
                    active_taxon_display = cfg["taxon_display_sibc"]
                    taxon_label = "Ordem / Subordem (SiBC)"
                else:
                    active_taxon_display = cfg["taxon_display"]
            else:
                active_taxon_display = cfg["taxon_display"]

            selected_sub = st.selectbox(taxon_label, ["— Select —"] + active_taxon_display, format_func=lambda x: strip_code(x) if x != "— Select —" else x, key=f"{k}_sub")
            selected_tex = st.selectbox("Texture", ["— Select —"] + list(cfg["texture_map"].keys()), format_func=lambda x: strip_code(x) if x != "— Select —" else x, key=f"{k}_tex")
            
            # ✨ SMART UI: Auto-select Texture Profile ✨
            raw_tex = selected_tex.lower() if selected_tex else ""
            if "— select —" in raw_tex: derived_tex_id = 0
            elif "silt loam" in raw_tex or "silt" in raw_tex: derived_tex_id = 3
            elif "clay" in raw_tex and "loam" not in raw_tex and "sandy" not in raw_tex and "silty" not in raw_tex: derived_tex_id = 5 
            elif "clay" in raw_tex: derived_tex_id = 4 
            elif "loam" in raw_tex: derived_tex_id = 2 
            elif "sand" in raw_tex: derived_tex_id = 1 
            else: derived_tex_id = 2
            
            tex_options = ["— Select —"] + list(SMAF_TEXTURE_MAP.keys())
            if derived_tex_id != 0: st.session_state[f"{k}_sm_tex"] = tex_options[derived_tex_id]
            selected_sm_tex = st.selectbox("Texture Profile (Auto-Assigned)", tex_options, key=f"{k}_sm_tex")
            
            texture_id = SMAF_TEXTURE_MAP.get(selected_sm_tex, 0)
            selected_bd_min = None
            if texture_id >= 4:
                selected_bd_min = st.selectbox("Clay Mineralogy", ["— Select —"] + list(SMAF_MINERALOGY_MAP.keys()), key=f"{k}_bd_min")

            selected_sm_slope = st.selectbox("Landscape Slope Profile", ["— Select —"] + list(SMAF_SLOPE_MAP.keys()), key=f"{k}_sm_slope")
            chosen_crop = st.selectbox("Target Field Crop", MASTER_CROP_OPTIONS, key=f"{k}_sm_crop")
            
        with c2:
            selected_method = st.selectbox("P Extraction Method", ["— Select —"] + list(SMAF_METHOD_MAP.keys()), key=f"{k}_sm_method")
            selected_weath = st.selectbox("Soil Weathering Class", ["— Select —"] + list(SMAF_WEATHERING_MAP.keys()), key=f"{k}_sm_weather")
            ec_method_str = st.selectbox("EC Method", ["— Select —", "Saturated Paste (ECsat)", "1:1 Soil:Water (EC1:1)"], key=f"{k}_ec_method")
            
            use_geo = st.checkbox("Fetch climate from coordinates", key=f"{k}_geo")
            lat_in, lon_in = cfg["default_latlon"]
            if use_geo:
                lat_in = st.number_input("Latitude", value=cfg["default_latlon"][0], format="%.4f", key=f"{k}_lat")
                lon_in = st.number_input("Longitude", value=cfg["default_latlon"][1], format="%.4f", key=f"{k}_lon")
                if st.button("🌐 Fetch Climate Data", key=f"{k}_fetch"):
                    if not in_bounds(lat_in, lon_in, cfg):
                        st.error(f"📍 Outside area of interest for {region_name}.")
                    else:
                        res = fetch_climate(lat_in, lon_in, need_precip=has_precip)
                        if res:
                            if "temp" in res:
                                st.session_state[f"{k}_temp"] = float(np.clip(res["temp"], *cfg["temp_range"]))
                            if has_precip and "precip" in res:
                                st.session_state[f"{k}_precip"] = float(np.clip(res["precip"], *cfg["precip_range"]))
                            st.success(f"Climate fetched: {res.get('temp', '—'):.1f}°C")
                        else:
                            st.warning("Could not fetch climate data. Enter manually below.")
            
            target_temp = st.slider("Mean Annual Temperature (°C)", cfg["temp_range"][0], cfg["temp_range"][1], value=float(st.session_state.get(f"{k}_temp", cfg["temp_default"])), step=0.1, key=f"{k}_temp")
            if has_precip:
                target_precip = st.slider("Mean Annual Precipitation (mm)", cfg["precip_range"][0], cfg["precip_range"][1], value=float(st.session_state.get(f"{k}_precip", cfg["precip_default"])), step=10.0, key=f"{k}_precip")
            else:
                target_precip = None

            # ✨ SMART UI: Auto-select Iron Oxide ✨
            sub_lower = selected_sub.lower()
            # Florida = ult(isol), ox(isol) | WRB = acrisol, alisol, ferralsol | SiBC = argissolo, alissolo, latossolo
            high_fe_keywords = ["ult", "oxs", "oxisol", "acrisol", "alisol", "ferralsol", "argissolo", "alissolo", "latossolo"]
            is_high_fe = any(keyword in sub_lower for keyword in high_fe_keywords)
            
            derived_fe_id = 1 if is_high_fe else 2 if "— select —" not in sub_lower else 0
            
            fe_options = ["— Select —"] + list(SMAF_FE_MAP.keys())
            if derived_fe_id != 0: st.session_state[f"{k}_sm_fe_class"] = fe_options[derived_fe_id]
            selected_fe_class = st.selectbox("Iron-Oxide Class (Auto-Assigned)", fe_options, key=f"{k}_sm_fe_class")
            # ✨ SMART UI: Auto-select Climate Class ✨
            is_warm = target_temp >= 15.0
            is_wet = target_precip >= 600.0 if target_precip is not None else True
            derived_clim_id = 1 if (is_warm and is_wet) else 2 if (is_warm and not is_wet) else 3 if (not is_warm and is_wet) else 4
            clim_options = ["— Select —"] + list(SMAF_CLIMATE_MAP.keys())
            st.session_state[f"{k}_sm_climate_class"] = clim_options[derived_clim_id]
            selected_climate_class = st.selectbox("Climate Class (Auto-Assigned)", clim_options, key=f"{k}_sm_climate_class")
                
            if cfg["has_histosol"]:
                hist_toggle = st.checkbox("📌 This is an organic / Histosol soil (Muck, Peat)", key=f"{k}_hist")
            else:
                hist_toggle = False

    # ── MASTER LAB INPUTS (Always Visible) ──
    with st.expander("🧪 Laboratory Measurements", expanded=True):
        lc1, lc2, lc3 = st.columns(3)
        with lc1:
            oc_val = st.number_input("Measured SOC (%)", 0.01, 80.0, key=f"{k}_oc")
            agg_val = st.number_input("Agg. Stability (%)", min_value=0.0, max_value=100.0, value=40.0, step=1.0, key=f"{k}_agg_val")
            pmn_val = st.number_input("Measured PMN (mg/kg)", min_value=0.0, max_value=200.0, value=10.0, step=1.0, key=f"{k}_pmn_val")
            w_val = st.number_input("Gravimetric Water (g/g)", min_value=0.0, max_value=1.0, value=0.25, step=0.01, key=f"{k}_w_val")
        with lc2:
            p_val = st.number_input("Measured Extractable P (mg/kg)", 0.0, 500.0, key=f"{k}_sm_p_input")
            ec_val = st.number_input("Measured EC (dS/m)", min_value=0.0, max_value=20.0, value=1.5, step=0.1, key=f"{k}_ec_val")
            sar_val = st.number_input("Measured SAR", min_value=0.0, max_value=50.0, value=2.0, step=0.5, key=f"{k}_sar_val")
            
        with lc3:
            bd_val = st.number_input("Measured Bulk Density (g/cm³)", min_value=0.5, max_value=2.0, value=1.45, step=0.05, key=f"{k}_bd_input")
            ph_val = st.number_input("Measured Soil pH", 0.0, 14.0, value=6.0, key=f"{k}_ph_measured_input")
            # ✨ NEW: AWC Input Box added
            awc_val = st.number_input("Measured AWC (g/g)", min_value=0.0, max_value=0.5, value=0.15, step=0.01, key=f"{k}_awc_val")
            target_pct = st.slider("Benchmark Percentile (SOC)", 50, 99, 90, key=f"{k}_pct")

    # ✨ SILENT DERIVATION ENGINE FOR OM CLASS & AWC REGION ✨
    if oc_val >= 2.9: derived_om_id = 1
    elif oc_val >= 1.45: derived_om_id = 2
    elif oc_val >= 0.6: derived_om_id = 3
    else: derived_om_id = 4
    rev_om = {1: "Class 1 (Highest OM)", 2: "Class 2 (Med-High OM)", 3: "Class 3 (Med-Low OM)", 4: "Class 4 (Lowest OM)"}
    st.session_state[f"{k}_sm_om_class"] = rev_om[derived_om_id]
    
    # Auto-assign AWC Region: Humid (2) if MAP >= 600mm, Arid (1) if MAP < 600mm
    is_wet_for_awc = target_precip >= 600.0 if target_precip is not None else True
    st.session_state[f"{k}_awc_region"] = 2 if is_wet_for_awc else 1
    # ✨ THE MASTER SITE INPUTS GATEKEEPER ✨
    required_inputs = [selected_sub, selected_tex, selected_sm_tex, selected_sm_slope, selected_method, selected_weath, ec_method_str, selected_fe_class, selected_climate_class]
    if selected_bd_min is not None:
        required_inputs.append(selected_bd_min)
        
    if any(val == "— Select —" for val in required_inputs):
        st.info("💡 Please complete all dropdown selections in the **Site Inputs** above to unlock your soil health scores and recommendations.")
        return
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

    # ── COMPREHENSIVE SOIL HEALTH SUMMARY ──
    st.markdown("### 📊 Comprehensive Soil Health Overview")
    
    # 1. Silently calculate all indicator scores for the summary chart
    # SOC Score (Already calculated globally)
    score_soc = compute_score(oc_val, lp_mean, sigma_val)
    
    # Phosphorus Score
    crop_id_sum = SMAF_DATA["crop_ui_map"].get(st.session_state[f"{k}_sm_crop"].lower(), 0)
    method_id_sum = SMAF_METHOD_MAP[st.session_state[f"{k}_sm_method"]]
    weather_id_sum = SMAF_WEATHERING_MAP[st.session_state[f"{k}_sm_weather"]]
    texture_id_sum = SMAF_TEXTURE_MAP[st.session_state[f"{k}_sm_tex"]]
    slope_id_sum = SMAF_SLOPE_MAP[st.session_state[f"{k}_sm_slope"]]
    score_p_sum = run_smaf_p_score(p_val, crop_id_sum, method_id_sum, weather_id_sum, texture_id_sum, slope_id_sum, oc_val)
    
    # Bulk Density Score
    mineral_str = st.session_state.get(f"{k}_bd_min", "— Select —")
    mineralogy_id_sum = SMAF_MINERALOGY_MAP.get(mineral_str, 0) if mineral_str != "— Select —" else 0
    raw_score_bd_sum = run_smaf_bd_score(bd_val, texture_id_sum, mineralogy_id_sum)

    # Electrical Conductivity Score 
    ec_method_id_sum = 1 if "Saturated Paste" in ec_method_str else 2
    raw_score_ec_sum = run_smaf_ec_score(ec_val, crop_id_sum, ec_method_id_sum, texture_id_sum, SMAF_DATA)

    # Macroaggregate Stability Score (Silent Calculation)
    om_string_sum = st.session_state.get(f"{k}_sm_om_class", "Class 2 (Med-High OM)")
    om_id_sum = SMAF_OM_MAP.get(om_string_sum, 2)
    
    fe_id_sum = SMAF_FE_MAP.get(selected_fe_class, 2)
    raw_score_agg_sum = run_smaf_agg_score(agg_val, om_id_sum, texture_id_sum, fe_id_sum, SMAF_DATA)
    # Sodium Adsorption Ratio (SAR) Score (Silent Calculation)
    raw_score_sar_sum = run_smaf_sar_score(sar_val, ec_val, ec_method_id_sum, texture_id_sum, SMAF_DATA)

    # Potentially Mineralizable Nitrogen (PMN) Score (Silent Calculation)
    climate_id_sum = SMAF_CLIMATE_MAP.get(selected_climate_class, 3) if selected_climate_class != "— Select —" else 3
    raw_score_pmn_sum = run_smaf_pmn_score(pmn_val, om_id_sum, texture_id_sum, climate_id_sum, SMAF_DATA)

    # Available Water Capacity (AWC) Score (Silent Calculation)
    awc_region_sum = st.session_state.get(f"{k}_awc_region", 2)
    raw_score_awc_sum = run_smaf_awc_score(awc_val, awc_region_sum, texture_id_sum, om_id_sum, SMAF_DATA)

    # Water-Filled Pore Space (WFPS) Score (Silent Calculation)
    wfps_frac_sum = get_wfps_frac(w_val, bd_val, SMAF_DATA)
    wfps_scores_sum = run_smaf_wfps_score(wfps_frac_sum, texture_id_sum, SMAF_DATA)
    raw_score_wfps_sum = wfps_scores_sum["combined"]
    
    # pH Score
    crop_selected_name_sum = st.session_state[f"{k}_sm_crop"]
    ph_benchmarks_sum = SMAF_DATA.get("ph_benchmarks", {}) if SMAF_DATA else {}
    ph_benchmarks_lower_sum = {key.lower(): val for key, val in ph_benchmarks_sum.items()}
    benchmarks_sum = ph_benchmarks_lower_sum.get(crop_selected_name_sum.lower())
    if benchmarks_sum:
        raw_score_ph_sum = float(100.0 * np.exp(-((ph_val - benchmarks_sum["opt"]) / (2.0 * benchmarks_sum["sigma"])) ** 2))
    else:
        raw_score_ph_sum = 0.0
        
    # =========================================================================
    # Calculate the Category Averages and the Overall Score
    def safe_float(val):
        try:
            return float(val) if val is not None else 0.0
        except (ValueError, TypeError):
            return 0.0

    # Biological = Average of SOC and PMN
    score_bio = (safe_float(score_soc) + safe_float(raw_score_pmn_sum)) / 2.0
    
    # Physical = Average of BD, AGG, AWC, and WFPS (Divide by 4.0!)
    score_phys = (safe_float(raw_score_bd_sum) + safe_float(raw_score_agg_sum) + safe_float(raw_score_awc_sum) + safe_float(raw_score_wfps_sum)) / 4.0
    
    # Chemical = Average of pH, P, EC, and SAR (Divide by 4.0!)
    score_chem = (safe_float(raw_score_ph_sum) + safe_float(score_p_sum) + safe_float(raw_score_ec_sum) + safe_float(raw_score_sar_sum)) / 4.0
    
    score_overall = (score_phys + score_chem + score_bio) / 3.0
    # =========================================================================
    # =========================================================================

    # 2. Build the Summary Bar Chart
    summary_scores = [int(round(score_phys)), int(round(score_chem)), int(round(score_bio)), int(round(score_overall))]
    summary_labels = ["Physical", "Chemical", "Biological", "<b>OVERALL</b>"]
    summary_colors = [score_color(s) for s in summary_scores]
    
    # ✨ Swapped back to horizontal text formatting with the pipe symbol
    summary_text = [f"{s}/100  |  {score_label(s)}" for s in summary_scores]
    
    # ✨ Adjusted the text position threshold back to 25 to account for horizontal space
    text_positions = ["inside" if s >= 25 else "outside" for s in summary_scores]

    fig_summary = go.Figure(go.Bar(
        x=summary_scores, # ✨ Swapped x and y back
        y=summary_labels,
        orientation='h',  # ✨ Added horizontal orientation back
        marker_color=summary_colors,
        text=summary_text,
        textposition=text_positions, 
        insidetextanchor='middle',
        textfont=dict(color='white', size=15, family="Arial Black")
    ))

    fig_summary.update_layout(
        # ✨ NEW: Added fixedrange=True to both axes to disable pinch-to-zoom and panning
        xaxis=dict(range=[0, 100], fixedrange=True, title="SHAPE Score", gridcolor="rgba(150,150,150,0.1)"), 
        yaxis=dict(autorange="reversed", fixedrange=True), 
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=320, 
        margin=dict(l=10, r=20, t=10, b=10)
    )
    
    # ✨ NEW: Added config={'displayModeBar': False} to hide the floating Plotly toolbar
    st.plotly_chart(
        fig_summary, 
        use_container_width=True, 
        key=f"{k}_summary_chart",
        config={'displayModeBar': False}
    )

    # =========================================================================
    # ✨ ✨ NATIVE STREAMLIT SOIL HEALTH CONSTRAINTS DIAGNOSTIC ✨ ✨
    # =========================================================================
    st.markdown("### 📋 Soil Health Constraint Diagnostic")
    st.markdown("Address these critical functional constraints to unlock full soil and crop potential:")
    
    # 1. Define the constraints dictionary directly inside the app
    CONSTRAINTS = {
        "Physical": {
            "Medium": "Root penetration; Water transmission",
            "Low": "Root penetration; Gas exchange; Water Infiltration; Erosion and runoff",
            "VeryLow": "Root penetration; Water transmission; Gas exchange; Infiltration; Water retention; Solute transport; Seedbed formation",
        },
        "Chemical": {
            "Medium": "Nutrient supply; Nutrient Solubilization",
            "Low": "Nutrient supply; Nutrient Solubilization; Ion exchange and retention; Rhizosphere habitat",
            "VeryLow": "Nutrient supply; Nutrient solubility; Ion exchange and retention; Rhizosphere habitat; pH buffering; Ionic toxicity regulation; Nitrogen transformation",
        },
        "SOC": {
            "Medium": "Nutrient mineralization; Microbial habitat",
            "Low": "Nutrient mineralization; Microbial habitat; Aggregate Formation; Water Retention",
            "VeryLow": "Nutrient mineralization; Microbial habitat; Aggregate Formation; Water Retention; Infiltration; Structural stability; Buffering capacity",
        }
    }

    # 2. Build the dataset based on current scores
    diag_rows = []
    
    # Loop through the variables already calculated for the chart above
    for pillar, s_val in [("Physical", score_phys), ("Chemical", score_chem), ("SOC", score_bio)]:
        score_int = int(round(s_val))
        if score_int < 20:
            diag_rows.append({"Pillar": pillar, "Score": score_int, "Assessment": "🔴 Very Low", "Critical Soil Functions Affected": CONSTRAINTS[pillar]["VeryLow"]})
        elif score_int < 40:
            diag_rows.append({"Pillar": pillar, "Score": score_int, "Assessment": "🔴 Low", "Critical Soil Functions Affected": CONSTRAINTS[pillar]["Low"]})
        elif score_int < 60:
            diag_rows.append({"Pillar": pillar, "Score": score_int, "Assessment": "🟠 Medium", "Critical Soil Functions Affected": CONSTRAINTS[pillar]["Medium"]})

    # 3. Render natively using Streamlit
    if len(diag_rows) == 0:
        st.success("Congratulations! All core soil health pillars scored High (>= 60), indicating fully functional soil systems that are unrestricted by major soil function constraints.")
    else:
        # Convert to Pandas DataFrame for clean rendering
        df_diag = pd.DataFrame(diag_rows)
        
        # Use st.table() so the text wraps nicely on multiple lines
        st.table(df_diag)
        
    st.divider()
    # =========================================================================
    
   # ── INDICATOR SELECTION ──
    indicator_options = ["Soil Organic Carbon", "Soil Phosphorus", "pH", "Bulk Density", "Electrical Conductivity", "Macroaggregate Stability", "Sodium Adsorption Ratio", "Potentially Mineralizable Nitrogen", "Available Water Capacity", "Water-Filled Pore Space"]
    chosen_indicator = st.selectbox(
        "Soil Health Indicators:",
        indicator_options,
        key=f"{cfg['key']}_indicator_shared"
    )
# ALWAYS calculate the SOC score in the background so the Recommendation Engine 
# and Carbon Calculator at the bottom of the page don't crash when switching tabs!
    score = compute_score(oc_val, lp_mean, sigma_val)
    tgt_oc = percentile_to_oc(target_pct, lp_mean, sigma_val)

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
                mode="gauge+number", value=int(round(score_p)),
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
            fig_p.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="#1F4E5F", width=3), name="Score Curve", hovertemplate="P: %{x:.1f}<br>Score: %{y:.2f}<extra></extra>"))
            fig_p.add_trace(go.Scatter(x=[p_val], y=[score_p / 100.0], mode="markers", marker=dict(color=color_p, size=14, line=dict(color="white", width=2)), name="Your Site"))
            
            fig_p.update_layout(
                xaxis_title="Extractable P (mg/kg)", yaxis_title="Performance Rating",
                yaxis=dict(range=[0, 1.05], tickformat=".2f"), xaxis=dict(range=[0, 300]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=400, margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig_p, width='stretch', key=f"{k}_p_curve_plot")

# ── 5-TIER PHOSPHORUS RECOMMENDATION ENGINE ──
            st.markdown("### 📋 Agronomic Recommendations")
            
            # 1. Assign the 5-tier logic
            if score_p >= 80:
                p_level = "Very High"
                p_rec = "Your soil phosphorus level is optimal, fully meeting crop demand. Additional phosphorus application is generally unnecessary and should be avoided to minimize risk of environmental runoff."
            elif score_p >= 60:
                p_level = "High"
                p_rec = "Your soil phosphorus level is adequate for healthy crop production. Routine soil testing and maintenance-level applications (matching crop removal rates) are recommended to maintain fertility."
            elif score_p >= 40:
                p_level = "Medium"
                p_rec = "Your soil phosphorus level is moderate and may occasionally limit yield during high-demand growth stages. Consider a modest application or targeted starter fertilizer. We suggest consulting a local agronomist to align application rates with crop removal."
            elif score_p >= 20:
                p_level = "Low"
                p_rec = "Your soil phosphorus level is low and likely restricting early root development and crop yield. A corrective application of phosphorus fertilizer or organic amendments is recommended. Please consult a certified agronomist for a soil-test based fertilizer prescription."
            else:
                p_level = "Very Low"
                p_rec = "Your soil phosphorus level is severely deficient, presenting a major constraint on crop growth. A structured nutrient management plan is recommended. Please consult with a certified agronomist or extension specialist to establish a safe, soil-test based application strategy."

            # 2. Render the recommendation box
            st.info(f"**Score Tier: {p_level}**\n\n{p_rec}")

    elif chosen_indicator == "Bulk Density":
        
        # 1. Grab inputs from the Master Panel via session_state
        texture_id = SMAF_TEXTURE_MAP[st.session_state[f"{k}_sm_tex"]]
        mineralogy_id = 0
        if texture_id >= 4:
            mineral_string = st.session_state.get(f"{k}_bd_min", list(SMAF_MINERALOGY_MAP.keys())[0])
            mineralogy_id = SMAF_MINERALOGY_MAP[mineral_string]
            
        bd_val = st.session_state[f"{k}_bd_input"]
        
        # 2. Score Calculation
        raw_score_bd = run_smaf_bd_score(bd_val, texture_id, mineralogy_id)
        
        # Shield against empty inputs! Converts 'None' to 0.0 before coloring.
        try:
            score_bd = float(raw_score_bd) if raw_score_bd is not None else 0.0
        except (ValueError, TypeError):
            score_bd = 0.0
            
        color_bd = score_color(score_bd)
        label_bd = score_label(score_bd)
        
        with col_l:
            gauge_title = f"<b style='font-size:17px'>{label_bd}</b><br><span style='font-size:11px;color:gray'>BD {bd_val} g/cm³</span>"
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=int(round(score_bd)),
                title={"text": gauge_title, "font": {"size": 13}},
                number={"suffix": "/100", "font": {"size": 38, "color": color_bd}},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "gray"},
                    "bar": {"color": color_bd, "thickness": 0.28},
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
            st.plotly_chart(fig_gauge, use_container_width=True, key=f"{k}_bd_gauge")

        with col_r:
            st.markdown("#### Scoring Curve")
            
            xs = np.linspace(0.6, 1.8, 400)
            ys = [run_smaf_bd_score(x, texture_id, mineralogy_id) for x in xs]
            
            fig_bd = go.Figure()
            fig_bd.add_trace(go.Scatter(x=xs, y=np.array(ys) / 100.0, mode="lines", line=dict(color="#5A3E85", width=3), name=" Score Curve", hovertemplate="BD: %{x:.2f} g/cm³<br>Score: %{y:.1%}<extra></extra>"))
            fig_bd.add_trace(go.Scatter(x=[bd_val], y=[score_bd / 100.0], mode="markers", marker=dict(color=color_bd, size=14, line=dict(color="white", width=2)), name="Your Soil"))
            
            fig_bd.update_layout(
                xaxis_title="Bulk Density (g/cm³)", yaxis_title="SHAPE Score",
                yaxis=dict(range=[0, 1.05], tickformat=".0%"), xaxis=dict(range=[0.6, 1.8]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=400, margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig_bd, width='stretch', key=f"{k}_bd_curve_plot")
            
    # ── 5-TIER BULK DENSITY RECOMMENDATION ENGINE ──
            st.markdown("### 📋 Agronomic Recommendations")
            
            # 1. Assign the 5-tier logic
            if score >= 80:
                bd_level = "Very High"
                bd_rec = "Your soil bulk density is optimal, providing excellent aeration, water infiltration, and unrestricted root penetration. Maintain current soil management and minimal disturbance practices."
            elif score >= 60:
                bd_level = "High"
                bd_rec = "Your soil bulk density is adequate and generally supportive of healthy root growth. Monitor heavy field traffic and maintain organic matter inputs to prevent future compaction."
            elif score >= 40:
                bd_level = "Medium"
                bd_rec = "Your soil shows moderate signs of compaction, which may begin to limit root expansion and water infiltration. Consider integrating practices like cover cropping (e.g., deep-rooted species like tillage radish) or reducing field traffic when the soil is wet to gradually improve porosity."
            elif score >= 20:
                bd_level = "Low"
                bd_rec = "Your soil bulk density indicates significant compaction that is likely restricting root development and field drainage. We suggest implementing compaction-alleviation strategies, such as adding organic amendments or utilizing deep-rooted cover crops. Consult a local agronomist to evaluate the exact depth of the compaction layer."
            else:
                bd_level = "Very Low"
                bd_rec = "Your soil bulk density is severely restricting root growth, water movement, and biological activity. Mechanical interventions like subsoiling or deep ripping, combined with long-term organic matter building, may be necessary. Please consult with a certified agronomist to properly diagnose the hardpan depth and determine the safest intervention strategy."

            # 2. Render the recommendation box
            st.info(f"**Score Tier: {bd_level}**\n\n{bd_rec}")
    elif chosen_indicator == "Electrical Conductivity":
        # 1. Grab Global Variables
        ec_method_id = 1 if "Saturated Paste" in ec_method_str else 2
        crop_name = st.session_state[f"{k}_sm_crop"]
        crop_id = SMAF_DATA["crop_ui_map"].get(crop_name.lower(), 0)
        texture_id = SMAF_TEXTURE_MAP[st.session_state[f"{k}_sm_tex"]]
        
        # 2. Calculate Score securely
        raw_score_ec = run_smaf_ec_score(ec_val, crop_id, ec_method_id, texture_id, SMAF_DATA)
        try:
            score_ec = float(raw_score_ec) if raw_score_ec is not None else 0.0
        except (ValueError, TypeError):
            score_ec = 0.0
            
        ec_color = score_color(score_ec)
        ec_label = score_label(score_ec)
        
        # 3. Create the 1:2 Column Layout
        col_l, col_r = st.columns([1, 2])
        
        with col_l:
            gauge_title = f"<b style='font-size:17px'>{ec_label}</b><br><span style='font-size:11px;color:gray'>{crop_name} - EC {ec_val}</span>"
            fig_ec_gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=int(round(score_ec)),
                title={"text": gauge_title, "font": {"size": 13}},
                number={"suffix": "/100", "font": {"size": 38, "color": ec_color}},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "gray", "tickvals": [0, 20, 40, 60, 80, 100]},
                    "bar": {"color": ec_color, "thickness": 0.28},
                    "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
                    "steps": [
                        {"range": [0, 20], "color": "rgba(215,48,39,0.35)"},
                        {"range": [20, 40], "color": "rgba(244,109,67,0.35)"},
                        {"range": [40, 60], "color": "rgba(255,193,7,0.35)"},
                        {"range": [60, 80], "color": "rgba(119,195,92,0.35)"},
                        {"range": [80, 100], "color": "rgba(26,150,65,0.35)"}
                    ],
                    "threshold": {"line": {"color": ec_color, "width": 5}, "thickness": 0.8, "value": score_ec}
                }
            ))
            fig_ec_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=260, margin=dict(l=20, r=20, t=80, b=10))
            st.plotly_chart(fig_ec_gauge, use_container_width=True, key=f"{k}_ec_gauge_plot")
            
            # Variance/Threshold Info
            threshold_val = smaf_ec_threshold(crop_id, ec_method_id, texture_id, SMAF_DATA)
            st.markdown("##### EC Threshold")
            st.markdown(f"**{threshold_val:.2f} dS/m**")
            
            if ec_val > threshold_val:
                st.markdown(f"<span style='color: #d7191c; font-size: 14px; font-weight: bold;'>↑ Exceeds Tolerance by {ec_val - threshold_val:.2f}</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"<span style='color: #1a9641; font-size: 14px; font-weight: bold;'>✓ Within Tolerance</span>", unsafe_allow_html=True)

        with col_r:
            st.markdown("#### Scoring Curve")
            hi_range = 9.0 if ec_method_id == 1 else 6.0
            xs = np.linspace(0, hi_range, 300)
            ys = [run_smaf_ec_score(x, crop_id, ec_method_id, texture_id, SMAF_DATA) for x in xs]
            
            fig_ec = go.Figure()
            fig_ec.add_trace(go.Scatter(
                x=xs, y=np.array(ys) / 100.0, mode="lines", 
                line=dict(color="#B5651D", width=3), 
                name="Score Curve", hovertemplate="EC: %{x:.2f} dS/m<br>Score: %{y:.0%}<extra></extra>"
            ))
            fig_ec.add_trace(go.Scatter(
                x=[ec_val], y=[score_ec / 100.0], mode="markers", 
                marker=dict(color=ec_color, size=14, line=dict(color="white", width=2)), 
                name="Your Soil"
            ))
            fig_ec.update_layout(
                xaxis_title=f"{'ECsat' if ec_method_id == 1 else 'EC 1:1'} (dS/m)", 
                yaxis_title="SHAPE Score",
                yaxis=dict(range=[0, 1.05], tickformat=".0%"), xaxis=dict(range=[0, hi_range]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", 
                height=400, margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig_ec, width='stretch', key=f"{k}_ec_curve_plot")

        # ── 5-TIER EC RECOMMENDATION ENGINE ──
        st.markdown("### 📋 Agronomic Recommendations")
        if ec_val > threshold_val:
            issue_type = "salinity"
            amendment = "leaching fractions, improving drainage, or applying gypsum to displace sodium"
        else:
            issue_type = "low solubility"
            amendment = "reviewing your fertilizer program and organic matter inputs to ensure adequate nutrient availability"

        if score_ec >= 80:
            ec_level = "Very High"
            ec_rec = "Your soil electrical conductivity is optimal. Soluble salts are at an ideal level to support active microbial life and crop nutrient uptake without causing osmotic stress."
        elif score_ec >= 60:
            ec_level = "High"
            ec_rec = "Your soil EC is adequate for healthy crop production. Continue routine monitoring, especially if irrigating with well water, to prevent long-term salt accumulation."
        elif score_ec >= 40:
            ec_level = "Medium"
            ec_rec = f"Your soil EC is moderately limiting crop potential due to {issue_type}. Consider {amendment}. We suggest consulting a local agronomist to adjust your management plan."
        elif score_ec >= 20:
            ec_level = "Low"
            ec_rec = f"Your soil EC indicates significant {issue_type} constraints. Osmotic stress or poor nutrient availability is likely reducing yields. A targeted intervention plan involving {amendment} is recommended."
        else:
            ec_level = "Very Low"
            ec_rec = f"Critical limitation. Your soil EC is severely restricting crop growth and soil biological function due to extreme {issue_type}. Immediate consultation with a certified agronomist is strongly advised to establish a safe remediation strategy."
        st.info(f"**Score Tier: {ec_level}**\n\n{ec_rec}")

    elif chosen_indicator == "Macroaggregate Stability":
        # 1. Grab Global Variables
        texture_id = SMAF_TEXTURE_MAP[st.session_state[f"{k}_sm_tex"]]
        om_id = SMAF_OM_MAP.get(st.session_state[f"{k}_sm_om_class"], 2)
        fe_id = SMAF_FE_MAP.get(st.session_state[f"{k}_sm_fe_class"], 2)
        
        # 2. Calculate Score securely
        raw_score_agg = run_smaf_agg_score(agg_val, om_id, texture_id, fe_id, SMAF_DATA)
        try:
            score_agg = float(raw_score_agg) if raw_score_agg is not None else 0.0
        except (ValueError, TypeError):
            score_agg = 0.0
            
        agg_color = score_color(score_agg)
        agg_label = score_label(score_agg)
        
        # 3. Create the 1:2 Column Layout
        col_l, col_r = st.columns([1, 2])
        
        with col_l:
            gauge_title = f"<b style='font-size:17px'>{agg_label}</b><br><span style='font-size:11px;color:gray'>Agg. Stability {agg_val}%</span>"
            fig_agg_gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=int(round(score_agg)),
                title={"text": gauge_title, "font": {"size": 13}},
                number={"suffix": "/100", "font": {"size": 38, "color": agg_color}},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "gray", "tickvals": [0, 20, 40, 60, 80, 100]},
                    "bar": {"color": agg_color, "thickness": 0.28},
                    "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
                    "steps": [
                        {"range": [0, 20], "color": "rgba(215,48,39,0.35)"},
                        {"range": [20, 40], "color": "rgba(244,109,67,0.35)"},
                        {"range": [40, 60], "color": "rgba(255,193,7,0.35)"},
                        {"range": [60, 80], "color": "rgba(119,195,92,0.35)"},
                        {"range": [80, 100], "color": "rgba(26,150,65,0.35)"}
                    ],
                    "threshold": {"line": {"color": agg_color, "width": 5}, "thickness": 0.8, "value": score_agg}
                }
            ))
            fig_agg_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=260, margin=dict(l=20, r=20, t=80, b=10))
            st.plotly_chart(fig_agg_gauge, use_container_width=True, key=f"{k}_agg_gauge_plot")
            
        with col_r:
            st.markdown("#### Scoring Curve")
            grid = np.array([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 80, 100.0])
            gy = np.array([run_smaf_agg_score(x, om_id, texture_id, fe_id, SMAF_DATA) for x in grid])
            spl = PchipInterpolator(grid, gy / 100.0)
            xs = np.linspace(0, 100, 300)
            ys = np.clip(spl(xs), 0.0, 1.0)
            
            fig_agg = go.Figure()
            fig_agg.add_trace(go.Scatter(
                x=xs, y=ys, mode="lines", 
                line=dict(color="#7A5C3E", width=3), 
                name="Score Curve", hovertemplate="Stability: %{x:.1f}%<br>Score: %{y:.0%}<extra></extra>"
            ))
            fig_agg.add_trace(go.Scatter(
                x=[agg_val], y=[score_agg / 100.0], mode="markers", 
                marker=dict(color=agg_color, size=14, line=dict(color="white", width=2)), 
                name="Your Soil"
            ))
            fig_agg.update_layout(
                xaxis_title="Macroaggregate Stability (%)", 
                yaxis_title="SHAPE Score",
                yaxis=dict(range=[0, 1.05], tickformat=".0%"), xaxis=dict(range=[0, 100]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", 
                height=400, margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig_agg, width='stretch', key=f"{k}_agg_curve_plot")

        # ── 5-TIER AGG RECOMMENDATION ENGINE ──
        st.markdown("### 📋 Agronomic Recommendations")
        if score_agg >= 80:
            agg_level = "Very High"
            agg_rec = "Your soil structure is optimal. The macroaggregates are highly stable, resisting slaking and crusting under heavy rainfall. This ensures excellent water infiltration and aeration. Continue minimal disturbance practices."
        elif score_agg >= 60:
            agg_level = "High"
            agg_rec = "Your soil structure is good and provides adequate resistance to erosion and compaction. Maintain current organic matter inputs and monitor heavy field traffic."
        elif score_agg >= 40:
            agg_level = "Medium"
            agg_rec = "Your macroaggregate stability is moderate, leaving the soil prone to crusting or sealing during intense rain events. Consider reducing tillage intensity or integrating short-term cover crops to build biological glues."
        elif score_agg >= 20:
            agg_level = "Low"
            agg_rec = "Your soil has weak structural integrity, creating a high risk of slaking, surface runoff, and erosion. Implementing no-till practices alongside active carbon inputs (like manure or dense cover crops) is strongly recommended."
        else:
            agg_level = "Very Low"
            agg_rec = "Critical structural degradation. Your soil aggregates fall apart rapidly when wet, severely limiting infiltration and root growth. Immediate intervention utilizing deep-rooted cover crops and significant organic amendments is required to rebuild soil structure."
        st.info(f"**Score Tier: {agg_level}**\n\n{agg_rec}")

    elif chosen_indicator == "Sodium Adsorption Ratio":
        # 1. Grab Global Variables
        ec_method_id = 1 if "Saturated Paste" in ec_method_str else 2
        texture_id = SMAF_TEXTURE_MAP[st.session_state[f"{k}_sm_tex"]]
        
        # 2. Calculate Score securely
        raw_score_sar = run_smaf_sar_score(sar_val, ec_val, ec_method_id, texture_id, SMAF_DATA)
        try:
            score_sar = float(raw_score_sar) if raw_score_sar is not None else 0.0
        except (ValueError, TypeError):
            score_sar = 0.0
            
        sar_color = score_color(score_sar)
        sar_label = score_label(score_sar)
        
        # 3. Create the 1:2 Column Layout
        col_l, col_r = st.columns([1, 2])
        
        with col_l:
            gauge_title = f"<b style='font-size:17px'>{sar_label}</b><br><span style='font-size:11px;color:gray'>Measured SAR {sar_val}</span>"
            fig_sar_gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=int(round(score_sar)),
                title={"text": gauge_title, "font": {"size": 13}},
                number={"suffix": "/100", "font": {"size": 38, "color": sar_color}},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "gray", "tickvals": [0, 20, 40, 60, 80, 100]},
                    "bar": {"color": sar_color, "thickness": 0.28},
                    "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
                    "steps": [
                        {"range": [0, 20], "color": "rgba(215,48,39,0.35)"},
                        {"range": [20, 40], "color": "rgba(244,109,67,0.35)"},
                        {"range": [40, 60], "color": "rgba(255,193,7,0.35)"},
                        {"range": [60, 80], "color": "rgba(119,195,92,0.35)"},
                        {"range": [80, 100], "color": "rgba(26,150,65,0.35)"}
                    ],
                    "threshold": {"line": {"color": sar_color, "width": 5}, "thickness": 0.8, "value": score_sar}
                }
            ))
            fig_sar_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=260, margin=dict(l=20, r=20, t=80, b=10))
            st.plotly_chart(fig_sar_gauge, use_container_width=True, key=f"{k}_sar_gauge_plot")
            
        with col_r:
            st.markdown("#### Scoring Curve")
            grid = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12.0])
            gy = np.array([run_smaf_sar_score(x, ec_val, ec_method_id, texture_id, SMAF_DATA) for x in grid])
            spl = PchipInterpolator(grid, gy / 100.0)
            xs = np.linspace(0, 12, 300)
            ys = np.clip(spl(xs), 0.0, 1.0)
            
            fig_sar = go.Figure()
            fig_sar.add_trace(go.Scatter(
                x=xs, y=ys, mode="lines", 
                line=dict(color="#2E5E8C", width=3), 
                name="Score Curve", hovertemplate="SAR: %{x:.1f}<br>Score: %{y:.0%}<extra></extra>"
            ))
            fig_sar.add_trace(go.Scatter(
                x=[sar_val], y=[score_sar / 100.0], mode="markers", 
                marker=dict(color=sar_color, size=14, line=dict(color="white", width=2)), 
                name="Your Soil"
            ))
            fig_sar.update_layout(
                xaxis_title="Sodium Adsorption Ratio (SAR)", 
                yaxis_title="SHAPE Score",
                yaxis=dict(range=[0, 1.05], tickformat=".0%"), xaxis=dict(range=[0, 12]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", 
                height=400, margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig_sar, width='stretch', key=f"{k}_sar_curve_plot")
            # ── 5-TIER SAR RECOMMENDATION ENGINE ──
        st.markdown("### 📋 Agronomic Recommendations")

        if score_sar >= 80:
            sar_level = "Very High"
            sar_rec = "Your soil sodium levels are optimal and pose no threat to soil structure or plant health. Water infiltration and aeration are unrestricted by sodicity."
        elif score_sar >= 60:
            sar_level = "High"
            sar_rec = "Your soil SAR is at a safe, manageable level. Continue routine monitoring, especially if irrigating with groundwater, to prevent slow sodium accumulation."
        elif score_sar >= 40:
            sar_level = "Medium"
            sar_rec = "Your soil indicates a moderate sodium hazard. You may begin to notice minor surface crusting or slightly reduced water infiltration. Consider a preventative application of a soluble calcium source (like gypsum) to displace sodium from the clay exchange sites."
        elif score_sar >= 20:
            sar_level = "Low"
            sar_rec = "Your soil has high sodicity, which is likely causing soil dispersion, severe crusting, and poor drainage. A structured remediation plan involving gypsum application followed by heavy leaching irrigation is recommended. Consult a local agronomist."
        else:
            sar_level = "Very Low"
            sar_rec = "Critical sodicity limitation. High sodium levels are causing severe structural collapse, rendering the soil highly impermeable and toxic to most crops. Immediate and aggressive remediation with calcium amendments and intensive leaching is required."

        st.info(f"**Score Tier: {sar_level}**\n\n{sar_rec}")

    elif chosen_indicator == "Potentially Mineralizable Nitrogen":
        # 1. Grab Global Variables
        texture_id = SMAF_TEXTURE_MAP[st.session_state[f"{k}_sm_tex"]]
        om_id = SMAF_OM_MAP.get(st.session_state[f"{k}_sm_om_class"], 2)
        climate_id = SMAF_CLIMATE_MAP.get(st.session_state[f"{k}_sm_climate_class"], 3)
        
        # 2. Calculate Score securely
        raw_score_pmn = run_smaf_pmn_score(pmn_val, om_id, texture_id, climate_id, SMAF_DATA)
        try:
            score_pmn = float(raw_score_pmn) if raw_score_pmn is not None else 0.0
        except (ValueError, TypeError):
            score_pmn = 0.0
            
        pmn_color = score_color(score_pmn)
        pmn_label = score_label(score_pmn)
        
        # 3. Create the 1:2 Column Layout
        col_l, col_r = st.columns([1, 2])
        
        with col_l:
            gauge_title = f"<b style='font-size:17px'>{pmn_label}</b><br><span style='font-size:11px;color:gray'>Measured PMN {pmn_val} mg/kg</span>"
            fig_pmn_gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=int(round(score_pmn)),
                title={"text": gauge_title, "font": {"size": 13}},
                number={"suffix": "/100", "font": {"size": 38, "color": pmn_color}},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "gray", "tickvals": [0, 20, 40, 60, 80, 100]},
                    "bar": {"color": pmn_color, "thickness": 0.28},
                    "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
                    "steps": [
                        {"range": [0, 20], "color": "rgba(215,48,39,0.35)"},
                        {"range": [20, 40], "color": "rgba(244,109,67,0.35)"},
                        {"range": [40, 60], "color": "rgba(255,193,7,0.35)"},
                        {"range": [60, 80], "color": "rgba(119,195,92,0.35)"},
                        {"range": [80, 100], "color": "rgba(26,150,65,0.35)"}
                    ],
                    "threshold": {"line": {"color": pmn_color, "width": 5}, "thickness": 0.8, "value": score_pmn}
                }
            ))
            fig_pmn_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=260, margin=dict(l=20, r=20, t=80, b=10))
            st.plotly_chart(fig_pmn_gauge, use_container_width=True, key=f"{k}_pmn_gauge_plot")
            
        with col_r:
            st.markdown("#### Scoring Curve")
            
            # Use linspace directly; logistic curves are inherently smooth
            chart_max = max(30.0, pmn_val + 5.0)
            xs = np.linspace(0, chart_max, 300)
            ys = [run_smaf_pmn_score(x, om_id, texture_id, climate_id, SMAF_DATA) for x in xs]
            
            fig_pmn = go.Figure()
            fig_pmn.add_trace(go.Scatter(
                x=xs, y=np.array(ys) / 100.0, mode="lines", 
                line=dict(color="#2F6E6B", width=3), 
                name="Score Curve", hovertemplate="PMN: %{x:.1f} mg/kg<br>Score: %{y:.0%}<extra></extra>"
            ))
            
            fig_pmn.add_trace(go.Scatter(
                x=[pmn_val], y=[score_pmn / 100.0], mode="markers", 
                marker=dict(color=pmn_color, size=14, line=dict(color="white", width=2)), 
                name="Your Soil"
            ))
            
            fig_pmn.update_layout(
                xaxis_title="Potentially Mineralizable Nitrogen (mg/kg)", 
                yaxis_title="SHAPE Score",
                yaxis=dict(range=[0, 1.05], tickformat=".0%"), xaxis=dict(range=[0, chart_max]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", 
                height=400, margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig_pmn, width='stretch', key=f"{k}_pmn_curve_plot")

        # ── 5-TIER PMN RECOMMENDATION ENGINE ──
        st.markdown("### 📋 Agronomic Recommendations")

        if score_pmn >= 80:
            pmn_level = "Very High"
            pmn_rec = "Your soil exhibits excellent biological activity and robust organic nitrogen reserves. A highly active microbial community is efficiently mineralizing nitrogen to meet peak crop demands. Continue your current organic matter inputs and diverse crop rotations."
        elif score_pmn >= 60:
            pmn_level = "High"
            pmn_rec = "Your PMN levels indicate good biological function and active nitrogen cycling. The soil microbiome is healthy and supportive of organic matter breakdown. Maintain current residue management practices."
        elif score_pmn >= 40:
            pmn_level = "Medium"
            pmn_rec = "Your soil's biological activity is moderate. Nitrogen mineralization may not fully keep up with rapid crop growth stages. Consider incorporating higher-nitrogen cover crops (like legumes) or applying compost to stimulate the microbial pool."
        elif score_pmn >= 20:
            pmn_level = "Low"
            pmn_rec = "Your PMN levels are low, indicating weak biological activity and sluggish organic nitrogen cycling. Yields may be heavily dependent on synthetic fertilizer inputs. Integrating manure, compost, or continuous living roots into the system is recommended to feed the soil biology."
        else:
            pmn_level = "Very Low"
            pmn_rec = "Critical biological limitation. Your soil has severely degraded biological function with minimal nitrogen mineralization capacity. Immediate intervention is required to rebuild the microbial community through aggressive organic amendments, reduced tillage, and diverse cover cropping."

        st.info(f"**Score Tier: {pmn_level}**\n\n{pmn_rec}")

    elif chosen_indicator == "Available Water Capacity":
        # 1. Grab Global Variables
        texture_id = SMAF_TEXTURE_MAP[st.session_state[f"{k}_sm_tex"]]
        om_string = st.session_state.get(f"{k}_sm_om_class", "Class 2 (Med-High OM)")
        om_id = SMAF_OM_MAP.get(om_string, 2)
        awc_region = st.session_state.get(f"{k}_awc_region", 2)
        
        # 2. Calculate Score securely
        raw_score_awc = run_smaf_awc_score(awc_val, awc_region, texture_id, om_id, SMAF_DATA)
        try:
            score_awc = float(raw_score_awc) if raw_score_awc is not None else 0.0
        except (ValueError, TypeError):
            score_awc = 0.0
            
        awc_color = score_color(score_awc)
        awc_label = score_label(score_awc)
        
        # 3. Create the 1:2 Column Layout
        col_l, col_r = st.columns([1, 2])
        
        with col_l:
            gauge_title = f"<b style='font-size:17px'>{awc_label}</b><br><span style='font-size:11px;color:gray'>Measured AWC {awc_val:.2f} g/g</span>"
            fig_awc_gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=int(round(score_awc)),
                title={"text": gauge_title, "font": {"size": 13}},
                number={"suffix": "/100", "font": {"size": 38, "color": awc_color}},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "gray", "tickvals": [0, 20, 40, 60, 80, 100]},
                    "bar": {"color": awc_color, "thickness": 0.28},
                    "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
                    "steps": [
                        {"range": [0, 20], "color": "rgba(215,48,39,0.35)"},
                        {"range": [20, 40], "color": "rgba(244,109,67,0.35)"},
                        {"range": [40, 60], "color": "rgba(255,193,7,0.35)"},
                        {"range": [60, 80], "color": "rgba(119,195,92,0.35)"},
                        {"range": [80, 100], "color": "rgba(26,150,65,0.35)"}
                    ],
                    "threshold": {"line": {"color": awc_color, "width": 5}, "thickness": 0.8, "value": score_awc}
                }
            ))
            fig_awc_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=260, margin=dict(l=20, r=20, t=80, b=10))
            st.plotly_chart(fig_awc_gauge, use_container_width=True, key=f"{k}_awc_gauge_plot")
            
        with col_r:
            st.markdown("#### Scoring Curve")
            
            # Smooth plotting using linspace
            xs = np.linspace(0, 0.30, 300)
            ys = [run_smaf_awc_score(x, awc_region, texture_id, om_id, SMAF_DATA) for x in xs]
            
            fig_awc = go.Figure()
            fig_awc.add_trace(go.Scatter(
                x=xs, y=np.array(ys) / 100.0, mode="lines", 
                line=dict(color="#356B8C", width=3), 
                name="Score Curve", hovertemplate="AWC: %{x:.3f} g/g<br>Score: %{y:.0%}<extra></extra>"
            ))
            
            fig_awc.add_trace(go.Scatter(
                x=[awc_val], y=[score_awc / 100.0], mode="markers", 
                marker=dict(color=awc_color, size=14, line=dict(color="white", width=2)), 
                name="Your Soil"
            ))
            
            fig_awc.update_layout(
                xaxis_title="Available Water Capacity (g H₂O / g soil)", 
                yaxis_title="SHAPE Score",
                yaxis=dict(range=[0, 1.05], tickformat=".0%"), xaxis=dict(range=[0, 0.30]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", 
                height=400, margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig_awc, width='stretch', key=f"{k}_awc_curve_plot")

        # ── 5-TIER AWC RECOMMENDATION ENGINE ──
        st.markdown("### 📋 Agronomic Recommendations")

        if score_awc >= 80:
            awc_level = "Very High"
            awc_rec = "Your soil’s capacity to store and supply plant-available water is excellent. This provides a strong buffer against short-term drought stress, ensuring continuous nutrient uptake and robust growth."
        elif score_awc >= 60:
            awc_level = "High"
            awc_rec = "Your soil has a good available water capacity. It adequately sustains crops between rain events or irrigation cycles. Maintain current practices that protect soil organic matter and aggregate structure."
        elif score_awc >= 40:
            awc_level = "Medium"
            awc_rec = "Your soil's water-holding capacity is moderate, making crops somewhat vulnerable during dry spells. Consider increasing organic matter inputs or adjusting irrigation frequency to compensate for limited storage."
        elif score_awc >= 20:
            awc_level = "Low"
            awc_rec = "Your soil holds minimal plant-available water, leading to rapid onset of drought stress. Roots likely struggle to access sufficient moisture. Implement practices to build organic matter (like cover crops or compost) to improve sponge-like retention."
        else:
            awc_level = "Very Low"
            awc_rec = "Critical physical limitation. Your soil cannot effectively retain water for plant use, heavily restricting yield potential in rainfed systems. A long-term strategy to rebuild soil structure and heavily incorporate organic amendments is essential."

        st.info(f"**Score Tier: {awc_level}**\n\n{awc_rec}")

    elif chosen_indicator == "Water-Filled Pore Space":
        # 1. Grab Global Variables
        texture_id = SMAF_TEXTURE_MAP.get(st.session_state.get(f"{k}_sm_tex", ""), 2)
        
        # 2. Calculate WFPS Fraction & Scores
        wfps_frac = get_wfps_frac(w_val, bd_val, SMAF_DATA)
        wfps_scores = run_smaf_wfps_score(wfps_frac, texture_id, SMAF_DATA)
        
        try:
            score_wfps = float(wfps_scores["combined"]) if wfps_scores["combined"] is not None else 0.0
        except (ValueError, TypeError):
            score_wfps = 0.0
            
        wfps_color = score_color(score_wfps)
        wfps_label = score_label(score_wfps)
        
        # 3. Create the 1:2 Column Layout
        col_l, col_r = st.columns([1, 2])
        
        with col_l:
            gauge_title = f"<b style='font-size:17px'>{wfps_label}</b><br><span style='font-size:11px;color:gray'>Calculated WFPS: {wfps_frac:.1%}</span>"
            fig_wfps_gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=int(round(score_wfps)),
                title={"text": gauge_title, "font": {"size": 13}},
                number={"suffix": "/100", "font": {"size": 38, "color": wfps_color}},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "gray", "tickvals": [0, 20, 40, 60, 80, 100]},
                    "bar": {"color": wfps_color, "thickness": 0.28},
                    "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
                    "steps": [
                        {"range": [0, 20], "color": "rgba(215,48,39,0.35)"},
                        {"range": [20, 40], "color": "rgba(244,109,67,0.35)"},
                        {"range": [40, 60], "color": "rgba(255,193,7,0.35)"},
                        {"range": [60, 80], "color": "rgba(119,195,92,0.35)"},
                        {"range": [80, 100], "color": "rgba(26,150,65,0.35)"}
                    ],
                    "threshold": {"line": {"color": wfps_color, "width": 5}, "thickness": 0.8, "value": score_wfps}
                }
            ))
            fig_wfps_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=260, margin=dict(l=20, r=20, t=80, b=10))
            st.plotly_chart(fig_wfps_gauge, use_container_width=True, key=f"{k}_wfps_gauge_plot")
            
        with col_r:
            st.markdown("#### Scoring Curve")
            
            # Plot both Biological and Environmental curves smoothly
            xs = np.linspace(0, 1.0, 300)
            ys_bio = []
            ys_env = []
            for x in xs:
                res = run_smaf_wfps_score(x, texture_id, SMAF_DATA)
                ys_bio.append(res["bio"] / 100.0)
                ys_env.append(res["env"] / 100.0)
            
            fig_wfps = go.Figure()
            
            # Biological Curve (Solid Green)
            fig_wfps.add_trace(go.Scatter(
                x=xs, y=ys_bio, mode="lines", 
                line=dict(color="#3F7A4C", width=3), 
                name="Biological Activity", hovertemplate="WFPS: %{x:.0%}<br>Bio Score: %{y:.0%}<extra></extra>"
            ))
            
            # Environmental Curve (Dashed Blue)
            fig_wfps.add_trace(go.Scatter(
                x=xs, y=ys_env, mode="lines", 
                line=dict(color="#2E5E8C", width=3, dash="dash"), 
                name="Env. Protection", hovertemplate="WFPS: %{x:.0%}<br>Env Score: %{y:.0%}<extra></extra>"
            ))
            
            # Your Soil Data Points (Plotting on both lines)
            fig_wfps.add_trace(go.Scatter(
                x=[wfps_frac, wfps_frac], 
                y=[wfps_scores["bio"]/100.0, wfps_scores["env"]/100.0], 
                mode="markers", 
                marker=dict(color=wfps_color, size=14, line=dict(color="white", width=2)), 
                name="Your Soil"
            ))
            
            fig_wfps.update_layout(
                xaxis_title="Water-Filled Pore Space (%)", 
                yaxis_title="SHAPE Score",
                yaxis=dict(range=[0, 1.05], tickformat=".0%"), xaxis=dict(range=[0, 1.0], tickformat=".0%"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", 
                height=400, margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig_wfps, width='stretch', key=f"{k}_wfps_curve_plot")

        # ── 5-TIER WFPS RECOMMENDATION ENGINE ──
        st.markdown("### 📋 Agronomic Recommendations")

        if score_wfps >= 80:
            wfps_level = "Very High"
            wfps_rec = "Your soil porosity and moisture balance is perfectly optimized. The current water level provides excellent conditions for aerobic biological activity (nutrient cycling) while minimizing environmental risks like denitrification and nitrate leaching."
        elif score_wfps >= 60:
            wfps_level = "High"
            wfps_rec = "Your WFPS is in a healthy range. It balances microbial water needs against the risk of anoxia. Continue practices that maintain good soil structure and drainage."
        elif score_wfps >= 40:
            wfps_level = "Medium"
            wfps_rec = "Your WFPS indicates a moderate imbalance. The soil may be either slightly too dry (suppressing microbial mineralization) or slightly too wet (increasing the risk of greenhouse gas emissions). Review your irrigation and drainage strategies."
        elif score_wfps >= 20:
            wfps_level = "Low"
            wfps_rec = "Your soil has poor pore space management. If heavily saturated, you are likely losing significant nitrogen to the atmosphere and experiencing restricted root respiration. If too dry, biological activity has stalled."
        else:
            wfps_level = "Very Low"
            wfps_rec = "Critical physical limitation. Extreme WFPS values mean the soil is either totally waterlogged (causing severe anaerobic conditions and nutrient leaching) or completely desiccated. Immediate adjustments to irrigation, drainage, or compaction management are required."

        st.info(f"**Score Tier: {wfps_level}**\n\n{wfps_rec}")
        
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
                    mode="gauge+number", value=int(round(score_ph)),
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
                fig_cdf.add_trace(go.Scatter(x=x_axis, y=y_axis / 100, mode="lines", line=dict(color="#1a9641", width=3), name="Score Curve", hovertemplate="pH: %{x:.1f}<br>Score: %{y:.1%}<extra></extra>"))
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
    # ── 5-TIER pH RECOMMENDATION ENGINE ──
            st.markdown("### 📋 Agronomic Recommendations")
            
            # 1. Determine the direction of the problem
            opt_ph = benchmarks["opt"]
            if ph_val > opt_ph:
                direction = "lower"
                amendment = "elemental sulfur, acidifying fertilizers (like ammonium sulfate), or organic matter"
            else:
                direction = "raise"
                amendment = "agricultural lime (calcium carbonate) or dolomite"
            # 2. Assign the 5-tier logic
            if score_ph >= 80:
                ph_level = "Very High"
                ph_rec = "Your soil pH is optimal for this crop, supporting maximum nutrient availability. Maintain current management practices; no amendments appear necessary at this time."
            elif score_ph >= 60:
                ph_level = "High"
                ph_rec = f"Your soil pH is adequate, though slightly outside the perfect optimum. Monitor in future seasons to ensure it doesn't drift further. Routine management is likely sufficient."
            elif score_ph >= 40:
                ph_level = "Medium"
                ph_rec = f"Your soil pH may be moderately limiting crop potential and nutrient availability. You might consider a targeted application of {amendment} to gradually {direction} the pH towards the {opt_ph} optimum. Please consult a local agronomist to determine the precise application rate for your specific soil type."
            elif score_ph >= 20:
                ph_level = "Low"
                ph_rec = f"Your soil pH is likely limiting yield potential and reducing fertilizer efficiency. An application of {amendment} is recommended to {direction} the pH. We suggest consulting a local agronomist or extension agent to calculate an accurate and safe application rate."
            else:
                ph_level = "Very Low"
                ph_rec = f"Your soil pH is substantially outside the optimal range for this crop, which can severely lock up essential nutrients. A corrective application of {amendment} to {direction} the pH towards {opt_ph} is highly recommended. Please consult with a certified agronomist for an accurate prescription and safe application strategy."
            # 3. Render the recommendation box
            st.info(f"**Score Tier: {ph_level}**\n\n{ph_rec}")

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
                value=int(round(score)),
                domain={"x": [0, 1], "y": [0, 1]},
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
                                height=260, margin=dict(l=40, r=40, t=80, b=10))
            st.plotly_chart(fig_gauge, use_container_width=True, key=f"{k}_gauge_chart")
            
            st.divider()
            gap = tgt_oc - oc_val
            # Calculate the literal SOC percentage for the 50th percentile (the median)
            median_soc = percentile_to_oc(50, lp_mean, sigma_val)
            
            m1, m2 = st.columns(2)
            with m1:
                # Compare their measured SOC against the peer median
                soc_diff = oc_val - median_soc
                st.metric("Peer Group Median", f"{median_soc:.2f}% SOC", 
                          f"{soc_diff:+.2f}% difference")
            with m2:
                # ✨ NEW: Display the actual target value as the main number, and the gap in the pill below
                st.metric(f"Target ({target_pct}th pct)", f"{tgt_oc:.2f}% SOC",
                          "✅ Exceeds target" if gap <= 0 else f"-{gap:.2f}% needed")

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
                name="Your Site", hovertemplate=f"Your site<br>SOC: {oc_val}%<br>Score: {score:.0f}/100<extra></extra>"
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
        # 🚦 THE TRAFFIC COP: All regions now dynamically route through Excel!
        render_excel_recommendation_engine(region_name, chosen_crop, score, key_prefix=f"{k}_soc_tab")

        # ── Carbon Sequestration Calculator ──
        st.divider()
        st.markdown("### 🌍 Carbon Sequestration Calculator")
        st.markdown("Estimate carbon stock, sequestration gap, credit value, and time to target based on the benchmark above.")

        with st.expander("⚙️ Field & Market Parameters", expanded=True):
            cc1, cc2, cc3, cc4, cc5 = st.columns(5)
            with cc1:
                field_area = st.number_input("Field area (acres)", min_value=1.0, max_value=100000.0, value=None, step=10.0, placeholder="—", key=f"{k}_area")
            with cc2:
                bulk_density = st.number_input("Bulk density (g/cm³)", min_value=0.8, max_value=2.0, value=None, step=0.05, placeholder="—", key=f"{k}_bd")
            with cc3:
                depth_cm = st.number_input("Sampling depth (cm)", min_value=5, max_value=100, value=None, step=5, placeholder="—", key=f"{k}_depth")
            with cc4:
                carbon_price = st.number_input("Carbon price ($/t CO₂e)", min_value=1.0, max_value=500.0, value=None, step=5.0, placeholder="—", key=f"{k}_price")
            with cc5:
                annual_rate = st.number_input("Annual SOC gain (%/yr)", min_value=0.01, max_value=2.0, value=None, step=0.05, placeholder="—", key=f"{k}_rate")

        # ✨ THE NEW CARBON GATEKEEPER ✨
        input_vars = [field_area, bulk_density, depth_cm, carbon_price, annual_rate]

        if None in input_vars:
            st.info("💡 Please fill in all **Field & Market Parameters** above to unlock your carbon stock and credit estimates.")
        else:
            # ⚠️ All math and charts are now indented below the Gatekeeper!
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
