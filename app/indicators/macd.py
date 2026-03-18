import numpy as np
from typing import List, Tuple
from dataclasses import dataclass
from app.models.domain import Candle

@dataclass(frozen=True)
class MACDSnapshot:
    macd_line: float
    signal_line: float
    histogram: float
    is_bullish_cross: bool
    is_bearish_cross: bool

def calculate_macd(candles: List[Candle], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    if len(candles) < slow + signal:
        raise ValueError(f"Insufficient candles for MACD calculation. Need at least {slow + signal}, got {len(candles)}.")
    
    closes = np.array([float(c.close) for c in candles])
    
    def _ema(data, span):
        alpha = 2 / (span + 1)
        ema = np.zeros_like(data)
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
        return ema

    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram

def get_macd_snapshot(candles: List[Candle], fast: int = 12, slow: int = 26, signal: int = 9) -> MACDSnapshot:
    macd_line, signal_line, histogram = calculate_macd(candles, fast, slow, signal)
    
    is_bullish_cross = macd_line[-2] <= signal_line[-2] and macd_line[-1] > signal_line[-1]
    is_bearish_cross = macd_line[-2] >= signal_line[-2] and macd_line[-1] < signal_line[-1]
    
    return MACDSnapshot(
        macd_line=float(macd_line[-1]),
        signal_line=float(signal_line[-1]),
        histogram=float(histogram[-1]),
        is_bullish_cross=is_bullish_cross,
        is_bearish_cross=is_bearish_cross
    )
