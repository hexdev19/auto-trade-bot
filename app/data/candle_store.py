from collections import deque
from typing import Dict, List, Optional
from app.models.domain import Candle

class CandleStore:
    def __init__(self, max_size: int = 500):
        self._max_size = max_size
        self._candles: Dict[str, deque[Candle]] = {}

    def append(self, candle: Candle, timeframe: str):
        if timeframe not in self._candles:
            self._candles[timeframe] = deque(maxlen=self._max_size)
        self._candles[timeframe].append(candle)

    def get(self, timeframe: str, n: Optional[int] = None) -> List[Candle]:
        if timeframe not in self._candles: return []
        data = list(self._candles[timeframe])
        return data[-n:] if n else data

    def size(self, timeframe: str) -> int:
        return len(self._candles.get(timeframe, []))

    def is_ready(self, timeframe: str, min_candles: int) -> bool:
        return self.size(timeframe) >= min_candles
