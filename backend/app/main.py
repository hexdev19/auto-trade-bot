# backend/app/main.py
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from binance.exceptions import BinanceAPIException
import time
from tasks.trading_bot_simple import trading_bot, start_trading_bot, stop_trading_bot
from utils.error_handler import (
    trading_error_handler, binance_error_handler, 
    generic_exception_handler, TradingError
)
from app import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AutoTrade API...")   

    try:
        # Don't auto-start the bot - wait for user to set amount and click start
        logger.info("AutoTrade API ready - bot can be started manually")       
        yield

    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise

    finally:
        logger.info("Shutting down AutoTrade API...")
        
        try:
            # Stop trading bot if running
            if trading_bot.is_running:
                await stop_trading_bot()
                logger.info("Trading bot stopped during shutdown")
            
        except Exception as e:
            logger.error(f"Shutdown error: {e}")
        
        logger.info("AutoTrade API shutdown complete")


app = FastAPI(
    title="AutoTrade BTC Bot",
    description="Automated Bitcoin trading bot - Set your amount and let it find the best buy/sell moments",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
app.add_exception_handler(TradingError, trading_error_handler)
app.add_exception_handler(BinanceAPIException, binance_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests for monitoring"""
    start_time = time.time()
    
    try:
        response = await call_next(request)
        
        # Log request details
        process_time = time.time() - start_time
        logger.info(
            f"{request.method} {request.url.path} - "
            f"Status: {response.status_code} - "
            f"Time: {process_time:.3f}s"
        )
        
        # Add performance headers
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(
            f"{request.method} {request.url.path} - "
            f"Error: {str(e)} - "
            f"Time: {process_time:.3f}s"
        )
        raise


# Essential Bot Management Endpoints
@app.get("/api/v1/bot/status")
async def get_bot_status():
    """Get trading bot status"""
    try:
        status = await trading_bot.get_status()
        return {
            "success": True,
            "data": status,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Error getting bot status: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": time.time()
        }

@app.post("/api/v1/bot/start")
async def start_bot(trading_amount: float = 100.0):
    """Start trading bot with specified USDT amount"""
    try:
        if trading_bot.is_running:
            return {
                "success": True,
                "message": "Trading bot is already running",
                "timestamp": time.time()
            }
        
        # Set the trading amount for the bot
        trading_bot.set_trading_amount(trading_amount)
        asyncio.create_task(start_trading_bot())
        return {
            "success": True,
            "message": f"Trading bot started with ${trading_amount} USDT",
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": time.time()
        }

@app.post("/api/v1/bot/stop")
async def stop_bot():
    """Stop trading bot and return final summary"""
    try:
        final_summary = await trading_bot.stop()
        
        response = {
            "success": True,
            "message": "Trading bot stopped",
            "timestamp": time.time()
        }
        
        # Include final summary if available
        if final_summary:
            response["final_summary"] = final_summary
            logger.info(f"Bot stopped with final summary: {final_summary}")
        
        return response
        
    except Exception as e:
        logger.error(f"Error stopping bot: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": time.time()
        }

@app.get("/api/v1/system/health")
async def health_check():
    """Comprehensive system health check"""
    try:
        health_status = {
            "api": "healthy",
            "trading_bot": "unknown",
            "timestamp": time.time()
        }
        
        # Check trading bot status
        try:
            if trading_bot.is_running:
                health_status["trading_bot"] = "running"
            else:
                health_status["trading_bot"] = "stopped"
        except Exception as e:
            health_status["trading_bot"] = f"error: {str(e)}"
        
        # Determine overall health
        overall_healthy = all(
            status in ["healthy", "running", "stopped"] 
            for status in [health_status["api"], health_status["trading_bot"]]
        )
        
        return {
            "status": "healthy" if overall_healthy else "degraded",
            "services": health_status,
            "version": app.version
        }
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }

@app.get("/api/v1/system/stats")
async def get_system_stats():
    """Get system statistics"""
    try:
        return {
            "success": True,
            "data": {
                "bot_stats": await trading_bot.get_status() if trading_bot.is_running else None,
                "uptime": time.time(),
                "api_version": app.version
            },
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": time.time()
        }

# Root endpoint
@app.get("/", include_in_schema=False)
async def root():
    """API root endpoint"""
    return {
        "app": "AutoTrade BTC Bot",
        "description": "Automated BTC trading bot - Just set your amount and let it trade!",
        "version": app.version,
        "docs": "/docs",
        "health": "/api/v1/system/health",
        "endpoints": {
            "start_bot": "POST /api/v1/bot/start?trading_amount=100.0",
            "stop_bot": "POST /api/v1/bot/stop",
            "bot_status": "GET /api/v1/bot/status"
        },
        "status": "operational"
    }

# Add startup event for additional initialization
@app.on_event("startup")
async def additional_startup():
    """Additional startup tasks"""
    logger.info("Running additional startup tasks...")
    
    try:
        logger.info("Additional startup tasks completed")
    except Exception as e:
        logger.warning(f"Non-critical startup task failed: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(config.PORT),
        reload=False,  # Set to False in production
        log_level="info"
    )
