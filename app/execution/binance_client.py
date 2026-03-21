import decimal
import asyncio
from decimal import Decimal
from typing import Dict, Any, List, Optional
from binance import AsyncClient
from binance.exceptions import BinanceAPIException
from app.core.config import settings
from app.core.logging import logger
from app.models.domain import Candle, TradingSide

class InsufficientBalanceError(Exception):
    pass

class BinanceSpotClient:
    def __init__(self):
        self._client: Optional[AsyncClient] = None
        self._api_key = settings.BINANCE_API_KEY.get_secret_value()
        self._api_secret = settings.BINANCE_SECRET_KEY.get_secret_value()
        self._testnet = settings.BINANCE_TESTNET
        self._symbol_cache: Dict[str, Dict[str, Any]] = {}

    @classmethod
    async def create(cls) -> "BinanceSpotClient":
        instance = cls()
        instance._client = await AsyncClient.create(
            api_key=instance._api_key,
            api_secret=instance._api_secret,
            testnet=instance._testnet
        )
        return instance

    async def close(self) -> None:
        if self._client:
            await self._client.close_connection()

    async def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        if symbol not in self._symbol_cache:
            info = await self._client.get_symbol_info(symbol)
            if not info: raise ValueError(f"Invalid symbol: {symbol}")
            filters = {f['filterType']: f for f in info['filters']}
            self._symbol_cache[symbol] = {
                "step_size": decimal.Decimal(filters['LOT_SIZE']['stepSize']),
                "min_notional": decimal.Decimal(filters['NOTIONAL']['minNotional']),
                "tick_size": decimal.Decimal(filters['PRICE_FILTER']['tickSize'])
            }
        return self._symbol_cache[symbol]

    async def _place_order(self, symbol: str, side: str, quantity: Decimal) -> Dict[str, Any]:
        retries = 0
        backoffs = [1, 2, 4]
        
        while retries <= 3:
            try:
                qty_str = f"{quantity:f}"
                order = await self._client.create_order(
                    symbol=symbol,
                    side=side,
                    type="MARKET",
                    quantity=qty_str
                )
                logger.info(f"Order success: {order['orderId']} | Price: {order.get('fills', [{}])[0].get('price', 'N/A')}")
                return order
            except BinanceAPIException as e:
                if e.code == -1121: raise ValueError("Invalid symbol")
                if e.code == -2010: raise InsufficientBalanceError("Insufficient balance")
                if e.code == -1013 and retries == 0:
                    info = await self.get_symbol_info(symbol)
                    quantity = (quantity // info['step_size']) * info['step_size']
                    retries += 1
                    continue
                
                if retries < 3:
                    await asyncio.sleep(backoffs[retries])
                    retries += 1
                else:
                    logger.error(f"Binance order failed after retries: {e}")
                    raise
        return {}

    async def place_market_order(self, symbol: str, side: TradingSide, quantity: decimal.Decimal) -> Dict[str, Any]:
        if side == TradingSide.BUY:
            return await self.place_market_buy(symbol, quantity)
        else:
            return await self.place_market_sell(symbol, quantity)

    async def place_market_buy(self, symbol: str, quantity: decimal.Decimal) -> Dict[str, Any]:
        return await self._place_order(symbol, "BUY", quantity)

    async def place_market_sell(self, symbol: str, quantity: decimal.Decimal) -> Dict[str, Any]:
        return await self._place_order(symbol, "SELL", quantity)

    async def get_balance(self, asset: str) -> decimal.Decimal:
        if not self._client: return decimal.Decimal('0')
        res = await self._client.get_asset_balance(asset=asset)
        return decimal.Decimal(str(res['free'])) if res else decimal.Decimal('0')

    async def get_price(self, symbol: str) -> decimal.Decimal:
        if not self._client: return decimal.Decimal('0')
        res = await self._client.get_symbol_ticker(symbol=symbol)
        return decimal.Decimal(str(res['price'])) if res else decimal.Decimal('0')

    async def get_asset_balance(self, asset: str) -> decimal.Decimal:
        balance = await self._client.get_asset_balance(asset=asset)
        return decimal.Decimal(balance["free"]) if balance else decimal.Decimal("0")

    async def get_account_balance(self, asset: str = "USDT") -> decimal.Decimal:
        return await self.get_asset_balance(asset)

    async def get_current_price(self, symbol: str) -> decimal.Decimal:
        ticker = await self._client.get_symbol_ticker(symbol=symbol)
        return decimal.Decimal(ticker["price"])

    async def get_klines(self, symbol: str, interval: str, limit: int = 100) -> List[Candle]:
        from datetime import datetime
        klines = await self._client.get_klines(symbol=symbol, interval=interval, limit=limit)
        return [
            Candle(
                symbol=symbol,
                timestamp=datetime.fromtimestamp(k[0] / 1000),
                open=decimal.Decimal(str(k[1])),
                high=decimal.Decimal(str(k[2])),
                low=decimal.Decimal(str(k[3])),
                close=decimal.Decimal(str(k[4])),
                volume=decimal.Decimal(str(k[5]))
            ) for k in klines
        ]
