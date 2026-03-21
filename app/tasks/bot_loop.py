import asyncio
import decimal
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.core.config import settings
from app.core.logging import logger
from app.models.domain import Candle, TradingSide, MarketRegime, RiskStatus, BotStatus
from app.data.ws_manager import WebSocketManager
from app.data.candle_store import CandleStore
from app.regime.engine import MarketRegimeEngine
from app.strategies.router import StrategyRouter
from app.risk.engine import RiskEngine
from app.execution.order_service import OrderExecutionService
from app.execution.position_monitor import PositionMonitor
from app.notifications.notifier import NotifierProtocol
from app.notifications.templates import trade_opened, regime_changed, risk_alert
from sqlalchemy.ext.asyncio import async_sessionmaker

async def run_bot_loop(
    ws_manager: WebSocketManager,
    candle_store: CandleStore,
    regime_engine: MarketRegimeEngine,
    strategy_router: StrategyRouter,
    risk_engine: RiskEngine,
    order_service: OrderExecutionService,
    position_monitor: PositionMonitor,
    notifier: NotifierProtocol,
    session_factory: async_sessionmaker
) -> None:
    symbol = settings.TRADING_SYMBOL
    logger.info(f"Bot loop started for {symbol}")

    while True:
        try:
            candle = await ws_manager.candle_queues[f"{symbol}_1m"].get()
            if candle is None:
                logger.error("Received permanent failure sentinel from ws_manager. Halting bot loop.")
                break
            candle_store.append(candle, "1m")
            
            while not ws_manager.candle_queues[f"{symbol}_5m"].empty():
                c5 = await ws_manager.candle_queues[f"{symbol}_5m"].get()
                candle_store.append(c5, "5m")

            old_regime = strategy_router.get_current_regime()
            new_regime = regime_engine.update(candle_store.get("1m"))
            changed = strategy_router.update_regime(new_regime)

            if changed and order_service.tracker.has_position(symbol):
                if new_regime == MarketRegime.HIGH_VOLATILITY:
                    # Emergency close
                    positions = [p for p in order_service.tracker.get_all() if p.symbol == symbol]
                    for p in positions:
                        await order_service.close_position(p.id, "REGIME_CHANGE_VOLATILITY")
                else:
                    for pos in order_service.tracker.get_all():
                        if pos.symbol == symbol and not pos.breakeven_moved:
                            await order_service.tracker.update_sl(pos.id, pos.entry_price)
                            pos.breakeven_moved = True # Tracker doesn't currently store this in DB, but tracker state is updated
                
                snap = regime_engine.get_indicator_snapshot()
                await notifier.send(regime_changed(old_regime, new_regime, snap))

            if strategy_router.is_trading_paused(): continue
            if order_service.tracker.has_position(symbol): continue

            candles_5m = candle_store.get("5m")
            if not candle_store.is_ready("5m", settings.EMA_SLOW): continue
            
            ob = ws_manager.orderbooks.get(symbol)
            strategy = strategy_router.get_active_strategy()
            signal = await strategy.generate_signal(candle_store.get("1m"), candles_5m, {}, new_regime, {
                "bid_depth": ob.bids[0][1] if ob and ob.bids else decimal.Decimal('0'),
                "ask_depth": ob.asks[0][1] if ob and ob.asks else decimal.Decimal('0'),
                "bid": ob.bids[0][0] if ob and ob.bids else decimal.Decimal('0'),
                "ask": ob.asks[0][0] if ob and ob.asks else decimal.Decimal('0')
            } if ob else None)

            if not signal: continue

            async with session_factory() as session:
                balance = await ws_manager.client.get_account_balance("USDT")
                from app.db.repository import TradingRepository
                repo = TradingRepository(session)
                daily_pnl = await repo.get_daily_pnl()
                
                decision = await risk_engine.validate_trade(signal, balance, daily_pnl)
                if decision.status != RiskStatus.APPROVED:
                    logger.info(f"Trade blocked: {decision.reason}")
                    metrics = risk_engine.get_metrics()
                    # Simplified notification logic
                    if metrics.bot_status != BotStatus.RUNNING:
                         await notifier.send(risk_alert(decision.reason, daily_pnl, balance))
                    continue

                # Use cloned order service with session
                session_order_service = order_service.clone_with_repo(repo)
                result = await session_order_service.execute_signal(signal, decision)
                
                if result:
                    pos = order_service.tracker.get(result.order_id)
                    if pos:
                        await notifier.send(trade_opened(pos, strategy.name, new_regime.value))

        except Exception as e:
            logger.error(f"Loop error: {e}")
            await asyncio.sleep(1)
