# backend/tasks/trading_bot.py

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import traceback
from contextlib import asynccontextmanager

from services.trading_service import TradingService
from schemas.trading_schema import (
    MarketOrderRequest, TradingSymbol, TradingSide,
    TradingSignalResponse, MarketDataResponse
)
from utils.discord import send_discord_notification
from app.config import BINANCE_API_KEY, BINANCE_SECRET_KEY

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TradingBot:
    """
    Automated trading bot that monitors markets and executes trades based on strategies.
    
    Features:
    - Real-time market monitoring
    - Automated signal generation and trade execution
    - Risk management with stop-loss and take-profit
    - Multi-user support
    - Comprehensive logging and notifications
    - Error handling and recovery
    """
    
    def __init__(self):
        self.is_running = False
        self.user_services: Dict[str, TradingService] = {}
        self.active_users: Set[str] = set()
        self.last_signal_time: Dict[str, datetime] = {}
        self.last_price_check: Dict[str, datetime] = {}
        self.error_counts: Dict[str, int] = {}
        
        # Bot configuration
        self.monitoring_interval = 60  # seconds between market checks
        self.signal_cooldown = 300  # seconds between signals for same symbol
        self.max_errors_per_user = 5  # Max errors before pausing user
        self.price_update_interval = 10  # seconds between price updates
        
        # Trading state
        self.current_signals: Dict[str, Dict[str, TradingSignalResponse]] = {}
        self.last_trades: Dict[str, Dict[str, datetime]] = {}
        
    async def start(self):
        """Start the trading bot"""
        if self.is_running:
            logger.warning("Trading bot is already running")
            return
        
        self.is_running = True
        logger.info("Starting automated trading bot...")
        
        try:
            # Initialize active users
            await self._load_active_users()
            
            # Start main monitoring loop
            await self._main_loop()
            
        except Exception as e:
            logger.error(f"Error starting trading bot: {e}")
            self.is_running = False
            raise
    
    async def stop(self):
        """Stop the trading bot"""
        logger.info("Stopping automated trading bot...")
        self.is_running = False
        
        # Cleanup trading services
        for user_id, service in self.user_services.items():
            try:
                await service.stop_websocket_streams()
            except Exception as e:
                logger.error(f"Error stopping WebSocket for user {user_id}: {e}")
        
        self.user_services.clear()
        self.active_users.clear()
        
        logger.info("Trading bot stopped")
    
    async def _main_loop(self):
        """Main trading bot loop"""
        logger.info("Trading bot main loop started")
        
        while self.is_running:
            try:
                loop_start = datetime.utcnow()
                
                # Load active users (refresh every loop)
                await self._load_active_users()
                
                # Process each active user
                for user_id in self.active_users.copy():
                    try:
                        await self._process_user(user_id)
                    except Exception as e:
                        await self._handle_user_error(user_id, e)
                
                # Calculate sleep time to maintain interval
                loop_duration = (datetime.utcnow() - loop_start).total_seconds()
                sleep_time = max(0, self.monitoring_interval - loop_duration)
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    logger.warning(f"Trading loop took {loop_duration:.2f}s, longer than interval {self.monitoring_interval}s")
                    
            except Exception as e:
                logger.error(f"Error in main trading loop: {e}")
                logger.error(traceback.format_exc())
                await asyncio.sleep(30)  # Wait before retrying
    
    async def _load_active_users(self):
        """Load users with active trading enabled"""
        try:
            collection = get_collection('trading_profiles')
            
            # Find users with trading enabled
            profiles = await collection.find({
                'trading_enabled': True,
                'binance_api_key': {'$exists': True, '$ne': None},
                'binance_secret_key': {'$exists': True, '$ne': None}
            }).to_list(None)
            
            new_active_users = set()
            
            for profile in profiles:
                user_id = profile['user_id']
                new_active_users.add(user_id)
                
                # Initialize trading service for new users
                if user_id not in self.user_services:
                    try:
                        await self._initialize_user_service(user_id, profile)
                    except Exception as e:
                        logger.error(f"Failed to initialize trading service for user {user_id}: {e}")
                        continue
            
            # Remove inactive users
            inactive_users = self.active_users - new_active_users
            for user_id in inactive_users:
                await self._deactivate_user(user_id)
            
            self.active_users = new_active_users
            
            if self.active_users:
                logger.info(f"Monitoring {len(self.active_users)} active users: {list(self.active_users)}")
            
        except Exception as e:
            logger.error(f"Error loading active users: {e}")
    
    async def _initialize_user_service(self, user_id: str, profile: Dict):
        """Initialize trading service for a user"""
        try:
            # In production, decrypt API keys
            api_key = profile.get('binance_api_key', BINANCE_API_KEY)
            api_secret = profile.get('binance_secret_key', BINANCE_SECRET_KEY)
            
            service = TradingService(
                api_key=api_key,
                api_secret=api_secret,
                testnet=True  # Use testnet for safety
            )
            
            await service.initialize(user_id)
            
            self.user_services[user_id] = service
            self.error_counts[user_id] = 0
            self.current_signals[user_id] = {}
            self.last_trades[user_id] = {}
            
            logger.info(f"Initialized trading service for user {user_id}")
            
            # Send startup notification
            await send_discord_notification(
                message="🤖 Trading bot started monitoring your account",
                user_id=user_id,
                bot_status=True
            )
            
        except Exception as e:
            logger.error(f"Error initializing user service for {user_id}: {e}")
            raise
    
    async def _deactivate_user(self, user_id: str):
        """Deactivate trading for a user"""
        try:
            if user_id in self.user_services:
                await self.user_services[user_id].stop_websocket_streams()
                del self.user_services[user_id]
            
            self.active_users.discard(user_id)
            self.current_signals.pop(user_id, None)
            self.last_trades.pop(user_id, None)
            self.error_counts.pop(user_id, None)
            
            logger.info(f"Deactivated user {user_id}")
            
        except Exception as e:
            logger.error(f"Error deactivating user {user_id}: {e}")
    
    async def _process_user(self, user_id: str):
        """Process trading logic for a single user"""
        try:
            service = self.user_services.get(user_id)
            if not service:
                return
            
            # Check if user has exceeded error limit
            if self.error_counts.get(user_id, 0) >= self.max_errors_per_user:
                logger.warning(f"User {user_id} has too many errors, skipping")
                return
            
            # Get user's trading configuration
            trading_config = await self._get_user_trading_config(user_id)
            if not trading_config:
                return
            
            # Get symbols to monitor
            symbols_to_trade = trading_config.get('symbols_to_trade', ['BTCUSDT', 'ETHUSDT'])
            
            # Process each symbol
            for symbol in symbols_to_trade:
                try:
                    await self._process_symbol(user_id, symbol, service, trading_config)
                except Exception as e:
                    logger.error(f"Error processing symbol {symbol} for user {user_id}: {e}")
            
            # Check stop-loss and take-profit
            await service.check_stop_loss_take_profit(user_id)
            
        except Exception as e:
            logger.error(f"Error processing user {user_id}: {e}")
            raise
    
    async def _process_symbol(self, user_id: str, symbol: str, service: TradingService, config: Dict):
        """Process trading logic for a specific symbol"""
        try:
            # Check if we should generate a new signal
            should_check_signal = await self._should_check_signal(user_id, symbol)
            
            if should_check_signal:
                # Generate trading signal
                signal = await service.generate_trading_signal(symbol)
                self.current_signals[user_id][symbol] = signal
                self.last_signal_time[f"{user_id}_{symbol}"] = datetime.utcnow()
                
                # Log signal
                logger.info(f"Signal for {user_id}/{symbol}: {signal.signal} (confidence: {signal.confidence:.2f})")
                
                # Execute trade if signal is strong enough
                if signal.confidence >= config.get('min_signal_confidence', 0.7):
                    await self._execute_signal(user_id, symbol, signal, service, config)
            
            # Update price cache (more frequent than signals)
            await self._update_price_cache(user_id, symbol, service)
            
        except Exception as e:
            logger.error(f"Error processing symbol {symbol} for user {user_id}: {e}")
            raise
    
    async def _should_check_signal(self, user_id: str, symbol: str) -> bool:
        """Determine if we should check for new signals"""
        signal_key = f"{user_id}_{symbol}"
        
        # Check if enough time has passed since last signal
        if signal_key in self.last_signal_time:
            time_since_signal = (datetime.utcnow() - self.last_signal_time[signal_key]).total_seconds()
            if time_since_signal < self.signal_cooldown:
                return False
        
        return True
    
    async def _execute_signal(self, user_id: str, symbol: str, signal: TradingSignalResponse, 
                            service: TradingService, config: Dict):
        """Execute a trading signal"""
        try:
            if signal.signal == "HOLD":
                return
            
            # Check if we've traded this symbol recently
            trade_key = f"{user_id}_{symbol}"
            if trade_key in self.last_trades:
                time_since_trade = (datetime.utcnow() - self.last_trades[trade_key]).total_seconds()
                min_trade_interval = config.get('min_trade_interval', 300)  # 5 minutes default
                
                if time_since_trade < min_trade_interval:
                    logger.info(f"Skipping trade for {symbol} - too soon since last trade")
                    return
            
            # Calculate position size
            risk_percentage = config.get('max_position_size_percentage', 10.0)
            position_size = await service.calculate_position_size(symbol, signal.signal, risk_percentage)
            
            if position_size <= 0:
                logger.warning(f"Invalid position size calculated for {symbol}: {position_size}")
                return
            
            # Validate minimum trade amount
            min_trade_amount = config.get('min_trade_amount', 10.0)
            estimated_value = position_size * signal.price
            
            if estimated_value < min_trade_amount:
                logger.info(f"Trade value ${estimated_value:.2f} below minimum ${min_trade_amount}")
                return
            
            # Create and execute order
            side = TradingSide.BUY if signal.signal == "BUY" else TradingSide.SELL
            
            order_request = MarketOrderRequest(
                symbol=TradingSymbol(symbol),
                side=side,
                quantity=position_size
            )
            
            # Execute the trade
            result = await service.place_market_order(user_id, order_request)
            
            # Record trade time
            self.last_trades[trade_key] = datetime.utcnow()
            
            # Send notification
            await self._send_trade_notification(user_id, symbol, signal, result)
            
            logger.info(f"Executed {signal.signal} order for {user_id}/{symbol}: {position_size} @ ${signal.price}")
            
        except Exception as e:
            logger.error(f"Error executing signal for {user_id}/{symbol}: {e}")
            await self._send_error_notification(user_id, f"Failed to execute {signal.signal} order for {symbol}: {str(e)}")
            raise
    
    async def _update_price_cache(self, user_id: str, symbol: str, service: TradingService):
        """Update price cache for faster access"""
        try:
            price_key = f"{user_id}_{symbol}"
            
            # Check if we need to update price
            if price_key in self.last_price_check:
                time_since_update = (datetime.utcnow() - self.last_price_check[price_key]).total_seconds()
                if time_since_update < self.price_update_interval:
                    return
            
            # Get current price (this updates the service's price cache)
            await service.get_current_price(symbol)
            self.last_price_check[price_key] = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error updating price cache for {symbol}: {e}")
    
    async def _get_user_trading_config(self, user_id: str) -> Optional[Dict]:
        """Get user's trading configuration"""
        try:
            collection = get_collection('trading_profiles')
            config = await collection.find_one({'user_id': user_id})
            return config
        except Exception as e:
            logger.error(f"Error getting trading config for user {user_id}: {e}")
            return None
    
    async def _handle_user_error(self, user_id: str, error: Exception):
        """Handle errors for a specific user"""
        try:
            self.error_counts[user_id] = self.error_counts.get(user_id, 0) + 1
            error_count = self.error_counts[user_id]
            
            logger.error(f"Error for user {user_id} (count: {error_count}): {error}")
            
            # Send error notification
            await self._send_error_notification(
                user_id, 
                f"Trading bot error (#{error_count}): {str(error)}"
            )
            
            # Pause user if too many errors
            if error_count >= self.max_errors_per_user:
                await self._pause_user_trading(user_id)
                
        except Exception as e:
            logger.error(f"Error handling user error for {user_id}: {e}")
    
    async def _pause_user_trading(self, user_id: str):
        """Pause trading for a user due to errors"""
        try:
            # Update database
            collection = get_collection('trading_profiles')
            await collection.update_one(
                {'user_id': user_id},
                {
                    '$set': {
                        'trading_enabled': False,
                        'paused_due_to_errors': True,
                        'paused_at': datetime.utcnow()
                    }
                }
            )
            
            # Remove from active users
            await self._deactivate_user(user_id)
            
            # Send notification
            await send_discord_notification(
                message="⚠️ Trading bot paused due to multiple errors. Please check your configuration.",
                user_id=user_id,
                error=True
            )
            
            logger.warning(f"Paused trading for user {user_id} due to errors")
            
        except Exception as e:
            logger.error(f"Error pausing user trading for {user_id}: {e}")
    
    async def _send_trade_notification(self, user_id: str, symbol: str, 
                                     signal: TradingSignalResponse, result):
        """Send notification about executed trade"""
        try:
            # Format message
            action = "🟢 BUY" if signal.signal == "BUY" else "🔴 SELL"
            message = (
                f"{action} {symbol}\n"
                f"💰 Quantity: {result.quantity}\n"
                f"💵 Price: ${signal.price:.4f}\n"
                f"📈 Confidence: {signal.confidence:.1%}\n"
                f"🧠 Strategy: {signal.strategy}\n"
                f"💭 Reason: {signal.reasoning[:100]}..."
            )
            
            # Send Discord notification
            await send_discord_notification(
                message=message,
                user_id=user_id,
                trade_data={
                    'symbol': symbol,
                    'side': signal.signal,
                    'quantity': result.quantity,
                    'price': signal.price,
                    'confidence': signal.confidence
                }
            )
            
            # Send email notification for significant trades
            if result.quantity * signal.price > 100:  # Notify for trades > $100
                await send_email_notification(
                    subject=f"Trade Executed: {action} {symbol}",
                    message=message,
                    user_id=user_id
                )
                
        except Exception as e:
            logger.error(f"Error sending trade notification: {e}")
    
    async def _send_error_notification(self, user_id: str, error_message: str):
        """Send error notification"""
        try:
            await send_discord_notification(
                message=f"🚨 Trading Bot Error: {error_message}",
                user_id=user_id,
                error=True
            )
        except Exception as e:
            logger.error(f"Error sending error notification: {e}")
    
    # === Public Methods for Bot Management ===
    
    async def add_user(self, user_id: str):
        """Add a user to active monitoring"""
        try:
            collection = get_collection('trading_profiles')
            profile = await collection.find_one({'user_id': user_id})
            
            if profile and profile.get('trading_enabled', False):
                await self._initialize_user_service(user_id, profile)
                self.active_users.add(user_id)
                logger.info(f"Added user {user_id} to active monitoring")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error adding user {user_id}: {e}")
            return False
    
    async def remove_user(self, user_id: str):
        """Remove a user from active monitoring"""
        try:
            await self._deactivate_user(user_id)
            logger.info(f"Removed user {user_id} from active monitoring")
            return True
            
        except Exception as e:
            logger.error(f"Error removing user {user_id}: {e}")
            return False
    
    async def get_status(self) -> Dict:
        """Get bot status information"""
        return {
            'is_running': self.is_running,
            'active_users': list(self.active_users),
            'user_count': len(self.active_users),
            'monitoring_interval': self.monitoring_interval,
            'signal_cooldown': self.signal_cooldown,
            'error_counts': dict(self.error_counts),
            'last_signals': {
                user_id: {
                    symbol: signal.dict() for symbol, signal in signals.items()
                } for user_id, signals in self.current_signals.items()
            },
            'timestamp': datetime.utcnow()
        }
    
    async def force_signal_check(self, user_id: str, symbol: str) -> Optional[TradingSignalResponse]:
        """Force a signal check for a specific user and symbol"""
        try:
            service = self.user_services.get(user_id)
            if not service:
                return None
            
            signal = await service.generate_trading_signal(symbol)
            self.current_signals.setdefault(user_id, {})[symbol] = signal
            
            logger.info(f"Forced signal check for {user_id}/{symbol}: {signal.signal}")
            return signal
            
        except Exception as e:
            logger.error(f"Error in forced signal check for {user_id}/{symbol}: {e}")
            return None


