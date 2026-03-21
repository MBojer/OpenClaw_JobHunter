"""
scripts/db/check_budget.py
Check remaining Together.ai budget.
Exits with code 1 if budget is below warning threshold.
Exits with code 2 if budget is exhausted.
Used by cv-writer skill before every Together.ai call.
"""
import os
import sys
import json
from scripts.db.client import fetchone
from dotenv import load_dotenv

load_dotenv()

BUDGET_USD   = float(os.environ.get("TOGETHER_BUDGET_USD", 10.0))
WARN_AT_USD  = float(os.environ.get("TOGETHER_WARN_AT_USD", 1.0))
REFUSE_AT_USD = 0.10


def check() -> dict:
    row = fetchone("""
        SELECT COALESCE(SUM(estimated_usd), 0) AS spent
        FROM spend_log
        WHERE provider = 'together'
    """)
    spent     = float(row["spent"]) if row else 0.0
    remaining = BUDGET_USD - spent

    return {
        "budget_usd":    BUDGET_USD,
        "spent_usd":     round(spent, 4),
        "remaining_usd": round(remaining, 4),
        "warn":          remaining < WARN_AT_USD,
        "refuse":        remaining < REFUSE_AT_USD,
    }


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, indent=2))

    if result["refuse"]:
        print(f"\n⛔ Budget nearly exhausted (${result['remaining_usd']:.2f} left). "
              f"Top up Together.ai before generating more applications.")
        sys.exit(2)

    if result["warn"]:
        print(f"\n⚠️  Budget low: ${result['remaining_usd']:.2f} remaining. "
              f"Consider topping up Together.ai.")
        sys.exit(1)

    sys.exit(0)
