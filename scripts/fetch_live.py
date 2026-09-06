"""
Background loop: fetches live prices for every stock on a user's
watchlist every 30 seconds.

"""
import argparse
import time
from sqlalchemy import select
from app.db import SessionLocal
from app.models import WatchlistItem
from app.services.live_fetcher import fetch_and_score_one

FETCH_INTERVAL_SECONDS = 30


def fetch_and_score_live(user_id: int):
    db = SessionLocal()
    try:
        items = db.execute(
            select(WatchlistItem).where(WatchlistItem.user_id == user_id)
        ).scalars().all()
        for item in items:
            fetch_and_score_one(db, item.stock_symbol, user_id=user_id)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--user-id", type=int, default=1)
    args = parser.parse_args()

    if args.loop:
        while True:
            fetch_and_score_live(user_id=args.user_id)
            print(f"Sleeping {FETCH_INTERVAL_SECONDS}s before next fetch...")
            time.sleep(FETCH_INTERVAL_SECONDS)
    else:
        fetch_and_score_live(user_id=args.user_id)