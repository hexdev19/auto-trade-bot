import asyncio
from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, List, Optional
from binance import BinanceSocketManager
from app.execution.binance_client import BinanceSpotClient
from app.models.domain import Candle, TradingSide, BotStatus
from app.core.logging import logger
from app.core.config import settings
from app.notifications.telegram import TelegramNotifier
from app.risk.engine import RiskEngine
from app.notifications.templates import emergency_halt

class OrderBookStore:
    def __init__(self):
        self.bids: List[List[Decimal]] = []
        self.asks: List[List[Decimal]] = []

    def update(self, bids: List, asks: List):
        self.bids = [[Decimal(str(p)), Decimal(str(q))] for p, q in bids]
        self.asks = [[Decimal(str(p)), Decimal(str(q))] for p, q in asks]

    def get_depth_imbalance(self) -> Decimal:
        bid_vol = sum(q for _, q in self.bids)
        ask_vol = sum(q for _, q in self.asks)
        return bid_vol / ask_vol if ask_vol > 0 else Decimal('1')

class WebSocketManager:
    def __init__(self, binance_client: BinanceSpotClient, notifier: TelegramNotifier, risk_engine: RiskEngine):
        self.client = binance_client
        self.notifier = notifier
        self.risk_engine = risk_engine
        self._bsm = BinanceSocketManager(self.client._client)
        self.price_queue = asyncio.Queue()
        self.candle_queues: Dict[str, asyncio.Queue[Candle]] = {}
        self.orderbooks: Dict[str, OrderBookStore] = {}
        self._tasks: List[asyncio.Task] = []

    async def start(self):
        for symbol in settings.SYMBOLS_TO_TRADE:
            self.orderbooks[symbol] = OrderBookStore()
            for interval in ["1m", "5m"]:
                q_key = f"{symbol}_{interval}"
                self.candle_queues[q_key] = asyncio.Queue()
                self._tasks.append(asyncio.create_task(self._stream_kline(symbol, interval)))
            self._tasks.append(asyncio.create_task(self._stream_depth(symbol)))

    async def _stream_kline(self, symbol: str, interval: str):
        retries = 0
        while retries < 5:
            try:
                async with self._bsm.kline_socket(symbol, interval) as stream:
                    while True:
                        res = await stream.recv()
                        k = res['k']
                        if k['x']:
                            candle = Candle(
                                symbol=symbol,
                                timestamp=datetime.fromtimestamp(k['t'] / 1000, tz=timezone.utc),
                                open=Decimal(k['o']),
                                high=Decimal(k['h']),
                                low=Decimal(k['l']),
                                close=Decimal(k['c']),
                                volume=Decimal(k['v'])
                            )
                            await self.candle_queues[f"{symbol}_{interval}"].put(candle)
                        if interval == "1m":
                            await self.price_queue.put(Decimal(k['c']))
            except Exception as e:
                logger.error(f"WS Kline error {symbol} {interval}: {e}")
                retries += 1
                await asyncio.sleep(2 ** retries)
        logger.error(f"WS Kline {symbol} {interval} failed permanently")
        self.risk_engine.set_status(BotStatus.PAUSED)
        await self.notifier.send(emergency_halt("WebSocket stream permanently disconnected. Bot paused. Manual restart required."))
        await self.candle_queues[f"{symbol}_{interval}"].put(None)
        return

    async def _stream_depth(self, symbol: str):
        retries = 0
        while retries < 5:
            try:
                async with self._bsm.depth_socket(symbol, depth="20") as stream:
                    while True:
                        res = await stream.recv()
                        self.orderbooks[symbol].update(res['bids'], res['asks'])
            except Exception as e:
                logger.error(f"WS Depth error {symbol}: {e}")
                retries += 1
                await asyncio.sleep(2 ** retries)

    async def stop(self):
        for t in self._tasks: t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
