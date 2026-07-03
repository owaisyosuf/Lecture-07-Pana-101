"""
utils.py

Small shared helpers: currency formatting, CSV export for the download
button, and lightweight input validation used across the app. Kept
together with basic "validator" responsibilities so we don't need a
separate validator.py module for a project this size.
"""

from __future__ import annotations

import io

import pandas as pd


def format_currency(amount: float) -> str:
    """Format a number as a Rupee currency string.

    Args:
        amount: Numeric amount.

    Returns:
        String like "Rs. 20,000".
    """
    return f"Rs. {amount:,.0f}"


def validate_totals_match(expected_total: float, received_total: float, tolerance: float = 0.01) -> bool:
    """Check whether the calculated total matches the expected total.

    Args:
        expected_total: The hand-counted ground truth total.
        received_total: The calculated total from the reconciliation engine.
        tolerance: Allowed floating-point tolerance.

    Returns:
        True if the totals match within tolerance, else False.
    """
    return abs(expected_total - received_total) <= tolerance


def build_summary_csv(person_ledger: pd.DataFrame, followup_list: pd.DataFrame, summary_row: dict) -> bytes:
    """Build a downloadable CSV summary report.

    The CSV has three sections: the top-line summary, the per-person
    ledger, and the follow-up list - written into a single file so a
    single download button covers the whole reconciliation.

    Args:
        person_ledger: Output of reconciler.build_person_ledger().
        followup_list: Output of reconciler.build_followup_list().
        summary_row: Dict of top-line summary metrics to write as a header block.

    Returns:
        UTF-8 encoded CSV content as bytes, ready for st.download_button.
    """
    buffer = io.StringIO()

    buffer.write("=== RECONCILIATION SUMMARY ===\n")
    for key, value in summary_row.items():
        buffer.write(f"{key},{value}\n")
    buffer.write("\n")

    buffer.write("=== PER-PERSON LEDGER ===\n")
    person_ledger.to_csv(buffer, index=False)
    buffer.write("\n")

    buffer.write("=== FOLLOW-UP REQUIRED ===\n")
    if followup_list.empty:
        buffer.write("No follow-up required - all payments reconciled.\n")
    else:
        followup_list.to_csv(buffer, index=False)

    return buffer.getvalue().encode("utf-8")


def validate_dataframe_not_empty(df: pd.DataFrame, name: str) -> None:
    """Raise a clear error if a required DataFrame is empty.

    Args:
        df: DataFrame to check.
        name: Human-readable name for the error message.

    Raises:
        ValueError: If df has zero rows.
    """
    if df.empty:
        raise ValueError(f"{name} is empty - check the source data file.")
