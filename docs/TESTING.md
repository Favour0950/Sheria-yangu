# Sheria Yangu — Setup & Testing Guide

For anyone setting up this repo fresh (Catherine, a judge, a new contributor) and
for Violet re-testing after a break. Covers every module currently built, in the
order you'd actually run them. **Keep this file updated** — when a new script,
route, or `.env` variable is added, add it here in the same commit.

---

## 0. Which terminal to use

Any of Git Bash, PowerShell, or CMD works, but **don't mix commands from
different shells in one line** — `source venv/Scripts/activate` is a Bash-only
command and will break if pasted into PowerShell, and vice versa. Pick one
terminal per session and stay in it.

| Shell | Activate the venv with |
|---|---|
| Git Bash | `source venv/Scripts/activate` |
| PowerShell | `& "venv\Scripts\Activate.ps1"` (may need `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` once first) |
| CMD | `venv\Scripts\activate.bat` |

You'll know it worked because the prompt gets a `(venv)` prefix.

**Don't run `python -m venv venv` while that same venv is active** — Windows
locks the interpreter file it's currently running, and recreation fails with
"Unable to copy ... venvlauncher.exe". Deactivate first, or open a fresh
terminal, if you ever need to rebuild the venv from scratch.

---

## 1. Clone & install

```bash
git clone https://github.com/Favour0950/Sheria-yangu.git
cd Sheria-yangu
python -m venv venv
source venv/Scripts/activate      # or the PowerShell/CMD equivalent above
pip install -r requirements.txt
```

**Important — the repo does NOT include scraped bill data.** `data/` is
gitignored on purpose (generated content, and some bill PDFs are 20-30MB —
too big to want in git history). Cloning the repo gives you the *code* for the
scrapers, not their *output*. You must run the scrapers yourself (section 4)
to populate `data/raw_pdfs/`, `data/scraped_bills/`, and `data/seen_urls.json`
locally. Two people cloning the same repo will NOT have identical `data/`
folders unless they both run the scrapers against the same live sites at
roughly the same time.

---

## 2. `.env` — every variable, what it's for, where to get it

Copy the template first: `cp .env.example .env`. Never commit the real `.env`
(already gitignored) or paste real key values into chat/Slack/anywhere public.

| Variable | Used by | What it is |
|---|---|---|
| `DEEPSEEK_API_KEY` | `main.py` (`/api/summarize`, `/api/memorandum`) | From the KamiLimu organiser email |
| `DEEPSEEK_MODEL` | `main.py` | Defaults to `deepseek-chat`, usually leave as-is |
| `DEEPSEEK_BASE_URL` | `main.py` | Defaults to `https://api.deepseek.com/v1`, usually leave as-is |
| `AT_USERNAME` | `sms.py`, `main.py` | `sandbox` while testing; your live app's username once deployed |
| `AT_API_KEY` | `sms.py`, `main.py` | From your Africa's Talking Sandbox app → Settings → API Key |
| `SENDGRID_API_KEY` / `SENDGRID_FROM_EMAIL` | not currently wired into any route | Held in reserve — email notifications were deprioritised in favour of SMS-only after SendGrid signup friction; revisit only if the team decides to add email back |
| `DATABASE_URL` | `main.py`, `src/db/init_db.py` | `postgresql://sheria_user:<password>@localhost:5432/sheria_yangu` — see `docs/postgres-setup.md` |
| `PEPPER` | `main.py` (phone-number hashing) | A random secret — generate your own with `python -c "import secrets; print(secrets.token_hex(32))"`, never reuse the example value |
| `JWT_SECRET` | `main.py` (session tokens) | Same as above — generate a *different* random value, don't reuse `PEPPER`'s |
| `SMS_DEV_MODE` | `main.py`'s `/api/auth/request-otp` only | `true` while testing the auth flow without needing real SMS delivery; **must be `false`/unset in any real deployment** |

---

## 3. Postgres

Full walkthrough: `docs/postgres-setup.md`. The one step everyone forgets on
Postgres 15+ (including 18): after `CREATE DATABASE`/`CREATE USER`, you must
also run `GRANT ALL ON SCHEMA public TO sheria_user;` **while connected to the
`sheria_yangu` database specifically** (`psql -U postgres -d sheria_yangu`,
not just `psql -U postgres`) — otherwise table creation fails with
`permission denied for schema public`.

Once set up:
```bash
python src/db/init_db.py
psql -U sheria_user -d sheria_yangu -c "\dt"
```
Expect 6 tables: `identity`, `bills`, `clauses`, `responses`, `memoranda`, `notification_log`.

If a model in `src/db/models.py` changes later (new column, etc.), `init_db.py`
only creates *missing* tables — it won't alter an existing one. Before real
user data exists, the fix is to drop and recreate the affected table:
```bash
psql -U postgres -d sheria_yangu -c "DROP TABLE identity;"
python src/db/init_db.py
```

