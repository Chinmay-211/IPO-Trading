from datetime import datetime

from backend.services.live_market_paper_service import (
    LiveMarketPaperService,
)


def test_no_trade_does_not_execute():
    service = LiveMarketPaperService(
        initial_cash=100000
    )

    result = service.process_decision(
        {
            "action": "NO_TRADE",
            "symbol": "TEST",
            "reason": "Strategy rejected IPO.",
        }
    )

    assert result["action"] == "NO_TRADE"
    assert result["executed"] is False
    assert service.get_orders() == []


def test_buy_is_paper_executed():
    service = LiveMarketPaperService(
        initial_cash=100000
    )

    result = service.process_decision(
        {
            "action": "BUY",
            "symbol": "TEST",
            "quantity": 10,
            "price": 100,
        },
        timestamp=datetime(
            2026,
            8,
            31,
            9,
            20,
        ),
    )

    assert result["action"] == "BUY"
    assert result["executed"] is True
    assert result["symbol"] == "TEST"
    assert result["quantity"] == 10
    assert result["price"] == 100
    assert len(service.get_orders()) == 1


def test_buy_then_sell_creates_realized_pnl():
    service = LiveMarketPaperService(
        initial_cash=100000
    )

    service.process_decision(
        {
            "action": "BUY",
            "symbol": "TEST",
            "quantity": 10,
            "price": 100,
        }
    )

    result = service.process_decision(
        {
            "action": "SELL",
            "symbol": "TEST",
            "quantity": 10,
            "price": 110,
        }
    )

    assert result["action"] == "SELL"
    assert result["executed"] is True
    assert service.get_realized_pnl() == 100