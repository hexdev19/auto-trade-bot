from typing import List, Dict, Any, Optional
from app.models.domain import Candle, MarketRegime
from app.indicators.adx import get_current_adx
from app.indicators.ema import get_ema_slope
from app.indicators.atr import get_current_atr, get_atr_average
from app.indicators.volume import is_volume_spike
import numpy as np
from app.core.config import settings

class MarketRegimeEngine:
    def __init__(self):
        self._current_regime = MarketRegime.UNKNOWN
        self._pending_regime = MarketRegime.UNKNOWN
        self._confirm_count = 0
        self._config = settings

    def update(self, candles: List[Candle]) -> MarketRegime:
        try:
            new_regime = self._classify(candles)
            
            if new_regime == self._current_regime:
                self._pending_regime = MarketRegime.UNKNOWN
                self._confirm_count = 0
            elif new_regime == self._pending_regime:
                self._confirm_count += 1
                if self._confirm_count >= self._config.REGIME_CONFIRM_CANDLES:
                    self._current_regime = new_regime
                    self._pending_regime = MarketRegime.UNKNOWN
                    self._confirm_count = 0
            else:
                self._pending_regime = new_regime
                self._confirm_count = 1
                
        except Exception:
            self._current_regime = MarketRegime.UNKNOWN
            
        return self._current_regime

    def _classify(self, candles: List[Candle]) -> MarketRegime:
        if len(candles) < self._config.REGIME_LOOKBACK * 2:
            return MarketRegime.UNKNOWN
            
        adx = get_current_adx(candles, self._config.ADX_PERIOD)
        ema_slope = get_ema_slope(candles, self._config.EMA_FAST)
        atr = get_current_atr(candles, self._config.ATR_PERIOD)
        atr_avg = get_atr_average(candles, self._config.ATR_PERIOD, self._config.REGIME_LOOKBACK)
        
        atr_ratio = atr / atr_avg if atr_avg > 0 else 1.0
        volume_spike = is_volume_spike(candles)
        
        last_candle_size = abs(float(candles[-1].close) - float(candles[-1].open))
        avg_candle_size = np.mean([abs(float(c.close) - float(c.open)) for c in candles[-20:]])
        
        if atr_ratio > self._config.ATR_VOLATILITY_MULTIPLIER or volume_spike or (last_candle_size > 3 * avg_candle_size):
            return MarketRegime.HIGH_VOLATILITY
            
        if adx > 25 and abs(ema_slope) > 0.0001:
            return MarketRegime.TRENDING
            
        if adx < 20 and atr_ratio < 1.0:
            return MarketRegime.SIDEWAYS
            
        return MarketRegime.UNKNOWN

    def get_current_regime(self) -> MarketRegime:
        return self._current_regime

    def get_regime_confidence(self) -> float:
        return 1.0 if self._current_regime != MarketRegime.UNKNOWN else 0.0

    def get_indicator_snapshot(self) -> Dict[str, Any]:
        return {
            "current_regime": self._current_regime.value,
            "pending_regime": self._pending_regime.value,
            "confirm_count": self._confirm_count
        }
