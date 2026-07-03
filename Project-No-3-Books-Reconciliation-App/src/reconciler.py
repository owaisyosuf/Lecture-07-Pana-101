"""
reconciler.py

The core reconciliation engine. Takes the rule-normalized payment history
and the expected contributors list, then:

    1. Flags each transaction's status (Matched, Duplicate, Unknown Sender).
    2. Aggregates payments per expected person and flags their status
       (Fully Paid, Partial, Overpaid, Missing).
    3. Produces the top-line summary (Expected Total, Received Total,
       Difference, counts) used by the Streamlit UI.
    4. Produces the follow-up list of people who still need action.

No file I/O and no ambiguity resolution happens here - that's loader.py
and rules.py. This module only does matching/aggregation math.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ReconciliationSummary:
    """Top-line reconciliation numbers shown at the top of the dashboard."""

    expected_total: float
    received_total: float
    difference: float
    matched_count: int
    missing_count: int
    unknown_count: int
    duplicate_count: int
    followup_count: int
    people_total: int = 20


def flag_transaction_status(normalized_payments: pd.DataFrame) -> pd.DataFrame:
    """Flag each transaction row as Matched, Duplicate, or Unknown Sender.

    Duplicate detection: if a Normalized Sender has more than one
    transaction, every transaction after the first (chronologically, then
    by Transaction ID) for that sender is flagged Duplicate. The first
    transaction keeps whatever status matching gives it.

    Args:
        normalized_payments: Output of rules.apply_rules().

    Returns:
        Copy of the input DataFrame with an added "Transaction Status" column.
    """
    df = normalized_payments.copy()
    df = df.sort_values(["Normalized Sender", "Date", "Transaction ID"]).reset_index(drop=True)

    df["Transaction Status"] = "Matched"
    df.loc[df["Normalized Sender"] == "UNKNOWN", "Transaction Status"] = "Unknown Sender"

    # Mark every occurrence after the first, per sender, as Duplicate
    # (skip UNKNOWN - unrelated unknown senders shouldn't collide as "duplicates").
    known_mask = df["Normalized Sender"] != "UNKNOWN"
    dup_mask = known_mask & df.duplicated(subset="Normalized Sender", keep="first")
    df.loc[dup_mask, "Transaction Status"] = "Duplicate"

    return df


def build_person_ledger(flagged_payments: pd.DataFrame, expected_df: pd.DataFrame, partial_threshold: float = 1.0) -> pd.DataFrame:
    """Aggregate payments per expected person and determine their status.

    Only the FIRST (non-duplicate) matched payment per person counts
    toward what they owe; duplicate payments are recorded but do not
    "double count" a person as overpaid unless the person's legitimate
    payment itself exceeded the expected amount.

    Args:
        flagged_payments: Output of flag_transaction_status().
        expected_df: Expected contributors DataFrame.
        partial_threshold: Fraction of ExpectedAmount below which a
            matched payment is considered Partial (from rules JSON).

    Returns:
        DataFrame with one row per expected person: Name, ExpectedAmount,
        PaidAmount, Status, TransactionIDs.
    """
    counted = flagged_payments[flagged_payments["Transaction Status"] == "Matched"]
    paid_by_person = counted.groupby("Normalized Sender")["Amount"].sum()
    txn_ids_by_person = counted.groupby("Normalized Sender")["Transaction ID"].apply(list)

    rows = []
    for _, person in expected_df.iterrows():
        name = person["Name"]
        expected_amount = float(person["ExpectedAmount"])
        paid_amount = float(paid_by_person.get(name, 0.0))
        txn_ids = txn_ids_by_person.get(name, [])

        if paid_amount == 0.0:
            status = "Missing"
        elif paid_amount < expected_amount * partial_threshold:
            status = "Partial"
        elif paid_amount > expected_amount:
            status = "Overpaid"
        else:
            status = "Fully Paid"

        rows.append(
            {
                "Name": name,
                "ExpectedAmount": expected_amount,
                "PaidAmount": paid_amount,
                "Difference": round(paid_amount - expected_amount, 2),
                "Status": status,
                "TransactionIDs": ", ".join(txn_ids) if txn_ids else "-",
            }
        )

    return pd.DataFrame(rows)


def build_summary(flagged_payments: pd.DataFrame, person_ledger: pd.DataFrame, expected_total: float) -> ReconciliationSummary:
    """Compute the top-line reconciliation summary.

    Args:
        flagged_payments: Output of flag_transaction_status().
        person_ledger: Output of build_person_ledger().
        expected_total: The ground-truth expected total (Rs. 20,000).

    Returns:
        A ReconciliationSummary with all headline metrics.
    """
    received_total = float(person_ledger["PaidAmount"].sum())
    difference = round(received_total - expected_total, 2)

    matched_count = int((person_ledger["Status"].isin(["Fully Paid", "Overpaid"])).sum())
    missing_count = int((person_ledger["Status"] == "Missing").sum())
    partial_count = int((person_ledger["Status"] == "Partial").sum())
    unknown_count = int((flagged_payments["Transaction Status"] == "Unknown Sender").sum())
    duplicate_count = int((flagged_payments["Transaction Status"] == "Duplicate").sum())
    followup_count = missing_count + partial_count + unknown_count

    return ReconciliationSummary(
        expected_total=expected_total,
        received_total=received_total,
        difference=difference,
        matched_count=matched_count,
        missing_count=missing_count,
        unknown_count=unknown_count,
        duplicate_count=duplicate_count,
        followup_count=followup_count,
        people_total=len(person_ledger),
    )


def build_followup_list(person_ledger: pd.DataFrame, flagged_payments: pd.DataFrame) -> pd.DataFrame:
    """Build the explicit "who needs follow-up, and for how much" list.

    Includes: Missing people (owe full amount), Partial payers (owe the
    gap), and Unknown-sender transactions (need identification).

    Args:
        person_ledger: Output of build_person_ledger().
        flagged_payments: Output of flag_transaction_status().

    Returns:
        DataFrame with columns: Name, Reason, AmountOutstanding, Notes.
    """
    rows = []

    for _, person in person_ledger.iterrows():
        if person["Status"] == "Missing":
            rows.append(
                {
                    "Name": person["Name"],
                    "Reason": "Missing Payment",
                    "AmountOutstanding": person["ExpectedAmount"],
                    "Notes": "No matching transaction found at all.",
                }
            )
        elif person["Status"] == "Partial":
            outstanding = round(person["ExpectedAmount"] - person["PaidAmount"], 2)
            rows.append(
                {
                    "Name": person["Name"],
                    "Reason": "Partial Payment",
                    "AmountOutstanding": outstanding,
                    "Notes": f"Paid Rs. {person['PaidAmount']:.0f} of Rs. {person['ExpectedAmount']:.0f}.",
                }
            )

    unknown_txns = flagged_payments[flagged_payments["Transaction Status"] == "Unknown Sender"]
    for _, txn in unknown_txns.iterrows():
        rows.append(
            {
                "Name": txn["Sender Name"],
                "Reason": "Unknown Sender",
                "AmountOutstanding": 0.0,
                "Notes": f"Rs. {txn['Amount']:.0f} received ({txn['Transaction ID']}) but sender not identifiable.",
            }
        )

    return pd.DataFrame(rows)
