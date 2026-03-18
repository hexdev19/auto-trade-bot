from app.models.domain import OpenPosition, ClosedTrade, TradingSide, MarketRegime
from decimal import Decimal

def trade_opened(pos: OpenPosition, strategy: str, regime: str) -> str:
    return (f"🟢 <b>BUY OPENED</b> · {pos.symbol} (SPOT)\n"
            f"Entry: ${pos.entry_price:,.2f} | Qty: {pos.quantity:.4f}\n"
            f"TP: ${pos.take_profit:,.2f} | SL: ${pos.stop_loss:,.2f}\n"
            f"Strategy: {strategy} | Regime: {regime}")

def trade_closed(trade: ClosedTrade, strategy: str, reason: str) -> str:
    icon = "🔴" if trade.pnl < 0 else "🟢"
    return (f"{icon} <b>SELL CLOSED</b> · {trade.symbol}\n"
            f"PnL: {trade.pnl:+.2f} ({trade.pnl_percent:+.2f}%)\n"
            f"Exit: ${trade.exit_price:,.2f} | Reason: {reason}\n"
            f"Strategy: {strategy}")

def regime_changed(old: MarketRegime, new: MarketRegime, snapshot: dict) -> str:
    return (f"🔄 <b>REGIME CHANGE</b>\n"
            f"{old.value} → {new.value}\n"
            f"ADX: {snapshot.get('adx', 0):.1f} | ATR: {snapshot.get('atr', 0):.2f}\n"
            f"Slope: {snapshot.get('slope', 0):.6f}")

def risk_alert(reason: str, daily_pnl: Decimal, balance: Decimal) -> str:
    pnl_perc = (daily_pnl / balance * 100) if balance > 0 else 0
    return (f"⚠️ <b>RISK ALERT</b>\n"
            f"Reason: {reason}\n"
            f"Daily PnL: ${daily_pnl:,.2f} ({pnl_perc:+.2f}%)")

def emergency_halt(reason: str) -> str:
    return (f"🚨 <b>EMERGENCY HALT</b>\n"
            f"{reason}\n"
            f"All positions closed. Manual review required.")
