"""
app.py

Streamlit app for Project 3: "The Books Don't Match".

Reconciles a known, hand-counted total (20 people x Rs. 1,000 = Rs. 20,000)
against a messy digital payment history, applying documented interpretation
rules (data/interpretation_rules.json) to resolve ambiguous entries before
matching. Surfaces the expected-vs-received gap and exactly who needs
follow-up.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.loader import load_expected_people, load_payment_history, load_interpretation_rules
from src.rules import apply_rules
from src.reconciler import (
    flag_transaction_status,
    build_person_ledger,
    build_summary,
    build_followup_list,
)
from src.utils import format_currency, validate_totals_match, build_summary_csv

# ---------------------------------------------------------------------------
# Paths & page config
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"
EXPECTED_PEOPLE_PATH = DATA_DIR / "expected_people.csv"
PAYMENT_HISTORY_PATH = DATA_DIR / "payment_history.csv"
RULES_PATH = DATA_DIR / "interpretation_rules.json"

st.set_page_config(page_title="Books Reconciliation App", layout="wide")

STATUS_COLORS = {
    "Matched": "#2ecc71",
    "Duplicate": "#f39c12",
    "Unknown Sender": "#e74c3c",
}


# ---------------------------------------------------------------------------
# Data pipeline (cached so the UI stays snappy)
# ---------------------------------------------------------------------------

@st.cache_data
def run_reconciliation():
    """Run the full load -> normalize -> match -> summarize pipeline once."""
    expected_df = load_expected_people(EXPECTED_PEOPLE_PATH)
    raw_payments = load_payment_history(PAYMENT_HISTORY_PATH)
    rules = load_interpretation_rules(RULES_PATH)

    normalized = apply_rules(raw_payments, expected_df, rules)
    flagged = flag_transaction_status(normalized)

    partial_threshold = float(rules.get("partial_payment_threshold", 1.0))
    person_ledger = build_person_ledger(flagged, expected_df, partial_threshold)

    expected_total = float(expected_df["ExpectedAmount"].sum())
    summary = build_summary(flagged, person_ledger, expected_total)
    followup = build_followup_list(person_ledger, flagged)

    return expected_df, flagged, person_ledger, summary, followup


try:
    expected_df, flagged, person_ledger, summary, followup = run_reconciliation()
except (FileNotFoundError, ValueError) as exc:
    st.error(f"Failed to load reconciliation data: {exc}")
    st.stop()


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

st.sidebar.title("📒 Books Reconciliation")
page = st.sidebar.radio("Navigate", ["Overview", "Reconciliation", "Reports", "About"])

st.sidebar.markdown("---")
st.sidebar.caption(
    "Expected Total is the hand-counted ground truth: **20 people x Rs. 1,000**. "
    "Every number on this page is checked against it."
)


# ---------------------------------------------------------------------------
# Shared header (top-of-page metrics) - shown on Overview & Reconciliation
# ---------------------------------------------------------------------------

def render_top_metrics():
    totals_match = validate_totals_match(summary.expected_total, summary.received_total)

    st.markdown("### Expected vs. Received")
    c1, c2, c3 = st.columns([1, 1, 1.2])
    c1.metric("Expected Total", format_currency(summary.expected_total))
    c2.metric("Received Total", format_currency(summary.received_total))
    c3.metric(
        "Difference",
        format_currency(summary.difference),
        delta=format_currency(summary.difference),
        delta_color="normal" if totals_match else "inverse",
    )

    if totals_match:
        st.success(f"✅ Books match. Received Total equals Expected Total ({format_currency(summary.expected_total)}).")
    else:
        direction = "short of" if summary.difference < 0 else "over"
        st.error(
            f"⚠️ Books do NOT match. Received Total is {format_currency(abs(summary.difference))} "
            f"{direction} the Expected Total."
        )

    st.markdown("#### Breakdown")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Matched", summary.matched_count)
    m2.metric("Missing", summary.missing_count)
    m3.metric("Unknown Sender", summary.unknown_count)
    m4.metric("Duplicate Txns", summary.duplicate_count)
    m5.metric("Follow-up Required", summary.followup_count)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

if page == "Overview":
    st.title("Books Reconciliation Dashboard")
    render_top_metrics()

    st.markdown("---")
    st.markdown("### Visual Summary")

    col1, col2 = st.columns(2)

    with col1:
        status_counts = flagged["Transaction Status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        fig_pie = px.pie(
            status_counts,
            names="Status",
            values="Count",
            title="Payment Status (Transactions)",
            color="Status",
            color_discrete_map=STATUS_COLORS,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        person_status_counts = person_ledger["Status"].value_counts().reindex(
            ["Fully Paid", "Overpaid", "Partial", "Missing"], fill_value=0
        ).reset_index()
        person_status_counts.columns = ["Status", "Count"]
        fig_bar = px.bar(
            person_status_counts,
            x="Status",
            y="Count",
            title="Matched vs. Missing (Per Person)",
            color="Status",
            text="Count",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    fig_hist = px.histogram(
        flagged,
        x="Amount",
        nbins=10,
        title="Amount Distribution (All Transactions)",
    )
    st.plotly_chart(fig_hist, use_container_width=True)

elif page == "Reconciliation":
    st.title("Reconciliation")
    render_top_metrics()

    st.markdown("---")
    st.markdown("### All Transactions")
    st.caption("Search or sort any column. Rows are flagged by status.")

    search = st.text_input("Search transactions (name, memo, transaction ID)", "")

    display_df = flagged[
        [
            "Transaction ID",
            "Date",
            "Sender Name",
            "Normalized Sender",
            "Amount",
            "Normalized Memo",
            "Transaction Status",
        ]
    ].rename(columns={"Normalized Sender": "Resolved Name", "Normalized Memo": "Memo"})

    if search:
        mask = display_df.apply(lambda col: col.astype(str).str.contains(search, case=False, na=False))
        display_df = display_df[mask.any(axis=1)]

    def highlight_status(row):
        color_map = {
            "Duplicate": "background-color: #fff3cd; color: #7a5b00",
            "Unknown Sender": "background-color: #f8d7da; color: #7a1a26",
        }
        style = color_map.get(row["Transaction Status"], "")
        return [style] * len(row)

    st.dataframe(
        display_df.style.apply(highlight_status, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")
    st.markdown("### Per-Person Ledger")
    st.caption("Every expected contributor, what they owed, and what was actually matched to them.")

    def highlight_person_status(row):
        color_map = {
            "Missing": "background-color: #f8d7da; color: #7a1a26",
            "Partial": "background-color: #fff3cd; color: #7a5b00",
            "Overpaid": "background-color: #d1ecf1; color: #0c4a5c",
        }
        style = color_map.get(row["Status"], "")
        return [style] * len(row)

    st.dataframe(
        person_ledger.style.apply(highlight_person_status, axis=1),
        use_container_width=True,
        hide_index=True,
    )

elif page == "Reports":
    st.title("Reports")
    render_top_metrics()

    st.markdown("---")
    st.markdown("### Follow-up Required")

    if followup.empty:
        st.success("No follow-up required - every expected contributor and transaction is fully reconciled.")
    else:
        st.warning(f"{len(followup)} item(s) need follow-up.")
        st.dataframe(followup, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### Download Summary Report")

    summary_row = {
        "Expected Total": summary.expected_total,
        "Received Total": summary.received_total,
        "Difference": summary.difference,
        "Matched": summary.matched_count,
        "Missing": summary.missing_count,
        "Unknown Sender Transactions": summary.unknown_count,
        "Duplicate Transactions": summary.duplicate_count,
        "Follow-up Required": summary.followup_count,
    }
    csv_bytes = build_summary_csv(person_ledger, followup, summary_row)

    st.download_button(
        label="⬇️ Download CSV Summary Report",
        data=csv_bytes,
        file_name="reconciliation_summary.csv",
        mime="text/csv",
    )

    st.caption("Future improvement: Excel/PDF export (out of scope for this task - see README).")

elif page == "About":
    st.title("About This Project")

    st.markdown(
        """
This app reconciles a **hand-counted total of Rs. 20,000** (20 people x
Rs. 1,000 each) against a **messy digital payment history**, using
explicit, documented interpretation rules for ambiguous entries.

**How verification was done:**
The Expected Total (Rs. 20,000) was compared against the Calculated
Total produced by the reconciliation engine. Every missing, duplicate,
and unmatched transaction shown above was cross-checked against what
was already known about the 20 contributors, confirming each was
correctly flagged.

**Data sources (all in `data/`):**
- `expected_people.csv` - the ground truth (20 contributors x Rs. 1,000)
- `payment_history.csv` - the raw, messy payment export (loaded unchanged)
- `interpretation_rules.json` - documented rules for name/memo ambiguity,
  applied automatically by `src/rules.py`

See `README.md` for setup instructions and `report.md` for the full
project writeup, including the AI prompts used to build this app.
        """
    )
