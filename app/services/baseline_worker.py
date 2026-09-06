"""
Baseline worker -- computes what's "normal" for each stock from imported
historical data (stock_daily_history). Stable, offline, zero-rate-limit
operation, run once (or occasionally).
"""
import pandas as pd
from sqlalchemy import select
from app.models import StockDailyHistory, StockBaseline
from app.db import SessionLocal

MIN_HISTORY_DAYS = 20


def compute_baseline_for_symbol(db, symbol: str) -> dict | None:
    rows = db.execute(
        select(StockDailyHistory)
        .where(StockDailyHistory.stock_symbol == symbol)
        .order_by(StockDailyHistory.trade_date)
    ).scalars().all()

    if len(rows) < MIN_HISTORY_DAYS:
        return None

    df = pd.DataFrame([{"date": r.trade_date, "close": float(r.close), "volume": r.volume} for r in rows])
    df = df.sort_values("date")
    df["pct_change"] = df["close"].pct_change().abs() * 100
    df = df.dropna()

    return {
        "avg_daily_move": float(round(df["pct_change"].mean(), 4)),
        "std_dev_move": float(round(df["pct_change"].std(), 4)),
        "avg_volume": int(df["volume"].mean()),
    }


def run_baseline_worker():
    """Computes baselines for every symbol present in stock_daily_history."""
    print("Connecting to database...")
    db = SessionLocal()
    try:
        print("Fetching distinct symbols...")
        symbols = [row[0] for row in db.execute(select(StockDailyHistory.stock_symbol).distinct())]
        print(f"Found {len(symbols)} symbols. Computing baselines...")

        updated, skipped = 0, 0
        for i, symbol in enumerate(symbols, 1):
            result = compute_baseline_for_symbol(db, symbol)
            if result is None:
                skipped += 1
            else:
                existing = db.get(StockBaseline, symbol)
                if existing:
                    existing.avg_daily_move = result["avg_daily_move"]
                    existing.std_dev_move = result["std_dev_move"]
                    existing.avg_volume = result["avg_volume"]
                else:
                    db.add(StockBaseline(stock_symbol=symbol, **result))
                updated += 1

            if i % 25 == 0:
                db.commit()
                print(f"  Progress: {i}/{len(symbols)} symbols processed...")

        db.commit()
        print(f"Baseline worker: updated {updated} stocks, skipped {skipped} (insufficient history)")
    finally:
        db.close()