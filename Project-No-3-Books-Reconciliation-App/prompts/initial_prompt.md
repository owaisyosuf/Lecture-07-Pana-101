# Initial Prompt

> Build a Streamlit app that reconciles a hand-counted total (20 people x
> Rs. 1,000 = Rs. 20,000) against a messy digital payment history. The
> payment data has spelling mistakes, inconsistent capitalization, blank
> memos, and other messiness that needs to be interpreted before matching.
> Show whether the total matches, and if not, who still needs to pay or
> needs follow-up.

This initial prompt captured the goal but was underspecified on:
- What "messy" concretely meant (no examples of the specific anomaly types)
- How ambiguous entries should be resolved (no documented rules, would
  have been hardcoded into matching logic)
- What the exact folder/module structure and deliverables should be
- What counted as "done" for verification

See `improved_prompt.md` for the refined version actually used to build
this project.
