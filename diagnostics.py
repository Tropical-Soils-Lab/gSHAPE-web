# File: diagnostics.py
import streamlit as st

# --- 1. CONSTRAINTS MASTER DATA (from image_7.png, corrected) ---
# Store as objects of lists for easy manipulation and clean display
CONSTRAINTS_MASTER = {
    "Physical": {
        "Medium": ["Root penetration", "Water transmission"],
        # uses red text correction, removed 'water transmission'
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

# --- 2. RATING & STYLING LOGIC ---
# Define the numeric cutoffs and their corresponding visual style
# 0-19: Very Low (Red Badge)
# 20-39: Low (Red Badge)
# 40-59: Medium (Orange Badge)
# 60+: High (Hidden)
def _get_diag_display_data(category_key, score):
    """
    Determines rating and returns specific visual styling data.
    Returns None if score is High (>= 60), hiding the category constraints.
    """
    if score is None:
        return None

    score_val = float(score)

    # Condition: Hide High scores (>= 60)
    if score_val >= 60:
        return None

    rating_key = ""
    display_name = ""
    css_class = ""

    if score_val < 20:
        rating_key = "VeryLow"
        display_name = "Very Low"
        css_class = "badge-danger" # Red visual
    elif score_val < 40:
        rating_key = "Low"
        display_name = "Low"
        css_class = "badge-danger" # Also use red visual for Low urgency
    else: # 40 - 59
        rating_key = "Medium"
        display_name = "Medium"
        css_class = "badge-warning" # Orange visual

    constrained_list = CONSTRAINTS_MASTER[category_key][rating_key]
    
    return {
        "rating": display_name,
        # Join constraints list with semicolon-space for readable display
        "functions": "; ".join(constrained_list), 
        "css": css_class
    }

# --- 3. HTML & CSS GENERATION FUNCTION ---
def render_constraints_table(user_scores_dict):
    """
    Generates a stylized diagnostic table based on user scores.
    Categories with high scores are omitted. If all are high, a positive message is shown.
    """
    # Define custom CSS for badges and table structure. 
    # Designed to be clean and visible on dark/light themes.
    constraints_css = """
        <style>
            .st-constraints-table-container { margin-top: 10px; margin-bottom: 20px; font-family: sans-serif; }
            
            .st-const-table { width: 100%; border-collapse: collapse; background-color: white; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); overflow: hidden; color: #333; }
            .st-const-table th { background-color: #f8f9fa; text-align: left; padding: 12px; border-bottom: 2px solid #eee; font-weight: bold; }
            .st-const-table td { padding: 12px; border-bottom: 1px solid #eee; vertical-align: top; }
            
            /* Columns sizes */
            .col-cat { width: 15%; font-weight: bold; }
            .col-score { width: 12%; text-align: center; }
            .col-rating { width: 18%; text-align: center; }
            .col-funcs { width: 55%; color: #444; }

            /* Status Badges */
            .st-status-badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: bold; color: white; }
            .badge-danger { background-color: #dc3545; } # Red for Very Low / Low
            .badge-warning { background-color: #fd7e14; } # Orange for Medium

            /* Placeholder/Success message when no constraints are shown */
            .placeholder-message { text-align: center; color: #28a745; padding: 25px; font-weight: bold; font-size: 1.1rem; background-color: white; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        </style>
    """

    has_constraints = False
    
    # Initialize table HTML
    table_rows_html = ""

    # Iterate through each defined category score
    for category_key, score in user_scores_dict.items():
        # Step A: Get diagnostic data. If High, returns None (hiding the row)
        diag_row_data = _get_diag_display_data(category_key, score)

        if diag_row_data:
            has_constraints = True
            
            # Step B: Build f-string row HTML with specific badges and functions list
            table_rows_html += f"""
                <tr>
                    <td class="col-cat">{category_key}</td>
                    <td class="col-score">{score}</td>
                    <td class="col-rating"><span class="st-status-badge {diag_row_data['css']}">{diag_row_data['rating']}</span></td>
                    <td class="col-funcs">{diag_row_data['functions']}</td>
                </tr>
            """

    # --- FINAL RENDERING LOGIC ---
    wrapper_html = f"<div class='st-constraints-table-container'>{constraints_css}"
    
    if not has_constraints:
        # Scenario: All scores are High (>= 60). Render a positive placeholder message.
        final_html = f"""{wrapper_html}
                            <p class="placeholder-message">Congratulations! All core soil health pillars scored High (>= 60), indicating fully functional soil systems that are unrestricted by major soil function constraints. Continue your existing management practices to maintain these optimal conditions.</p>
                         </div>"""
    else:
        # Scenario: Show constraints for Low-Medium scores. Build the full table.
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

    # --- Output to Streamlit using Markdown with Unsafe HTML ---
    st.markdown(final_html, unsafe_allow_html=True)
