# Admin review backend — spec for Catherine

What it's for: a human checks that an AI-generated clause summary (English +
Swahili) actually matches the real bill text before it's trusted — directly
backs the "100% of our summaries link back to the exact original text" claim
in the Responsible Computing slide. Right now that claim is true by
construction (the summarizer is only ever given real scraped text, never
asked to invent one), but there's no step that catches the AI getting the
*meaning* wrong while still citing a real source. This closes that gap.

## What already exists that this builds on

- `Clause` model (`src/db/models.py`): `bill_id`, `raw_text`, `summary_en`,
  `summary_sw`, `source_url` — the right shape for this, but **not currently
  populated**. Bill/clause content today lives in flat JSON files under
  `data/scraped_bills/*.json` (see that class's docstring for why), and
  `/api/summarize` calls DeepSeek fresh each time rather than reading/writing
  a stored summary.
- `/api/summarize` (`main.py`) — takes `raw_text`, returns `EN:`/`SW:` text.
  No persistence today; the frontend calls this live and shows the result.

## Decision Catherine needs to make first

Whether verified summaries live in **Postgres** (start actually populating
`Bill`/`Clause`, add `verified`/`verified_by`/`verified_at` columns) or as a
**JSON sidecar** next to each scraped bill file (e.g.
`data/scraped_bills/<bill>.reviewed.json`, matching the project's existing
JSON-file-as-source-of-truth pattern). Postgres is the more "real" answer
and gives you a queryable review log for free; the JSON route is less new
code since everything else bill/clause-related already reads and writes
JSON. Either is defensible — pick based on how much time is actually left,
not which is "more correct."

## Minimum viable version (what to build first)

1. **Admin auth** — separate from the citizen phone/OTP flow entirely. For
   hackathon scope, a single shared admin password (env var, e.g.
   `ADMIN_PASSWORD`) behind a `/api/admin/login` route issuing its own JWT
   (reuse `JWT_SECRET` or a second secret) is enough — a full admin-user
   table with individual logins is a nice-to-have, not required for finals.
2. **Review queue** — `GET /api/admin/summaries/pending` returns clauses
   whose summary hasn't been reviewed yet: `raw_text`, `summary_en`,
   `summary_sw`, `source_url`, `bill_id`, `clause_id`.
3. **Review action** — `POST /api/admin/summaries/<clause_id>/review` with
   `{ "decision": "approve" | "reject" | "edit", "corrected_summary_en":
   ..., "corrected_summary_sw": ..., "note": ... }`. Approve/edit both mark
   `verified = true`; reject marks it flagged and excluded from what
   citizens see until re-summarized.
4. **Citizen-facing effect** — decide (and this is a product call, not a
   pure engineering one): does `clauses.html` *block* on an unverified
   summary, or show it with an "unverified" badge? Given how close finals
   are, showing with a badge and fixing egregious mismatches as they're
   caught is more realistic than gating the whole flow on review completing
   first — but say that decision out loud to the team rather than have it
   default silently either way.

## Not required for finals, real nice-to-haves later

Per-admin accountability (who reviewed what), a diff view highlighting
exactly which words changed on an edit, and batch-approve for low-risk
clauses (e.g. procedural/administrative ones) once there's a sense of which
categories rarely have summarization errors.

## One thing to flag to Catherine directly

This is Violet's understanding of what's needed, written from the outside —
Catherine should sanity-check the auth approach and the Postgres-vs-JSON
call against however much time is actually left before finals, and adjust
scope down further if needed. A working approve/reject queue with simple
shared-password auth is a real, honest Responsible Computing story even if
nothing past the MVP list above gets built.
