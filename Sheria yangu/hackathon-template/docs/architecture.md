# Architecture & Data Schema — Sheria Yangu

## End-to-end flow

```
[User: Web App]                 [Backend: Flask]                [AI Module: DeepSeek API]
       |                               |                                  |
       |  1. Open app                  |                                  |
       |------------------------------>|                                  |
       |          GET /api/bill        |                                  |
       |<------------------------------|  (reads data/sample_bill.json)   |
       |  shows notification + clauses |                                  |
       |                               |                                  |
       |  2. For each clause           |                                  |
       |------------------------------>|                                  |
       |     POST /api/summarize       |  system+user prompt              |
       |      {clause_id, raw_text,    |--------------------------------->|
       |       affected_group}         |                                  |
       |                               |  {summary_en, summary_sw}        |
       |<------------------------------|<---------------------------------|
       |  shows EN + SW summaries      |                                  |
       |                               |                                  |
       |  3. User taps Kubali/Kataa    |                                  |
       |     per clause (client-side)  |                                  |
       |                               |                                  |
       |  4. Review memorandum         |                                  |
       |------------------------------>|                                  |
       |    POST /api/memorandum       |  system+user prompt              |
       |     {bill_title,              |--------------------------------->|
       |      rejected_clauses[]}      |                                  |
       |                               |  {memorandum_text}               |
       |<------------------------------|<---------------------------------|
       |  shows editable draft         |                                  |
       |                               |                                  |
       |  5. User taps "Send"          |                                  |
       |  -> mailto: link opens        |                                  |
       |     (no server round-trip)    |                                  |
```

## What is built vs. mocked today

| Component | Status | Notes |
|---|---|---|
| Web app frontend (notification, clause vote, memorandum screens) | **Built** | `src/static/index.html`, runs on localhost |
| Flask backend + API routes | **Built** | `src/main.py` |
| Clause simplification (English + Swahili) via DeepSeek | **Built** | Live call to DeepSeek chat completions API; falls back to raw clause text if the call fails, so the demo never breaks |
| Memorandum auto-drafting via DeepSeek | **Built** | Live call; falls back to a templated objection list if the call fails |
| Bill content (Nairobi Finance Bill clauses) | **Mocked** | Hardcoded in `data/sample_bill.json`, modeled on the real, court-nullified Nairobi City County Finance Act 2023 — not pulled live from Kenya Law or the county assembly site |
| Sending the memorandum to Parliament/county assembly | **Mocked** | Opens a `mailto:` draft in the user's own email client; does not actually transmit anything server-side |
| Push notification | **Mocked** | Simulated as the first screen the user sees on opening the app, not a real push/SMS trigger |
| User authentication / one-ID-per-vote / anonymous token system | **Not built** | Phase 2 — described in the pitch, not implemented in this sprint |
| County-level participation analytics dashboard | **Not built** | Phase 2 |
| SMS/USSD channel for non-smartphone users | **Not built** | Phase 2 |
| Live bill scraper (Kenya Law / county assembly sites) | **Not built** | Phase 2 — `data/sample_bill.json` stands in for this today |

## Core data schema

### Bill object (`GET /api/bill` response, and shape of `data/sample_bill.json`)
```json
{
  "bill_id": "string",
  "title": "string",
  "county": "string",
  "status": "open_for_participation",
  "participation_deadline": "YYYY-MM-DD",
  "clauses": [
    {
      "clause_id": "string",
      "title": "string",
      "raw_text": "string — the original legal-English clause text",
      "affected_group": "string — who this clause most directly affects"
    }
  ]
}
```

### Clause summary (`POST /api/summarize` response)
```json
{
  "clause_id": "string",
  "summary_en": "string — plain English, <=30 words",
  "summary_sw": "string — plain Kiswahili, <=30 words"
}
```

### Memorandum draft (`POST /api/memorandum` response)
```json
{
  "memorandum_text": "string — 2-3 sentences per rejected clause, ready to edit and send"
}
```
