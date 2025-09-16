# backend/schemas/trading_schema.py

from datetime import datetime
from typing import Optional, List, Dict, Any
from decimal import Decimal
from pydantic import BaseModel, Field, validator
from enum import Enum


class TradingSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"


class OrderStatus(str, Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class TradingSymbol(str, Enum):
    BTCUSDT = "BTCUSDT"
    ETHUSDT = "ETHUSDT"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Request Schemas
class MarketOrderRequest(BaseModel):
    symbol: TradingSymbol
    side: TradingSide
    quantity: Optional[float] = Field(None, gt=0, description="Quantity to trade")
    quote_order_qty: Optional[float] = Field(None, gt=0, description="Amount in quote asset (USDT)")
    
    @validator('*', pre=True)
    def validate_quantity_or_quote(cls, v, values):
        if 'quantity' in values and 'quote_order_qty' in values:
            if values.get('quantity') and values.get('quote_order_qty'):
                raise ValueError("Specify either quantity or quote_order_qty, not both")
            if not values.get('quantity') and not values.get('quote_order_qty'):
                raise ValueError("Must specify either quantity or quote_order_qty")
        return v


class LimitOrderRequest(BaseModel):
    symbol: TradingSymbol
    side: TradingSide
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    time_in_force: str = Field(default="GTC", description="Time in force (GTC, IOC, FOK)")


class StopLossOrderRequest(BaseModel):
    symbol: TradingSymbol
    side: TradingSide
    quantity: float = Field(..., gt=0)
    stop_price: float = Field(..., gt=0)
    price: Optional[float] = Field(None, gt=0, description="Limit price for stop-loss limit orders")


class TakeProfitOrderRequest(BaseModel):
    symbol: TradingSymbol
    side: TradingSide
    quantity: float = Field(..., gt=0)
    stop_price: float = Field(..., gt=0)
    price: Optional[float] = Field(None, gt=0, description="Limit price for take-profit limit orders")


class TradingConfigRequest(BaseModel):
    risk_level: RiskLevel = RiskLevel.MEDIUM
    max_position_size_percentage: float = Field(default=10.0, ge=1.0, le=100.0)
    stop_loss_percentage: float = Field(default=5.0, ge=0.1, le=50.0)
    take_profit_percentage: float = Field(default=10.0, ge=0.1, le=100.0)
    trading_enabled: bool = Field(default=True)
    symbols_to_trade: List[TradingSymbol] = Field(default=[TradingSymbol.BTCUSDT, TradingSymbol.ETHUSDT])
    min_trade_amount: float = Field(default=10.0, ge=1.0)
    max_trade_amount: float = Field(default=1000.0, ge=10.0)


class StrategyConfigRequest(BaseModel):
    strategy_name: str = Field(default="moving_average")
    moving_average_period: int = Field(default=20, ge=5, le=200)
    price_change_threshold: float = Field(default=1.0, ge=0.1, le=10.0)
    volume_threshold_multiplier: float = Field(default=1.5, ge=1.0, le=5.0)
    rsi_overbought: float = Field(default=70.0, ge=60.0, le=90.0)
    rsi_oversold: float = Field(default=30.0, ge=10.0, le=40.0)
    bollinger_bands_period: int = Field(default=20, ge=10, le=50)
    bollinger_bands_std: float = Field(default=2.0, ge=1.0, le=3.0)


# Response Schemas
class PriceData(BaseModel):
    symbol: str
    price: float
    price_change_24h: float
    price_change_percent_24h: float
    high_24h: float
    low_24h: float
    volume_24h: float
    timestamp: datetime


class BalanceInfo(BaseModel):
    asset: str
    free: float
    locked: float
    total: float


class AccountBalanceResponse(BaseModel):
    balances: List[BalanceInfo]
    total_usdt_value: float
    timestamp: datetime


class OrderResponse(BaseModel):
    order_id: str
    client_order_id: str
    symbol: str
    side: str
    type: str
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: str
    time_in_force: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    executed_quantity: float = 0.0
    cumulative_quote_qty: float = 0.0


class TradeResponse(BaseModel):
    trade_id: str
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    commission: float
    commission_asset: str
    realized_pnl: Optional[float] = None
    timestamp: datetime


class PositionResponse(BaseModel):
    symbol: str
    side: str
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_percentage: float
    margin_used: float
    created_at: datetime


class TradingStatsResponse(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    win_rate: float
    average_win: float
    average_loss: float
    max_profit: float
    max_loss: float
    total_commission: float
    period_start: datetime
    period_end: datetime


class MarketDataResponse(BaseModel):
    symbol: str
    current_price: float
    moving_average_20: Optional[float] = None
    moving_average_50: Optional[float] = None
    rsi: Optional[float] = None
    bollinger_upper: Optional[float] = None
    bollinger_lower: Optional[float] = None
    volume_24h: float
    volume_average: Optional[float] = None
    trend_direction: Optional[str] = None  # "bullish", "bearish", "sideways"
    signal_strength: Optional[float] = None  # 0.0 to 1.0
    last_updated: datetime


class TradingSignalResponse(BaseModel):
    symbol: str
    signal: str  # "BUY", "SELL", "HOLD"
    confidence: float  # 0.0 to 1.0
    price: float
    strategy: str
    indicators: Dict[str, Any]
    timestamp: datetime
    reasoning: str


class AutoTradingStatusResponse(BaseModel):
    is_enabled: bool
    symbols_monitored: List[str]
    current_positions: List[PositionResponse]
    pending_orders: List[OrderResponse]
    last_signal_time: Optional[datetime] = None
    last_trade_time: Optional[datetime] = None
    total_trades_today: int
    pnl_today: float
    bot_status: str  # "running", "paused", "error"
    error_message: Optional[str] = None


# Error Response Schemas
class ErrorResponse(BaseModel):
    error: str
    error_code: Optional[str] = None
    message: str
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None


class TradingErrorResponse(ErrorResponse):
    symbol: Optional[str] = None
    order_id: Optional[str] = None
    balance_required: Optional[float] = None
    balance_available: Optional[float] = None


# Notification Schemas
class TradeNotification(BaseModel):
    type: str  # "trade_executed", "stop_loss_triggered", "take_profit_hit"
    symbol: str
    side: str
    quantity: float
    price: float
    pnl: Optional[float] = None
    total_balance: float
    timestamp: datetime
    message: str


class AlertNotification(BaseModel):
    type: str  # "price_alert", "volume_alert", "system_error"
    symbol: Optional[str] = None
    message: str
    severity: str  # "info", "warning", "error", "critical"
    timestamp: datetime
    data: Optional[Dict[str, Any]] = None


# Historical Data Schemas
class CandlestickData(BaseModel):
    symbol: str
    open_time: datetime
    close_time: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    quote_asset_volume: float
    number_of_trades: int


class HistoricalDataRequest(BaseModel):
    symbol: TradingSymbol
    interval: str = Field(default="1m", description="Kline interval (1m, 5m, 15m, 1h, 4h, 1d)")
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(default=100, ge=1, le=1000)


class HistoricalDataResponse(BaseModel):
    symbol: str
    interval: str
    data: List[CandlestickData]
    count: int
    start_time: datetime
    end_time: datetime


# Validation helpers
def validate_trading_pair(symbol: str) -> bool:
    """Validate if trading pair is supported"""
    return symbol in [s.value for s in TradingSymbol]


def validate_order_amount(amount: float, min_amount: float = 10.0) -> bool:
    """Validate if order amount meets minimum requirements"""
    return amount >= min_amount


def calculate_position_size(balance: float, risk_percentage: float, price: float) -> float:
    """Calculate position size based on risk management"""
    risk_amount = balance * (risk_percentage / 100)
    return risk_amount / price
