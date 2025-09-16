# backend/utils/helpers.py

import uuid
import hashlib
import hmac
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import asyncio
import random
import string
import json
from decimal import Decimal, ROUND_DOWN

# Setup logging
logger = logging.getLogger(__name__)


def generate_client_order_id(user_id: str, prefix: str = "AUTO") -> str:
    """
    Generate a unique client order ID for Binance orders.
    
    Args:
        user_id: User identifier
        prefix: Prefix for the order ID
        
    Returns:
        Unique client order ID
    """
    timestamp = str(int(time.time() * 1000))
    random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    user_hash = hashlib.md5(user_id.encode()).hexdigest()[:6]
    
    # Format: PREFIX_USERHASH_TIMESTAMP_RANDOM
    order_id = f"{prefix}_{user_hash}_{timestamp}_{random_suffix}"
    
    # Ensure it's within Binance's 36 character limit
    if len(order_id) > 36:
        order_id = order_id[:36]
    
    return order_id


def generate_api_signature(query_string: str, secret: str) -> str:
    """
    Generate HMAC SHA256 signature for Binance API requests.
    
    Args:
        query_string: Query parameters string
        secret: API secret key
        
    Returns:
        HMAC signature
    """
    return hmac.new(
        secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def format_decimal(value: Union[float, str, Decimal], precision: int = 8) -> str:
    """
    Format decimal value with specified precision.
    
    Args:
        value: Value to format
        precision: Number of decimal places
        
    Returns:
        Formatted decimal string
    """
    if isinstance(value, str):
        value = Decimal(value)
    elif isinstance(value, float):
        value = Decimal(str(value))
    elif not isinstance(value, Decimal):
        value = Decimal(str(value))
    
    # Round down to avoid precision errors
    quantized = value.quantize(Decimal('0.' + '0' * (precision - 1) + '1'), rounding=ROUND_DOWN)
    return str(quantized)


def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """
    Calculate percentage change between two values.
    
    Args:
        old_value: Original value
        new_value: New value
        
    Returns:
        Percentage change
    """
    if old_value == 0:
        return 0.0
    
    return ((new_value - old_value) / old_value) * 100


def calculate_risk_amount(portfolio_value: float, risk_percentage: float) -> float:
    """
    Calculate risk amount based on portfolio value and risk percentage.
    
    Args:
        portfolio_value: Total portfolio value
        risk_percentage: Risk percentage (0-100)
        
    Returns:
        Risk amount in currency units
    """
    return portfolio_value * (risk_percentage / 100)


def calculate_position_size(risk_amount: float, entry_price: float, stop_loss_price: float) -> float:
    """
    Calculate position size based on risk management.
    
    Args:
        risk_amount: Amount willing to risk
        entry_price: Entry price for the position
        stop_loss_price: Stop loss price
        
    Returns:
        Position size in base currency
    """
    if stop_loss_price == 0 or entry_price == stop_loss_price:
        return 0.0
    
    risk_per_unit = abs(entry_price - stop_loss_price)
    position_size = risk_amount / risk_per_unit
    
    return position_size


def validate_symbol_format(symbol: str) -> bool:
    """
    Validate trading symbol format.
    
    Args:
        symbol: Trading symbol (e.g., BTCUSDT)
        
    Returns:
        True if valid format
    """
    if not symbol or len(symbol) < 6:
        return False
    
    # Basic validation for crypto pairs ending with USDT
    valid_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'DOTUSDT', 'LINKUSDT']
    
    return symbol.upper() in valid_symbols or symbol.upper().endswith('USDT')


