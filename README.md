# Smart Market Watchlist

A watchlist that judges each stock's move against its OWN normal
behaviour and against what you've personally already seen -- instead of
a flat "moved 5%" rule used by every mainstream trading app.

## Architecture -- a deliberate hybrid, and why

**Baselines** ("what's normal for this stock") are computed from
**imported historical data** (a Kaggle Nifty500 5-year dataset, filtered
to 2025 and 2026 only, the most recent data available) -- a stable,
offline, one-time operation with zero rate-limit risk.

**Live current prices** come from **yfinance**, fetched continuously in
the background -- a small, low-risk API call per stock, not a bulk
historical pull.

This split exists because we tried computing baselines via yfinance too
(bulk-fetching a year of history per stock) and hit real, repeated
rate-limit/reliability failures -- exactly the kind of fragile,
internet-dependent step you don't want as a hard requirement right
before a live demo. Historical data for the (stable) baseline, live data
for the (must-be-current) price -- each piece uses the source that's
actually reliable for that job.

Sector is stored as a **display label only** (joined from a static CSV
of NSE sector classifications) -- never used in scoring. A stock is
judged only against its own history, per an explicit product decision.

## Honest limitations (stated up front, not hidden)

- **Baseline data currently reflects 2025-2026 only** -- filtered
  deliberately from a longer available window, so "normal" reflects
  genuinely recent market behaviour rather than years-old patterns
  (this also avoids old extreme-volatility periods skewing what counts
  as "normal" today).
- **yfinance is unofficial** -- scrapes Yahoo Finance's public site, not
  a licensed feed, typically ~15min delayed. Disclosed trade-off for a
  working prototype; production would use a licensed vendor.
- **Cold-start stocks** need 20+ days of history before a baseline is
  trusted -- honestly skipped otherwise, not guessed.

## 1. Set up Supabase

1. https://supabase.com -> sign up -> new project (set a DB password).
2. Project Settings -> Database -> Connection pooling.
3. Use **Session pooler** or **Transaction pooler** (port 5432 or 6543)
   -- not the direct `db.xxxx.supabase.co` host (requires IPv6, fails on
   many networks).
4. Copy the connection string.

## 2. Local setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# paste your real Supabase connection string into .env
```
If your password contains `@`, URL-encode it as `%40`.

## 3. Get the Kaggle dataset

Download "NSE India Stock Market Data (2015-2024)" from Kaggle, place
the CSV in `data/kaggle_raw/`.

## 4. Run the app once (creates tables)

```bash
uvicorn app.main:app --reload
```
Ctrl+C once it starts cleanly.

## 5. Create a demo user

```bash
python -c "from app.db import SessionLocal; from app.models import User; db = SessionLocal(); u = User(name='Demo User'); db.add(u); db.commit(); print('Created user id:', u.id)"
```

## 6. Import historical data and compute baselines

```bash
python -m scripts.import_kaggle data/kaggle_raw/nifty500_stocks.csv
python -m scripts.run_baseline
```

## 7. Start the live fetcher (own terminal, keep running)

```bash
python -m scripts.fetch_live --loop
```

## 8. Start the app and use it

```bash
uvicorn app.main:app --reload
```
Open http://localhost:8000/watchlist/1, add a symbol that exists in your
imported data (e.g. RELIANCE, TCS, INFY), watch it populate.

## 9. Run the tests

```bash
pytest tests/ -v
```
Targets the scoring logic specifically -- proof the same raw % move
scores differently for a calm vs. volatile stock, independent of any
data source.

## Project structure

```
app/
  main.py                    FastAPI entrypoint
  db.py                      database connection
  models.py                  6 tables: users, watchlist_items,
                              stock_daily_history, stock_baselines,
                              stock_signals, watchlist_checkins
  routers/watchlist.py        add/remove/view + "what changed" logic
  services/
    baseline_worker.py         computes "normal" from imported history
    signal_engine.py           core scoring math, fully transparent
  templates/watchlist.html     the UI
scripts/
  import_kaggle.py            one-time: load historical CSV, filtered to 2025-2026
  run_baseline.py              CLI: recompute baselines from imported data
  fetch_live.py                CLI: fetch + score current prices (--loop)
data/
  kaggle_raw/                  put the downloaded CSV here
  sector_mapping.csv           NSE sector labels (display only)
tests/
  test_signal_engine.py        5 tests on the core scoring logic
```

## Explicitly out of scope (and why)

- No real trading / auto-buy / wallet feature.
- No portfolio-based ML recommendations.
- No microservices, Kafka, Redis -- a small monolith is the right choice
  for a solo build at this scale.
