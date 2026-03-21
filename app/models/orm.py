from sqlalchemy import Numeric, String, DateTime, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from decimal import Decimal
from typing import Optional
from app.models.base import Base

class TradeRecord(Base):
    __tablename__ = "trades"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    symbol: Mapped[str] = mapped_column(String)
    side: Mapped[str] = mapped_column(String)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    exit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    stop_loss: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    take_profit: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    pnl: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
    pnl_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    strategy_name: Mapped[str] = mapped_column(String)
    regime: Mapped[str] = mapped_column(String)
    close_reason: Mapped[Optional[str]] = mapped_column(String)
    exit_reason: Mapped[Optional[str]] = mapped_column(String)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)

class PerformanceSnapshot(Base):
    __tablename__ = "performance_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    balance: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    equity: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    daily_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    win_rate: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    total_trades: Mapped[int] = mapped_column(Integer)

class RegimeHistory(Base):
    __tablename__ = "regime_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    regime: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Numeric(10, 4))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
