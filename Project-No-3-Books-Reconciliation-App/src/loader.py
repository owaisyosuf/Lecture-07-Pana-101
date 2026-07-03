"""
loader.py

Responsible for loading the three raw inputs the reconciliation engine
needs:
    1. expected_people.csv    - the hand-counted ground truth (20 x Rs.1000)
    2. payment_history.csv    - the messy digital payment export
    3. interpretation_rules.json - documented rules for ambiguous entries

No cleaning or matching logic lives here - this module only reads files
and does basic structural validation. Interpretation happens in rules.py,
matching/aggregation happens in reconciler.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

EXPECTED_PEOPLE_COLUMNS = {"Name", "ExpectedAmount"}
PAYMENT_HISTORY_COLUMNS = {"Date", "Sender Name", "Amount", "Memo", "Transaction ID"}


def load_expected_people(path: Path) -> pd.DataFrame:
    """Load the hand-counted list of expected contributors.

    Args:
        path: Path to expected_people.csv.

    Returns:
        DataFrame with columns Name, ExpectedAmount.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If required columns are missing.
    """
    if not path.exists():
        raise FileNotFoundError(f"Expected people file not found: {path}")

    df = pd.read_csv(path)
    missing_cols = EXPECTED_PEOPLE_COLUMNS - set(df.columns)
    if missing_cols:
        raise ValueError(f"expected_people.csv is missing columns: {missing_cols}")

    df["Name"] = df["Name"].astype(str).str.strip()
    df["ExpectedAmount"] = pd.to_numeric(df["ExpectedAmount"], errors="coerce")

    if df["ExpectedAmount"].isna().any():
        raise ValueError("expected_people.csv contains non-numeric ExpectedAmount values")

    return df


def load_payment_history(path: Path) -> pd.DataFrame:
    """Load the raw, messy digital payment history exactly as received.

    No name cleaning, casing fixes, or deduplication happens here - the
    data is loaded as-is so the interpretation rules layer has the true
    raw input to work against.

    Args:
        path: Path to payment_history.csv.

    Returns:
        DataFrame with columns Date, Sender Name, Amount, Memo,
        Transaction ID.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If required columns are missing.
    """
    if not path.exists():
        raise FileNotFoundError(f"Payment history file not found: {path}")

    df = pd.read_csv(path, keep_default_na=False, na_values=["", "NaN", "nan"])
    missing_cols = PAYMENT_HISTORY_COLUMNS - set(df.columns)
    if missing_cols:
        raise ValueError(f"payment_history.csv is missing columns: {missing_cols}")

    # Keep Amount numeric but preserve everything else exactly as received
    # (including blank memos, odd casing, odd separators, emoji, etc.)
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df["Memo"] = df["Memo"].fillna("")

    if df["Amount"].isna().any():
        bad_rows = df[df["Amount"].isna()]["Transaction ID"].tolist()
        raise ValueError(f"Non-numeric Amount found in transactions: {bad_rows}")

    return df


def load_interpretation_rules(path: Path) -> dict:
    """Load the documented interpretation rules for ambiguous entries.

    Args:
        path: Path to interpretation_rules.json.

    Returns:
        Parsed rules dictionary (name_aliases, memo_aliases,
        known_unknown_senders, partial_payment_threshold, ...).

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not valid JSON.
    """
    if not path.exists():
        raise FileNotFoundError(f"Interpretation rules file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            rules = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"interpretation_rules.json is not valid JSON: {exc}") from exc

    return rules
