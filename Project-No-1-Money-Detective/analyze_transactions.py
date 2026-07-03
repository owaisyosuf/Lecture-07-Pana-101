#!/usr/bin/env python3
"""
analyze_transactions.py
------------------------
Command-line entry point for Money Detective.

Reads transactions.csv AND transactions.xlsx, runs every rule-based
analysis (duplicates, recurring payments, forgotten subscriptions,
category spend, summary stats, monthly summary), then verifies the
Python-computed total against the SUM() formula stored in the Excel
file's bottom row.

Usage:
    python analyze_transactions.py
    python analyze_transactions.py --csv path/to/transactions.csv --xlsx path/to/transactions.xlsx

No AI/LLM calls are made anywhere in this script -- every "detection" is
deterministic pandas/Python logic that you can step through and verify by
hand against the sample data.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from utils import analysis as az

# --- logging setup ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("money_detective")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Money Detective — rule-based transaction analyzer")
    parser.add_argument("--csv", default="transactions.csv", help="Path to transactions CSV file")
    parser.add_argument("--xlsx", default="transactions.xlsx", help="Path to transactions Excel file")
    return parser.parse_args()


def print_section(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def main() -> int:
    args = parse_args()

    try:
        logger.info("Loading CSV: %s", args.csv)
        df = az.load_transactions_csv(args.csv)

        logger.info("Loading Excel: %s", args.xlsx)
        _, excel_total = az.load_transactions_excel(args.xlsx)
    except FileNotFoundError as exc:
        logger.error("File not found: %s", exc)
        return 1
    except ValueError as exc:
        logger.error("Invalid data: %s", exc)
        return 1
    except Exception:  # noqa: BLE001 -- top-level CLI guard, log and exit cleanly
        logger.exception("Unexpected error while loading transaction files")
        return 1

    logger.info("Loaded %d transactions", len(df))

    # --- run every rule-based analysis ---
    duplicates = az.detect_duplicates(df)
    duplicates_summary = az.summarize_duplicates(duplicates)

    recurring = az.detect_recurring(df)
    forgotten = az.detect_forgotten_subscriptions(recurring)

    categorized = az.add_category_column(df)
    category_summary = az.category_spend_summary(categorized)

    stats = az.compute_summary_stats(df)
    monthly = az.monthly_summary(df)

    verification = az.verify_total(stats["net_total"], excel_total)
    insights = az.build_plain_language_summary(duplicates_summary, recurring, forgotten, stats)

    # --- print results ---
    print_section("SUMMARY STATISTICS")
    print(f"Transactions     : {stats['transaction_count']}")
    print(f"Total spent      : Rs. {stats['total_expense']:,.2f}")
    print(f"Total received   : Rs. {stats['total_income']:,.2f}")
    print(f"Net total        : Rs. {stats['net_total']:,.2f}")
    print(f"Average txn      : Rs. {stats['average_transaction']:,.2f}")
    print(f"Largest expense  : Rs. {stats['largest_expense']:,.2f}")
    print(f"Smallest expense : Rs. {stats['smallest_expense']:,.2f}")

    print_section("DUPLICATE TRANSACTIONS")
    if duplicates.empty:
        print("None found.")
    else:
        print(duplicates.to_string(index=False))
        print(f"\n{duplicates_summary['row_count']} duplicate rows across "
              f"{duplicates_summary['group_count']} group(s), totaling Rs. {duplicates_summary['total_amount']:,.2f}")

    print_section("RECURRING PAYMENTS (>= 2 different months)")
    if recurring.empty:
        print("None found.")
    else:
        print(recurring.to_string(index=False))

    print_section("FORGOTTEN SUBSCRIPTIONS (recurring + keyword match)")
    if forgotten.empty:
        print("None flagged.")
    else:
        print(forgotten.to_string(index=False))

    print_section("CATEGORY SPEND")
    if category_summary.empty:
        print("No expense data.")
    else:
        print(category_summary.to_string(index=False))

    print_section("MONTHLY SUMMARY")
    if monthly.empty:
        print("No monthly data.")
    else:
        print(monthly.to_string(index=False))

    print_section("TOTAL VERIFICATION (Python recompute vs Excel SUM cell)")
    print(f"Python-computed total : Rs. {verification['python_total']:,.2f}")
    if verification["excel_total"] is not None:
        print(f"Excel SUM() total     : Rs. {verification['excel_total']:,.2f}")
        print(f"Delta                 : Rs. {verification['delta']:,.2f}")
    print(verification["message"])

    print_section("PLAIN-LANGUAGE INSIGHTS")
    for line in insights:
        print(f"• {line}")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
