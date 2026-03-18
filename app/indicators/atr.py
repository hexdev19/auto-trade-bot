import numpy as np
from typing import List
from app.models.domain import Candle

def calculate_atr(candles: List[Candle], period: int = 14) -> np.ndarray:
    if len(candles) < period + 1:
        raise ValueError(f"Insufficient candles for ATR calculation. Need at least {period + 1}, got {len(candles)}.")
    
    highs = np.array([float(c.high) for c in candles])
    lows = np.array([float(c.low) for c in candles])
    prev_closes = np.array([float(c.close) for c in candles[:-1]])
    
    tr1 = highs[1:] - lows[1:]
    tr2 = np.abs(highs[1:] - prev_closes)
    tr3 = np.abs(lows[1:] - prev_closes)
    
    true_range = np.maximum(tr1, np.maximum(tr2, tr3))
    
    atr = np.zeros(len(candles))
    atr[:period] = np.nan
    atr[period] = np.mean(true_range[:period])
    
    for i in range(period + 1, len(candles)):
        atr[i] = (atr[i-1] * (period - 1) + true_range[i-1]) / period
        
    return atr

def get_current_atr(candles: List[Candle], period: int = 14) -> float:
    atr_array = calculate_atr(candles, period)
    return float(atr_array[-1])

def get_atr_average(candles: List[Candle], period: int = 14, avg_period: int = 20) -> float:
    atr_array = calculate_atr(candles, period)
    valid_atr = atr_array[~np.isnan(atr_array)]
    return float(np.mean(valid_atr[-avg_period:]))
