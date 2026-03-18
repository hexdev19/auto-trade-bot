from typing import List, Optional, Dict, Any
from app.models.domain import Candle, TradeSignal, MarketRegime
from app.strategies.base import BaseStrategy

class VolatilityPauseStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("VolatilityPauseStrategy")

    async def generate_signal(
        self, 
        candles_1m: List[Candle], 
        candles_5m: List[Candle],
        indicators: Dict[str, Any],
        regime: MarketRegime,
        orderbook: Optional[Dict[str, Any]] = None
    ) -> Optional[TradeSignal]:
        return None
