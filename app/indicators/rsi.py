import numpy as np
from typing import List
from app.models.domain import Candle

def calculate_rsi(candles: List[Candle], period: int) -> np.ndarray:
    if len(candles) < period + 1:
        raise ValueError(f"Insufficient candles for RSI calculation. Need at least {period + 1}, got {len(candles)}.")
    
    closes = np.array([float(c.close) for c in candles])
    deltas = np.diff(closes)
    seed = deltas[:period]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 0
    rsi = np.zeros_like(closes)
    rsi[:period] = np.nan
    rsi[period] = 100. - (100. / (1. + rs)) if down != 0 else 100.

    for i in range(period + 1, len(closes)):
        delta = deltas[i - 1]
        if delta > 0:
            upval = delta
            downval = 0.
        else:
            upval = 0.
            downval = -delta

        up = (up * (period - 1) + upval) / period
        down = (down * (period - 1) + downval) / period
        rs = up / down if down != 0 else 0
        rsi[i] = 100. - (100. / (1. + rs)) if down != 0 else 100.

    return rsi

def get_rsi(candles: List[Candle], period: int = 14) -> float:
    rsi_array = calculate_rsi(candles, period)
    return float(rsi_array[-1])
