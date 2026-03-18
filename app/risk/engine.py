from decimal import Decimal
from typing import Optional
from datetime import datetime, timedelta
from app.models.domain import TradeSignal, RiskDecision, RiskStatus
from app.core.config import settings

class RiskEngine:
    def __init__(self):
        self.peak_balance = Decimal('0')
        self.consecutive_losses = 0
        self.cooldown_until: Optional[datetime] = None

    def _calculate_size(self, balance: Decimal, entry: Decimal, sl: Decimal) -> Decimal:
        risk = balance * settings.RISK_PER_TRADE_PCT
        dist = abs(entry - sl)
        if dist == 0: return Decimal('0')
        qty = risk / dist
        if qty * entry > settings.MAX_POSITION_SIZE_USD:
            qty = settings.MAX_POSITION_SIZE_USD / entry
        return qty.quantize(Decimal("0.00001"))

    def _atr_sl(self, entry: Decimal, atr: float, side: str) -> Decimal:
        dist = max(Decimal(str(atr)) * Decimal("1.5"), entry * Decimal("0.002"))
        return entry - dist if side == "BUY" else entry + dist

    async def validate_trade(self, signal: TradeSignal, balance: Decimal, daily_pnl: Decimal) -> RiskDecision:
        if self.cooldown_until and datetime.utcnow() < self.cooldown_until:
            return RiskDecision(status=RiskStatus.REJECTED, reason="Cooldown active")

        if daily_pnl <= -(balance * settings.MAX_DAILY_LOSS_PCT):
            return RiskDecision(status=RiskStatus.REJECTED, reason="Daily loss limit")

        if self.consecutive_losses >= settings.MAX_CONSECUTIVE_LOSSES:
            self.cooldown_until = datetime.utcnow() + timedelta(minutes=settings.COOLDOWN_MINUTES)
            self.consecutive_losses = 0
            return RiskDecision(status=RiskStatus.REJECTED, reason="Consecutive losses")

        if balance > self.peak_balance: self.peak_balance = balance
        if self.peak_balance > 0 and (self.peak_balance - balance) / self.peak_balance >= settings.MAX_DRAWDOWN_PCT:
            return RiskDecision(status=RiskStatus.REJECTED, reason="Max drawdown")

        atr = signal.indicators.get("atr", 0.0)
        sl = self._atr_sl(signal.price, atr, signal.side.value)
        tp = signal.price + (abs(signal.price - sl) * Decimal('2.0'))
        qty = self._calculate_size(balance, signal.price, sl)

        if qty <= 0: return RiskDecision(status=RiskStatus.REJECTED, reason="Invalid size")

        return RiskDecision(RiskStatus.APPROVED, None, qty, sl, tp)

    def record_trade_result(self, is_win: bool):
        if is_win: self.consecutive_losses = 0
        else: self.consecutive_losses += 1
