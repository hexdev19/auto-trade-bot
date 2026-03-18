import asyncio
import functools
import time
from decimal import Decimal, ROUND_DOWN
from typing import Union, Optional, Any, Callable, TypeVar, ParamSpec
from app.core.logging import logger

T = TypeVar("T")
P = ParamSpec("P")

def retry_async(
    max_retries: int = 3, 
    delay: float = 1.0, 
    backoff: float = 2.0, 
    exceptions: tuple = (Exception,)
):
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            current_delay = delay
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}")
                        raise e
                    
                    logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {current_delay:.2f}s...")
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            return None 
        return wrapper
    return decorator

def to_decimal(value: Union[float, str, int, Decimal]) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))

def format_decimal(value: Decimal, precision: int = 8) -> str:
    return f"{value:.{precision}f}"

def calculate_pnl(entry_price: Decimal, exit_price: Decimal, quantity: Decimal, side: str = "BUY") -> Decimal:
    if side == "BUY":
        return (exit_price - entry_price) * quantity
    else: 
        return (entry_price - exit_price) * quantity

def calculate_pnl_percent(entry_price: Decimal, exit_price: Decimal, side: str = "BUY") -> Decimal:
    if entry_price == Decimal('0'):
        return Decimal('0')
    
    if side == "BUY":
        return ((exit_price - entry_price) / entry_price) * 100
    else: 
        return ((entry_price - exit_price) / entry_price) * 100

def quantize_decimal(value: Decimal, step_size: Decimal) -> Decimal:
    precision_str = format(step_size.normalize(), 'f')
    if '.' in precision_str:
        precision = len(precision_str.split('.')[1])
    else:
        precision = 0
        
    return value.quantize(Decimal(str(10**-precision)), rounding=ROUND_DOWN)
