import decimal
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
        return decimal.Decimal(str(res)) if res else decimal.Decimal('0')

    async def get_trade_stats(self) -> Dict[str, Any]:
        query = select(
            func.count(TradeRecord.id),
            func.sum(TradeRecord.pnl),
            func.count().filter(TradeRecord.pnl > 0)
        ).where(TradeRecord.is_open == False)
        result = await self.session.execute(query)
        total, pnl, wins = result.one()
        pnl_out = decimal.Decimal(str(pnl)) if pnl else decimal.Decimal('0')
        win_rate = (wins / total * 100) if total > 0 else 0
        
        strat_query = select(
            TradeRecord.strategy_name,
            func.count(TradeRecord.id),
            func.sum(TradeRecord.pnl),
            func.count().filter(TradeRecord.pnl > 0)
        ).where(TradeRecord.is_open == False).group_by(TradeRecord.strategy_name)
        strat_result = await self.session.execute(strat_query)
        
        by_strategy = {}
        for strat, s_total, s_pnl, s_wins in strat_result.all():
            s_pnl_val = decimal.Decimal(str(s_pnl)) if s_pnl else decimal.Decimal('0')
            s_win_rate = (s_wins / s_total * 100) if s_total > 0 else 0
            by_strategy[strat] = {"count": s_total, "pnl": s_pnl_val, "win_rate": float(s_win_rate)}

        return {
            "total_trades": total,
            "win_rate": float(win_rate),
            "total_pnl": pnl_out,
            "by_strategy": by_strategy
        }

    async def get_open_trades(self) -> List[TradeRecord]:
        query = select(TradeRecord).where(TradeRecord.is_open == True)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_trade_by_id(self, trade_id: str) -> Optional[TradeRecord]:
        query = select(TradeRecord).where(TradeRecord.id == trade_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
