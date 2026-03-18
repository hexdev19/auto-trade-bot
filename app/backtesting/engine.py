import asyncio
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Optional, Any
from app.models.domain import Candle, TradeSignal, TradingSide, MarketRegime, RiskDecision, RiskStatus, OpenPosition, ClosedTrade
from app.execution.binance_client import BinanceSpotClient
from app.regime.engine import MarketRegimeEngine
from app.strategies.router import StrategyRouter
from app.risk.engine import RiskEngine
from app.core.config import settings
from app.core.logging import logger

class Backtester:
    def __init__(self, fee: Decimal = Decimal("0.001"), slippage: Decimal = Decimal("0.0005")):
        self.fee = fee
        self.slippage = slippage
        self.regime_engine = MarketRegimeEngine()
        self.router = StrategyRouter()
        self.risk_engine = RiskEngine()

    async def load_data(self, client: BinanceSpotClient, symbol: str, start: str, end: str, interval: str = "1m") -> List[Candle]:
        # Using a higher-level client method or raw AsyncClient
        klines = await client._client.get_historical_klines(symbol, interval, start, end)
        return [
            Candle(
                symbol=symbol,
                timestamp=datetime.fromtimestamp(k[0] / 1000),
                open=Decimal(str(k[1])),
                high=Decimal(str(k[2])),
                low=Decimal(str(k[3])),
                close=Decimal(str(k[4])),
                volume=Decimal(str(k[5]))
            ) for k in klines
        ]

    def run(self, candles: List[Candle], initial_balance: Decimal = Decimal("10000")) -> Dict[str, Any]:
        balance = initial_balance
        equity = balance
        active_pos: Optional[OpenPosition] = None
        closed_trades: List[ClosedTrade] = []
        
        # Buffer for indicators
        history: List[Candle] = []
        
        for i in range(100, len(candles) - 1):
            current = candles[i]
            next_c = candles[i+1]
            history.append(current)
            
            regime = self.regime_engine.update(history[-100:])
            self.router.update_regime(regime)
            
            if active_pos:
                # Monitor SL/TP
                low, high = current.low, current.high
                triggered = False
                exit_price = Decimal('0')
                reason = ""
                
                if active_pos.side == TradingSide.BUY:
                    if low <= active_pos.stop_loss:
                        exit_price = active_pos.stop_loss
                        triggered, reason = True, "SL"
                    elif high >= active_pos.take_profit:
                        exit_price = active_pos.take_profit
                        triggered, reason = True, "TP"
                else:
                    if high >= active_pos.stop_loss:
                        exit_price = active_pos.stop_loss
                        triggered, reason = True, "SL"
                    elif low <= active_pos.take_profit:
                        exit_price = active_pos.take_profit
                        triggered, reason = True, "TP"
                        
                if triggered:
                    # Apply slippage to exit
                    exit_price = exit_price * (1 - self.slippage) if active_pos.side == TradingSide.BUY else exit_price * (1 + self.slippage)
                    pnl = (exit_price - active_pos.entry_price) * active_pos.quantity if active_pos.side == TradingSide.BUY else (active_pos.entry_price - exit_price) * active_pos.quantity
                    fee_val = exit_price * active_pos.quantity * self.fee
                    pnl -= fee_val
                    balance += active_pos.quantity * active_pos.entry_price + pnl
                    
                    closed_trades.append(ClosedTrade(
                        id=active_pos.id, symbol=active_pos.symbol, side=active_pos.side,
                        entry_price=active_pos.entry_price, exit_price=exit_price,
                        quantity=active_pos.quantity, pnl=pnl,
                        pnl_percent=(pnl / (active_pos.entry_price * active_pos.quantity)) * 100,
                        opened_at=active_pos.opened_at
                    ))
                    active_pos = None
                    continue

            # Entry Logic
            if not active_pos and not self.router.is_trading_paused():
                strategy = self.router.get_active_strategy()
                signal = asyncio.run(strategy.generate_signal(history[-100:], [], {}, regime, None))
                
                if signal:
                    # Risk validation (mocked for backtest)
                    decision = asyncio.run(self.risk_engine.validate_trade(signal, balance, Decimal('0'))) # Simplified daily pnl
                    if decision.status == RiskStatus.APPROVED:
                        # Simulate fill at NEXT candle open
                        fill_price = next_c.open * (1 + self.slippage if signal.side == TradingSide.BUY else 1 - self.slippage)
                        qty = decision.max_quantity
                        cost = qty * fill_price
                        fee_val = cost * self.fee
                        
                        if balance >= cost + fee_val:
                            balance -= (cost + fee_val)
                            active_pos = OpenPosition(
                                id=f"BT_{i}", symbol=current.symbol, side=signal.side,
                                entry_price=fill_price, quantity=qty,
                                stop_loss=decision.adjusted_sl,
                                take_profit=decision.adjusted_tp,
                                entry_atr=Decimal(str(signal.indicators.get("atr", 0)))
                            )

        return {"trades": closed_trades, "final_balance": balance}
