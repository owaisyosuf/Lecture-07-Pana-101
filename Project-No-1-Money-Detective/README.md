# 🕵️ Money Detective

A simple, fully offline Streamlit dashboard that analyzes bank transaction
history and detects recurring payments, forgotten subscriptions, duplicate
charges, and spending patterns — **all rule-based, no AI/LLM API calls.**

## Overview

Money Detective reads a CSV (and optionally an Excel file) of bank
transactions and runs a set of deterministic, hand-readable rules over the
data with pandas:

- finds **duplicate charges** (same Date + Description + Amount)
- finds **recurring payments** (same description billed in 2+ different months)
- flags **possibly forgotten subscriptions** (recurring charges matching a
  subscription keyword list, e.g. Netflix, Spotify)
- buckets every expense into a **spending category** using keyword rules
- computes **summary statistics** (total, count, max, min, average)
- builds a **monthly income vs. expense summary**
- **verifies its own total** against the `SUM()` formula stored in the
  bottom row of `transactions.xlsx`, printing `✅ Total Verified` or
  `❌ Total Mismatch` with the delta

Everything runs locally. No API keys, no `.env` file, no network calls.

## Features

- 📊 Streamlit dashboard with sidebar navigation, file upload, and an
  **Analyze** button
- Summary cards: total spend, recurring payment count, duplicate count,
  flagged-subscription count
- Plotly pie chart (spend by category) and bar chart (monthly income vs.
  expense)
- Plain-language insight panel (e.g. *"You have 3 duplicate charges
  totaling Rs. 2,550 — check if you were billed twice"*)
- One-click downloadable `.txt` analysis report
- Dark-mode friendly styling via Streamlit's native theming
  (`.streamlit/config.toml`) — no inline `<style>` hacks
- Standalone command-line analyzer (`analyze_transactions.py`) for
  reading the report without opening the UI

## Setup

```bash
# 1. Clone / copy this folder, then move into it
cd Money-Detective

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

## How to run

**Dashboard (Streamlit):**

```bash
streamlit run app.py
```

This opens the app in your browser (usually `http://localhost:8501`). Tick
**"Use built-in sample data"** in the sidebar and click **Analyze**, or
uncheck it to upload your own `Date | Description | Amount` CSV (and
optional `.xlsx` for total verification).

**Command-line analyzer:**

```bash
python analyze_transactions.py
```

Prints summary statistics, duplicate transactions, recurring payments,
forgotten subscriptions, category spend, a monthly summary, and the
total-verification result straight to the terminal.

## Expected output

Running either entry point against the bundled sample data (`transactions.csv`
/ `transactions.xlsx`) should report:

- 20 transactions analyzed
- 3 duplicate rows (one accidental triple Foodpanda charge)
- 5 recurring payments (Netflix, Spotify, Internet Bill, Mobile Package,
  PTCL Bill)
- 2 of those flagged as possibly-forgotten subscriptions (Netflix, Spotify)
- `✅ Total Verified` — the Python-recomputed total (Rs. 37,700) matches the
  Excel `SUM()` cell exactly

## Folder structure

```
Money-Detective/
├── app.py                    # Streamlit dashboard
├── analyze_transactions.py   # Command-line analyzer
├── transactions.xlsx         # Sample data (20 rows + SUM() formula row)
├── transactions.csv          # Sample data (20 rows)
├── requirements.txt          # Pinned dependencies
├── README.md                 # This file
├── prompt.md                 # Plain-language explanation of the detection rules
├── .streamlit/
│   └── config.toml           # Dark-mode theme (no inline CSS hacks)
├── utils/
│   ├── __init__.py
│   ├── analysis.py           # Core rule-based analysis engine
│   └── rules.py               # Keyword lists (categories, subscriptions)
├── assets/                   # (reserved for icons/images)
└── screenshots/              # (reserved for dashboard screenshots)
```

## Tech stack

- **Python 3.10+**
- **Streamlit** — dashboard UI
- **pandas** — data loading, cleaning, and rule-based analysis
- **Plotly (Express)** — interactive pie/bar charts
- **openpyxl** — reading the Excel `SUM()` formula cell
- Built with **Claude Sonnet 4.6** as the coding assistant

## Future improvements

- Support multiple currencies / locales instead of hardcoded `Rs.`
- Let users edit the category-keyword rules from within the UI
- Add a date-range filter and a search box on the Transactions page
- Export the report as PDF in addition to `.txt`
- Add unit tests for `utils/analysis.py` (pytest)
- Persist uploaded transaction history between sessions (currently
  in-memory only, by design — no database, no network calls)
