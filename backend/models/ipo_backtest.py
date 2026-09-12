from dataclasses import dataclass


@dataclass
class IPOBacktestResult:
    ipo_id: int
    company_name: str

    strategy_result: str

    entry_price: float | None
    exit_price: float | None

    stop_loss_price: float | None

    profit_loss: float | None
    profit_loss_percent: float | None

    outcome: str
    reason: str