import decimal
from decimal import Decimal
from typing import Optional
from datetime import datetime
from app.core.logging import logger

class DrawdownTracker:
    def __init__(self, max_drawdown_allowed: float = 20.0):
        self.max_drawdown_allowed = decimal.Decimal(str(max_drawdown_allowed))
        self.peak_equity = decimal.Decimal('0')
        self.current_drawdown = decimal.Decimal('0')

    def update(self, current_equity: Decimal) -> Decimal:
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
            self.current_drawdown = decimal.Decimal('0')
        elif self.peak_equity > 0:
            self.current_drawdown = ((self.peak_equity - current_equity) / self.peak_equity) * 100
            
        if self.current_drawdown > self.max_drawdown_allowed:
            logger.warning(f"CRITICAL: Max drawdown exceeded! Current: {self.current_drawdown:.2f}% | Max: {self.max_drawdown_allowed}%")
            
        return self.current_drawdown

    def is_halt_required(self) -> bool:
        return self.current_drawdown >= self.max_drawdown_allowed