def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize sensitive data for logging.
    
    Args:
        data: Data dictionary to sanitize
        
    Returns:
        Sanitized data dictionary
    """
    sensitive_keys = [
        'api_key', 'api_secret', 'password', 'secret', 'token',
        'binance_api_key', 'binance_secret_key', 'email_password'
    ]
    
    sanitized = {}
    for key, value in data.items():
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            if value:
                sanitized[key] = f"***{str(value)[-4:]}" if len(str(value)) > 4 else "***"
            else:
                sanitized[key] = None
        else:
            sanitized[key] = value
    
    return sanitized


def format_currency(amount: float, currency: str = "USD", decimal_places: int = 2) -> str:
    """
    Format currency amount for display.
    
    Args:
        amount: Amount to format
        currency: Currency symbol
        decimal_places: Number of decimal places
        
    Returns:
        Formatted currency string
    """
    if currency.upper() == "USD":
        return f"${amount:,.{decimal_places}f}"
    else:
        return f"{amount:,.{decimal_places}f} {currency}"


def format_percentage(value: float, decimal_places: int = 2) -> str:
    """
    Format percentage for display.
    
    Args:
        value: Percentage value
        decimal_places: Number of decimal places
        
    Returns:
        Formatted percentage string
    """
    return f"{value:.{decimal_places}f}%"


def format_timestamp(timestamp: datetime, format_string: str = "%Y-%m-%d %H:%M:%S UTC") -> str:
    """
    Format timestamp for display.
    
    Args:
        timestamp: Datetime object
        format_string: Format string
        
    Returns:
        Formatted timestamp string
    """
    return timestamp.strftime(format_string)


def is_market_hours(timezone: str = "UTC") -> bool:
    """
    Check if crypto markets are active (they're always active).
    
    Args:
        timezone: Timezone to check
        
    Returns:
        Always True for crypto markets
    """
    return True  # Crypto markets are 24/7


def get_time_until_next_interval(interval_minutes: int) -> int:
    """
    Get seconds until next interval boundary.
    
    Args:
        interval_minutes: Interval in minutes (e.g., 5, 15, 60)
        
    Returns:
        Seconds until next interval
    """
    now = datetime.utcnow()
    current_minute = now.minute
    current_second = now.second
    
    # Calculate minutes until next interval
    minutes_into_interval = current_minute % interval_minutes
    minutes_until_next = interval_minutes - minutes_into_interval
    
    # Calculate total seconds
    seconds_until_next = (minutes_until_next * 60) - current_second
    
    return max(1, seconds_until_next)  # Minimum 1 second


def parse_timeframe(timeframe: str) -> int:
    """
    Parse timeframe string to minutes.
    
    Args:
        timeframe: Timeframe string (e.g., "1m", "5m", "1h", "1d")
        
    Returns:
        Timeframe in minutes
    """
    timeframe = timeframe.lower()
    
    if timeframe.endswith('m'):
        return int(timeframe[:-1])
    elif timeframe.endswith('h'):
        return int(timeframe[:-1]) * 60
    elif timeframe.endswith('d'):
        return int(timeframe[:-1]) * 24 * 60
    elif timeframe.endswith('w'):
        return int(timeframe[:-1]) * 7 * 24 * 60
    else:
        raise ValueError(f"Invalid timeframe format: {timeframe}")


def retry_async(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator for retrying async functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries
        backoff: Backoff multiplier
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}")
                        raise last_exception
            
            raise last_exception
        
        return wrapper
    return decorator


def rate_limit(calls_per_second: float = 1.0):
    """
    Decorator for rate limiting function calls.
    
    Args:
        calls_per_second: Maximum calls per second
    """
    min_interval = 1.0 / calls_per_second
    last_called = {}
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            func_key = f"{func.__module__}.{func.__name__}"
            now = time.time()
            
            if func_key in last_called:
                elapsed = now - last_called[func_key]
                if elapsed < min_interval:
                    await asyncio.sleep(min_interval - elapsed)
            
            last_called[func_key] = time.time()
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


class MovingAverage:
    """Simple moving average calculator"""
    
    def __init__(self, period: int):
        self.period = period
        self.values = []
    
    def add_value(self, value: float) -> Optional[float]:
        """Add a value and return current moving average"""
        self.values.append(value)
        
        if len(self.values) > self.period:
            self.values.pop(0)
        
        if len(self.values) == self.period:
            return sum(self.values) / self.period
        
        return None
    
    def get_current(self) -> Optional[float]:
        """Get current moving average"""
        if len(self.values) == self.period:
            return sum(self.values) / self.period
        return None
    
    def is_ready(self) -> bool:
        """Check if moving average is ready (has enough values)"""
        return len(self.values) == self.period


class RateLimiter:
    """Rate limiter for API calls"""
    
    def __init__(self, max_calls: int, time_window: int):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
    
    async def acquire(self):
        """Acquire permission to make a call"""
        now = time.time()
        
        # Remove old calls outside the time window
        self.calls = [call_time for call_time in self.calls if now - call_time < self.time_window]
        
        # Check if we can make a call
        if len(self.calls) >= self.max_calls:
            # Calculate wait time
            oldest_call = min(self.calls)
            wait_time = self.time_window - (now - oldest_call)
            
            if wait_time > 0:
                logger.debug(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                await asyncio.sleep(wait_time)
        
        # Record this call
        self.calls.append(time.time())


class CircuitBreaker:
    """Circuit breaker for handling failures"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func, *args, **kwargs):
        """Call function through circuit breaker"""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker entering HALF_OPEN state")
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
                logger.info("Circuit breaker reset to CLOSED state")
            
            return result
            
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
            
            raise e


def validate_trading_config(config: Dict[str, Any]) -> List[str]:
    """
    Validate trading configuration.
    
    Args:
        config: Trading configuration dictionary
        
    Returns:
        List of validation errors
    """
    errors = []
    
    # Required fields
    required_fields = ['max_position_size_percentage', 'stop_loss_percentage', 'take_profit_percentage']
    for field in required_fields:
        if field not in config:
            errors.append(f"Missing required field: {field}")
    
    # Validate percentages
    percentage_fields = {
        'max_position_size_percentage': (0.1, 100.0),
        'stop_loss_percentage': (0.1, 50.0),
        'take_profit_percentage': (0.1, 100.0)
    }
    
    for field, (min_val, max_val) in percentage_fields.items():
        if field in config:
            value = config[field]
            if not isinstance(value, (int, float)) or value < min_val or value > max_val:
                errors.append(f"{field} must be between {min_val} and {max_val}")
    
    # Validate symbols
    if 'symbols_to_trade' in config:
        symbols = config['symbols_to_trade']
        if not isinstance(symbols, list) or not symbols:
            errors.append("symbols_to_trade must be a non-empty list")
        else:
            for symbol in symbols:
                if not validate_symbol_format(symbol):
                    errors.append(f"Invalid symbol format: {symbol}")
    
    return errors


def create_error_response(error_code: str, message: str, details: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Create standardized error response.
    
    Args:
        error_code: Error code
        message: Error message
        details: Additional error details
        
    Returns:
        Error response dictionary
    """
    response = {
        'error': error_code,
        'message': message,
        'timestamp': datetime.utcnow().isoformat(),
        'success': False
    }
    
    if details:
        response['details'] = details
    
    return response


def create_success_response(data: Any, message: str = "Success") -> Dict[str, Any]:
    """
    Create standardized success response.
    
    Args:
        data: Response data
        message: Success message
        
    Returns:
        Success response dictionary
    """
    return {
        'success': True,
        'message': message,
        'data': data,
        'timestamp': datetime.utcnow().isoformat()
    }
