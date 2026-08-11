"""
src/test_summarize.py — quick manual test of /api/summarize against a REAL
scraped clause, not the old demo bill.

Why this exists: hand-copying a real clause's raw_text (often 500-2000
characters of legal text, with quotes/newlines in it) into a curl -d string
is exactly the kind of thing that breaks on shell-quoting, not on the API
itself. This script reads the clause straight out of the JSON file and posts
it directly, so what you're actually testing is DeepSeek's summarization
quality, not your terminal's quoting rules.

Usage:
  python src/main.py                                  # in one terminal, leave running
  python src/test_summarize.py                        # in another: tests the first bill, first clause
  python src/test_summarize.py --bill-id <id>          # a specific bill (id from /api/bills)
  python src/test_summarize.py --bill-id <id> --clause 2   # a specific clause index (0-based)
  python src/test_summarize.py --affected-group "boda boda riders"
"""

import argparse
import json
import sys
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
SCRAPED_BILLS_DIR = BASE_DIR / "data" / "scraped_bills"
API_URL = "http://localhost:5000/api/summarize"


def load_bill(bill_id: str | None) -> dict:
    files = sorted(SCRAPED_BILLS_DIR.glob("*.json"))
    if not files:
        print(f"No scraped bills found in {SCRAPED_BILLS_DIR}. Run scraper.py or "
              f"scraper_national.py first.")
        sys.exit(1)
    if bill_id:
        match = next((f for f in files if f.stem == bill_id), None)
        if not match:
            print(f"No bill with id '{bill_id}'. Available ids: {[f.stem for f in files]}")
            sys.exit(1)
        return json.loads(match.read_text(encoding="utf-8"))
    return json.loads(files[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bill-id", help="id from /api/bills; defaults to the first scraped bill")
    parser.add_argument("--clause", type=int, default=0, help="0-based clause index; defaults to the first clause")
    parser.add_argument("--affected-group", default="the public", help="who the clause affects, for the prompt")
    args = parser.parse_args()

    bill = load_bill(args.bill_id)
    clauses = bill.get("clauses", [])
    if not clauses:
        print(f"'{bill.get('title')}' has no clauses (probably a 0-clause scrape). Try --bill-id with a different bill.")
        sys.exit(1)
    if args.clause >= len(clauses):
        print(f"'{bill.get('title')}' only has {len(clauses)} clause(s) — --clause {args.clause} is out of range.")
        sys.exit(1)

    clause = clauses[args.clause]
    print(f"Bill: {bill.get('title')}")
    print(f"Clause {clause.get('clause_number')} ({len(clause.get('raw_text', ''))} chars):")
    print(clause.get("raw_text", "")[:300] + ("..." if len(clause.get("raw_text", "")) > 300 else ""))
    print("\n--- Calling /api/summarize (make sure `python src/main.py` is running) ---\n")

    resp = requests.post(API_URL, json={
        "clause_id": clause.get("clause_id"),
        "raw_text": clause.get("raw_text"),
        "affected_group": args.affected_group,
    }, timeout=30)

    print(f"HTTP {resp.status_code}")
    print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
