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

import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "sample_bill.json"
FRONTEND_DIR = BASE_DIR / "src" / "static"

app = Flask(__name__, static_folder=None)


def call_deepseek(system_prompt: str, user_prompt: str) -> str:
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
            "max_tokens": 400,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(FRONTEND_DIR, path)


@app.route("/api/bill", methods=["GET"])
def get_bill():
    """Returns the (mocked) bill currently open for public participation."""
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        bill = json.load(f)
    return jsonify(bill)


@app.route("/api/summarize", methods=["POST"])
def summarize_clause():
    """
    Input:  { "clause_id": str, "raw_text": str, "affected_group": str }
    Output: { "clause_id": str, "summary_en": str, "summary_sw": str }
    """
    payload = request.get_json(force=True)
    clause_id = payload.get("clause_id", "")
    raw_text = payload.get("raw_text", "")
    affected_group = payload.get("affected_group", "the public")

    system_prompt = (
        "You simplify Kenyan legislative clauses for ordinary citizens. "
        "Given a clause of a bill, respond with EXACTLY two lines, no preamble:\n"
        "EN: <one plain-English sentence, max 30 words, explaining what this clause "
        "means and how it affects the named group>\n"
        "SW: <the same explanation in plain Kiswahili, max 30 words>"
    )
    user_prompt = (
        f"Clause text: {raw_text}\n"
        f"Group most affected: {affected_group}\n"
        "Simplify this clause."
    )

    try:
        raw_response = call_deepseek(system_prompt, user_prompt)
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
        return jsonify({"clause_id": clause_id, "summary_en": summary_en, "summary_sw": summary_sw})
    except Exception as exc:  # keep the demo alive even if the API call fails
        return jsonify({
            "clause_id": clause_id,
            "summary_en": f"[AI call failed, showing raw clause] {raw_text}",
            "summary_sw": "[Ombi la AI limeshindwa]",
            "error": str(exc),
        }), 200


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


if __name__ == "__main__":
    app.run(debug=True, port=5000)
