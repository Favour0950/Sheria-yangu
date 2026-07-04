# Sheria Yangu

> Built during the **Democracy & AI Hackathon** — July 4th, 2026
> Hosted by **Mozilla Foundation** & **KamiLimu**

This work is part of a hackathon hosted by Mozilla Foundation and KamiLimu on Democracy and AI, July 4th, 2026.

**Suggested repo name:** `sheria-yangu-<teamname>` (e.g. `sheria-yangu-violet-catherine`) — makes it easy for organisers to ID your team's repo among many.

---

## Team

| Name | Role | GitHub |
|------|------|--------|
| Onyango Violet Atieno | Frontend | [@handle] |
| Catherine Atieno | Backend / AI integration | [@handle] |

**Team Name:** [Insert Team Name]
**Universities:** Violet — University of Nairobi · Catherine — JKUAT

---

## Problem & User

### Problem Statement

Young Nairobi residents aged 18–35 — boda boda riders in Mathare, market vendors in Gikomba,
students in Embakasi — cannot exercise their Article 118 and Article 196 constitutional rights
to participate in legislation because bills are published only in legal English on platforms
requiring active search, and no tool exists that notifies them and translates bill content into
plain language before the participation window closes.

### Target User

| Dimension | Detail |
|---|---|
| Primary user | Mobile-first youth aged 18–25 in peri-urban Nairobi (Mathare, Kibra, Embakasi) — boda boda riders, market vendors, small business owners |
| Tech comfort | Comfortable with smartphones and social media; not comfortable with government websites or legal English |
| Language | Kiswahili and English |
| Current workflow | Learns about bills informally via social media, if at all — no direct, verified channel |

### The Specific Gap

**What's already there:** Mzalendo Trust's Dokeza; Kenya Law's bill repository; Parliament's social media.
**Why it falls short:** English-only, desktop-oriented, manually annotated, no proactive notification.
**The gap we fill:** Mobile notification + AI plain-language (English/Swahili) clause summaries + one-tap agree/reject + auto-drafted memorandum.

See `docs/problem-statement.md` for the full write-up, including sources.

### Why It Matters

The Nairobi City County Finance Act 2023 was declared unconstitutional in June 2025 for
failing meaningful public participation — after two years of citizens paying fees under a bill
they never knew was open for comment. See `docs/problem-statement.md` for the full case and sources.

---

## Run Instructions

### Prerequisites
- Python 3.10+
- A DeepSeek API key (provided by organisers via email)

### Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/[org]/[repo].git
cd [repo]

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
cp .env.example .env
# Edit .env and paste your DeepSeek API key into DEEPSEEK_API_KEY
# Never commit .env — it's already in .gitignore

# 5. Run the project
python src/main.py

# 6. Open the demo
# Visit http://localhost:5000 in your browser
```

## 📁 Project Structure

```
.
├── README.md
├── docs/
│   ├── problem-statement.md    ← Problem & user one-pager
│   └── architecture.md         ← Data flow diagram, schema, built vs mocked
├── src/
│   ├── main.py                 ← Flask backend + DeepSeek calls
│   └── static/
│       └── index.html          ← 3-screen demo frontend (notification, clauses, memorandum)
├── data/
│   └── sample_bill.json        ← Mocked bill (modeled on the real, nullified Nairobi Finance Act 2023)
├── requirements.txt
├── .env.example
├── .gitignore
└── LICENSE
```

## Approach & Architecture

```
[User: Web App] → [Flask Backend] → [DeepSeek LLM API] → [Plain-language clause summaries + memorandum draft]
```

Full diagram and data schema: `docs/architecture.md`.

**Built today:** Flask API, mock bill data, live DeepSeek calls for clause simplification and memorandum drafting, 3-screen web demo.
**Mocked today:** The bill content itself (not scraped live), and "sending" the memorandum (opens a `mailto:` draft rather than actually transmitting to Parliament).
**Not built (Phase 2):** Push notifications, SMS/USSD channel, one-ID-per-vote verification, county-level analytics dashboard.

## License

MIT © Violet & Catherine, 2026
