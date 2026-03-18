from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Dict, Any, Optional
from app.core.dependencies import get_trade_manager, get_risk_engine, get_regime_engine, get_strategy_router, get_binance
from app.execution.trade_manager import TradeManager
from app.risk.engine import RiskEngine
from app.regime.engine import MarketRegimeEngine
from app.strategies.router import StrategyRouter
from app.models.domain import BotStatus
from app.core.logging import logger

router = APIRouter(prefix="/bot", tags=["bot"])

@router.post("/start")
async def start_bot(
    risk_engine: RiskEngine = Depends(get_risk_engine),
    regime_engine: MarketRegimeEngine = Depends(get_regime_engine)
) -> Dict[str, Any]:
    if not risk_engine:
        raise HTTPException(status_code=500, detail="Risk engine not initialized.")

    if risk_engine.get_metrics().bot_status == BotStatus.STOPPED:
        risk_engine.set_status(BotStatus.RUNNING)

    regime = regime_engine.get_current_regime().value if regime_engine else "UNKNOWN"
    return {"started": True, "regime": regime}

@router.post("/stop")
async def stop_bot(
    force: bool = Query(False, description="Force close all open positions as part of stop"),
    trade_manager: TradeManager = Depends(get_trade_manager),
    risk_engine: RiskEngine = Depends(get_risk_engine)
) -> Dict[str, Any]:
    logger.info(f"Stopping bot... Force liquidation: {force}")    
    closed_count = 0
    if risk_engine:
        if risk_engine.get_metrics().bot_status == BotStatus.RUNNING:
            risk_engine.set_status(BotStatus.STOPPED)
            if force and trade_manager:
                closed_positions = await trade_manager.close_all_positions(reason="MANUAL")
                closed_count = len(closed_positions)

    return {"stopped": True, "open_positions_closed": closed_count}

@router.get("/status")
async def get_bot_status(
    trade_manager: TradeManager = Depends(get_trade_manager),
    risk_engine: RiskEngine = Depends(get_risk_engine),
    regime_engine: MarketRegimeEngine = Depends(get_regime_engine),
    strategy_router: StrategyRouter = Depends(get_strategy_router)
) -> Dict[str, Any]:
    metrics = risk_engine.get_metrics() if risk_engine else None
    bot_status = metrics.bot_status.value if metrics else "UNKNOWN"
    regime = regime_engine.get_current_regime().value if regime_engine else "UNKNOWN"
    active_strategy = strategy_router.get_active_strategy().name if strategy_router else "UNKNOWN"
    open_positions = len(trade_manager.get_open_positions()) if trade_manager else 0
    
    return {
        "bot_status": bot_status,
        "regime": regime,
        "active_strategy": active_strategy,
        "open_positions": open_positions,
        "peak_balance": float(metrics.peak_balance) if metrics else 0.0,
        "consecutive_losses": metrics.consecutive_losses if metrics else 0,
        "cooldown_active": metrics.cooldown_active if metrics else False
    }
