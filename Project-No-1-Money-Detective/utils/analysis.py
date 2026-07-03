"""
analysis.py
-----------
Core, rule-based analysis engine for Money Detective.

Every function here is a small, pure(ish) helper that takes a pandas
DataFrame of transactions and returns either another DataFrame or a plain
Python dict/list. There is no AI/LLM call anywhere in this file -- every
"detection" is a deterministic rule implemented directly in pandas/Python,
which is what makes the results reproducible and easy to verify by hand.

Expected input DataFrame columns: Date, Description, Amount
    - Date: parseable date string / datetime
    - Description: short text label for the transaction
    - Amount: signed number. Negative = money out (expense), positive =
      money in (income/credit).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from utils.rules import (
    CATEGORY_KEYWORDS,
    DEFAULT_CATEGORY,
    INCOME_CATEGORY,
    MIN_MONTHS_FOR_RECURRING,
    SUBSCRIPTION_KEYWORDS,
    TOTAL_VERIFICATION_TOLERANCE,
)

logger = logging.getLogger("money_detective")
if not logger.handlers:
    # Keep logging quiet by default; the CLI script attaches a console
    # handler explicitly when run directly.
    logger.addHandler(logging.NullHandler())


REQUIRED_COLUMNS = ["Date", "Description", "Amount"]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_transactions_csv(path) -> pd.DataFrame:
    """Load and clean the transactions CSV file.

    Args:
        path: A filesystem path (str/Path) OR a file-like object such as a
            Streamlit `UploadedFile` (anything pandas.read_csv accepts).

    Returns:
        A cleaned DataFrame with a parsed 'Date' column and a 'Month'
        period column (e.g. '2026-06') used for recurring-payment checks.

    Raises:
        FileNotFoundError: If a path is given and it does not exist.
        ValueError: If required columns are missing.
    """
    if hasattr(path, "read"):
        df = pd.read_csv(path)
    else:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Transactions CSV not found: {path}")
        df = pd.read_csv(path)
    return _clean_transactions(df)


def load_transactions_excel(path, sheet_name: int | str = 0) -> tuple[pd.DataFrame, float | None]:
    """Load the transactions Excel file AND read its bottom SUM() total.

    The .xlsx sample file has a bottom row with a formula like
    '=SUM(C2:C21)'. That row is NOT a transaction, so it is excluded from
    the returned DataFrame, but its calculated value is returned separately
    so the caller can verify Python's own recomputed total against it.

    Args:
        path: A filesystem path (str/Path) OR a file-like object such as a
            Streamlit `UploadedFile`.
        sheet_name: Worksheet to read (default: first sheet).

    Returns:
        (df, excel_total) where excel_total is the value of the bottom
        SUM() cell, or None if it could not be found/read (e.g. the file
        was never recalculated by Excel/LibreOffice).
    """
    if hasattr(path, "read"):
        raw = pd.read_excel(path, sheet_name=sheet_name, header=0)
    else:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Transactions Excel file not found: {path}")
        raw = pd.read_excel(path, sheet_name=sheet_name, header=0)

    raw.columns = [str(c).strip() for c in raw.columns]

    # The SUM row has a non-numeric label/blank in some columns -- isolate
    # it before cleaning the rest of the rows.
    is_total_row = raw["Amount"].apply(lambda v: not _is_number(v)) | raw["Date"].isna()
    total_rows = raw[is_total_row]
    data_rows = raw[~is_total_row].copy()

    excel_total: float | None = None
    if not total_rows.empty:
        last_amount = total_rows.iloc[-1]["Amount"]
        if _is_number(last_amount):
            excel_total = float(last_amount)

    df = _clean_transactions(data_rows)
    return df, excel_total


def _is_number(value: object) -> bool:
    try:
        float(value)  # type: ignore[arg-type]
        return True
    except (TypeError, ValueError):
        return False


def _clean_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Validate columns, parse dates, and add a helper 'Month' column."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required column(s): {missing}")

    df = df[REQUIRED_COLUMNS].copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date", "Description", "Amount"]).reset_index(drop=True)
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df = df.dropna(subset=["Amount"]).reset_index(drop=True)
    df["Description"] = df["Description"].astype(str).str.strip()
    df["Month"] = df["Date"].dt.to_period("M").astype(str)
    return df


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------
def detect_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Flag transactions that share the same Date + Description + Amount.

    Rule: if two or more rows are identical on (Date, Description, Amount),
    every one of those rows is a "duplicate row" -- this is the classic
    sign of an accidental double charge.

    Returns:
        A DataFrame containing only the duplicate rows (all occurrences,
        not just the repeats), sorted by Date/Description for readability.
    """
    if df.empty:
        return df.copy()

    dup_mask = df.duplicated(subset=["Date", "Description", "Amount"], keep=False)
    duplicates = df[dup_mask].sort_values(["Date", "Description"]).reset_index(drop=True)
    return duplicates


