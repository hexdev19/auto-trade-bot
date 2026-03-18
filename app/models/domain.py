from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, Any, Optional

class MarketRegime(str, Enum):
    TRENDING = "TRENDING"
    SIDEWAYS = "SIDEWAYS"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"

class TradingSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

@dataclass(frozen=True)
class Candle:
    symbol: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

@dataclass(frozen=True)
class TradeSignal:
    symbol: str
    side: TradingSide
    price: Decimal
    confidence: float
    regime: MarketRegime
    indicators: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class OpenPosition:
    id: str
    symbol: str
    side: TradingSide
    entry_price: Decimal
    quantity: Decimal
    take_profit: Decimal
    stop_loss: Decimal
    entry_atr: Decimal = Decimal('0')
    breakeven_moved: bool = False
    opened_at: datetime = field(default_factory=datetime.utcnow)
    is_open: bool = True

@dataclass
class ClosedTrade:
    id: str
    symbol: str
    side: TradingSide
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    pnl: Decimal
    pnl_percent: Decimal
    opened_at: datetime
    closed_at: datetime = field(default_factory=datetime.utcnow)

class RiskStatus(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

@dataclass(frozen=True)
class RiskDecision:
    status: RiskStatus
    reason: Optional[str] = None
    max_quantity: Optional[Decimal] = None
    adjusted_sl: Optional[Decimal] = None
    adjusted_tp: Optional[Decimal] = None
