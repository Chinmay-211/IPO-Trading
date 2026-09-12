from backend.services.ipo_paper_performance_service import (
    IPOPaperPerformanceService,
)


def buy(
    symbol,
    quantity,
    price,
):
    return {
        "side": "BUY",
        "symbol": symbol,
        "quantity": quantity,
        "price": price,
    }


def sell(
    symbol,
    quantity,
    price,
):
    return {
        "side": "SELL",
        "symbol": symbol,
        "quantity": quantity,
        "price": price,
    }


def test_profitable_trade():
    service = IPOPaperPerformanceService(
        [
            buy("IPOONE", 10, 100),
            sell("IPOONE", 10, 110),
        ]
    )

    assert service.total_trades() == 1
    assert service.winning_trades() == 1
    assert service.losing_trades() == 0
    assert service.total_profit_loss() == 100
    assert service.win_rate() == 100


def test_losing_trade():
    service = IPOPaperPerformanceService(
        [
            buy("IPOONE", 10, 100),
            sell("IPOONE", 10, 90),
        ]
    )

    assert service.total_trades() == 1
    assert service.winning_trades() == 0
    assert service.losing_trades() == 1
    assert service.total_profit_loss() == -100
    assert service.win_rate() == 0


def test_breakeven_trade():
    service = IPOPaperPerformanceService(
        [
            buy("IPOONE", 10, 100),
            sell("IPOONE", 10, 100),
        ]
    )

    assert service.total_trades() == 1
    assert service.breakeven_trades() == 1
    assert service.total_profit_loss() == 0


def test_profit_loss_percent():
    service = IPOPaperPerformanceService(
        [
            buy("IPOONE", 10, 100),
            sell("IPOONE", 10, 110),
        ]
    )

    assert service.overall_profit_loss_percent() == 10


def test_multiple_trades():
    service = IPOPaperPerformanceService(
        [
            buy("IPOONE", 10, 100),
            sell("IPOONE", 10, 110),
            buy("IPOONE", 10, 120),
            sell("IPOONE", 10, 115),
        ]
    )

    assert service.total_trades() == 2
    assert service.winning_trades() == 1
    assert service.losing_trades() == 1
    assert service.total_profit_loss() == 50


def test_partial_exit():
    service = IPOPaperPerformanceService(
        [
            buy("IPOONE", 10, 100),
            sell("IPOONE", 5, 110),
            sell("IPOONE", 5, 120),
        ]
    )

    trades = service.get_trades()

    assert len(trades) == 2
    assert trades[0]["profit_loss"] == 50
    assert trades[1]["profit_loss"] == 100
    assert service.total_profit_loss() == 150


def test_multiple_ipos_are_separated():
    service = IPOPaperPerformanceService(
        [
            buy("IPOONE", 10, 100),
            sell("IPOONE", 10, 110),
            buy("IPOTWO", 20, 200),
            sell("IPOTWO", 20, 190),
        ]
    )

    assert service.total_profit_loss("IPOONE") == 100
    assert service.total_profit_loss("IPOTWO") == -200

    assert service.total_trades("IPOONE") == 1
    assert service.total_trades("IPOTWO") == 1


def test_summary_contains_per_ipo_results():
    service = IPOPaperPerformanceService(
        [
            buy("IPOONE", 10, 100),
            sell("IPOONE", 10, 110),
            buy("IPOTWO", 20, 200),
            sell("IPOTWO", 20, 190),
        ]
    )

    summary = service.get_summary()

    assert summary["total_trades"] == 2
    assert summary["winning_trades"] == 1
    assert summary["losing_trades"] == 1

    assert (
        summary["symbols"]["IPOONE"]["profit_loss"]
        == 100
    )

    assert (
        summary["symbols"]["IPOTWO"]["profit_loss"]
        == -200
    )


def test_symbol_summary():
    service = IPOPaperPerformanceService(
        [
            buy("IPOONE", 10, 100),
            sell("IPOONE", 10, 105),
        ]
    )

    summary = service.get_symbol_summary(
        "IPOONE"
    )

    assert summary["symbol"] == "IPOONE"
    assert summary["total_trades"] == 1
    assert summary["profit_loss"] == 50
    assert summary["profit_loss_percent"] == 5


def test_empty_service():
    service = IPOPaperPerformanceService()

    summary = service.get_summary()

    assert summary["total_trades"] == 0
    assert summary["winning_trades"] == 0
    assert summary["losing_trades"] == 0
    assert summary["win_rate"] == 0
    assert summary["profit_loss"] == 0
    assert summary["profit_loss_percent"] == 0


def test_add_order():
    service = IPOPaperPerformanceService()

    service.add_order(
        buy("IPOONE", 10, 100)
    )

    service.add_order(
        sell("IPOONE", 10, 110)
    )

    assert service.total_trades() == 1
    assert service.total_profit_loss() == 100


def test_reset():
    service = IPOPaperPerformanceService(
        [
            buy("IPOONE", 10, 100),
            sell("IPOONE", 10, 110),
        ]
    )

    service.reset()

    assert service.orders == []
    assert service.total_trades() == 0