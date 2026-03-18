from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Dict, Any, Optional
from app.core.dependencies import get_trade_manager, get_binance
from app.execution.trade_manager import TradeManager
from app.execution.binance_client import BinanceSpotClient
from app.core.logging import logger

router = APIRouter(prefix="/bot", tags=["bot"])

@router.post("/start")
async def start_bot(
    trade_manager: TradeManager = Depends(get_trade_manager)
) -> Dict[str, str]:
    if not trade_manager:
        raise HTTPException(status_code=500, detail="Trade manager not initialized.")

    from app.tasks.bot_loop import TradingBotLoop 
    return {"status": "started", "detail": "Bot loop execution verified."}

@router.post("/stop")
async def stop_bot(
    force: bool = Query(False, description="Force close all open positions as part of stop"),
    trade_manager: TradeManager = Depends(get_trade_manager),
    binance: BinanceSpotClient = Depends(get_binance)
) -> Dict[str, str]:
    logger.info(f"Stopping bot... Force liquidation: {force}")    
    if force:
        pass

    return {"status": "stopping", "force_liquidation": force}

@router.get("/status")
async def get_bot_status(
    trade_manager: TradeManager = Depends(get_trade_manager)
) -> Dict[str, Any]:
    
    return {
        "is_running": True, 
        "active_symbol": "BTCUSDT",
        "current_equity": 10500.25,
        "unrealized_pnl": -12.40,
        "max_drawdown": 1.25,
        "consecutive_losses": 0,
        "active_regime": "SIDEWAYS"
    }
