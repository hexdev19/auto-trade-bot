from fastapi import APIRouter, Depends, Query
from typing import List, Dict, Any, Optional
from app.core.dependencies import get_db, get_trade_manager, get_repository
from app.db.repository import TradingRepository
from app.execution.trade_manager import TradeManager
from app.models.schemas import OrderResponse, TradeStatsResponse
from decimal import Decimal
import dataclasses

router = APIRouter(prefix="/trades", tags=["trades"])

@router.get("/")
async def get_trade_history(
    repo: TradingRepository = Depends(get_repository),
    limit: int = Query(50, ge=1, le=100)
) -> List[Dict[str, Any]]:
    trades = await repo.get_recent_trades(limit=limit)
    return [
        {
            "id": t.id,
            "symbol": t.symbol,
            "side": t.side,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "quantity": t.quantity,
            "pnl": t.pnl,
            "pnl_percent": t.pnl_percent,
            "opened_at": t.opened_at,
            "closed_at": t.closed_at
        } for t in trades
    ]

@router.get("/open")
async def get_open_positions(
    trade_manager: TradeManager = Depends(get_trade_manager)
) -> List[Dict[str, Any]]:
    if not trade_manager: return []
    positions = trade_manager.get_open_positions()
    return [dataclasses.asdict(p) for p in positions]

@router.get("/stats")
async def get_trade_stats(
    repo: TradingRepository = Depends(get_repository)
) -> Dict[str, Any]:    
    return await repo.get_trade_stats()
