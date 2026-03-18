import numpy as np
from typing import List
from app.models.domain import Candle

def get_volume_ratio(candles: List[Candle], period: int = 20) -> float:
    if len(candles) < period:
        raise ValueError(f"Insufficient candles for Volume Ratio. Need at least {period}, got {len(candles)}.")
    
    volumes = np.array([float(c.volume) for c in candles])
    current_volume = volumes[-1]
    average_volume = np.mean(volumes[-period-1:-1])
    
    return float(current_volume / average_volume) if average_volume != 0 else 0.

def is_volume_spike(candles: List[Candle], period: int = 20, threshold: float = 2.5) -> bool:
    return get_volume_ratio(candles, period) >= threshold
