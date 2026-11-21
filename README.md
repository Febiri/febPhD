# 🎓 febPhD — My PhD Corner & Academic Research Workstation

A comprehensive, **100% free-tier doctoral research platform** that empowers PhD candidates and academic researchers with two specialized engines:
1. **📖 Paper Reader & Spoken Research Studio (`/app`)**: Ingests papers from your [Zotero](https://www.zotero.org/) library or PDF uploads, narrates 100% verbatim or synthesizes 4-part senior briefings with natural West African neural voices (Ghanaian Abeo & Ezinne), vocalizes complex mathematical formulas phonetically, and synchronizes real-time text and extracted figures.
2. **🌐 Intelligent Conference & Academic Event Scout (`/conferences`)**: Scans all over academic registries, CORE rankings (A*, A, B), and academic networks to discover upcoming conferences, doctoral consortiums / PhD tracks, and student travel grants tailored to your exact research area with live submission countdowns.

> **Zero Cloud Costs ($0.00/month):** Powered entirely by Google Gemini Flash free tier, Microsoft Edge-TTS neural speech, PyMuPDF, and local SQLite.

---

## 🏛️ System Architecture

```
                                  🎓 MY PHD CORNER HOME
                                           (/)
                                            │
              ┌─────────────────────────────┴─────────────────────────────┐
              │                                                           │
              ▼                                                           ▼
     [ Engine Card 01 ]                                          [ Engine Card 02 ]
  📖 Paper Reader Studio (/app)                               🌐 Conference Scout (/conferences)
  • 100% Verbatim & 4-Part Briefings                          • Live Academic Search
  • 🇬🇭 Ghanaian Abeo & Ezinne Voices                          • 🎓 Doctoral Consortiums / PhD Tracks
  • Scientific Math & Symbol Phonetics                        • ✈️ Student Travel Grants & Waivers
  • Extracted Figures & Diagram Viewer                        • 🏛️ CORE A*, IEEE, ACM & WikiCFP Rankings
  • Interactive Seek-to-Paragraph                             • ⏳ Live Submission Countdown Badges
  • Zotero Web Sync + Drag & Drop PDFs                        • ⭐ "My PhD Watchlist" & Calendar Export
```

---

## ⚡ Core Features

### 1. 📖 Paper Reader & Spoken Audio Mentor (`/app`)
* **100% Verbatim Full Paper Reading**: Reads entire papers word-for-word without skipping derivations, citations, or equations.
* **4-Part Senior Mentor Briefings**:
  1. 🎯 *The Core Problem & Theoretical Foundation*
  2. 🔬 *Methodology & Architectural Formulation*
  3. 📊 *Empirical Results, Benchmarks & Statistical Significance*
  4. ⚠️ *Critical Limitations, Theoretical Bounds & Future Research*
* **Expressive West African Neural Voices**:
  * 🇬🇭 **Abeo** (West Africa / Ghana - Male, natural scholarly cadence)
  * 🇬🇭 **Ezinne** (West Africa / Ghana - Female, melodic and clear)
  * Additional African and international voices (Kenya, South Africa, UK, US).
* **Phonetic Scientific Normalizer**: Correctly vocalizes mathematical symbols ($\alpha, \beta, \theta, \sum, \int$), powers of 10 ($10^{-5}$), statistical metrics ($p < 0.001$, $R^2$), and Greek nomenclature for auditory clarity.
* **Synchronized Reading & Visuals**: Follow along with paragraph-by-paragraph highlights, skip backward/forward by 10s/30s, seek by chapters, and inspect extracted in-document figures and diagrams.

### 2. 🌐 Intelligent Conference & Academic Event Scout (`/conferences`)
* **Dedicated PhD Event Search**: Enter any research topic (e.g. *Natural Language Processing for African Languages, Computer Vision, Microgrids, Healthcare AI*).
* **PhD Opportunities**:
  * 🎓 **Doctoral Consortiums**: Dedicated mentorship tracks where PhD students receive 1-on-1 thesis reviews from distinguished professors.
  * ✈️ **Student Travel Grants**: Direct visibility into ACM, IEEE, USENIX, and NSF travel stipends and registration fee waivers.
  * 🏛️ **CORE Ranking (A*, A, B)**: Objective venue prestige indicators.
* **Dynamic Calendar & Live Countdowns**:
  * Live color-coded submission countdowns (`⏰ Closing Soon • 21d left`, `🟢 Open CFP • 88d left`).
  * Direct links to official Call for Papers (CFP) portals and conference homepages.
* **⭐ My PhD Watchlist**: Pin conferences to track deadlines and copy key dates directly to your calendar or thesis notes.

---

## 🛠️ Tech Stack

* **Backend:** Python 3.10+ with [FastAPI](https://fastapi.tiangolo.com/) and [Uvicorn](https://www.uvicorn.org/)
* **AI & LLM:** [Google GenAI SDK](https://github.com/googleapis/python-genai) (`google-genai`) with `gemini-2.5-flash`
* **Speech Synthesis:** [edge-tts](https://github.com/rany2/edge-tts) (Microsoft Edge high-fidelity neural voices)
* **PDF Extraction:** [PyMuPDF](https://pymupdf.readthedocs.io/) (`fitz`) for text sanitization and figure rendering
* **Zotero Integration:** [pyzotero](https://pyzotero.readthedocs.io/) for library sync and PDF attachment downloading
* **Database:** SQLite with [SQLAlchemy](https://www.sqlalchemy.org/) ORM
* **Frontend:** Modern responsive UI with Tailwind CSS, KaTeX formula rendering, Newsreader editorial serif typography, and vanilla JavaScript

---

## 📁 Repository Structure

```
febPhD/
├── backend/
│   ├── __init__.py
│   ├── config.py             # Environment config, directory paths, and voice registries
│   ├── database.py           # SQLAlchemy Paper models, SQLite engine, and DB session
│   ├── zotero_sync.py        # Pyzotero integration, item fetching, and PDF attachment download
│   ├── processor.py          # PyMuPDF text cleaning, phonetic formula normalizer, Edge-TTS audio
│   ├── conference_scout.py   # Intelligent conference scout service (CORE registry + Gemini scan)
│   └── main.py               # FastAPI application, REST endpoints, and static file routers
├── frontend/
│   ├── home.html             # "My PhD Corner" clean white landing hub & dual engine cards
│   ├── conferences.html      # Dedicated full-page Conference & Academic Event Scout
│   └── index.html            # Paper Reader & Spoken Research Studio with interactive player
├── static/
│   ├── favicon.ico
│   ├── favicon.svg
│   ├── audio/                # Generated audio briefing tracks (.gitkeep)
│   ├── pdfs/                 # Ingested PDF papers (.gitkeep)
│   ├── figures/              # Extracted figures and diagrams (.gitkeep)
│   └── diagrams/             # Architectural diagrams (.gitkeep)
├── .env.example              # Configuration template
├── .gitignore                # Comprehensive exclusion rules (protects credentials & large binaries)
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation
```

---

## 🚀 Getting Started

### 1. Clone the Repository
```bash
git clone https://github.com/Febiri/febPhD.git
cd febPhD
```

### 2. Set Up Virtual Environment & Dependencies
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
copy .env.example .env
```
Add your free Google Gemini API key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
DEFAULT_TTS_VOICE=en-NG-AbeoNeural
```
*(Optional) If using Zotero sync, add your Zotero User ID and API Key.*

### 4. Run the Platform
```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser:
* **PhD Corner (Home):** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
* **Conference Scout:** [http://127.0.0.1:8000/conferences](http://127.0.0.1:8000/conferences)
* **Paper Reader Studio:** [http://127.0.0.1:8000/app](http://127.0.0.1:8000/app)

---

## 📜 License
MIT License. Free for academic researchers, PhD candidates, and universities worldwide.
