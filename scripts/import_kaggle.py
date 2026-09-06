"""
Imports the downloaded Kaggle CSV into stock_daily_history -- FILTERED TO
2025 AND 2026 ONLY, the most recent data available, to keep baselines
genuinely current. No sector data is stored (removed -- not used
anywhere in scoring or display).

"""
import sys
import pandas as pd
from app.db import SessionLocal
from app.models import StockDailyHistory

COLUMN_MAP = {
    "Ticker": "stock_symbol",
    "Date": "trade_date",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume",
}

BASELINE_YEARS = [2025, 2026]


def import_csv(path: str):
    df = pd.read_csv(path)

    missing = [c for c in COLUMN_MAP if c not in df.columns]
    if missing:
        print(f"These expected columns were not found: {missing}")
        print(f"Actual columns in the file are: {list(df.columns)}")
        sys.exit(1)

    df = df.rename(columns=COLUMN_MAP)
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y-%m-%d", errors="coerce").dt.date

    before_null_drop = len(df)
    df = df.dropna(subset=["trade_date", "open", "high", "low", "close", "volume"])
    print(f"Dropped {before_null_drop - len(df)} rows with null/unparseable values")

    before_year_filter = len(df)
    df = df[pd.to_datetime(df["trade_date"]).dt.year.isin(BASELINE_YEARS)]
    print(f"Filtered to {BASELINE_YEARS}: {before_year_filter} -> {len(df)} rows")

    if len(df) == 0:
        print("WARNING: 0 rows after year filter.")
        sys.exit(1)

    before = len(df)
    df = df.groupby(["stock_symbol", "trade_date"], as_index=False).agg({
        "open": "mean", "high": "mean", "low": "mean", "close": "mean", "volume": "mean",
    })
    after = len(df)
    if before != after:
        print(f"Note: found {before - after} conflicting/duplicate (symbol, date) rows -- averaged them.")

    wipe = SessionLocal()
    wipe.query(StockDailyHistory).delete()
    wipe.commit()
    wipe.close()

    db = SessionLocal()
    try:
        count = 0
        for _, row in df.iterrows():
            db.add(
                StockDailyHistory(
                    stock_symbol=str(row["stock_symbol"]).upper(),
                    trade_date=row["trade_date"],
                    open=row["open"], high=row["high"], low=row["low"], close=row["close"],
                    volume=int(row["volume"]),
                )
            )
            count += 1
            if count % 2000 == 0:
                db.commit()
        db.commit()
        print(f"Imported {count} rows from {path}")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.import_kaggle <path-to-csv>")
        sys.exit(1)
    import_csv(sys.argv[1])