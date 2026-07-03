# How Money Detective's Rules Work

This file explains, in plain language, the three core detection rules
behind Money Detective. None of this uses AI or machine learning — it's
all plain pandas/Python logic you can read directly in
`utils/analysis.py` and `utils/rules.py`.

## 1. Duplicate detection logic

**The rule:** if two or more rows have the exact same `Date`,
`Description`, AND `Amount`, every one of those rows is flagged as a
duplicate.

**Why this rule:** an accidental double charge from a merchant or bank
almost always shows up as an identical row appearing more than once — same
day, same description, same amount. A legitimate second purchase (say, two
separate Foodpanda orders on the same day) will usually differ in amount,
so it won't get flagged.

**In code:** this is `df.duplicated(subset=["Date", "Description",
"Amount"], keep=False)` — `keep=False` means *all* matching rows are kept
as duplicates, not just the 2nd, 3rd, etc. copy.

**In the sample data:** "Foodpanda Order" for Rs. 850 appears three times
on 2026-06-12 — a deliberately built triple charge so the rule has
something concrete to catch.

## 2. Recurring-payment detection logic

**The rule:** group all expense rows by their exact `Description` text.
If a description shows up with charges in **2 or more different calendar
months**, it's treated as recurring.

**Why this rule:** a one-off purchase only ever appears once. A
subscription or monthly bill, by definition, repeats — so looking for the
same description charging across multiple months is a simple, reliable
signal without needing to guess at billing cycles or exact intervals.

**In code:** `detect_recurring()` groups by `Description`, counts
`Month.nunique()` (the `Month` column is a `YYYY-MM` string derived from
`Date`), and keeps any group with at least 2 distinct months. It also
reports an `EstimatedMonthlyCost` (the average absolute amount charged).

**In the sample data:** Netflix, Spotify, Internet Bill, Mobile Package,
and PTCL Bill each appear once in May 2026 and once in June 2026 — exactly
2 months each — so all five are correctly detected as recurring.

## 3. "Forgotten subscription" detection logic

**The rule:** take the list of recurring payments (from rule #2) and check
whether the description matches a keyword from a fixed
`SUBSCRIPTION_KEYWORDS` list (Netflix, Spotify, Prime Video, YouTube
Premium, Disney+, Apple Music, Amazon Prime, "subscription", "membership").
Any match gets flagged as a possibly-forgotten subscription.

**Why this rule:** the sample data has no separate "I logged in / I used
this" signal, so there's no way to truly know whether someone still uses a
service. Instead of guessing, the rule is explicit about its limitation:
it flags *every* recurring charge that looks like a subscription by name,
and leaves the actual "do I still use this?" judgment to the person
reviewing the report. This is intentionally conservative and transparent
rather than trying to be clever about usage.

**In the sample data:** Netflix and Spotify are flagged (their names match
the keyword list). Internet Bill, Mobile Package, and PTCL Bill are *not*
flagged even though they're recurring — they're treated as utility bills,
not subscriptions, since nobody "forgets" they have internet.

## Category-mapping rules

Every expense is assigned to a spending category using a keyword
dictionary (`CATEGORY_KEYWORDS` in `utils/rules.py`). The logic is simple:

1. If the transaction `Amount` is positive, it's categorized as **Income**
   — no keyword matching needed.
2. Otherwise, the description is lower-cased and checked against each
   category's keyword list, **in order**:
   - `Subscriptions` → netflix, spotify, prime video, youtube premium, disney, apple music, amazon prime
   - `Utilities & Bills` → internet bill, mobile package, ptcl, electricity, wifi, gas bill, water bill
   - `Food & Dining` → foodpanda, kfc, mcdonald, restaurant, cafe, food
   - `Transport` → uber, careem, fuel, petrol, diesel, transport
   - `Shopping` → daraz, imtiaz, super market, supermarket, mall, shopping
   - `Transfers & Payments` → jazzcash, easypaisa, transfer, payment sent
   - `Health & Pharmacy` → pharmacy, hospital, clinic, medicine, medical
   - `Cash & ATM` → atm, withdrawal, cash out
3. The **first** category whose keyword is found in the description wins.
   This is why category order matters in `CATEGORY_KEYWORDS` — more
   specific categories should come before more generic ones.
4. If nothing matches, the transaction falls into a catch-all `Other`
   category, so nothing silently disappears from the totals.

Because this is plain keyword matching on the description string, it's
completely transparent: you can always explain *why* a transaction landed
in a given category by pointing at the exact keyword that matched.

## Total verification

`transactions.xlsx` has a bottom row with an actual Excel `=SUM()` formula
over the `Amount` column — this represents a "manually stated total" the
way a real spreadsheet user might leave one. `analyze_transactions.py`
independently recomputes the total in Python (`df["Amount"].sum()`) and
compares it to that Excel-calculated value. If they match (within a tiny
floating-point tolerance), it prints `✅ Total Verified`; if they don't,
it prints `❌ Total Mismatch` along with the exact delta, so any
discrepancy between the spreadsheet and the raw data is immediately
visible.
