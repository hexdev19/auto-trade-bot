# backend/utils/error_handler.py

import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, Union
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from binance.exceptions import BinanceAPIException, BinanceOrderException, BinanceRequestException
import asyncio
from utils.discord import send_discord_notification

# Setup logging
logger = logging.getLogger(__name__)

# Error code mappings
BINANCE_ERROR_CODES = {
    -1000: "UNKNOWN",
    -1001: "DISCONNECTED",
    -1002: "UNAUTHORIZED",
    -1003: "TOO_MANY_REQUESTS",
    -1006: "UNEXPECTED_RESP",
    -1007: "TIMEOUT",
    -1013: "INVALID_QUANTITY",
    -1014: "UNKNOWN_ORDER_COMPOSITION",
    -1015: "TOO_MANY_ORDERS",
    -1016: "SERVICE_SHUTTING_DOWN",
    -1020: "UNSUPPORTED_OPERATION",
    -1021: "INVALID_TIMESTAMP",
    -1022: "INVALID_SIGNATURE",
    -2010: "NEW_ORDER_REJECTED",
    -2011: "CANCEL_REJECTED",
    -2013: "NO_SUCH_ORDER",
    -2014: "BAD_API_KEY_FMT",
    -2015: "REJECTED_MBX_KEY",
    -2016: "NO_TRADING_WINDOW",
    -2018: "BALANCE_NOT_SUFFICIENT",
    -2019: "MARGIN_NOT_SUFFICIENT",
    -2021: "ORDER_WOULD_IMMEDIATELY_TRIGGER"
}

