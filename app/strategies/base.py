from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from app.models.domain import Candle, TradeSignal, MarketRegime

class BaseStrategy(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def generate_signal(
        self, 
        candles_1m: List[Candle], 
        candles_5m: List[Candle],
        indicators: Dict[str, Any],
        regime: MarketRegime,
        orderbook: Optional[Dict[str, Any]] = None
    ) -> Optional[TradeSignal]:
        pass
