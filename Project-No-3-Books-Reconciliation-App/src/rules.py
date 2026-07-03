"""
rules.py

Applies the interpretation rules loaded from interpretation_rules.json to
the raw payment history. This is the ONLY place ambiguous-entry decisions
get made, and every decision comes from the JSON file - nothing here is
hardcoded reconciliation logic.

The output is a normalized copy of the payment history with two new
columns:
    - Normalized Sender: best-guess canonical name (or "UNKNOWN")
    - Normalized Memo:   cosmetic cleanup of the memo field
"""

from __future__ import annotations

import re

import pandas as pd


def _fold(name: str) -> str:
    """Case-fold and collapse whitespace for tolerant comparison."""
    return re.sub(r"\s+", " ", str(name).strip()).casefold()


def normalize_sender_name(raw_name: str, expected_names: list[str], name_aliases: dict[str, str]) -> str:
    """Resolve a raw sender name to a canonical expected name, or UNKNOWN.

    Resolution order:
        1. Exact case-insensitive match against an alias key in the rules.
        2. Exact case-insensitive match against an expected contributor name.
        3. Otherwise -> "UNKNOWN" (flagged for manual follow-up).

    Args:
        raw_name: The raw Sender Name field from the payment history.
        expected_names: List of canonical expected contributor names.
        name_aliases: Mapping of raw/variant names to canonical names,
            as documented in interpretation_rules.json.

    Returns:
        The canonical name if resolvable, otherwise "UNKNOWN".
    """
    folded_raw = _fold(raw_name)

    folded_aliases = {_fold(k): v for k, v in name_aliases.items()}
    if folded_raw in folded_aliases:
        return folded_aliases[folded_raw]

    folded_expected = {_fold(n): n for n in expected_names}
    if folded_raw in folded_expected:
        return folded_expected[folded_raw]

    return "UNKNOWN"


def normalize_memo(raw_memo: str, memo_aliases: dict[str, str]) -> str:
    """Clean up a memo field for display purposes only.

    Memo normalization is cosmetic and never affects matching - it only
    makes the transactions table more readable (e.g. stripping emoji,
    unifying separators).

    Args:
        raw_memo: The raw Memo field from the payment history.
        memo_aliases: Mapping of raw memo text to cleaned display text,
            as documented in interpretation_rules.json.

    Returns:
        The cleaned memo string, or "(no memo)" if blank.
    """
    if raw_memo is None or str(raw_memo).strip() == "":
        return "(no memo)"

    if raw_memo in memo_aliases:
        return memo_aliases[raw_memo]

    return str(raw_memo).strip()


def apply_rules(payments: pd.DataFrame, expected_df: pd.DataFrame, rules: dict) -> pd.DataFrame:
    """Apply all interpretation rules to the raw payment history.

    Args:
        payments: Raw payment history DataFrame (from loader.load_payment_history).
        expected_df: Expected contributors DataFrame (from loader.load_expected_people).
        rules: Parsed interpretation rules (from loader.load_interpretation_rules).

    Returns:
        A copy of `payments` with added columns:
            - Normalized Sender
            - Normalized Memo
    """
    df = payments.copy()

    expected_names = expected_df["Name"].tolist()
    name_aliases = rules.get("name_aliases", {})
    memo_aliases = rules.get("memo_aliases", {})

    df["Normalized Sender"] = df["Sender Name"].apply(
        lambda n: normalize_sender_name(n, expected_names, name_aliases)
    )
    df["Normalized Memo"] = df["Memo"].apply(lambda m: normalize_memo(m, memo_aliases))

    return df
