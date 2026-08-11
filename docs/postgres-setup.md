# Local Postgres setup (both Violet & Catherine)

Confirmed plan: build the real schema against a **local** Postgres now, then migrate
by pointing `DATABASE_URL` at the KamiLimu-provisioned DigitalOcean droplet's Postgres
later. The schema (`src/db/models.py`) doesn't change between the two — only the
connection string does.

## 1. Confirm Postgres is running

```bash
# Windows (Git Bash) / macOS / Linux — one of these should work:
pg_isready
# or
psql --version
```

If `psql` isn't found, Postgres is installed but not on your PATH — find its `bin`
folder (Windows: usually `C:\Program Files\PostgreSQL\<version>\bin`) and add it, or
use the full path to `psql.exe` below.

## 2. Create the database + a dedicated app user

Open `psql` as the postgres superuser (Windows: this is usually the account you set a
password for during install):

```bash
psql -U postgres
```

Then, inside the `psql` prompt:

```sql
CREATE DATABASE sheria_yangu;
CREATE USER sheria_user WITH PASSWORD 'pick-a-local-password';
GRANT ALL PRIVILEGES ON DATABASE sheria_yangu TO sheria_user;
\c sheria_yangu
GRANT ALL ON SCHEMA public TO sheria_user;
\q
```

**Note (Postgres 15+, including 18):** `GRANT ALL PRIVILEGES ON DATABASE` alone is
NOT enough anymore — Postgres 15 changed the default so a new user has no
`CREATE` permission inside the `public` schema even after that grant. Without
the `\c sheria_yangu` + `GRANT ALL ON SCHEMA public` step above, table creation
fails with `permission denied for schema public`. This is the single most common
setup snag on a fresh Postgres 15+ install — if you ever recreate the DB/user
from scratch, don't skip this line.

Use a different password from anything real/production — this is a local dev
database, but don't reuse a password you care about out of habit.

## 3. Point the app at it

In your `.env` (not `.env.example` — that one stays a template, never real values):

```
DATABASE_URL=postgresql://sheria_user:pick-a-local-password@localhost:5432/sheria_yangu
```

Both Violet and Catherine set this locally in their own `.env` — it's not shared or
committed (`.env` is already in `.gitignore`).

## 4. Install the new Python dependencies

```bash
pip install -r requirements.txt
```

This pulls in `SQLAlchemy` and `psycopg2-binary` (added alongside the existing
scraper/SMS dependencies).

## 5. Create the tables

```bash
python src/db/init_db.py
```

This reads `src/db/models.py` (which matches `docs/erd-and-security.md` exactly —
`identity`, `bills`, `clauses`, `responses`, `memoranda`, `notification_log`) and
creates any tables that don't already exist. Safe to re-run.

Verify it worked:

```bash
psql -U sheria_user -d sheria_yangu -c "\dt"
```

You should see all six tables listed.

## 6. Migrating to the VPS (this is now live, not speculative)

Mark's readiness-check email confirmed every team has now received VPS access
— so this section is the actual next step for Catherine, not a someday-later
note anymore.

**Status as of this handoff:** Violet has the schema working against a local
Postgres (steps 1–5 above, all six tables created and verified with `\dt`).
Catherine has NOT yet run the same local setup on her own machine, and needs
to — the `DATABASE_URL` in `.env` is never committed/shared, so this isn't
something that carries over automatically from Violet's machine. Do steps
1–5 above on your own machine first, confirm the six tables exist locally,
*then* do the VPS migration below — that way if something breaks on the VPS,
you already know the schema itself is fine and the problem is
connection/environment-specific.

**Migrating once you have the VPS's Postgres details:**

```
DATABASE_URL=postgresql://<vps-user>:<vps-password>@<vps-ip>:5432/sheria_yangu
```

then re-run `python src/db/init_db.py` once against the new URL to create the same
tables there. If real data already exists locally by then and needs to move over
too (not just the empty schema), that's a `pg_dump` / `pg_restore` job — worth
doing as its own step closer to the actual migration date, not something to solve
speculatively now.

**Also needed on the VPS, not just Postgres:** the app itself (`src/main.py`)
needs to actually run there and be reachable on a public URL/port, since
that's also the URL we owe Mark for the SMS Two-Way callback registration
(see `docs/TESTING.md` section 5b). Worth doing the Postgres migration and
the app deployment as one pass rather than two separate ones, since Mark's
waiting on the callback URL specifically.