---

## 4. Scrapers

```bash
python src/scraper.py --test              # offline, needs data/sample_bill.pdf
python src/scraper.py                      # live: Nairobi County Assembly bills
python src/scraper_national.py --house na       # live: National Assembly bills, via Mzalendo
python src/scraper_national.py --house senate   # live: Senate bills, via Mzalendo
python src/participation_notices.py --house na  # standalone: just prints Mzalendo's active-bill list, doesn't write files
```
Expected: `scraper.py` prints a per-bill line and a `Done. X new, Y retried, Z skipped as too old` summary. `scraper_national.py` prints the same shape. Neither should error out — a "no PDF found" or "0 clauses" line for a specific bill is normal/expected (some bills genuinely don't have parseable PDFs yet), not a failure of the run itself.

**On legality**: everything scraped is public, unauthenticated content — government bill PDFs from `nairobiassembly.go.ke` (an official public-participation page, no login) and Mzalendo Trust's own re-hosted bill PDFs + bill-tracker CSV export (Mzalendo's `robots.txt` explicitly allows crawling: `User-agent: * / Allow: /`). No X/Twitter scraping is used anywhere in this codebase — Mzalendo's Twitter account came up earlier only as evidence that "active participation calls" get curated publicly somewhere, not as a scrape target. One nuance worth knowing: `scraper_national.py` uses a standard browser User-Agent for Mzalendo specifically (see that file's docstring) because Mzalendo's server serves a stripped-down page to non-browser UAs — this works around basic bot-filtering on one site, not around any paywall or login, and the data being accessed is identical either way.

**What's still NOT real**: neither scraper knows a bill's actual public-participation open/close date. `scraper.py`/`scraper_national.py` always write `status: "needs_manual_review"`; `participation_notices.py` gives Mzalendo's legislative *stage* (passed/withdrawn vs. still active) as a proxy for relevance, not a real deadline. No dashboard code should ever display a bill as "open" based on scraper output alone.

---

## 5. SMS

```bash
python src/sms.py --test-otp +2547XXXXXXXX
python src/sms.py --test-notification +2547XXXXXXXX
```
Requires a real Africa's Talking Sandbox `AT_API_KEY` (see section 2) and, for the number to actually appear in AT's simulator, that number must be added as a simulator number in the AT dashboard first. A successful run prints `[sms] OTP send response for ...: {'SMSMessageData': ...'status': 'Success'...}`.

If this fails with a connection/SSL/timeout error but not on every machine/network, that's a known local TLS-stack quirk, not a code bug — `sms.py` and `scraper_national.py` both have an automatic curl-based fallback (`src/net.py`) for exactly this. If curl also fails, it's a real outage, not a code fix.

### 5b. Two-Way SMS (inbound) — new, shared KamiLimu gateway

This is separate from the outbound OTP/notification sending above. KamiLimu
gave every team a shared shortcode (20880) and keyword ("kamilimu") — users
text `kamilimu <project> <message>`, Mark's router identifies the project and
re-POSTs matching messages to *our* registered callback URL. We don't parse
the "kamilimu" prefix ourselves; that already happened upstream by the time a
request reaches us.

**Route:** `POST /api/sms/inbound` in `main.py` — currently a **stub**. It
logs whatever it receives and returns 200. It does NOT yet do anything with
an inbound reply, because the product behavior isn't decided yet (does
replying to a bill notification vote on it? Unsubscribe? Something else?)
— that's a call for the team, not something to guess at in code.

**Testing locally before we're deployed:**
```bash
curl -X POST http://localhost:5000/api/sms/inbound -d "from=+254700000000&text=kamilimu sheriayangu hello&to=20880&id=test123"
```
Expect: `[sms_inbound] raw payload received: ...` printed in the `main.py`
console, and an empty 200 response.

**Getting a real public URL before the VPS is live:** Mark needs an actual
reachable URL to register, which `localhost:5000` isn't. Until the VPS
deployment is done (see `docs/postgres-setup.md` section 6), the fastest way
to get a real URL to hand him is a temporary tunnel:
```bash
ngrok http 5000
```
then give him the `https://....ngrok-free.app/api/sms/inbound` URL it prints.
Swap to the real VPS URL once deployed — ngrok URLs expire/rotate on the free
tier, so don't treat that as the permanent one.

**Still unconfirmed with Mark:** the exact keyword prefix that routes to
*our* project specifically (is it `kamilimu sheriayangu`? something else?),
and the exact shape of the payload his router re-POSTs to us (the route
above guesses at Africa's Talking's normal `from`/`text`/`to`/`id` fields,
which may not survive his re-routing exactly as-is — check the printed log
against whatever the first real inbound message actually looks like).

