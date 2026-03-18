from typing import Dict, Any
from app.models.domain import MarketRegime
from app.strategies.base import BaseStrategy
from app.strategies.trend import TrendStrategy
from app.strategies.scalping import ScalpingStrategy
from app.strategies.volatility_pause import VolatilityPauseStrategy

class StrategyRouter:
    def __init__(self):
        self._strategies: Dict[MarketRegime, BaseStrategy] = {
            MarketRegime.TRENDING: TrendStrategy(),
            MarketRegime.SIDEWAYS: ScalpingStrategy(),
            MarketRegime.HIGH_VOLATILITY: VolatilityPauseStrategy(),
            MarketRegime.UNKNOWN: VolatilityPauseStrategy()
        }
        self._current_regime = MarketRegime.UNKNOWN

    def update_regime(self, regime: MarketRegime) -> bool:
        changed = False
        if regime != self._current_regime:
            changed = True
            self._current_regime = regime
            
        return changed

    def get_active_strategy(self) -> BaseStrategy:
        return self._strategies.get(self._current_regime, self._strategies[MarketRegime.UNKNOWN])

    def is_trading_paused(self) -> bool:
        return self._current_regime in [MarketRegime.HIGH_VOLATILITY, MarketRegime.UNKNOWN]

    def get_strategy_for_regime(self, regime: MarketRegime) -> BaseStrategy:
        return self._strategies.get(regime, self._strategies[MarketRegime.UNKNOWN])
