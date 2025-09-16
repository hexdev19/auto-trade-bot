# 🤖 Automated BTC Trading Bot

**Set your amount, start the bot, and let it trade Bitcoin automatically!**

## 🎯 What This Bot Does

1. **💰 You Set the Amount**: Specify how much USDT to trade with (e.g., $100)
2. **🧠 AI Trading**: Bot analyzes BTC market using technical indicators 
3. **📈 Auto Buy**: Finds optimal moments to buy BTC
4. **📉 Auto Sell**: Automatically sells for profit or cuts losses
5. **📊 Track Performance**: Monitor profits, trades, and bot status

## ✨ Key Features

- 🚀 **One-Click Trading**: Start with just your trading amount
- 🎯 **Smart Analysis**: RSI, MACD, Bollinger Bands technical analysis
- 🛡️ **Risk Management**: 2% stop-loss, 1% minimum profit
- 📱 **Web Dashboard**: Beautiful interface to control and monitor
- 🔔 **Discord Alerts**: Get notified of every trade
- 🧪 **Testnet Ready**: Practice with fake money first

## 🏗️ Project Structure

```
auto-trade-bot/
├── backend/          # API server and trading engine
│   ├── app/          # FastAPI application
│   ├── services/     # Trading logic
│   ├── tasks/        # Automated bot
│   └── utils/        # Helpers and notifications
├── frontend/         # Streamlit web dashboard
│   ├── app.py        # Main dashboard
│   └── run_frontend.py
└── README.md
```

## 🚀 Quick Start

### 1. Backend Setup (Trading Engine)

```bash
# Navigate to backend
cd backend

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Binance API keys

# Start the trading engine
python run_server.py
```

**Backend will run on: http://localhost:8080**

### 2. Frontend Setup (Web Dashboard)

```bash
# Navigate to frontend (new terminal)
cd frontend

# Install dependencies
pip install -r requirements.txt

# Start the dashboard
python run_frontend.py
```

**Dashboard will open at: http://localhost:8501**

### 3. Start Trading

1. Open the dashboard at http://localhost:8501
2. Set your trading amount (e.g., 100 USDT)
3. Click "🚀 Start Bot"
4. Monitor your bot's performance in real-time!

## 📊 Dashboard Features

### 🎛️ Controls
- **Trading Amount**: Set how much USDT to trade with
- **Start/Stop Bot**: One-click bot control
- **System Health**: API connection status

### 📈 Monitoring
- **Real-time Status**: Bot running/stopped
- **Current Position**: Holding BTC or USDT
- **Profit/Loss**: Live P&L calculation
- **Trade Count**: Number of completed trades
- **Performance Charts**: Visual profit tracking

### 📱 Auto-refresh
- Updates every 30 seconds when bot is running
- Manual refresh button available
- Real-time connection monitoring

## ⚙️ Configuration

### Environment Variables (.env)
```bash
# Binance API (get from binance.com or testnet.binance.vision)
BINANCE_API_KEY=your_api_key
BINANCE_SECRET_KEY=your_secret_key
BINANCE_TESTNET=true  # Use testnet for practice

# Server
PORT=8080

# Optional: Discord notifications
DISCORD_WEBHOOK_URL=your_discord_webhook_url
```

### Trading Parameters
- **Symbol**: BTCUSDT (Bitcoin/USDT)
- **Check Interval**: 30 seconds
- **Minimum Profit**: 1%
- **Stop Loss**: 2%
- **Signal Cooldown**: 5 minutes

## 🔒 Security & Safety

### ⚠️ Important Notes
- **Start with Testnet**: Use fake money to test first
- **Small Amounts**: Begin with small trading amounts
- **Monitor Closely**: Always supervise automated trading
- **Understand Risks**: Crypto trading involves significant risk

### 🛡️ Built-in Safety
- **Testnet Support**: Practice mode with fake funds
- **Stop Loss**: Automatic 2% loss protection
- **Error Handling**: Bot stops if too many errors occur
- **Position Tracking**: Always knows current state

## 📖 How It Works

### 1. Market Analysis
- Fetches real-time BTC price data from Binance
- Calculates technical indicators (RSI, MACD, Bollinger Bands)
- Determines market trend and momentum

### 2. Buy Decision
- **RSI Oversold**: RSI < 30 (potential bounce)
- **MACD Bullish**: MACD line crosses above signal
- **Bollinger Touch**: Price touches lower Bollinger Band
- **Volume Confirmation**: Above-average trading volume

### 3. Sell Decision
- **Profit Target**: Price rises 1%+ from buy price
- **Stop Loss**: Price falls 2% from buy price
- **Technical Reversal**: RSI overbought (RSI > 70)
- **MACD Bearish**: MACD line crosses below signal

### 4. Risk Management
- **Position Sizing**: Uses specified USDT amount
- **One Position**: Only one BTC position at a time
- **Loss Limits**: Stops trading after consecutive losses
- **Error Handling**: Graceful handling of API issues

## 🚨 Troubleshooting

### Backend Issues
```bash
# Check if backend is running
curl http://localhost:8080/api/v1/system/health

# View logs
python run_server.py
# Check terminal for error messages
```

### Frontend Issues
```bash
# If dashboard won't load
streamlit run app.py --server.port 8501

# Check Streamlit installation
pip install streamlit==1.28.1
```

### Common Problems
1. **API Connection Failed**: Check Binance API keys
2. **Bot Won't Start**: Verify sufficient testnet balance
3. **No Trades**: Market may be in consolidation
4. **Dashboard Error**: Ensure backend is running first

## 📈 Performance Tips

### Optimal Conditions
- **Volatile Markets**: Bot performs best in trending markets
- **Sufficient Balance**: Ensure enough USDT for trading
- **Stable Connection**: Reliable internet for API calls
- **Regular Monitoring**: Check dashboard periodically

### Avoiding Issues
- **Don't Overtrade**: Larger amounts need more careful monitoring
- **Market Hours**: Consider high-volume trading periods
- **News Events**: Be aware of major Bitcoin news
- **Technical Issues**: Monitor for API rate limits

## 🔮 Future Enhancements

- 📊 **Multiple Pairs**: Trade ETH, other cryptocurrencies
- 📱 **Mobile App**: Native mobile interface
- 🔔 **SMS Alerts**: Text message notifications
- 📈 **Advanced Charts**: TradingView-style interface
- 🤖 **ML Models**: Machine learning price prediction
- 💼 **Portfolio Mode**: Multiple trading strategies

## 📄 License

MIT License - Use at your own risk. Cryptocurrency trading involves substantial risk of loss.

## 🆘 Support

1. **Check Logs**: Backend terminal shows detailed error messages
2. **Test API**: Visit http://localhost:8080/docs for API testing
3. **Health Check**: http://localhost:8080/api/v1/system/health
4. **Discord**: Join the community for support (link in Discord webhook setup)

---

**⚠️ Disclaimer**: This software is for educational purposes. Cryptocurrency trading involves significant financial risk. Always test with small amounts and understand the risks before trading with real money.