---

## 6. Flask app + auth routes

```bash
python src/main.py
```
Runs on `http://localhost:5000`.

**Auth flow (with `SMS_DEV_MODE=true`):**
```bash
curl -X POST http://localhost:5000/api/auth/request-otp -H "Content-Type: application/json" -d '{"phone_number":"+2547XXXXXXXX","constituency":"Kibra"}'
```
Copy the `dev_otp_code` from the response, then **immediately** (codes expire after 5 minutes and each new request invalidates the previous code):
```bash
curl -X POST http://localhost:5000/api/auth/verify-otp -H "Content-Type: application/json" -d '{"phone_number":"+2547XXXXXXXX","code":"<paste the real code here>"}'
```
Expect `{"access_token": "...", "token_type": "bearer"}`.

**Flipping to real SMS**: set `SMS_DEV_MODE=false` in `.env`, restart `main.py`. `request-otp` will then actually text the code instead of returning it — no other code change needed.

**Votes and memoranda** (needs the access_token from `verify-otp` above, and a real bill id from `/api/bills`):
```bash
curl -X POST http://localhost:5000/api/responses -H "Content-Type: application/json" -H "Authorization: Bearer <access_token>" -d '{"bill_id":"<id>","clause_id":"c1","vote":"kubali"}'

curl -X POST http://localhost:5000/api/memoranda -H "Content-Type: application/json" -H "Authorization: Bearer <access_token>" -d '{"bill_id":"<id>","rejected_clause_ids":["c1"],"consent_read_summary":true,"consent_not_bot":true,"consent_terms":true}'
# → returns a memorandum_id, use it below:
curl -X POST http://localhost:5000/api/memoranda/<memorandum_id>/mark-sent -H "Content-Type: application/json" -H "Authorization: Bearer <access_token>" -d '{}'
```
**Important — every `<...>` above is a placeholder you must replace with a real value, not literal text to paste.** In Bash/Git Bash specifically, a literal `<id>` left in a command is interpreted as "read input from a file named `id`", not as a placeholder — it will fail with a confusing error, not a helpful one. Always substitute the actual id/token before running.

