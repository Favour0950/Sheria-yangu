"""
Sheria Yangu — backend entry point.

Built during the Mozilla Foundation x KamiLimu Democracy & AI Hackathon — July 4th, 2026.

What this does (matches the "what is built/mocked today" line in docs/architecture.md):
  - BUILT:  Flask API serving a hardcoded bill, calling the DeepSeek LLM to generate
            plain-language Swahili + English clause summaries, and compiling a
            memorandum draft from clauses the user rejected.
  - MOCKED: The bill itself (data/sample_bill.json) instead of a live scraper of
            Kenya Law / county assembly sites. The "send to Parliament" step opens
            a mailto: link in the browser rather than actually emailing Parliament.

Run:
  python src/main.py
Then open http://localhost:5000 in your browser.
"""

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

import jwt
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sms
from db.models import Identity, Memorandum, Response
from sqlalchemy import func

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

DATABASE_URL = os.getenv("DATABASE_URL")
PEPPER = os.getenv("PEPPER")
JWT_SECRET = os.getenv("JWT_SECRET")
SMS_DEV_MODE = os.getenv("SMS_DEV_MODE", "false").lower() == "true"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "sample_bill.json"
SCRAPED_BILLS_DIR = BASE_DIR / "data" / "scraped_bills"
FRONTEND_DIR = BASE_DIR / "src" / "static"

app = Flask(__name__, static_folder=None)

# Engine is created lazily/tolerantly so the rest of the app (bill/summarize/
# memorandum routes, which predate the DB work) still runs even if DATABASE_URL
# isn't set yet — only the /api/auth/* routes below actually need it.
_engine = create_engine(DATABASE_URL) if DATABASE_URL else None
_SessionLocal = sessionmaker(bind=_engine) if _engine else None


def hash_phone(phone_number: str) -> str:
    """Keyed HMAC-SHA256, per docs/erd-and-security.md — never plain hashlib.sha256
    on its own, since that would be brute-forceable against the small space of
    valid Kenyan phone numbers. PEPPER lives only in .env, never in the DB."""
    if not PEPPER:
        raise RuntimeError("PEPPER is not set — copy .env.example to .env and set a real random value.")
    return hmac.new(PEPPER.encode(), phone_number.encode(), hashlib.sha256).hexdigest()


