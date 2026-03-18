from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis, from_url
from app.db.session import AsyncSessionLocal
from app.execution.binance_client import BinanceSpotClient
from app.regime.engine import MarketRegimeEngine
from app.strategies.router import StrategyRouter
from app.risk.engine import RiskEngine
from app.execution.trade_manager import TradeManager
from app.db.repository import TradingRepository
from app.core.config import settings

_redis: Optional[Redis] = None
_binance_client: Optional[BinanceSpotClient] = None
_regime_engine: Optional[MarketRegimeEngine] = None
_strategy_router: Optional[StrategyRouter] = None
_risk_engine: Optional[RiskEngine] = None

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = await from_url(settings.REDIS_URL, decode_responses=True)
    return _redis

async def get_binance() -> BinanceSpotClient:
    global _binance_client
    if _binance_client is None:
        _binance_client = BinanceSpotClient()
        await _binance_client.connect()
    return _binance_client

async def get_regime_engine() -> MarketRegimeEngine:
    global _regime_engine
    if _regime_engine is None:
        _regime_engine = MarketRegimeEngine()
    return _regime_engine

async def get_strategy_router() -> StrategyRouter:
    global _strategy_router
    if _strategy_router is None:
        _strategy_router = StrategyRouter()
    return _strategy_router

async def get_risk_engine() -> RiskEngine:
    global _risk_engine
    if _risk_engine is None:
        _risk_engine = RiskEngine()
    return _risk_engine

async def get_repository(db: AsyncSession) -> TradingRepository:
    return TradingRepository(db)

async def get_trade_manager() -> TradeManager:
    global _binance_client
    from app.db.session import engine 
    return getattr(get_trade_manager, "_singleton", None)
