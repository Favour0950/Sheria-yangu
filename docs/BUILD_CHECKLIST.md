# Sheria Yangu — Build Checklist

Living document — check items off as they're actually verified working (not just
written). Update this in the same commit as the work it describes.

## Pitch / deck (hackathon submission, July 4 + re-pitch July 31)

- [x] Scoresheet feedback reconciled, problem statement backed with cited stats
- [x] Persona corrected (Jared Ngisa Nyabuto, 2023 Nairobi Finance Act ruling)
- [x] 11-slide deck built to Dr C's template, validated, QA'd (`docs/SheriaYangu_Deck_v3.pptx`)
- [x] Responsible Computing / pseudo-anonymization architecture reconciled and documented (`docs/erd-and-security.md`)
- [x] 3:30 condensed re-pitch script + rubric coverage checklist
- [ ] Re-pitch delivered July 31 and finals delivered August 21 (Riara University) — outcome TBD

## Data layer

- [x] Nairobi County bill scraper (`src/scraper.py`) — live, tested, retry logic fixed, year filter added
- [x] National bill scraper (`src/scraper_national.py`) — live, tested against real Mzalendo data
- [x] Participation-notice/status cross-check (`src/participation_notices.py`) — live, tested
- [ ] Real public-participation open/close dates — still not available from any scraped source; every bill still lands as `needs_manual_review`, not `open`
- [x] Local Postgres schema live (`identity`, `bills`, `clauses`, `responses`, `memoranda`, `notification_log`) — all 6 tables created and verified
- [x] VPS access received from KamiLimu (137.184.204.191, Ubuntu 24.04) — Catherine to deploy + migrate Postgres, see `docs/postgres-setup.md` section 6
- [ ] Schema migrated to the VPS Postgres — Catherine, blocked on her running local setup (steps 1–5) first
- [ ] App actually deployed/running on the VPS, reachable on a public URL — Catherine
- [ ] SMS Two-Way callback URL registered with Mark Tanui — Violet, blocked on the above (needs a real public URL, or an ngrok tunnel as an interim) — stub route `/api/sms/inbound` is built and ready, see `docs/TESTING.md` section 5b

## Backend / API

