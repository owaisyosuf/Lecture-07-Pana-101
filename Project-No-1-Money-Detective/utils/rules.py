"""
rules.py
--------
Plain keyword "rule books" used by the analysis engine.

Nothing in this file calls an AI/LLM. It is just Python dictionaries and
lists that the rest of the app uses to classify transactions. Keeping the
rules in one file makes them easy to read, tweak, and extend without
touching the analysis logic itself.

See prompt.md for a plain-language explanation of how these rules are used.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Category keyword map
# ---------------------------------------------------------------------------
# Each category maps to a list of lowercase keywords. A transaction is
# assigned to the FIRST category whose keyword appears anywhere inside the
# (lowercased) description. Order matters -- more specific categories are
# checked before generic ones.
#
# "Income" is handled separately (any positive amount is income), so it is
# not part of this keyword map.
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Subscriptions": [
        "netflix",
        "spotify",
        "prime video",
        "youtube premium",
        "disney",
        "apple music",
        "amazon prime",
    ],
    "Utilities & Bills": [
        "internet bill",
        "mobile package",
        "ptcl",
        "electricity",
        "wifi",
        "gas bill",
        "water bill",
    ],
    "Food & Dining": [
        "foodpanda",
        "kfc",
        "mcdonald",
        "restaurant",
        "cafe",
        "food",
    ],
    "Transport": [
        "uber",
        "careem",
        "fuel",
        "petrol",
        "diesel",
        "transport",
    ],
    "Shopping": [
        "daraz",
        "imtiaz",
        "super market",
        "supermarket",
        "mall",
        "shopping",
    ],
    "Transfers & Payments": [
        "jazzcash",
        "easypaisa",
        "transfer",
        "payment sent",
    ],
    "Health & Pharmacy": [
        "pharmacy",
        "hospital",
        "clinic",
        "medicine",
        "medical",
    ],
    "Cash & ATM": [
        "atm",
        "withdrawal",
        "cash out",
    ],
}

# Fallback category when nothing in CATEGORY_KEYWORDS matches.
DEFAULT_CATEGORY = "Other"

# Category used for any transaction with a positive amount.
INCOME_CATEGORY = "Income"

# ---------------------------------------------------------------------------
# Subscription keywords
# ---------------------------------------------------------------------------
# Used to flag "forgotten subscriptions": recurring charges whose
# description matches one of these keywords. The transactions.csv sample
# has no separate usage/login log, so -- per the project brief -- a
# recurring charge that matches this keyword list is treated as having
# "no matching usage signal" and is flagged for the user to double check.
SUBSCRIPTION_KEYWORDS: list[str] = [
    "netflix",
    "spotify",
    "prime video",
    "youtube premium",
    "disney",
    "apple music",
    "amazon prime",
    "subscription",
    "membership",
]

# Minimum number of distinct calendar months a description must appear in
# (with a charge) to be considered "recurring".
MIN_MONTHS_FOR_RECURRING = 2

# Tolerance (in currency units) allowed when comparing the Python-computed
# total against the Excel SUM() cell before flagging a mismatch.
TOTAL_VERIFICATION_TOLERANCE = 0.01
