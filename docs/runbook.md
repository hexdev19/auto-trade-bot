# Trading Bot Operational Runbook

## 1. First-time Setup
Ensure `.env` contains:
- `BINANCE_API_KEY` / `BINANCE_SECRET_KEY`
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`
- `DATABASE_URL` (PostgreSQL)
- `REDIS_URL`

**Binance Permissions:**
- Enable Spot Trading
- Disable Futures/Margin/Withdrawals
- Restrict to IP (if on VPS)

## 2. Testnet Validation
1. Set `BINANCE_TESTNET=True`
2. Run `alembic upgrade head`
3. Start bot via `docker-compose up`
4. Verify WebSocket connection (logs)
5. Verify Telegram Welcome message

## 3. Reading Telegram Alerts
- 🟢 **BUY OPENED:** New position entered.
- 🔴 **SELL CLOSED:** Position exited (SL/TP/Signal). Check PnL.
- 🔄 **REGIME CHANGE:** Market conditions shifted. Strategy router updated.
- ⚠️ **RISK ALERT:** Circuit breaker (daily loss/drawdown) triggered.

## 4. Manual Bot Control
- **Stop Trading:** `POST /api/v1/bot/stop`
- **Restart Trading:** `POST /api/v1/bot/start`
- **Check Status:** `GET /api/v1/health`

## 5. Emergency Halt Procedures
If `EMERGENCY_HALT` alert is received:
1. Verify all positions are closed via `/api/v1/trades/open`.
2. check logs: `docker-compose logs -f app`
3. Fix root cause (API disconnect, major slippage).
4. Reset bot via Docker restart.

## 6. Daily Monitoring Checklist
1. **Balance:** Verify USDT balance is stable.
2. **PnL:** Check daily PnL has not exceeded limits.
3. **Regime:** Ensure current regime aligns with market visuals.
4. **WebSocket:** Verify heartbeats in logs.
5. **Database:** Checks snapshots in `performance_snapshots` table.

## 7. Adding New Strategy
1. Create `app/strategies/new_strategy.py` (Inherit `BaseStrategy`).
2. Implement `generate_signal()`.
3. Register in `app/strategies/router.py`.
4. Run backtest: `python -m app.backtesting.run --strategy new`
