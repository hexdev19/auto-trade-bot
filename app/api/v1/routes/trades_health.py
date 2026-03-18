from fastapi import APIRouter, Depends
from app.core.dependencies import get_repository
from app.db.repository import TradingRepository
from app.models.schemas import OrderResponse, TradeStatsResponse
from typing import List, Dict, Any

trades_router = APIRouter(prefix="/trades", tags=["trades"])
health_router = APIRouter(prefix="/health", tags=["health"])

@trades_router.get("/open")
async def get_open_positions(repo: TradingRepository = Depends(get_repository)) -> List[Any]:
    return await repo.get_open_positions()

@trades_router.get("/history")
async def get_trade_history(repo: TradingRepository = Depends(get_repository), limit: int = 100) -> List[Any]:
    return await repo.get_trade_history(limit=limit)

@health_router.get("/")
async def health_check() -> Dict[str, str]:
    return {"status": "ok", "version": "v2.0-async"}
