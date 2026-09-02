import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
from scipy.interpolate import PchipInterpolator
import plotly.graph_objects as go
import requests
from pathlib import Path

from soc_recommendations import load_soc_rules, get_management_questions, get_selected_answers, get_soc_recommendation, get_cropping_systems

import streamlit as st
import pandas as pd
import numpy as np
# ... (your other imports) ...

# 1. Master Page Configuration 
# (This MUST be the very first Streamlit command in your script)
st.set_page_config(
    page_title="gSHAPE | Soil Health Scoring",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Custom CSS for Spacing and Layout
st.markdown("""
    <style>
        /* Hide the Streamlit header, menu, and footer */
        header {visibility: hidden;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* Pull the main content up to remove the massive top padding */
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
        }
    </style>
""", unsafe_allow_html=True)


# ── GLOBAL GEOGRAPHY & ROUTING DATA ──
SSA_COUNTRIES = [
    "Angola", "Benin", "Botswana", "Burkina Faso", "Burundi", "Cameroon", "Cape Verde", 
    "Central African Republic", "Chad", "Comoros", "Democratic Republic of the Congo", 
    "Djibouti", "Equatorial Guinea", "Eritrea", "Eswatini", "Ethiopia", "Gabon", "Gambia", 
    "Ghana", "Guinea", "Guinea-Bissau", "Ivory Coast", "Kenya", "Lesotho", "Liberia", 
    "Madagascar", "Malawi", "Mali", "Mauritania", "Mauritius", "Mozambique", "Namibia", 
    "Niger", "Nigeria", "Rwanda", "Sao Tome and Principe", "Senegal", "Seychelles", 
    "Sierra Leone", "Somalia", "South Africa", "South Sudan", "Sudan", "Tanzania", 
    "Togo", "Uganda", "Zambia", "Zimbabwe"
]

US_STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", 
    "Delaware", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", 
    "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", 
    "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", 
    "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio", 
    "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", 
    "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington", "West Virginia", 
    "Wisconsin", "Wyoming"
]

# Comprehensive list of all world countries
WORLD_COUNTRIES = [
    "Afghanistan", "Albania", "Algeria", "Andorra", "Antigua and Barbuda", "Argentina", 
    "Armenia", "Australia", "Austria", "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", 
    "Barbados", "Belarus", "Belgium", "Belize", "Bhutan", "Bolivia", "Bosnia and Herzegovina", 
    "Brazil", "Brunei", "Bulgaria", "Cabo Verde", "Cambodia", "Canada", "Chile", "China", 
    "Colombia", "Congo (Congo-Brazzaville)", "Costa Rica", "Croatia", "Cuba", "Cyprus", 
    "Czechia", "Denmark", "Dominica", "Dominican Republic", "Ecuador", "Egypt", 
    "El Salvador", "Estonia", "Fiji", "Finland", "France", "Georgia", "Germany", "Greece", 
    "Grenada", "Guatemala", "Guyana", "Haiti", "Holy See", "Honduras", "Hungary", "Iceland", 
    "India", "Indonesia", "Iran", "Iraq", "Ireland", "Israel", "Italy", "Jamaica", "Japan", 
    "Jordan", "Kazakhstan", "Kiribati", "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon", 
    "Libya", "Liechtenstein", "Lithuania", "Luxembourg", "Malaysia", "Maldives", "Malta", 
    "Marshall Islands", "Mexico", "Micronesia", "Moldova", "Monaco", "Mongolia", "Montenegro", 
    "Morocco", "Myanmar", "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", 
    "North Korea", "North Macedonia", "Norway", "Oman", "Pakistan", "Palau", "Palestine State", 
    "Panama", "Papua New Guinea", "Paraguay", "Peru", "ilippines", "Poland", "Portugal", 
    "Qatar", "Romania", "Russia", "Saint Kitts and Nevis", "Saint Lucia", 
    "Saint Vincent and the Grenadines", "Samoa", "San Marino", "Saudi Arabia", "Serbia", 
    "Singapore", "Slovakia", "Slovenia", "Solomon Islands", "South Korea", "Spain", "Sri Lanka", 
    "Suriname", "Sweden", "Switzerland", "Syria", "Tajikistan", "Thailand", "Timor-Leste", 
    "Tonga", "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan", "Tuvalu", "Ukraine", 
    "United Arab Emirates", "United Kingdom", "United States", "Uruguay", "Uzbekistan", 
    "Vanuatu", "Venezuela", "Vietnam", "Yemen"
]

# Safely combine both lists to ensure no duplicates, then sort alabetically
ALL_COUNTRIES = list(set(WORLD_COUNTRIES + SSA_COUNTRIES))
ALL_COUNTRIES.sort()

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

/* Enhanced title banner: centered, fully visible corners, and flanking soil graics */
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

/* Left Side Graic: Soil & Diagnostics Microscope Symbol */
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

/* Right Side Graic: Regenerative Sprout Symbol */
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
BR_R3 = ["Histosols","Umbrisols","aeozems","Chernozems","Kastanozems","Podzols","Andosols","Cambisols"]

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
    "R3": "Histosols, Umbrisols, aeozems, Chernozems, Kastanozems, Podzols, Andosols, Cambisols",
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
ET_OR2 = ["Andosols","Chernozems","Gleysols","Kastanozems","aeozems","Podzols","Stagnosols"]
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
    "Or2": "Andosols, Chernozems, Gleysols, Kastanozems, aeozems, Podzols, Stagnosols",
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
TAXON_LABEL = {
    "Florida": "Soil Taxonomy Suborder", 
    "Brazil": "Reference Soil Group (WRB)", 
    "Sub-Saharan Africa": "Reference Soil Group (WRB)",
    "Global_SMAF": "Reference Soil Group / Taxonomy"
}
# ════════════════════════════════════════════════════════════════════
# 4. DATA LOADING & DYNAMIC MASTER LOOKUP
# ════════════════════════════════════════════════════════════════════
@st.cache_data
def load_csv_safe(path, col_map=None):
    if not path:  # ✨ NEW: Skip loading entirely if path is None or empty
        return None
    try:
        d = pd.read_csv(path)
        d.columns = d.columns.str.strip()
        if col_map:
            d = d.rename(columns=col_map)
        return d
    except (FileNotFoundError, ValueError):
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

        # 2. Parse osorus Crop Factors
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

        # 3. Parse NEW pH Gaussian Factors
        K_ph = {}
        if "ph_constants" in sh:
            for _, r in rows("ph_constants").iterrows():
                v = num(r["value"])
                if pd.notna(r["param_name"]) and str(r["param_name"]).strip() not in ("", "nan", "None") and v is not None:
                    K_ph[str(r["param_name"]).strip()] = v
                    
        ph_crops = {}
        if "ph_crop_factors" in sh:
            for _, r in rows("ph_crop_factors").iterrows():
                cc = num(r["crop_code"])
                if cc is not None:
                    ph_crops[int(cc)] = {
                        "name": str(r["crop_name"]).strip(),
                        "b": num(r["b_optimum"]),
                        "c": num(r["c_half_range"])
                    }

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
            "crop_ui_map": crop_ui_map, 
            "ph_constants": K_ph, 
            "ph_crops": ph_crops
        }
    except Exception as e:
        st.error(f"⚠️ Could not dynamically process SMAF_lookup.xlsx: {e}")
        return None

# Initial database processing build
SMAF_DATA = load_smaf_lookup_dynamic("SMAF_lookup.xlsx")

# ── CONSTRAINT: Master crop list ──
if SMAF_DATA and "crop_ui_map" in SMAF_DATA:
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
    "Sand / Loamy Sand / Sandy Loam (<8% clay)": 1, 
    "Sandy Loam (>8% clay) / Sandy Clay Loam / Loam": 2, 
    "Silt Loam / Silt": 3,
    "Sandy Clay / Clay Loam / Silty Clay loam / Silty Clay / Clay (<60% clay)": 4, 
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
def safe_float(val):
    try:
        return float(val) if val is not None else 0.0
    except (ValueError, TypeError):
        return 0.0

def run_smaf_ph_score(ph_val, crop_id, smaf_data, use_alt_c=False):
    """Calculates SMAF pH score using a Gaussian curve based on crop tolerances."""
    try:
        import math
        K = smaf_data.get("ph_constants", {})
        cr = smaf_data.get("ph_crops", {}).get(crop_id)
        if not cr or not K: return 0.0
        
        b, c = cr["b"], cr["c"]
        if b is None or c is None or c == 0: return 0.0
            
        if use_alt_c:
            c = K.get("alt_c_coef_b", 1.2627176) * c + K.get("alt_c_coef_c", 0.29161387) * (c ** 2)
            
        y = K.get("a", 1.0) * math.exp(-((ph_val - b) ** 2) / (2 * (c ** 2)))
        score_val = max(K.get("score_min", 0.0), min(K.get("score_max", 1.0), y))
        return score_val * 100.0
    except (KeyError, TypeError, ValueError):
        return 0.0

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


# ----------------------------------------------------------------------
# SMAF MICROBIAL BIOMASS CARBON (MBC) BACKEND ENGINE
# ----------------------------------------------------------------------
def load_mbc_data(smaf_data, path="SMAF_lookup.xlsx"):
    """Injects the MBC sheets into the global SMAF_DATA dictionary safely."""
    if "mbc_K" in smaf_data and len(smaf_data.get("mbc_K", {})) > 0:
        return
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
        
    mbc_K, mbc_om, mbc_texture, mbc_sc = {}, {}, {}, {}
    
    df_K = clean_df("mbc_constants")
    if not df_K.empty:
        for _, r in df_K.iterrows():
            v = num(r.get("value"))
            p = str(r.get("param_name")).strip()
            if p != "nan" and v is not None: mbc_K[p] = v
            
    df_om = clean_df("mbc_om_factors")
    if not df_om.empty:
        for _, r in df_om.iterrows():
            oc = num(r.get("om_class"))
            if oc is not None:
                # ✨ FIXED: Pulls 'c1_override' and falls back to a safe number if blank
                val = num(r.get("c1_override"))
                if val is None:
                    # Fallback math if override cell is empty
                    R = num(r.get("max_range")) or 1.0
                    val = mbc_K.get("c1_coef_a", 0.0) + mbc_K.get("c1_coef_b", 0.0) * R + mbc_K.get("c1_coef_c", 0.0) * (R ** 2)
                mbc_om[int(oc)] = val
                
    df_tex = clean_df("mbc_texture_factors")
    if not df_tex.empty:
        for _, r in df_tex.iterrows():
            tc = num(r.get("texture_code"))
            if tc is not None: mbc_texture[int(tc)] = num(r.get("c2"))
            
    df_sc = clean_df("mbc_season_climate_factors")
    if not df_sc.empty:
        for _, r in df_sc.iterrows():
            sc = num(r.get("season_climate_code"))
            if sc is not None: mbc_sc[round(sc, 1)] = num(r.get("c3"))
            
    smaf_data["mbc_K"] = mbc_K
    smaf_data["mbc_om"] = mbc_om
    smaf_data["mbc_texture"] = mbc_texture
    smaf_data["mbc_sc"] = mbc_sc

def run_smaf_mbc_score(mbc_val, om_class, texture, season_climate, smaf_data, clamp=True):
    load_mbc_data(smaf_data)
    K = smaf_data.get("mbc_K", {})
    if not K: return 0.0
    
    try:
        mbc_val = float(mbc_val)
    except (TypeError, ValueError):
        mbc_val = 0.0
        
    if mbc_val <= 0:
        return 0.0

    import math
    om_dict = smaf_data.get("mbc_om", {})
    try:
        clean_oc = int(om_class)
    except (TypeError, ValueError):
        clean_oc = 2
        
    c1 = om_dict.get(clean_oc)
    if c1 is None:
        c1 = om_dict.get(2, 0.0124192)
    
    tex_dict = smaf_data.get("mbc_texture", {})
    c2 = tex_dict.get(int(texture)) or tex_dict.get(str(texture)) or 1.0
    
    # ✨ Advanced Season/Climate Lookup
    sc_dict = smaf_data.get("mbc_sc", {})
    sc_key = round(float(season_climate), 1)
    base_season = int(math.floor(sc_key))
    
    # Checks for exact decimal (2.3), then base integer (2), then defaults to 1.0
    c3 = sc_dict.get(sc_key) or sc_dict.get(str(sc_key)) or sc_dict.get(base_season) or sc_dict.get(str(base_season)) or 1.0
    
    c = float(c1) * float(c2) * float(c3)
    
    try:
        # Hardcoding the correct 40.478 constant to override the Excel typo
        y = float(K.get("a", 1.0)) / (1.0 + float(K.get("b", 40.478)) * math.exp(-c * mbc_val))
    except (OverflowError, TypeError, ValueError):
        y = 0.0
        
    if clamp:
        y = max(float(K.get("score_min", 0.0)), min(float(K.get("score_max", 1.0)), y))
        
    return y * 100.0

# ----------------------------------------------------------------------
# SMAF SOIL ORGANIC CARBON (SOC) BACKEND ENGINE
# ----------------------------------------------------------------------
def load_smaf_soc_data(smaf_data, path="SMAF_lookup.xlsx"):
    """Injects the 4 new SOC sheets into the global SMAF_DATA dictionary safely."""
    if "soc_K" in smaf_data and len(smaf_data.get("soc_K", {})) > 0: return 
    
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
        
    soc_K, soc_om, soc_texture, soc_climate = {}, {}, {}, {}
    
    df_K = clean_df("soc_constants")
    if not df_K.empty:
        for _, r in df_K.iterrows():
            v = num(r.get("value"))
            p = str(r.get("param_name")).strip()
            if p != "nan" and v is not None: soc_K[p] = v
            
    df_om = clean_df("soc_om_factors")
    if not df_om.empty:
        for _, r in df_om.iterrows():
            oc = num(r.get("om_class"))
            if oc is not None: soc_om[int(oc)] = num(r.get("c1"))
            
    df_tex = clean_df("soc_texture_factors")
    if not df_tex.empty:
        for _, r in df_tex.iterrows():
            tc = num(r.get("texture_code"))
            if tc is not None: soc_texture[int(tc)] = num(r.get("c2"))
            
    df_clim = clean_df("soc_climate_factors")
    if not df_clim.empty:
        for _, r in df_clim.iterrows():
            cc = num(r.get("climate_class"))
            if cc is not None: soc_climate[int(cc)] = num(r.get("c3"))
            
    smaf_data["soc_K"] = soc_K
    smaf_data["soc_om"] = soc_om
    smaf_data["soc_texture"] = soc_texture
    smaf_data["soc_climate"] = soc_climate