# Custom error classes
class TradingError(Exception):
    """Base trading error"""
    def __init__(self, message: str, error_code: str = None, details: Dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "TRADING_ERROR"
        self.details = details or {}
        self.timestamp = datetime.utcnow()


class InsufficientBalanceError(TradingError):
    """Insufficient balance error"""
    def __init__(self, required: float, available: float, asset: str):
        message = f"Insufficient {asset} balance. Required: {required}, Available: {available}"
        details = {
            "required_balance": required,
            "available_balance": available,
            "asset": asset
        }
        super().__init__(message, "INSUFFICIENT_BALANCE", details)


class InvalidOrderError(TradingError):
    """Invalid order parameters error"""
    def __init__(self, message: str, order_data: Dict = None):
        details = {"order_data": order_data} if order_data else {}
        super().__init__(message, "INVALID_ORDER", details)


class MarketDataError(TradingError):
    """Market data retrieval error"""
    def __init__(self, symbol: str, message: str = None):
        message = message or f"Failed to retrieve market data for {symbol}"
        details = {"symbol": symbol}
        super().__init__(message, "MARKET_DATA_ERROR", details)


class RateLimitError(TradingError):
    """Rate limit exceeded error"""
    def __init__(self, retry_after: int = None):
        message = "API rate limit exceeded"
        details = {"retry_after": retry_after} if retry_after else {}
        super().__init__(message, "RATE_LIMIT_EXCEEDED", details)


class ConnectionError(TradingError):
    """Connection error"""
    def __init__(self, service: str, message: str = None):
        message = message or f"Connection failed to {service}"
        details = {"service": service}
        super().__init__(message, "CONNECTION_ERROR", details)


class ErrorHandler:
    """Centralized error handling and logging"""
    
    def __init__(self):
        self.error_counts = {}
        self.last_notifications = {}
        self.notification_cooldown = 300  # 5 minutes
    
    async def handle_binance_error(self, error: BinanceAPIException, user_id: str = None, 
                                  symbol: str = None) -> TradingError:
        """Handle Binance API errors"""
        try:
            error_code = error.code
            error_msg = error.message
            
            # Map Binance error codes to our error types
            if error_code == -2018:  # Insufficient balance
                return InsufficientBalanceError(0, 0, "UNKNOWN")
            elif error_code == -1003:  # Too many requests
                return RateLimitError(retry_after=60)
            elif error_code in [-1013, -1014, -2010]:  # Invalid order
                return InvalidOrderError(error_msg)
            elif error_code in [-1000, -1001, -1006, -1007]:  # Connection issues
                return ConnectionError("Binance API", error_msg)
            else:
                # Generic trading error
                trading_error = TradingError(
                    message=error_msg,
                    error_code=BINANCE_ERROR_CODES.get(error_code, "UNKNOWN_BINANCE_ERROR"),
                    details={
                        "binance_code": error_code,
                        "binance_message": error_msg,
                        "symbol": symbol
                    }
                )
            
            # Log the error
            await self._log_error(trading_error, user_id, symbol)
            
            # Send notification if appropriate
            await self._maybe_send_error_notification(trading_error, user_id)
            
            return trading_error
            
        except Exception as e:
            logger.error(f"Error handling Binance error: {e}")
            return TradingError("Error processing Binance API error", "ERROR_HANDLER_FAILED")
    
    async def handle_generic_error(self, error: Exception, context: str, 
                                 user_id: str = None, additional_data: Dict = None) -> TradingError:
        """Handle generic errors"""
        try:
            error_message = str(error)
            error_type = type(error).__name__
            
            # Create trading error
            trading_error = TradingError(
                message=f"{context}: {error_message}",
                error_code=f"GENERIC_{error_type.upper()}",
                details={
                    "original_error": error_type,
                    "context": context,
                    "additional_data": additional_data or {}
                }
            )
            
            # Log the error
            await self._log_error(trading_error, user_id)
            
            # Send notification for critical errors
            if self._is_critical_error(error):
                await self._maybe_send_error_notification(trading_error, user_id)
            
            return trading_error
            
        except Exception as e:
            logger.error(f"Error in generic error handler: {e}")
            return TradingError("Error in error handler", "ERROR_HANDLER_FAILED")
    
    async def _log_error(self, error: TradingError, user_id: str = None, symbol: str = None):
        """Log error with appropriate level"""
        try:
            error_key = f"{error.error_code}_{user_id or 'global'}"
            self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
            
            log_data = {
                "error_code": error.error_code,
                "message": error.message,
                "user_id": user_id,
                "symbol": symbol,
                "count": self.error_counts[error_key],
                "details": error.details,
                "timestamp": error.timestamp.isoformat()
            }
            
            # Determine log level based on error type
            if error.error_code in ["RATE_LIMIT_EXCEEDED", "CONNECTION_ERROR"]:
                logger.warning(f"Trading warning: {log_data}")
            elif error.error_code in ["INSUFFICIENT_BALANCE", "INVALID_ORDER"]:
                logger.info(f"Trading info: {log_data}")
            else:
                logger.error(f"Trading error: {log_data}")
                
        except Exception as e:
            logger.error(f"Error logging error: {e}")
    
    async def _maybe_send_error_notification(self, error: TradingError, user_id: str = None):
        """Send error notification if appropriate"""
        try:
            if not user_id:
                return
            
            # Check notification cooldown
            notification_key = f"{error.error_code}_{user_id}"
            now = datetime.utcnow()
            
            if notification_key in self.last_notifications:
                time_since_last = (now - self.last_notifications[notification_key]).total_seconds()
                if time_since_last < self.notification_cooldown:
                    return
            
            # Determine if we should send notification
            should_notify = (
                error.error_code in [
                    "INSUFFICIENT_BALANCE", 
                    "CONNECTION_ERROR", 
                    "RATE_LIMIT_EXCEEDED",
                    "INVALID_ORDER"
                ] or 
                "CRITICAL" in error.error_code
            )
            
            if should_notify:
                # Send Discord notification
                await send_discord_notification(
                    message=f"Trading Error: {error.message}",
                    user_id=user_id,
                    error=True,
                    error_type=error.error_code
                )
                
                # Update last notification time
                self.last_notifications[notification_key] = now
                
        except Exception as e:
            logger.error(f"Error sending error notification: {e}")
    
    def _is_critical_error(self, error: Exception) -> bool:
        """Determine if error is critical"""
        critical_error_types = [
            ConnectionRefusedError,
            TimeoutError,
            MemoryError,
            KeyboardInterrupt
        ]
        
        return any(isinstance(error, error_type) for error_type in critical_error_types)
    
    def get_error_stats(self, user_id: str = None) -> Dict[str, Any]:
        """Get error statistics"""
        try:
            if user_id:
                user_errors = {
                    key: count for key, count in self.error_counts.items() 
                    if key.endswith(f"_{user_id}")
                }
                return {
                    "user_errors": user_errors,
                    "total_errors": sum(user_errors.values()),
                    "unique_error_types": len(user_errors)
                }
            else:
                return {
                    "all_errors": dict(self.error_counts),
                    "total_errors": sum(self.error_counts.values()),
                    "unique_error_types": len(self.error_counts)
                }
                
        except Exception as e:
            logger.error(f"Error getting error stats: {e}")
            return {"error": "Failed to get error statistics"}
    
    async def reset_error_count(self, error_code: str, user_id: str = None):
        """Reset error count for specific error type"""
        try:
            error_key = f"{error_code}_{user_id or 'global'}"
            self.error_counts.pop(error_key, None)
            logger.info(f"Reset error count for {error_key}")
        except Exception as e:
            logger.error(f"Error resetting error count: {e}")


# Global error handler instance
error_handler = ErrorHandler()


# FastAPI exception handlers
async def trading_error_handler(request: Request, exc: TradingError) -> JSONResponse:
    """Handle TradingError exceptions"""
    return JSONResponse(
        status_code=400,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details,
            "timestamp": exc.timestamp.isoformat()
        }
    )


