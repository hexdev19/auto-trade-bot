import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Server configuration
PORT = os.getenv("PORT", "8080")

# Binance configuration
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")
BINANCE_TESTNET = os.getenv("BINANCE_TESTNET", "True").lower() == "true"

# Discord configuration (optional)
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# BTC Trading configuration
DEFAULT_TRADING_AMOUNT = float(os.getenv("DEFAULT_TRADING_AMOUNT", "100.0"))
MIN_PROFIT_PERCENT = float(os.getenv("MIN_PROFIT_PERCENT", "1.0"))
STOP_LOSS_PERCENT = float(os.getenv("STOP_LOSS_PERCENT", "2.0"))
