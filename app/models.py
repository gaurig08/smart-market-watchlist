"""
SQLAlchemy models. All market data (baselines, live signals) is fetched
live via yfinance -- there is no raw historical staging table used at
runtime (stock_daily_history is only read once, during baseline
computation). No sector comparison is used anywhere (a deliberate
product decision) -- each stock is judged purely on its own history.
"""
from sqlalchemy import (
    Column, Integer, Numeric, BigInteger, Date, DateTime,
    Boolean, ForeignKey, Text, PrimaryKeyConstraint
)
from sqlalchemy.sql import func
from app.db import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    stock_symbol = Column(Text, nullable=False)
    added_at = Column(DateTime, server_default=func.now())


class StockDailyHistory(Base):
    """Raw historical data imported from Kaggle -- read ONCE by
    baseline_worker.py to compute what's 'normal' per stock. Never read
    again after that; not shown to the user directly."""
    __tablename__ = "stock_daily_history"
    id = Column(Integer, primary_key=True)
    stock_symbol = Column(Text, nullable=False, index=True)
    trade_date = Column(Date, nullable=False)
    open = Column(Numeric)
    high = Column(Numeric)
    low = Column(Numeric)
    close = Column(Numeric)
    volume = Column(BigInteger)


class StockBaseline(Base):
    __tablename__ = "stock_baselines"
    stock_symbol = Column(Text, primary_key=True)
    avg_daily_move = Column(Numeric)    
    std_dev_move = Column(Numeric)        
    avg_volume = Column(BigInteger)
    computed_at = Column(DateTime, server_default=func.now())


class StockSignal(Base):
    """One row per live fetch, per stock. 'What changed since you
    checked' compares this table's rows against
    WatchlistCheckin.last_seen_at."""
    __tablename__ = "stock_signals"
    id = Column(Integer, primary_key=True)
    stock_symbol = Column(Text, nullable=False, index=True)
    fetched_at = Column(DateTime, nullable=False)
    current_price = Column(Numeric)
    raw_pct_change = Column(Numeric)
    volume = Column(BigInteger)
    open_price = Column(Numeric)
    day_high = Column(Numeric)
    day_low = Column(Numeric)
    prev_close = Column(Numeric)
    deviation_score = Column(Numeric)        
    is_meaningful = Column(Boolean, default=False)
    reason_text = Column(Text)


class WatchlistCheckin(Base):
    """When did this user last see this stock -- powers the 'what changed' diff."""
    __tablename__ = "watchlist_checkins"
    user_id = Column(Integer, ForeignKey("users.id"))
    stock_symbol = Column(Text, nullable=False)
    last_seen_at = Column(DateTime, nullable=False)

    __table_args__ = (PrimaryKeyConstraint("user_id", "stock_symbol"),)