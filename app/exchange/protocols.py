from typing import List, Optional, Protocol, Dict, Any
from decimal import Decimal
from app.models.domain import TradingSide

class ExchangeClient(Protocol):
    async def connect(self) -> None:
        ...

    async def close(self) -> None:
        ...

    async def place_market_order(
        self, 
        symbol: str, 
        side: TradingSide, 
        quantity: Decimal
    ) -> Dict[str, Any]:
        ...

    async def get_balance(self, asset: str) -> Decimal:
        ...

    async def get_price(self, symbol: str) -> Decimal:
        ...
