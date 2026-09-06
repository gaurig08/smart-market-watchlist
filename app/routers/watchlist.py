"""
Watchlist endpoints -- CRUD, ranking with "what changed since I checked",
symbol autocomplete, and the AI chat assistant.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, Form, Body
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import WatchlistItem, StockSignal, WatchlistCheckin, StockBaseline
from app.services.live_fetcher import fetch_and_score_one
from app.services.explainer import chat_response

router = APIRouter()


@router.get("/symbols/search")
def search_symbols(q: str = "", db: Session = Depends(get_db)):
    if not q:
        return []
    q_upper = q.upper().strip()
    all_symbols = [row[0] for row in db.execute(select(StockBaseline.stock_symbol))]
    starts_with = sorted([s for s in all_symbols if s.startswith(q_upper)])
    contains = sorted([s for s in all_symbols if q_upper in s and not s.startswith(q_upper)])
    return (starts_with + contains)[:8]


@router.post("/watchlist/add")
def add_stock(user_id: int = Form(...), stock_symbol: str = Form(...), db: Session = Depends(get_db)):
    symbol = stock_symbol.upper().strip()

    baseline = db.get(StockBaseline, symbol)
    if baseline is None:
        return RedirectResponse(url=f"/watchlist/{user_id}?error=not_found", status_code=303)

    existing = db.execute(
        select(WatchlistItem).where(
            WatchlistItem.user_id == user_id,
            WatchlistItem.stock_symbol == symbol,
        )
    ).scalar_one_or_none()
    if not existing:
        db.add(WatchlistItem(user_id=user_id, stock_symbol=symbol))
        db.commit()
        fetch_and_score_one(db, symbol, user_id=user_id)
    return RedirectResponse(url=f"/watchlist/{user_id}", status_code=303)


@router.post("/watchlist/remove")
def remove_stock(user_id: int = Form(...), stock_symbol: str = Form(...), db: Session = Depends(get_db)):
    items = db.execute(
        select(WatchlistItem).where(
            WatchlistItem.user_id == user_id,
            WatchlistItem.stock_symbol == stock_symbol.upper(),
        )
    ).scalars().all()
    for item in items:
        db.delete(item)
    db.commit()
    return RedirectResponse(url=f"/watchlist/{user_id}", status_code=303)


def get_ranked_watchlist(user_id: int, db: Session) -> list[dict]:
    items = db.execute(
        select(WatchlistItem).where(WatchlistItem.user_id == user_id)
    ).scalars().all()

    checkins = {
        c.stock_symbol: c.last_seen_at
        for c in db.execute(
            select(WatchlistCheckin).where(WatchlistCheckin.user_id == user_id)
        ).scalars().all()
    }

    rows = []
    for item in items:
        symbol = item.stock_symbol
        last_seen = checkins.get(symbol)
        baseline = db.get(StockBaseline, symbol)

        latest = db.execute(
            select(StockSignal)
            .where(StockSignal.stock_symbol == symbol)
            .order_by(StockSignal.fetched_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        if latest is None:
            rows.append({
                "symbol": symbol, "price": None, "change_rupees": None, "deviation_score": 0, "meter_width": 0,
                "is_meaningful": False, "is_new_since_checkin": False,
                "reason_text": "No data fetched yet for this stock.",
                "since_visit_text": None,
                "raw_pct_change": None, "volume": None, "open_price": None,
                "day_high": None, "day_low": None, "prev_close": None,
                "baseline_avg_move": None, "baseline_std_dev": None,
            })
            continue

        reason = latest.reason_text
        is_meaningful = bool(latest.is_meaningful)
        deviation_score = float(latest.deviation_score or 0)
        is_new = False
        since_visit_text = None

        if last_seen is None:
            since_visit_text = "First time viewing this stock."
        else:
            since_checkin = db.execute(
                select(StockSignal)
                .where(StockSignal.stock_symbol == symbol, StockSignal.fetched_at > last_seen)
                .order_by(StockSignal.fetched_at)
            ).scalars().all()

            if not since_checkin:
                since_visit_text = "No new data fetched since your last visit."
            else:
                meaningful_since = [s for s in since_checkin if s.is_meaningful]
                first_price = float(since_checkin[0].current_price)
                last_price = float(since_checkin[-1].current_price)
                net_change = ((last_price - first_price) / first_price) * 100 if first_price else 0

                if meaningful_since:
                    is_new = True
                    peak = max(meaningful_since, key=lambda s: float(s.deviation_score or 0))
                    is_meaningful = True
                    deviation_score = float(peak.deviation_score or 0)
                    peak_pct = float(peak.raw_pct_change or 0)
                    peak_price = float(peak.current_price)
                    peak_verb = "climbed to" if peak_pct >= 0 else "dropped to"
                    since_visit_text = (
                        f"Since your last visit: {peak_verb} \u20b9{peak_price:.2f} ({peak_pct:+.2f}%) at its most unusual point "
                        f"-- {peak.reason_text} Now back at \u20b9{last_price:.2f}."
                    )
                else:
                    since_visit_text = (
                        f"No significant change since your last visit "
                        f"(\u20b9{first_price:.2f} \u2192 \u20b9{last_price:.2f}, {net_change:+.2f}%)."
                    )

        rows.append({
            "symbol": symbol,
            "price": float(latest.current_price) if latest.current_price is not None else None,
            "change_rupees": (
                float(latest.current_price) - float(latest.prev_close)
                if latest.current_price is not None and latest.prev_close is not None else None
            ),
            "raw_pct_change": float(latest.raw_pct_change) if latest.raw_pct_change is not None else None,
            "volume": latest.volume,
            "open_price": float(latest.open_price) if latest.open_price is not None else None,
            "day_high": float(latest.day_high) if latest.day_high is not None else None,
            "day_low": float(latest.day_low) if latest.day_low is not None else None,
            "prev_close": float(latest.prev_close) if latest.prev_close is not None else None,
            "deviation_score": deviation_score,
            "meter_width": min(deviation_score / 6 * 100, 100),
            "is_meaningful": is_meaningful,
            "is_new_since_checkin": is_new,
            "reason_text": reason,
            "since_visit_text": since_visit_text,
            "baseline_avg_move": float(baseline.avg_daily_move) if baseline and baseline.avg_daily_move else None,
            "baseline_std_dev": float(baseline.std_dev_move) if baseline and baseline.std_dev_move else None,
        })

    rows.sort(key=lambda r: (r["is_meaningful"] and r["is_new_since_checkin"], r["deviation_score"]), reverse=True)
    return rows


def mark_watchlist_seen(user_id: int, ranked: list[dict], db: Session) -> None:
    now = datetime.utcnow()
    for row in ranked:
        checkin = db.get(WatchlistCheckin, {"user_id": user_id, "stock_symbol": row["symbol"]})
        if checkin:
            checkin.last_seen_at = now
        else:
            db.add(WatchlistCheckin(user_id=user_id, stock_symbol=row["symbol"], last_seen_at=now))
    db.commit()


@router.get("/watchlist/{user_id}/data")
def watchlist_data(user_id: int, db: Session = Depends(get_db)):
    return get_ranked_watchlist(user_id, db)


@router.post("/watchlist/{user_id}/chat")
def chat(user_id: int, payload: dict = Body(...), db: Session = Depends(get_db)):
    language = payload.get("language", "English")
    mode = payload.get("mode")
    message = payload.get("message")
    symbol = payload.get("symbol")
    ranked = get_ranked_watchlist(user_id, db)
    reply = chat_response(ranked, language=language, mode=mode, user_message=message, symbol=symbol)
    return {"reply": reply}