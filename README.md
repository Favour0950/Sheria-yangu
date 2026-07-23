# Sheria Yangu

> Built during the **Democracy & AI Hackathon** — hosted by **Mozilla Foundation** and **KamiLimu** — July 4th, 2026.
> This repository documents the feasibility sprint output submitted on the day of the hackathon.

**Suggested repo naming convention:** `sheria-yangu` 
## Team

| Name | Role | GitHub |
|------|------|--------|
| Onyango Violet Atieno | Backend & LLM Integration | @Favour0950 |
| Catherine Atieno | Frontend | @katepaul685 |

**Team Name:** T002

**University:** University of Nairobi & JKUAT

**Statement:** This work was built as part of the Democracy and AI Hackathon hosted by Mozilla Foundation and KamiLimu on July 4th, 2026.

---

## Problem & User

### Problem Statement

> Young Nairobi residents aged 18–35 — boda boda riders in Mathare, market vendors in Gikomba, students in Embakasi — cannot exercise their Article 118 and Article 196 constitutional rights to participate in legislation. During the Finance Bill 2023's public participation window, Parliament received just 1,080 memoranda from a country of 55 million people, overwhelmingly from corporations rather than individuals. This is because Parliament and county assemblies have no obligation to notify citizens when a bill opens for comment, bills are published only in dense legal English on platforms requiring active search, and existing tools like Mzalendo's Dokeza remain pull-based — citizens must actively visit the site to discover a bill, since Dokeza itself admits it has no push notification capability yet — and offer no Swahili translation or audio. Sheria Yangu closes this gap with a mobile-first tool that notifies citizens the moment a bill opens and translates its content into plain Swahili and English before the participation window closes.

*(Full version with sources: [`docs/problem-statement.md`](docs/problem-statement.md))*

### Target User

| Dimension | Detail |
|-----------|--------|
| **Primary user** | A mobile-first young resident of Nairobi's peri-urban constituencies — Mathare, Kibra, Embakasi — such as a boda boda rider or market vendor aged 18–35 |
| **Tech comfort** | Digitally active social media |
| **Language** | Comfortable in plain Swahili and English |
| **Current workflow** | Learns a law affects them only after it's enforced (e.g. a new county fee), with no prior awareness that the bill was ever open for public comment |

### The Specific Gap

1. **What's already there:** Mzalendo Trust's **Dokeza** lets citizens annotate parliamentary bills online, endorsed by the National Assembly and Senate, and accessible on any internet-connected device, including mobile.
2. **Why it falls short:** Dokeza is **pull-based** — its own FAQ admits push notifications are a feature they "hope to add... later" — so citizens must already know a bill exists to find it. Its expert annotations simplify legal jargon, but only **in English**, leaving non-English readers unserved. Annotation is manual, limiting coverage within tight participation windows, and it covers national bills only, not county ones.
3. **The gap we fill:** Sheria Yangu proactively notifies citizens when a bill (national or county) opens for comment, delivers AI-generated clause summaries in plain Swahili and English, and compiles rejected clauses into a memorandum sent to the relevant legislative body.

### Why It Matters

> In 2023, Nairobi City County passed a Finance Act that introduced a Sh1,000 annual registration fee for every boda boda rider in the city, alongside new charges for taxis, market traders, and landlords. Most riders had no idea the bill had been open for public comment before it became law. Nairobi resident Jared Ngisa Nyabuto took the county to court — and in June 2025, the High Court declared the entire Finance Act 2023 unconstitutional, ruling that the county had presented fee schedules with no underlying policy analysis, meaning citizens had nothing meaningful to actually respond to. Two years of fees were collected under a law later found illegal. Nobody should need a court case to do what the Constitution already guarantees. Sheria Yangu exists so that the next Jared gets a notification on his phone instead — closing the gap between a constitutional right on paper and a right citizens can actually use.

---

## Run Instructions

### Prerequisites

- Python 3.10+
- pip
- A DeepSeek API key (provided by KamiLimu for this hackathon)
- A modern web browser (Chrome, Firefox, etc.)

### Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/Favour0950/Sheria-yangu.git
cd Sheria-yangu

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows (Git Bash): source venv/Scripts/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
cp .env.example .env
# Open .env and fill in:
#   DEEPSEEK_API_KEY=your-key-here
#   DEEPSEEK_MODEL=deepseek-chat
#   DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# 5. Run the app
python src/main.py
# The app will be available locally at http://localhost:5000

# 6. (optional) Try the bill scraper
python src/scraper.py --test     # offline dry run, needs data/sample_bill.pdf
python src/scraper.py            # live: scrapes nairobiassembly.go.ke for real bills
```


---

## 📁 Project Structure

```
.
├── README.md                     ← You are here
├── docs/
│   ├── problem-statement.md      ← Full problem one-pager with sources
│   └── architecture.md           ← Architecture diagram, data schema, built-vs-mocked table
├── src/
│   ├── main.py                   ← Flask entry point & API routes
│   └── static/
│       └── index.html            ← 3-screen demo: notification → clause vote → memorandum
├── data/
│   └── sample_bill.json          ← Mocked Nairobi Finance Bill clauses (demo input)
├── requirements.txt
├── .env.example
├── .gitignore
└── LICENSE
```

---

## Approach & Architecture

Sheria Yangu takes a bill's clauses (currently a mocked Nairobi Finance Bill, see `data/sample_bill.json`), sends each clause to the DeepSeek API to generate a plain-language Swahili and English summary, and lets the user agree or reject it. Rejected clauses are compiled into a memorandum draft ready to send to Parliament.

```
[Bill clauses — data/sample_bill.json, mocked for this demo]
        ↓
[Flask backend — src/main.py]
        ↓  POST /api/summarize
[DeepSeek API — clause-by-clause Swahili + English summary]
        ↓
[Frontend — src/static/index.html: notification → clause cards → agree/reject]
        ↓  POST /api/memorandum
[Rejected clauses auto-compiled into memorandum draft]
        ↓
[User reviews → sends via mailto: routed by bill level/origin —
 county: clerk@nairobiassembly.go.ke · national (National Assembly): cna@parliament.go.ke ·
 national (Senate): maoni@parliament.go.ke]
```

**Built today (hackathon, real):**
- Flask backend with three working endpoints: `/api/bill`, `/api/summarize`, `/api/memorandum`
- Live DeepSeek API call generating real clause summaries
- 3-screen frontend demo (notification, clause vote, memorandum send), fully wired to the backend

**Mocked today:**
- Bill content — a hardcoded Nairobi Finance Bill (`data/sample_bill.json`), not a live scrape of Parliament/county sources

**Explicitly out of scope (Phase 2):**
- Real-time bill scraping from Kenya Law / county assembly sites
- User authentication and one-account-per-national-ID verification
- Push notifications (in-app, SMS/USSD)
- County-level participation analytics

*(Full diagram and data schema: [`docs/architecture.md`](docs/architecture.md))*

---

## License

MIT © Violet & Catherine, 2026
