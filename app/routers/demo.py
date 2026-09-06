"""
Injects synthetic ticks through the REAL
scoring pipeline (score_move / write_signal) so users can see the
"new since visit" logic working even when NSE is closed (weekends,
holidays, or after market hours). Nothing here bypasses the scoring
math -- only the input price move is synthetic.

"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import StockBaseline, StockSignal, WatchlistItem, WatchlistCheckin
from app.services.signal_engine import score_move, write_signal

router = APIRouter()

GAP = timedelta(seconds=5)

DEMO_SCENARIOS = {
    "RELIANCE": ("new", +1),   
    "TCS":      ("new", -1),   
    "INFY":     ("calm", +1),  
}


def _ensure_on_watchlist(db, user_id, symbol):
    if not db.query(WatchlistItem).filter_by(user_id=user_id, stock_symbol=symbol).first():
        db.add(WatchlistItem(user_id=user_id, stock_symbol=symbol))
        db.commit()


def _set_checkin(db, user_id, symbol, when):
    row = db.query(WatchlistCheckin).filter_by(user_id=user_id, stock_symbol=symbol).first()
    if row:
        row.last_seen_at = when
    else:
        db.add(WatchlistCheckin(user_id=user_id, stock_symbol=symbol, last_seen_at=when))
    db.commit()


def _inject(db, symbol, pct_move, volume, baseline, fetched_at):

    score = score_move(symbol=symbol, pct_move_today=pct_move, volume_today=volume, baseline=baseline)

    prev_close = 980.0
    current_price = round(prev_close * (1 + pct_move / 100), 2)
    change_rupees = round(current_price - prev_close, 2)

    write_signal(
        db, symbol=symbol, fetched_at=fetched_at,
        current_price=current_price, raw_pct_change=pct_move, volume=volume,
        open_price=prev_close,
        day_high=max(current_price, prev_close) + 5,
        day_low=min(current_price, prev_close) - 5,
        prev_close=prev_close,
        score=score,
    )
    db.commit()
    return score, current_price, change_rupees


@router.post("/watchlist/{user_id}/demo/setup")
def setup_demo(user_id: int, db: Session = Depends(get_db)):
    for symbol in DEMO_SCENARIOS:
        db.query(StockSignal).filter_by(stock_symbol=symbol).delete()
        db.query(WatchlistCheckin).filter_by(user_id=user_id, stock_symbol=symbol).delete()
    db.commit()

    results = {}
    for symbol, (kind, sign) in DEMO_SCENARIOS.items():
        baseline = db.get(StockBaseline, symbol)
        if baseline is None:
            results[symbol] = {"error": "no baseline -- skipped"}
            continue

        _ensure_on_watchlist(db, user_id, symbol)
        std_dev = float(baseline.std_dev_move) if baseline.std_dev_move else 1.0
        big_move = std_dev * 3 * sign
        small_move = 0.3 * sign

        anchor = datetime.utcnow()

        if kind == "new":

            _set_checkin(db, user_id, symbol, anchor - timedelta(days=1))
            score, price, chg = _inject(db, symbol, big_move, 500_000, baseline, fetched_at=anchor)

        elif kind == "calm":
            _set_checkin(db, user_id, symbol, anchor - timedelta(hours=1))
            score, price, chg = _inject(db, symbol, small_move, 500_000, baseline, fetched_at=anchor)

        results[symbol] = {
            "scenario": kind,
            "direction": "up" if sign > 0 else "down",
            "deviation_score": score["deviation_score"],
            "is_meaningful": score["is_meaningful"],
            "price": price,
            "change_rupees": chg,
        }

    return {"status": "ok", "results": results}


@router.post("/watchlist/{user_id}/demo/reset")
def reset_demo(user_id: int, db: Session = Depends(get_db)):
    for symbol in DEMO_SCENARIOS:
        db.query(WatchlistCheckin).filter_by(user_id=user_id, stock_symbol=symbol).delete()
        db.query(StockSignal).filter_by(stock_symbol=symbol).delete()
    db.commit()
    return {"status": "reset"}