def run_smaf_soc_score(toc_pct, om_class, texture, climate, smaf_data, clamp=True):
    load_smaf_soc_data(smaf_data)
    K = smaf_data.get("soc_K", {})
    if not K: return 0.0
    
    import math
    c1 = smaf_data.get("soc_om", {}).get(om_class, 1.0)
    c2 = smaf_data.get("soc_texture", {}).get(texture, 1.0)
    c3 = smaf_data.get("soc_climate", {}).get(climate, 1.0)
    
    # Reverted to your original additive logic that perfectly matches your Excel calibration!
    c = (float(c1) * float(c2)) + (float(c1) * float(c2) * float(c3))
    
    # ✨ THE FIX: Convert UI percentage (e.g., 2.0%) to SMAF g/kg (20.0 g/kg)
    toc_g_kg = float(toc_pct) * 10.0
    
    try:
        a = float(K.get("a", 1.0))
        b = float(K.get("b", 1.0))
        
        # The math runs using the g/kg value
        y = a / (1.0 + b * math.exp(-c * toc_g_kg))
    except (OverflowError, TypeError, ValueError):
        y = 0.0
        
    if clamp:
        y = max(float(K.get("score_min", 0.0)), min(float(K.get("score_max", 1.0)), y))
        
    return y * 100.0
# ----------------------------------------------------------------------
# SMAF BETA-GLUCOSIDASE (BG) BACKEND ENGINE
# ----------------------------------------------------------------------
def load_bg_data(smaf_data, path="SMAF_lookup.xlsx"):
    """Injects the 4 new BG sheets into the global SMAF_DATA dictionary safely."""
    if "bg_K" in smaf_data and len(smaf_data.get("bg_K", {})) > 0: return 
    
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
        
    bg_K, bg_om, bg_texture, bg_climate = {}, {}, {}, {}
    
    df_K = clean_df("bg_constants")
    if not df_K.empty:
        for _, r in df_K.iterrows():
            v = num(r.get("value"))
            p = str(r.get("param_name")).strip()
            if p != "nan" and v is not None: bg_K[p] = v
            
    df_om = clean_df("bg_om_factors")
    if not df_om.empty:
        for _, r in df_om.iterrows():
            oc = num(r.get("om_class"))
            if oc is not None: bg_om[int(oc)] = num(r.get("c1"))
            
    df_tex = clean_df("bg_texture_factors")
    if not df_tex.empty:
        for _, r in df_tex.iterrows():
            tc = num(r.get("texture_code"))
            if tc is not None: bg_texture[int(tc)] = num(r.get("c2"))
            
    df_clim = clean_df("bg_climate_factors")
    if not df_clim.empty:
        for _, r in df_clim.iterrows():
            cc = num(r.get("climate_class"))
            if cc is not None: bg_climate[int(cc)] = num(r.get("c3"))
            
    smaf_data["bg_K"] = bg_K
    smaf_data["bg_om"] = bg_om
    smaf_data["bg_texture"] = bg_texture
    smaf_data["bg_climate"] = bg_climate

def run_smaf_bg_score(bg_val, om_class, texture, climate, smaf_data, clamp=True):
    load_bg_data(smaf_data)
    K = smaf_data.get("bg_K", {})
    if not K: return 0.0
    
    import math
    c1 = smaf_data.get("bg_om", {}).get(om_class, 1.0)
    c2 = smaf_data.get("bg_texture", {}).get(texture, 1.0)
    c3 = smaf_data.get("bg_climate", {}).get(climate, 1.0)
    c = (c1 * c2) + (c1 * c2 * c3)
    
    try:
        x_scale = K.get("x_scale", 1000.0)
        y = K.get("a", 1.0) / (1.0 + K.get("b", 1.0) * math.exp(-c * bg_val / x_scale))
    except OverflowError:
        y = 0.0
        
    if clamp:
        y = max(K.get("score_min", 0.0), min(K.get("score_max", 1.0), y))
        
    return y * 100.0

# ----------------------------------------------------------------------
# SMAF EXTRACTABLE POTASSIUM (EX-K) BACKEND ENGINE
# ----------------------------------------------------------------------
def load_exk_data(smaf_data, path="SMAF_lookup.xlsx"):
    """Injects the Ex-K sheets into the global SMAF_DATA dictionary safely."""
    if "exk_params" in smaf_data and len(smaf_data.get("exk_params", {})) > 0: return 
    
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
        
    exk_texture = {}
    df_tex = clean_df("exk_texture_params")
    if not df_tex.empty:
        for _, r in df_tex.iterrows():
            tc = num(r.get("texture_code"))
            if tc is not None:
                exk_texture[int(tc)] = str(r.get("param_set")).strip()
                
    exk_params = {}
    df_const = clean_df("exk_constants")
    if not df_const.empty:
        for _, r in df_const.iterrows():
            ps = str(r.get("param_set")).strip()
            a, b = num(r.get("a")), num(r.get("b"))
            if ps != "nan" and a is not None and b is not None:
                exk_params[ps] = {"a": a, "b": b}
                
    smaf_data["exk_texture"] = exk_texture
    smaf_data["exk_params"] = exk_params

def run_smaf_exk_score(k_val, texture_id, smaf_data, clamp=True):
    load_exk_data(smaf_data)
    t = smaf_data.get("exk_texture", {})
    p = smaf_data.get("exk_params", {})
    
    if not t or not p: return 0.0
    
    pset = t.get(texture_id)
    if not pset or pset not in p: return 0.0
    
    a = p[pset]["a"]
    b = p[pset]["b"]
    
    import math
    try:
        y = a * (1.0 - math.exp(b * k_val))
    except OverflowError:
        y = 1.0
        
    if clamp:
        y = max(0.0, min(1.0, y))
        
    return y * 100.0

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

  # ── MASTER SITE INPUTS (DYNAMICALLY FILTERED BY CHECKBOXES) ──
    target_indicators = st.session_state.get("target_indicators", [])
    
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
            raw_tex = selected_tex.lower().strip() if selected_tex else ""
            
            if "— select —" in raw_tex or not raw_tex:
                derived_tex_id = 0
            elif raw_tex in ["sand", "loamy sand"]:
                derived_tex_id = 1
            elif raw_tex in ["sandy loam", "sandy clay loam", "loam"]:
                derived_tex_id = 2
            elif raw_tex in ["silt", "silt loam"]:
                derived_tex_id = 3
            elif raw_tex in ["silty clay", "silty clay loam", "clay loam", "sandy clay"]:
                derived_tex_id = 4
            elif raw_tex == "clay":
                derived_tex_id = 5
            else:
                # 3-word combinations first
                if "sandy clay loam" in raw_tex: derived_tex_id = 2
                elif "silty clay loam" in raw_tex: derived_tex_id = 4
                # 2-word combinations next
                elif "silty clay" in raw_tex: derived_tex_id = 4
                elif "sandy clay" in raw_tex: derived_tex_id = 4
                elif "clay loam" in raw_tex: derived_tex_id = 4
                elif "silt loam" in raw_tex: derived_tex_id = 3
                elif "sandy loam" in raw_tex: derived_tex_id = 2
                elif "loamy sand" in raw_tex: derived_tex_id = 1
                # Single words last (so they don't steal the multi-word phrases)
                elif "silt" in raw_tex: derived_tex_id = 3
                elif "clay" in raw_tex: derived_tex_id = 5
                elif "loam" in raw_tex: derived_tex_id = 2
                elif "sand" in raw_tex: derived_tex_id = 1
                else: derived_tex_id = 2
                
            tex_options = ["— Select —"] + list(SMAF_TEXTURE_MAP.keys())
            
            if derived_tex_id != 0: 
                st.session_state[f"{k}_sm_tex"] = tex_options[derived_tex_id]
                
            selected_sm_tex = st.selectbox("Texture Profile (Auto-Assigned)", tex_options, key=f"{k}_sm_tex")
            
            texture_id = SMAF_TEXTURE_MAP.get(selected_sm_tex, 0)
            selected_bd_min = None
            if texture_id >= 4 and "Bulk Density" in target_indicators:
                selected_bd_min = st.selectbox("Clay Mineralogy", ["— Select —"] + list(SMAF_MINERALOGY_MAP.keys()), key=f"{k}_bd_min")

            # Only show Slope if Macroaggregate Stability is selected
            selected_sm_slope = "0–2% Level Slope"
            if "Macroaggregate Stability" in target_indicators or "Soil Phosphorus" in target_indicators:
                selected_sm_slope = st.selectbox("Landscape Slope Profile", ["— Select —"] + list(SMAF_SLOPE_MAP.keys()), key=f"{k}_sm_slope")
                
            chosen_crop = st.selectbox("Target Field Crop", MASTER_CROP_OPTIONS, key=f"{k}_sm_crop")
            
            # Only show Sampling Season if MBC is selected
            selected_season = "Spring"
            if "Microbial Biomass Carbon" in target_indicators:
                selected_season = st.selectbox("Sampling Season", ["Spring", "Summer", "Fall", "Winter"], key=f"{k}_sm_season")
                
        with c2:
            # Only show P Method/Weathering if Soil Phosphorus is selected
            selected_method = "Mehlich-3"
            selected_weath = "Slightly Weathered"
            if "Soil Phosphorus" in target_indicators:
                selected_method = st.selectbox("P Extraction Method", ["— Select —"] + list(SMAF_METHOD_MAP.keys()), key=f"{k}_sm_method")
                selected_weath = st.selectbox("Soil Weathering Class", ["— Select —"] + list(SMAF_WEATHERING_MAP.keys()), key=f"{k}_sm_weather")
                
            # Only show EC Method if EC or SAR is selected
            ec_method_str = "Saturated Paste (ECsat)"
            if "Electrical Conductivity" in target_indicators or "Sodium Adsorption Ratio" in target_indicators:
                ec_method_str = st.selectbox("EC Method", ["— Select —", "Saturated Paste (ECsat)", "1:1 Soil:Water"], key=f"{k}_ec_method")
            
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

            # Iron Oxide Class auto-assignment for Aggregates
            sub_lower = selected_sub.lower()
            high_fe_keywords = ["ult", "oxs", "oxisol", "acrisol", "alisol", "ferralsol", "argissolo", "alissolo", "latossolo"]
            is_high_fe = any(keyword in sub_lower for keyword in high_fe_keywords)
            derived_fe_id = 1 if is_high_fe else 2 if "— select —" not in sub_lower else 0
            fe_options = ["— Select —"] + list(SMAF_FE_MAP.keys())
            if derived_fe_id != 0: st.session_state[f"{k}_sm_fe_class"] = fe_options[derived_fe_id]
            
            selected_fe_class = "All Other Soil Orders"
            if "Macroaggregate Stability" in target_indicators:
                selected_fe_class = st.selectbox("Iron-Oxide Class (Auto-Assigned)", fe_options, key=f"{k}_sm_fe_class")
                
            clim_options = ["— Select —"] + list(SMAF_CLIMATE_MAP.keys())
            selected_climate_class = clim_options[1]
            if "Potentially Mineralizable Nitrogen" in target_indicators or "Microbial Biomass Carbon" in target_indicators:
                is_warm = target_temp >= 15.0
                is_wet = target_precip >= 600.0 if target_precip is not None else True
                derived_clim_id = 1 if (is_warm and is_wet) else 2 if (is_warm and not is_wet) else 3 if (not is_warm and is_wet) else 4
                st.session_state[f"{k}_sm_climate_class"] = clim_options[derived_clim_id]
                selected_climate_class = st.selectbox("Climate Class (Auto-Assigned)", clim_options, key=f"{k}_sm_climate_class")

           # ✨ VISIBLE OM CLASS DERIVATION (Taxonomy-Based Default) ✨
            # Safely grab the taxonomy dropdown value (Ensure 'selected_sub' matches your left-column variable!)
            raw_tax = selected_sub.lower().strip() if 'selected_sub' in locals() and selected_sub else ""
            raw_tax = raw_tax.replace("oxs", "ox").replace("oxes", "ox")
            
            # Use base (singular) forms to catch any variations or pluralizations
            class_1_subs = ["aquand", "aquod", "aquox", "fibrist", "folist", "hemist", "histel", "saprist", "turbel"]
            class_2_subs = ["alboll", "aquept", "aquert", "aquoll", "aquult", "boroll", "cryoll", "humod", "humult", "rendoll", "udand", "udoll", "udox", "ustand", "ustert", "ustoll", "xerert", "xeroll"]
            class_3_subs = ["andept", "anthrept", "aqualf", "aquent", "boralf", "cryalf", "cryand", "cryert", "cryod", "orthel", "udalf", "ustalf", "vitrand", "xeralf"]
            
            # Use 'any()' to search for the keyword anywhere inside the dropdown string
            if any(sub in raw_tax for sub in class_1_subs):
                default_om_idx = 0
            elif any(sub in raw_tax for sub in class_2_subs):
                default_om_idx = 1
            elif any(sub in raw_tax for sub in class_3_subs):
                default_om_idx = 2
            else:
                default_om_idx = 3  # Class 4 fallback
            
            om_options = [
                "Class 1 (Highest OM)", 
                "Class 2 (Med-High OM)", 
                "Class 3 (Med-Low OM)", 
                "Class 4 (Lowest OM)"
            ]

            # Initialize session state default if it doesn't exist yet
            if f"{k}_sm_om_class" not in st.session_state:
                st.session_state[f"{k}_sm_om_class"] = om_options[1] # Default to Class 2

            # ✨ REMOVED THE TAXONOMY OVERRIDE LOOP SO YOUR MANUAL SELECTION STICKS!
            selected_om_class = st.selectbox(
                "Organic Matter (OM) Class", 
                options=om_options, 
                key=f"{k}_sm_om_class"
            )
        
            # This explicitly locks the checkbox so it ONLY appears for United States -> Florida
            hist_toggle = False 
            
            if region_name == "Florida":
                hist_toggle = st.checkbox(
                    "📌 This is an organic / Histosol soil (Muck, Peat)", 
                    key=f"{k}_hist_toggle"
                )
    # ── MASTER LAB INPUTS (DYNAMICALLY FILTERED BY CHECKBOXES) ──
 # ── MASTER LAB INPUTS (DYNAMICALLY FILTERED BY CHECKBOXES) ──
    with st.expander("🧪 Laboratory Measurements", expanded=True):
        # 1. Initialize variables as None so they start completely blank!
        oc_val, p_val, k_val, ph_val, ec_val, sar_val = None, None, None, None, None, None
        bd_val, agg_val, awc_val, wfps_frac = None, None, None, None
        pmn_val, mbc_val, bg_val = None, None, None

        # 2. Setup columns and a counter to dynamically route inputs left-to-right
        cols = st.columns(3)
        col_idx = 0 

        # 3. Render inputs dynamically into the next available column
        if "Soil Organic Carbon" in target_indicators or "SMAF Soil Organic Carbon" in target_indicators:
            with cols[col_idx % 3]: 
                oc_val = st.number_input("Measured SOC (%)", min_value=0.0, max_value=20.0, step=0.1, value=None, placeholder="Enter value...", key=f"{k}_oc")
            col_idx += 1
            
        if "Soil Phosphorus" in target_indicators:
            with cols[col_idx % 3]: 
                p_val = st.number_input("Measured Phosphorus (mg/kg)", min_value=0.0, max_value=500.0, step=5.0, value=None, placeholder="Enter value...", key=f"{k}_sm_p_input")
            col_idx += 1
            
        if "Extractable Potassium" in target_indicators:
            with cols[col_idx % 3]: 
                k_val = st.number_input("Measured Extractable K (mg/kg)", min_value=0.0, max_value=1000.0, step=5.0, value=None, placeholder="Enter value...", key=f"{k}_exk_val")
            col_idx += 1
            
        if "pH" in target_indicators:
            with cols[col_idx % 3]: 
                ph_val = st.number_input("Measured Soil pH", min_value=0.0, max_value=14.0, step=0.1, value=None, placeholder="Enter value...", key=f"{k}_ph")
            col_idx += 1
            
        if "Electrical Conductivity" in target_indicators:
            with cols[col_idx % 3]: 
                ec_val = st.number_input("Measured EC (dS/m)", min_value=0.0, max_value=20.0, step=0.1, value=None, placeholder="Enter value...", key=f"{k}_ec")
            col_idx += 1
            
        if "Sodium Adsorption Ratio" in target_indicators:
            with cols[col_idx % 3]: 
                sar_val = st.number_input("Measured SAR", min_value=0.0, max_value=50.0, step=0.1, value=None, placeholder="Enter value...", key=f"{k}_sar")
            col_idx += 1
            
        if "Bulk Density" in target_indicators:
            with cols[col_idx % 3]: 
                bd_val = st.number_input("Measured Bulk Density (g/cm³)", min_value=0.1, max_value=2.5, step=0.05, value=None, placeholder="Enter value...", key=f"{k}_bd")
            col_idx += 1
            
        if "Macroaggregate Stability" in target_indicators:
            with cols[col_idx % 3]: 
                agg_val = st.number_input("Macroaggregate Stability (%)", min_value=0.0, max_value=100.0, step=1.0, value=None, placeholder="Enter value...", key=f"{k}_agg")
            col_idx += 1
            
        if "Available Water Capacity" in target_indicators:
            with cols[col_idx % 3]: 
                awc_val = st.number_input("Measured AWC (g/g)", min_value=0.0, max_value=1.0, step=0.01, value=None, placeholder="Enter value...", key=f"{k}_awc")
            col_idx += 1
            
        if "Water-Filled Pore Space" in target_indicators:
            with cols[col_idx % 3]: 
                wfps_frac = st.number_input("Measured WFPS (fraction)", min_value=0.0, max_value=1.0, step=0.05, value=None, placeholder="Enter value...", key=f"{k}_wfps")
            col_idx += 1
            
        if "Potentially Mineralizable Nitrogen" in target_indicators:
            with cols[col_idx % 3]: 
                pmn_val = st.number_input("Measured PMN (mg/kg)", min_value=0.0, max_value=200.0, step=1.0, value=None, placeholder="Enter value...", key=f"{k}_pmn")
            col_idx += 1
            
        if "Microbial Biomass Carbon" in target_indicators:
            with cols[col_idx % 3]: 
                mbc_val = st.number_input("Measured MBC (mg/kg)", min_value=0.0, max_value=2000.0, step=10.0, value=None, placeholder="Enter value...", key=f"{k}_mbc_val")
            col_idx += 1
            
        if "Beta-glucosidase" in target_indicators:
            with cols[col_idx % 3]: 
                bg_val = st.number_input("Measured BG (mg/kg/hr)", min_value=0.0, max_value=2000.0, step=10.0, value=None, placeholder="Enter value...", key=f"{k}_bg_val")
            col_idx += 1

    # ✨ THE NEW LAB MEASUREMENTS GATEKEEPER ✨
    # This prevents the app from running the math until the user physically types in a value
    missing_labs = []
    
    if ("Soil Organic Carbon" in target_indicators or "SMAF Soil Organic Carbon" in target_indicators) and oc_val is None: missing_labs.append("Soil Organic Carbon")
    if "Soil Phosphorus" in target_indicators and p_val is None: missing_labs.append("Soil Phosphorus")
    if "Extractable Potassium" in target_indicators and k_val is None: missing_labs.append("Extractable Potassium")
    if "pH" in target_indicators and ph_val is None: missing_labs.append("pH")
    if "Electrical Conductivity" in target_indicators and ec_val is None: missing_labs.append("Electrical Conductivity")
    if "Sodium Adsorption Ratio" in target_indicators and sar_val is None: missing_labs.append("Sodium Adsorption Ratio")
    if "Bulk Density" in target_indicators and bd_val is None: missing_labs.append("Bulk Density")
    if "Macroaggregate Stability" in target_indicators and agg_val is None: missing_labs.append("Macroaggregate Stability")
    if "Available Water Capacity" in target_indicators and awc_val is None: missing_labs.append("Available Water Capacity")
    if "Water-Filled Pore Space" in target_indicators and wfps_frac is None: missing_labs.append("Water-Filled Pore Space")
    if "Potentially Mineralizable Nitrogen" in target_indicators and pmn_val is None: missing_labs.append("Potentially Mineralizable Nitrogen")
    if "Microbial Biomass Carbon" in target_indicators and mbc_val is None: missing_labs.append("Microbial Biomass Carbon")
    if "Beta-glucosidase" in target_indicators and bg_val is None: missing_labs.append("Beta-glucosidase")

    if missing_labs:
        st.info(f"🧪 **Pending Lab Results:** Please enter values for **{', '.join(missing_labs)}** to calculate your scores.")
        return  # ✨ Changed from st.stop() to return!
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
    row = None  # ✨ Initialize row safely here

    if hist_toggle and cfg["has_histosol"] and df_hist is not None:
        lp_mean   = float(df_hist["mean_lp"].iloc[0])
        lp_lcl    = float(df_hist["lcl_lp"].iloc[0])
        lp_ucl    = float(df_hist["ucl_lp"].iloc[0])
        sigma_val = float(np.exp(df_hist["mean_sigma"].iloc[0]))
        plot_max  = 80.0
    else:
        if df is None:
            # Bypass SHAPE SOC math for Global SMAF fallback mode
            lp_mean, lp_lcl, lp_ucl, sigma_val, plot_max = 0.0, 0.0, 0.0, 1.0, 15.0
        else:
            row = get_params_any(cfg, df, tax, tex, target_temp, target_precip)
            
        if row is not None:
            lp_mean   = float(row["mean_lp"])
            lp_lcl    = float(row["lcl_lp"])
            lp_ucl    = float(row["ucl_lp"])
            sigma_val = float(np.exp(row["mean_sigma"]))
            plot_max  = max(15.0, oc_val + 5)
        else:
            lp_mean, lp_lcl, lp_ucl, sigma_val, plot_max = 0.0, 0.0, 0.0, 1.0, 15.0

