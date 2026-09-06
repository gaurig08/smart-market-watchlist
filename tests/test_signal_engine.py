"""
Tests for the core scoring logic -- the most architecturally important
part of this project, tested independently of any live data source.
"""
from app.services.signal_engine import score_move
from app.models import StockBaseline


def make_baseline(std_dev=1.0):
    return StockBaseline(stock_symbol="TEST", avg_daily_move=1.0, std_dev_move=std_dev, avg_volume=1_000_000)


def test_normal_move_is_not_flagged():
    result = score_move(symbol="TEST", pct_move_today=0.5, volume_today=1_000_000, baseline=make_baseline(std_dev=1.0))
    assert result["is_meaningful"] is False


def test_unusual_move_is_flagged():
    result = score_move(symbol="TEST", pct_move_today=6.0, volume_today=1_000_000, baseline=make_baseline(std_dev=1.0))
    assert result["is_meaningful"] is True
    assert result["deviation_score"] >= 2.0


def test_same_raw_percent_different_stocks_score_differently():
    calm_stock = make_baseline(std_dev=0.5)
    wild_stock = make_baseline(std_dev=5.0)
    calm_result = score_move("CALM", 3.0, 1_000_000, calm_stock)
    wild_result = score_move("WILD", 3.0, 1_000_000, wild_stock)
    assert calm_result["deviation_score"] > wild_result["deviation_score"]
    assert calm_result["is_meaningful"] is True
    assert wild_result["is_meaningful"] is False


def test_low_liquidity_is_not_trusted():
    result = score_move(symbol="THIN", pct_move_today=8.0, volume_today=500, baseline=make_baseline(std_dev=1.0))
    assert result["is_meaningful"] is False
    assert "volume" in result["reason_text"].lower()


def test_zero_volatility_baseline_does_not_crash():
    result = score_move(symbol="FLAT", pct_move_today=1.0, volume_today=1_000_000, baseline=make_baseline(std_dev=0.0))
    assert isinstance(result["deviation_score"], float)