async def binance_error_handler(request: Request, exc: BinanceAPIException) -> JSONResponse:
    """Handle Binance API exceptions"""
    trading_error = await error_handler.handle_binance_error(exc)
    
    # Determine HTTP status code based on Binance error
    if exc.code == -2018:  # Insufficient balance
        status_code = 400
    elif exc.code == -1003:  # Rate limit
        status_code = 429
    elif exc.code in [-1021, -1022]:  # Auth errors
        status_code = 401
    else:
        status_code = 500
    
    return JSONResponse(
        status_code=status_code,
        content={
            "error": trading_error.error_code,
            "message": trading_error.message,
            "details": trading_error.details,
            "timestamp": trading_error.timestamp.isoformat()
        }
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all other exceptions"""
    try:
        # Don't handle HTTP exceptions here
        if isinstance(exc, HTTPException):
            raise exc
        
        # Log the full traceback
        logger.error(f"Unhandled exception: {exc}")
        logger.error(traceback.format_exc())
        
        # Create generic error response
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.critical(f"Error in exception handler: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "CRITICAL_ERROR",
                "message": "Critical system error",
                "timestamp": datetime.utcnow().isoformat()
            }
        )


# Utility functions for error handling
async def handle_with_retries(func, max_retries: int = 3, delay: float = 1.0, 
                             backoff: float = 2.0, user_id: str = None):
    """Execute function with retry logic"""
    last_error = None
    current_delay = delay
    
    for attempt in range(max_retries):
        try:
            return await func()
        except BinanceAPIException as e:
            last_error = await error_handler.handle_binance_error(e, user_id)
            
            # Don't retry certain errors
            if e.code in [-2018, -1021, -1022]:  # Balance, auth errors
                raise last_error
                
        except Exception as e:
            last_error = await error_handler.handle_generic_error(
                e, f"Retry attempt {attempt + 1}", user_id
            )
        
        if attempt < max_retries - 1:
            logger.info(f"Retrying in {current_delay} seconds (attempt {attempt + 1}/{max_retries})")
            await asyncio.sleep(current_delay)
            current_delay *= backoff
    
    # All retries failed
    logger.error(f"All {max_retries} retry attempts failed")
    raise last_error


def log_performance(func_name: str, duration: float, user_id: str = None):
    """Log function performance"""
    try:
        if duration > 5.0:  # Log slow operations
            logger.warning(f"Slow operation: {func_name} took {duration:.2f}s (user: {user_id})")
        elif duration > 1.0:
            logger.info(f"Operation: {func_name} took {duration:.2f}s (user: {user_id})")
    except Exception as e:
        logger.error(f"Error logging performance: {e}")


def create_error_context(user_id: str = None, symbol: str = None, 
                        operation: str = None, **kwargs) -> Dict[str, Any]:
    """Create error context for logging"""
    context = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "symbol": symbol,
        "operation": operation
    }
    context.update(kwargs)
    return {k: v for k, v in context.items() if v is not None}