# ── COMPREHENSIVE SOIL HEALTH SUMMARY (DYNAMICALLY FILTERED) ──
    st.markdown("### 📊 Comprehensive Soil Health Overview")
    
    target_indicators = st.session_state.get("target_indicators", [])
    
    # ── 0. PRE-DEFINE SAFE GLOBAL VARIABLES FOR SUMMARY/TABLE ──
    texture_id_sum = SMAF_TEXTURE_MAP.get(st.session_state.get(f"{k}_sm_tex", ""), 2)
    om_string_sum = st.session_state.get(f"{k}_sm_om_class", "Class 2 (Med-High OM)")
    om_id_sum = SMAF_OM_MAP.get(om_string_sum, 2)
    fe_id_sum = SMAF_FE_MAP.get(selected_fe_class, 2) if 'selected_fe_class' in locals() else 2
    climate_id_sum = SMAF_CLIMATE_MAP.get(st.session_state.get(f"{k}_sm_climate_class", ""), 3)

    bd_val_sum = st.session_state.get(f"{k}_bd", 1.45)
    mineral_str = st.session_state.get(f"{k}_bd_min", "— Select —")
    mineralogy_id_sum = SMAF_MINERALOGY_MAP.get(mineral_str, 0) if mineral_str != "— Select —" else 0

    agg_val_sum = st.session_state.get(f"{k}_agg", 40.0)
    awc_val_sum = st.session_state.get(f"{k}_awc", 0.15)
    w_val_sum = st.session_state.get(f"{k}_w_val", 0.25)
    ph_val_sum = st.session_state.get(f"{k}_ph", 6.0)
    p_val_sum = st.session_state.get(f"{k}_sm_p_input", 25.0)
    k_val_sum = st.session_state.get(f"{k}_exk_val", 125.0)
    ec_val_sum = st.session_state.get(f"{k}_ec", 1.5)
    sar_val_sum = st.session_state.get(f"{k}_sar", 2.0)
    pmn_val_sum = st.session_state.get(f"{k}_pmn", 10.0)
    mbc_val_sum = st.session_state.get(f"{k}_mbc_val", 200.0)
    bg_val_sum = st.session_state.get(f"{k}_bg_val", 300.0)
    
    wfps_frac_sum = get_wfps_frac(w_val_sum, bd_val_sum, SMAF_DATA)

    # Initialize category scores and counts
    phys_scores, chem_scores, bio_scores = [], [], []
    
    # ── PHYSICAL INDICATORS ──
    if "Bulk Density" in target_indicators:
        mineral_str = st.session_state.get(f"{k}_bd_min", "— Select —")
        mineralogy_id_sum = SMAF_MINERALOGY_MAP.get(mineral_str, 0) if mineral_str != "— Select —" else 0
        phys_scores.append(safe_float(run_smaf_bd_score(bd_val_sum, texture_id_sum, mineralogy_id_sum)))
        
    if "Macroaggregate Stability" in target_indicators:
        phys_scores.append(safe_float(run_smaf_agg_score(agg_val_sum, om_id_sum, texture_id_sum, fe_id_sum, SMAF_DATA)))
        
    if "Available Water Capacity" in target_indicators:
        awc_region_sum = st.session_state.get(f"{k}_awc_region", 2)
        phys_scores.append(safe_float(run_smaf_awc_score(awc_val_sum, awc_region_sum, texture_id_sum, om_id_sum, SMAF_DATA)))
        
    if "Water-Filled Pore Space" in target_indicators:
        wfps_scores_sum = run_smaf_wfps_score(wfps_frac_sum, texture_id_sum, SMAF_DATA)
        phys_scores.append(safe_float(wfps_scores_sum["combined"]))

    # ── CHEMICAL INDICATORS ──
  # ── CHEMICAL INDICATORS ──
    if "pH" in target_indicators:
        crop_id_sum = SMAF_DATA.get("crop_ui_map", {}).get(st.session_state.get(f"{k}_sm_crop", "").lower(), 82)
        chem_scores.append(safe_float(run_smaf_ph_score(ph_val_sum, crop_id_sum, SMAF_DATA)))
        
    if "Soil Phosphorus" in target_indicators:
        crop_id_sum = SMAF_DATA["crop_ui_map"].get(st.session_state.get(f"{k}_sm_crop", "").lower(), 0)
        method_str = st.session_state.get(f"{k}_sm_method", "Mehlich-3")
        weather_str = st.session_state.get(f"{k}_sm_weather", "Slightly Weathered")
        method_id_sum = SMAF_METHOD_MAP.get(method_str, 2)
        weather_id_sum = SMAF_WEATHERING_MAP.get(weather_str, 3)
        slope_str = st.session_state.get(f"{k}_sm_slope", "0–2% Level Slope")
        slope_id_sum = SMAF_SLOPE_MAP.get(slope_str, 1)
        oc_val_sum = st.session_state.get(f"{k}_oc", 2.0)
        chem_scores.append(safe_float(run_smaf_p_score(p_val_sum, crop_id_sum, method_id_sum, weather_id_sum, texture_id_sum, slope_id_sum, oc_val_sum)))
        
    if "Electrical Conductivity" in target_indicators:
        ec_method_str_sum = st.session_state.get(f"{k}_ec_method", "Saturated Paste (ECsat)")
        ec_method_id_sum = 1 if "Saturated Paste" in ec_method_str_sum else 2
        crop_id_sum = SMAF_DATA["crop_ui_map"].get(st.session_state.get(f"{k}_sm_crop", "").lower(), 0)
        chem_scores.append(safe_float(run_smaf_ec_score(ec_val_sum, crop_id_sum, ec_method_id_sum, texture_id_sum, SMAF_DATA)))
        
    if "Sodium Adsorption Ratio" in target_indicators:
        ec_method_str_sum = st.session_state.get(f"{k}_ec_method", "Saturated Paste (ECsat)")
        ec_method_id_sum = 1 if "Saturated Paste" in ec_method_str_sum else 2
        chem_scores.append(safe_float(run_smaf_sar_score(sar_val_sum, ec_val_sum, ec_method_id_sum, texture_id_sum, SMAF_DATA)))

    if "Extractable Potassium" in target_indicators:
        chem_scores.append(safe_float(run_smaf_exk_score(k_val_sum, texture_id_sum, SMAF_DATA)))

    # ── BIOLOGICAL INDICATORS ──
    if "Soil Organic Carbon" in target_indicators:
        bio_scores.append(safe_float(compute_score(oc_val, lp_mean, sigma_val)))
    if "SMAF Soil Organic Carbon" in target_indicators:
        bio_scores.append(safe_float(run_smaf_soc_score(oc_val, om_id_sum, texture_id_sum, climate_id_sum, SMAF_DATA)))
        
    if "Potentially Mineralizable Nitrogen" in target_indicators:
        bio_scores.append(safe_float(run_smaf_pmn_score(pmn_val_sum, om_id_sum, texture_id_sum, climate_id_sum, SMAF_DATA)))
        
    if "Microbial Biomass Carbon" in target_indicators:
        season_name = st.session_state.get(f"{k}_sm_season", "Spring")
        season_num = {"Spring": 1, "Summer": 2, "Fall": 3, "Winter": 4}.get(season_name, 1)
        
        # ✨ Define climate_id safely here too
        climate_id = SMAF_CLIMATE_MAP.get(st.session_state.get(f"{k}_sm_climate_class", ""), 3)
        
        season_climate_code = 1.0 if season_num == 1 else float(f"{season_num}.{climate_id}")
        bio_scores.append(safe_float(run_smaf_mbc_score(mbc_val_sum, om_id_sum, texture_id_sum, season_climate_code, SMAF_DATA)))

    if "Beta-glucosidase" in target_indicators:
        bio_scores.append(safe_float(run_smaf_bg_score(bg_val_sum, om_id_sum, texture_id_sum, climate_id_sum, SMAF_DATA)))

   # ── DYNAMIC CATEGORY AVERAGING (Only includes categories with selected indicators) ──
    score_phys = sum(phys_scores) / len(phys_scores) if phys_scores else None
    score_chem = sum(chem_scores) / len(chem_scores) if chem_scores else None
    score_bio = sum(bio_scores) / len(bio_scores) if bio_scores else None
    
    # Collect only categories that have at least one selected indicator
    active_pillar_scores = [s for s in [score_phys, score_chem, score_bio] if s is not None]
    score_overall = sum(active_pillar_scores) / len(active_pillar_scores) if active_pillar_scores else 0.0

    # Build chart data dynamically so unselected categories are hidden entirely
    summary_scores, summary_labels, summary_colors = [], [], []
    
    if score_phys is not None:
        summary_scores.append(int(round(score_phys)))
        summary_labels.append("Physical")
        summary_colors.append(score_color(score_phys))
    if score_chem is not None:
        summary_scores.append(int(round(score_chem)))
        summary_labels.append("Chemical")
        summary_colors.append(score_color(score_chem))
    if score_bio is not None:
        summary_scores.append(int(round(score_bio)))
        summary_labels.append("Biological")
        summary_colors.append(score_color(score_bio))
        
    # Always append Overall at the bottom
    summary_scores.append(int(round(score_overall)))
    summary_labels.append("<b>OVERALL</b>")
    summary_colors.append(score_color(score_overall))

    summary_text = [f"{s}/100  |  {score_label(s)}" for s in summary_scores]
    text_positions = ["inside" if s >= 25 else "outside" for s in summary_scores]

    fig_summary = go.Figure(go.Bar(
        x=summary_scores,
        y=summary_labels,
        orientation='h',
        marker_color=summary_colors,
        text=summary_text,
        textposition=text_positions,
        insidetextanchor='middle',
        textfont=dict(color='white', size=15, family="Arial Black")
    ))

    fig_summary.update_layout(
        xaxis=dict(range=[0, 100], fixedrange=True, title="SHAPE Score", gridcolor="rgba(150,150,150,0.1)"),
        yaxis=dict(autorange="reversed", fixedrange=True),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=max(220, len(summary_labels) * 70),
        margin=dict(l=10, r=20, t=10, b=10)
    )
    
    st.plotly_chart(
        fig_summary,
        use_container_width=True,
        key=f"{k}_summary_chart",
        config={'displayModeBar': False}
    )

 # ── INDIVIDUAL INDICATOR SUMMARY TABLE ──
    table_rows = []
    cat_map = {
        "Bulk Density": "Physical", "Macroaggregate Stability": "Physical", 
        "Available Water Capacity": "Physical", "Water-Filled Pore Space": "Physical",
        "pH": "Chemical", "Soil Phosphorus": "Chemical", "Extractable Potassium": "Chemical",
        "Electrical Conductivity": "Chemical", "Sodium Adsorption Ratio": "Chemical",
        "Soil Organic Carbon": "Biological", "SMAF Soil Organic Carbon": "Biological", 
        "Potentially Mineralizable Nitrogen": "Biological", "Microbial Biomass Carbon": "Biological","Beta-glucosidase": "Biological"
    }
    
    for ind in target_indicators:
        cat = cat_map.get(ind, "General")
        val, scr = "—", 0.0
        
        if ind == "Bulk Density":
            val = f"{bd_val_sum} g/cm³"
            scr = run_smaf_bd_score(bd_val_sum, texture_id_sum, mineralogy_id_sum)
        elif ind == "Macroaggregate Stability":
            val = f"{agg_val_sum}%"
            scr = run_smaf_agg_score(agg_val_sum, om_id_sum, texture_id_sum, fe_id_sum, SMAF_DATA)
        elif ind == "Available Water Capacity":
            val = f"{awc_val_sum} g/g"
            awc_region_sum = st.session_state.get(f"{k}_awc_region", 2)
            scr = run_smaf_awc_score(awc_val_sum, awc_region_sum, texture_id_sum, om_id_sum, SMAF_DATA)
        elif ind == "Water-Filled Pore Space":
            val = f"{wfps_frac_sum:.1%}"
            wfps_res = run_smaf_wfps_score(wfps_frac_sum, texture_id_sum, SMAF_DATA)
            scr = wfps_res["combined"]
        elif ind == "pH":
            val = f"{ph_val_sum}"
            crop_id_sum = SMAF_DATA.get("crop_ui_map", {}).get(st.session_state.get(f"{k}_sm_crop", "").lower(), 82)
            scr = run_smaf_ph_score(ph_val_sum, crop_id_sum, SMAF_DATA)

        elif ind == "Soil Phosphorus":
            val = f"{p_val_sum} mg/kg"
            crop_id_sum = SMAF_DATA["crop_ui_map"].get(st.session_state.get(f"{k}_sm_crop", "").lower(), 0)
            method_str = st.session_state.get(f"{k}_sm_method", "Mehlich-3")
            weather_str = st.session_state.get(f"{k}_sm_weather", "Slightly Weathered")
            method_id_sum = SMAF_METHOD_MAP.get(method_str, 2)
            weather_id_sum = SMAF_WEATHERING_MAP.get(weather_str, 3)
            slope_str = st.session_state.get(f"{k}_sm_slope", "0–2% Level Slope")
            slope_id_sum = SMAF_SLOPE_MAP.get(slope_str, 1)
            oc_val_sum = st.session_state.get(f"{k}_oc", 2.0)
            scr = run_smaf_p_score(p_val_sum, crop_id_sum, method_id_sum, weather_id_sum, texture_id_sum, slope_id_sum, oc_val_sum)
        elif ind == "Electrical Conductivity":
            val = f"{ec_val_sum} dS/m"
            ec_method_str_sum = st.session_state.get(f"{k}_ec_method", "Saturated Paste (ECsat)")
            ec_method_id_sum = 1 if "Saturated Paste" in ec_method_str_sum else 2
            crop_id_sum = SMAF_DATA["crop_ui_map"].get(st.session_state.get(f"{k}_sm_crop", "").lower(), 0)
            scr = run_smaf_ec_score(ec_val_sum, crop_id_sum, ec_method_id_sum, texture_id_sum, SMAF_DATA)
        elif ind == "Sodium Adsorption Ratio":
            val = f"{sar_val_sum}"
            ec_method_str_sum = st.session_state.get(f"{k}_ec_method", "Saturated Paste (ECsat)")
            ec_method_id_sum = 1 if "Saturated Paste" in ec_method_str_sum else 2
            scr = run_smaf_sar_score(sar_val_sum, ec_val_sum, ec_method_id_sum, texture_id_sum, SMAF_DATA)
        elif ind == "Soil Organic Carbon":
            val = f"{oc_val}%"
            scr = compute_score(oc_val, lp_mean, sigma_val)
        elif ind == "SMAF Soil Organic Carbon":
            val = f"{oc_val}%"
            scr = run_smaf_soc_score(oc_val, om_id_sum, texture_id_sum, climate_id_sum, SMAF_DATA)
        elif ind == "Potentially Mineralizable Nitrogen":
            val = f"{pmn_val_sum} mg/kg"
            scr = run_smaf_pmn_score(pmn_val_sum, om_id_sum, texture_id_sum, climate_id_sum, SMAF_DATA)

        elif ind == "Beta-glucosidase":
            val = f"{bg_val_sum} mg/kg/hr"
            scr = run_smaf_bg_score(bg_val_sum, om_id_sum, texture_id_sum, climate_id_sum, SMAF_DATA)

        elif ind == "Extractable Potassium":
            val = f"{k_val_sum} mg/kg"
            scr = run_smaf_exk_score(k_val_sum, texture_id_sum, SMAF_DATA)
            
        elif ind == "Microbial Biomass Carbon":
            val = f"{mbc_val_sum} mg/kg"
            season_name = st.session_state.get(f"{k}_sm_season", "Spring")
            season_num = {"Spring": 1, "Summer": 2, "Fall": 3, "Winter": 4}.get(season_name, 1)
            season_climate_code = 1.0 if season_num == 1 else float(f"{season_num}.{climate_id_sum}")
            scr = run_smaf_mbc_score(mbc_val_sum, om_id_sum, texture_id_sum, season_climate_code, SMAF_DATA)
            
        zone = score_label(scr)
        table_rows.append({
            "Category": cat,
            "Indicator Name": ind,
            "Measured Value": val,
            "Score": f"{int(round(scr))}/100",
            "Rating": zone,
            "_raw_score": scr
        })
        
    if table_rows:
        df_summary_table = pd.DataFrame(table_rows)
        
        def color_table_rows(row):
            # Pull the score safely using the row's index position in the dataframe
            idx = row.name
            s = df_summary_table.loc[idx, "_raw_score"]
            
            if s >= 80: bg = "background-color: rgba(26, 150, 65, 0.25); font-weight: 500;"
            elif s >= 60: bg = "background-color: rgba(119, 195, 92, 0.25); font-weight: 500;"
            elif s >= 40: bg = "background-color: rgba(255, 193, 7, 0.25); font-weight: 500;"
            elif s >= 20: bg = "background-color: rgba(244, 109, 67, 0.25); font-weight: 500;"
            else: bg = "background-color: rgba(215, 48, 39, 0.25); font-weight: 500;"
            return [bg] * len(row)
            
        display_table_df = df_summary_table.drop(columns=["_raw_score"])
        st.dataframe(
            display_table_df.style.apply(color_table_rows, axis=1),
            width='stretch',
            hide_index=True
        )
    st.divider()

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
        # ✨ THE FIX: Skip this pillar entirely if no indicators were selected for it
        if s_val is None:
            continue
            
        score_int = int(round(s_val))
        if score_int < 20:
            diag_rows.append({"Pillar": pillar, "Score": score_int, "Assessment": "🔴 Very Low", "Critical Soil Functions Affected": CONSTRAINTS[pillar]["VeryLow"]})
        elif score_int < 40:
            diag_rows.append({"Pillar": pillar, "Score": score_int, "Assessment": "🔴 Low", "Critical Soil Functions Affected": CONSTRAINTS[pillar]["Low"]})
        elif score_int < 60:
            diag_rows.append({"Pillar": pillar, "Score": score_int, "Assessment": "🟠 Medium", "Critical Soil Functions Affected": CONSTRAINTS[pillar]["Medium"]})

    # 3. Render natively using Streamlit
    if len(diag_rows) == 0:
        st.success("Congratulations! All measured soil health pillars scored High (>= 60), indicating fully functional soil systems that are unrestricted by major soil function constraints.")
    else:
        # Convert to Pandas DataFrame for clean rendering
        df_diag = pd.DataFrame(diag_rows)
        
        # Use st.table() so the text wraps nicely on multiple lines
        st.table(df_diag)
        
    st.divider()

    # ── INDICATOR SELECTION DROPDOWN (Correctly positioned below summary) ──
    chosen_indicator = st.selectbox(
        "Soil Health Indicators:",
        target_indicators,
        key=f"{cfg['key']}_indicator_shared"
    )
