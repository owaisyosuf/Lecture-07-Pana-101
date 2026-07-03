"""
What's My Grade, Really
------------------------
A single-file Streamlit app that computes a real course grade using a
specific teacher policy:

  - Six weighted categories: Assignments, Quizzes, Labs, Projects,
    Midterm, Final Exam.
  - Final Exam Replacement Rule: if the Final Exam percentage is HIGHER
    than the Midterm percentage, the Final Exam percentage is used in
    the Midterm's weight slot instead of the actual Midterm score.
    The Final Exam keeps its own weight and its own score as well —
    this is a substitution of the number used for Midterm's weight,
    not a removal of either category.
  - No drop-lowest rules apply to Assignments/Quizzes/Labs (none were
    specified) — every entered score counts toward that category's
    average.

All scores are entered as PERCENTAGES (0-100) in an editable table.
Leave a score blank if that item hasn't happened yet (e.g. Final Exam).

Run with:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

CATEGORIES = ["Assignments", "Quizzes", "Labs", "Projects", "Midterm", "Final Exam"]

DEFAULT_WEIGHTS = {
    "Assignments": 15.0,
    "Quizzes": 10.0,
    "Labs": 10.0,
    "Projects": 15.0,
    "Midterm": 20.0,
    "Final Exam": 30.0,
}

LETTER_SCALE = [
    (90, 100.0001, "A+"),
    (85, 90, "A"),
    (80, 85, "B+"),
    (75, 80, "B"),
    (70, 75, "C+"),
    (65, 70, "C"),
    (50, 65, "D"),
    (-0.0001, 50, "F"),
]


def letter_grade(pct: float) -> str:
    """Map a percentage to a letter grade using the fixed scale above."""
    for low, high, letter in LETTER_SCALE:
        if low <= pct < high:
            return letter
    # exact 100 edge case
    if pct >= 100:
        return "A+"
    return "F"


# --------------------------------------------------------------------------
# Core calculation logic
# --------------------------------------------------------------------------

def category_average(df: pd.DataFrame, category: str):
    """
    Average of all non-blank scores entered for a category.
    Returns None if the category has no graded scores yet ("ungraded").
    """
    scores = df.loc[df["Category"] == category, "Score"]
    scores = scores.dropna()
    if len(scores) == 0:
        return None
    return float(scores.mean())


def apply_replacement_rule(midterm_avg, final_avg):
    """
    Teacher's Final Exam Replacement Rule, implemented explicitly so it can
    be hand-checked.

    Logic:
      - If either Midterm or Final Exam is not yet graded, replacement
        cannot be evaluated -> use the Midterm's own score for its slot
        (no replacement).
      - If Final Exam % > Midterm %, the Final Exam % is used in the
        Midterm's weight slot. The Final Exam category itself still uses
        its own score and its own weight separately.
      - Otherwise, the Midterm's own score is used for its slot.

    Returns:
      effective_midterm_value: the number to use for the Midterm's WEIGHT
                                SLOT (may be None if Midterm ungraded)
      replaced: bool, whether the substitution happened
    """
    if midterm_avg is None or final_avg is None:
        return midterm_avg, False

    if final_avg > midterm_avg:
        # Substitution: Final Exam % takes over the Midterm's weight slot.
        return final_avg, True
    else:
        return midterm_avg, False


def build_breakdown(df: pd.DataFrame, weights: dict):
    """
    Build a per-category breakdown: raw average, weight, weighted
    contribution, and whether the category counted as "graded".
    Applies the replacement rule to the Midterm's slot only.
    """
    averages = {cat: category_average(df, cat) for cat in CATEGORIES}

    midterm_avg = averages["Midterm"]
    final_avg = averages["Final Exam"]
    effective_midterm, replaced = apply_replacement_rule(midterm_avg, final_avg)

    rows = []
    for cat in CATEGORIES:
        raw_avg = averages[cat]
        weight = weights[cat]

        if cat == "Midterm":
            # Use the (possibly replaced) value for the weight slot,
            # but still show the real Midterm average as "raw".
            slot_value = effective_midterm
        else:
            slot_value = raw_avg

        graded = slot_value is not None
        weighted_contribution = (slot_value * weight / 100.0) if graded else 0.0

        rows.append({
            "Category": cat,
            "Raw Average (%)": None if raw_avg is None else round(raw_avg, 2),
            "Used For Weight Slot (%)": None if slot_value is None else round(slot_value, 2),
            "Weight (%)": weight,
            "Graded?": "Yes" if graded else "Not yet",
            "Weighted Contribution": round(weighted_contribution, 3),
        })

    breakdown_df = pd.DataFrame(rows)
    return breakdown_df, averages, effective_midterm, replaced


def compute_current_grade(breakdown_df: pd.DataFrame):
    """
    Current grade = (sum of weighted contributions of GRADED categories)
                     / (sum of weights of GRADED categories) * 100

    This is the standard "current grade" approach: ungraded categories are
    excluded from both the numerator and denominator so the grade reflects
    only what has actually happened so far.
    """
    graded_rows = breakdown_df[breakdown_df["Graded?"] == "Yes"]
    graded_weight_sum = graded_rows["Weight (%)"].sum()

    if graded_weight_sum <= 0:
        return None, 0.0, 100.0

    weighted_sum = graded_rows["Weighted Contribution"].sum()
    current_grade = (weighted_sum / graded_weight_sum) * 100.0
    remaining_weight = 100.0 - graded_weight_sum
    return current_grade, graded_weight_sum, remaining_weight


def solve_final_target(averages: dict, weights: dict, target: float):
    """
    Solve for the Final Exam score needed to reach `target`, accounting for
    the replacement rule. Two scenarios are tested:

      Scenario 1 - NO replacement (Final <= Midterm):
        Midterm's slot keeps using the actual Midterm average.
        target*Total/100 = FixedOther + Weight_Midterm*Midterm_avg + Weight_Final*X
        Solve for X.
        Valid only if 0 <= X <= 100 AND X <= Midterm_avg (consistent with
        "no replacement" assumption).

      Scenario 2 - Replacement TRIGGERS (Final > Midterm):
        Midterm's slot is driven by X (the Final Exam score) too.
        target*Total/100 = FixedOther + (Weight_Midterm + Weight_Final)*X
        Solve for X.
        Valid only if 0 <= X <= 100 AND X > Midterm_avg (consistent with
        "replacement" assumption).

    "FixedOther" = weighted contributions of every graded category other
    than Midterm and Final Exam (Assignments, Quizzes, Labs, Projects).
    "Total" = weight of those graded categories + Midterm weight + Final
    weight (i.e. the weight base once the Final Exam is graded).
    """
    midterm_avg = averages["Midterm"]

    if midterm_avg is None:
        return {
            "error": "The Midterm needs a score before target scenarios can "
                     "be evaluated, since the replacement rule compares the "
                     "Final Exam against the Midterm."
        }

    other_cats = ["Assignments", "Quizzes", "Labs", "Projects"]
    other_weight = 0.0
    other_weighted = 0.0
    for cat in other_cats:
        avg = averages[cat]
        if avg is not None:
            other_weight += weights[cat]
            other_weighted += weights[cat] * avg / 100.0

    w_mid = weights["Midterm"]
    w_final = weights["Final Exam"]
    total_weight = other_weight + w_mid + w_final

    if total_weight <= 0 or w_final <= 0:
        return {"error": "Not enough weighted categories are graded yet, "
                          "or the Final Exam weight is 0, so a target "
                          "can't be solved for."}

    target_points = target / 100.0 * total_weight  # points needed (out of total_weight)

    # --- Scenario 1: no replacement ---
    fixed1 = other_weighted + (w_mid * midterm_avg / 100.0)
    x1 = (target_points - fixed1) / (w_final / 100.0)
    valid1 = (0 <= x1 <= 100) and (x1 <= midterm_avg)

    # --- Scenario 2: replacement triggers ---
    fixed2 = other_weighted
    denom2 = (w_mid + w_final) / 100.0
    x2 = (target_points - fixed2) / denom2 if denom2 > 0 else None
    valid2 = (x2 is not None) and (0 <= x2 <= 100) and (x2 > midterm_avg)

    return {
        "error": None,
        "other_weight": other_weight,
        "other_weighted": other_weighted,
        "total_weight": total_weight,
        "target_points": target_points,
        "midterm_avg": midterm_avg,
        "w_mid": w_mid,
        "w_final": w_final,
        "x1": x1,
        "valid1": valid1,
        "fixed1": fixed1,
        "x2": x2,
        "valid2": valid2,
        "fixed2": fixed2,
    }


# --------------------------------------------------------------------------
# Streamlit UI
# --------------------------------------------------------------------------

st.set_page_config(page_title="What's My Grade, Really", page_icon="🎓", layout="wide")

st.title("🎓 What's My Grade, Really")
st.caption(
    "Enter your real scores and real weights below. All scores are "
    "percentages (0-100). Leave a score blank for anything not graded yet."
)

# ---- Sidebar: weights ----
st.sidebar.header("Grading Weights (%)")
st.sidebar.caption("Must add up to exactly 100%.")

weights = {}
for cat in CATEGORIES:
    weights[cat] = st.sidebar.number_input(
        cat, min_value=0.0, max_value=100.0,
        value=DEFAULT_WEIGHTS[cat], step=0.5, key=f"weight_{cat}"
    )

weight_total = sum(weights.values())
if abs(weight_total - 100.0) > 0.01:
    st.sidebar.error(f"Weights currently sum to {weight_total:.1f}%. They must total 100%.")
else:
    st.sidebar.success(f"Weights sum to {weight_total:.1f}%. ✔")

with st.sidebar.expander("📋 Replacement Rule (as implemented)"):
    st.markdown(
        "If your **Final Exam %** is higher than your **Midterm %**, the "
        "Final Exam % is substituted into the **Midterm's weight slot**. "
        "The Final Exam still keeps its own score and its own weight — "
        "nothing is removed, only the number used for Midterm's slot "
        "changes.\n\n"
        "**No drop-lowest rules** apply to Assignments/Quizzes/Labs — "
        "every score you enter counts."
    )

weights_ok = abs(weight_total - 100.0) <= 0.01

# ---- Main area: editable score table ----
st.header("1. Enter Your Scores")
st.caption(
    "Add a row per item (e.g. each assignment or quiz). Leave Score blank "
    "if you haven't gotten that item back yet. Scores are entered as a "
    "percentage (0-100)."
)

if "scores_df" not in st.session_state:
    st.session_state.scores_df = pd.DataFrame({
        "Category": CATEGORIES,
        "Score": [None] * len(CATEGORIES),
    })

edited_df = st.data_editor(
    st.session_state.scores_df,
    num_rows="dynamic",
    use_container_width=True,
    key="score_editor",
    column_config={
        "Category": st.column_config.SelectboxColumn(
            "Category", options=CATEGORIES, required=True
        ),
        "Score": st.column_config.NumberColumn(
            "Score (%)", min_value=0.0, max_value=100.0, step=0.5,
            help="Leave blank if not graded yet."
        ),
    },
)
st.session_state.scores_df = edited_df

# ---- Validation of entered scores ----
validation_errors = []
for idx, row in edited_df.iterrows():
    score = row["Score"]
    if score is None or (isinstance(score, float) and pd.isna(score)):
        continue
    if score < 0:
        validation_errors.append(f"Row {idx + 1} ({row['Category']}): score can't be negative.")
    if score > 100:
        validation_errors.append(f"Row {idx + 1} ({row['Category']}): score can't exceed 100.")

if validation_errors:
    for err in validation_errors:
        st.error(err)

can_calculate = weights_ok and not validation_errors

if not weights_ok:
    st.warning("Fix your weights in the sidebar (must total 100%) before results are calculated.")

# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------

if can_calculate:
    breakdown_df, averages, effective_midterm, replaced = build_breakdown(edited_df, weights)

    st.header("2. Breakdown (hand-verify this)")
    st.caption(
        "Pick one category and check it by hand: "
        "Weighted Contribution = Used For Weight Slot × Weight ÷ 100."
    )
    st.dataframe(breakdown_df, use_container_width=True, hide_index=True)

    if replaced:
        st.info(
            f"🔁 Replacement triggered: Final Exam "
            f"({averages['Final Exam']:.2f}%) replaced Midterm "
            f"({averages['Midterm']:.2f}%) — using "
            f"{effective_midterm:.2f}% for the Midterm's weight slot."
        )
    elif averages["Midterm"] is not None and averages["Final Exam"] is not None:
        st.info(
            f"No replacement: Final Exam ({averages['Final Exam']:.2f}%) is "
            f"not higher than Midterm ({averages['Midterm']:.2f}%), so the "
            f"actual Midterm score ({averages['Midterm']:.2f}%) is used."
        )

    current_grade, graded_weight, remaining_weight = compute_current_grade(breakdown_df)

    st.header("3. Current Grade")
    col1, col2, col3 = st.columns(3)
    with col1:
        if current_grade is None:
            st.metric("Current Grade", "N/A")
        else:
            st.metric("Current Grade", f"{current_grade:.2f}%")
    with col2:
        st.metric("Letter Grade", letter_grade(current_grade) if current_grade is not None else "N/A")
    with col3:
        st.metric("Remaining Weight (ungraded)", f"{remaining_weight:.1f}%")

    if current_grade is not None:
        st.caption(
            f"Calculated from {graded_weight:.1f}% of the total weight that "
            f"has scores entered so far. Categories still worth "
            f"{remaining_weight:.1f}% haven't been graded yet."
        )

    # ---- Chart ----
    st.header("4. Weighted Contribution Chart")
    chart_df = breakdown_df.copy()
    fig = go.Figure(data=[
        go.Bar(
            x=chart_df["Category"],
            y=chart_df["Weighted Contribution"],
            marker_color=["#888888" if g == "Not yet" else "#2E86AB" for g in chart_df["Graded?"]],
            text=chart_df["Weighted Contribution"].round(2),
            textposition="outside",
        )
    ])
    fig.update_layout(
        yaxis_title="Weighted Contribution (points out of 100)",
        xaxis_title="Category",
        showlegend=False,
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ---- Target calculator ----
    st.header("5. Final Exam Target Calculator")
    st.caption(
        "Enter the overall grade you want and see what you need on the "
        "Final Exam, accounting for the replacement rule."
    )
    target = st.number_input(
        "Target overall grade (%)", min_value=0.0, max_value=100.0,
        value=85.0, step=0.5, key="target_grade"
    )

    if st.button("Calculate what I need"):
        result = solve_final_target(averages, weights, target)

        if result.get("error"):
            st.error(result["error"])
        else:
            st.markdown("**Setup:**")
            st.markdown(
                f"- Weight of graded Assignments/Quizzes/Labs/Projects: "
                f"`{result['other_weight']:.1f}%`, contributing "
                f"`{result['other_weighted']:.3f}` points so far.\n"
                f"- Midterm average: `{result['midterm_avg']:.2f}%` "
                f"(weight `{result['w_mid']:.1f}%`)\n"
                f"- Final Exam weight: `{result['w_final']:.1f}%`\n"
                f"- Total weight base once Final is graded: "
                f"`{result['total_weight']:.1f}%`\n"
                f"- Points needed for target: "
                f"`{target}% × {result['total_weight']:.1f} / 100 = "
                f"{result['target_points']:.3f}`"
            )

            st.markdown("**Scenario 1 — no replacement (Final ≤ Midterm):**")
            st.markdown(
                f"`X = (target_points − fixed1) / (Final weight / 100)`\n\n"
                f"`X = ({result['target_points']:.3f} − {result['fixed1']:.3f}) "
                f"/ {result['w_final'] / 100:.3f} = {result['x1']:.2f}%`"
            )
            if result["valid1"]:
                st.success(
                    f"✅ Valid: you'd need **{result['x1']:.2f}%** on the "
                    f"Final Exam, and this is consistent with the "
                    f"'no replacement' assumption (≤ Midterm's "
                    f"{result['midterm_avg']:.2f}%)."
                )
            else:
                reason = "it's outside the 0-100% range" if not (0 <= result["x1"] <= 100) else \
                    f"it's above the Midterm's {result['midterm_avg']:.2f}%, which would actually trigger the replacement rule"
                st.warning(f"❌ Not valid in this scenario — {reason}.")

            st.markdown("**Scenario 2 — replacement triggers (Final > Midterm):**")
            if result["x2"] is None:
                st.warning("Could not be solved (zero combined weight).")
            else:
                st.markdown(
                    f"`X = (target_points − fixed2) / ((Midterm weight + Final weight) / 100)`\n\n"
                    f"`X = ({result['target_points']:.3f} − {result['fixed2']:.3f}) "
                    f"/ {(result['w_mid'] + result['w_final']) / 100:.3f} = {result['x2']:.2f}%`"
                )
                if result["valid2"]:
                    st.success(
                        f"✅ Valid: you'd need **{result['x2']:.2f}%** on the "
                        f"Final Exam, and this is consistent with the "
                        f"replacement rule triggering (> Midterm's "
                        f"{result['midterm_avg']:.2f}%)."
                    )
                else:
                    reason = "it's outside the 0-100% range" if not (0 <= result["x2"] <= 100) else \
                        f"it's not above the Midterm's {result['midterm_avg']:.2f}%, so replacement wouldn't actually trigger"
                    st.warning(f"❌ Not valid in this scenario — {reason}.")

            if not result["valid1"] and not result["valid2"]:
                st.error(
                    "🚫 This target grade is not achievable with any Final "
                    "Exam score between 0% and 100% under either scenario."
                )
            elif result["valid1"] and result["valid2"]:
                st.info(
                    "Both scenarios came out mathematically valid (an edge "
                    "case right at the Midterm boundary) — either "
                    f"{result['x1']:.2f}% or {result['x2']:.2f}% works."
                )
else:
    st.info("Enter/fix your weights and scores above to see results.")
