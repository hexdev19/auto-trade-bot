import decimal
from typing import Optional, Any
from datetime import datetime, timedelta
from app.models.domain import TradeSignal, RiskDecision, RiskStatus, BotStatus, RiskMetrics
from app.core.config import settings

class RiskEngine:
    def __init__(self, settings_obj: Any):
        self.settings = settings_obj
        self.peak_balance = decimal.Decimal('0')
        self.consecutive_losses = 0
        self.cooldown_until: Optional[datetime] = None
        self._status = BotStatus.RUNNING

    def set_status(self, status: BotStatus):
        self._status = status

    def get_metrics(self) -> RiskMetrics:
        return RiskMetrics(
            bot_status=self._status,
            peak_balance=self.peak_balance,
            consecutive_losses=self.consecutive_losses,
            cooldown_active=bool(self.cooldown_until and datetime.utcnow() < self.cooldown_until)
        )

    def _calculate_size(self, balance: decimal.Decimal, entry: decimal.Decimal, sl: decimal.Decimal) -> decimal.Decimal:
        risk = balance * self.settings.RISK_PER_TRADE_PCT
        dist = abs(entry - sl)
        if dist == 0: return decimal.Decimal('0')
        qty = risk / dist
        if qty * entry > self.settings.MAX_POSITION_SIZE_USD:
            qty = self.settings.MAX_POSITION_SIZE_USD / entry
        return qty.quantize(decimal.Decimal("0.00001"))

    def _atr_sl(self, entry: decimal.Decimal, atr: float, side: str) -> decimal.Decimal:
        dist = max(decimal.Decimal(str(atr)) * decimal.Decimal("1.5"), entry * decimal.Decimal("0.002"))
        return entry - dist if side == "BUY" else entry + dist

    async def validate_trade(self, signal: TradeSignal, balance: decimal.Decimal, daily_pnl: decimal.Decimal) -> RiskDecision:
        if self.cooldown_until and datetime.utcnow() < self.cooldown_until:
            return RiskDecision(status=RiskStatus.REJECTED, reason="Cooldown active")

        if daily_pnl <= -(balance * self.settings.MAX_DAILY_LOSS_PCT):
            return RiskDecision(status=RiskStatus.REJECTED, reason="Daily loss limit")

        if self.consecutive_losses >= self.settings.MAX_CONSECUTIVE_LOSSES:
            self.cooldown_until = datetime.utcnow() + timedelta(minutes=self.settings.COOLDOWN_MINUTES)
            self.consecutive_losses = 0
            return RiskDecision(status=RiskStatus.REJECTED, reason="Consecutive losses")

        if balance > self.peak_balance: self.peak_balance = balance
        if self.peak_balance > 0 and (self.peak_balance - balance) / self.peak_balance >= self.settings.MAX_DRAWDOWN_PCT:
            return RiskDecision(status=RiskStatus.REJECTED, reason="Max drawdown")

        atr = signal.indicators.get("atr", 0.0)
        sl = self._atr_sl(signal.price, atr, signal.side.value)
        tp = signal.price + (abs(signal.price - sl) * decimal.Decimal('2.0'))
        qty = self._calculate_size(balance, signal.price, sl)

        if qty <= 0: return RiskDecision(status=RiskStatus.REJECTED, reason="Invalid size")

        return RiskDecision(RiskStatus.APPROVED, None, qty, sl, tp)

    def record_trade_result(self, is_win: bool):
        if is_win: self.consecutive_losses = 0
        else: self.consecutive_losses += 1
