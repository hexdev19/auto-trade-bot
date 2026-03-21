"""
Batch indicator calculator.

Computes all technical indicators relevant to strategy signal generation
in a single pass over a candle series.
"""
from typing import List, Dict, Any
from app.models.domain import Candle
from app.indicators.rsi import get_rsi
from app.indicators.macd import get_macd_snapshot
from app.indicators.bollinger import get_band_snapshot
from app.indicators.ema import get_ema_slope
from app.indicators.atr import get_current_atr, get_atr_average
from app.indicators.adx import get_current_adx
from app.indicators.volume import get_volume_ratio, is_volume_spike
from app.indicators.support_resistance import find_levels
from app.core.config import settings


class IndicatorCalculator:
    """Batch-computes all indicators for a candle series."""

    def __init__(self, config=None):
        self._config = config or settings

    def compute(self, candles: List[Candle]) -> Dict[str, Any]:
        """Compute all indicators from a candle series.

        Returns a dict with all computed indicator values that strategies
        and the regime engine can use.
        """
        result: Dict[str, Any] = {}

        if len(candles) < 30:
            return result

        try:
            result["rsi"] = get_rsi(candles, self._config.RSI_PERIOD)
        except Exception:
            result["rsi"] = None

        try:
            macd = get_macd_snapshot(candles)
            result["macd_histogram"] = macd.histogram
            result["macd_is_bullish_cross"] = macd.is_bullish_cross
            result["macd_is_bearish_cross"] = macd.is_bearish_cross
        except Exception:
            result["macd_histogram"] = None
            result["macd_is_bullish_cross"] = False
            result["macd_is_bearish_cross"] = False

        try:
            bb = get_band_snapshot(candles)
            result["bb_price_below_lower"] = bb.price_below_lower
            result["bb_price_above_upper"] = bb.price_above_upper
        except Exception:
            result["bb_price_below_lower"] = False
            result["bb_price_above_upper"] = False

        try:
            result["ema_slope"] = get_ema_slope(candles, self._config.EMA_FAST)
        except Exception:
            result["ema_slope"] = None

        try:
            result["atr"] = get_current_atr(candles, self._config.ATR_PERIOD)
        except Exception:
            result["atr"] = None

        try:
            result["atr_avg"] = get_atr_average(
                candles, self._config.ATR_PERIOD, self._config.REGIME_LOOKBACK
            )
        except Exception:
            result["atr_avg"] = None

        try:
            result["adx"] = get_current_adx(candles, self._config.ADX_PERIOD)
        except Exception:
            result["adx"] = None

        try:
            result["volume_ratio"] = get_volume_ratio(candles, 20)
        except Exception:
            result["volume_ratio"] = None

        try:
            result["volume_spike"] = is_volume_spike(candles)
        except Exception:
            result["volume_spike"] = False

        try:
            result["sr_levels"] = find_levels(
                candles, self._config.SR_LOOKBACK, self._config.SR_BINS
            )
        except Exception:
            result["sr_levels"] = []

        return result
