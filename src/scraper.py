"""
src/scraper.py — Sheria Yangu bill scraper.

What this does:
  1. Fetches a bills-listing page (Nairobi City County Assembly to start) and finds
     links to bill PDFs.
  2. Downloads any PDF it hasn't seen before (tracked in data/seen_urls.json).
  3. Extracts the text with pdfplumber and splits it into numbered clauses with a
     regex heuristic.
  4. Writes one JSON file per bill into data/scraped_bills/, in a shape close to
     data/sample_bill.json so main.py's /api/summarize loop can consume it with
     minimal changes.

What this does NOT do yet (be honest about this in the pitch/demo):
  - It does not reliably know a bill's public-participation open/close dates —
    those are usually announced separately (a notice or gazette entry), not
    printed inside the bill PDF itself. status/opens_at/closes_at below are
    placeholders you fill in by hand until a second scrape target for notices
    is built.
  - Clause splitting is a heuristic (numbered "1. ", "2. " sections). Always
    spot-check a newly scraped bill's clauses against the source PDF before
    trusting it for a real demo — legal documents are not consistently
    formatted, and this WILL occasionally mis-split or merge clauses.

Run:
  python src/scraper.py            # hits the real listing page over the network
  python src/scraper.py --test     # offline: parses data/sample_bill.pdf if present
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import pdfplumber
import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "data" / "scraped_bills"
RAW_DIR = BASE_DIR / "data" / "raw_pdfs"
SEEN_PATH = BASE_DIR / "data" / "seen_urls.json"

# Add Kenya Law / parliament.go.ke here once you confirm their listing page structure —
# it differs from the county assembly site, so find_bill_pdf_links may need a second
# variant rather than reusing this one as-is.
SOURCES = {
    "nairobi_county": "https://nairobiassembly.go.ke/bills/",
}

HEADERS = {"User-Agent": "SheriaYangu-Scraper/0.1 (KamiLimu Democracy & AI hackathon, team T002)"}

CLAUSE_PATTERN = re.compile(r"\n\s*(\d{1,3})\.\s+", re.MULTILINE)

# --- recency filter -----------------------------------------------------
# This is a heuristic band-aid, not real status detection. It stops obviously
# old bills (2018-2021 etc.) from ever reaching the dashboard, but it does NOT
# tell you whether a 2025/2026 bill's participation window is actually still
# open — that requires cross-referencing a notices source (see
# src/participation_notices.py). MIN_YEAR is computed from today's date so you
# don't have to remember to bump it: it always keeps "this year and last year."
YEAR_PATTERN = re.compile(r"(20[1-3]\d)")
MIN_YEAR = datetime.now().year - 1

# --- seen-URL tracking ---------------------------------------------------
# seen_urls.json is a dict: { url: {"status": "ok"|"no_clauses"|"no_text", "pdf_path": str} }
#   - "ok"         -> clauses were extracted successfully. Never reprocessed.
#   - "no_clauses" -> text came back but no numbered clauses matched. RETRIED
#                     every run (against the already-downloaded PDF, no
#                     re-download) so a CLAUSE_PATTERN/parser improvement gets
#                     a chance to fix it without waiting on a fresh scrape.
#   - "no_text"    -> pdfplumber got under 200 chars, almost always a
#                     scanned/image PDF. Retrying text extraction on the same
#                     file will never help without OCR, so this is skipped on
#                     future runs — but it's tracked separately from "ok" so
#                     you can see how many bills are silently unreadable.
# Old-format seen_urls.json (a flat list of URL strings) is auto-upgraded to
# "ok" entries the first time this runs against it.


def load_seen() -> dict:
    if not SEEN_PATH.exists():
        return {}
    raw = json.loads(SEEN_PATH.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        # Old flat-list format only recorded "we touched this URL", never whether
        # extraction actually succeeded — so it must NOT be upgraded to "ok"
        # (that would permanently hide bills that silently got 0 clauses under
        # the old buggy run). Mark as "legacy_unknown" instead: run_live() only
        # skips "ok"/"no_text", so this status forces every one of these URLs to
        # be fully re-downloaded and re-parsed exactly once, after which it gets
        # a real, trustworthy status.
        return {url: {"status": "legacy_unknown", "pdf_path": None} for url in raw}
    return raw


def save_seen(seen: dict) -> None:
    SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEEN_PATH.write_text(json.dumps(seen, indent=2, sort_keys=True), encoding="utf-8")


def extract_year(url: str, title: str) -> int | None:
    """
    Best-effort year detection. Checks the URL path first (Nairobi Assembly's
    uploads are organised in /wp-content/uploads/YYYY/MM/ folders, which is a
    reliable signal), then falls back to the link title text. Returns None if
    no plausible year is found — callers should treat "unknown year" as
    "keep it but flag for manual review", not as "discard it".
    """
    for source in (url, title):
        matches = YEAR_PATTERN.findall(source)
        if matches:
            return max(int(y) for y in matches)
    return None


def find_bill_pdf_links(listing_url: str) -> list:
    """Scrape a bills-listing page for links to PDF documents."""
    resp = requests.get(listing_url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    links = []
    seen_urls_this_page = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            full_url = urljoin(listing_url, href)
            if full_url in seen_urls_this_page:
                continue
            seen_urls_this_page.add(full_url)
            links.append({
                "title": a.get_text(strip=True) or href.rsplit("/", 1)[-1],
                "url": full_url,
            })
    return links


def download_pdf(url: str, dest: Path) -> Path:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return dest


def extract_text(pdf_path: Path) -> str:
    """
    Uses layout=True so pdfplumber preserves left-to-right, top-to-bottom
    reading order as closely as possible. Kenyan Acts/Bills print a column
    of marginal notes ("Short title.", "Amendment of section 34.") next to
    the main clause text — without layout=True, pdfplumber can interleave
    that column into the body text in the wrong order, which is what caused
    the spurious "Clause 233" jump in early testing. layout=True doesn't
    eliminate the problem (a genuinely scanned/image PDF still returns
    nothing at all — see the "no extractable text" warning below), but it
    measurably reduces column-jumbling on text-based PDFs.
    """
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text(layout=True) or page.extract_text() or ""
            text_parts.append(page_text)
    return "\n".join(text_parts)


def split_into_clauses(full_text: str) -> list:
    """
    Splits on numbered top-level sections ("1. ", "2. ", ...). This is a
    heuristic, not a full legal-document parser: verify against the source
    PDF before trusting it, especially for schedules/annexes which number
    differently from the main body.

    Guards against the marginal-notes-column problem (see extract_text):
    a matched number is only accepted if it continues roughly sequentially
    from the last accepted clause (same number, +1, or a modest jump for
    genuinely skipped/repealed sections). A number that suddenly jumps by
    more than 20 — like "233" appearing right after "2" — is almost always
    a cross-reference or marginal note caught by the regex, not a real
    233rd clause, so it's dropped rather than silently included.
    """
    matches = list(CLAUSE_PATTERN.finditer(full_text))
    clauses = []
    last_num = 0
    for i, m in enumerate(matches):
        num = int(m.group(1))
        if num < last_num or num - last_num > 20:
            continue  # likely a marginal note / cross-reference, not a real next clause
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        clause_text = full_text[start:end].strip()
        if len(clause_text) < 20:  # filters out table-of-contents / stray numbers
            continue
        clauses.append({"clause_number": m.group(1), "raw_text": clause_text[:2000]})
        last_num = num
    return clauses


def bill_to_json(title: str, source_url: str, clauses: list, level: str = "county",
                  year: int | None = None) -> dict:
    return {
        "title": title,
        "source_url": source_url,
        "level": level,
        "year": year,  # None means "couldn't detect a year — check by hand"
        "status": "needs_manual_review",  # confirm the real participation window by hand
        "opens_at": None,
        "closes_at": None,
        "clauses": [
            {
                "clause_id": f"c{i + 1}",
                "clause_number": c["clause_number"],
                "title": None,  # fill in by hand, or generate with a short follow-up LLM call
                "raw_text": c["raw_text"],
            }
            for i, c in enumerate(clauses)
        ],
    }


def run_live() -> None:
    seen = load_seen()
    new_count = 0
    retried_count = 0
    skipped_old_count = 0
    for source_name, listing_url in SOURCES.items():
        print(f"Checking {source_name}: {listing_url}")
        links = find_bill_pdf_links(listing_url)
        print(f"  found {len(links)} PDF link(s) on the page")
        for link in links:
            url = link["url"]
            entry = seen.get(url)

            if entry is not None and entry.get("status") in ("ok", "no_text"):
                continue  # done, or unrecoverable without OCR — nothing to gain by retrying

            year = extract_year(url, link["title"])
            if year is not None and year < MIN_YEAR:
                skipped_old_count += 1
                continue  # e.g. a 2019 bill — almost certainly long closed, don't surface it

            pdf_name = url.rsplit("/", 1)[-1]
            pdf_path = RAW_DIR / f"{source_name}_{pdf_name}"

            if entry is not None and entry.get("status") == "no_clauses":
                # Retry parsing against the PDF we already downloaded — no re-fetch needed,
                # so an improved CLAUSE_PATTERN gets a second chance without hitting the network.
                cached_path = Path(entry["pdf_path"]) if entry.get("pdf_path") else pdf_path
                if cached_path.exists():
                    print(f"  retrying (previously 0 clauses): {link['title']}")
                    pdf_path = cached_path
                    retried_count += 1
                else:
                    print(f"  re-downloading (cache missing): {link['title']}  ({url})")
                    download_pdf(url, pdf_path)
            else:
                print(f"  new bill: {link['title']}  ({url})")
                download_pdf(url, pdf_path)

            text = extract_text(pdf_path)
            clauses = split_into_clauses(text)

            if len(text.strip()) < 200:
                print(f"    !! only {len(text.strip())} chars extracted — this PDF is probably "
                      f"scanned/image-based, not real text. pdfplumber can't read it without OCR.")
                seen[url] = {"status": "no_text", "pdf_path": str(pdf_path)}
                continue

            if not clauses:
                print(f"    !! extracted {len(text)} chars of text but found 0 numbered clauses — "
                      f"this bill's PDF likely uses a different numbering style than \"1. \", \"2. \". "
                      f"Check {pdf_path.name} by eye and adjust CLAUSE_PATTERN if needed. "
                      f"Will retry automatically on the next run.")
                seen[url] = {"status": "no_clauses", "pdf_path": str(pdf_path)}
                continue

            bill_json = bill_to_json(link["title"], url, clauses, year=year)
            if year is None:
                bill_json["status"] = "needs_manual_review"  # no year detected — flag, don't guess
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            out_path = OUT_DIR / f"{pdf_path.stem}.json"
            out_path.write_text(json.dumps(bill_json, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"    -> {len(clauses)} clause(s) written to {out_path}")
            seen[url] = {"status": "ok", "pdf_path": str(pdf_path)}
            new_count += 1

    save_seen(seen)
    print(f"Done. {new_count} new bill(s) processed, {retried_count} retried, "
          f"{skipped_old_count} skipped as too old (pre-{MIN_YEAR}) this run.")


def run_test() -> None:
    """Offline test: point this at a bill PDF you already have, no network needed."""
    sample = BASE_DIR / "data" / "sample_bill.pdf"
    if not sample.exists():
        print(f"Put a sample PDF at {sample} to test offline, or run without --test.")
        sys.exit(1)
    text = extract_text(sample)
    clauses = split_into_clauses(text)
    print(f"Extracted {len(text)} characters, split into {len(clauses)} clause(s).")
    for c in clauses[:3]:
        print(f"--- Clause {c['clause_number']} ---")
        print(c["raw_text"][:200], "...\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="run offline against a local sample PDF")
    args = parser.parse_args()
    run_test() if args.test else run_live()
