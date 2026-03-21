import asyncio
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.db.session import AsyncSessionLocal, engine
from app.execution.position_tracker import PositionTracker
from app.execution.order_service import OrderExecutionService
from app.execution.position_monitor import PositionMonitor
from app.db.repository import TradingRepository
from app.risk.engine import RiskEngine
from app.execution.binance_client import BinanceSpotClient
from app.notifications.notifier import TelegramNotifier
from app.regime.engine import MarketRegimeEngine
from app.strategies.router import StrategyRouter

class DIContainer:
    _instance: Optional['DIContainer'] = None
    _lock = asyncio.Lock()

    def __init__(self):
        self.risk_engine: Optional[RiskEngine] = None
        self.binance_client: Optional[BinanceSpotClient] = None
        self.notifier: Optional[TelegramNotifier] = None
        self.regime_engine: Optional[MarketRegimeEngine] = None
        self.strategy_router: Optional[StrategyRouter] = None
        self.position_tracker: Optional[PositionTracker] = None
        self.order_service: Optional[OrderExecutionService] = None
        self.position_monitor: Optional[PositionMonitor] = None

    @classmethod
    async def get_instance(cls) -> 'DIContainer':
        if not cls._instance:
            async with cls._lock:
                if not cls._instance:
                    cls._instance = cls()
                    await cls._instance.initialize()
        return cls._instance

    async def initialize(self):
        self.risk_engine = RiskEngine(settings)
        self.binance_client = BinanceSpotClient(
            api_key=settings.BINANCE_API_KEY.get_secret_value(),
            secret_key=settings.BINANCE_SECRET_KEY.get_secret_value(),
            testnet=settings.BINANCE_TESTNET
        )
        self.notifier = TelegramNotifier()
        self.regime_engine = MarketRegimeEngine()
        self.strategy_router = StrategyRouter()
        
        # Phase 3 services
        self.position_tracker = PositionTracker()
        self.order_service = OrderExecutionService(
            exchange=self.binance_client,
            repository=TradingRepository(None),  # Placeholder; use get_order_service() for proper session
            tracker=self.position_tracker,
            notifier=self.notifier
        )
        self.position_monitor = PositionMonitor(
            exchange=self.binance_client,
            tracker=self.position_tracker,
            on_trigger=self.order_service.close_position
        )

    def get_order_service(self, session: AsyncSession) -> OrderExecutionService:
        """Create an OrderExecutionService with a proper DB session."""
        return OrderExecutionService(
            exchange=self.binance_client,
            repository=TradingRepository(session),
            tracker=self.position_tracker,
            notifier=self.notifier
        )

    def get_repository(self, session: AsyncSession) -> TradingRepository:
        return TradingRepository(session)

async def get_container() -> DIContainer:
    return await DIContainer.get_instance()