# Global bot instance
trading_bot = TradingBot()


# === Bot Management Functions ===

async def start_trading_bot():
    """Start the trading bot"""
    try:
        await trading_bot.start()
    except Exception as e:
        logger.error(f"Failed to start trading bot: {e}")
        raise


async def stop_trading_bot():
    """Stop the trading bot"""
    try:
        await trading_bot.stop()
    except Exception as e:
        logger.error(f"Failed to stop trading bot: {e}")
        raise


async def get_bot_status():
    """Get trading bot status"""
    return await trading_bot.get_status()


async def add_user_to_bot(user_id: str):
    """Add user to bot monitoring"""
    return await trading_bot.add_user(user_id)


async def remove_user_from_bot(user_id: str):
    """Remove user from bot monitoring"""
    return await trading_bot.remove_user(user_id)


async def force_user_signal_check(user_id: str, symbol: str):
    """Force signal check for user"""
    return await trading_bot.force_signal_check(user_id, symbol)


# === Context Manager for Bot Lifecycle ===

@asynccontextmanager
async def trading_bot_context():
    """Context manager for trading bot lifecycle"""
    try:
        await start_trading_bot()
        yield trading_bot
    finally:
        await stop_trading_bot()


# === Background Task Runner ===

async def run_trading_bot_forever():
    """Run trading bot indefinitely with error recovery"""
    retry_count = 0
    max_retries = 5
    
    while retry_count < max_retries:
        try:
            logger.info(f"Starting trading bot (attempt {retry_count + 1}/{max_retries})")
            await start_trading_bot()
            break  # If we get here, bot stopped normally
            
        except KeyboardInterrupt:
            logger.info("Trading bot stopped by user")
            break
            
        except Exception as e:
            retry_count += 1
            logger.error(f"Trading bot crashed: {e}")
            logger.error(traceback.format_exc())
            
            if retry_count < max_retries:
                wait_time = min(300, 30 * retry_count)  # Max 5 minutes wait
                logger.info(f"Restarting in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                logger.error("Max retries reached. Trading bot will not restart.")
                break
    
    # Ensure cleanup
    try:
        await stop_trading_bot()
    except:
        pass


if __name__ == "__main__":
    """Run trading bot as standalone script"""
    try:
        asyncio.run(run_trading_bot_forever())
    except KeyboardInterrupt:
        logger.info("Trading bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error in trading bot: {e}")
        logger.error(traceback.format_exc())
