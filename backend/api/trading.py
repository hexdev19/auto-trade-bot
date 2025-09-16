import logging
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Path

from services.trading_service import TradingService
from schemas.trading_schema import (
    MarketOrderRequest, LimitOrderRequest, StopLossOrderRequest,
    TakeProfitOrderRequest, TradingConfigRequest, StrategyConfigRequest,
    PriceData, AccountBalanceResponse, OrderResponse, TradeResponse,
    TradingStatsResponse, MarketDataResponse, TradingSignalResponse,
    AutoTradingStatusResponse, HistoricalDataRequest, HistoricalDataResponse,
    TradingErrorResponse, ErrorResponse, TradingSymbol
)
from app.config import BINANCE_API_KEY, BINANCE_SECRET_KEY

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Global trading service instance - no auth required for development/testing
trading_service = None

async def get_trading_service() -> TradingService:
    """
    Get trading service instance without authentication.
    """
    global trading_service
    
    if not trading_service:
        try:
            trading_service = TradingService(
                api_key=BINANCE_API_KEY,
                api_secret=BINANCE_SECRET_KEY,
                testnet=True  # Use testnet for development
            )
            logger.info("Trading service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize trading service: {e}")
            raise HTTPException(status_code=500, detail="Trading service initialization failed")
    
    return trading_service

# =============================================================================
# MARKET DATA ENDPOINTS
# =============================================================================

@router.get("/price/{symbol}", response_model=PriceData)
async def get_current_price(
    symbol: TradingSymbol = Path(..., description="Trading symbol (BTCUSDT, ETHUSDT)")
):
    """Get current market price for a trading symbol"""
    try:
        trading_service = await get_trading_service()
        price_data = await trading_service.get_price_data(symbol.value)
        return price_data
    except Exception as e:
        logger.error(f"Error getting price for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get price for {symbol}")

@router.get("/market-data/{symbol}", response_model=MarketDataResponse)
async def get_market_analysis(
    symbol: TradingSymbol = Path(..., description="Trading symbol")
):
    """Get comprehensive market analysis with technical indicators"""
    try:
        trading_service = await get_trading_service()
        market_data = await trading_service.analyze_market(symbol.value)
        return market_data
    except Exception as e:
        logger.error(f"Error getting market analysis for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze market for {symbol}")

@router.get("/signal/{symbol}", response_model=TradingSignalResponse)
async def get_trading_signal(
    symbol: TradingSymbol = Path(..., description="Trading symbol")
):
    """Generate trading signal based on technical analysis"""
    try:
        trading_service = await get_trading_service()
        signal = await trading_service.generate_trading_signal(symbol.value)
        return signal
    except Exception as e:
        logger.error(f"Error generating trading signal for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate signal for {symbol}")

@router.post("/historical-data", response_model=HistoricalDataResponse)
async def get_historical_data(request: HistoricalDataRequest):
    """Get historical candlestick data for technical analysis"""
    try:
        trading_service = await get_trading_service()
        historical_data = await trading_service.get_historical_data(
            symbol=request.symbol,
            interval=request.interval,
            start_time=request.start_time,
            end_time=request.end_time
        )
        return historical_data
    except Exception as e:
        logger.error(f"Error getting historical data: {e}")
        raise HTTPException(status_code=500, detail="Failed to get historical data")

# =============================================================================
# ACCOUNT MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("/balance", response_model=AccountBalanceResponse)
async def get_account_balance():
    """Get account balance from Binance testnet"""
    try:
        trading_service = await get_trading_service()
        balance = await trading_service.get_balance()
        return balance
    except Exception as e:
        logger.error(f"Error getting account balance: {e}")
        raise HTTPException(status_code=500, detail="Failed to get account balance")

# =============================================================================
# TRADING ORDER ENDPOINTS
# =============================================================================

@router.post("/order/market", response_model=OrderResponse)
async def place_market_order(order: MarketOrderRequest):
    """Place a market order"""
    try:
        trading_service = await get_trading_service()
        result = await trading_service.place_market_order(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity
        )
        
        # Send notification
        try:
            await trading_service.send_order_notification(result, "market", "user_123")
        except Exception as e:
            logger.warning(f"Failed to send order notification: {e}")
        
        return result
    except Exception as e:
        logger.error(f"Error placing market order: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to place market order: {str(e)}")

@router.post("/order/limit", response_model=OrderResponse)
async def place_limit_order(order: LimitOrderRequest):
    """Place a limit order"""
    try:
        trading_service = await get_trading_service()
        result = await trading_service.place_limit_order(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=order.price
        )
        
        # Send notification
        try:
            await trading_service.send_order_notification(result, "limit", "user_123")
        except Exception as e:
            logger.warning(f"Failed to send order notification: {e}")
        
        return result
    except Exception as e:
        logger.error(f"Error placing limit order: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to place limit order: {str(e)}")

@router.post("/order/stop-loss", response_model=OrderResponse)
async def place_stop_loss_order(order: StopLossOrderRequest):
    """Place a stop-loss order"""
    try:
        trading_service = await get_trading_service()
        result = await trading_service.place_stop_loss_order(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            stop_price=order.stop_price
        )
        
        # Send notification
        try:
            await trading_service.send_order_notification(result, "stop_loss", "user_123")
        except Exception as e:
            logger.warning(f"Failed to send order notification: {e}")
        
        return result
    except Exception as e:
        logger.error(f"Error placing stop-loss order: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to place stop-loss order: {str(e)}")

