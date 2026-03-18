from fastapi import APIRouter, Depends, Query
from typing import List, Dict, Any, Optional
from app.core.dependencies import get_db, get_trade_manager, get_repository
from app.db.repository import TradingRepository
from app.execution.trade_manager import TradeManager
from app.models.schemas import OrderResponse, TradeStatsResponse
from decimal import Decimal

router = APIRouter(prefix="/trades", tags=["trades"])

@router.get("/")
async def get_trade_history(
    repo: TradingRepository = Depends(get_repository),
    limit: int = Query(10, ge=1, le=100),
    offset: int = 0
) -> List[Dict[str, Any]]:
    trades = await repo.get_trade_history(limit=limit)
    return [{"id": t.id, "symbol": t.symbol, "pnl": t.pnl} for t in trades]

@router.get("/open")
async def get_open_positions(
    trade_manager: TradeManager = Depends(get_trade_manager)
) -> List[Dict[str, Any]]:
    return [
        {
            "id": "abc-123",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "entry": 65000.5,
            "current": 65120.2,
            "unrealized_pnl": 12.45
        }
    ]

@router.get("/stats")
async def get_trade_stats(
    repo: TradingRepository = Depends(get_repository)
) -> Dict[str, Any]:    
    return {
        "win_rate": 0.65,
        "total_pnl": Decimal('1250.40'),
        "sharpe_ratio": 1.45,
        "max_drawdown": 3.2,
        "by_strategy": {
            "TrendStrategy": {"trades": 12, "win_rate": 0.7},
            "ScalpingStrategy": {"trades": 8, "win_rate": 0.55}
        }
    }
