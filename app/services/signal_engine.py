"""
Signal engine -- the core "meaningful change" scoring logic.

Given a stock's current price move and its precomputed baseline, decides
how unusual this move actually is FOR THIS STOCK -- purely based on its
own historical behaviour.
"""
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import StockBaseline, StockSignal

MEANINGFUL_DEVIATION = 2.0
MIN_LIQUIDITY_VOLUME = 10_000


def score_move(
    symbol: str,
    pct_move_today: float,
    volume_today: int,
    baseline: StockBaseline,
) -> dict:

    if volume_today is not None and volume_today < MIN_LIQUIDITY_VOLUME:
        return {
            "deviation_score": 0.0,
            "is_meaningful": False,
            "reason_text": "Low trading volume today -- move may not be reliable.",
        }

    std_dev = float(baseline.std_dev_move) if baseline.std_dev_move and baseline.std_dev_move > 0 else 0.01

    deviation_score = round(abs(pct_move_today) / std_dev, 2)
    is_meaningful = deviation_score >= MEANINGFUL_DEVIATION

    if is_meaningful:
        reason = f"Moved {deviation_score}x its normal daily range."
    else:
        reason = "Within its normal daily range."

    return {
        "deviation_score": deviation_score,
        "is_meaningful": is_meaningful,
        "reason_text": reason,
    }


def write_signal(
    db: Session,
    symbol: str,
    fetched_at: datetime,
    current_price: float,
    raw_pct_change: float,
    volume: int,
    open_price: float,
    day_high: float,
    day_low: float,
    prev_close: float,
    score: dict,
):

    db.add(
        StockSignal(
            stock_symbol=symbol,
            fetched_at=fetched_at,
            current_price=current_price,
            raw_pct_change=round(raw_pct_change, 2) if raw_pct_change is not None else None,
            volume=volume,
            open_price=open_price,
            day_high=day_high,
            day_low=day_low,
            prev_close=prev_close,
            deviation_score=score["deviation_score"],
            is_meaningful=score["is_meaningful"],
            reason_text=score["reason_text"],
        )
    )