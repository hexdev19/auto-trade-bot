from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.repository import TradingRepository
from app.di.container import DIContainer, get_container

async def get_repository(
    session: AsyncSession = Depends(get_db)
) -> TradingRepository:
    return TradingRepository(session)

async def get_risk_engine(
    container: DIContainer = Depends(get_container)
) -> 'RiskEngine':
    return container.risk_engine

async def get_binance(
    container: DIContainer = Depends(get_container)
) -> 'BinanceSpotClient':
    return container.binance_client

async def get_notifier(
    container: DIContainer = Depends(get_container)
) -> 'TelegramNotifier':
    return container.notifier

async def get_regime_engine(
    container: DIContainer = Depends(get_container)
) -> 'MarketRegimeEngine':
    return container.regime_engine

async def get_strategy_router(
    container: DIContainer = Depends(get_container)
) -> 'StrategyRouter':
    return container.strategy_router

async def get_trade_manager(
    container: DIContainer = Depends(get_container)
) -> 'TradeManager':
    return container.trade_manager