def summarize_duplicates(duplicates: pd.DataFrame) -> dict:
    """Turn the duplicate-rows DataFrame into headline numbers."""
    if duplicates.empty:
        return {"row_count": 0, "group_count": 0, "total_amount": 0.0}

    groups = duplicates.groupby(["Date", "Description", "Amount"])
    return {
        "row_count": int(len(duplicates)),
        "group_count": int(groups.ngroups),
        "total_amount": float(duplicates["Amount"].sum()),
    }


# ---------------------------------------------------------------------------
# Recurring payment detection
# ---------------------------------------------------------------------------
def detect_recurring(df: pd.DataFrame, min_months: int = MIN_MONTHS_FOR_RECURRING) -> pd.DataFrame:
    """Find descriptions that charge in two or more different months.

    Rule: group by exact Description text. If a description appears with
    at least `min_months` distinct Year-Month values, treat it as a
    recurring payment (e.g. a subscription or monthly bill).

    Returns:
        DataFrame with one row per recurring description: Description,
        Months (count), AverageAmount, EstimatedMonthlyCost, FirstSeen,
        LastSeen.
    """
    empty_cols = ["Description", "Months", "AverageAmount", "EstimatedMonthlyCost", "FirstSeen", "LastSeen"]
    if df.empty:
        return pd.DataFrame(columns=empty_cols)

    expense_df = df[df["Amount"] < 0]
    grouped = expense_df.groupby("Description")

    rows = []
    for description, group in grouped:
        distinct_months = group["Month"].nunique()
        if distinct_months >= min_months:
            rows.append(
                {
                    "Description": description,
                    "Months": int(distinct_months),
                    "AverageAmount": float(group["Amount"].mean()),
                    "EstimatedMonthlyCost": float(group["Amount"].abs().mean()),
                    "FirstSeen": group["Date"].min().date().isoformat(),
                    "LastSeen": group["Date"].max().date().isoformat(),
                }
            )

    result = pd.DataFrame(rows, columns=empty_cols) if not rows else pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values("EstimatedMonthlyCost", ascending=False).reset_index(drop=True)
    return result


# ---------------------------------------------------------------------------
# Forgotten subscription detection
# ---------------------------------------------------------------------------
def detect_forgotten_subscriptions(
    recurring: pd.DataFrame,
    subscription_keywords: list[str] = SUBSCRIPTION_KEYWORDS,
) -> pd.DataFrame:
    """Flag recurring charges that look like subscriptions worth a second look.

    Rule: a recurring payment (from detect_recurring) is flagged as a
    "forgotten subscription" candidate if its description matches one of
    the SUBSCRIPTION_KEYWORDS. The sample data has no login/usage log, so
    -- per the project brief -- any keyword match is treated as having "no
    matching usage signal" and is surfaced for the user to manually
    confirm they still use it.

    Returns:
        Subset of `recurring` whose Description matched a keyword, with an
        added 'MatchedKeyword' column.
    """
    if recurring.empty:
        return recurring.assign(MatchedKeyword=pd.Series(dtype=str))

    def first_match(description: str) -> str | None:
        text = description.lower()
        for keyword in subscription_keywords:
            if keyword in text:
                return keyword
        return None

    flagged = recurring.copy()
    flagged["MatchedKeyword"] = flagged["Description"].apply(first_match)
    flagged = flagged[flagged["MatchedKeyword"].notna()].reset_index(drop=True)
    return flagged


# ---------------------------------------------------------------------------
# Category spend
# ---------------------------------------------------------------------------
def categorize_transaction(description: str, amount: float) -> str:
    """Assign a single category to one transaction using keyword rules.

    Positive amounts are always 'Income'. Otherwise, the first category in
    CATEGORY_KEYWORDS whose keyword appears in the (lowercased) description
    wins. If nothing matches, the transaction falls into DEFAULT_CATEGORY.
    """
    if amount > 0:
        return INCOME_CATEGORY

    text = description.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return category
    return DEFAULT_CATEGORY


