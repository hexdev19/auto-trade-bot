import asyncio
import decimal
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.models.domain import TradeSignal, OpenPosition, ClosedTrade, TradingSide, RiskStatus
from app.exchange.protocols import ExchangeClient
from app.exchange.order_types import OrderResult
from app.db.repository import TradingRepository
from app.execution.position_tracker import PositionTracker
from app.notifications.notifier import NotifierProtocol
from app.notifications.templates import trade_closed
from app.core.logging import logger

class OrderExecutionService:
    def __init__(
        self, 
        exchange: ExchangeClient, 
        repository: TradingRepository, 
        tracker: PositionTracker,
        notifier: NotifierProtocol
    ):
        self.exchange = exchange
        self.repository = repository
        self.tracker = tracker
        self.notifier = notifier
        self._lock = asyncio.Lock()

    async def execute_signal(self, signal: TradeSignal, risk_decision: Any) -> Optional[OrderResult]:
        if risk_decision.status != RiskStatus.APPROVED:
            logger.warning(f"Risk rejected signal for {signal.symbol}: {risk_decision.reason}")
            return None

        async with self._lock:
            if self.tracker.has_position(signal.symbol):
                logger.warning(f"Position already exists for {signal.symbol}, skipping signal")
                return None

            try:
                # 1. Place Order
                order_resp = await self.exchange.place_market_order(
                    signal.symbol, 
                    signal.side, 
                    risk_decision.max_quantity
                )
                
                # 2. Extract Price
                price = decimal.Decimal(str(order_resp["fills"][0]["price"]))
                
                # 3. Create Position
                pos = OpenPosition(
                    id=order_resp["clientOrderId"],
                    symbol=signal.symbol,
                    side=signal.side,
                    entry_price=price,
                    quantity=risk_decision.max_quantity,
                    stop_loss=risk_decision.adjusted_sl or signal.stop_loss,
                    take_profit=risk_decision.adjusted_tp or signal.take_profit,
                    entry_atr=decimal.Decimal(str(signal.indicators.get("atr", 0)))
                )

                # 4. Update Tracker
                await self.tracker.add(pos)

                # 5. Record in DB
                trade_data = {
                    "id": pos.id,
                    "symbol": pos.symbol,
                    "side": pos.side.value,
                    "entry_price": pos.entry_price,
                    "quantity": pos.quantity,
                    "stop_loss": pos.stop_loss,
                    "take_profit": pos.take_profit,
                    "is_open": True,
                    "strategy_name": signal.indicators.get("strategy", "unknown"),
                    "regime": signal.regime.value
                }
                await self.repository.save_trade(trade_data)

                logger.info(f"Successfully opened {signal.side} position for {signal.symbol} at {price}")
                return OrderResult(
                    order_id=pos.id,
                    symbol=pos.symbol,
                    side=pos.side,
                    quantity=pos.quantity,
                    price=price,
                    value=price * pos.quantity,
                    status="FILLED",
                    raw_response=order_resp
                )

            except Exception as e:
                logger.error(f"Failed to execute signal for {signal.symbol}: {str(e)}")
                return None

    async def close_position(self, pos_id: str, reason: str = "SIGNAL") -> Optional[ClosedTrade]:
        pos = self.tracker.get(pos_id)
        if not pos:
            logger.warning(f"Attempted to close nonexistent position {pos_id}")
            return None

        async with self._lock:
            # Double check inside lock
            pos = await self.tracker.remove(pos_id)
            if not pos: return None

            try:
                # 1. Place Closing Order
                exit_side = TradingSide.SELL if pos.side == TradingSide.BUY else TradingSide.BUY
                order_resp = await self.exchange.place_market_order(pos.symbol, exit_side, pos.quantity)
                
                # 2. Extract Price
                exit_price = decimal.Decimal(str(order_resp["fills"][0]["price"]))
                
                # 3. Calculate PnL
                if pos.side == TradingSide.BUY:
                    pnl = (exit_price - pos.entry_price) * pos.quantity
                else:
                    pnl = (pos.entry_price - exit_price) * pos.quantity
                    
                pnl_pct = (pnl / (pos.entry_price * pos.quantity)) * 100 if pos.entry_price > 0 else decimal.Decimal('0')

                # 4. Record in DB
                status_data = {
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "is_open": False,
                    "closed_at": datetime.utcnow(),
                    "exit_reason": reason
                }
                await self.repository.update_trade_status(pos_id, status_data)

                closed = ClosedTrade(
                    id=pos_id,
                    symbol=pos.symbol,
                    side=pos.side,
                    entry_price=pos.entry_price,
                    exit_price=exit_price,
                    quantity=pos.quantity,
                    pnl=pnl,
                    pnl_percent=pnl_pct,
                    opened_at=pos.opened_at
                )

                # 5. Notify
                await self.notifier.send(trade_closed(closed, "UNKNOWN", reason))
                
                logger.info(f"Closed {pos.symbol} position {pos_id}. PnL: {pnl} ({pnl_pct}%)")
                return closed

            except Exception as e:
                logger.error(f"Failed to close position {pos_id} for {pos.symbol}: {str(e)}")
                await self.tracker.add(pos)
                return None
