# Smart Market Watchlist

A smart stock watchlist that doesn't just show prices — it tells you **what meaningfully changed** since you last checked, judged against each stock's **own normal behaviour** (not a flat 5% rule).

Built for the **Code by Groww Hackathon**.

---

## The Core Idea

Most apps alert on fixed thresholds ("moved more than 5%").  
We define "meaningful" as **relative to that stock's own history**:

- A calm stock moving 3% can be more significant than a volatile stock moving 8%.
- Each stock gets a **Relative Move** score (e.g. `2.4x` its normal daily range).
- Users also see what changed **since their last visit** — personal, not global.

Transparent math. No black box. No investment advice.

---

## Features

- Create & manage a personal watchlist
- Live prices (LTP, Change ₹, Change %, High, Low, Volume)
- **Relative Move** score vs each stock's historical baseline
- Plain-language **Status** explaining why a move matters
- **Since Last Visit** — what changed while you were away
- Multilingual AI assistant (Groq) that only explains already-computed data
- Filters (price range, "needs attention only")
- Graceful fallbacks when AI / live data is unavailable

---

## Architecture (deliberate choices)

| Piece | Source | Why |
|-------|--------|-----|
| Historical baselines | Kaggle NSE dataset (offline) | Stable, zero rate-limit risk |
| Live prices | yfinance (background fetch) | Simple, good enough for prototype |
| Scoring | Deterministic Python (`signal_engine`) | Transparent, testable, no ML magic |
| AI explainer | Groq (Llama) | Explains only — never decides scores |
| UI | FastAPI + Jinja2 + Tailwind | Single deploy, solo-friendly |
| DB | PostgreSQL (Supabase) | Persistent watchlists + baselines |

**Explicitly avoided:** microservices, Kafka, Redis, React SPA, WebSockets — over-engineering for a 72-hour solo build.

---

## Tech Stack

- **Backend:** Python, FastAPI, SQLAlchemy
- **Frontend:** Jinja2 templates + Tailwind CSS + vanilla JS
- **Database:** PostgreSQL (Supabase)
- **Data:** Kaggle historical OHLCV + yfinance live
- **AI:** Groq API (OpenAI-compatible)
- **Deploy:** Replit / local

---

## Quick Start (Local)

```bash
# 1. Clone & setup
git clone https://github.com/gaurig08/smart-market-watchlist.git
cd smart-market-watchlist
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Environment
cp .env.example .env
# Fill in:
#   DATABASE_URL=postgresql://...   (Supabase session pooler)
#   GROQ_API_KEY=gsk_...

# 3. Create tables (start app once)
uvicorn app.main:app --reload
# Ctrl+C after it starts cleanly

# 4. Create demo user
python -c "from app.db import SessionLocal; from app.models import User; db = SessionLocal(); u = User(name='Demo User'); db.add(u); db.commit(); print('User id:', u.id)"

# 5. Import history + compute baselines
python -m scripts.import_kaggle data/kaggle_raw/your_file.csv
python -m scripts.run_baseline

# 6. (Optional) Live price loop — separate terminal
python -m scripts.fetch_live --loop

# 7. Run
uvicorn app.main:app --reload