**One-time DB migration needed for this**: `responses.clause_id` and `memoranda.bill_id` changed from UUID columns to plain strings (see `src/db/models.py`'s `Bill` class docstring for why). Since `init_db.py` never alters existing tables, drop and recreate these three before testing:
```bash
psql -U postgres -d sheria_yangu -c "DROP TABLE responses, memoranda, notification_log;"
python src/db/init_db.py
```

**Second migration, more recent**: `responses` and `memoranda` each gained a `UniqueConstraint` (one vote per person per clause; one memorandum per person per bill — see the checklist's "Vote integrity fix" entry). If you migrated for the paragraph above before this fix landed, your `responses`/`memoranda` tables may already have duplicate rows (e.g. the 7-votes-from-3-clicks bug) that would violate the new constraint. Drop and recreate both again:
```bash
psql -U postgres -d sheria_yangu -c "DROP TABLE responses, memoranda;"
python src/db/init_db.py
```

**Bill routes** (now wired to real scraped data — falls back to the old mock only if `data/scraped_bills/` is empty, e.g. a fresh clone before you've run any scraper):
```bash
curl http://localhost:5000/api/bills            # list every scraped bill (any status)
curl http://localhost:5000/api/bills/open       # only bills with status == "open" — the dashboard's real data source, will be empty until a bill is manually confirmed open
curl http://localhost:5000/api/bill             # full detail of the first scraped bill (or the mock, if none exist yet)
curl "http://localhost:5000/api/bill?id=<id from /api/bills>"   # full detail of a specific bill
curl -X POST http://localhost:5000/api/summarize -H "Content-Type: application/json" -d '{"clause_id":"c1","raw_text":"...","affected_group":"boda boda riders"}'
```
**Verify the summarization output yourself** — the prompt was just loosened from one 30-word sentence to up to 3 sentences (~90 words) per language, to handle real bills' denser clause text. Use the helper script instead of hand-copying clause text into curl (real legal text has quotes/newlines that break shell quoting):
```bash
python src/test_summarize.py                                    # first bill, first clause
python src/test_summarize.py --bill-id <id> --clause 2 --affected-group "boda boda riders"
```
Check: does it still return exactly the `EN:`/`SW:` two-line format the frontend parses, is the length actually reasonable, and is the Swahili genuinely usable? DeepSeek doesn't always respect a word cap exactly.

---

## 7. New UI screens (the approved design, not the old 3-screen demo)

`index.html` (section 6 above) is still the old hackathon demo — unauthenticated,
mocked-vote-in-memory, kept only for backward compatibility. The real, approved
screens are separate files under `src/static/`, sharing one `css/style.css` and
one `js/app.js` (no build step — just open them through the running Flask app,
same as `index.html`).

**Start here:** `http://localhost:5000/splash.html`

Click through in this order — each screen links to the next automatically:

1. **`splash.html`** — logo + tagline + light/dark toggle. Click "Get Started".
2. **`signin.html`** — enter a real-looking phone number (e.g. `+254700000001`)
   and, optionally, a constituency. Click "Send code →". This calls the same
   `/api/auth/request-otp` you already tested by curl.
3. **`otp.html`** — with `SMS_DEV_MODE=true`, the 6 boxes **auto-fill with the
   real dev code** so you don't have to check a terminal. Click "Verify →".
   This calls `/api/auth/verify-otp` and stores the real JWT in the browser's
   `localStorage` (key `sy_access_token`) — open DevTools → Application →
   Local Storage to see it if you want to confirm.
4. **`bill-detail.html`** — lists bills from `/api/bills/open` if any exist,
   otherwise falls back to `/api/bills` with an honest "pending review" label
   (expected right now, since no bill has a confirmed open status — see
   section 4/checklist). Click "View this bill →" on any bill.
5. **`bill-choice.html`** — the bill's full detail plus two choices: "Read
   plain-language summary & vote" or "View original bill text ↗" (opens the
   real source PDF/URL in a new tab).
6. **`clauses.html`** — same clause-summary-and-vote UI as the old demo, but
   every Kubali/Kataa click now writes a **real, authenticated** row via
   `POST /api/responses` (check `psql -U sheria_user -d sheria_yangu -c "SELECT * FROM responses;"`
   afterward to confirm). Reject at least one clause, then "Review my response →".
7. **`terms.html`** — the 3 required consent checkboxes. All three must be
   checked before "Draft my memorandum →" enables.
8. **`memo.html`** — drafts via `POST /api/memoranda` (real DeepSeek call,
   same as `test_summarize.py`'s summaries), shows the draft, lets you edit it,
   and "Tuma kwa Bunge (Send)" both marks it sent via `mark-sent` **and**
   opens your email client addressed correctly by bill level (county →
   `clerk@nairobiassembly.go.ke`, national → `cna@parliament.go.ke`).
9. **`settings.html`** — loads your real constituency/notification settings via
   `GET /api/me`, saves changes via `PATCH /api/me`. "Sign out" clears the
   stored token and sends you back to `splash.html`.
10. **`analytics.html`** — now has a bill selector at the top (populated from
    `GET /api/analytics/bills`); pick a bill to see its own vote-by-
    constituency breakdown from `GET /api/analytics/constituency?bill_id=...`.
    No sign-in needed to view this page. Should show whatever constituency
    you entered in step 2/9, with a count of exactly 1 per clause you voted
    on (re-clicking Kubali/Kataa updates your existing vote, it no longer
    stacks up duplicate rows — this was the "7 votes in 2 minutes" bug).
11. **`profile.html`** — your own votes and memoranda (`GET /api/me/activity`),
    separate from settings.html's editable preferences.
12. **`policy.html`** — static Terms & data policy page.
13. **Hamburger menu** — every authenticated screen now has a ☰ button
    (top-right of the header) opening a side drawer: Bills, Profile,
    Settings, County analytics, Terms & data policy, a theme toggle, and
    Sign out — all reachable from anywhere, not just settings.html.
14. **Language toggle** — on `clauses.html`, an English/Kiswahili toggle above
    the clause list shows one language at a time (both are still fetched in
    one `/api/summarize` call, the toggle just shows/hides). Resets to
    English on every fresh bill — it's not persisted.

**What I've already verified (this session, before handing off to you):**
Every one of the 10 pages above returns HTTP 200 and loads its CSS/JS with no
404s. Every inline `<script>` block passed a Node syntax check. The full
backend chain behind these screens (request-otp → verify-otp → `/api/me` GET
and PATCH → `/api/responses` → `/api/analytics/constituency` → `/api/memoranda`)
was run end-to-end in an isolated test database and returned correct data at
every step. **What I have NOT done: opened these pages in an actual browser.**
Layout, spacing, dark-mode contrast, and anything that only shows up visually
still needs your eyes on it — that's the point of this round.

---

## 8. Known environment quirks (so you don't re-debug these)

- **Postgres 15+ schema permission** — see section 3.
- **Local TLS/network flakiness on some machines** — `src/net.py`'s curl fallback handles it for SMS and the national scraper; if you hit a similar SSL/timeout error somewhere else, that's the pattern to apply.
- **Mzalendo's bot-filtering** — needs a browser User-Agent, already handled in `scraper_national.py`.
- **`init_db.py` doesn't alter existing tables** — drop-and-recreate is fine pre-launch, not once real users exist.