@router.post("/order/take-profit", response_model=OrderResponse)
async def place_take_profit_order(order: TakeProfitOrderRequest):
    """Place a take-profit order"""
    try:
        trading_service = await get_trading_service()
        result = await trading_service.place_take_profit_order(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            stop_price=order.stop_price
        )
        
        # Send notification
        try:
            await trading_service.send_order_notification(result, "take_profit", "user_123")
        except Exception as e:
            logger.warning(f"Failed to send order notification: {e}")
        
        return result
    except Exception as e:
        logger.error(f"Error placing take-profit order: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to place take-profit order: {str(e)}")

@router.delete("/order/{order_id}")
async def cancel_order(
    order_id: str = Path(..., description="Order ID to cancel"),
    symbol: TradingSymbol = Query(..., description="Trading symbol")
):
    """Cancel an open order"""
    try:
        trading_service = await get_trading_service()
        result = await trading_service.cancel_order(symbol.value, order_id)
        
        # Send notification
        try:
            await trading_service.send_cancel_notification(order_id, symbol.value, "user_123")
        except Exception as e:
            logger.warning(f"Failed to send cancel notification: {e}")
        
        return {"status": "success", "message": f"Order {order_id} cancelled"}
    except Exception as e:
        logger.error(f"Error cancelling order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel order: {str(e)}")

# =============================================================================
# TRADING HISTORY AND STATS ENDPOINTS
# =============================================================================

@router.get("/trades", response_model=List[TradeResponse])
async def get_trade_history(
    symbol: Optional[TradingSymbol] = Query(None, description="Filter by symbol"),
    limit: int = Query(100, ge=1, le=1000, description="Number of trades to return")
):
    """Get trading history"""
    try:
        trading_service = await get_trading_service()
        trades = await trading_service.get_trade_history(
            symbol=symbol.value if symbol else None,
            limit=limit
        )
        return trades
    except Exception as e:
        logger.error(f"Error getting trade history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get trade history")

@router.get("/stats", response_model=TradingStatsResponse)
async def get_trading_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days for stats calculation")
):
    """Get trading statistics for the specified period"""
    try:
        trading_service = await get_trading_service()
        stats = await trading_service.get_trading_stats("user_123", days)
        return stats
    except Exception as e:
        logger.error(f"Error getting trading stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get trading statistics")

# =============================================================================
# AUTO-TRADING ENDPOINTS
# =============================================================================

@router.post("/auto-trading/start")
async def start_auto_trading(config: TradingConfigRequest):
    """Start automated trading with the given configuration"""
    try:
        trading_service = await get_trading_service()
        result = await trading_service.start_auto_trading("user_123", config.dict())
        return {"status": "success", "message": "Auto-trading started", "config": result}
    except Exception as e:
        logger.error(f"Error starting auto-trading: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start auto-trading: {str(e)}")

@router.post("/auto-trading/stop")
async def stop_auto_trading():
    """Stop automated trading"""
    try:
        trading_service = await get_trading_service()
        await trading_service.stop_auto_trading("user_123")
        return {"status": "success", "message": "Auto-trading stopped"}
    except Exception as e:
        logger.error(f"Error stopping auto-trading: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop auto-trading: {str(e)}")

@router.get("/auto-trading/status", response_model=AutoTradingStatusResponse)
async def get_auto_trading_status():
    """Get current auto-trading status and configuration"""
    try:
        trading_service = await get_trading_service()
        status = await trading_service.get_auto_trading_status("user_123")
        return status
    except Exception as e:
        logger.error(f"Error getting auto-trading status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get auto-trading status")

@router.put("/strategy", response_model=dict)
async def update_trading_strategy(strategy: StrategyConfigRequest):
    """Update trading strategy configuration"""
    try:
        trading_service = await get_trading_service()
        result = await trading_service.update_strategy("user_123", strategy.dict())
        return {"status": "success", "message": "Strategy updated", "strategy": result}
    except Exception as e:
        logger.error(f"Error updating trading strategy: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update strategy: {str(e)}")

# =============================================================================
# HEALTH CHECK ENDPOINTS
# =============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint for trading service"""
    try:
        trading_service = await get_trading_service()
        
        # Test Binance connection
        price_data = await trading_service.get_price_data("BTCUSDT")
        
        return {
            "status": "healthy",
            "service": "trading",
            "binance_connection": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "test_price": price_data.price
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@router.get("/")
async def trading_root():
    """Root endpoint for trading API"""
    return {
        "message": "Trading API v1.0",
        "status": "active",
        "endpoints": {
            "market_data": ["/price/{symbol}", "/market-data/{symbol}", "/signal/{symbol}"],
            "trading": ["/order/market", "/order/limit", "/order/stop-loss", "/order/take-profit"],
            "account": ["/balance", "/trades", "/stats"],
            "auto_trading": ["/auto-trading/start", "/auto-trading/stop", "/auto-trading/status"],
            "health": ["/health"]
        }
    }