# What's My Grade, Really

A single-file Streamlit app that calculates your real current grade using
your actual grading weights and the Final Exam Replacement Rule — not a
generic weighted-average calculator.

## How to Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`).

## How to Use It

1. **Sidebar** — enter your real category weights (Assignments, Quizzes,
   Labs, Projects, Midterm, Final Exam). They must sum to 100%.
2. **Score table** — add a row for each score you've received. Pick the
   category from the dropdown and type in the percentage (0–100). You can
   add as many rows as you need per category (e.g. one row per quiz), and
   the app averages them. Leave a category with no rows/blank scores if
   you haven't been graded on it yet (e.g. Final Exam).
3. **Breakdown table** — shows each category's raw average, the value
   actually used for its weight slot (relevant for Midterm, see below),
   its weight, and its weighted contribution. Use this to hand-check the
   math: `Weighted Contribution = Used For Weight Slot × Weight ÷ 100`.
4. **Current grade** — computed only from categories you've actually
   entered scores for (ungraded categories are excluded from both the
   numerator and denominator, so it reflects "where you stand today").
5. **Target calculator** — enter a target overall grade and the app
   solves for the Final Exam score you'd need, checking both the
   "no replacement" and "replacement triggers" scenarios and telling you
   which one is mathematically consistent.

All scores are entered and calculated as **percentages (0–100)**.

## The Final Exam Replacement Rule

> If your **Final Exam %** is higher than your **Midterm %**, the Final
> Exam % replaces the Midterm % *in the Midterm's weight slot only*. The
> Final Exam keeps its own score and its own weight as normal — this is a
> substitution, not a removal of either category.

**Example:** Midterm = 74%, Final Exam = 91%, Midterm weight = 20%, Final
Exam weight = 30%.

- Because 91% > 74%, the replacement triggers.
- The Midterm's 20% weight slot now uses 91% (not 74%).
- The Final Exam's 30% weight slot still uses 91% as well.
- So the Final Exam's 91% effectively counts toward **50%** of your grade
  (20% + 30%), and the Midterm's real 74% score is not used at all.

This logic lives in its own function, `apply_replacement_rule()`, in
`app.py`, with a comment explaining exactly what it does — check it
against your own math if your teacher's actual policy differs even
slightly (e.g. "only if final is X points higher" or "replaces only part
of the weight").

**No drop-lowest rule** is applied to Assignments/Quizzes/Labs — every
score you enter counts toward that category's average. If your teacher
does drop lowest scores, remove the lowest one yourself before entering
the table (or ask for an updated version of this app that automates it).

## Letter Grade Scale Used

| Grade | Range     |
|-------|-----------|
| A+    | 90–100    |
| A     | 85–89     |
| B+    | 80–84     |
| B     | 75–79     |
| C+    | 70–74     |
| C     | 65–69     |
| D     | 50–64     |
| F     | Below 50  |

## Files

- `app.py` — the full app (single file, commented)
- `requirements.txt` — dependencies (`streamlit`, `pandas`, `plotly`)
- `README.md` — this file

## Assumptions Made

Since the weights and the exact wording of the replacement rule weren't
filled in when this app was generated, it ships with:
- Placeholder default weights in the sidebar (Assignments 15%, Quizzes
  10%, Labs 10%, Projects 15%, Midterm 20%, Final Exam 30%) — **change
  these to your real weights**, they're just a starting point.
- Scores treated as percentages (0–100) rather than raw points out of a
  custom maximum, since no per-item max was specified.
- The replacement rule exactly as described in the prompt (full
  substitution when Final % > Midterm %, no partial/point-based version).
- No drop-lowest rule, since none was specified.

If any of these don't match your teacher's actual policy, the relevant
code is isolated and commented so it's easy to adjust:
`apply_replacement_rule()` for the rule, `DEFAULT_WEIGHTS` for the
starting weights.