def hash_otp(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def get_bearer_token() -> uuid.UUID | None:
    """
    Verifies the Authorization: Bearer <JWT> header and returns the
    pseudonymous identity.token it carries as a real uuid.UUID object (not a
    plain string — SQLAlchemy's UUID(as_uuid=True) columns require an actual
    UUID instance to bind correctly; passing the JWT's string form straight
    through fails with "'str' object has no attribute 'hex'" the moment you
    try to insert/filter with it). Returns None if the header is missing,
    the JWT is invalid/expired, or its "token" claim isn't a valid UUID.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    raw_token = auth_header.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(raw_token, JWT_SECRET, algorithms=["HS256"])
        return uuid.UUID(payload.get("token"))
    except (jwt.PyJWTError, ValueError, TypeError):
        return None


def require_auth(view_func):
    """Rejects a request with 401 unless it carries a valid access_token from
    /api/auth/verify-otp. On success, stashes the pseudonymous token on
    `request.identity_token` for the view to use."""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        token = get_bearer_token()
        if not token:
            return jsonify({"error": "Missing or invalid Authorization: Bearer <access_token> header — "
                                      "sign in via /api/auth/request-otp + /api/auth/verify-otp first"}), 401
        request.identity_token = token
        return view_func(*args, **kwargs)
    return wrapper

def require_admin(view_func):
    """Rejects a request with 401/403 unless it carries a valid admin JWT
    from /api/admin/login. Separate from require_auth (citizen sessions) —
    an admin JWT carries {"admin": true} instead of a pseudonymous
    identity.token, and a citizen's JWT must never pass this check even
    though both are signed with the same JWT_SECRET."""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing Authorization: Bearer <admin_token> header — "
                                      "sign in via /api/admin/login first"}), 401
        raw_token = auth_header.split(" ", 1)[1].strip()
        try:
            payload = jwt.decode(raw_token, JWT_SECRET, algorithms=["HS256"])
        except jwt.PyJWTError:
            return jsonify({"error": "Invalid or expired admin token"}), 401
        if not payload.get("admin"):
            return jsonify({"error": "This token is not an admin token"}), 403
        return view_func(*args, **kwargs)
    return wrapper

def call_deepseek(system_prompt: str, user_prompt: str, max_tokens: int = 400) -> str:
    """Single-turn chat completion call to DeepSeek's OpenAI-compatible API."""
    if not DEEPSEEK_API_KEY:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is not set. Copy .env.example to .env and add the key "
            "from the organiser email (never commit .env)."
        )

    resp = requests.post(
        f"{DEEPSEEK_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": max_tokens,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


@app.route("/")
def index():
    """
    Root now points at the new approved flow (splash.html), not the old
    3-screen hackathon demo — that demo predates the real screens built this
    session and was only ever kept for backward compatibility, not as the
    thing a fresh visit to localhost:5000 should show. The old demo is still
    reachable directly at /index.html if you specifically want it.
    """
    return send_from_directory(FRONTEND_DIR, "splash.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(FRONTEND_DIR, path)

def _reviewed_path(bill_id: str) -> Path:
    """Path to a bill's admin-review sidecar file — sits next to the bill's
    scraped JSON, e.g. data/scraped_bills/<bill_id>.reviewed.json. Keeps
    admin-verified summaries separate from the scraper's own output so
    re-running a scraper never wipes out review history."""
    return SCRAPED_BILLS_DIR / f"{bill_id}.reviewed.json"


def _load_reviewed(bill_id: str) -> dict:
    """Loads a bill's review sidecar file. Returns {} if it doesn't exist
    yet (normal for a bill nobody has summarized/reviewed)."""
    path = _reviewed_path(bill_id)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_reviewed(bill_id: str, data: dict) -> None:
    """Writes a bill's review sidecar file back to disk."""
    SCRAPED_BILLS_DIR.mkdir(parents=True, exist_ok=True)
    with open(_reviewed_path(bill_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _bill_verification_status(bill: dict) -> dict:
    """
    Checks review completeness for one bill's clauses.

    A clause counts as "needing review" if it has ever been summarized
    (i.e. it has an entry in the .reviewed.json sidecar) OR has raw_text to
    summarize at all — a clause nobody has viewed yet still needs review
    before the bill can be shown to citizens, it just hasn't been generated
    yet. rejected clauses count as NOT verified (they need a fresh AI pass).

    Returns: {
      "total_clauses": int,
      "verified_clauses": int,
      "fully_verified": bool,   # True only if every clause is verified
    }
    A bill with zero clauses (e.g. a 0-clause scrape) is never fully_verified
    — nothing to show citizens either way, but it shouldn't silently pass as
    "done" with zero real content.
    """
    clauses = bill.get("clauses", [])
    total = len(clauses)
    if total == 0:
        return {"total_clauses": 0, "verified_clauses": 0, "fully_verified": False}

    reviewed = _load_reviewed(bill["_id"])
    verified_count = 0
    for clause in clauses:
        entry = reviewed.get(clause.get("clause_id"))
        if entry and entry.get("verified"):
            verified_count += 1

    return {
        "total_clauses": total,
        "verified_clauses": verified_count,
        "fully_verified": verified_count == total,
    }

def _load_scraped_bills() -> list:
    """
    Loads every bill JSON out of data/scraped_bills/ (written by scraper.py
    and scraper_national.py). Sorted by filename for a stable, repeatable
    order across requests — not by anything meaningful about the bill itself.

    A bill missing/unreadable JSON is skipped with a log line, not allowed to
    break the whole listing — one bad scrape shouldn't take down every other
    bill's display.
    """
    if not SCRAPED_BILLS_DIR.exists():
        return []
    bills = []
    all_json_files = sorted(SCRAPED_BILLS_DIR.glob("*.json"))
    for path in [p for p in all_json_files if not p.name.endswith(".reviewed.json")]:
        raw_text = None
        # scraper.py/scraper_national.py now always write UTF-8 explicitly, but
        # files written before that fix may be in Windows' default codepage
        # (cp1252) instead — a stray em dash/curly quote from a scraped PDF is
        # enough to trigger this. Try utf-8 first (the correct, expected case),
        # fall back to cp1252, and only as a last resort force-decode with
        # replacement characters rather than take the whole endpoint down over
        # one bad file. Re-running the scraper regenerates the file correctly.
        for encoding in ("utf-8", "cp1252"):
            try:
                raw_text = path.read_bytes().decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if raw_text is None:
            print(f"[main] {path.name} isn't valid utf-8 or cp1252 — forcing a "
                  f"lossy decode. Re-run the scraper to regenerate this file properly.")
            raw_text = path.read_bytes().decode("utf-8", errors="replace")

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            print(f"[main] skipping unreadable bill file {path.name}: {exc}")
            continue
        data["_id"] = path.stem  # stable per-file id, used by ?id= below and by the frontend
        bills.append(data)
    return bills




@app.route("/api/bills", methods=["GET"])
def list_bills():
    """
    Lightweight listing for a bill-picker UI — id/title/level/status/year/
    clause count only, NOT full clause text (use /api/bill?id=... for that).

    As of the pre-publish review change: only returns bills where EVERY
    clause has been admin-verified (see _bill_verification_status above).
    A bill sits invisible to citizens the whole time it's being scraped and
    reviewed — it only appears here the moment the last clause is approved.
    This is the single filter point for that rule; admin-side endpoints
    (admin_pending_summaries, the bills-overview endpoint) intentionally
    bypass this and call _load_scraped_bills() directly, since admins need
    to see in-progress bills too.
    """
    scraped = _load_scraped_bills()
    visible = [b for b in scraped if _bill_verification_status(b)["fully_verified"]]
    return jsonify([
        {
            "id": b["_id"],
            "title": b.get("title"),
            "level": b.get("level"),
            "status": b.get("status"),
            "year": b.get("year"),
            "source_url": b.get("source_url"),
            "clause_count": len(b.get("clauses", [])),
        }
        for b in visible
    ])

@app.route("/api/bills/open", methods=["GET"])
def list_open_bills():
    """
    THE dashboard data source — the one and only place that should ever
    decide "is this bill shown as open." Every other bill-listing code path
    (list_bills() above, or anything built later) must not be trusted for
    that decision; this is the single filter point on purpose, so the rule
    can never quietly get bypassed by a second copy of the same check drifting
    out of sync.

    Filters to status == "open" AND fully_verified (see
    _bill_verification_status) — a bill only shows here once BOTH its
    participation window is confirmed live AND every one of its clauses has
    passed admin review. Right now this will almost always return an empty
    list, since status == "open" alone was already rare before this change
    (see scraper.py's and scraper_national.py's docstrings) — adding the
    verification requirement makes an empty list here even more likely
    until admins actively review scraped bills. An empty list here is the
    CORRECT, honest behaviour until both conditions are met, not a bug.
    """
    scraped = _load_scraped_bills()
    visible = [
        b for b in scraped
        if b.get("status") == "open" and _bill_verification_status(b)["fully_verified"]
    ]
    return jsonify([
        {
            "id": b["_id"],
            "title": b.get("title"),
            "level": b.get("level"),
            "year": b.get("year"),
            "opens_at": b.get("opens_at"),
            "closes_at": b.get("closes_at"),
            "source_url": b.get("source_url"),
            "clause_count": len(b.get("clauses", [])),
        }
        for b in visible
    ])

def _is_admin_request() -> bool:
    """Checks for a valid admin bearer token WITHOUT requiring one — used by
    routes like get_bill() that serve both citizens and the admin dashboard,
    where citizens get the verified-only view and admins get to see
    everything including in-progress bills. Unlike require_admin, this never
    rejects the request; it just reports true/false so the route can decide
    what to return."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False
    raw_token = auth_header.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(raw_token, JWT_SECRET, algorithms=["HS256"])
        return bool(payload.get("admin"))
    except jwt.PyJWTError:
        return False


@app.route("/api/bill", methods=["GET"])
def get_bill():
    """
    Returns one bill's full detail, including clauses.

    Query param: ?id=<id from /api/bills>. If omitted, returns the first real
    scraped bill if any exist yet, otherwise falls back to the original
    mocked sample_bill.json (flagged with "_mocked": true) so the old demo
    frontend and a fresh clone with no scraper output yet don't just break.

    Pre-publish review gate: a citizen (no admin token) requesting a bill
    that isn't fully_verified gets a 404, exactly as if the bill didn't
    exist — it genuinely shouldn't be visible to them yet. An admin token
    (see _is_admin_request) bypasses this, since the admin dashboard needs
    to show in-progress bills to review them in the first place.
    """
    bill_id = request.args.get("id")
    scraped = _load_scraped_bills()
    is_admin = _is_admin_request()

    if bill_id:
        match = next((b for b in scraped if b["_id"] == bill_id), None)
        if match is None:
            return jsonify({"error": f"No bill found with id '{bill_id}'"}), 404
        if not is_admin and not _bill_verification_status(match)["fully_verified"]:
            return jsonify({"error": f"No bill found with id '{bill_id}'"}), 404
        return jsonify(match)

    visible = scraped if is_admin else [b for b in scraped if _bill_verification_status(b)["fully_verified"]]
    if visible:
        return jsonify(visible[0])

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        bill = json.load(f)
    bill["_id"] = "mock"
    bill["_mocked"] = True
    return jsonify(bill)

def _find_clause(bill_id: str, clause_id: str) -> tuple[dict | None, dict | None]:
    """Looks up (bill, clause) by id across scraped bills — used to validate a
    vote/memorandum actually references something real before writing it,
    since clause_id/bill_id aren't real foreign keys (see db/models.py)."""
    for bill in _load_scraped_bills():
        if bill["_id"] != bill_id:
            continue
        clause = next((c for c in bill.get("clauses", []) if c.get("clause_id") == clause_id), None)
        return bill, clause
    return None, None


@app.route("/api/responses", methods=["POST"])
@require_auth
def submit_response():
    """
    Records a citizen's vote on one clause — or UPDATES their existing vote
    on that clause if they'd already voted (same token + bill_id + clause_id).

    Input:  { "bill_id": str, "clause_id": str, "vote": "kubali" | "kataa" }
    Output: { "status": "recorded" | "updated", "response_id": str }

    This used to be an unconditional INSERT — every click of Kubali/Kataa in
    clauses.html added a brand new row, even for the same person re-clicking
    the same clause. That meant no real "one vote per person" guarantee at
    all, and it silently inflated /api/analytics/constituency's counts (7
    votes from re-clicking, not 7 real people). Fixed by looking up any
    existing Response for this (token, bill_id, clause_id) first: if found,
    update its vote in place; only insert a new row if none exists. The
    Response model's UniqueConstraint (see db/models.py) backstops this at
    the database level too, so this can never silently regress.

    Requires a valid access_token (see /api/auth/verify-otp). Never touches
    phone_hash/email — only the pseudonymous token carried in the JWT.
    constituency_snapshot is copied from identity.constituency AT THIS MOMENT,
    so later analytics queries never need to join back to the identity table
    (see docs/erd-and-security.md).
    """
    if not _SessionLocal:
        return jsonify({"error": "DATABASE_URL is not configured"}), 500

    payload = request.get_json(force=True)
    bill_id = payload.get("bill_id", "")
    clause_id = payload.get("clause_id", "")
    vote = payload.get("vote", "")

    if vote not in ("kubali", "kataa"):
        return jsonify({"error": "vote must be 'kubali' or 'kataa'"}), 400

    bill, clause = _find_clause(bill_id, clause_id)
    if bill is None:
        return jsonify({"error": f"No bill found with id '{bill_id}'"}), 404
    if clause is None:
        return jsonify({"error": f"No clause '{clause_id}' found on bill '{bill_id}'"}), 404

    session = _SessionLocal()
    try:
        identity = session.query(Identity).filter_by(token=request.identity_token).first()
        existing = session.query(Response).filter_by(
            token=request.identity_token, bill_id=bill_id, clause_id=clause_id
        ).first()

        if existing:
            existing.vote = vote
            existing.constituency_snapshot = identity.constituency if identity else None
            session.commit()
            return jsonify({"status": "updated", "response_id": str(existing.id)})

        response = Response(
            token=request.identity_token,
            bill_id=bill_id,
            clause_id=clause_id,
            vote=vote,
            constituency_snapshot=identity.constituency if identity else None,
        )
        session.add(response)
        session.commit()
        return jsonify({"status": "recorded", "response_id": str(response.id)})
    finally:
        session.close()


@app.route("/api/memoranda", methods=["POST"])
@require_auth
def create_memorandum():
    """
    Drafts AND persists a memorandum from a citizen's rejected clauses —
    the real, authenticated, database-backed counterpart to the original
    /api/memorandum (singular, still kept below for the old demo frontend,
    which has no auth and doesn't save anything).

    Input:  { "bill_id": str, "rejected_clause_ids": [str, ...],
               "consent_read_summary": bool, "consent_not_bot": bool, "consent_terms": bool }
    Output: { "memorandum_id": str, "draft_text": str, "status": "draft" }

    All three consent flags must be true — this mirrors the real submission
    flow's requirement that a citizen actively confirms they read the
    summary, aren't a bot, and accept the terms before a memorandum can be
    created at all, not just before it's sent.

    One memorandum per (token, bill_id) is enforced here AND at the database
    level (see Memorandum's UniqueConstraint in db/models.py): if the citizen
    already has a SENT memorandum for this bill, this returns 409 rather than
    creating a duplicate — you can send one memorandum to Parliament/a county
    assembly per bill, not several. If they have a still-in-progress DRAFT
    for this bill (never marked sent), that existing row is updated in place
    instead — redrafting/editing before you actually send is not penalised,
    only sending twice is.
    """
    if not _SessionLocal:
        return jsonify({"error": "DATABASE_URL is not configured"}), 500

    payload = request.get_json(force=True)
    bill_id = payload.get("bill_id", "")
    rejected_ids = payload.get("rejected_clause_ids", [])
    consents = (payload.get("consent_read_summary"), payload.get("consent_not_bot"), payload.get("consent_terms"))

    if not all(consents):
        return jsonify({"error": "consent_read_summary, consent_not_bot, and consent_terms must all be true"}), 400

    bill = next((b for b in _load_scraped_bills() if b["_id"] == bill_id), None)
    if bill is None:
        return jsonify({"error": f"No bill found with id '{bill_id}'"}), 404

    rejected_clauses = [c for c in bill.get("clauses", []) if c.get("clause_id") in rejected_ids]
    if not rejected_clauses:
        return jsonify({"error": "No matching clauses found for the given rejected_clause_ids"}), 400

    session = _SessionLocal()
    existing = session.query(Memorandum).filter_by(token=request.identity_token, bill_id=bill_id).first()
    if existing and existing.status == "sent":
        session.close()
        return jsonify({
            "error": "You have already submitted a memorandum for this bill.",
            "memorandum_id": str(existing.id),
            "sent_at": existing.sent_at.isoformat() if existing.sent_at else None,
        }), 409

    system_prompt = (
        "You draft short, respectful citizen memoranda objecting to specific clauses "
        "of a Kenyan bill, for submission to Parliament or a county assembly. "
        "Write 2-3 sentences per clause, plain English, no legal jargon."
    )
    clause_list = "\n".join(f"- Clause {c.get('clause_number')}: {c.get('raw_text')}" for c in rejected_clauses)
    user_prompt = (
        f"Bill: {bill.get('title')}\n"
        f"Clauses the citizen objects to:\n{clause_list}\n"
        "Draft a short memorandum a citizen could submit, objecting to these clauses."
    )

    try:
        draft_text = call_deepseek(system_prompt, user_prompt, max_tokens=700)
    except Exception:
        draft_text = (
            f"[AI call failed — draft manually] Objection to {bill.get('title')}:\n"
            + "\n".join(f"- I object to the clause on {c.get('clause_number')}." for c in rejected_clauses)
        )

    # A judge reviewing this build (Rose, via Catherine's July 27 email) flagged
    # that memoranda without a real name/email read as anonymous form
    # submissions and risk being dismissed as spam rather than taken as
    # genuine citizen input. Baking a placeholder signature straight into the
    # draft — rather than adding a separate name field/state — means the
    # citizen sees it the moment the draft loads in the already-editable
    # textarea on memo.html and naturally replaces it before sending. This
    # does NOT get stored anywhere tied to the pseudonymous token; it only
    # ever lives in the text the citizen types into their own outgoing email.
    draft_text = draft_text.rstrip() + "\n\nSincerely,\n[Your name]"

    try:
        if existing:
            # Still a draft (the "sent" case already returned above) — update
            # it in place rather than inserting a second row, since the
            # UniqueConstraint on (token, bill_id) would reject a duplicate
            # insert anyway. This lets a citizen re-vote/redraft before
            # sending without being penalised for changing their mind.
            existing.draft_text = draft_text
            existing.consent_read_summary = True
            existing.consent_not_bot = True
            existing.consent_terms = True
            session.commit()
            return jsonify({"memorandum_id": str(existing.id), "draft_text": draft_text, "status": "draft"})

        memo = Memorandum(
            token=request.identity_token,
            bill_id=bill_id,
            draft_text=draft_text,
            consent_read_summary=True,
            consent_not_bot=True,
            consent_terms=True,
            status="draft",
        )
        session.add(memo)
        session.commit()
        return jsonify({"memorandum_id": str(memo.id), "draft_text": draft_text, "status": "draft"})
    finally:
        session.close()


@app.route("/api/memoranda/<memorandum_id>/mark-sent", methods=["POST"])
@require_auth
def mark_memorandum_sent(memorandum_id):
    """
    Marks a memorandum as sent, once the citizen has actually clicked through
    the mailto: link in their own email client (see index.html's sendMemo()).
    This does NOT send the email itself — Sheria Yangu has never done that;
    it opens the user's own mail client. This just records that they did.

    Input:  { "edited_text": str (optional) } — if the user edited the AI
             draft before sending, save what they actually sent.
    Output: { "status": "sent" }
    """
    if not _SessionLocal:
        return jsonify({"error": "DATABASE_URL is not configured"}), 500

    try:
        memorandum_uuid = uuid.UUID(memorandum_id)
    except ValueError:
        return jsonify({"error": f"'{memorandum_id}' is not a valid memorandum id"}), 400

    payload = request.get_json(silent=True) or {}
    session = _SessionLocal()
    try:
        memo = session.query(Memorandum).filter_by(id=memorandum_uuid, token=request.identity_token).first()
        if memo is None:
            return jsonify({"error": "No memorandum found with that id for this account"}), 404
        if payload.get("edited_text"):
            memo.edited_text = payload["edited_text"]
        memo.status = "sent"
        memo.sent_at = datetime.now()
        session.commit()
        return jsonify({"status": "sent"})
    finally:
        session.close()


@app.route("/api/summarize", methods=["POST"])
def summarize_clause():
    """
    Input:  { "clause_id": str, "raw_text": str, "affected_group": str, "bill_id": str }
    Output: { "clause_id": str, "summary_en": str, "summary_sw": str, "verified": bool }

    If bill_id is provided and this clause already has an admin-verified
    summary in data/scraped_bills/<bill_id>.reviewed.json, that verified
    version is returned directly and DeepSeek is never called — this is
    what makes admin corrections actually take effect for citizens.

    Otherwise, DeepSeek is called as before, and the fresh result is saved
    to the sidecar file as verified: false, so it shows up in the admin
    review queue. If bill_id is missing (shouldn't happen from clauses.html
    after this change, but keeps old callers like test_summarize.py and
    index.html working), summarization still works, it just isn't saved
    for review.
    """
    
    payload = request.get_json(force=True)
    clause_id = payload.get("clause_id", "")
    raw_text = payload.get("raw_text", "")
    affected_group = payload.get("affected_group", "the public")
    bill_id = payload.get("bill_id", "")

    if bill_id and clause_id:
        reviewed = _load_reviewed(bill_id)
        entry = reviewed.get(clause_id)
        if entry and entry.get("verified"):
            return jsonify({
                "clause_id": clause_id,
                "summary_en": entry.get("summary_en", ""),
                "summary_sw": entry.get("summary_sw", ""),
                "verified": True,
            })

    # Loosened from the original hackathon-demo version, which forced exactly
    # one 30-word sentence per language — fine for the short demo bill, but
    # real bill clauses (some 1500+ characters, dense legal/financial detail)
    # lose meaning when compressed that hard. Now allows up to 3 sentences,
    # ~90 words, per language — still a real simplification, not a rewrite of
    # the clause, but with room for "what it says" + "who it affects" + "what
    # changes for them" as three distinct, short sentences instead of one
    # over-compressed one. Re-verify actual output against real scraped
    # clauses (not just the demo bill) before trusting this for the pitch —
    # DeepSeek doesn't always respect a word cap exactly.
    system_prompt = (
        "You simplify Kenyan legislative clauses for ordinary citizens, especially "
        "people with no legal background. Given a clause of a bill, respond with "
        "EXACTLY two lines, no preamble, no markdown formatting:\n"
        "EN: <up to 3 short plain-English sentences (about 90 words total) covering: "
        "what this clause actually says, who it affects, and what concretely changes "
        "for the named group. Avoid legal jargon; explain any term you must use.>\n"
        "SW: <the same explanation in plain Kiswahili, same length limit>"
    )
    user_prompt = (
        f"Clause text: {raw_text}\n"
        f"Group most affected: {affected_group}\n"
        "Simplify this clause for someone with no legal training."
    )
    try:
        raw_response = call_deepseek(system_prompt, user_prompt, max_tokens=700)
        summary_en, summary_sw = "", ""
        for line in raw_response.splitlines():
            if line.strip().upper().startswith("EN:"):
                summary_en = line.split(":", 1)[1].strip()
            elif line.strip().upper().startswith("SW:"):
                summary_sw = line.split(":", 1)[1].strip()
        if not summary_en or not summary_sw:
            # Model didn't follow the format — fall back to raw response for EN
            summary_en = summary_en or raw_response
            summary_sw = summary_sw or "(Tafsiri haikupatikana)"

        if bill_id and clause_id:
            reviewed = _load_reviewed(bill_id)
            reviewed[clause_id] = {
                "summary_en": summary_en,
                "summary_sw": summary_sw,
                "raw_text": raw_text,
                "verified": False,
                "verified_by": None,
                "verified_at": None,
            }
            _save_reviewed(bill_id, reviewed)

        return jsonify({
            "clause_id": clause_id,
            "summary_en": summary_en,
            "summary_sw": summary_sw,
            "verified": False,
        })
    except Exception as exc:  # keep the demo alive even if the API call fails
        return jsonify({
            "clause_id": clause_id,
            "summary_en": f"[AI call failed, showing raw clause] {raw_text}",
            "summary_sw": "[Ombi la AI limeshindwa]",
            "error": str(exc),
        }), 200

@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    """
    Input:  { "password": str }
    Output: { "access_token": <JWT with admin:true claim>, "token_type": "bearer" }

    Single shared admin password for hackathon scope — see ADMIN_PASSWORD in
    .env. Not per-admin accounts; that's a real nice-to-have, not required
    for finals (see docs/admin-review-spec.md).
    """
    if not ADMIN_PASSWORD:
        return jsonify({"error": "ADMIN_PASSWORD is not configured — set it in .env"}), 500
    if not JWT_SECRET:
        return jsonify({"error": "JWT_SECRET is not configured"}), 500

    payload = request.get_json(force=True)
    password = payload.get("password", "")
    if password != ADMIN_PASSWORD:
        return jsonify({"error": "Incorrect admin password"}), 401

    access_token = jwt.encode(
        {"admin": True, "exp": datetime.now() + timedelta(hours=8)},
        JWT_SECRET, algorithm="HS256",
    )
    return jsonify({"access_token": access_token, "token_type": "bearer"})


@app.route("/api/admin/summaries/pending", methods=["GET"])
@require_admin
def admin_pending_summaries():
    """
    Returns every clause across every bill whose summary hasn't been
    reviewed yet (verified == false in its .reviewed.json sidecar).

    Output: [ { "bill_id": str, "bill_title": str, "clause_id": str,
                "clause_number": str|None, "raw_text": str,
                "summary_en": str, "summary_sw": str, "source_url": str|None }, ... ]
    """
    pending = []
    for bill in _load_scraped_bills():
        bill_id = bill["_id"]
        reviewed = _load_reviewed(bill_id)
        clauses_by_id = {c.get("clause_id"): c for c in bill.get("clauses", [])}
        for clause_id, entry in reviewed.items():
            if entry.get("verified") or entry.get("rejected"):
                continue
            clause = clauses_by_id.get(clause_id, {})
            pending.append({
                "bill_id": bill_id,
                "bill_title": bill.get("title", bill_id),
                "clause_id": clause_id,
                "clause_number": clause.get("clause_number"),
                "raw_text": entry.get("raw_text", clause.get("raw_text", "")),
                "summary_en": entry.get("summary_en", ""),
                "summary_sw": entry.get("summary_sw", ""),
                "source_url": bill.get("source_url"),
            })
    return jsonify(pending)


@app.route("/api/admin/summaries/<bill_id>/<clause_id>/review", methods=["POST"])
@require_admin
def admin_review_summary(bill_id, clause_id):
    """
    Input:  { "decision": "approve" | "reject" | "edit",
              "corrected_summary_en": str (required if decision == "edit"),
              "corrected_summary_sw": str (required if decision == "edit"),
              "note": str (optional) }
    Output: { "status": "verified" | "rejected", "clause_id": str, "bill_id": str }

    approve: marks the existing DeepSeek summary verified as-is.
    edit:    saves the admin's corrected text, marks it verified — this is
             what makes a fix actually reach citizens (see the verified-check
             at the top of /api/summarize).
    reject:  marks it rejected (verified stays false, but flagged so it's
             excluded from the pending queue and from being served to
             citizens) — this clause needs re-summarizing before anyone
             sees it again. Deleting the entry entirely would just cause it
             to regenerate identically next time someone views the clause,
             so a "rejected" flag is used instead of a delete.
    """
    payload = request.get_json(force=True)
    decision = payload.get("decision", "")
    if decision not in ("approve", "reject", "edit"):
        return jsonify({"error": "decision must be 'approve', 'reject', or 'edit'"}), 400

    reviewed = _load_reviewed(bill_id)
    entry = reviewed.get(clause_id)
    if entry is None:
        return jsonify({"error": f"No pending summary found for bill '{bill_id}' clause '{clause_id}'"}), 404

    if decision == "edit":
        corrected_en = payload.get("corrected_summary_en", "")
        corrected_sw = payload.get("corrected_summary_sw", "")
        if not corrected_en or not corrected_sw:
            return jsonify({"error": "corrected_summary_en and corrected_summary_sw are required for an edit"}), 400
        entry["summary_en"] = corrected_en
        entry["summary_sw"] = corrected_sw
        entry["verified"] = True
        entry["verified_by"] = "admin"
        entry["verified_at"] = datetime.now().isoformat()
        entry["note"] = payload.get("note")
        status = "verified"
    elif decision == "approve":
        entry["verified"] = True
        entry["verified_by"] = "admin"
        entry["verified_at"] = datetime.now().isoformat()
        entry["note"] = payload.get("note")
        status = "verified"
    else:  # reject
        entry["verified"] = False
        entry["rejected"] = True
        entry["verified_by"] = "admin"
        entry["verified_at"] = datetime.now().isoformat()
        entry["note"] = payload.get("note")
        status = "rejected"

    reviewed[clause_id] = entry
    _save_reviewed(bill_id, reviewed)
    return jsonify({"status": status, "clause_id": clause_id, "bill_id": bill_id})

@app.route("/api/admin/bills/<bill_id>/generate-summaries", methods=["POST"])
@require_admin
def admin_generate_summaries(bill_id):
    """
    Proactively summarizes every clause of one bill that doesn't already
    have a summary — this is the "review before publish" trigger. Without
    this, a clause only ever gets summarized reactively (someone has to
    view it first), which doesn't work now that citizens can't see a bill
    until every clause is verified: nobody would ever generate the first
    draft for the admin to review. An admin clicks this right after a bill
    is scraped, populating the whole pending queue for that bill at once.

    Skips any clause that already has an entry in the sidecar (verified,
    rejected, or still pending) — safe to click more than once, it only
    fills in genuine gaps rather than re-summarizing everything each time.

    Output: { "bill_id": str, "generated": int, "skipped": int,
              "total_clauses": int }
    generated = clauses that got a fresh DeepSeek call this run.
    skipped   = clauses that already had an entry (any status) and were left alone.
    """
    scraped = _load_scraped_bills()
    bill = next((b for b in scraped if b["_id"] == bill_id), None)
    if bill is None:
        return jsonify({"error": f"No bill found with id '{bill_id}'"}), 404

    clauses = bill.get("clauses", [])
    reviewed = _load_reviewed(bill_id)
    generated = 0
    skipped = 0

    system_prompt = (
        "You simplify Kenyan legislative clauses for ordinary citizens, especially "
        "people with no legal background. Given a clause of a bill, respond with "
        "EXACTLY two lines, no preamble, no markdown formatting:\n"
        "EN: <up to 3 short plain-English sentences (about 90 words total) covering: "
        "what this clause actually says, who it affects, and what concretely changes "
        "for the named group. Avoid legal jargon; explain any term you must use.>\n"
        "SW: <the same explanation in plain Kiswahili, same length limit>"
    )

    for clause in clauses:
        clause_id = clause.get("clause_id")
        if not clause_id or clause_id in reviewed:
            skipped += 1
            continue

        raw_text = clause.get("raw_text", "")
        user_prompt = (
            f"Clause text: {raw_text}\n"
            "Group most affected: the public\n"
            "Simplify this clause for someone with no legal training."
        )
        try:
            raw_response = call_deepseek(system_prompt, user_prompt, max_tokens=700)
            summary_en, summary_sw = "", ""
            for line in raw_response.splitlines():
                if line.strip().upper().startswith("EN:"):
                    summary_en = line.split(":", 1)[1].strip()
                elif line.strip().upper().startswith("SW:"):
                    summary_sw = line.split(":", 1)[1].strip()
            if not summary_en or not summary_sw:
                summary_en = summary_en or raw_response
                summary_sw = summary_sw or "(Tafsiri haikupatikana)"
        except Exception as exc:
            summary_en = f"[AI call failed, showing raw clause] {raw_text}"
            summary_sw = "[Ombi la AI limeshindwa]"

        reviewed[clause_id] = {
            "summary_en": summary_en,
            "summary_sw": summary_sw,
            "raw_text": raw_text,
            "verified": False,
            "verified_by": None,
            "verified_at": None,
        }
        generated += 1

    _save_reviewed(bill_id, reviewed)
    return jsonify({
        "bill_id": bill_id,
        "generated": generated,
        "skipped": skipped,
        "total_clauses": len(clauses),
    })

@app.route("/api/admin/bills", methods=["GET"])
@require_admin
def admin_bills_overview():
    """
    Admin-only bird's-eye view of every scraped bill and its review
    progress — lets an admin see at a glance which bills still need work,
    and is the natural entry point for triggering
    admin_generate_summaries() on a bill that hasn't been touched yet.

    Unlike list_bills()/list_open_bills(), this deliberately shows EVERY
    scraped bill regardless of verification status — an admin needs to see
    in-progress bills specifically, since that's the whole point of this
    view.

    Output: [ { "bill_id": str, "title": str, "level": str|None,
                "status": str, "source_url": str|None,
                "total_clauses": int, "verified_clauses": int,
                "fully_verified": bool }, ... ]
    Sorted so bills needing the most attention (least reviewed, as a
    fraction) show up first — a freshly scraped bill with 0 of 12 clauses
    reviewed surfaces above one sitting at 2 of 3.
    """
    bills = _load_scraped_bills()
    result = []
    for bill in bills:
        vstatus = _bill_verification_status(bill)
        result.append({
            "bill_id": bill["_id"],
            "title": bill.get("title", bill["_id"]),
            "level": bill.get("level"),
            "status": bill.get("status"),
            "source_url": bill.get("source_url"),
            "total_clauses": vstatus["total_clauses"],
            "verified_clauses": vstatus["verified_clauses"],
            "fully_verified": vstatus["fully_verified"],
        })

    def _progress_fraction(item):
        if item["total_clauses"] == 0:
            return 1.0  # nothing to review — sorts last, not first
        return item["verified_clauses"] / item["total_clauses"]

    result.sort(key=_progress_fraction)
    return jsonify(result)

@app.route("/api/auth/request-otp", methods=["POST"])
def request_otp():
    """
    Input:  { "phone_number": "+2547...", "constituency": str (optional),
              "notify_sms": bool (optional), "notify_email": bool (optional) }
    Output: { "status": "otp_sent" }
            (+ "dev_otp_code" ONLY when SMS_DEV_MODE=true in .env — lets you
            test the whole register/verify flow without a working SMS
            connection. Must never be true in a real deployment.)

    Creates the identity row on first sign-in (phone_hash only — see
    docs/erd-and-security.md), or reuses the existing one on repeat sign-ins.
    Either way, a fresh OTP is generated and its HASH (never the code itself)
    is stored with an expiry, then the code is sent by SMS (or, in dev mode,
    skipped and returned directly for testing).
    """
    if not _SessionLocal:
        return jsonify({"error": "DATABASE_URL is not configured — see docs/postgres-setup.md"}), 500

    payload = request.get_json(force=True)
    phone_number = payload.get("phone_number", "").strip()
    if not phone_number:
        return jsonify({"error": "phone_number is required"}), 400

    phone_hash = hash_phone(phone_number)
    session = _SessionLocal()
    try:
        identity = session.query(Identity).filter_by(phone_hash=phone_hash).first()
        if identity is None:
            identity = Identity(
                phone_hash=phone_hash,
                constituency=payload.get("constituency"),
                notify_sms=bool(payload.get("notify_sms", True)),
                notify_email=bool(payload.get("notify_email", False)),
            )
            session.add(identity)

        if SMS_DEV_MODE:
            code = sms.generate_otp()
            expires_at = datetime.now() + timedelta(minutes=sms.OTP_VALID_MINUTES)
        else:
            issued = sms.issue_otp(phone_number)  # actually sends the SMS
            code, expires_at = issued.code, issued.expires_at

        identity.otp_hash = hash_otp(code)
        identity.otp_expires_at = expires_at
        session.commit()

        response = {"status": "otp_sent"}
        if SMS_DEV_MODE:
            response["dev_otp_code"] = code
        return jsonify(response)
    finally:
        session.close()


@app.route("/api/auth/verify-otp", methods=["POST"])
def verify_otp():
    """
    Input:  { "phone_number": "+2547...", "code": "123456" }
    Output: { "access_token": <JWT>, "token_type": "bearer" }

    access_token is a signed JWT (session auth — proves "this request comes
    from a verified session") that the client attaches to future requests.
    It carries the pseudonymous identity.token, NOT the phone number or
    phone_hash, so nothing downstream that reads this JWT ever needs to
    touch the identity table again for routine requests.
    """
    if not _SessionLocal:
        return jsonify({"error": "DATABASE_URL is not configured — see docs/postgres-setup.md"}), 500
    if not JWT_SECRET:
        return jsonify({"error": "JWT_SECRET is not configured"}), 500

    payload = request.get_json(force=True)
    phone_number = payload.get("phone_number", "").strip()
    code = payload.get("code", "").strip()
    if not phone_number or not code:
        return jsonify({"error": "phone_number and code are required"}), 400

    phone_hash = hash_phone(phone_number)
    session = _SessionLocal()
    try:
        identity = session.query(Identity).filter_by(phone_hash=phone_hash).first()
        if identity is None or not identity.otp_hash:
            return jsonify({"error": "No pending OTP for this number — request one first"}), 401
        if identity.otp_expires_at is None or datetime.now() > identity.otp_expires_at:
            return jsonify({"error": "OTP has expired — request a new one"}), 401
        if hash_otp(code) != identity.otp_hash:
            return jsonify({"error": "Incorrect code"}), 401

        identity.verified = True
        identity.otp_hash = None
        identity.otp_expires_at = None
        session.commit()

        access_token = jwt.encode(
            {"token": str(identity.token), "exp": datetime.now() + timedelta(days=30)},
            JWT_SECRET, algorithm="HS256",
        )
        return jsonify({"access_token": access_token, "token_type": "bearer"})
    finally:
        session.close()


@app.route("/api/me", methods=["GET"])
@require_auth
def get_me():
    """
    Returns the signed-in identity's own self-reported settings — never a
    phone number or phone_hash, since the frontend only ever holds the JWT
    (which carries identity.token, not phone_hash). Used by settings.html to
    pre-fill the current constituency/notification toggles.

    Output: { "constituency": str|None, "notify_sms": bool, "notify_email": bool, "verified": bool }
    """
    if not _SessionLocal:
        return jsonify({"error": "DATABASE_URL is not configured"}), 500

    session = _SessionLocal()
    try:
        identity = session.query(Identity).filter_by(token=request.identity_token).first()
        if identity is None:
            return jsonify({"error": "Identity not found for this session"}), 404
        return jsonify({
            "constituency": identity.constituency,
            "notify_sms": identity.notify_sms,
            "notify_email": identity.notify_email,
            "verified": identity.verified,
        })
    finally:
        session.close()


@app.route("/api/me", methods=["PATCH"])
@require_auth
def update_me():
    """
    Lets a signed-in user update their own self-reported constituency and
    notification preferences. constituency stays self-reported/unverified —
    see docs/erd-and-security.md's "Constituency — self-reported or verified?"
    section for why that's a deliberate choice, not a gap to close later.

    Input (all optional):
      { "constituency": str, "notify_sms": bool, "notify_email": bool }
    Output: { "status": "updated", ...same shape as GET /api/me }
    """
    if not _SessionLocal:
        return jsonify({"error": "DATABASE_URL is not configured"}), 500

    payload = request.get_json(force=True)
    session = _SessionLocal()
    try:
        identity = session.query(Identity).filter_by(token=request.identity_token).first()
        if identity is None:
            return jsonify({"error": "Identity not found for this session"}), 404

        if "constituency" in payload:
            identity.constituency = payload["constituency"] or None
        if "notify_sms" in payload:
            identity.notify_sms = bool(payload["notify_sms"])
        if "notify_email" in payload:
            identity.notify_email = bool(payload["notify_email"])

        session.commit()
        return jsonify({
            "status": "updated",
            "constituency": identity.constituency,
            "notify_sms": identity.notify_sms,
            "notify_email": identity.notify_email,
            "verified": identity.verified,
        })
    finally:
        session.close()


@app.route("/api/me/activity", methods=["GET"])
@require_auth
def get_my_activity():
    """
    The signed-in citizen's OWN votes and memoranda — the "see my data" view
    (profile.html), distinct from settings.html's editable preferences.
    Scoped strictly to request.identity_token; never touches phone_hash/email.

    Output: {
      "responses": [ { "bill_id", "bill_title", "clause_id", "vote", "created_at" }, ... ],
      "memoranda": [ { "memorandum_id", "bill_id", "bill_title", "status", "sent_at" }, ... ]
    }
    """
    if not _SessionLocal:
        return jsonify({"error": "DATABASE_URL is not configured"}), 500

    session = _SessionLocal()
    try:
        responses = session.query(Response).filter_by(token=request.identity_token).order_by(Response.created_at.desc()).all()
        memoranda = session.query(Memorandum).filter_by(token=request.identity_token).order_by(Memorandum.id.desc()).all()
    finally:
        session.close()

    bills_by_id = {b["_id"]: b for b in _load_scraped_bills()}

    return jsonify({
        "responses": [
            {
                "bill_id": r.bill_id,
                "bill_title": bills_by_id.get(r.bill_id, {}).get("title", r.bill_id),
                "clause_id": r.clause_id,
                "vote": r.vote,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in responses
        ],
        "memoranda": [
            {
                "memorandum_id": str(m.id),
                "bill_id": m.bill_id,
                "bill_title": bills_by_id.get(m.bill_id, {}).get("title", m.bill_id),
                "status": m.status,
                "sent_at": m.sent_at.isoformat() if m.sent_at else None,
            }
            for m in memoranda
        ],
    })


@app.route("/api/analytics/bills", methods=["GET"])
def analytics_bills_list():
    """
    Lists every bill that has at least one recorded vote, with its vote
    count — feeds the bill picker on analytics.html so county participation
    can be shown PER BILL instead of one combined blob (which was the
    original gap: the first version of /api/analytics/constituency mixed
    every bill's votes together with no way to tell them apart).

    Output: [ { "bill_id": str, "title": str, "level": str|None, "vote_count": int }, ... ]
    (desc by vote_count)

    vote_count is DISTINCT PARTICIPANTS (unique tokens), not raw response
    rows. It used to be COUNT(responses.id) — which counts one row per
    clause someone voted on, so a single citizen voting on all 3 clauses of
    a bill showed up as "3 votes," reading exactly like 3 different people
    had participated. Fixed to COUNT(DISTINCT token) so this reflects real
    participants, matching what "how many people voted on this bill" should
    actually mean.
    """
    if not _SessionLocal:
        return jsonify({"error": "DATABASE_URL is not configured"}), 500

    session = _SessionLocal()
    try:
        rows = (
            session.query(Response.bill_id, func.count(func.distinct(Response.token)))
            .group_by(Response.bill_id)
            .order_by(func.count(func.distinct(Response.token)).desc())
            .all()
        )
    finally:
        session.close()

    bills_by_id = {b["_id"]: b for b in _load_scraped_bills()}
    result = []
    for bill_id, count in rows:
        bill = bills_by_id.get(bill_id, {})
        result.append({
            "bill_id": bill_id,
            "title": bill.get("title", bill_id),
            "level": bill.get("level"),
            "vote_count": count,
        })
    return jsonify(result)


@app.route("/api/analytics/constituency", methods=["GET"])
def analytics_by_constituency():
    """
    THE county analytics data source (see docs/erd-and-security.md, "the
    analytics dashboard should show that a verified person participated, but
    not who"). Reads ONLY responses.constituency_snapshot — a self-reported,
    point-in-time copy taken when someone voted — and NEVER queries the
    identity table. No phone number, email, or token ever appears in this
    response. No auth required: this is aggregate, non-identifying data.

    constituency_snapshot is self-reported and unverified against the voter
    roll (see the same doc) — the counts below reflect what people typed in,
    not confirmed residency.

    Query param: ?bill_id=<id from /api/analytics/bills> — filters to just
    that bill's votes. Omit it to get every bill's votes combined (the
    original behaviour); analytics.html always passes a specific bill_id
    once the user picks one from the selector, so this stays opt-in rather
    than a breaking change.

    Output: {
      "bill_id": str|None,
      "total_responses": int,
      "by_constituency": [ { "constituency": str|"Unreported", "count": int }, ... ]  (desc by count)
    }

    count is DISTINCT PARTICIPANTS per constituency (unique tokens), not raw
    response rows — same fix as analytics_bills_list() above, and for the
    same reason: one citizen voting on multiple clauses of a bill must not
    inflate that constituency's count past the number of real people who
    actually took part.
    """
    if not _SessionLocal:
        return jsonify({"error": "DATABASE_URL is not configured"}), 500

    bill_id = request.args.get("bill_id")
    session = _SessionLocal()
    try:
        query = session.query(Response.constituency_snapshot, func.count(func.distinct(Response.token)))
        if bill_id:
            query = query.filter(Response.bill_id == bill_id)
        rows = query.group_by(Response.constituency_snapshot).order_by(
            func.count(func.distinct(Response.token)).desc()
        ).all()
        by_constituency = [
            {"constituency": constituency or "Unreported", "count": count}
            for constituency, count in rows
        ]
        total = sum(r["count"] for r in by_constituency)
        return jsonify({"bill_id": bill_id, "total_responses": total, "by_constituency": by_constituency})
    finally:
        session.close()


@app.route("/api/memorandum", methods=["POST"])
def compile_memorandum():
    """
    Input:  { "bill_title": str, "rejected_clauses": [ { "title": str, "raw_text": str } ] }
    Output: { "memorandum_text": str }
    """
    payload = request.get_json(force=True)
    bill_title = payload.get("bill_title", "the Bill")
    rejected = payload.get("rejected_clauses", [])

    if not rejected:
        return jsonify({"memorandum_text": "No clauses were rejected — no memorandum needed."})

    system_prompt = (
        "You draft short, respectful citizen memoranda objecting to specific clauses "
        "of a Kenyan bill, for submission to Parliament or a county assembly. "
        "Write 2-3 sentences per clause, plain English, no legal jargon."
    )
    clause_list = "\n".join(f"- {c.get('title')}: {c.get('raw_text')}" for c in rejected)
    user_prompt = (
        f"Bill: {bill_title}\n"
        f"Clauses the citizen objects to:\n{clause_list}\n"
        "Draft a short memorandum a citizen could submit, objecting to these clauses."
    )

    try:
        memo = call_deepseek(system_prompt, user_prompt)
    except Exception:
        memo = (
            f"[AI call failed — draft manually] Objection to {bill_title}:\n"
            + "\n".join(f"- I object to the clause on {c.get('title')}." for c in rejected)
        )
    return jsonify({"memorandum_text": memo})


@app.route("/api/sms/inbound", methods=["POST"])
def sms_inbound():
    """
    Receives inbound Two-Way SMS for this project, forwarded from KamiLimu's
    shared Africa's Talking gateway (shortcode 20880, keyword "kamilimu").

    How the routing works: users text the shared shortcode, e.g.
    "kamilimu sheriayangu <message>". Africa's Talking sends that to a single
    central callback that Mark Tanui controls, which then re-POSTs it to
    *this* URL — only messages meant for this project ever arrive here. This
    endpoint does not do the "kamilimu <project>" parsing itself; that
    happens upstream, before we ever see the request.

    STUB — logs and 200s, nothing else yet. What this repo doesn't have a
    decided answer for: what should happen when a real user texts back? Reply
    with their vote on the last clause they were notified about? Unsubscribe?
    Something else? That's a product decision, not a code one — don't wire up
    real behaviour here until Catherine/the team decides what an inbound
    reply is supposed to *do*. Until then this just proves the plumbing
    works, so a callback URL can be registered with Mark today.

    Payload shape is a guess, matching Africa's Talking's normal incoming-SMS
    webhook fields (from, to, text, date, id, linkId) — Mark's re-POST may or
    may not preserve these exactly. First real message that arrives should be
    checked against request.form (see the log line below) and this docstring
    updated once we know for sure.
    """
    data = request.form.to_dict() or request.get_json(silent=True) or {}
    print(f"[sms_inbound] raw payload received: {data}")

    sender = data.get("from", "unknown")
    text = data.get("text", "")
    print(f"[sms_inbound] from={sender!r} text={text!r}")

    # Africa's Talking (and presumably Mark's re-POST) expects a 200 with an
    # empty/plain body to acknowledge receipt — returning JSON here is not
    # required by the spec but doesn't hurt; keep it minimal either way.
    return "", 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)
