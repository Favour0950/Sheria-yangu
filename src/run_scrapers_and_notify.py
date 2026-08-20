"""
src/run_scrapers_and_notify.py — cron entry point: runs both scrapers, then
texts the admin phone number if anything new showed up.

Why this exists: scraper.py/scraper_national.py only ever find bill
*documents* — they still cannot detect a real public-participation open/close
date (see both files' docstrings; that's a separate, harder problem this does
NOT solve — see docs/BUILD_CHECKLIST.md's "Nairobi County public-notices
scraper" entry for why). What this DOES solve: an admin no longer has to
remember to manually re-run the scrapers to notice a new bill exists. Run on
a schedule (see the cron line below), it pings the admin phone the moment
something new lands in data/scraped_bills/, so they know to log into
admin.html and start the generate-summaries -> review -> publish workflow.

Detects "new" by diffing the set of *.json filenames in data/scraped_bills/
before and after both scrapers run — deliberately NOT touching scraper.py's/
scraper_national.py's own tested run_live()/run() logic to compute this, so
this stays a thin wrapper around already-working, already-tested code rather
than a second copy of "what counts as new" that could drift out of sync.

Set ADMIN_NOTIFY_PHONE in .env to the admin's real phone number (+2547...)
for the SMS step to actually send anything. If it's unset, this still runs
both scrapers and logs everything to stdout/the cron log — it just skips the
notification step (printed clearly, not a silent no-op).

Run manually:
  python src/run_scrapers_and_notify.py

Cron (daily at 6pm — see docs/TESTING.md or ask Claude for the exact
crontab line for your VPS user):
  0 18 * * * cd /home/sheriayangu/Sheria-yangu && \
    /home/sheriayangu/Sheria-yangu/venv/bin/python3 src/run_scrapers_and_notify.py \
    >> /home/sheriayangu/Sheria-yangu/logs/scraper_cron.log 2>&1
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
SCRAPED_DIR = BASE_DIR / "data" / "scraped_bills"
ADMIN_NOTIFY_PHONE = os.getenv("ADMIN_NOTIFY_PHONE")


def _current_bill_files() -> set:
    """Every scraped-bill JSON filename right now, excluding *.reviewed.json
    sidecars (see main.py's _load_scraped_bills for why those must never be
    treated as bills)."""
    if not SCRAPED_DIR.exists():
        return set()
    return {p.name for p in SCRAPED_DIR.glob("*.json") if not p.name.endswith(".reviewed.json")}


def main():
    before = _current_bill_files()

    print("=== Running county scraper (scraper.py) ===")
    try:
        import scraper
        scraper.run_live()
    except Exception as exc:
        print(f"!! county scraper failed: {exc}")

    for house in ("na", "senate"):
        print(f"=== Running national scraper (scraper_national.py) — {house} ===")
        try:
            import scraper_national
            scraper_national.run(house)
        except Exception as exc:
            print(f"!! national scraper ({house}) failed: {exc}")

    after = _current_bill_files()
    new_files = sorted(after - before)

    if not new_files:
        print("No new bills this run.")
        return

    titles = []
    for fname in new_files:
        try:
            data = json.loads((SCRAPED_DIR / fname).read_text(encoding="utf-8"))
            titles.append(data.get("title", fname))
        except (json.JSONDecodeError, OSError):
            titles.append(fname)

    print(f"{len(new_files)} new bill(s) found: {titles}")

    if not ADMIN_NOTIFY_PHONE:
        print("ADMIN_NOTIFY_PHONE not set in .env — skipping SMS notification. "
              "Set it to one or more admin phone numbers (comma-separated) to enable this.")
        return

    # Comma-separated so both Violet and Catherine (or anyone else) can be
    # notified, not just one hardcoded number — e.g.
    # ADMIN_NOTIFY_PHONE=+254700000001,+254700000002 in .env. Each number is
    # sent to independently so one bad/unreachable number doesn't block the
    # others from getting notified.
    phone_numbers = [p.strip() for p in ADMIN_NOTIFY_PHONE.split(",") if p.strip()]
    import sms
    for phone in phone_numbers:
        try:
            sms.notify_admin_new_bills(phone, titles)
        except Exception as exc:
            print(f"!! failed to send admin notification SMS to {phone}: {exc}")


if __name__ == "__main__":
    main()
