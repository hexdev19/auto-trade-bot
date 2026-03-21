import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.api.v1.routes import bot, trades, health
from app.db.session import engine, AsyncSessionLocal
from app.models.base import Base
from app.api.v1.dependencies import (
    get_binance,
    get_risk_engine,
    get_notifier,
    get_regime_engine,
    get_strategy_router,
    get_repository
)
from app.tasks.bot_loop import run_bot_loop
from app.data.candle_store import CandleStore
from app.execution.trade_manager import TradeManager
from app.execution.position_monitor import PositionMonitor
from app.db.repository import TradingRepository
from app.di.container import get_container

setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing trading bot v2 system components...")
    
    container = await get_container()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Initialize services that need connection
    if container.binance_client:
        await container.binance_client.connect()
    
    # Start background tasks
    if container.position_monitor:
        await container.position_monitor.start()
    
    logger.info("Bot components initialized. Starting main loop task...")
    
    bot_task = asyncio.create_task(
        run_bot_loop(
            ws_manager=ws_manager,
            candle_store=candle_store,
            regime_engine=regime_engine,
            strategy_router=strategy_router,
            risk_engine=risk_engine,
            trade_manager=trade_manager,
            position_monitor=position_monitor,
            notifier=notifier,
            session_factory=AsyncSessionLocal,
        ),
        name="TradingBotMainLoop"
    )
    
    yield
    
    logger.info("Shutting down trading bot system...")
    bot_task.cancel()
    try:
        await bot_task
    except asyncio.CancelledError:
        pass
        
    await binance.close()
    await engine.dispose()
    logger.info("Database and API connections closed.")

app = FastAPI(
    title="Binance BTC Trading Bot v2",
    description="Redesigned production-grade async trading bot.",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": str(exc) if settings.DEBUG else "A critical error occurred.",
            "timestamp": datetime.utcnow().isoformat()
        }
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bot.router, prefix="/api/v1")
app.include_router(trades.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")
