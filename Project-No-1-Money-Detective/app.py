"""
app.py
------
Money Detective — Streamlit dashboard (lightweight edition).

Uses only Streamlit's built-in native charts — no Plotly, no Matplotlib.
Full offline, no AI/LLM calls. Just 3 pip packages: streamlit, pandas, openpyxl.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import streamlit as st

from utils import analysis as az

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("money_detective")

APP_DIR = Path(__file__).parent
DEFAULT_CSV  = APP_DIR / "transactions.csv"
DEFAULT_XLSX = APP_DIR / "transactions.xlsx"

PAGES = ["📊 Dashboard", "📋 Transactions", "🔁 Recurring & Subscriptions", "ℹ️ About"]


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
def init_session_state() -> None:
    defaults = {
        "analyzed": False,
        "df": pd.DataFrame(),
        "duplicates": pd.DataFrame(),
        "duplicates_summary": {"row_count": 0, "group_count": 0, "total_amount": 0.0},
        "recurring": pd.DataFrame(),
        "forgotten": pd.DataFrame(),
        "categorized": pd.DataFrame(),
        "category_summary": pd.DataFrame(),
        "stats": {},
        "monthly": pd.DataFrame(),
        "verification": {"verified": None, "message": ""},
        "insights": [],
        "report_text": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ---------------------------------------------------------------------------
# Analysis pipeline
# ---------------------------------------------------------------------------
def run_analysis(csv_source, xlsx_source) -> None:
    df = az.load_transactions_csv(csv_source)

    excel_total = None
    if xlsx_source is not None:
        _, excel_total = az.load_transactions_excel(xlsx_source)

    duplicates        = az.detect_duplicates(df)
    duplicates_summary = az.summarize_duplicates(duplicates)
    recurring         = az.detect_recurring(df)
    forgotten         = az.detect_forgotten_subscriptions(recurring)
    categorized       = az.add_category_column(df)
    category_summary  = az.category_spend_summary(categorized)
    stats             = az.compute_summary_stats(df)
    monthly           = az.monthly_summary(df)
    verification      = az.verify_total(stats["net_total"], excel_total)
    insights          = az.build_plain_language_summary(duplicates_summary, recurring, forgotten, stats)
    report_text       = az.build_text_report(
        stats, duplicates_summary, recurring, forgotten,
        category_summary, monthly, verification, insights
    )

    st.session_state.update({
        "analyzed": True,
        "df": df,
        "duplicates": duplicates,
        "duplicates_summary": duplicates_summary,
        "recurring": recurring,
        "forgotten": forgotten,
        "categorized": categorized,
        "category_summary": category_summary,
        "stats": stats,
        "monthly": monthly,
        "verification": verification,
        "insights": insights,
        "report_text": report_text,
    })


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def render_sidebar() -> str:
    with st.sidebar:
        st.title("🕵️ Money Detective")
        st.caption("Rule-based analyzer — offline, no AI calls, 3 packages only.")
        st.divider()

        st.subheader("Data source")
        use_sample = st.checkbox("Use built-in sample data", value=True)

        uploaded_csv  = None
        uploaded_xlsx = None
        if not use_sample:
            uploaded_csv  = st.file_uploader("Transactions CSV", type=["csv"])
            uploaded_xlsx = st.file_uploader(
                "Transactions Excel (optional, enables total verification)", type=["xlsx"]
            )

        analyze_clicked = st.button("🔍 Analyze", type="primary", width="stretch")

        if analyze_clicked:
            try:
                if use_sample:
                    csv_source, xlsx_source = DEFAULT_CSV, DEFAULT_XLSX
                else:
                    if uploaded_csv is None:
                        st.error("Please upload a CSV file or switch back to sample data.")
                        csv_source = None
                    else:
                        csv_source = uploaded_csv
                    xlsx_source = uploaded_xlsx

                if csv_source is not None:
                    with st.spinner("Analyzing..."):
                        run_analysis(csv_source, xlsx_source)
                    st.success(f"Analyzed {len(st.session_state['df'])} transactions.")
            except FileNotFoundError as exc:
                st.error(f"File not found: {exc}")
            except ValueError as exc:
                st.error(f"Could not read file: {exc}")
            except Exception:
                logger.exception("Unexpected error during analysis")
                st.error("Something went wrong. Check the terminal for details.")

        st.divider()
        page = st.radio("Go to", PAGES, label_visibility="collapsed")

        if st.session_state["analyzed"]:
            st.divider()
            v = st.session_state["verification"]
            if v["verified"] is True:
                st.success(v["message"])
            elif v["verified"] is False:
                st.error(v["message"])
            else:
                st.info("Upload an Excel file to verify totals against its SUM() cell.")

    return page


# ---------------------------------------------------------------------------
# Page: Dashboard
# ---------------------------------------------------------------------------
def render_dashboard() -> None:
    st.header("📊 Dashboard")

    if not st.session_state["analyzed"]:
        st.info("👈 Choose a data source in the sidebar and click **Analyze** to get started.")
        return

    stats            = st.session_state["stats"]
    recurring        = st.session_state["recurring"]
    dup_summary      = st.session_state["duplicates_summary"]
    forgotten        = st.session_state["forgotten"]
    category_summary = st.session_state["category_summary"]
    monthly          = st.session_state["monthly"]

    # --- summary cards ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Spend",          f"Rs. {stats['total_expense']:,.0f}")
    c2.metric("Recurring Payments",   len(recurring))
    c3.metric("Duplicate Charges",    dup_summary["row_count"])
    c4.metric("Flagged Subscriptions", len(forgotten))

    st.divider()

    # --- charts side by side ---
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Spend by Category")
        if not category_summary.empty:
            # Horizontal bar: Category on index, TotalSpend as value
            cat_chart = (
                category_summary
                .set_index("Category")[["TotalSpend"]]
                .rename(columns={"TotalSpend": "Rs. Spent"})
            )
            st.bar_chart(cat_chart)
        else:
            st.caption("No expense data.")

    with chart_col2:
        st.subheader("Monthly Income vs Expense")
        if not monthly.empty:
            monthly_chart = (
                monthly
                .set_index("Month")[["Income", "Expense"]]
            )
            st.bar_chart(monthly_chart)
        else:
            st.caption("No monthly data.")

    st.divider()

    # --- insights panel ---
    st.subheader("🗣️ What this means for you")
    for line in st.session_state["insights"]:
        st.markdown(f"- {line}")

    st.divider()

    # --- download report ---
    st.download_button(
        label="📥 Download Full Report (.txt)",
        data=st.session_state["report_text"],
        file_name="money_detective_report.txt",
        mime="text/plain",
        width="stretch",
    )


# ---------------------------------------------------------------------------
# Page: Transactions
# ---------------------------------------------------------------------------
def render_transactions() -> None:
    st.header("📋 Transactions")

    if not st.session_state["analyzed"]:
        st.info("👈 Click **Analyze** in the sidebar first.")
        return

    categorized = st.session_state["categorized"]
    duplicates  = st.session_state["duplicates"]

    st.subheader("All transactions")
    st.dataframe(
        categorized.drop(columns=["Month"]).sort_values("Date"),
        width="stretch", hide_index=True
    )

    st.subheader("⚠️ Duplicate charges")
    if duplicates.empty:
        st.caption("No duplicate Date + Description + Amount rows found. ✅")
    else:
        st.dataframe(
            duplicates.drop(columns=["Month"]),
            width="stretch", hide_index=True
        )
        s = st.session_state["duplicates_summary"]
        st.caption(
            f"{s['row_count']} duplicate rows across {s['group_count']} group(s) "
            f"— totaling Rs. {abs(s['total_amount']):,.0f}."
        )


# ---------------------------------------------------------------------------
# Page: Recurring & Subscriptions
# ---------------------------------------------------------------------------
def render_recurring() -> None:
    st.header("🔁 Recurring & Subscriptions")

    if not st.session_state["analyzed"]:
        st.info("👈 Click **Analyze** in the sidebar first.")
        return

    recurring = st.session_state["recurring"]
    forgotten = st.session_state["forgotten"]

    st.subheader("Recurring payments")
    st.caption("Any description that charges in 2 or more different months is flagged as recurring.")
    if recurring.empty:
        st.caption("None detected.")
    else:
        st.dataframe(recurring, width="stretch", hide_index=True)

    st.divider()

    st.subheader("Possibly forgotten subscriptions")
    st.caption(
        "Recurring charges whose name matches a subscription keyword (Netflix, Spotify, etc.) "
        "are surfaced here for you to confirm you still use them."
    )
    if forgotten.empty:
        st.caption("None flagged. ✅")
    else:
        st.dataframe(forgotten, width="stretch", hide_index=True)


# ---------------------------------------------------------------------------
# Page: About
# ---------------------------------------------------------------------------
def render_about() -> None:
    st.header("ℹ️ About Money Detective")
    st.markdown("""
Money Detective is a fully offline, rule-based transaction analyzer.
No AI/LLM calls — every number comes from deterministic pandas logic.
See **prompt.md** in the project folder for a plain-language walkthrough
of the duplicate-detection, recurring-payment, and category-mapping rules.

**Dependencies (just 3):**
- `streamlit` — dashboard UI
- `pandas` — data loading and all rule-based analysis
- `openpyxl` — reading the Excel SUM() formula cell
    """)

    if st.session_state["analyzed"]:
        st.divider()
        st.subheader("Total verification")
        v = st.session_state["verification"]
        st.write(v["message"])
        if v["excel_total"] is not None:
            st.write(
                f"Python total: **Rs. {v['python_total']:,.2f}** &nbsp;|&nbsp; "
                f"Excel SUM(): **Rs. {v['excel_total']:,.2f}**"
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="Money Detective", page_icon="🕵️", layout="wide")
    init_session_state()

    page = render_sidebar()

    if   page == "📊 Dashboard":                render_dashboard()
    elif page == "📋 Transactions":             render_transactions()
    elif page == "🔁 Recurring & Subscriptions": render_recurring()
    elif page == "ℹ️ About":                    render_about()


if __name__ == "__main__":
    main()
