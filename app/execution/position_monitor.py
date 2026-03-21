import asyncio
import decimal
from typing import Dict, List, Optional, Callable, Awaitable
from app.exchange.protocols import ExchangeClient
from app.execution.position_tracker import PositionTracker
from app.models.domain import TradingSide
from app.core.logging import logger

class PositionMonitor:
    def __init__(
        self, 
        exchange: ExchangeClient, 
        tracker: PositionTracker,
        on_trigger: Callable[[str, str], Awaitable[None]]
    ):
        self.exchange = exchange
        self.tracker = tracker
        self.on_trigger = on_trigger
        self._is_running = False
        self._monitoring_task: Optional[asyncio.Task] = None

    async def start(self):
        if self._is_running:
            logger.warning("Position monitor is already running.")
            return
        self._is_running = True
        logger.info("Position monitor started")
        self._monitoring_task = asyncio.create_task(self._monitor_loop())

    async def _monitor_loop(self):
        while self._is_running:
            try:
                positions = self.tracker.get_all()
                for pos in positions:
                    try:
                        price = await self.exchange.get_price(pos.symbol)
                        if price <= 0: continue

                        triggered = False
                        reason = ""

                        if pos.side == TradingSide.BUY:
                            if price <= pos.stop_loss:
                                triggered, reason = True, "SL"
                            elif price >= pos.take_profit:
                                triggered, reason = True, "TP"
                            elif not pos.breakeven_moved and price >= pos.entry_price + (pos.entry_atr if pos.entry_atr else decimal.Decimal('0')):
                                pos.stop_loss = pos.entry_price
                                pos.breakeven_moved = True
                                logger.info(f"Position {pos.id} ({pos.symbol}) breakeven moved to {pos.stop_loss}")
                        else: # SELL
                            if price >= pos.stop_loss:
                                triggered, reason = True, "SL"
                            elif price <= pos.take_profit:
                                triggered, reason = True, "TP"
                            elif not pos.breakeven_moved and price <= pos.entry_price - (pos.entry_atr if pos.entry_atr else decimal.Decimal('0')):
                                pos.stop_loss = pos.entry_price
                                pos.breakeven_moved = True
                                logger.info(f"Position {pos.id} ({pos.symbol}) breakeven moved to {pos.stop_loss}")

                        if triggered:
                            logger.info(f"Position {pos.id} ({pos.symbol}) triggered {reason} at {price}")
                            await self.on_trigger(pos.id, reason)
                    except Exception as e:
                        logger.error(f"Error monitoring {pos.symbol}: {e}")

                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Position monitor global loop error: {e}")
                await asyncio.sleep(5)

    async def stop(self):
        self._is_running = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
        logger.info("Position monitor stopped")