- [x] Flask app skeleton, DeepSeek integration (`/api/summarize`, `/api/memorandum`) — but still running against the **mocked** `sample_bill.json`
- [x] SMS module (`src/sms.py`) — OTP + bill-notification sending, confirmed working with real Africa's Talking sandbox
- [x] `/api/auth/request-otp` + `/api/auth/verify-otp` — built, end-to-end tested (real code → real JWT)
- [x] **`/api/bill` + `/api/bills` wired to real scraped data** (`data/scraped_bills/`) — falls back to the old mock only if no scraper has run yet; tested with real fixture data (list, id lookup, 404, mock fallback all verified)
- [x] **Summarization prompt loosened** for real (longer/denser) clause text — up to 3 sentences/~90 words per language instead of one 30-word sentence; **not yet re-verified against real DeepSeek output — Violet to test with real scraped clauses and confirm quality/format before trusting for the pitch**
- [x] **Open-bills-only listing endpoint** (`/api/bills/open`, `status == "open"` filter) — tested with mixed-status fixture data, confirmed it correctly excludes everything except `open`. Will return an empty list until a bill's status is manually (or later, automatically) confirmed as open — that's correct, honest behaviour, not a bug. Also now excludes a bill whose `closes_at` has already passed (`_is_currently_open()`), so a published bill stops showing as open automatically once its window ends, without needing an admin to remember to close it by hand.
- [x] **Bill-detail.html no longer falls back to showing unpublished bills** — citizens only ever see `/api/bills/open`'s result; an empty result shows an honest "no bills open right now" message instead of listing pending/unreviewed bills. Unreviewed bills are admin-only from now on (see the review gate below).
- [x] **Admin review gate on publishing** (`admin_publish_bill()`) — a bill can only move to `status: "open"` once every one of its clauses has a `verified: true` entry in `<bill>.reviewed.json`. Rejects with 400 + the exact list of still-pending `clause_id`s otherwise. This is what actually enforces "citizens only ever see admin-approved summaries," closing the gap where an unreviewed AI summary could reach a citizen the moment a bill went open.
- [x] **`/api/admin/bills/<bill_id>/generate-summaries`** — bulk-triggers AI summarization for every clause of a bill that doesn't already have a review-queue entry, since summaries normally only generate when a citizen views a clause (and citizens can no longer reach an unpublished bill to do that). This is the new prerequisite step before the review gate above can ever be satisfied. Runs clauses serially, catches per-clause failures without aborting the batch — tested end-to-end (zero-review block, graceful per-clause failure with no `DEEPSEEK_API_KEY` set, and full success once every clause is hand-verified).
- [x] **`/api/admin/bills/<bill_id>/review-status`** + a live "X/Y clauses reviewed" badge on each Bills-tab card — added after real testing showed generate-summaries' "skipped" count reads as ambiguous ("skipped" only means "already has a queue entry," not "already approved"; a bill fully summarized in an earlier session showed "skipped 45" with no way to tell if those were reviewed or not). This endpoint gives an unambiguous verified/pending/rejected count per bill instead.
- [x] **`/api/responses`** — real votes written to the `responses` table, auth-required (JWT), `constituency_snapshot` copied at vote time, invalid vote/clause values rejected. Tested end-to-end.
- [x] **`/api/memoranda`** (+ `/api/memoranda/<id>/mark-sent`) — real memoranda drafted (DeepSeek, falls back to a manual template if the API call fails) and persisted, all three consent flags required, auth-required. Tested end-to-end including the missing-consent and bad-id rejection cases.
- [ ] `notification_log` writes — deliberately NOT built yet. This table records when a citizen was notified that a bill opened, but there's currently no "notify everyone this bill just opened" job to attach it to (no bill has a confirmed `open` status yet, see the open-bills-only endpoint above). Building this now would be a write path nothing ever calls. Revisit once there's a real trigger — either a human flips a bill to `open` and a batch job fires, or an admin action does.
- [x] County-vs-national memorandum email routing wired end-to-end in the real flow — `src/static/memo.html` now does this for the new authenticated flow (fetches the bill's `level`, routes to `clerk@nairobiassembly.go.ke` for county / `cna@parliament.go.ke` for national). `index.html`'s old copy of this logic is untouched, kept for the legacy demo.
- [x] `GET/PATCH /api/me` — self-reported constituency + notification toggle read/update, auth-required. Tested end-to-end (sqlite smoke test in this session).
- [x] `GET /api/analytics/constituency` — public, aggregate-only county participation counts, sourced from `responses.constituency_snapshot` only, never touches `identity`. Now takes an optional `?bill_id=` filter (see per-bill breakdown item below).
- [x] **Vote integrity fix** — `/api/responses` used to unconditionally INSERT a new row on every vote click, so repeat-clicking the same clause (intentional or not) inflated the vote count and let one person vote unlimited times per clause. Fixed with a database-level `UniqueConstraint(token, bill_id, clause_id)` on `responses` (see `db/models.py`) plus update-if-exists logic in `submit_response()`. Verified with an assertion-backed test: 3 clicks on the same clause (2 same choice, 1 changed mind) now leaves exactly 1 row, not 3.
- [x] **One memorandum per bill fix** — `/api/memoranda` used to allow unlimited memoranda per (citizen, bill). Fixed with `UniqueConstraint(token, bill_id)` on `memoranda` plus app logic: a still-`draft` memorandum for a bill is updated in place on redraft (not penalised), but attempting to create a new one after the existing one is `sent` returns 409. Verified with an assertion-backed test covering all three cases (create, redraft, blocked-after-send).
- [x] **Per-bill analytics** — new `GET /api/analytics/bills` (bills with vote counts, for the picker) + `?bill_id=` filter on `/api/analytics/constituency`. Fixes the original gap where county analytics mixed every bill's votes into one undifferentiated total.
- [x] **`GET /api/me/activity`** — the signed-in citizen's own votes + memoranda (the "see my data" profile view), scoped strictly to their token.
- [x] **Inbound SMS feedback now persisted + admin-viewable** — `sms_inbound()` writes every message to `data/inbound_sms.json`; `GET /api/admin/feedback` + a new "Feedback (SMS)" tab in `admin.html` show them. Added because the only way to see a received message used to be SSHing into the VPS and grepping `journalctl` — not something a judge can verify. Tested end-to-end (simulated inbound message → persisted → readable via the authenticated endpoint, blocked without auth).
- [x] **`ADMIN_NOTIFY_PHONE` now supports multiple numbers**, comma-separated (`run_scrapers_and_notify.py`) — sends to each independently so one bad/unreachable number doesn't block the others. Tested with two numbers.
- [x] **`feedback.html` + sidebar nav entry** — signed-in citizens now have an in-app feedback route (same SMS-compose pattern as welcome.html's public one), not just the public marketing page. Reachable from the hamburger drawer on every authenticated screen.

**Migration needed for the two new UniqueConstraints**: existing `responses`/`memoranda` tables (including any duplicate rows from testing before this fix) must be dropped and recreated — `init_db.py` never alters existing tables. See `docs/TESTING.md` section 3's migration note.

- [x] **Second analytics fix — distinct participants, not raw vote rows**: `/api/analytics/constituency` and `/api/analytics/bills` were still counting `Response` rows, so one citizen voting on all 3 clauses of a bill showed up as "3 votes" — inflated in a different way than the earlier re-click bug, but the same underlying problem (a count that doesn't represent real distinct people). Fixed to `COUNT(DISTINCT token)`. Verified: one person voting on 3 clauses now shows count 1; a second real person voting once correctly increments it to 2.
- [x] **Memorandum signature placeholder** — responding to judge feedback (Rose, via Catherine's July 27 email) that memoranda without a real name read as anonymous and risk being dismissed as spam. `create_memorandum()` now appends `"\n\nSincerely,\n[Your name]"` to every draft; `memo.html`'s status line explicitly tells the citizen to replace it. Nothing new stored server-side against the pseudonymous token — the name only ever lives in the outgoing email text.
- [x] **Clause language toggle now covers the clause heading too** — "Clause 1" was staying in English even in Kiswahili mode; now shows "Kifungu cha 1" when Kiswahili is selected (real clause titles, when present, are left as-is in either language).
- [x] **Root route (`/`) now serves `welcome.html`** (the public marketing landing page), not `splash.html` — `splash.html` (real sign-in entry) stays reachable at `/splash.html`, which is exactly what welcome.html's "Get started" button links to. The old 3-screen demo is still reachable directly at `/index.html`. Built and validated locally — **not yet deployed to the VPS as of this entry**, see Deployment section below.
- [x] **Admin bill-publish route** (`POST /api/admin/bills/<bill_id>/publish`) — flips a bill from `needs_manual_review` to `open` with admin-entered `opens_at`/`closes_at`. Admin-auth-gated, validates dates (both required, `closes_at` must be after `opens_at`). Tested end-to-end (success case + bad-dates/no-auth/unknown-bill error cases all verified) against a sandbox copy before touching real data.
- [x] **`admin.html` "Bills (Open/Closed)" tab** — lists every scraped bill regardless of status, lets an admin type real dates and publish. Sits alongside the existing "Summary Reviews" tab (clause-level AI summary approve/reject/edit) — these are two independent actions; publishing a bill open does not require its clauses to be reviewed first, and vice versa.
- [x] **Summary review cards now link to the real source PDF** (`source_url`, "View original bill PDF →") — the API was already returning this field but the admin UI never rendered it; now it does, closing a real gap in the "100% of our summaries link back to original text" claim.
- [x] **Ghost-bill bug fixed** — `_load_scraped_bills()`'s `*.json` glob was also matching each bill's own `<bill>.reviewed.json` sidecar file, showing a fake bill entry with every field null in `/api/bills`. Fixed by explicitly skipping `*.reviewed.json`. Found by hitting the real endpoint while testing the publish route, not by inspection.

**A schema/architecture note from this step**: `bills`/`clauses` tables are NOT populated — bill/clause content lives in `data/scraped_bills/*.json` (the working source of truth from day one), and `responses.clause_id`, `memoranda.bill_id` now reference that JSON file's ids as plain strings instead of real foreign keys into `bills`/`clauses`. This avoids needing a second, easy-to-drift copy of every scraped bill inside Postgres just to satisfy a foreign key. Documented fully in `src/db/models.py`'s `Bill` class docstring. If this ever needs tightening (e.g., a future admin panel manages bills directly in Postgres), it's a deliberate later upgrade, not an oversight.

## Frontend

- [x] Old 3-screen hackathon demo (`index.html`) — functional, kept as-is for backward compatibility, not the approved new design
- [x] **New approved UI screens built** — `src/static/{splash,signin,otp,bill-detail,bill-choice,clauses,terms,memo,settings,analytics,profile,policy}.html` + shared `css/style.css` + `js/app.js`. Real flow: splash (theme toggle) → sign-in (phone + optional constituency) → OTP entry (pre-fills the dev code when `SMS_DEV_MODE=true`) → bill list → bill detail (choice: read summary & vote, or view original text) → clause summaries + real votes (EN/Kiswahili toggle, defaults to English each new bill) → T&Cs/consent → memorandum draft + send (real county/national routing, plus a copy-to-clipboard fallback since `mailto:` only works with a default mail app configured) → settings, profile (own votes/memoranda), county analytics (now per-bill), Terms & data policy. All pages load (every page returned HTTP 200, inline JS syntax-checked clean), and the full backend flow behind them was exercised end-to-end with assertion-backed tests in this session.
- [x] **Persistent side-drawer nav** — `SY.injectNav()` in `app.js` injects a hamburger button + slide-out drawer (Bills, Profile, Settings, County analytics, Terms & data policy, a theme toggle, and Sign out) on every authenticated screen, not just the three pages with a bottom nav. Fixes the earlier gap where settings/theme/sign-out were only reachable from specific pages.
- [x] Two real TDZ (JS "temporal dead zone") bugs fixed — `clauses.html` and `memo.html` called their load function before the `const`s it read were assigned, causing the pages to silently freeze on "Fetching clauses…"/"Drafting your memorandum…" forever with no visible error (async functions turn a synchronous throw into an unhandled rejection, not a crash). Fixed by reordering; reproduced the exact failure and the fix in an isolated Node test before and after.

**Violet still needs to test/critique these visually in a real browser against the real Postgres + Africa's Talking setup** — this session's verification was page-loads + scripted API tests, not a human looking at the screens.

**Still open, not part of this batch** (from the notification-channels discussion): email verification flow + picking an email provider (Brevo recommended), and an in-app "new open bill" notification badge/list. Both still need Violet's go-ahead before building.

## Documentation

- [x] README (setup, architecture, problem statement)
- [x] `docs/erd-and-security.md` (schema + pseudo-anonymization write-up)
- [x] `docs/postgres-setup.md` (local Postgres walkthrough)
- [x] `docs/TESTING.md` (full setup-and-test runbook, every `.env` var, known quirks)
- [x] This checklist

## Known follow-ups (not urgent, tracked)

- [ ] Remove/replace the `mailto:` email-client handoff on `memo.html` (and `index.html`'s legacy copy) — works, but isn't the intended final UX; lower priority than VPS/SMS
- [ ] **Nairobi County public-notices scraper — evaluated, not built.** nairobi.go.ke's individual notice pages (e.g. the public-participation notices under "Tenders & Notices") only serve nav chrome + a title through static HTML; the actual notice text/dates render client-side via JavaScript, which this project's `requests`+`beautifulsoup4` stack cannot read. A real scraper here would need a headless browser (Playwright/Selenium), a new dependency this project doesn't have and isn't worth adding this close to finals. Real participation-window dates stay a deliberate human-in-the-loop step (admin reads the real notice, types the two dates into the new Bills tab) — not a gap to "finish" later, a permanent design choice given the source site.
- [x] **Scraper automation + admin SMS alert — built.** `src/run_scrapers_and_notify.py` runs both scrapers, diffs `data/scraped_bills/` before/after to find what's genuinely new (without touching either scraper's own tested logic), and texts `ADMIN_NOTIFY_PHONE` (new `.env` var) via a new `sms.notify_admin_new_bills()`. Tested end-to-end with stubbed scrapers (new-bill detection, no-phone-set skip, and SMS-failure-doesn't-crash-the-run all verified). Cron wiring itself still needs to be added by hand on the VPS (`crontab -e`) — one line, see the note in that file's docstring. Does NOT solve the separate notices-scraper problem above — this only alerts that a new bill *document* was found, never a real open/close date.
- [ ] **Alternative SMS provider/route for Safaricom numbers.** The Safaricom USSD opt-out fix (`*456*9#` → option 5 → option 5, to clear the marketing-SMS blacklist flag behind Africa's Talking's `UserInBlacklist`/406 error) did not resolve the issue when tested. Worth researching whether Africa's Talking has an alternative sender ID/route for transactional (non-marketing) SMS that bypasses this, or whether a different aggregator handles Safaricom transactional OTP/notification delivery more reliably. Not blocking for finals if `SMS_DEV_MODE=true` is used for the live demo (see Demo-day readiness below), but a real gap for actual production use.

## Demo-day readiness

- [ ] Test venue WiFi/network before presenting (network reliability has varied by location during dev)
- [ ] Record a real backup video of SMS/OTP working end-to-end, in case of live network issues
- [ ] Decide + rehearse whether the live demo runs with `SMS_DEV_MODE=true` (safer) or real SMS (higher risk, more impressive if it works)
