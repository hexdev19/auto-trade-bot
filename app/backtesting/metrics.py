import numpy as np
import decimal
from dataclasses import dataclass
from typing import List, Dict, Any
from datetime import datetime
from app.models.domain import ClosedTrade

@dataclass
class BacktestMetrics:
    total_return_pct: decimal.Decimal
    win_rate: decimal.Decimal
    profit_factor: decimal.Decimal
    max_drawdown_pct: decimal.Decimal
    sharpe_ratio: float
    sortino_ratio: float
    avg_win: decimal.Decimal
    avg_loss: decimal.Decimal
    total_trades: int
    trades_by_strategy: Dict[str, Any]
    regime_distribution: Dict[str, float]
    regime_pnl: Dict[str, decimal.Decimal]

def calculate_metrics(trades: List[ClosedTrade], initial_balance: decimal.Decimal, final_balance: decimal.Decimal) -> BacktestMetrics:
    if not trades:
        return BacktestMetrics(decimal.Decimal('0'), decimal.Decimal('0'), decimal.Decimal('0'), decimal.Decimal('0'), 0.0, 0.0, decimal.Decimal('0'), decimal.Decimal('0'), 0, {}, {}, {})

    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    
    total_return = ((final_balance - initial_balance) / initial_balance) * 100
    win_rate = (len(wins) / len(trades)) * 100
    profit_factor = sum(wins) / abs(sum(losses)) if losses else decimal.Decimal('0')
    
    cum_pnl = np.cumsum([float(p) for p in pnls])
    peak = np.maximum.accumulate(cum_pnl)
    drawdown = (peak - cum_pnl) / (float(initial_balance) + peak)
    max_dd = np.max(drawdown) * 100
    
    daily_returns = [float(p / initial_balance) for p in pnls]
    avg_ret = np.mean(daily_returns) if daily_returns else 0
    std_ret = np.std(daily_returns) if daily_returns else 1
    sharpe = (avg_ret / std_ret) * np.sqrt(365) if std_ret > 0 else 0
    
    neg_ret = [r for r in daily_returns if r < 0]
    std_neg = np.std(neg_ret) if neg_ret else 1
    sortino = (avg_ret / std_neg) * np.sqrt(365) if std_neg > 0 else 0
    
    return BacktestMetrics(
        total_return_pct=decimal.Decimal(str(total_return)),
        win_rate=decimal.Decimal(str(win_rate)),
        profit_factor=decimal.Decimal(str(profit_factor)),
        max_drawdown_pct=decimal.Decimal(str(max_dd)),
        sharpe_ratio=float(sharpe),
        sortino_ratio=float(sortino),
        avg_win=sum(wins) / len(wins) if wins else decimal.Decimal('0'),
        avg_loss=sum(losses) / len(losses) if losses else decimal.Decimal('0'),
        total_trades=len(trades),
        trades_by_strategy={},
        regime_distribution={},
        regime_pnl={}
    )
