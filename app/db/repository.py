from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, date
from decimal import Decimal
from typing import List, Dict, Any, Optional
from app.models.orm import TradeRecord, PerformanceSnapshot, RegimeHistory
from app.models.domain import ClosedTrade

class TradingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_trade(self, trade_data: Dict[str, Any]) -> TradeRecord:
        record = TradeRecord(**trade_data)
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_recent_trades(self, limit: int = 50) -> List[TradeRecord]:
        query = select(TradeRecord).order_by(TradeRecord.closed_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_daily_pnl(self) -> Decimal:
        today = datetime.utcnow().date()
        start = datetime(today.year, today.month, today.day)
        query = select(func.sum(TradeRecord.pnl)).where(
            and_(TradeRecord.closed_at >= start, TradeRecord.is_open == False)
        )
        result = await self.session.execute(query)
        res = result.scalar_one_or_none()
        return Decimal(str(res)) if res else Decimal('0')

    async def get_trade_stats(self) -> Dict[str, Any]:
        query = select(
            func.count(TradeRecord.id),
            func.sum(TradeRecord.pnl),
            func.count().filter(TradeRecord.pnl > 0)
        ).where(TradeRecord.is_open == False)
        result = await self.session.execute(query)
        total, pnl, wins = result.one()
        pnl = Decimal(str(pnl)) if pnl else Decimal('1')
        win_rate = (wins / total * 100) if total > 0 else 0
        return {"total_trades": total, "win_rate": float(win_rate), "total_pnl": pnl}

    async def save_regime_change(self, old_regime: str, new_regime: str, confidence: float):
        now = datetime.utcnow()
        await self.session.execute(
            update(RegimeHistory).where(RegimeHistory.ended_at == None).values(ended_at=now)
        )
        self.session.add(RegimeHistory(regime=new_regime, confidence=confidence, started_at=now))
        await self.session.flush()

    async def save_performance_snapshot(self, balance: Decimal, equity: Decimal, daily_pnl: Decimal):
        stats = await self.get_trade_stats()
        snapshot = PerformanceSnapshot(
            balance=balance, equity=equity, daily_pnl=daily_pnl,
            win_rate=Decimal(str(stats["win_rate"])), total_trades=stats["total_trades"]
        )
        self.session.add(snapshot)
        await self.session.flush()

    async def get_symbol_in_flight(self, symbol: str) -> bool:
        query = select(TradeRecord).where(and_(TradeRecord.symbol == symbol, TradeRecord.is_open == True))
        result = await self.session.execute(query)
        return result.scalars().first() is not None

    async def update_trade_status(self, pos_id: str, status_data: Dict[str, Any]):
        await self.session.execute(
            update(TradeRecord).where(TradeRecord.id == pos_id).values(**status_data)
        )
        await self.session.flush()

async def save_trade(session: AsyncSession, trade: ClosedTrade) -> TradeRecord:
    trade_data = {
        "id": trade.id,
        "symbol": trade.symbol,
        "side": trade.side.value if hasattr(trade.side, 'value') else trade.side,
        "entry_price": trade.entry_price,
        "quantity": trade.quantity,
        "exit_price": trade.exit_price,
        "pnl": trade.pnl,
        "pnl_percent": trade.pnl_percent,
        "is_open": False,
        "closed_at": datetime.utcnow()
    }
    record = TradeRecord(**trade_data)
    session.add(record)
    await session.flush()
    return record

async def get_recent_trades(session: AsyncSession, limit: int = 50) -> list[TradeRecord]:
    query = select(TradeRecord).order_by(TradeRecord.closed_at.desc()).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())

async def get_daily_pnl(session: AsyncSession, date_val: date) -> Decimal:
    start = datetime(date_val.year, date_val.month, date_val.day)
    query = select(func.sum(TradeRecord.pnl)).where(
        and_(TradeRecord.closed_at >= start, TradeRecord.is_open == False)
    )
    result = await session.execute(query)
    res = result.scalar_one_or_none()
    return Decimal(str(res)) if res else Decimal('0')

async def get_trade_stats(session: AsyncSession) -> dict:
    query = select(
        func.count(TradeRecord.id),
        func.sum(TradeRecord.pnl),
        func.count().filter(TradeRecord.pnl > 0)
    ).where(TradeRecord.is_open == False)
    result = await session.execute(query)
    total, pnl, wins = result.one()
    pnl_out = Decimal(str(pnl)) if pnl else Decimal('0')
    win_rate = (wins / total * 100) if total > 0 else 0
    
    strat_query = select(
        TradeRecord.strategy,
        func.count(TradeRecord.id),
        func.sum(TradeRecord.pnl),
        func.count().filter(TradeRecord.pnl > 0)
    ).where(TradeRecord.is_open == False).group_by(TradeRecord.strategy)
    strat_result = await session.execute(strat_query)
    
    by_strategy = {}
    for strat, s_total, s_pnl, s_wins in strat_result.all():
        s_pnl_val = Decimal(str(s_pnl)) if s_pnl else Decimal('0')
        s_win_rate = (s_wins / s_total * 100) if s_total > 0 else 0
        by_strategy[strat] = {"count": s_total, "pnl": s_pnl_val, "win_rate": float(s_win_rate)}

    return {
        "total_trades": total,
        "win_rate": float(win_rate),
        "total_pnl": pnl_out,
        "by_strategy": by_strategy
    }

async def save_regime_change(session: AsyncSession, old_regime: str, new_regime: str, confidence: float) -> None:
    now = datetime.utcnow()
    await session.execute(
        update(RegimeHistory).where(RegimeHistory.ended_at == None).values(ended_at=now)
    )
    session.add(RegimeHistory(regime=new_regime, confidence=confidence, started_at=now))
    await session.flush()

async def save_performance_snapshot(session: AsyncSession, balance: Decimal, equity: Decimal, daily_pnl: Decimal) -> None:
    stats = await get_trade_stats(session)
    snapshot = PerformanceSnapshot(
        balance=balance, equity=equity, daily_pnl=daily_pnl,
        win_rate=Decimal(str(stats["win_rate"])), total_trades=stats["total_trades"]
    )
    session.add(snapshot)
    await session.flush()
