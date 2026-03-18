from decimal import Decimal
from typing import Optional
from app.core.config import settings
from app.core.logging import logger
from app.core.utils import quantize_decimal

class PositionSizer:
    def __init__(self, risk_per_trade: float = 1.0, max_pos_size: float = 10.0):
        self.risk_per_trade = Decimal(str(risk_per_trade / 100))
        self.max_pos_size_percent = Decimal(str(max_pos_size / 100))

    def calculate_quantity(
        self, 
        symbol: str, 
        current_price: Decimal, 
        equity: Decimal, 
        atr: Optional[Decimal] = None,
        step_size: Decimal = Decimal('0.00001')
    ) -> Decimal:
        if equity <= 0:
            return Decimal('0')
        risk_amount = equity * self.risk_per_trade
        if atr and atr > 0:
            stop_distance = 2 * atr
            quantity = risk_amount / stop_distance
        else:
            max_notional = equity * self.max_pos_size_percent
            quantity = max_notional / current_price
            
        max_notional = equity * self.max_pos_size_percent
        if quantity * current_price > max_notional:
            logger.info(f"Sizing down from {quantity} to {max_notional/current_price} due to max position limit")
            quantity = max_notional / current_price
            
        return quantize_decimal(quantity, step_size)
