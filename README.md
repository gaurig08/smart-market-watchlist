# Smart Market Watchlist

A smart stock watchlist that doesn't just show prices - it tells you **what meaningfully changed** since you last checked, judged against each stock's **own normal behaviour** (not a flat 5% rule).

Built for the **Code by Groww Hackathon**.

---

## The Core Idea

Most apps alert on fixed thresholds ("moved more than 5%").  
I define "meaningful" as **relative to that stock's own history**:

- A calm stock moving 3% can be more significant than a volatile stock moving 8%.
- Each stock gets a **Relative Move** score (e.g. `2.4x` its normal daily range).
- Users also see what changed **since their last visit** - personal, not global.

Transparent math. No black box. No investment advice.

---

## Features

- Create & manage a personal watchlist
- Live prices (LTP, Change ₹, Change %, High, Low, Volume)
- **Relative Move** score vs each stock's historical baseline
- Plain-language **Status** explaining why a move matters
- **Since Last Visit** - what changed while you were away
- Multilingual AI assistant (Groq, 11 Indian languages) that only explains already-computed data
- Filters (price range)
- Graceful fallbacks when AI / live data is unavailable

---

## Architecture (deliberate choices)

| Piece | Source | Why |
|-------|--------|-----|
| Historical baselines | Kaggle NSE dataset (offline) | Stable, zero rate-limit risk |
| Live prices | yfinance (background fetch) | Simple, good enough for prototype |
| Scoring | Deterministic Python (`signal_engine`) | Transparent, testable, no ML magic |
| AI explainer | Groq (Llama) | Explains only, never decides scores |
| UI | FastAPI + Jinja2 + Tailwind | Single deploy, solo-friendly |
| DB | PostgreSQL (Supabase) | Persistent watchlists + baselines |

---

## Process & Key Decisions

**Why relative moves, not flat thresholds.** Before writing any code, I compared how 7+ existing platforms flag stock moves and found every one uses a fixed percentage cutoff, treating a blue-chip and a small-cap identically. Judging a move against a stock's *own* historical volatility, not a universal number, is the entire premise of this project, validated before implementation started.

**Why sector comparison was cut.** An early version compared a stock's move to its sector average. I removed it deliberately — it added a second axis of "meaningful" that muddied the pitch and wasn't defensible with the data available. Every score here is purely a stock judged against its own history.

**Why multilingual AI, not just an English chatbot.** SEBI's Investor Survey 2025 covering 90,000+ households across 400 cities and 1,000 villages found a consistent preference for investor education in regional languages across every demographic group. RBI/NCFE financial literacy data has repeatedly shown literacy stuck around 27%, and RBI's National Strategy for Financial Inclusion (2025-30) is explicitly built around improving last-mile delivery. The assistant's 11-language support directly targets that gap: it only explains numbers the deterministic engine already computed, so language access is added without touching the trustworthiness of the scoring.

**Why historical baselines and live prices come from different sources.** Bulk historical fetching through `yfinance` proved unreliable for stable baselines, so baselines are computed once from a Kaggle NSE dataset, while `yfinance` is used only for today's live price.

**Why timestamps are UTC everywhere.** A real bug during testing: "New since last visit" stayed stuck because one part of the code used local time and another used UTC, so a checkin could never catch up to a signal written hours "in the future." Fixed by standardizing every timestamp on UTC.

**Why there's a built-in demo mode.** NSE is closed most of the time a reviewer opens this app. The app detects market hours and offers a "Run Demo Scenarios" button that injects synthetic price moves through the *real* scoring pipeline, not a mock an honest way to prove the logic works outside trading hours.

**Why Groq instead of Gemini.** Gemini's free-tier limits made the chat assistant fail after 1-2 messages. Groq's free tier is far more generous for this workload, and the explainer falls back to a deterministic, localized response if the AI call fails the feature never just breaks.

**What was knowingly simplified.** The Relative Move score assumes a stock's average daily return is close enough to zero to skip tracking separately true for short lookback windows, but a simplification worth naming. A proper baseline mean would make the z-score fully rigorous instead of a close approximation.

---

## Tech Stack

- **Backend:** Python, FastAPI, SQLAlchemy
- **Frontend:** Jinja2 templates + Tailwind CSS + vanilla JS
- **Database:** PostgreSQL (Supabase)
- **Data:** Kaggle historical OHLCV + yfinance live
- **AI:** Groq API (OpenAI-compatible)

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

# 6. (Optional) Live price loop - separate terminal
python -m scripts.fetch_live --loop

# 7. Run
uvicorn app.main:app --reload
```