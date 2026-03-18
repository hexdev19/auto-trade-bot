import asyncio
from typing import Dict, Optional, List
from decimal import Decimal
from datetime import datetime
from app.execution.binance_client import BinanceSpotClient
from app.db.repository import TradingRepository
from app.models.domain import TradeSignal, OpenPosition, ClosedTrade, TradingSide, RiskDecision
from app.core.logging import logger
from app.notifications.telegram import TelegramNotifier
from app.notifications.templates import trade_closed

class TradeManager:
    def __init__(self, binance_client: BinanceSpotClient, repository: TradingRepository, notifier: TelegramNotifier):
        self.binance_client = binance_client
        self.repository = repository
        self.notifier = notifier
        self._locks: Dict[str, asyncio.Lock] = {}
        self._open_positions: Dict[str, OpenPosition] = {}

    def _get_lock(self, symbol: str) -> asyncio.Lock:
        if symbol not in self._locks: self._locks[symbol] = asyncio.Lock()
        return self._locks[symbol]

    async def try_open_position(self, symbol: str, signal: TradeSignal, risk: RiskDecision) -> bool:
        lock = self._get_lock(symbol)
        async with lock:
            if any(p.symbol == symbol for p in self._open_positions.values()): return False
            try:
                if signal.side == TradingSide.BUY:
                    order = await self.binance_client.place_market_buy(symbol, risk.max_quantity)
                else:
                    order = await self.binance_client.place_market_sell(symbol, risk.max_quantity)
                
                entry_price = Decimal(str(order["fills"][0]["price"]))
                pos = OpenPosition(
                    id=order["clientOrderId"],
                    symbol=symbol,
                    side=signal.side,
                    entry_price=entry_price,
                    quantity=risk.max_quantity,
                    stop_loss=risk.adjusted_sl,
                    take_profit=risk.adjusted_tp,
                    entry_atr=Decimal(str(signal.indicators.get("atr", 0)))
                )
                
                trade_data = {
                    "id": pos.id,
                    "symbol": pos.symbol,
                    "side": pos.side.value,
                    "entry_price": pos.entry_price,
                    "quantity": pos.quantity,
                    "stop_loss": pos.stop_loss,
                    "take_profit": pos.take_profit,
                    "is_open": True,
                    "strategy": signal.indicators.get("strategy", "unknown"),
                    "regime": signal.regime.value
                }
                await self.repository.save_trade(trade_data)
                self._open_positions[pos.id] = pos
                return True
            except Exception as e:
                logger.error(f"Open failed for {symbol}: {e}")
                return False

    async def close_position(self, pos_id: str, reason: str = "SIGNAL") -> Optional[ClosedTrade]:
        pos = self._open_positions.get(pos_id)
        if not pos: return None
        
        lock = self._get_lock(pos.symbol)
        async with lock:
            if pos_id not in self._open_positions: return None
            try:
                if pos.side == TradingSide.BUY:
                    order = await self.binance_client.place_market_sell(pos.symbol, pos.quantity)
                else:
                    order = await self.binance_client.place_market_buy(pos.symbol, pos.quantity)
                
                exit_price = Decimal(str(order["fills"][0]["price"]))
                pnl = (exit_price - pos.entry_price) * pos.quantity if pos.side == TradingSide.BUY else (pos.entry_price - exit_price) * pos.quantity
                pnl_pct = (pnl / (pos.entry_price * pos.quantity)) * 100 if pos.entry_price > 0 else Decimal('0')
                
                status_data = {
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "pnl_percent": pnl_pct,
                    "is_open": False,
                    "closed_at": datetime.utcnow(),
                    "exit_reason": reason
                }
                await self.repository.update_trade_status(pos_id, status_data)
                closed = ClosedTrade(
                    id=pos_id, symbol=pos.symbol, side=pos.side,
                    entry_price=pos.entry_price, exit_price=exit_price,
                    quantity=pos.quantity, pnl=pnl, pnl_percent=pnl_pct,
                    opened_at=pos.opened_at
                )
                self._open_positions.pop(pos_id)
                await self.notifier.send(trade_closed(closed, "UNKNOWN", reason))
                return closed
            except Exception as e:
                logger.error(f"Close failed for {pos.symbol}: {e}")
                return None

    async def close_all_positions(self, reason: str) -> List[ClosedTrade]:
        tasks = [self.close_position(pid, reason) for pid in list(self._open_positions.keys())]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    def get_open_positions(self) -> List[OpenPosition]: return list(self._open_positions.values())
    def has_open_position(self, symbol: str) -> bool: return any(p.symbol == symbol for p in self._open_positions.values())
