from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.models.domain import TradingSide, MarketRegime

class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class PriceData(BaseSchema):
    symbol: str
    price: Decimal
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class CandlestickData(BaseSchema):
    symbol: str
    open_time: datetime
    close_time: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal

class MarketAnalysisResponse(BaseSchema):
    symbol: str
    current_price: Decimal
    regime: MarketRegime
    indicators: Dict[str, Any]
    last_updated: datetime = Field(default_factory=datetime.utcnow)

class TradingSignalResponse(BaseSchema):
    symbol: str
    signal: str
    confidence: float
    price: Decimal
    reasoning: str
    indicators: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class MarketOrderRequest(BaseSchema):
    symbol: str
    side: TradingSide
    quantity: Decimal
    quote_order_qty: Optional[Decimal] = None

class OrderResponse(BaseSchema):
    order_id: str
    client_order_id: str
    symbol: str
    side: TradingSide
    quantity: Decimal
    price: Optional[Decimal] = None
    status: str
    executed_quantity: Decimal
    cumulative_quote_qty: Decimal
    created_at: datetime

class TradeStatsResponse(BaseSchema):
    total_trades: int
    win_rate: float
    total_pnl: Decimal
    total_pnl_percent: Decimal
    max_drawdown: Decimal
    avg_trade_duration: float
