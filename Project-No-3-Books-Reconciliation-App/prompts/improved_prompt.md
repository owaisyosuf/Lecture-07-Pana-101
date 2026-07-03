# Improved Prompt

The refined prompt fixed the gaps in the initial version by adding:

1. **A fixed ground truth stated up front** - Expected Total = Rs. 20,000
   (20 people x Rs. 1,000), which every output must be checked against,
   with the gap and short/over amount always visible.
2. **Explicit anomaly types to include in the dummy data** - spelling
   variants, abbreviations, blank/emoji memos, random capitalization,
   different separators, one duplicate, one unknown sender, one partial
   payment, one overpayment, one fully missing person.
3. **Interpretation rules pulled out into a separate JSON file**
   (`data/interpretation_rules.json`) instead of being hardcoded into the
   matching logic, so the "why" behind every ambiguous-entry decision is
   documented and auditable.
4. **A concrete, scoped folder structure** (`app.py`, `src/loader.py`,
   `src/rules.py`, `src/reconciler.py`, `src/utils.py`, `data/`, `prompts/`,
   `assets/`) sized appropriately for a ~45-minute assignment - no extra
   modules, no extra export formats, no extra charts beyond three.
5. **An explicit verification method** - compare Expected Total against
   the Calculated Total from the engine, and confirm every missing,
   duplicate, and unmatched transaction was correctly flagged against what
   was already known about the 20 contributors.

The full improved prompt used to generate this project is the Claude Code
build prompt this repository was built from (kept alongside this repo /
provided to the assistant as the task brief).