def add_category_column(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of df with a 'Category' column added."""
    out = df.copy()
    out["Category"] = out.apply(lambda row: categorize_transaction(row["Description"], row["Amount"]), axis=1)
    return out


def category_spend_summary(df_with_category: pd.DataFrame) -> pd.DataFrame:
    """Total expense amount (absolute value) per category, expenses only."""
    expenses = df_with_category[df_with_category["Amount"] < 0]
    if expenses.empty:
        return pd.DataFrame(columns=["Category", "TotalSpend", "TransactionCount"])

    summary = (
        expenses.groupby("Category")
        .agg(TotalSpend=("Amount", lambda s: float(s.abs().sum())), TransactionCount=("Amount", "count"))
        .reset_index()
        .sort_values("TotalSpend", ascending=False)
        .reset_index(drop=True)
    )
    return summary


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------
def compute_summary_stats(df: pd.DataFrame) -> dict:
    """Headline totals/count/max/min/average used in the dashboard cards."""
    if df.empty:
        return {
            "transaction_count": 0,
            "total_income": 0.0,
            "total_expense": 0.0,
            "net_total": 0.0,
            "average_transaction": 0.0,
            "largest_expense": 0.0,
            "smallest_expense": 0.0,
        }

    expenses = df[df["Amount"] < 0]["Amount"]
    income = df[df["Amount"] > 0]["Amount"]

    return {
        "transaction_count": int(len(df)),
        "total_income": float(income.sum()),
        "total_expense": float(expenses.abs().sum()),
        "net_total": float(df["Amount"].sum()),
        "average_transaction": float(df["Amount"].mean()),
        "largest_expense": float(expenses.abs().max()) if not expenses.empty else 0.0,
        "smallest_expense": float(expenses.abs().min()) if not expenses.empty else 0.0,
    }


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Per-month totals: income, expense, net, and transaction count."""
    if df.empty:
        return pd.DataFrame(columns=["Month", "Income", "Expense", "Net", "TransactionCount"])

    def _agg(group: pd.DataFrame) -> pd.Series:
        income = group.loc[group["Amount"] > 0, "Amount"].sum()
        expense = group.loc[group["Amount"] < 0, "Amount"].abs().sum()
        return pd.Series(
            {
                "Income": float(income),
                "Expense": float(expense),
                "Net": float(income - expense),
                "TransactionCount": int(len(group)),
            }
        )

    summary = df.groupby("Month").apply(_agg, include_groups=False).reset_index()
    return summary.sort_values("Month").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Total verification (Python recompute vs Excel SUM cell)
# ---------------------------------------------------------------------------
def verify_total(
    python_total: float, excel_total: float | None, tolerance: float = TOTAL_VERIFICATION_TOLERANCE
) -> dict:
    """Compare the Python-recomputed total against the Excel SUM() cell.

    Returns:
        dict with keys: verified (bool or None if excel_total missing),
        python_total, excel_total, delta, message (ready-to-print string).
    """
    if excel_total is None:
        return {
            "verified": None,
            "python_total": python_total,
            "excel_total": None,
            "delta": None,
            "message": "Could not read an Excel SUM() total to verify against.",
        }

    delta = round(python_total - excel_total, 2)
    verified = abs(delta) <= tolerance
    message = "✅ Total Verified" if verified else f"❌ Total Mismatch (delta: {delta:+,.2f})"

    return {
        "verified": verified,
        "python_total": python_total,
        "excel_total": excel_total,
        "delta": delta,
        "message": message,
    }


# ---------------------------------------------------------------------------
# Plain-language summary + downloadable report
# ---------------------------------------------------------------------------
def build_plain_language_summary(
    duplicates_summary: dict,
    recurring: pd.DataFrame,
    forgotten: pd.DataFrame,
    stats: dict,
) -> list[str]:
    """Build a list of short, human-readable insight sentences."""
    lines: list[str] = []

    if duplicates_summary["row_count"] > 0:
        lines.append(
            f"You have {duplicates_summary['row_count']} duplicate charges totaling "
            f"Rs. {abs(duplicates_summary['total_amount']):,.0f} — check if you were billed twice."
        )
    else:
        lines.append("No duplicate charges detected. Nice and clean.")

    if not recurring.empty:
        monthly_cost = recurring["EstimatedMonthlyCost"].sum()
        lines.append(f"{len(recurring)} recurring payments cost about Rs. {monthly_cost:,.0f}/month in total.")
    else:
        lines.append("No recurring monthly payments detected yet.")

    if not forgotten.empty:
        names = ", ".join(forgotten["Description"].tolist())
        forgotten_cost = forgotten["EstimatedMonthlyCost"].sum()
        lines.append(
            f"{len(forgotten)} subscription(s) — {names} — are still charging Rs. {forgotten_cost:,.0f}/month. "
            "Double check you're still using these."
        )
    else:
        lines.append("No subscriptions flagged as potentially forgotten.")

    lines.append(
        f"Across {stats['transaction_count']} transactions: Rs. {stats['total_expense']:,.0f} spent, "
        f"Rs. {stats['total_income']:,.0f} received, net Rs. {stats['net_total']:,.0f}."
    )

    if stats["largest_expense"] > 0:
        lines.append(f"Your single largest expense was Rs. {stats['largest_expense']:,.0f}.")

    return lines


def build_text_report(
    stats: dict,
    duplicates_summary: dict,
    recurring: pd.DataFrame,
    forgotten: pd.DataFrame,
    category_summary: pd.DataFrame,
    monthly: pd.DataFrame,
    verification: dict,
    insights: list[str],
) -> str:
    """Assemble the full downloadable plain-text report."""
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("MONEY DETECTIVE — TRANSACTION ANALYSIS REPORT")
    lines.append("=" * 60)
    lines.append("")

    lines.append("SUMMARY")
    lines.append("-" * 60)
    lines.append(f"Transactions analyzed  : {stats['transaction_count']}")
    lines.append(f"Total spent            : Rs. {stats['total_expense']:,.2f}")
    lines.append(f"Total received         : Rs. {stats['total_income']:,.2f}")
    lines.append(f"Net total              : Rs. {stats['net_total']:,.2f}")
    lines.append(f"Average transaction    : Rs. {stats['average_transaction']:,.2f}")
    lines.append(f"Largest expense        : Rs. {stats['largest_expense']:,.2f}")
    lines.append(f"Smallest expense       : Rs. {stats['smallest_expense']:,.2f}")
    lines.append("")

    lines.append("TOTAL VERIFICATION (Python vs Excel SUM)")
    lines.append("-" * 60)
    lines.append(verification["message"])
    if verification["excel_total"] is not None:
        lines.append(
            f"Python total: {verification['python_total']:,.2f}  |  Excel total: {verification['excel_total']:,.2f}"
        )
    lines.append("")

    lines.append("DUPLICATE CHARGES")
    lines.append("-" * 60)
    lines.append(
        f"Duplicate rows: {duplicates_summary['row_count']}  |  Groups: {duplicates_summary['group_count']}  "
        f"|  Total: Rs. {abs(duplicates_summary['total_amount']):,.2f}"
    )
    lines.append("")

    lines.append("RECURRING PAYMENTS")
    lines.append("-" * 60)
    if recurring.empty:
        lines.append("None detected.")
    else:
        for _, row in recurring.iterrows():
            lines.append(
                f"  - {row['Description']}: ~Rs. {row['EstimatedMonthlyCost']:,.0f}/month "
                f"(seen in {row['Months']} months)"
            )
    lines.append("")

    lines.append("POSSIBLY FORGOTTEN SUBSCRIPTIONS")
    lines.append("-" * 60)
    if forgotten.empty:
        lines.append("None flagged.")
    else:
        for _, row in forgotten.iterrows():
            lines.append(f"  - {row['Description']}: ~Rs. {row['EstimatedMonthlyCost']:,.0f}/month")
    lines.append("")

    lines.append("CATEGORY BREAKDOWN")
    lines.append("-" * 60)
    if category_summary.empty:
        lines.append("No expense data.")
    else:
        for _, row in category_summary.iterrows():
            lines.append(f"  - {row['Category']}: Rs. {row['TotalSpend']:,.2f} ({int(row['TransactionCount'])} txns)")
    lines.append("")

    lines.append("MONTHLY SUMMARY")
    lines.append("-" * 60)
    if monthly.empty:
        lines.append("No monthly data.")
    else:
        for _, row in monthly.iterrows():
            lines.append(
                f"  - {row['Month']}: Income Rs. {row['Income']:,.0f} | Expense Rs. {row['Expense']:,.0f} "
                f"| Net Rs. {row['Net']:,.0f}"
            )
    lines.append("")

    lines.append("PLAIN-LANGUAGE INSIGHTS")
    lines.append("-" * 60)
    for insight in insights:
        lines.append(f"  • {insight}")
    lines.append("")
    lines.append("=" * 60)
    lines.append("Generated by Money Detective — fully rule-based, no AI/LLM calls.")
    lines.append("=" * 60)

    return "\n".join(lines)
