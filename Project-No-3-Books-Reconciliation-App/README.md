# Books Reconciliation App

**Project 3 of 4 - "The Books Don't Match"**

## Problem Statement

A group of 20 people each owed Rs. 1,000, for a hand-counted expected
total of **Rs. 20,000**. The digital payment history that came back,
however, is messy: misspelled names, inconsistent capitalization,
abbreviations, blank/emoji memos, inconsistent separators, a duplicate
transaction, an unknown sender, a partial payment, an overpayment, and one
person who never paid at all. This app reconciles the messy payment
history against the known expected total, applies documented
interpretation rules to resolve ambiguous entries, and clearly surfaces
the gap and exactly who needs follow-up.

## AI Tool Used

Built with Claude (Anthropic), via a two-stage prompt process. See
`prompts/initial_prompt.md` and `prompts/improved_prompt.md`.

## Features

- Expected Total (Rs. 20,000) always shown as the reconciliation target
- Automatic name/memo normalization driven entirely by
  `data/interpretation_rules.json` (no hardcoded reconciliation logic)
- Transaction-level and person-level status detection: Matched, Duplicate,
  Unknown Sender, Missing, Partial, Overpaid, Fully Paid
- Searchable/sortable transactions table with status highlighting
- Explicit follow-up list: who needs contacting, and for how much
- Three Plotly charts: Payment Status Pie, Matched vs. Missing Bar, Amount
  Distribution Histogram
- Downloadable CSV summary report

## Tech Stack

- Python 3.12+
- Streamlit (UI)
- Pandas (data handling)
- Plotly (charts)
- pathlib (file paths)

## Folder Structure

```
Books-Reconciliation-App/
├── app.py                     # Streamlit UI
├── requirements.txt
├── README.md
├── report.md
├── prompts/
│   ├── initial_prompt.md
│   └── improved_prompt.md
├── data/
│   ├── expected_people.csv        # ground truth: 20 x Rs. 1,000
│   ├── payment_history.csv        # raw, messy payment export
│   └── interpretation_rules.json  # documented ambiguity rules
├── src/
│   ├── loader.py                  # file loading + basic validation
│   ├── rules.py                   # applies interpretation rules
│   ├── reconciler.py              # matching, status detection, summary
│   └── utils.py                   # formatting, CSV export, validation
└── assets/
    └── README.md               # screenshot/clip instructions
```

## Installation & Run Instructions

```bash
# From inside Books-Reconciliation-App/
pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501` and runs with no modifications
needed - all data is bundled in `data/`.

## Screenshots

> **Before submitting:** run the app locally, take 2-3 screenshots, save
> them into `assets/`, and embed them below.
>
> 1. `assets/dashboard.png` - the Overview page (top metrics + charts)
> 2. `assets/reconciliation_table.png` - the Reconciliation page's
>    transactions table, with status highlighting visible
> 3. `assets/followup_list.png` - the Reports page's follow-up list
>
> Optional: a short screen recording (`assets/demo_clip.mp4` or `.gif`)
> clicking through Overview → Reconciliation → Reports.

```markdown
![Dashboard](assets/dashboard.png)
![Reconciliation Table](assets/reconciliation_table.png)
![Follow-up List](assets/followup_list.png)
```

## Verification Method

Verification was done by comparing the **Expected Total (Rs. 20,000)**
against the **Calculated Total** produced by the reconciliation engine
(shown live on every page of the app), and by confirming that every
missing, duplicate, and unmatched transaction was correctly flagged
against what was already known about the 20 contributors (i.e. manually
tracing each of the 21 payment rows back to its intended person or
Unknown-Sender status and checking it matched the app's output).

With the bundled dummy data, the app correctly reports:
- Expected Total: Rs. 20,000
- Received Total: Rs. 18,700
- Difference: -Rs. 1,300 (short)
- 1 missing person (Sheraz), 1 partial payment (Kashif, Rs. 500 of Rs.
  1,000), 1 overpayment (Waleed, Rs. 1,200), 1 duplicate transaction
  (Bilal), 1 unknown sender (Zubair Khan)

## Future Improvements

- Excel and PDF export options for the summary report
- Fuzzy string matching (e.g. Levenshtein distance) as a fallback when a
  sender name isn't covered by an explicit alias rule
- Multi-batch reconciliation (compare against several expected-total
  periods, not just one)

## Learning Outcomes

- Reconciliation logic should never be entangled with ambiguity
  resolution - separating "what counts as a match" (`reconciler.py`) from
  "how do we interpret messy input" (`rules.py` + JSON) keeps the matching
  engine auditable and the interpretation rules changeable without
  touching code.
- A single, clearly-stated ground-truth number (Rs. 20,000) is what makes
  a reconciliation tool trustworthy - every other number on the page
  should be checked against it, not the other way around.
- Duplicate detection needs a defined tie-break rule (here: first
  chronological transaction per person counts, later ones are flagged) or
  the person-level totals become ambiguous.
