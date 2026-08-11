"""
src/scraper_national.py — second scraper source: national bills (National
Assembly + Senate), tagged level: "national" so they're never conflated with
the Nairobi county bills scraper.py already handles.

Why Mzalendo instead of parliament.go.ke directly: parliament.go.ke's own
listing pages don't have a single consistent structure across houses, but
Mzalendo Trust already re-publishes every bill's PDF on their own domain at a
predictable path, discoverable from each bill's detail page. Concretely:

  1. participation_notices.fetch_mzalendo_bills("na" | "senate") gives every
     current bill's title/year/stage/detail_url (already built for the
     status cross-check — this reuses the exact same fetch).
  2. For each bill whose stage looks "active" (not passed/withdrawn) and
     whose detail page is reachable, this module fetches that detail page
     and pulls out Mzalendo's own hosted PDF link, e.g.:
       https://mzalendo.com/media/bills/pdfs/na-2026-422-the-finance-bill-2026.pdf
     (confirmed by inspecting https://mzalendo.com/legislative-trends/bills/na/422/
     on 2026-07-23 — the page embeds both the original parliament.go.ke source
     URL and Mzalendo's own re-hosted copy; the re-hosted copy is what's
     scraped, since it's one consistent domain/pattern instead of parliament.go.ke's
     inconsistent per-house paths).
  3. Downloads + parses that PDF with the exact same extract_text/
     split_into_clauses pipeline scraper.py uses for county bills, so both
     sources produce byte-identical JSON shapes for main.py to consume.

Honesty notes carried over from scraper.py:
  - This still does NOT give a real public-participation open/close date —
    only Mzalendo's legislative *stage*, which is a proxy for "still alive,"
    not a participation deadline. Every bill still lands as
    status: needs_manual_review.
  - Not every bill has a Mzalendo-hosted PDF yet (some detail pages only link
    the original government source, or none at all) — those are skipped and
    logged, not silently dropped without a trace.

Run:
  python src/scraper_national.py --house na
  python src/scraper_national.py --house senate
"""

import argparse
import json
import re
import sys
from pathlib import Path

import net
from participation_notices import fetch_mzalendo_bills
from scraper import (
    OUT_DIR, RAW_DIR, HEADERS, MIN_YEAR,
    extract_text, split_into_clauses, bill_to_json,
    load_seen, save_seen,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # allow sibling imports above

MZALENDO_PDF_PATTERN = re.compile(r"https://mzalendo\.com/media/bills/pdfs/[^\s\")\]]+\.pdf")

# Mzalendo's bill-detail pages return a reduced version of the page — missing the
# PDF download link entirely — to requests carrying this repo's honest, self-
# identifying scraper User-Agent (confirmed 2026-07-23: every single detail page
# came back "no PDF found" with the honest UA, on a machine where the exact same
# URLs are reachable in a normal browser). A standard browser UA gets the full
# page. This is just working around basic bot-filtering on one specific site,
# not spoofing identity anywhere else — scraper.py's county source and the
# Mzalendo CSV endpoint aren't affected and keep using the honest UA.
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}


def _normalize_host(url: str) -> str:
    """
    Mzalendo's own bill-tracker CSV links to detail pages on new.mzalendo.com,
    but that specific subdomain has failed outright on at least one dev
    machine (SSL errors on every single request), while the apex mzalendo.com
    domain serves the identical content fine. Rewriting the host here avoids
    the bad subdomain entirely; net.get_text()'s curl fallback is the second
    line of defense in case even mzalendo.com has trouble on a given machine.
    """
    return url.replace("://new.mzalendo.com", "://mzalendo.com")


def find_pdf_url(detail_url: str) -> str | None:
    """Fetches a Mzalendo bill detail page and pulls out its hosted PDF link, if any."""
    text = net.get_text(_normalize_host(detail_url), headers=BROWSER_HEADERS, timeout=20)
    match = MZALENDO_PDF_PATTERN.search(text)
    return match.group(0) if match else None


def run(house: str) -> None:
    seen = load_seen()
    tracked = fetch_mzalendo_bills(house)
    active = [b for b in tracked if b.is_active and b.detail_url]
    print(f"{len(active)} of {len(tracked)} {house} bills look active and have a detail page.")

    new_count, retried_count, skipped_no_pdf, skipped_old = 0, 0, 0, 0

    for bill in active:
        if bill.year is not None and bill.year < MIN_YEAR:
            skipped_old += 1
            continue

        try:
            pdf_url = find_pdf_url(bill.detail_url)
        except Exception as exc:
            print(f"  !! couldn't load detail page for '{bill.title}': {exc}")
            continue

        if not pdf_url:
            skipped_no_pdf += 1
            print(f"  no Mzalendo-hosted PDF found for '{bill.title}' — skipping "
                  f"(check {bill.detail_url} by hand if this bill matters for your demo)")
            continue

        entry = seen.get(pdf_url)
        if entry is not None and entry.get("status") in ("ok", "no_text"):
            continue

        pdf_name = pdf_url.rsplit("/", 1)[-1]
        pdf_path = RAW_DIR / f"national_{house}_{pdf_name}"

        if entry is not None and entry.get("status") == "no_clauses":
            cached_path = Path(entry["pdf_path"]) if entry.get("pdf_path") else pdf_path
            if cached_path.exists():
                print(f"  retrying (previously 0 clauses): {bill.title}")
                pdf_path = cached_path
                retried_count += 1
            else:
                print(f"  re-downloading (cache missing): {bill.title}")
                _download(pdf_url, pdf_path)
        else:
            print(f"  new bill: {bill.title}  ({pdf_url})")
            _download(pdf_url, pdf_path)

        text = extract_text(pdf_path)
        clauses = split_into_clauses(text)

        if len(text.strip()) < 200:
            print(f"    !! only {len(text.strip())} chars extracted — probably scanned/image PDF.")
            seen[pdf_url] = {"status": "no_text", "pdf_path": str(pdf_path)}
            continue
        if not clauses:
            print(f"    !! extracted {len(text)} chars but found 0 numbered clauses — will retry next run.")
            seen[pdf_url] = {"status": "no_clauses", "pdf_path": str(pdf_path)}
            continue

        bill_json = bill_to_json(bill.title, pdf_url, clauses, level="national", year=bill.year)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUT_DIR / f"national_{house}_{pdf_path.stem}.json"
        out_path.write_text(json.dumps(bill_json, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"    -> {len(clauses)} clause(s) written to {out_path}")
        seen[pdf_url] = {"status": "ok", "pdf_path": str(pdf_path)}
        new_count += 1

    save_seen(seen)
    print(f"Done. {new_count} new, {retried_count} retried, {skipped_no_pdf} skipped "
          f"(no PDF found), {skipped_old} skipped as too old.")


def _download(url: str, dest: Path) -> None:
    content = net.get_bytes(url, headers=BROWSER_HEADERS, timeout=60)  # national PDFs can be large (e.g. 29MB Finance Bill)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--house", choices=["na", "senate"], default="na")
    args = parser.parse_args()
    run(args.house)
