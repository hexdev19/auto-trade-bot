import asyncio
from typing import Dict, Set, Optional, Callable, Awaitable
from decimal import Decimal
from binance import BinanceSocketManager
from app.execution.binance_client import BinanceSpotClient
from app.models.domain import OpenPosition, TradingSide
from app.core.logging import logger

class PositionMonitor:
    def __init__(self, binance_client: BinanceSpotClient, on_trigger: Callable[[str, str, Decimal, TradingSide], Awaitable[None]]):
        self.binance_client = binance_client
        self.on_trigger = on_trigger
        self.active_positions: Dict[str, OpenPosition] = {}
        self.active_symbols: Set[str] = set()
        self._bsm: Optional[BinanceSocketManager] = None
        self._monitoring_task: Optional[asyncio.Task] = None

    async def add_position(self, position: OpenPosition):
        self.active_positions[position.id] = position
        self.active_symbols.add(position.symbol)
        if not self._monitoring_task or self._monitoring_task.done():
            self._monitoring_task = asyncio.create_task(self._run_socket_loop())

    async def _run_socket_loop(self):
        self._bsm = BinanceSocketManager(self.binance_client.client)
        while self.active_symbols:
            try:
                for symbol in list(self.active_symbols):
                    async with self._bsm.symbol_ticker_socket(symbol) as stream:
                        while symbol in self.active_symbols:
                            msg = await stream.recv()
                            await self._handle_ticker_msg(msg)
            except Exception as e:
                logger.error(f"WS monitor error: {e}")
                await asyncio.sleep(5) 

    async def _handle_ticker_msg(self, msg: Dict):
        symbol = msg['s']
        price = Decimal(str(msg['c']))
        matching = [p for p in self.active_positions.values() if p.symbol == symbol]
        for pos in matching:
            if pos.side == TradingSide.BUY:
                if price <= pos.stop_loss or price >= pos.take_profit:
                    await self._close(pos, price)
                elif not pos.breakeven_moved and price >= pos.entry_price + pos.entry_atr:
                    pos.stop_loss = pos.entry_price
                    pos.breakeven_moved = True
            else:
                if price >= pos.stop_loss or price <= pos.take_profit:
                    await self._close(pos, price)
                elif not pos.breakeven_moved and price <= pos.entry_price - pos.entry_atr:
                    pos.stop_loss = pos.entry_price
                    pos.breakeven_moved = True

    async def _close(self, pos: OpenPosition, price: Decimal):
        await self.on_trigger(pos.id, pos.symbol, price, pos.side)
        self.active_positions.pop(pos.id, None)
        if not any(p.symbol == pos.symbol for p in self.active_positions.values()):
            self.active_symbols.discard(pos.symbol)

    async def stop(self):
        if self._monitoring_task: self._monitoring_task.cancel()
        self.active_positions.clear()
        self.active_symbols.clear()
