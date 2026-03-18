import numpy as np
from typing import List, Tuple
from dataclasses import dataclass
from app.models.domain import Candle

@dataclass(frozen=True)
class BBSnapshot:
    upper: float
    middle: float
    lower: float
    pct_b: float
    bandwidth: float
    price_above_upper: bool
    price_below_lower: bool

def calculate_bands(candles: List[Candle], period: int = 20, std_dev: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    if len(candles) < period:
        raise ValueError(f"Insufficient candles for Bollinger Bands calculation. Need at least {period}, got {len(candles)}.")
    
    closes = np.array([float(c.close) for c in candles])
    
    def _sma(data, span):
        sma = np.zeros_like(data)
        sma[:span - 1] = np.nan
        for i in range(span - 1, len(data)):
            sma[i] = np.mean(data[i - span + 1:i + 1])
        return sma

    def _std(data, span):
        std = np.zeros_like(data)
        std[:span - 1] = np.nan
        for i in range(span - 1, len(data)):
            std[i] = np.std(data[i - span + 1:i + 1])
        return std

    middle = _sma(closes, period)
    std = _std(closes, period)
    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)
    
    return upper, middle, lower

def get_band_snapshot(candles: List[Candle], period: int = 20, std_dev: float = 2.0) -> BBSnapshot:
    upper, middle, lower = calculate_bands(candles, period, std_dev)
    
    current_price = float(candles[-1].close)
    current_upper = float(upper[-1])
    current_middle = float(middle[-1])
    current_lower = float(lower[-1])
    
    pct_b = (current_price - current_lower) / (current_upper - current_lower) if current_upper != current_lower else 0.5
    bandwidth = (current_upper - current_lower) / current_middle if current_middle != 0 else 0
    
    return BBSnapshot(
        upper=current_upper,
        middle=current_middle,
        lower=current_lower,
        pct_b=pct_b,
        bandwidth=bandwidth,
        price_above_upper=current_price > current_upper,
        price_below_lower=current_price < current_lower
    )
