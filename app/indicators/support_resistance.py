import decimal
import numpy as np
from typing import List, Tuple
from dataclasses import dataclass
from decimal import Decimal
from app.models.domain import Candle

@dataclass(frozen=True)
class SRLevels:
    support: Decimal
    resistance: Decimal
    support_strength: float
    resistance_strength: float

def find_levels(candles: List[Candle], lookback: int = 20, bins: int = 10) -> SRLevels:
    if len(candles) < lookback:
        raise ValueError(f"Insufficient candles for S/R calculation. Need at least {lookback}, got {len(candles)}.")
    
    recent_candles = candles[-lookback:]
    np_prices = np.array([float(c.close) for c in recent_candles])
    
    counts, bin_edges = np.histogram(np_prices, bins=bins)
    
    current_price = float(candles[-1].close)
    
    supports = []
    resistances = []
    
    for i in range(len(counts)):
        midpoint = (bin_edges[i] + bin_edges[i+1]) / 2
        strength = counts[i] / len(recent_candles)
        if midpoint < current_price:
            supports.append((midpoint, strength))
        elif midpoint > current_price:
            resistances.append((midpoint, strength))
            
    support = max(supports, key=lambda x: x[1]) if supports else (current_price * 0.95, 0.)
    resistance = min(resistances, key=lambda x: x[1]) if resistances else (current_price * 1.05, 0.)
    
    return SRLevels(
        support=decimal.Decimal(str(support[0])),
        resistance=decimal.Decimal(str(resistance[0])),
        support_strength=float(support[1]),
        resistance_strength=float(resistance[1])
    )

def is_near_support(price: Decimal, levels: SRLevels, tolerance_pct: Decimal = decimal.Decimal("0.002")) -> bool:
    return abs(price - levels.support) / price <= tolerance_pct

def is_near_resistance(price: Decimal, levels: SRLevels, tolerance_pct: Decimal = decimal.Decimal("0.002")) -> bool:
    return abs(price - levels.resistance) / price <= tolerance_pct
