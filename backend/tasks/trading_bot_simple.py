# backend/tasks/trading_bot_simple.py

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable
import traceback
import json
import time

from services.trading_service import TradingService
from schemas.trading_schema import TradingSignalResponse
from utils.discord import send_discord_notification
from app.config import BINANCE_API_KEY, BINANCE_SECRET_KEY, BINANCE_TESTNET

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RealTimeTradingBot:
    """
    Real-Time Event-Driven BTC Trading Bot
    
    Features:
    - Real-time WebSocket price streaming with 2-second API fallback
    - Event-driven architecture for minimal latency
    - Automatic connection monitoring and recovery
    - Clean, efficient, and maintainable code
    """
    
    def __init__(self):
        self.is_running = False
        self.trading_service: Optional[TradingService] = None
        self.error_count = 0
        
        # Trading configuration
        self.symbol = "BTCUSDT"
        self.trading_amount = 100.0
        self.max_errors = 5
        
        # Real-time streaming
        self.use_websocket = True
        self.websocket_connected = False
        self.last_price_update = None
        self.current_price = 0.0
        self.api_fallback_interval = 2.0  # 2 seconds
        
        # Event-driven components
        self.price_update_callbacks = []
        self.monitoring_task = None
        self.fallback_task = None
        
        # TEST MODE - More aggressive trading for testing
        self.test_mode = True
        
        # Trading state
        self.current_position = None
        self.buy_price = 0.0
        self.btc_quantity = 0.0
        self.total_profit = 0.0
        self.trade_count = 0
        self.last_signal_time = None
        
        # Strategy parameters - More aggressive for faster trading
        if self.test_mode:
            self.min_profit_percent = 0.3  # Reduced from 0.5% for faster trades
            self.stop_loss_percent = 1.0   # Reduced from 1.5% for faster exits
            self.signal_cooldown = 10      # Reduced from 30s for immediate responses
        else:
            self.min_profit_percent = 0.5  # More aggressive than before
            self.stop_loss_percent = 1.5
            self.signal_cooldown = 20
            self.signal_cooldown = 60
        
        # Aggressive trading timers
        self.scanning_timeout = 5 * 60    # Force buy after 5 minutes scanning
        self.position_timeout = 3 * 60    # Force sell after 3 minutes in position
        self.scanning_start_time = None
        self.position_start_time = None
    
    def set_trading_amount(self, amount: float):
        """Set the amount of USDT to trade with"""
        self.trading_amount = amount
        logger.info(f"Trading amount set to ${amount} USDT")
    
    async def start(self):
        """Start the real-time trading bot"""
        if self.is_running:
            logger.warning("Trading bot is already running")
            return
        
        self.is_running = True
        logger.info(f"🚀 Starting Real-Time BTC Trading Bot with ${self.trading_amount} USDT")
        
        # Initialize scanning timer
        self.scanning_start_time = datetime.now()
        self.position_start_time = None
        
        try:
            await self._initialize_trading_service()
            await self._start_real_time_monitoring()
            
        except Exception as e:
            logger.error(f"Error starting trading bot: {e}")
            self.is_running = False
            raise
    
    async def stop(self):
        """Stop the trading bot and force sell any open positions"""
        logger.info("Stopping Real-Time BTC Trading Bot...")
        self.is_running = False
        
        # Force sell any open position before stopping
        final_summary = None
        if self.current_position == "BUY":
            logger.info("🔄 Force selling BTC position before stopping...")
            try:
                current_price = await self._update_price_from_api()
                if current_price and current_price > 0:
                    final_summary = await self._force_sell_position(current_price)
                else:
                    logger.warning("Could not get current price for force sell")
            except Exception as e:
                logger.error(f"Error during force sell: {e}")
        
        # Stop monitoring tasks
        if self.monitoring_task:
            self.monitoring_task.cancel()
        if self.fallback_task:
            self.fallback_task.cancel()
        
        # Stop trading service
        if self.trading_service:
            try:
                await self.trading_service.stop_websocket_streams()
            except Exception as e:
                logger.error(f"Error stopping WebSocket: {e}")
        
        # Log final summary
        if final_summary:
            logger.info(f"🏁 Final Trading Summary:")
            logger.info(f"   � Total Profit/Loss: ${final_summary['total_pnl']:.2f}")
            logger.info(f"   📊 Total Trades: {final_summary['total_trades']}")
            logger.info(f"   📈 Win Rate: {final_summary['win_rate']:.1f}%")
            logger.info(f"   💵 Final Balance: ${final_summary['final_value']:.2f}")
        
        logger.info("�🛑 Real-Time BTC Trading Bot stopped")
        return final_summary
    
    async def _initialize_trading_service(self):
        """Initialize the trading service with real-time capabilities"""
        try:
            self.trading_service = TradingService(
                api_key=BINANCE_API_KEY,
                api_secret=BINANCE_SECRET_KEY,
                testnet=BINANCE_TESTNET
            )
            
            # Initialize user (if needed by trading service)
            await self.trading_service.initialize("bot_user")
            
            logger.info("✅ Trading service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize trading service: {e}")
            raise
    
    
    async def _start_real_time_monitoring(self):
        """Start real-time price monitoring with WebSocket and API fallback"""
        logger.info("🔗 Initializing real-time price monitoring...")
        
        # Register price update callback
        self.price_update_callbacks.append(self._on_price_update)
        
        # Try to start WebSocket first
        try:
            await self._setup_websocket_monitoring()
            logger.info("� WebSocket monitoring active")
        except Exception as e:
            logger.warning(f"WebSocket failed, using API fallback: {e}")
            self.use_websocket = False
        
        # Always start API fallback as backup
        self.fallback_task = asyncio.create_task(self._api_fallback_monitor())
        
        # Start main monitoring task
        self.monitoring_task = asyncio.create_task(self._connection_monitor())
        
        # Get initial price
        await self._update_price_from_api()
    
    async def _setup_websocket_monitoring(self):
        """Setup WebSocket price monitoring"""
        try:
            # Start WebSocket streams in trading service
            await self.trading_service._start_websocket_streams()
            
            # Override the ticker handler to call our callback
            original_handler = self.trading_service._handle_ticker_data
            
            def enhanced_handler(msg):
                original_handler(msg)  # Keep original functionality
                self._handle_websocket_price(msg)
            
            self.trading_service._handle_ticker_data = enhanced_handler
            self.websocket_connected = True
            
        except Exception as e:
            logger.error(f"Failed to setup WebSocket: {e}")
            raise
    
    def _handle_websocket_price(self, msg):
        """Handle real-time price updates from WebSocket"""
        try:
            symbol = msg.get('s')
            if symbol == self.symbol:
                new_price = float(msg.get('c', 0))
                if new_price > 0:
                    self.current_price = new_price
                    self.last_price_update = time.time()
                    
                    # Trigger event-driven callbacks
                    asyncio.create_task(self._trigger_price_callbacks(new_price))
                    
        except Exception as e:
            logger.error(f"Error handling WebSocket price: {e}")
    
    async def _api_fallback_monitor(self):
        """API polling fallback when WebSocket is unavailable"""
        while self.is_running:
            try:
                # Only use API if WebSocket is down or too old
                current_time = time.time()
                websocket_stale = (
                    not self.websocket_connected or 
                    not self.last_price_update or 
                    (current_time - self.last_price_update) > 10  # 10 seconds stale
                )
                
                if websocket_stale:
                    await self._update_price_from_api()
                
                await asyncio.sleep(self.api_fallback_interval)
                
            except Exception as e:
                logger.error(f"API fallback error: {e}")
                await asyncio.sleep(5)
    
    async def _update_price_from_api(self):
        """Update price using API call and return the price"""
        try:
            price_data = await self.trading_service.get_price_data(self.symbol)
            new_price = price_data.price
            
            if new_price != self.current_price:
                self.current_price = new_price
                self.last_price_update = time.time()
                await self._trigger_price_callbacks(new_price)
            
            return new_price
                
        except Exception as e:
            logger.error(f"Error getting price from API: {e}")
            return None
    
    async def _force_sell_position(self, current_price: float):
        """Force sell current position when stopping bot"""
        try:
            if not self.current_position or self.current_position != "BUY":
                return None
            
            profit = (current_price - self.buy_price) * self.btc_quantity
            profit_percent = ((current_price - self.buy_price) / self.buy_price) * 100
            
            logger.info(f"🔴 FORCE SELLING {self.btc_quantity:.6f} BTC at ${current_price:.2f} (BOT STOP)")
            
            # Update totals
            self.total_profit += profit
            
            # Calculate final summary
            final_summary = {
                'total_pnl': self.total_profit,
                'final_trade_profit': profit,
                'final_trade_percent': profit_percent,
                'total_trades': self.trade_count,
                'win_rate': 100.0 if self.total_profit > 0 else 0.0,  # Simplified
                'final_value': self.trading_amount + self.total_profit,
                'buy_price': self.buy_price,
                'sell_price': current_price,
                'btc_quantity': self.btc_quantity
            }
            
            await self._send_trade_notification("SELL", current_price, self.btc_quantity, profit, profit_percent, is_force_sell=True)
            
            # Reset position
            self.current_position = None
            self.buy_price = 0.0
            self.btc_quantity = 0.0
            
            # Reset timers
            self.position_start_time = None
            self.scanning_start_time = None
            
            logger.info(f"✅ Force sold BTC - Final Profit: ${profit:.2f} ({profit_percent:.2f}%)")
            
            return final_summary
            
        except Exception as e:
            logger.error(f"Error executing force sell: {e}")
            return None
    
    async def _connection_monitor(self):
        """Monitor connection health and reconnect if needed"""
        while self.is_running:
            try:
                current_time = time.time()
                
                # Check if WebSocket is stale
                if (self.use_websocket and self.last_price_update and 
                    (current_time - self.last_price_update) > 30):
                    
                    logger.warning("🔄 WebSocket appears stale, reconnecting...")
                    await self._reconnect_websocket()
                
                await asyncio.sleep(15)  # Check every 15 seconds
                
            except Exception as e:
                logger.error(f"Connection monitor error: {e}")
                await asyncio.sleep(30)
    
    async def _reconnect_websocket(self):
        """Reconnect WebSocket connection"""
        try:
            self.websocket_connected = False
            await self.trading_service.stop_websocket_streams()
            await asyncio.sleep(2)
            await self._setup_websocket_monitoring()
            logger.info("✅ WebSocket reconnected successfully")
            
        except Exception as e:
            logger.error(f"Failed to reconnect WebSocket: {e}")
            self.use_websocket = False
    
    async def _trigger_price_callbacks(self, price: float):
        """Trigger all registered price update callbacks"""
        for callback in self.price_update_callbacks:
            try:
                await callback(price)
            except Exception as e:
                logger.error(f"Error in price callback: {e}")
    
    async def _on_price_update(self, price: float):
        """Handle real-time price updates (event-driven trading logic)"""
        try:
            logger.debug(f"💰 Real-time price update: ${price:.2f}")
            current_time = datetime.now()
            
            if self.current_position is None:
                # Initialize scanning start time if not set
                if self.scanning_start_time is None:
                    self.scanning_start_time = current_time
                
                # Check for force buy timeout (5 minutes scanning)
                scanning_duration = (current_time - self.scanning_start_time).total_seconds()
                if scanning_duration > self.scanning_timeout:
                    logger.info(f"⏰ Force buy after {scanning_duration/60:.1f} minutes scanning!")
                    await self._execute_buy_order(price)
                    self.scanning_start_time = None  # Reset
                    return
                
                # No position - check for BUY opportunity
                await self._check_buy_opportunity(price)
            else:
                # Initialize position start time if not set
                if self.position_start_time is None:
                    self.position_start_time = current_time
                
                # Check for force sell timeout (3 minutes in position)
                position_duration = (current_time - self.position_start_time).total_seconds()
                if position_duration > self.position_timeout:
                    logger.info(f"⏰ Force sell after {position_duration/60:.1f} minutes in position!")
                    await self._force_sell_position(price)
                    self.position_start_time = None  # Reset
                    return
                
                # Have position - check for SELL opportunity
                await self._check_sell_opportunity(price)
                
        except Exception as e:
            self.error_count += 1
            logger.error(f"Error processing price update: {e}")
            
            if self.error_count >= self.max_errors:
                logger.error("❌ Max errors reached, stopping bot")
                await self.stop()
    
    async def _check_buy_opportunity(self, current_price: float):
        """Check if it's a good time to buy BTC (event-driven)"""
        try:
            # Skip if we recently checked
            if self._should_skip_signal():
                return
            
            # Get trading signal
            signal = await self.trading_service.generate_trading_signal(self.symbol)
            
            # Log current market conditions for debugging
            logger.info(f"🔍 BTC Analysis - Price: ${current_price:.2f}")
            if signal:
                logger.info(f"📊 Signal: {signal.signal}, Confidence: {signal.confidence:.2f}")
                logger.info(f"💡 Reasoning: {signal.reasoning}")
                
                if signal.indicators:
                    rsi = signal.indicators.get('rsi', 'N/A')
                    ma_20 = signal.indicators.get('ma_20', 'N/A')
                    logger.info(f"📈 RSI: {rsi}, MA20: {ma_20}")
            
            if signal and signal.signal == "BUY" and signal.confidence > 0.4:  # Lowered from 0.6 for better price capture
                await self._execute_buy_order(current_price)
                self.last_signal_time = datetime.now()
            else:
                logger.debug(f"❌ No buy signal - Signal: {signal.signal if signal else 'None'}, Confidence: {signal.confidence if signal else 'N/A'}")
                
        except Exception as e:
            logger.error(f"Error checking buy opportunity: {e}")
    
    async def _check_sell_opportunity(self, current_price: float):
        """Check if it's time to sell BTC (event-driven)"""
        try:
            if not self.current_position:
                return
            
            profit_percent = ((current_price - self.buy_price) / self.buy_price) * 100
            
            logger.debug(f"🔍 Position Check - Current: ${current_price:.2f}, Buy: ${self.buy_price:.2f}, P&L: {profit_percent:.2f}%")
            
            # Check stop-loss
            if profit_percent <= -self.stop_loss_percent:
                logger.warning(f"🛑 Stop-loss triggered at {profit_percent:.2f}% loss")
                await self._execute_sell_order(current_price, "STOP_LOSS")
                return
            
            # Check profit target or get sell signal
            if profit_percent >= self.min_profit_percent:
                logger.info(f"💰 Profit target reached ({profit_percent:.2f}% >= {self.min_profit_percent}%), checking sell signal...")
                signal = await self.trading_service.generate_trading_signal(self.symbol)
                
                if signal:
                    logger.info(f"📊 Sell Signal: {signal.signal}, Confidence: {signal.confidence:.2f}")
                    
                if signal and ((signal.signal == "SELL" and signal.confidence > 0.4) or profit_percent >= 3.0):
                    await self._execute_sell_order(current_price, "PROFIT")
                else:
                    logger.debug(f"💎 Holding position - waiting for sell signal (conf: {signal.confidence:.2f}) or 3% profit")
            else:
                logger.debug(f"⏳ Holding position - need {self.min_profit_percent}% profit (currently {profit_percent:.2f}%)")
                    
        except Exception as e:
            logger.error(f"Error checking sell opportunity: {e}")
    
    
    async def _execute_buy_order(self, price: float):
        """Execute BTC buy order"""
        try:
            # Calculate BTC quantity to buy
            quantity = self.trading_amount / price
            
            logger.info(f"🟢 BUYING {quantity:.6f} BTC at ${price:.2f}")
            
            # Here you would place the actual order:
            # result = await self.trading_service.place_market_order(...)
            
            # For now, simulate the trade
            self.current_position = "BUY"
            self.buy_price = price
            self.btc_quantity = quantity
            self.trade_count += 1
            
            # Reset timers - starting position phase
            self.scanning_start_time = None
            self.position_start_time = datetime.now()
            
            await self._send_trade_notification("BUY", price, quantity)
            logger.info(f"✅ Successfully bought {quantity:.6f} BTC")
            
        except Exception as e:
            logger.error(f"Error executing buy order: {e}")
    
    async def _execute_sell_order(self, price: float, reason: str):
        """Execute BTC sell order"""
        try:
            profit = (price - self.buy_price) * self.btc_quantity
            profit_percent = ((price - self.buy_price) / self.buy_price) * 100
            
            logger.info(f"🔴 SELLING {self.btc_quantity:.6f} BTC at ${price:.2f} ({reason})")
            
            # Here you would place the actual sell order:
            # result = await self.trading_service.place_market_order(...)
            
            # Update totals
            self.total_profit += profit
            
            await self._send_trade_notification("SELL", price, self.btc_quantity, profit, profit_percent)
            
            # Reset position
            self.current_position = None
            self.buy_price = 0.0
            self.btc_quantity = 0.0
            
            # Reset timers - starting scanning phase
            self.position_start_time = None
            self.scanning_start_time = datetime.now()
            
            logger.info(f"✅ Sold BTC - Profit: ${profit:.2f} ({profit_percent:.2f}%)")
            
        except Exception as e:
            logger.error(f"Error executing sell order: {e}")
    
    def _should_skip_signal(self) -> bool:
        """Check if we should skip checking signals (cooldown)"""
        if self.last_signal_time:
            time_since_last = datetime.now() - self.last_signal_time
            return time_since_last.total_seconds() < self.signal_cooldown
        return False
    
    async def _send_trade_notification(self, action: str, price: float, quantity: float, 
                                     profit: float = None, profit_percent: float = None, is_force_sell: bool = False):
        """Send Discord notification about trade"""
        try:
            if action == "BUY":
                message = f"🟢 **BTC BUY EXECUTED** (Real-Time)\n" \
                         f"💰 Amount: {quantity:.6f} BTC\n" \
                         f"💵 Price: ${price:.2f}\n" \
                         f"📊 Total Investment: ${self.trading_amount:.2f}\n" \
                         f"⚡ Triggered by: {'WebSocket' if self.websocket_connected else 'API'}"
            else:
                emoji = "🟢" if profit > 0 else "🔴"
                sell_type = " (FORCE SELL - BOT STOPPED)" if is_force_sell else ""
                message = f"{emoji} **BTC SELL EXECUTED**{sell_type} (Real-Time)\n" \
                         f"💰 Amount: {quantity:.6f} BTC\n" \
                         f"💵 Price: ${price:.2f}\n" \
                         f"📈 Profit: ${profit:.2f} ({profit_percent:.2f}%)\n" \
                         f"💎 Total Profit: ${self.total_profit:.2f}\n" \
                         f"⚡ Triggered by: {'WebSocket' if self.websocket_connected else 'API'}"
            
            await send_discord_notification(message=message, user_id="bot")
            
        except Exception as e:
            logger.error(f"Error sending trade notification: {e}")
    
    async def get_status(self) -> Dict:
        """Get current bot status"""
        try:
            current_price = self.current_price if self.current_price > 0 else 0.0
        except:
            current_price = 0.0
        
        # Connection status
        connection_status = "WebSocket" if self.websocket_connected else "API Fallback"
        last_update_ago = time.time() - (self.last_price_update or 0) if self.last_price_update else 0
        
        # Calculate current session stats
        session_return = (self.total_profit / self.trading_amount * 100) if self.trading_amount > 0 else 0.0
            
        return {
            "is_running": self.is_running,
            "symbol": self.symbol,
            "trading_amount": self.trading_amount,
            "current_position": self.current_position,
            "current_price": current_price,
            "buy_price": self.buy_price,
            "btc_quantity": self.btc_quantity,
            "total_profit": self.total_profit,
            "session_return_percent": session_return,
            "trade_count": self.trade_count,
            "error_count": self.error_count,
            "unrealized_pnl": ((current_price - self.buy_price) * self.btc_quantity) if self.current_position else 0.0,
            "connection_type": connection_status,
            "last_price_update_seconds_ago": last_update_ago,
            "websocket_connected": self.websocket_connected,
            "test_mode": self.test_mode,
            "final_value": self.trading_amount + self.total_profit
        }


# Global trading bot instance (renamed to match new class)
trading_bot = RealTimeTradingBot()


async def start_trading_bot():
    """Start the global trading bot instance"""
    await trading_bot.start()


async def stop_trading_bot():
    """Stop the global trading bot instance"""
    await trading_bot.stop()