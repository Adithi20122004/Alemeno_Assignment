CATEGORIES = [
    "Food",
    "Shopping",
    "Travel",
    "Transport",
    "Utilities",
    "Cash Withdrawal",
    "Entertainment",
    "Other",
]

CATEGORY_PROMPT = """You are a strict financial-transaction categorizer.
Given a list of transactions, assign each one exactly ONE category from:
{categories}

Return ONLY valid JSON. No prose. No markdown fences.
Schema:
{{
  "results": [
    {{"txn_id": "<txn_id>", "category": "<one of the categories>"}}
  ]
}}

Transactions:
{items}
"""

SUMMARY_PROMPT = """You are a financial insights analyst.
Given the aggregated statistics below, produce a JSON response ONLY (no prose, no fences).

Schema:
{{
  "total_spend_inr": <number>,
  "total_spend_usd": <number>,
  "top_merchants": [{{"merchant": "<name>", "total_amount": <number>}}, ...],
  "anomaly_count": <int>,
  "narrative": "<2-3 sentence plain-English summary of spending behaviour>",
  "risk_level": "<LOW|MEDIUM|HIGH>"
}}

Risk rules:
- LOW: anomaly_count == 0
- MEDIUM: 1 <= anomaly_count <= 3
- HIGH: anomaly_count > 3 OR total_spend_usd > 20000

Aggregated statistics:
{stats}
"""
