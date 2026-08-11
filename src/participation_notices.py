"""
src/participation_notices.py — cross-reference bill status against Mzalendo's
live Bill Tracker, to avoid showing long-closed bills as "open" on the dashboard.

Why this exists:
  scraper.py can find a bill PDF and its clause text, but a bill PDF never states
  its own public-participation open/close dates — those are announced separately
  (a Gazette notice / Parliament press release), and there is no single official
  API for them. What Parliament's own site and Mzalendo Trust's public Twitter
  account DO publish ad hoc are memoranda-submission deadlines for specific bills
  (e.g. "Finance Bill 2026 — submit by 25 May 2026"), but that is unstructured,
  one-off text, not a scrapable feed with a stable schema.

  What IS a real, structured, live-updating, scrapable source is Mzalendo's own
  Bill Tracker CSV export:
      https://mzalendo.com/legislative-trends/bills/?house=na&format=csv
      https://mzalendo.com/legislative-trends/bills/?house=senate&format=csv
  This gives every current bill's title, year, and legislative stage (First
  Reading, Second Reading, Committee of the Whole House, Third Reading,
  Presidential Assent, Withdrawn/Lapsed/Rejected, or "stage not recorded").
  That's enough to answer the question that actually matters for a dashboard —
  "is this bill still alive, or has it already been passed/withdrawn?" — even
  though it does NOT give an exact public-participation deadline.

IMPORTANT — read before wiring this into the dashboard:
  This CSV only covers NATIONAL bills (National Assembly + Senate). It does
  NOT cover county assembly bills. Sheria Yangu's current scraper target
  (nairobi_county in scraper.py) is a COUNTY source, so this module will not
  match any of the 97 bills you've already scraped — there is currently no
  known equivalent structured tracker for Nairobi County Assembly bill status.
  This module is here so that (a) it's ready the moment a national-bill
  source is added to scraper.py, and (b) the gap is documented rather than
  silently assumed away.

  The actual fix for "will old bills show as open on the dashboard" is NOT
  this module — it's a rule in whatever serves the dashboard: only ever
  display bills where status == "open". scraper.py already defaults every
  freshly scraped bill to status == "needs_manual_review", never "open".
  A bill should only flip to "open" (with real opens_at/closes_at filled in)
  after a human — or, once this module has a matching national source to
  read from, an automated cross-check — confirms it.

Run standalone to inspect what Mzalendo currently has on record:
  python src/participation_notices.py --house na
  python src/participation_notices.py --house senate
"""

import argparse
import csv
import io
from dataclasses import dataclass
from datetime import datetime

import requests

MZALENDO_CSV_URL = "https://mzalendo.com/legislative-trends/bills/?house={house}&format=csv"
HEADERS = {"User-Agent": "SheriaYangu-Scraper/0.1 (KamiLimu Democracy & AI hackathon, team T002)"}

# Stages that mean "this bill is no longer awaiting public input" — either it's
# law already, or it's dead. Anything else is treated as potentially still live.
CLOSED_STAGES = {"presidential assent", "withdrawn", "lapsed", "rejected"}

CURRENT_YEAR = datetime.now().year


@dataclass
class TrackedBill:
    title: str
    year: int | None
    stage: str
    is_active: bool  # heuristic only — NOT a confirmed public-participation window
    detail_url: str | None = None  # Mzalendo's own bill detail page — scraper_national.py
    # follows this to find the bill's actual PDF (see that module's docstring)


def fetch_mzalendo_bills(house: str = "na") -> list[TrackedBill]:
    """
    house: "na" (National Assembly) or "senate".
    Raises requests.HTTPError if Mzalendo's export format has changed or the
    request fails — don't silently swallow that, since a schema change here
    would otherwise fail silently and mark everything "closed" by accident.
    """
    url = MZALENDO_CSV_URL.format(house=house)
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()

    reader = csv.DictReader(io.StringIO(resp.text))
    bills = []
    for row in reader:
        # Confirmed real column names (2026-07-23): ID,Bill,Year,Stage,Sponsor,House,Updated,URL
        # Kept the lowercase/"name" fallbacks too in case Mzalendo ever renames columns.
        title = (row.get("Bill") or row.get("title") or row.get("name") or "").strip()
        stage_raw = (row.get("Stage") or row.get("stage") or "").strip()
        detail_url = (row.get("URL") or row.get("url") or "").strip() or None
        year_cell = (row.get("Year") or "").strip()
        year = int(year_cell) if year_cell.isdigit() and len(year_cell) == 4 else None
        if year is None:  # fallback: scan every cell if the Year column itself is missing/renamed
            for cell in row.values():
                if cell and cell.strip().isdigit() and len(cell.strip()) == 4:
                    year = int(cell.strip())
                    break
        stage_lower = stage_raw.lower()
        is_withdrawn_or_done = any(closed in stage_lower for closed in CLOSED_STAGES)
        is_recent = year is None or year >= CURRENT_YEAR - 1
        bills.append(TrackedBill(
            title=title,
            year=year,
            stage=stage_raw or "stage not recorded",
            is_active=(not is_withdrawn_or_done) and is_recent,
            detail_url=detail_url,
        ))
    return bills


def find_match(bill_title: str, tracked: list[TrackedBill]) -> TrackedBill | None:
    """
    Loose title match (case-insensitive substring both ways) — bill titles
    from different sources are rarely byte-identical ("The Finance Bill, 2026"
    vs "Finance Bill 2026"). Good enough for a cross-check, not for anything
    where a false match matters more than a false miss.
    """
    needle = bill_title.lower().strip()
    for t in tracked:
        hay = t.title.lower().strip()
        if needle in hay or hay in needle:
            return t
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--house", choices=["na", "senate"], default="na")
    args = parser.parse_args()

    results = fetch_mzalendo_bills(args.house)
    active = [b for b in results if b.is_active]
    print(f"Fetched {len(results)} bill(s) from Mzalendo ({args.house}); "
          f"{len(active)} look still-active by stage/year heuristic.\n")
    for b in active[:15]:
        print(f"  [{b.year}] {b.title}  — stage: {b.stage}")
    if len(active) > 15:
        print(f"  ... and {len(active) - 15} more")
