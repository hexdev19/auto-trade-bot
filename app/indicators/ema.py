import numpy as np
from typing import List
from app.models.domain import Candle

def calculate_ema(candles: List[Candle], period: int) -> np.ndarray:
    if len(candles) < period:
        raise ValueError(f"Insufficient candles for EMA calculation. Need at least {period}, got {len(candles)}.")
    
    closes = np.array([float(c.close) for c in candles])
    alpha = 2 / (period + 1)
    ema = np.zeros_like(closes)
    ema[0] = closes[0]
    for i in range(1, len(closes)):
        ema[i] = alpha * closes[i] + (1 - alpha) * ema[i - 1]
    return ema

def get_ema_slope(candles: List[Candle], period: int, lookback: int = 3) -> float:
    ema = calculate_ema(candles, period)
    if len(ema) < lookback:
        return 0.
    recent = ema[-lookback:]
    slope = (recent[-1] - recent[0]) / lookback
    return float(slope / recent[-1])

def is_ema_crossover_bullish(candles: List[Candle], fast: int, slow: int) -> bool:
    ema_fast = calculate_ema(candles, fast)
    ema_slow = calculate_ema(candles, slow)
    return ema_fast[-2] <= ema_slow[-2] and ema_fast[-1] > ema_slow[-1]

def is_ema_crossover_bearish(candles: List[Candle], fast: int, slow: int) -> bool:
    ema_fast = calculate_ema(candles, fast)
    ema_slow = calculate_ema(candles, slow)
    return ema_fast[-2] >= ema_slow[-2] and ema_fast[-1] < ema_slow[-1]
