import streamlit as st

# --- 1. CONSTRAINTS MASTER DATA ---
CONSTRAINTS_MASTER = {
    "Physical": {
        "Medium": ["Root penetration", "Water transmission"],
        "Low": ["Root penetration", "Gas exchange", "Water Infiltration", "Erosion and runoff"], 
        "VeryLow": ["Root penetration", "Water transmission", "Gas exchange", "Infiltration", "Water retention", "Solute transport", "Seedbed formation"],
    },
    "Chemical": {
        "Medium": ["Nutrient supply", "Nutrient Solubilization"],
        "Low": ["Nutrient supply", "Nutrient Solubilization", "Ion exchange and retention", "Rhizosphere habitat"],
        "VeryLow": ["Nutrient supply", "Nutrient solubility", "Ion exchange and retention", "Rhizosphere habitat", "pH buffering", "Ionic toxicity regulation", "Nitrogen transformation"],
    },
    "SOC": {
        "Medium": ["Nutrient mineralization", "Microbial habitat"],
        "Low": ["Nutrient mineralization", "Microbial habitat", "Aggregate Formation", "Water Retention"],
        "VeryLow": ["Nutrient mineralization", "Microbial habitat", "Aggregate Formation", "Water Retention", "Infiltration", "Structural stability", "Buffering capacity"],
    },
}

def _get_diag_display_data(category_key, score):
    if score is None:
        return None

    score_val = float(score)

    if score_val >= 60:
        return None

    rating_key = ""
    display_name = ""
    css_class = ""

    if score_val < 20:
        rating_key = "VeryLow"
        display_name = "Very Low"
        css_class = "badge-danger"
    elif score_val < 40:
        rating_key = "Low"
        display_name = "Low"
        css_class = "badge-danger"
    else: 
        rating_key = "Medium"
        display_name = "Medium"
        css_class = "badge-warning"

    constrained_list = CONSTRAINTS_MASTER[category_key][rating_key]
    
    return {
        "rating": display_name,
        "functions": "; ".join(constrained_list), 
        "css": css_class
    }

def render_constraints_table(user_scores_dict):
    # CSS updated with proper /* comments */ and transparent/light borders for Dark Mode
    constraints_css = """
        <style>
            .st-constraints-table-container { margin-top: 10px; margin-bottom: 20px; font-family: sans-serif; }
            
            .st-const-table { width: 100%; border-collapse: collapse; background-color: transparent; color: inherit; }
            .st-const-table th { text-align: left; padding: 12px; border-bottom: 2px solid rgba(255,255,255,0.2); font-weight: bold; }
            .st-const-table td { padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.1); vertical-align: top; }
            
            .col-cat { width: 15%; font-weight: bold; }
            .col-score { width: 12%; text-align: center; }
            .col-rating { width: 18%; text-align: center; }
            .col-funcs { width: 55%; }

            .st-status-badge { display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 0.85rem; font-weight: bold; color: white; }
            .badge-danger { background-color: #dc3545; } /* Red for Low/Very Low */
            .badge-warning { background-color: #fd7e14; } /* Orange for Medium */

            .placeholder-message { text-align: center; color: #28a745; padding: 25px; font-weight: bold; font-size: 1.1rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); }
        </style>
    """

    has_constraints = False
    table_rows_html = ""

    for category_key, score in user_scores_dict.items():
        diag_row_data = _get_diag_display_data(category_key, score)

        if diag_row_data:
            has_constraints = True
            table_rows_html += f"""
                <tr>
                    <td class="col-cat">{category_key}</td>
                    <td class="col-score">{score}</td>
                    <td class="col-rating"><span class="st-status-badge {diag_row_data['css']}">{diag_row_data['rating']}</span></td>
                    <td class="col-funcs">{diag_row_data['functions']}</td>
                </tr>
            """

    wrapper_html = f"<div class='st-constraints-table-container'>{constraints_css}"
    
    if not has_constraints:
        final_html = f"""{wrapper_html}
                            <p class="placeholder-message">Congratulations! All core soil health pillars scored High (>= 60), indicating fully functional soil systems that are unrestricted by major soil function constraints. Continue your existing management practices to maintain these optimal conditions.</p>
                         </div>"""
    else:
        final_html = f"""{wrapper_html}
            <table class="st-const-table">
                <thead>
                    <tr>
                        <th class="col-cat">Pillar</th>
                        <th class="col-score">Score</th>
                        <th class="col-rating">Assessment</th>
                        <th class="col-funcs">Critical Soil Functions Affected</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows_html}
                </tbody>
            </table>
        </div>"""

    st.markdown(final_html, unsafe_allow_html=True)
