import decimal
import numpy as np
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from app.models.domain import Candle, TradeSignal, MarketRegime, TradingSide
from app.strategies.base import BaseStrategy
from app.indicators.rsi import get_rsi
from app.indicators.macd import get_macd_snapshot
from app.indicators.bollinger import get_band_snapshot
from app.indicators.support_resistance import find_levels, is_near_support, is_near_resistance
from app.indicators.atr import get_current_atr
from app.core.config import settings

class ScalpingStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("ScalpingStrategy")
        self._config = settings
        self._trade_history: List[datetime] = []

    async def generate_signal(
        self, 
        candles_1m: List[Candle], 
        candles_5m: List[Candle],
        indicators: Dict[str, Any],
        regime: MarketRegime,
        orderbook: Optional[Dict[str, Any]] = None
    ) -> Optional[TradeSignal]:
        
        if regime != MarketRegime.SIDEWAYS:
            return None
        if orderbook:
            bid = decimal.Decimal(str(orderbook.get("bid", 0)))
            ask = decimal.Decimal(str(orderbook.get("ask", 0)))
            if ask > 0:
                spread_pct = (ask - bid) / ask
                if spread_pct >= decimal.Decimal('0.0005'): # 0.05%
                    return None
        atr = decimal.Decimal(str(get_current_atr(candles_1m, self._config.ATR_PERIOD)))
        
        now = datetime.utcnow()
        self._trade_history = [t for t in self._trade_history if now - t < timedelta(hours=1)]
        if len(self._trade_history) >= 3:
            return None

        sr_levels = find_levels(candles_1m, self._config.SR_LOOKBACK, self._config.SR_BINS)
        score, confidence = self.compute_composite_score(candles_1m, sr_levels, orderbook)
        
        current_price = candles_1m[-1].close
        rsi = get_rsi(candles_1m, self._config.RSI_PERIOD)

        if score > 0.15 and confidence >= 0.7:
             if is_near_support(current_price, sr_levels) and rsi < 40:
                self._trade_history.append(now)
                return TradeSignal(
                    symbol=candles_1m[-1].symbol,
                    side=TradingSide.BUY,
                    price=current_price,
                    confidence=float(confidence),
                    regime=regime,
                    take_profit=current_price + (atr * decimal.Decimal('1.2')),
                    stop_loss=current_price - (atr * decimal.Decimal('0.8')),
                    indicators={"strategy": self.name, "score": score, "atr": float(atr)}
                )

        if score < -0.15 and confidence >= 0.7:
            if is_near_resistance(current_price, sr_levels) and rsi > 60:
                self._trade_history.append(now)
                return TradeSignal(
                    symbol=candles_1m[-1].symbol,
                    side=TradingSide.SELL,
                    price=current_price,
                    confidence=float(confidence),
                    regime=regime,
                    take_profit=current_price - (atr * decimal.Decimal('1.2')),
                    stop_loss=current_price + (atr * decimal.Decimal('0.8')),
                    indicators={"strategy": self.name, "score": score, "atr": float(atr)}
                )

        return None

    def compute_composite_score(self, candles: List[Candle], sr_levels: Any, orderbook: Optional[Dict[str, Any]]) -> Tuple[float, float]:
        rsi = get_rsi(candles, 14)
        macd = get_macd_snapshot(candles)
        bb = get_band_snapshot(candles)
        
        score = 0.0
        
        if rsi < 30: score += 0.4
        elif rsi < 40: score += 0.2
        elif rsi > 70: score -= 0.4
        elif rsi > 60: score -= 0.2
        
        if macd.histogram > 0: score += 0.2
        else: score -= 0.2
        if macd.is_bullish_cross: score += 0.3
        if macd.is_bearish_cross: score -= 0.3
        
        if bb.price_below_lower: score += 0.4
        elif bb.price_above_upper: score -= 0.4
        
        score = max(-1.0, min(1.0, score))
        confidence = 0.7 + (abs(score) * 0.2)
        
        return float(score), float(confidence)
