import decimal
from typing import List, Optional, Dict, Any
from app.models.domain import Candle, TradeSignal, MarketRegime, TradingSide
from app.strategies.base import BaseStrategy
from app.indicators.ema import is_ema_crossover_bullish, is_ema_crossover_bearish
from app.indicators.volume import get_volume_ratio
from app.indicators.atr import get_current_atr
from app.core.config import settings

class TrendStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("TrendStrategy")
        self._config = settings

    async def generate_signal(
        self, 
        candles_1m: List[Candle], 
        candles_5m: List[Candle],
        indicators: Dict[str, Any],
        regime: MarketRegime,
        orderbook: Optional[Dict[str, Any]] = None
    ) -> Optional[TradeSignal]:
        
        if regime != MarketRegime.TRENDING:
            return None

        bullish_ema = is_ema_crossover_bullish(candles_5m, self._config.EMA_FAST, self._config.EMA_SLOW)
        bearish_ema = is_ema_crossover_bearish(candles_5m, self._config.EMA_FAST, self._config.EMA_SLOW)

        vol_ratio = get_volume_ratio(candles_1m, 20)
        vol_confirmed = vol_ratio > 1.3

        bid_depth = decimal.Decimal(str(orderbook.get("bid_depth", 0))) if orderbook else decimal.Decimal('0')
        ask_depth = decimal.Decimal(str(orderbook.get("ask_depth", 0))) if orderbook else decimal.Decimal('0')
        
        imbalance_bullish = bid_depth > (ask_depth * decimal.Decimal('1.15')) if ask_depth > 0 else False
        imbalance_bearish = ask_depth > (bid_depth * decimal.Decimal('1.15')) if bid_depth > 0 else False

        atr = decimal.Decimal(str(get_current_atr(candles_1m, self._config.ATR_PERIOD)))
        current_price = candles_1m[-1].close

        if bullish_ema and vol_confirmed and imbalance_bullish:
            return TradeSignal(
                symbol=candles_1m[-1].symbol,
                side=TradingSide.BUY,
                price=current_price,
                confidence=0.85,
                regime=regime,
                take_profit=current_price + (atr * decimal.Decimal('3.0')),
                stop_loss=current_price - (atr * decimal.Decimal('1.5')),
                indicators={"strategy": self.name, "reason": "EMA Bullish + Vol + OB Imbalance", "atr": float(atr)}
            )
        
        if bearish_ema and vol_confirmed and imbalance_bearish:
            return TradeSignal(
                symbol=candles_1m[-1].symbol,
                side=TradingSide.SELL,
                price=current_price,
                confidence=0.85,
                regime=regime,
                take_profit=current_price - (atr * decimal.Decimal('3.0')),
                stop_loss=current_price + (atr * decimal.Decimal('1.5')),
                indicators={"strategy": self.name, "reason": "EMA Bearish + Vol + OB Imbalance", "atr": float(atr)}
            )

        return None
