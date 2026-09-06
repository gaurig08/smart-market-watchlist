"""
Live price fetching -- shared by scripts/fetch_live.py (the background
loop) AND app/routers/watchlist.py (so a newly-added stock gets fetched
immediately on add, instead of waiting for the next scheduled loop cycle).

"""
import time
import yfinance as yf
from datetime import datetime, timezone
from app.models import StockBaseline
from app.services.signal_engine import score_move, write_signal

MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 3


def fetch_history_with_retry(symbol: str):

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            info = ticker.history(period="2d")
            if len(info) >= 2:
                return info
        except Exception as e:
            print(f"    Attempt {attempt}/{MAX_RETRIES} failed for {symbol}: {e}")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY_SECONDS)
    return None


def fetch_and_score_one(db, symbol: str, user_id: int = None) -> bool:

    baseline = db.get(StockBaseline, symbol)
    if baseline is None:
        print(f"  Skipping {symbol}: no baseline computed yet.")
        return False

    info = fetch_history_with_retry(symbol)
    if info is None:
        print(f"  Skipping {symbol}: no usable data after {MAX_RETRIES} attempts.")
        return False

    prev_close = float(info["Close"].iloc[-2])
    current_price = float(info["Close"].iloc[-1])
    today_volume = int(info["Volume"].iloc[-1])
    pct_move = ((current_price - prev_close) / prev_close) * 100

    score = score_move(symbol=symbol, pct_move_today=pct_move, volume_today=today_volume, baseline=baseline)
    write_signal(
        db, symbol=symbol, fetched_at=datetime.now(timezone.utc).replace(tzinfo=None),
        current_price=current_price, raw_pct_change=pct_move, volume=today_volume,
        open_price=float(info["Open"].iloc[-1]), day_high=float(info["High"].iloc[-1]),
        day_low=float(info["Low"].iloc[-1]), prev_close=prev_close, score=score,
    )
    db.commit()
    print(f"  {symbol}: \u20b9{current_price:.2f}  {score['reason_text']}")
    return True