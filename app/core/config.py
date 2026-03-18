from decimal import Decimal
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    BINANCE_API_KEY: SecretStr
    BINANCE_SECRET_KEY: SecretStr
    BINANCE_TESTNET: bool = True
    BINANCE_SPOT: bool = True 
    
    TELEGRAM_BOT_TOKEN: Optional[SecretStr] = None
    TELEGRAM_CHAT_ID: Optional[str] = None

    DATABASE_URL: str
    REDIS_URL: str

    TRADING_SYMBOL: str = "BTCUSDT"
    DEFAULT_TIMEFRAME: str = "1m"
    SECONDARY_TIMEFRAME: str = "5m"
    COOLDOWN_MINUTES: int = 60
    
    RISK_PER_TRADE_PCT: Decimal = Field(Decimal('0.01'), ge=Decimal('0.001'), le=Decimal('0.1'))
    MAX_DAILY_LOSS_PCT: Decimal = Field(Decimal('0.05'), ge=Decimal('0.01'), le=Decimal('0.2'))
    MAX_CONSECUTIVE_LOSSES: int = 3
    MAX_DRAWDOWN_PCT: Decimal = Field(Decimal('0.10'), ge=Decimal('0.01'), le=Decimal('0.5'))
    MAX_POSITION_SIZE_USD: Decimal = Field(Decimal('500'), ge=Decimal('10'))
    
    ATR_PERIOD: int = 14
    EMA_FAST: int = 20
    EMA_SLOW: int = 50
    RSI_PERIOD: int = 14
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9
    BB_PERIOD: int = 20
    BB_STD: float = 2.0
    ADX_PERIOD: int = 14
    
    REGIME_LOOKBACK: int = 20
    REGIME_CONFIRM_CANDLES: int = 3
    ATR_VOLATILITY_MULTIPLIER: float = 1.8
    
    SR_LOOKBACK: int = 20
    SR_BINS: int = 10
    
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

settings = Settings()
