from pathlib import Path
import re
import unicodedata

import pandas as pd


REQUIRED_COLUMNS = [
    "Rule ID",
    "Code",
    "Cropping system",
    "Crops",
    "Management question",
    "Selected answer",
    "SOC level",
    "Interpretation",
    "Practical SOC recommendation",
]


def normalize_text(value: object) -> str:
    """Normalize text so small formatting differences do not prevent matching."""

    if pd.isna(value):
        return ""

    value = unicodedata.normalize("NFKC", str(value)).casefold()

    value = (
        value.replace("–", "-")
        .replace("—", "-")
        .replace("−", "-")
    )

    return re.sub(r"[^a-z0-9]+", "", value)


def load_soc_rules(
    excel_path: str | Path,
    sheet_name: str = "Rules_Data",
) -> pd.DataFrame:
    """Load and validate the SOC recommendation database."""

    excel_path = Path(excel_path)

    if not excel_path.exists():
        raise FileNotFoundError(
            f"SOC recommendation file not found: {excel_path}"
        )

    df = pd.read_excel(
        excel_path,
        sheet_name=sheet_name,
        dtype=str,
        engine="openpyxl",
    ).fillna("")

    df.columns = df.columns.str.strip()

    for column in df.columns:
        df[column] = df[column].astype(str).str.strip()

    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required Excel columns: {missing}"
        )

    required_cells = [
        "Rule ID",
        "Code",
        "Cropping system",
        "Management question",
        "Selected answer",
        "SOC level",
        "Interpretation",
        "Practical SOC recommendation",
    ]

    blank_rows = df[required_cells].eq("").any(axis=1)

    if blank_rows.any():
        excel_rows = (df.index[blank_rows] + 2).tolist()

        raise ValueError(
            f"Blank required cells in Excel rows: {excel_rows}"
        )

    if df["Rule ID"].duplicated().any():
        duplicate_ids = df.loc[
            df["Rule ID"].duplicated(keep=False),
            "Rule ID",
        ].tolist()

        raise ValueError(
            f"Duplicate Rule IDs: {duplicate_ids}"
        )

    df["_code_key"] = df["Code"].map(normalize_text)
    df["_system_key"] = df["Cropping system"].map(normalize_text)
    df["_question_key"] = df["Management question"].map(normalize_text)
    df["_answer_key"] = df["Selected answer"].map(normalize_text)
    df["_soc_key"] = df["SOC level"].map(normalize_text)

    duplicate_rules = df.duplicated(
        subset=[
            "_code_key",
            "_question_key",
            "_answer_key",
            "_soc_key",
        ],
        keep=False,
    )

    if duplicate_rules.any():
        duplicates = df.loc[
            duplicate_rules,
            [
                "Rule ID",
                "Code",
                "Management question",
                "Selected answer",
                "SOC level",
            ],
        ]

        raise ValueError(
            "Duplicate recommendation combinations:\n"
            f"{duplicates.to_string(index=False)}"
        )

    return df


def get_cropping_systems(rules_df: pd.DataFrame) -> pd.DataFrame:
    """Return available SSA codes and cropping-system names."""

    return (
        rules_df[
            ["Code", "Cropping system"]
        ]
        .drop_duplicates()
        .sort_values(["Code", "Cropping system"])
        .reset_index(drop=True)
    )


def get_management_questions(
    rules_df: pd.DataFrame,
    code: str,
) -> list[str]:
    """Return management questions available for one cropping system."""

    mask = rules_df["_code_key"].eq(normalize_text(code))

    return (
        rules_df.loc[mask, "Management question"]
        .drop_duplicates()
        .tolist()
    )


def get_selected_answers(
    rules_df: pd.DataFrame,
    code: str,
    management_question: str,
) -> list[str]:
    """Return answer options for one management question."""

    mask = (
        rules_df["_code_key"].eq(normalize_text(code))
        & rules_df["_question_key"].eq(
            normalize_text(management_question)
        )
    )

    return (
        rules_df.loc[mask, "Selected answer"]
        .drop_duplicates()
        .tolist()
    )


def get_soc_recommendation(
    rules_df: pd.DataFrame,
    code: str,
    management_question: str,
    selected_answer: str,
    soc_level: str,
) -> dict:
    """Return the matching SOC interpretation and recommendation."""

    mask = (
        rules_df["_code_key"].eq(normalize_text(code))
        & rules_df["_question_key"].eq(
            normalize_text(management_question)
        )
        & rules_df["_answer_key"].eq(
            normalize_text(selected_answer)
        )
        & rules_df["_soc_key"].eq(
            normalize_text(soc_level)
        )
    )

    match = rules_df.loc[mask]

    if match.empty:
        raise KeyError(
            "No SOC recommendation found for: "
            f"{code} | {management_question} | "
            f"{selected_answer} | {soc_level}"
        )

    if len(match) > 1:
        raise ValueError(
            "More than one recommendation matches this selection."
        )

    row = match.iloc[0]

    return {
        "rule_id": row["Rule ID"],
        "code": row["Code"],
        "cropping_system": row["Cropping system"],
        "crops": row["Crops"],
        "management_question": row["Management question"],
        "selected_answer": row["Selected answer"],
        "soc_level": row["SOC level"],
        "interpretation": row["Interpretation"],
        "recommendation": row[
            "Practical SOC recommendation"
        ],
    }
