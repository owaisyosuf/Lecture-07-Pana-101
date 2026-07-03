# Project Report - Books Reconciliation App

## Project Title

Books Reconciliation App - "The Books Don't Match" (Project 3 of 4)

## Problem Solved

Twenty people each owed Rs. 1,000, hand-counted to a known total of Rs.
20,000. The digital payment history collected afterward was messy and
inconsistent (name misspellings, abbreviations, casing, blank/emoji
memos, separator differences) and included a duplicate transaction, an
unidentifiable sender, a partial payment, an overpayment, and one person
who never paid. This project builds a reconciliation engine and Streamlit
dashboard that resolves the messiness using documented rules, then
clearly shows the expected-vs-received gap and exactly who needs
follow-up.

## AI Tool Used

Claude (Anthropic), used to design the reconciliation architecture,
generate the dummy dataset with all required anomaly types, write the
interpretation rules, and build the Streamlit UI.

## Prompts

- Initial prompt: `prompts/initial_prompt.md`
- Improved prompt (used to build this version): `prompts/improved_prompt.md`

The key improvement between versions was moving from "clean the messy
data somehow" to "document every ambiguous-entry decision in a separate
JSON rules file, applied automatically" - this keeps the matching logic
in `reconciler.py` free of any hardcoded name-fixing, so the rules can be
audited or changed without touching the engine.

## Verification Method

Verification was done by comparing the Expected Total (Rs. 20,000, the
hand-counted ground truth) against the Calculated Total produced by the
reconciliation engine, and by manually tracing each of the 21 transactions
in `data/payment_history.csv` back to its intended person (or Unknown
Sender) to confirm the app's flags were correct:

| Check | Expected | App Output | Match? |
|---|---|---|---|
| Expected Total | Rs. 20,000 | Rs. 20,000 | ✅ |
| Received Total | Rs. 18,700 (hand-traced) | Rs. 18,700 | ✅ |
| Difference | -Rs. 1,300 | -Rs. 1,300 | ✅ |
| Missing person | Sheraz | Sheraz flagged Missing | ✅ |
| Partial payment | Kashif, Rs. 500 of Rs. 1,000 | Kashif flagged Partial, Rs. 500 outstanding | ✅ |
| Overpayment | Waleed, Rs. 1,200 | Waleed flagged Overpaid, +Rs. 200 | ✅ |
| Duplicate | Bilal (2 transactions) | 1 transaction flagged Duplicate | ✅ |
| Unknown sender | Zubair Khan | Flagged Unknown Sender | ✅ |
| Name variants resolved | Aly→Ali, M Ahmed→Ahmed, HamZa/HAMZA→Hamza, USMAN→Usman, etc. | All resolved to canonical names via `interpretation_rules.json` | ✅ |

All 20 expected contributors and all 21 payment transactions were
accounted for with no unexplained gaps.

## Problems Faced and Solutions

- **Problem:** Deciding how a "duplicate" payment should affect a
  person's paid total - should it double-count?
  **Solution:** Defined a clear rule in `reconciler.py`: only the first
  chronological transaction per resolved sender counts toward their
  ledger total; later transactions for the same person are flagged
  Duplicate and excluded from the sum, so duplicates don't silently
  create false overpayments.

- **Problem:** Keeping interpretation rules genuinely separate from
  matching logic, rather than sneaking name-fixes into `reconciler.py`
  "just this once."
  **Solution:** All alias resolution lives in `rules.py`, driven purely by
  `data/interpretation_rules.json`. `reconciler.py` only ever sees the
  already-normalized `Normalized Sender` column and has no knowledge of
  specific names.

- **Problem:** Blank memos and emoji in memos breaking simple string
  display/sorting in the UI.
  **Solution:** `normalize_memo()` in `rules.py` converts blank memos to a
  readable placeholder and applies documented cosmetic replacements from
  `memo_aliases`, without touching the underlying matching logic (memo
  normalization is display-only and never affects matching).

## Final Output and Lessons Learned

The final app runs with `streamlit run app.py` with no modifications,
loads the bundled dummy data, and correctly reconciles it against Rs.
20,000: Received Total Rs. 18,700, a Rs. 1,300 shortfall, with 1 missing
person, 1 partial payment, 1 overpayment, 1 duplicate transaction, and 1
unknown sender all correctly identified and surfaced in the follow-up
list.

The main lesson: a reconciliation tool is only as trustworthy as its
separation between "ground truth," "raw messy input," and "the rules used
to bridge the two." Keeping those three as distinct, inspectable pieces
(`expected_people.csv`, `payment_history.csv`,
`interpretation_rules.json`) made it straightforward to verify every
number the app produced by hand.