# ALWAYS calculate the SOC score in the background so the Recommendation Engine 
# and Carbon Calculator at the bottom of the page don't crash when switching tabs!
    score = compute_score(oc_val, lp_mean, sigma_val)
    # Safely grab the target percentile from the slider (default to 90 if it doesn't exist)
    target_pct = st.session_state.get(f"{k}_target_pct", 90)

        # Safely calculate Target SOC ONCE for the entire sample
    try:
        tgt_oc = percentile_to_oc(target_pct, lp_mean, sigma_val)
    except (NameError, TypeError, ValueError):
        tgt_oc = 0.0
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
            
        bd_val = st.session_state.get(f"{k}_bd", 1.45)
        
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
            
            # Plot the Combined (50/50) curve smoothly to match the gauge
            xs = np.linspace(0, 1.0, 300)
            ys_combined = []
            for x in xs:
                res = run_smaf_wfps_score(x, texture_id, SMAF_DATA)
                ys_combined.append(res["combined"] / 100.0)
            
            fig_wfps = go.Figure()
            
            # Combined Curve (Solid Line)
            fig_wfps.add_trace(go.Scatter(
                x=xs, y=ys_combined, mode="lines", 
                line=dict(color="#356B8C", width=3), 
                name="Score Curve", hovertemplate="WFPS: %{x:.0%}<br>Score: %{y:.0%}<extra></extra>"
            ))
            
            # Your Soil Data Point (Single point)
            fig_wfps.add_trace(go.Scatter(
                x=[wfps_frac], 
                y=[score_wfps / 100.0], 
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
    
    elif chosen_indicator == "Microbial Biomass Carbon":
        # 1. Grab Global Variables
        texture_id = SMAF_TEXTURE_MAP.get(st.session_state.get(f"{k}_sm_tex", ""), 2)
        om_string = st.session_state.get(f"{k}_sm_om_class", "Class 2 (Med-High OM)")
        om_id = SMAF_OM_MAP.get(om_string, 2)
        
        season_name = st.session_state.get(f"{k}_sm_season", "Spring")
        season_num = {"Spring": 1, "Summer": 2, "Fall": 3, "Winter": 4}.get(season_name, 1)
        climate_id = SMAF_CLIMATE_MAP.get(st.session_state.get(f"{k}_sm_climate_class", ""), 3)
        season_climate_code = 1.0 if season_num == 1 else float(f"{season_num}.{climate_id}")
        
        # 2. Calculate Score securely
        raw_score_mbc = run_smaf_mbc_score(mbc_val, om_id, texture_id, season_climate_code, SMAF_DATA)
        try:
            score_mbc = float(raw_score_mbc) if raw_score_mbc is not None else 0.0
        except (ValueError, TypeError):
            score_mbc = 0.0
            
        mbc_color = score_color(score_mbc)
        mbc_label = score_label(score_mbc)
        
        # 3. Create the 1:2 Column Layout
        col_l, col_r = st.columns([1, 2])
        
        with col_l:
            gauge_title = f"<b style='font-size:17px; color:#333;'>{mbc_label}</b><br><span style='font-size:11px; color:#555;'>Measured MBC: {mbc_val} mg/kg</span>"
            fig_mbc_gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=int(round(score_mbc)),
                title={"text": gauge_title, "font": {"size": 13}},
                number={"suffix": "/100", "font": {"size": 38, "color": mbc_color}},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#555", "tickvals": [0, 20, 40, 60, 80, 100]},
                    "bar": {"color": mbc_color, "thickness": 0.28},
                    "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
                    "steps": [
                        {"range": [0, 20], "color": "rgba(215,48,39,0.85)"},
                        {"range": [20, 40], "color": "rgba(244,109,67,0.85)"},
                        {"range": [40, 60], "color": "rgba(255,193,7,0.85)"},
                        {"range": [60, 80], "color": "rgba(119,195,92,0.85)"},
                        {"range": [80, 100], "color": "rgba(26,150,65,0.85)"}
                    ],
                    "threshold": {"line": {"color": mbc_color, "width": 5}, "thickness": 0.8, "value": score_mbc}
                }
            ))
            fig_mbc_gauge.update_layout(font=dict(color="#333"), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=260, margin=dict(l=20, r=20, t=80, b=10))
            st.plotly_chart(fig_mbc_gauge, use_container_width=True, key=f"{k}_mbc_gauge_plot")
            
        with col_r:
            st.markdown("#### Scoring Curve")
            
            # ✨ Dynamically re-calculates the curve using the active OM class!
            xs = np.linspace(0, 1000, 300)
            ys = [run_smaf_mbc_score(x, om_id, texture_id, season_climate_code, SMAF_DATA) for x in xs]
            
            fig_mbc = go.Figure()
            fig_mbc.add_trace(go.Scatter(
                x=xs, y=np.array(ys) / 100.0, mode="lines", 
                line=dict(color="#8C5A9E", width=3), 
                name="Score Curve", hovertemplate="MBC: %{x:.0f} mg/kg<br>Score: %{y:.0%}<extra></extra>"
            ))
            
            fig_mbc.add_trace(go.Scatter(
                x=[mbc_val], y=[score_mbc / 100.0], mode="markers", 
                marker=dict(color=mbc_color, size=14, line=dict(color="white", width=2)), 
                name="Your Soil"
            ))
            
            fig_mbc.update_layout(
                xaxis_title="Microbial Biomass Carbon (mg/kg)", 
                yaxis_title="SHAPE Score",
                yaxis=dict(range=[0, 1.05], tickformat=".0%"), xaxis=dict(range=[0, 1000]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", 
                height=400, margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig_mbc, width='stretch', key=f"{k}_mbc_curve_plot")

        # ── 5-TIER MBC RECOMMENDATION ENGINE ──
        st.markdown("### 📋 Agronomic Recommendations")

        if score_mbc >= 80:
            mbc_level = "Very High"
            mbc_rec = "Your soil supports an incredibly active and thriving microbial population. This robust living biomass acts as a massive 'bank' for nutrients, rapidly turning over organic matter and preventing nutrient loss to leaching."
        elif score_mbc >= 60:
            mbc_level = "High"
            mbc_rec = "Your microbial biomass levels indicate healthy biological functioning. The soil microbes are actively mediating nutrient availability and contributing to soil structure. Keep minimizing soil disturbance to protect them."
        elif score_mbc >= 40:
            mbc_level = "Medium"
            mbc_rec = "Your microbial biomass is moderate. The biological engine of your soil is functioning but isn't operating at full capacity. Consider diversifying your crop rotations or adding high-quality compost to stimulate microbial growth."
        elif score_mbc >= 20:
            mbc_level = "Low"
            mbc_rec = "Your soil biology is sluggish. Low microbial biomass means fewer nutrients are being actively cycled, likely forcing a higher dependence on synthetic fertilizers. Adopt practices that 'feed the soil' with continuous living roots."
        else:
            mbc_level = "Very Low"
            mbc_rec = "Critical biological limitation. Your soil is biologically depleted, likely due to heavy tillage, lack of organic inputs, or extended fallow periods. Immediate incorporation of organic amendments and cover cropping is needed to revive the soil food web."

        st.info(f"**Score Tier: {mbc_level}**\n\n{mbc_rec}")

    elif chosen_indicator == "Beta-glucosidase":
        # 1. Grab Global Variables
        texture_id = SMAF_TEXTURE_MAP.get(st.session_state.get(f"{k}_sm_tex", ""), 2)
        om_string = st.session_state.get(f"{k}_sm_om_class", "Class 2 (Med-High OM)")
        om_id = SMAF_OM_MAP.get(om_string, 2)
        climate_id = SMAF_CLIMATE_MAP.get(st.session_state.get(f"{k}_sm_climate_class", ""), 3)
        
        # 2. Calculate Score
        raw_score_bg = run_smaf_bg_score(bg_val, om_id, texture_id, climate_id, SMAF_DATA)
        try:
            score_bg = float(raw_score_bg) if raw_score_bg is not None else 0.0
        except (ValueError, TypeError):
            score_bg = 0.0
            
        bg_color = score_color(score_bg)
        bg_label = score_label(score_bg)
        
        # 3. Layout
        col_l, col_r = st.columns([1, 2])
        
        with col_l:
            gauge_title = f"<b style='font-size:17px; color:#333;'>{bg_label}</b><br><span style='font-size:11px; color:#555;'>Measured BG: {bg_val} mg/kg/hr</span>"
            fig_bg_gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=int(round(score_bg)),
                title={"text": gauge_title, "font": {"size": 13}},
                number={"suffix": "/100", "font": {"size": 38, "color": bg_color}},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#555", "tickvals": [0, 20, 40, 60, 80, 100]},
                    "bar": {"color": bg_color, "thickness": 0.28},
                    "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
                    "steps": [
                        {"range": [0, 20], "color": "rgba(215,48,39,0.85)"},
                        {"range": [20, 40], "color": "rgba(244,109,67,0.85)"},
                        {"range": [40, 60], "color": "rgba(255,193,7,0.85)"},
                        {"range": [60, 80], "color": "rgba(119,195,92,0.85)"},
                        {"range": [80, 100], "color": "rgba(26,150,65,0.85)"}
                    ],
                    "threshold": {"line": {"color": bg_color, "width": 5}, "thickness": 0.8, "value": score_bg}
                }
            ))
            fig_bg_gauge.update_layout(font=dict(color="#333"), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=260, margin=dict(l=20, r=20, t=80, b=10))
            st.plotly_chart(fig_bg_gauge, use_container_width=True, key=f"{k}_bg_gauge_plot")
            
        with col_r:
            st.markdown("#### Scoring Curve")
            xs = np.linspace(0, 1250, 300)
            ys = [run_smaf_bg_score(x, om_id, texture_id, climate_id, SMAF_DATA) for x in xs]
            
            fig_bg = go.Figure()
            fig_bg.add_trace(go.Scatter(
                x=xs, y=np.array(ys) / 100.0, mode="lines", 
                line=dict(color="#4C7A3F", width=3), 
                name="Score Curve", hovertemplate="BG: %{x:.0f} mg/kg/hr<br>Score: %{y:.0%}<extra></extra>"
            ))
            fig_bg.add_trace(go.Scatter(
                x=[bg_val], y=[score_bg / 100.0], mode="markers", 
                marker=dict(color=bg_color, size=14, line=dict(color="white", width=2)), 
                name="Your Soil"
            ))
            fig_bg.update_layout(
                xaxis_title="Beta-glucosidase activity (mg PNP / kg / hr)", 
                yaxis_title="SHAPE Score",
                yaxis=dict(range=[0, 1.05], tickformat=".0%"), xaxis=dict(range=[0, 1250]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", 
                height=400, margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig_bg, width='stretch', key=f"{k}_bg_curve_plot")

        # ── 5-TIER BG RECOMMENDATION ENGINE ──
        st.markdown("### 📋 Agronomic Recommendations")
        if score_bg >= 80:
            bg_level = "Very High"
            bg_rec = "Your soil demonstrates optimal carbon cycling and robust enzyme activity. The microbial community is highly efficient at breaking down crop residues and organic matter, rapidly releasing energy to the soil food web. Continue minimal disturbance and high-residue practices."
        elif score_bg >= 60:
            bg_level = "High"
            bg_rec = "Your Beta-glucosidase levels indicate healthy, active carbon turnover. Soil microbes are successfully processing organic inputs. Maintain continuous living roots and varied crop rotations to feed the microbiome."
        elif score_bg >= 40:
            bg_level = "Medium"
            bg_rec = "Your soil's enzyme activity is moderate, suggesting that the breakdown of organic matter is somewhat constrained. Consider incorporating high-biomass cover crops or organic amendments (like manure or compost) to stimulate the biological engine."
        elif score_bg >= 20:
            bg_level = "Low"
            bg_rec = "Your Beta-glucosidase levels are low, indicating sluggish carbon cycling. Crop residues are likely breaking down very slowly. Adopt practices that increase organic carbon inputs and reduce tillage to rebuild the microbial population."
        else:
            bg_level = "Very Low"
            bg_rec = "Critical biological limitation. Your soil exhibits severely degraded enzyme activity, meaning carbon cycling has nearly stalled. This is typically caused by extreme physical compaction, chemical toxicity, or prolonged fallow periods. Immediate incorporation of diverse living roots and organic inputs is required."

        st.info(f"**Score Tier: {bg_level}**\n\n{bg_rec}")

    elif chosen_indicator == "SMAF Soil Organic Carbon":
        # 1. Grab Global Variables
        texture_id = SMAF_TEXTURE_MAP.get(st.session_state.get(f"{k}_sm_tex", ""), 2)
        om_string = st.session_state.get(f"{k}_sm_om_class", "Class 2 (Med-High OM)")
        om_id = SMAF_OM_MAP.get(om_string, 2)
        climate_id = SMAF_CLIMATE_MAP.get(st.session_state.get(f"{k}_sm_climate_class", ""), 3)
        
        # 2. Calculate Score securely
        raw_score_smaf_soc = run_smaf_soc_score(oc_val, om_id, texture_id, climate_id, SMAF_DATA)
        try:
            score_smaf_soc = float(raw_score_smaf_soc) if raw_score_smaf_soc is not None else 0.0
        except (ValueError, TypeError):
            score_smaf_soc = 0.0
            
        smaf_soc_color = score_color(score_smaf_soc)
        smaf_soc_label = score_label(score_smaf_soc)
        
        # 3. Create the 1:2 Column Layout
        col_l, col_r = st.columns([1, 2])
        
        with col_l:
            gauge_title = f"<b style='font-size:17px; color:#333;'>{smaf_soc_label}</b><br><span style='font-size:11px; color:#555;'>Measured SOC: {oc_val}% (SMAF Logistic)</span>"
            fig_smaf_soc_gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=int(round(score_smaf_soc)),
                title={"text": gauge_title, "font": {"size": 13}},
                number={"suffix": "/100", "font": {"size": 38, "color": smaf_soc_color}},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#555", "tickvals": [0, 20, 40, 60, 80, 100]},
                    "bar": {"color": smaf_soc_color, "thickness": 0.28},
                    "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
                    "steps": [
                        {"range": [0, 20], "color": "rgba(215,48,39,0.85)"},
                        {"range": [20, 40], "color": "rgba(244,109,67,0.85)"},
                        {"range": [40, 60], "color": "rgba(255,193,7,0.85)"},
                        {"range": [60, 80], "color": "rgba(119,195,92,0.85)"},
                        {"range": [80, 100], "color": "rgba(26,150,65,0.85)"}
                    ],
                    "threshold": {"line": {"color": smaf_soc_color, "width": 5}, "thickness": 0.8, "value": score_smaf_soc}
                }
            ))
            fig_smaf_soc_gauge.update_layout(font=dict(color="#333"), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=260, margin=dict(l=20, r=20, t=80, b=10))
            st.plotly_chart(fig_smaf_soc_gauge, use_container_width=True, key=f"{k}_smaf_soc_gauge_plot")
            
            st.divider()
            st.markdown("**📥 Export result**")
            result_df = pd.DataFrame([{
                "Indicator": "SMAF Soil Organic Carbon",
                "SOC_pct": oc_val, "SMAF_Score": round(score_smaf_soc, 2), "Zone": smaf_soc_label
            }])
            st.download_button("⬇️ Download as CSV", data=result_df.to_csv(index=False).encode("utf-8"),
                               file_name=f"SMAF_{cfg['key']}_{tax}_{tex}_{oc_val}pct.csv",
                               mime="text/csv", width='stretch', key=f"{k}_export_btn_smaf_unique")

        with col_r:
            st.markdown("#### Scoring Curve (SMAF Logistic)")
            
            # Smooth plotting using linspace
            xs = np.linspace(0, 5.0, 300)
            ys = [run_smaf_soc_score(x, om_id, texture_id, climate_id, SMAF_DATA) for x in xs]
            
            fig_smaf_soc = go.Figure()
            fig_smaf_soc.add_trace(go.Scatter(
                x=xs, y=np.array(ys) / 100.0, mode="lines", 
                line=dict(color="#5C4033", width=3), 
                name="Score Curve", hovertemplate="SOC: %{x:.2f}%<br>Score: %{y:.0%}<extra></extra>"
            ))
            
            fig_smaf_soc.add_trace(go.Scatter(
                x=[oc_val], y=[score_smaf_soc / 100.0], mode="markers", 
                marker=dict(color=smaf_soc_color, size=14, line=dict(color="white", width=2)), 
                name="Your Soil"
            ))
            
            fig_smaf_soc.update_layout(
                xaxis_title="Total Organic Carbon (%)", 
                yaxis_title="Score",
                yaxis=dict(range=[0, 1.05], tickformat=".0%"), xaxis=dict(range=[0, 5.0]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", 
                height=400, margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig_smaf_soc, width='stretch', key=f"{k}_smaf_soc_curve_plot")

            # ── MAP RENDERER ──
            if use_geo and f"{k}_lat" in st.session_state and in_bounds(lat_in, lon_in, cfg):
                st.markdown("#### Site Location")
                st.map(pd.DataFrame({"lat": [lat_in], "lon": [lon_in]}), zoom=6)

        st.divider()
        # 🚦 THE TRAFFIC COP: Route SMAF SOC score to the Excel Recommendation Engine
        render_excel_recommendation_engine(region_name, chosen_crop, score_smaf_soc, key_prefix=f"{k}_smaf_soc_tab")

    elif chosen_indicator == "Extractable Potassium":
        # 1. Grab Global Variables
        texture_id = SMAF_TEXTURE_MAP[st.session_state[f"{k}_sm_tex"]]
        
        # 2. Calculate Score
        raw_score_exk = run_smaf_exk_score(k_val, texture_id, SMAF_DATA)
        try:
            score_exk = float(raw_score_exk) if raw_score_exk is not None else 0.0
        except (ValueError, TypeError):
            score_exk = 0.0
            
        exk_color = score_color(score_exk)
        exk_label = score_label(score_exk)
        
        # 3. Layout
        col_l, col_r = st.columns([1, 2])
        
        with col_l:
            gauge_title = f"<b style='font-size:17px; color:#333;'>{exk_label}</b><br><span style='font-size:11px; color:#555;'>Measured K: {k_val} mg/kg</span>"
            fig_exk_gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=int(round(score_exk)),
                title={"text": gauge_title, "font": {"size": 13}},
                number={"suffix": "/100", "font": {"size": 38, "color": exk_color}},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#555", "tickvals": [0, 20, 40, 60, 80, 100]},
                    "bar": {"color": exk_color, "thickness": 0.28},
                    "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
                    "steps": [
                        {"range": [0, 20], "color": "rgba(215,48,39,0.85)"},
                        {"range": [20, 40], "color": "rgba(244,109,67,0.85)"},
                        {"range": [40, 60], "color": "rgba(255,193,7,0.85)"},
                        {"range": [60, 80], "color": "rgba(119,195,92,0.85)"},
                        {"range": [80, 100], "color": "rgba(26,150,65,0.85)"}
                    ],
                    "threshold": {"line": {"color": exk_color, "width": 5}, "thickness": 0.8, "value": score_exk}
                }
            ))
            fig_exk_gauge.update_layout(font=dict(color="#333"), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=260, margin=dict(l=20, r=20, t=80, b=10))
            st.plotly_chart(fig_exk_gauge, use_container_width=True, key=f"{k}_exk_gauge_plot")
            
        with col_r:
            st.markdown("#### Scoring Curve")
            xs = np.linspace(0, 400, 300)
            ys = [run_smaf_exk_score(x, texture_id, SMAF_DATA) for x in xs]
            
            fig_exk = go.Figure()
            fig_exk.add_trace(go.Scatter(
                x=xs, y=np.array(ys) / 100.0, mode="lines", 
                line=dict(color="#1E6B52", width=3), 
                name="Score Curve", hovertemplate="K: %{x:.0f} mg/kg<br>Score: %{y:.0%}<extra></extra>"
            ))
            fig_exk.add_trace(go.Scatter(
                x=[k_val], y=[score_exk / 100.0], mode="markers", 
                marker=dict(color=exk_color, size=14, line=dict(color="white", width=2)), 
                name="Your Soil"
            ))
            fig_exk.update_layout(
                xaxis_title="Extractable Potassium (mg/kg)", 
                yaxis_title="SHAPE Score",
                yaxis=dict(range=[0, 1.05], tickformat=".0%"), xaxis=dict(range=[0, 400]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", 
                height=400, margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig_exk, width='stretch', key=f"{k}_exk_curve_plot")

        # ── 5-TIER EX-K RECOMMENDATION ENGINE ──
        st.markdown("### 📋 Agronomic Recommendations")
        if score_exk >= 80:
            k_level = "Very High"
            k_rec = "Your soil potassium levels are highly optimal. Sufficient potassium is available to regulate plant stomata, maintain drought resistance, and support maximum crop yields. No additional potash applications are required at this time."
        elif score_exk >= 60:
            k_level = "High"
            k_rec = "Your soil potassium is adequate for general crop production. You should maintain these levels through routine maintenance applications matching annual crop removal rates."
        elif score_exk >= 40:
            k_level = "Medium"
            k_rec = "Your soil potassium levels are moderate and may occasionally become limiting, particularly during dry periods or late-season pod/grain fill. Consider a targeted potash application based on local extension recommendations."
        elif score_exk >= 20:
            k_level = "Low"
            k_rec = "Your extractable potassium is deficient. Crops will likely suffer from reduced drought tolerance, weaker stalk strength, and diminished yields. A corrective application of a potassium fertilizer is recommended."
        else:
            k_level = "Very Low"
            k_rec = "Critical nutrient limitation. Your soil potassium is severely depleted, which will result in stunted growth, high susceptibility to diseases, and major yield penalties. An immediate, soil-test guided corrective application of potash is strongly advised."

        st.info(f"**Score Tier: {k_level}**\n\n{k_rec}")
        
    elif chosen_indicator == "pH":
        # 1. Grab Live Variables
        ph_val = st.session_state.get(f"{k}_ph", 6.0)
        selected_crop_input = st.session_state.get(f"{k}_sm_crop", "").lower()
        crop_id = SMAF_DATA.get("crop_ui_map", {}).get(selected_crop_input, 82) # Defaults to Soybean
        
        # 2. Calculate Score
        score_ph = run_smaf_ph_score(ph_val, crop_id, SMAF_DATA)
        ph_color = score_color(score_ph)
        ph_label = score_label(score_ph)
        
        # 3. Create Layout
        col_l, col_r = st.columns([1, 2])
        
        with col_l:
            gauge_title = f"<b style='font-size:17px; color:#333;'>{ph_label}</b><br><span style='font-size:11px; color:#555;'>Measured pH: {ph_val} (2:1 Water)</span>"
            fig_ph_gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=int(round(score_ph)),
                title={"text": gauge_title, "font": {"size": 13}},
                number={"suffix": "/100", "font": {"size": 38, "color": ph_color}},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#555"},
                    "bar": {"color": ph_color, "thickness": 0.28},
                    "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
                    "steps": [
                        {"range": [0, 20], "color": "rgba(215,48,39,0.85)"},
                        {"range": [20, 40], "color": "rgba(244,109,67,0.85)"},
                        {"range": [40, 60], "color": "rgba(255,193,7,0.85)"},
                        {"range": [60, 80], "color": "rgba(119,195,92,0.85)"},
                        {"range": [80, 100], "color": "rgba(26,150,65,0.85)"}
                    ],
                    "threshold": {"line": {"color": ph_color, "width": 5}, "thickness": 0.8, "value": score_ph}
                }
            ))
            fig_ph_gauge.update_layout(font=dict(color="#333"), paper_bgcolor="rgba(0,0,0,0)", height=260, margin=dict(l=20, r=20, t=80, b=10))
            st.plotly_chart(fig_ph_gauge, use_container_width=True, key=f"{k}_ph_gauge")
            
            st.divider()
            st.markdown("**📥 Export result**")
            result_df = pd.DataFrame([{"Indicator": "SMAF pH", "pH_Val": ph_val, "Score": round(score_ph, 2), "Zone": ph_label}])
            st.download_button("⬇️ Download as CSV", data=result_df.to_csv(index=False).encode("utf-8"),
                               file_name=f"SMAF_{cfg['key']}_pH_{ph_val}.csv", mime="text/csv", width='stretch', key=f"{k}_export_ph")

        with col_r:
            st.markdown("#### Scoring Curve")
            
            xs = np.linspace(3.5, 9.5, 300)
            ys = [run_smaf_ph_score(x, crop_id, SMAF_DATA) / 100.0 for x in xs]
            
            fig_ph_curve = go.Figure()
            fig_ph_curve.add_trace(go.Scatter(
                x=xs, y=ys, mode="lines", 
                line=dict(color="#8C3F5A", width=3), 
                name="Target Range", hovertemplate="pH: %{x:.2f}<br>Score: %{y:.0%}<extra></extra>"
            ))
            fig_ph_curve.add_trace(go.Scatter(
                x=[ph_val], y=[score_ph / 100.0], mode="markers", 
                marker=dict(color="#D1495B", size=14, line=dict(color="white", width=2)), 
                name="Your Soil"
            ))
            
            crop_name = SMAF_DATA.get("ph_crops", {}).get(crop_id, {}).get("name", "Target Crop")
            fig_ph_curve.update_layout(
                xaxis_title="Soil pH", yaxis_title="Score",
                yaxis=dict(range=[0, 1.05], tickformat=".0%"), xaxis=dict(range=[3.5, 9.5]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", 
                height=400, margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig_ph_curve, width='stretch', key=f"{k}_ph_curve")

        # ── 5-TIER pH RECOMMENDATION ENGINE ──
        st.markdown("### 📋 Agronomic Recommendations")
        opt_ph = SMAF_DATA.get("ph_crops", {}).get(crop_id, {}).get("b", 6.0)
        
        if ph_val > opt_ph:
            direction, amendment = "lower", "elemental sulfur or acidifying fertilizers"
        else:
            direction, amendment = "raise", "agricultural lime (calcium carbonate)"

        if score_ph >= 80:
            ph_level, ph_rec = "Very High", "Your soil pH is optimal for this crop, supporting maximum nutrient availability. Maintain current management practices."
        elif score_ph >= 60:
            ph_level, ph_rec = "High", "Your soil pH is adequate, though slightly outside the perfect optimum. Monitor in future seasons to ensure it doesn't drift further."
        elif score_ph >= 40:
            ph_level, ph_rec = "Medium", f"Your soil pH may be moderately limiting nutrient availability. Consider a targeted application of {amendment} to gradually {direction} the pH towards the {opt_ph} optimum."
        elif score_ph >= 20:
            ph_level, ph_rec = "Low", f"Your soil pH is likely limiting yield potential. An application of {amendment} is recommended to {direction} the pH."
        else:
            ph_level, ph_rec = "Very Low", f"Your soil pH is substantially outside the optimal range. A corrective application of {amendment} to {direction} the pH towards {opt_ph} is highly recommended."

        st.info(f"**Score Tier: {ph_level}**\n\n{ph_rec}")

    elif chosen_indicator == "Soil Organic Carbon":
        score  = compute_score(oc_val, lp_mean, sigma_val)
        color  = score_color(score)
        label  = score_label(score)

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

       # ── Carbon Sequestration Calculator (SHAPE Model Only) ──
        if "Soil Organic Carbon" in target_indicators:
            st.divider()
            st.markdown("### 🌍 Carbon Sequestration Calculator")
            st.markdown("Estimate carbon stock, sequestration gap, credit value, and time to target based on the benchmark above.")

            with st.expander("⚙️ Field & Market Parameters", expanded=True):
                cc1, cc2, cc3, cc4, cc5 = st.columns(5)
                with cc1:
                    field_area = st.number_input("Field area (acres)", min_value=1.0, max_value=100000.0, value=None, step=10.0, placeholder="—", key=f"{k}_area")
                with cc2:
                    bulk_density = st.number_input("Bulk density (g/cm³)", min_value=0.8, max_value=2.0, value=None, step=0.05, placeholder="—", key=f"{k}_bd_calc")
                with cc3:
                    depth_cm = st.number_input("Sampling depth (cm)", min_value=5, max_value=100, value=None, step=5, placeholder="—", key=f"{k}_depth")
                with cc4:
                    carbon_price = st.number_input("Carbon price ($/t CO₂e)", min_value=1.0, max_value=500.0, value=None, step=5.0, placeholder="—", key=f"{k}_price")
                with cc5:
                    annual_rate = st.number_input("Annual SOC gain (%/yr)", min_value=0.01, max_value=2.0, value=None, step=0.05, placeholder="—", key=f"{k}_rate")

            input_vars = [field_area, bulk_density, depth_cm, carbon_price, annual_rate]

            if None in input_vars:
                st.info("💡 Please fill in all **Field & Market Parameters** above to unlock your carbon stock and credit estimates.")
            else:
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
    target_indicators = st.session_state.get("target_indicators", [])
    selected_framework = st.session_state.get("selected_framework", "SMAF")

    st.markdown("#### Upload a CSV to score multiple samples at once")
    st.markdown("""
    <div class="info-box">
    <b>💡 Smart Override System:</b> Your CSV template includes columns for site conditions (Crop, Texture, etc.). If you fill them out, the app will score that specific row using the CSV data. If you leave a cell blank, the app will fall back to the <b>Site Inputs</b> currently selected in the UI.
    </div>
    """, unsafe_allow_html=True)

    # 1. Map Indicators to Clean CSV Column Names
    csv_col_map = {
        "Soil Organic Carbon": "soc_pct",
        "SMAF Soil Organic Carbon": "soc_pct",
        "pH": "ph_val",
        "Soil Phosphorus": "p_mg_kg",
        "Extractable Potassium": "k_mg_kg",
        "Electrical Conductivity": "ec_ds_m",
        "Sodium Adsorption Ratio": "sar_val",
        "Bulk Density": "bd_g_cm3",
        "Macroaggregate Stability": "agg_pct",
        "Available Water Capacity": "awc_g_g",
        "Water-Filled Pore Space": "wfps_frac",
        "Potentially Mineralizable Nitrogen": "pmn_mg_kg",
        "Microbial Biomass Carbon": "mbc_mg_kg",
        "Beta-glucosidase": "bg_mg_kg_hr"
    }

    # 2. Dynamically Build the CSV Template with Metadata Columns
    template_cols = {"sample_id": ["Site_A", "Site_B", "Site_C"]}
    template_cols["lat"] = [cfg["default_latlon"][0]] * 3
    template_cols["lon"] = [cfg["default_latlon"][1]] * 3
    
    # SHAPE Spatial Parameters
    if "Soil Organic Carbon" in target_indicators and selected_framework in ["SHAPE", "SHAPE + SMAF (Hybrid)"]:
        template_cols["peer_group_taxon"] = [parse_code(cfg["taxon_display"][0])] * 3
        template_cols["peer_group_texture"] = list(set(cfg["texture_map"].values()))[:3] if len(set(cfg["texture_map"].values())) >= 3 else ["T2"]*3
        template_cols["PRISM_tmea"] = [cfg["temp_default"]] * 3
        if has_precip: template_cols["PRISM_ppt"] = [cfg["precip_default"]] * 3

    # Dynamic SMAF Metadata Overrides (Only added if relevant indicators are checked)
    if any(ind in target_indicators for ind in ["Bulk Density", "Macroaggregate Stability", "Available Water Capacity", "Water-Filled Pore Space", "Soil Phosphorus", "Electrical Conductivity", "Sodium Adsorption Ratio", "Potentially Mineralizable Nitrogen", "Microbial Biomass Carbon", "Beta-glucosidase", "Extractable Potassium", "SMAF Soil Organic Carbon"]):
        template_cols["Texture"] = ["Sandy Loam (>8% clay) / Sandy Clay Loam / Loam"] * 3
    if any(ind in target_indicators for ind in ["Macroaggregate Stability", "Available Water Capacity", "Potentially Mineralizable Nitrogen", "Microbial Biomass Carbon", "Beta-glucosidase", "SMAF Soil Organic Carbon"]):
        template_cols["OM_Class"] = ["Class 2 (Med-High OM)"] * 3
    if any(ind in target_indicators for ind in ["pH", "Soil Phosphorus", "Electrical Conductivity"]):
        template_cols["Crop"] = ["Soybean"] * 3
    if "Soil Phosphorus" in target_indicators:
        template_cols["P_Method"] = ["Mehlich-3"] * 3
        template_cols["Weathering"] = ["Slightly Weathered"] * 3
    if "Electrical Conductivity" in target_indicators or "Sodium Adsorption Ratio" in target_indicators:
        template_cols["EC_Method"] = ["Saturated Paste (ECsat)"] * 3
    if any(ind in target_indicators for ind in ["Potentially Mineralizable Nitrogen", "Beta-glucosidase", "SMAF Soil Organic Carbon"]):
        template_cols["Climate_Class"] = ["Class 3 (Cool/Wet)"] * 3

    # Add Raw Lab Value columns
    for ind in target_indicators:
        col_name = csv_col_map.get(ind)
        if col_name and col_name not in template_cols:
            template_cols[col_name] = [0.0, 0.0, 0.0]

    template = pd.DataFrame(template_cols)

    # Render Download Button & Data Dictionary
    c_dl, c_dict = st.columns([1, 1])
    with c_dl:
        st.download_button(
            "⬇️ Download Custom CSV Template", 
            data=template.to_csv(index=False).encode("utf-8"),
            file_name=f"gSHAPE_batch_template.csv", 
            mime="text/csv",
            use_container_width=True, 
            key=f"{k}_template_btn"
        )
        
        # Inject realistic fake data for whatever indicators happen to be active!
        if st.button("✨ Try Demo Data", use_container_width=True, key=f"{k}_demo_btn"):
            demo_df = pd.DataFrame(template_cols)
            if "soc_pct" in demo_df.columns: demo_df["soc_pct"] = [1.2, 2.5, 4.8]
            if "ph_val" in demo_df.columns: demo_df["ph_val"] = [5.2, 6.5, 7.8]
            if "p_mg_kg" in demo_df.columns: demo_df["p_mg_kg"] = [10.0, 35.0, 150.0]
            if "k_mg_kg" in demo_df.columns: demo_df["k_mg_kg"] = [60.0, 140.0, 300.0]
            if "ec_ds_m" in demo_df.columns: demo_df["ec_ds_m"] = [0.5, 1.8, 4.2]
            if "sar_val" in demo_df.columns: demo_df["sar_val"] = [0.8, 3.5, 9.0]
            if "bd_g_cm3" in demo_df.columns: demo_df["bd_g_cm3"] = [1.70, 1.45, 1.10]
            if "agg_pct" in demo_df.columns: demo_df["agg_pct"] = [15.0, 45.0, 85.0]
            if "awc_g_g" in demo_df.columns: demo_df["awc_g_g"] = [0.05, 0.15, 0.25]
            if "wfps_frac" in demo_df.columns: demo_df["wfps_frac"] = [0.20, 0.60, 0.90]
            if "pmn_mg_kg" in demo_df.columns: demo_df["pmn_mg_kg"] = [8.0, 25.0, 60.0]
            if "mbc_mg_kg" in demo_df.columns: demo_df["mbc_mg_kg"] = [120.0, 350.0, 850.0]
            if "bg_mg_kg_hr" in demo_df.columns: demo_df["bg_mg_kg_hr"] = [80.0, 220.0, 550.0]
            st.session_state[f"{k}_batch_df"] = demo_df

    with c_dict:
        with st.expander("📖 View CSV Data Dictionary (Copy & Paste Reference)"):
            st.markdown("To use the **Smart Override**, your CSV cells must exactly match these phrases. Click the copy icon in the top right of any block to paste these into your spreadsheet as a reference!")
            
            if "Texture" in template.columns:
                st.markdown("**Texture:**")
                st.code('\n'.join(list(SMAF_TEXTURE_MAP.keys())), language="text")
            if "OM_Class" in template.columns:
                st.markdown("**OM_Class:**")
                st.code('\n'.join(list(SMAF_OM_MAP.keys())), language="text")
            if "Climate_Class" in template.columns:
                st.markdown("**Climate_Class:**")
                st.code('\n'.join(list(SMAF_CLIMATE_MAP.keys())), language="text")
            if "P_Method" in template.columns:
                st.markdown("**P_Method:**")
                st.code('\n'.join(list(SMAF_METHOD_MAP.keys())), language="text")
            if "Weathering" in template.columns:
                st.markdown("**Weathering:**")
                st.code('\n'.join(list(SMAF_WEATHERING_MAP.keys())), language="text")
            if "EC_Method" in template.columns:
                st.markdown("**EC_Method:**")
                st.code("Saturated Paste (ECsat)\n1:1 Soil:Water", language="text")
            if "Crop" in template.columns:
                st.markdown(f"**Crop ({len(MASTER_CROP_OPTIONS)} supported):**")
                st.code(', '.join(MASTER_CROP_OPTIONS), language="text")

    # 3. Handle File Upload
    uploaded = st.file_uploader("Upload your populated CSV", type="csv", key=f"{k}_uploader")
    if uploaded is not None:
        try:
            up_df = pd.read_csv(uploaded)
            up_df.columns = up_df.columns.str.strip()
            st.session_state[f"{k}_batch_df"] = up_df
        except Exception as e:
            st.error(f"Error reading file: {e}")

    batch = st.session_state.get(f"{k}_batch_df")

    # 4. Processing the Batch
    if batch is not None:
        # Grab UI Global Defaults (The Fallbacks)
        ui_texture_id = SMAF_TEXTURE_MAP.get(st.session_state.get(f"{k}_sm_tex", ""), 2)
        ui_om_id = SMAF_OM_MAP.get(st.session_state.get(f"{k}_sm_om_class", ""), 2)
        ui_climate_id = SMAF_CLIMATE_MAP.get(st.session_state.get(f"{k}_sm_climate_class", ""), 3)
        ui_fe_id = SMAF_FE_MAP.get(st.session_state.get(f"{k}_sm_fe_class", ""), 2)
        ui_crop_id = SMAF_DATA.get("crop_ui_map", {}).get(st.session_state.get(f"{k}_sm_crop", "").lower(), 0)
        ui_method_id = SMAF_METHOD_MAP.get(st.session_state.get(f"{k}_sm_method", ""), 2)
        ui_weather_id = SMAF_WEATHERING_MAP.get(st.session_state.get(f"{k}_sm_weather", ""), 3)
        ui_slope_id = SMAF_SLOPE_MAP.get(st.session_state.get(f"{k}_sm_slope", ""), 1)
        ui_ec_method_id = 1 if "Saturated Paste" in st.session_state.get(f"{k}_ec_method", "") else 2
        
        season_name = st.session_state.get(f"{k}_sm_season", "Spring")
        season_num = {"Spring": 1, "Summer": 2, "Fall": 3, "Winter": 4}.get(season_name, 1)
        
        ui_awc_region = st.session_state.get(f"{k}_awc_region", 2)
        mineral_str = st.session_state.get(f"{k}_bd_min", "— Select —")
        ui_mineralogy_id = SMAF_MINERALOGY_MAP.get(mineral_str, 0) if mineral_str != "— Select —" else 0

        # Initialize tracking arrays for SHAPE SOC targets
        tgt_ocs = []
        score_columns = []

        # Initialize result columns in the dataframe
        for ind in target_indicators:
            batch[f"{ind} Score"] = np.nan
            score_columns.append(f"{ind} Score")

        # Loop through rows and score!
        for index, r in batch.iterrows():
            
            # Extract row metadata if it exists, otherwise use the UI fallback
            r_tex = str(r.get("Texture", "")).strip()
            row_texture_id = SMAF_TEXTURE_MAP.get(r_tex, ui_texture_id) if r_tex and r_tex != "nan" else ui_texture_id
            
            r_om = str(r.get("OM_Class", "")).strip()
            row_om_id = SMAF_OM_MAP.get(r_om, ui_om_id) if r_om and r_om != "nan" else ui_om_id

            r_crop = str(r.get("Crop", "")).strip().lower()
            row_crop_id = SMAF_DATA.get("crop_ui_map", {}).get(r_crop, ui_crop_id) if r_crop and r_crop != "nan" else ui_crop_id

            r_clim = str(r.get("Climate_Class", "")).strip()
            row_climate_id = SMAF_CLIMATE_MAP.get(r_clim, ui_climate_id) if r_clim and r_clim != "nan" else ui_climate_id
            row_season_climate = 1.0 if season_num == 1 else float(f"{season_num}.{row_climate_id}")

            r_pmeth = str(r.get("P_Method", "")).strip()
            row_method_id = SMAF_METHOD_MAP.get(r_pmeth, ui_method_id) if r_pmeth and r_pmeth != "nan" else ui_method_id
            
            r_weath = str(r.get("Weathering", "")).strip()
            row_weather_id = SMAF_WEATHERING_MAP.get(r_weath, ui_weather_id) if r_weath and r_weath != "nan" else ui_weather_id

            r_ecmeth = str(r.get("EC_Method", "")).strip()
            row_ec_method_id = 1 if "Saturated Paste" in r_ecmeth else (2 if "1:1" in r_ecmeth else ui_ec_method_id)

            # --- EXECUTE SCORING MATH ---
            
            # SHAPE SOC 
            if "Soil Organic Carbon" in target_indicators and selected_framework in ["SHAPE", "SHAPE + SMAF (Hybrid)"]:
                if all(col in r for col in ["oc", "peer_group_taxon", "peer_group_texture", "PRISM_tmea"]) or all(col in r for col in ["soc_pct", "peer_group_taxon", "peer_group_texture", "PRISM_tmea"]):
                    oc_val = safe_float(r.get("soc_pct", r.get("oc")))
                    row_b = get_params_any(cfg, df, str(r["peer_group_taxon"]).strip(), str(r["peer_group_texture"]).strip(), float(r["PRISM_tmea"]), float(r.get("PRISM_ppt", 0)) if has_precip else None)
                    if row_b is not None:
                        lp_b = float(row_b["mean_lp"])
                        sig_b = float(np.exp(row_b["mean_sigma"]))
                        s = compute_score(oc_val, lp_b, sig_b)
                        batch.at[index, "Soil Organic Carbon Score"] = round(s, 1)
                        tgt_ocs.append(round(percentile_to_oc(90, lp_b, sig_b), 3))
                    else:
                        tgt_ocs.append(np.nan)
                else:
                    tgt_ocs.append(np.nan)
            else:
                tgt_ocs.append(np.nan)

            # SMAF SOC 
            if "SMAF Soil Organic Carbon" in target_indicators and "soc_pct" in r and pd.notna(r["soc_pct"]):
                batch.at[index, "SMAF Soil Organic Carbon Score"] = round(run_smaf_soc_score(float(r["soc_pct"]), row_om_id, row_texture_id, row_climate_id, SMAF_DATA), 1)

            # pH 
            if "pH" in target_indicators and "ph_val" in r and pd.notna(r["ph_val"]):
                batch.at[index, "pH Score"] = round(run_smaf_ph_score(float(r["ph_val"]), row_crop_id, SMAF_DATA), 1)

            # Phosphorus 
            if "Soil Phosphorus" in target_indicators and "p_mg_kg" in r and pd.notna(r["p_mg_kg"]):
                oc_val = safe_float(r.get("soc_pct", 2.0))
                batch.at[index, "Soil Phosphorus Score"] = round(run_smaf_p_score(float(r["p_mg_kg"]), row_crop_id, row_method_id, row_weather_id, row_texture_id, ui_slope_id, oc_val), 1)

            # Extractable Potassium 
            if "Extractable Potassium" in target_indicators and "k_mg_kg" in r and pd.notna(r["k_mg_kg"]):
                batch.at[index, "Extractable Potassium Score"] = round(run_smaf_exk_score(float(r["k_mg_kg"]), row_texture_id, SMAF_DATA), 1)

            # Electrical Conductivity 
            if "Electrical Conductivity" in target_indicators and "ec_ds_m" in r and pd.notna(r["ec_ds_m"]):
                batch.at[index, "Electrical Conductivity Score"] = round(run_smaf_ec_score(float(r["ec_ds_m"]), row_crop_id, row_ec_method_id, row_texture_id, SMAF_DATA), 1)

            # Sodium Adsorption Ratio 
            if "Sodium Adsorption Ratio" in target_indicators and "sar_val" in r and "ec_ds_m" in r and pd.notna(r["sar_val"]) and pd.notna(r["ec_ds_m"]):
                batch.at[index, "Sodium Adsorption Ratio Score"] = round(run_smaf_sar_score(float(r["sar_val"]), float(r["ec_ds_m"]), row_ec_method_id, row_texture_id, SMAF_DATA), 1)

            # Bulk Density 
            if "Bulk Density" in target_indicators and "bd_g_cm3" in r and pd.notna(r["bd_g_cm3"]):
                batch.at[index, "Bulk Density Score"] = round(run_smaf_bd_score(float(r["bd_g_cm3"]), row_texture_id, ui_mineralogy_id), 1)

            # Macroaggregate Stability 
            if "Macroaggregate Stability" in target_indicators and "agg_pct" in r and pd.notna(r["agg_pct"]):
                batch.at[index, "Macroaggregate Stability Score"] = round(run_smaf_agg_score(float(r["agg_pct"]), row_om_id, row_texture_id, ui_fe_id, SMAF_DATA), 1)

            # Available Water Capacity 
            if "Available Water Capacity" in target_indicators and "awc_g_g" in r and pd.notna(r["awc_g_g"]):
                batch.at[index, "Available Water Capacity Score"] = round(run_smaf_awc_score(float(r["awc_g_g"]), ui_awc_region, row_texture_id, row_om_id, SMAF_DATA), 1)

            # Water-Filled Pore Space 
            if "Water-Filled Pore Space" in target_indicators and "wfps_frac" in r and pd.notna(r["wfps_frac"]):
                wfps_res = run_smaf_wfps_score(float(r["wfps_frac"]), row_texture_id, SMAF_DATA)
                batch.at[index, "Water-Filled Pore Space Score"] = round(wfps_res["combined"], 1)

            # PMN 
            if "Potentially Mineralizable Nitrogen" in target_indicators and "pmn_mg_kg" in r and pd.notna(r["pmn_mg_kg"]):
                batch.at[index, "Potentially Mineralizable Nitrogen Score"] = round(run_smaf_pmn_score(float(r["pmn_mg_kg"]), row_om_id, row_texture_id, row_climate_id, SMAF_DATA), 1)

            # Microbial Biomass Carbon 
            if "Microbial Biomass Carbon" in target_indicators and "mbc_mg_kg" in r and pd.notna(r["mbc_mg_kg"]):
                batch.at[index, "Microbial Biomass Carbon Score"] = round(run_smaf_mbc_score(float(r["mbc_mg_kg"]), row_om_id, row_texture_id, row_season_climate, SMAF_DATA), 1)

            # Beta-glucosidase 
            if "Beta-glucosidase" in target_indicators and "bg_mg_kg_hr" in r and pd.notna(r["bg_mg_kg_hr"]):
                batch.at[index, "Beta-glucosidase Score"] = round(run_smaf_bg_score(float(r["bg_mg_kg_hr"]), row_om_id, row_texture_id, row_climate_id, SMAF_DATA), 1)

        # 5. Post-Processing & Aggregation
        batch = batch.copy()
        
        # Calculate Overall SQI across all active indicators for the row
        batch["Overall_SQI"] = batch[score_columns].mean(axis=1).round(1)
        
        # Generate categorical zones based on Overall SQI
        batch["Zone"] = batch["Overall_SQI"].apply(lambda s: score_label(s) if pd.notna(s) else "No data")
        
        # Add SHAPE targets if they were calculated
        if "Soil Organic Carbon" in target_indicators and selected_framework in ["SHAPE", "SHAPE + SMAF (Hybrid)"]:
            batch["SOC_target_90th"] = tgt_ocs
            soc_col = "soc_pct" if "soc_pct" in batch.columns else "oc"
            if soc_col in batch.columns:
                batch["Gap_to_90th"] = (batch["SOC_target_90th"] - batch[soc_col]).round(3)

        # 6. Render Restored Metrics
        valid = batch["Overall_SQI"].dropna()
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Samples scored", len(valid))
        mc2.metric("Mean SQI", f"{valid.mean():.1f}/100" if len(valid) else "—")
        mc3.metric("High / V. High", f"{(valid >= 60).sum()} ({100*(valid>=60).mean():.0f}%)" if len(valid) else "—")
        mc4.metric("Low / V. Low", f"{(valid < 40).sum()} ({100*(valid<40).mean():.0f}%)" if len(valid) else "—")

        st.divider()

        # 7. Render Restored Histogram
        fig_dist = go.Figure()
        fig_dist.add_trace(go.Histogram(x=valid, nbinsx=20, marker_color="#1a9641", opacity=0.75))
        for xv, lbl, clr in [(20, "V.Low|Low", "#f46d43"), (40, "Low|Med", "#ffc107"), (60, "Med|High", "#77c35c"), (80, "High|V.High", "#1a9641")]:
            fig_dist.add_vline(x=xv, line_dash="dash", line_color=clr, annotation_text=lbl, annotation_position="top right")
        fig_dist.update_layout(
            xaxis_title="Overall Soil Quality Index (SQI)", 
            yaxis_title="Count",
            paper_bgcolor="rgba(0,0,0,0)", 
            plot_bgcolor="rgba(0,0,0,0)",
            height=280, margin=dict(l=10, r=10, t=20, b=10), showlegend=False
        )
        st.plotly_chart(fig_dist, width='stretch', key=f"{k}_dist_chart")

        st.markdown("#### 🧪 Scored Results")
        
        # 8. Render Restored Colored Dataframe
        def highlight_zone(row):
            s = row.get("Overall_SQI", np.nan)
            if pd.isna(s): return [""] * len(row)
            if s >= 80: bg = "background-color: rgba(26,150,65,0.25)"
            elif s >= 60: bg = "background-color: rgba(119,195,92,0.25)"
            elif s >= 40: bg = "background-color: rgba(255,193,7,0.25)"
            elif s >= 20: bg = "background-color: rgba(244,109,67,0.25)"
            else: bg = "background-color: rgba(215,48,39,0.25)"
            return [bg] * len(row)
            
        st.dataframe(batch.style.apply(highlight_zone, axis=1), width='stretch', hide_index=True)

        # 9. Render Restored Map
        if "lat" in batch.columns and "lon" in batch.columns:
            map_data = batch[["lat", "lon"]].dropna()
            if not map_data.empty:
                st.markdown("#### 📍 Site Map")
                st.map(map_data, zoom=4)

        st.divider()
        st.download_button(
            "⬇️ Download Scored Results as CSV", 
            data=batch.to_csv(index=False).encode("utf-8"),
            file_name=f"gSHAPE_batch_results.csv", 
            mime="text/csv",
            use_container_width=True, 
            key=f"{k}_results_dl"
        )
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

    if mineral_df is None and region_name != "Global_SMAF":
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
        # Dynamically list ALL selected indicators
        active_inds = st.session_state.get("target_indicators", [])
        if active_inds:
            st.markdown(f"**Active Indicators:** `{', '.join(active_inds)}`")
        
        render_batch_scoring(region_name, cfg, mineral_df, hist_df)

    # 4. Render How to Use View
    with tab_use:
        render_how_to_use(region_name, cfg)

# ════════════════════════════════════════════════════════════════════
# 9. GLOBAL ROUTING ENGINE (Replaces Region Tabs)
# ════════════════════════════════════════════════════════════════════
st.markdown("### Global Location Setup")

loc_c1, loc_c2 = st.columns(2)
with loc_c1:
    selected_country = st.selectbox("Country", ALL_COUNTRIES)
    
with loc_c2:
    selected_state = None
    if selected_country == "United States":
        selected_state = st.selectbox("State", US_STATES)
        
# ── FRAMEWORK LOGIC (The SHAPE Gatekeeper) ──
active_region_name = "Global_SMAF"
if selected_country == "Brazil": active_region_name = "Brazil"
elif selected_country in SSA_COUNTRIES: active_region_name = "Sub-Saharan Africa"
elif selected_country == "United States" and selected_state == "Florida": active_region_name = "Florida"

st.markdown("### Scoring Framework")
framework_options = ["SMAF"]
if active_region_name != "Global_SMAF":
    # ✨ Add all three modes here!
    framework_options = ["SHAPE + SMAF (Hybrid)", "SMAF", "SHAPE"]

selected_framework = st.selectbox("Select your preferred evaluation framework:", framework_options)
st.session_state["selected_framework"] = selected_framework

# Silently force the fallback to global parameters if they strictly select SMAF
if selected_framework in ["SMAF", "SMAF Only"]:
    active_region_name = "Global_SMAF"

# Create the Global CFG dynamically if it doesn't exist
if "Global_SMAF" not in REGIONS:
    REGIONS["Global_SMAF"] = dict(REGIONS["Florida"]) # Inherit default UI maps
    REGIONS["Global_SMAF"]["key"] = "GL"
    REGIONS["Global_SMAF"]["csv"] = None        # Disables SHAPE parsing
    REGIONS["Global_SMAF"]["csv_hist"] = None   # Disables Histosol parsing

active_cfg = REGIONS[active_region_name]

# Create the Global CFG dynamically if it doesn't exist
if "Global_SMAF" not in REGIONS:
    REGIONS["Global_SMAF"] = dict(REGIONS["Florida"]) # Inherit default UI maps
    REGIONS["Global_SMAF"]["key"] = "GL"
    REGIONS["Global_SMAF"]["csv"] = None        # Disables SHAPE parsing
    REGIONS["Global_SMAF"]["csv_hist"] = None   # Disables Histosol parsing

active_cfg = REGIONS[active_region_name]

# ── DYNAMIC INDICATOR FILTER ──
# ── DYNAMIC INDICATOR FILTER ──
st.markdown("### Target Soil Health Indicators")
chk_c1, chk_c2, chk_c3 = st.columns(3)
target_indicators = []

# ✨ THE FIX: Updated string names to match your clean dropdown labels
smaf_active = selected_framework in ["SMAF", "SHAPE + SMAF (Hybrid)"]

with chk_c1:
    st.markdown("**Physical Indicators**")
    if st.checkbox("Bulk Density", value=smaf_active, disabled=not smaf_active): 
        if smaf_active: target_indicators.append("Bulk Density")
    if st.checkbox("Macroaggregate Stability", value=smaf_active, disabled=not smaf_active): 
        if smaf_active: target_indicators.append("Macroaggregate Stability")
    if st.checkbox("Available Water Capacity", value=False, disabled=not smaf_active): 
        if smaf_active: target_indicators.append("Available Water Capacity")
    if st.checkbox("Water-Filled Pore Space", value=False, disabled=not smaf_active): 
        if smaf_active: target_indicators.append("Water-Filled Pore Space")

with chk_c2:
    st.markdown("**Chemical Indicators**")
    if st.checkbox("pH", value=smaf_active, disabled=not smaf_active): 
        if smaf_active: target_indicators.append("pH")
    if st.checkbox("Soil Phosphorus", value=smaf_active, disabled=not smaf_active): 
        if smaf_active: target_indicators.append("Soil Phosphorus")
    if st.checkbox("Extractable Potassium", value=False, disabled=not smaf_active): 
        if smaf_active: target_indicators.append("Extractable Potassium")
    if st.checkbox("Electrical Conductivity", value=smaf_active, disabled=not smaf_active): 
        if smaf_active: target_indicators.append("Electrical Conductivity")
    if st.checkbox("Sodium Adsorption Ratio", value=False, disabled=not smaf_active): 
        if smaf_active: target_indicators.append("Sodium Adsorption Ratio")

with chk_c3:
    st.markdown("**Biological Indicators**")
    
    # ✨ THE FIX: Updated string names for the SOC routing
    if st.checkbox("Soil Organic Carbon", value=True): 
        if selected_framework == "SHAPE":
            target_indicators.append("Soil Organic Carbon") # Routes to SHAPE math
        elif selected_framework == "SMAF":
            target_indicators.append("SMAF Soil Organic Carbon") # Routes to SMAF math
        else: # Hybrid Mode
            target_indicators.append("Soil Organic Carbon") # Uses SHAPE for SOC override
            
    if st.checkbox("Potentially Mineralizable Nitrogen", value=False, disabled=not smaf_active): 
        if smaf_active: target_indicators.append("Potentially Mineralizable Nitrogen")
    if st.checkbox("Microbial Biomass Carbon", value=False, disabled=not smaf_active): 
        if smaf_active: target_indicators.append("Microbial Biomass Carbon")
    if st.checkbox("Beta-glucosidase", value=False, disabled=not smaf_active): 
        if smaf_active: target_indicators.append("Beta-glucosidase")
        
if len(target_indicators) == 0:
    st.warning("⚠️ Please select all the indicators you want to score.")
    st.stop()
    
st.session_state["target_indicators"] = target_indicators
st.divider()
# Launch the app engine dynamically based on selections!
render_region(active_region_name, active_cfg)

# ════════════════════════════════════════════════════════════════════
# 10. DYNAMIC CITATIONS
# ════════════════════════════════════════════════════════════════════
st.divider()
st.markdown("### 📝 Citations")
st.markdown("<span style='font-size:13px; color:gray'>The following methodologies and frameworks are actively being utilized to evaluate your current selection:</span>", unsafe_allow_html=True)

# 1. gSHAPE App Citation (Always First)
st.markdown("**gSHAPE Web Application:**")
st.markdown("- Singh, M., Nunes, M. R., Biru, M. K., & Ologunde, O. H. *gSHAPE: Global Soil Health Assessment Protocol and Evaluation*. (Citation coming soon).")

# 2. Evaluate active indicators for conditional citations
has_general_smaf = any(ind in target_indicators for ind in [
    "Bulk Density", "Macroaggregate Stability", "Available Water Capacity", 
    "pH", "Soil Phosphorus", "Electrical Conductivity", 
    "Sodium Adsorption Ratio", "Potentially Mineralizable Nitrogen", 
    "Microbial Biomass Carbon", "SMAF Soil Organic Carbon"
])
has_wfps = "Water-Filled Pore Space" in target_indicators
has_beta_g = "Beta-glucosidase" in target_indicators
has_k = "Extractable Potassium" in target_indicators  # Future-proofing 
has_shape_soc = "Soil Organic Carbon" in target_indicators and selected_framework == "SHAPE + SMAF"

# 3. SHAPE SOC Citations
if has_shape_soc:
    if active_region_name == "Sub-Saharan Africa":
        st.markdown(f"**SHAPE Soil Organic Carbon ({active_region_name}):**")
        st.markdown("- Biru, M. K., Nunes, M. R., Singh, M., et al. (2026). A region-specific soil health assessment protocol and evaluation for Sub-Saharan Africa. *Commun Earth Environ*, 7, 670. [https://doi.org/10.1038/s43247-026-03727-1](https://doi.org/10.1038/s43247-026-03727-1)")
    elif active_region_name in ["Florida", "Brazil"]:
        st.markdown(f"**SHAPE Soil Organic Carbon ({active_region_name}):**")
        st.markdown("- (Citation coming soon).")
        
# 4. SMAF Core Citation
if has_general_smaf:
    st.markdown("**SMAF General Framework & Core Indicators:**")
    st.markdown("- Andrews, S. S., Karlen, D. L., & Cambardella, C. A. (2004). The Soil Management Assessment Framework: a quantitative soil quality evaluation method. *Soil Sci. Soc. Am. J.*, 68, 1945-1962. [https://doi.org/10.2136/sssaj2004.1945](https://doi.org/10.2136/sssaj2004.1945)")
    
# 5. SMAF WFPS / K Citation
if has_wfps or has_k:
    st.markdown("**SMAF Water-Filled Pore Space / Potassium:**")
    st.markdown("- Wienhold, B. J., Karlen, D. L., Andrews, S. S., & Stott, D. E. (2009). Protocol for indicator scoring in the soil management assessment framework (SMAF). *Renew. Agric. Food Syst.*, 24(4), 260-266. [https://doi.org/10.1017/S174217050999015X](https://www.cambridge.org/core/journals/renewable-agriculture-and-food-systems/article/protocol-for-indicator-scoring-in-the-soil-management-assessment-framework-smaf/3B3C2C94F977CEFF8D294D87B0D06DBF)")
    
# 6. SMAF Beta-glucosidase Citation
if has_beta_g:
    st.markdown("**SMAF Beta-glucosidase:**")
    st.markdown("- Stott, D. E., Andrews, S. S., Liebig, M. A., Wienhold, B. J., & Karlen, D. L. (2010). Evaluation of β-glucosidase activity as a soil quality indicator for the soil management assessment framework. *Soil Sci. Soc. Am. J.*, 74, 107-119. [https://doi.org/10.2136/sssaj2009.0029](https://acsess.onlinelibrary.wiley.com/doi/full/10.2136/sssaj2009.0029)")

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
