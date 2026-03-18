import numpy as np
from typing import List
from app.models.domain import Candle

def calculate_adx(candles: List[Candle], period: int = 14) -> np.ndarray:
    if len(candles) < 2 * period:
        raise ValueError(f"Insufficient candles for ADX calculation. Need at least {2 * period}, got {len(candles)}.")
    
    highs = np.array([float(c.high) for c in candles])
    lows = np.array([float(c.low) for c in candles])
    closes = np.array([float(c.close) for c in candles])
    
    prev_highs = highs[:-1]
    prev_lows = lows[:-1]
    prev_closes = closes[:-1]
    
    curr_highs = highs[1:]
    curr_lows = lows[1:]
    
    tr1 = curr_highs - curr_lows
    tr2 = np.abs(curr_highs - prev_closes)
    tr3 = np.abs(curr_lows - prev_closes)
    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    
    dm_plus = np.where((curr_highs - prev_highs) > (prev_lows - curr_lows), 
                       np.maximum(curr_highs - prev_highs, 0), 0)
    dm_minus = np.where((prev_lows - curr_lows) > (curr_highs - prev_highs), 
                        np.maximum(prev_lows - curr_lows, 0), 0)
    
    def _smooth(data, period):
        smoothed = np.zeros(len(data))
        smoothed[period-1] = np.sum(data[:period])
        for i in range(period, len(data)):
            smoothed[i] = smoothed[i-1] - (smoothed[i-1] / period) + data[i]
        return smoothed

    tr_s = _smooth(tr, period)
    dm_plus_s = _smooth(dm_plus, period)
    dm_minus_s = _smooth(dm_minus, period)
    
    di_plus = 100 * (dm_plus_s / tr_s)
    di_minus = 100 * (dm_minus_s / tr_s)
    
    dx = 100 * np.abs(di_plus - di_minus) / (di_plus + di_minus)
    
    adx = np.zeros(len(candles))
    adx[:2*period-1] = np.nan
    
    valid_dx = dx[period-1:]
    adx[2*period-1] = np.mean(valid_dx[:period])
    
    for i in range(2*period, len(candles)):
        adx[i] = (adx[i-1] * (period - 1) + dx[i-1]) / period
        
    return adx

def get_current_adx(candles: List[Candle], period: int = 14) -> float:
    adx_array = calculate_adx(candles, period)
    return float(adx_array[-1])
