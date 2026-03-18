import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1.routes import bot, trades, health
from app.db.session import engine, Base
from app.core.dependencies import get_binance, get_redis, get_trade_manager, get_risk_engine, get_repository
from app.tasks.bot_loop import TradingBotLoop

setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):

    from app.core.logging import logger
    logger.info("Initializing trading bot v2 system components...")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    binance = await get_binance()
    logger.info("Binance AsyncClient connected.")
    
    from app.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        repo = await get_repository(session)
        risk = await get_risk_engine()
        bot_loop_task = TradingBotLoop(binance, repo, risk)
        setattr(get_trade_manager, "_singleton", bot_loop_task.trade_manager)
    
    bg_task = asyncio.create_task(bot_loop_task.start(), name="TradingBotMainLoop")
    logger.info("Background trading task spawned.")
    yield
    logger.info("Shutting down trading bot system...")
    bg_task.cancel()
    try:
        await bg_task
    except asyncio.CancelledError:
        logger.info("Background bot task cancelled successfully.")
        
    await binance.disconnect()
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
    from app.core.logging import logger
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
