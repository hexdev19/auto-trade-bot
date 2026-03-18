import asyncio
from typing import List, Dict, Any, Callable
from decimal import Decimal
from app.core.config import settings
from app.core.logging import logger
from app.models.domain import Candle, TradingSide, MarketRegime, RiskStatus
from app.data.ws_manager import WebSocketManager
from app.data.candle_store import CandleStore
from app.regime.engine import MarketRegimeEngine
from app.strategies.router import StrategyRouter
from app.risk.engine import RiskEngine
from app.execution.trade_manager import TradeManager
from app.execution.position_monitor import PositionMonitor
from app.notifications.telegram import TelegramNotifier
from app.notifications.templates import trade_opened, regime_changed
from sqlalchemy.ext.asyncio import async_sessionmaker

async def run_bot_loop(
    ws_manager: WebSocketManager,
    candle_store: CandleStore,
    regime_engine: MarketRegimeEngine,
    strategy_router: StrategyRouter,
    risk_engine: RiskEngine,
    trade_manager: TradeManager,
    position_monitor: PositionMonitor,
    notifier: TelegramNotifier,
    session_factory: async_sessionmaker
) -> None:
    symbol = settings.TRADING_SYMBOL
    logger.info(f"Bot loop started for {symbol}")

    while True:
        try:
            candle = await ws_manager.candle_queues[f"{symbol}_1m"].get()
            candle_store.append(candle, "1m")
            
            while not ws_manager.candle_queues[f"{symbol}_5m"].empty():
                c5 = await ws_manager.candle_queues[f"{symbol}_5m"].get()
                candle_store.append(c5, "5m")

            old_regime = strategy_router._current_regime
            new_regime = regime_engine.update(candle_store.get("1m"))
            changed = strategy_router.update_regime(new_regime)

            if changed and trade_manager.has_open_position(symbol):
                if new_regime == MarketRegime.HIGH_VOLATILITY:
                    await trade_manager.close_all_positions("REGIME_CHANGE_VOLATILITY")
                else:
                    for pos in trade_manager.get_open_positions():
                        if pos.symbol == symbol and not pos.breakeven_moved:
                            pos.stop_loss = pos.entry_price
                            pos.breakeven_moved = True
                
                snap = regime_engine.get_indicator_snapshot()
                await notifier.send(regime_changed(old_regime, new_regime, snap))

            if strategy_router.is_trading_paused(): continue
            if trade_manager.has_open_position(symbol): continue

            candles_5m = candle_store.get("5m")
            if not candle_store.is_ready("5m", settings.EMA_SLOW): continue
            
            ob = ws_manager.orderbooks.get(symbol)
            strategy = strategy_router.get_active_strategy()
            signal = await strategy.generate_signal(candle_store.get("1m"), candles_5m, {}, new_regime, {
                "bid_depth": ob.bids[0][1] if ob and ob.bids else Decimal('0'),
                "ask_depth": ob.asks[0][1] if ob and ob.asks else Decimal('0'),
                "bid": ob.bids[0][0] if ob and ob.bids else Decimal('0'),
                "ask": ob.asks[0][0] if ob and ob.asks else Decimal('0')
            } if ob else None)

            if not signal: continue

            async with session_factory() as session:
                balance = await ws_manager.client.get_account_balance("USDT")
                from app.db.repository import TradingRepository
                repo = TradingRepository(session)
                daily_pnl = await repo.get_daily_pnl()
                
                decision = await risk_engine.validate_trade(signal, balance, daily_pnl)
                if decision.status != RiskStatus.APPROVED:
                    logger.info(f"Rejected: {decision.reason}")
                    continue

                success = await trade_manager.try_open_position(symbol, signal, decision)
                if success:
                    pos = [p for p in trade_manager.get_open_positions() if p.symbol == symbol][-1]
                    await position_monitor.add_position(pos)
                    await notifier.send(trade_opened(pos, strategy.name, new_regime.value))

        except Exception as e:
            logger.error(f"Loop error: {e}")
            await asyncio.sleep(1)
