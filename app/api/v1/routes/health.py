from fastapi import APIRouter, Depends
from datetime import datetime
from typing import Dict, Any
from app.core.dependencies import get_binance, get_regime_engine, get_trade_manager, get_risk_engine, get_strategy_router
from app.execution.binance_client import BinanceSpotClient
from app.regime.engine import MarketRegimeEngine
from app.execution.trade_manager import TradeManager
from app.risk.engine import RiskEngine
from app.strategies.router import StrategyRouter
from decimal import Decimal

router = APIRouter(prefix="/health", tags=["health"])

app_startup_time = datetime.utcnow()

@router.get("/")
async def get_health(
    binance: BinanceSpotClient = Depends(get_binance),
    regime_engine: MarketRegimeEngine = Depends(get_regime_engine),
    trade_manager: TradeManager = Depends(get_trade_manager),
    risk_engine: RiskEngine = Depends(get_risk_engine),
    strategy_router: StrategyRouter = Depends(get_strategy_router)
) -> Dict[str, Any]:    
    uptime = datetime.utcnow() - app_startup_time
    regime = regime_engine.get_current_regime().value if regime_engine else "UNKNOWN"
    confidence = regime_engine.get_regime_confidence() if regime_engine else 0.0
    indicators = regime_engine.get_indicator_snapshot() if regime_engine else {}
    bot_status = risk_engine.get_metrics().bot_status.value if risk_engine else "UNKNOWN"
    open_positions = len(trade_manager.get_open_positions()) if trade_manager else 0
    paused = strategy_router.is_trading_paused() if strategy_router else False
    active_strategy = strategy_router.get_active_strategy().name if strategy_router else "UNKNOWN"
    
    return {
        "status": "ok",
        "bot_status": bot_status,
        "regime": regime,
        "regime_confidence": confidence,
        "active_strategy": active_strategy,
        "paused": paused,
        "open_positions": open_positions,
        "indicators": indicators,
        "uptime_seconds": int(uptime.total_seconds()),
        "ws_connected": binance is not None
    }
