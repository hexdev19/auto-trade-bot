from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Any, Optional
from datetime import datetime
from app.models.domain import TradingSide

@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: TradingSide
    quantity: Decimal
    order_type: str = "MARKET"

@dataclass(frozen=True)
class OrderResult:
    order_id: str
    symbol: str
    side: TradingSide
    quantity: Decimal
    price: Decimal
    value: Decimal
    status: str
    raw_response: Dict[str, Any]
    timestamp: datetime = datetime.utcnow()
