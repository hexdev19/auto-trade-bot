# backend/services/trading_service.py

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal, ROUND_DOWN
import statistics
from binance import Client, ThreadedWebsocketManager  
from binance.exceptions import BinanceAPIException, BinanceOrderException
import numpy as np
import pandas as pd

from schemas.trading_schema import (
    MarketOrderRequest, LimitOrderRequest, TradingConfigRequest,
    StrategyConfigRequest, PriceData, BalanceInfo, AccountBalanceResponse,
    OrderResponse, TradeResponse, TradingStatsResponse, MarketDataResponse,
    TradingSignalResponse, TradingErrorResponse, CandlestickData,
    TradingSide, OrderType, OrderStatus, TradingSymbol
)
from utils.helpers import generate_client_order_id
from utils.discord import send_discord_notification

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradingService:
    """
    Production-ready trading service with Binance integration.
    Handles market data, order execution, risk management, and trading strategies.
    """
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        """Initialize trading service with Binance client"""
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        # Initialize Binance client
        self.client = Client(
            api_key,
            api_secret,
            testnet=testnet
        )
        
        # Cache for market data and indicators
        self.price_cache: Dict[str, List[float]] = {}
        self.volume_cache: Dict[str, List[float]] = {}
        self.indicator_cache: Dict[str, Dict[str, float]] = {}
        
        # Risk management settings
        self.max_position_size = 0.10  # 10% of portfolio
        self.stop_loss_percentage = 0.05  # 5%
        self.take_profit_percentage = 0.10  # 10%
        
        # Trading configuration
        self.trading_config = None
        self.strategy_config = None
        self.is_trading_enabled = False
        
        # WebSocket manager for real-time data
        self.twm = None
        self.active_streams = []
        
    async def initialize(self, user_id: str):
        """Initialize trading service for a specific user"""
        try:
            # For simplified bot, we don't need database profiles
            # Just use default configuration
            self.is_trading_enabled = True
            
            # Initialize price cache for supported symbols
            for symbol in TradingSymbol:
                self.price_cache[symbol.value] = []
                self.volume_cache[symbol.value] = []
                self.indicator_cache[symbol.value] = {}
            
            logger.info(f"Trading service initialized for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize trading service: {e}")
            return False
    
    # === Market Data Methods ===
    
    async def get_current_price(self, symbol: str) -> float:
        """Get current market price for a symbol"""
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            price = float(ticker['price'])
            
            # Update price cache
            if symbol in self.price_cache:
                self.price_cache[symbol].append(price)
                # Keep only last 200 prices for moving averages
                if len(self.price_cache[symbol]) > 200:
                    self.price_cache[symbol] = self.price_cache[symbol][-200:]
            
            return price
            
        except BinanceAPIException as e:
            logger.error(f"Binance API error getting price for {symbol}: {e}")
            raise TradingErrorResponse(
                error="BINANCE_API_ERROR",
                message=f"Failed to get price for {symbol}",
                symbol=symbol,
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            logger.error(f"Unexpected error getting price for {symbol}: {e}")
            raise TradingErrorResponse(
                error="PRICE_FETCH_ERROR",
                message=f"Failed to get price for {symbol}",
                symbol=symbol,
                timestamp=datetime.utcnow()
            )
    
    async def get_price_data(self, symbol: str) -> PriceData:
        """Get comprehensive price data for a symbol"""
        try:
            ticker = self.client.get_ticker(symbol=symbol)
            
            return PriceData(
                symbol=symbol,
                price=float(ticker['lastPrice']),
                price_change_24h=float(ticker['priceChange']),
                price_change_percent_24h=float(ticker['priceChangePercent']),
                high_24h=float(ticker['highPrice']),
                low_24h=float(ticker['lowPrice']),
                volume_24h=float(ticker['volume']),
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error getting price data for {symbol}: {e}")
            raise
    
    async def get_historical_data(self, symbol: str, interval: str = "1m", limit: int = 100) -> List[CandlestickData]:
        """Get historical candlestick data"""
        try:
            klines = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
            
            candlesticks = []
            for kline in klines:
                candlestick = CandlestickData(
                    symbol=symbol,
                    open_time=datetime.fromtimestamp(kline[0] / 1000),
                    close_time=datetime.fromtimestamp(kline[6] / 1000),
                    open_price=float(kline[1]),
                    high_price=float(kline[2]),
                    low_price=float(kline[3]),
                    close_price=float(kline[4]),
                    volume=float(kline[5]),
                    quote_asset_volume=float(kline[7]),
                    number_of_trades=int(kline[8])
                )
                candlesticks.append(candlestick)
            
            return candlesticks
            
        except Exception as e:
            logger.error(f"Error getting historical data for {symbol}: {e}")
            raise
    
    # === Account & Balance Methods ===
    
    async def get_account_balance(self) -> AccountBalanceResponse:
        """Get account balance information"""
        try:
            account = self.client.get_account()
            balances = []
            total_usdt_value = 0.0
            
            for balance in account['balances']:
                free = float(balance['free'])
                locked = float(balance['locked'])
                total = free + locked
                
                if total > 0:  # Only include non-zero balances
                    balance_info = BalanceInfo(
                        asset=balance['asset'],
                        free=free,
                        locked=locked,
                        total=total
                    )
                    balances.append(balance_info)
                    
                    # Calculate USDT value
                    if balance['asset'] == 'USDT':
                        total_usdt_value += total
                    elif total > 0:
                        try:
                            symbol = f"{balance['asset']}USDT"
                            price = await self.get_current_price(symbol)
                            total_usdt_value += total * price
                        except:
                            pass  # Skip if can't get price
            
            return AccountBalanceResponse(
                balances=balances,
                total_usdt_value=total_usdt_value,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            raise
    
    async def get_usdt_balance(self) -> float:
        """Get available USDT balance"""
        try:
            account = self.client.get_account()
            for balance in account['balances']:
                if balance['asset'] == 'USDT':
                    return float(balance['free'])
            return 0.0
            
        except Exception as e:
            logger.error(f"Error getting USDT balance: {e}")
            return 0.0
    
    # === Order Management Methods ===
    
    async def place_market_order(self, user_id: str, order_request: MarketOrderRequest) -> OrderResponse:
        """Place a market order"""
        try:
            # Validate balance before placing order
            if order_request.side == TradingSide.BUY:
                await self._validate_buy_order(order_request)
            else:
                await self._validate_sell_order(order_request)
            
            # Generate client order ID
            client_order_id = generate_client_order_id(user_id)
            
            # Prepare order parameters
            order_params = {
                'symbol': order_request.symbol.value,
                'side': order_request.side.value,
                'type': Client.ORDER_TYPE_MARKET,
                'newClientOrderId': client_order_id
            }
            
            if order_request.quantity:
                order_params['quantity'] = self._format_quantity(order_request.quantity, order_request.symbol.value)
            elif order_request.quote_order_qty:
                order_params['quoteOrderQty'] = self._format_quote_quantity(order_request.quote_order_qty)
            
            # Place order
            result = self.client.create_order(**order_params)
            
            # Store order in database
            order_data = {
                'user_id': user_id,
                'symbol': order_request.symbol.value,
                'side': order_request.side.value,
                'type': OrderType.MARKET.value,
                'quantity': float(result.get('executedQty', 0)),
                'status': result['status'],
                'binance_order_id': str(result['orderId']),
                'client_order_id': client_order_id,
                'created_at': datetime.utcnow()
            }
            
            await self._save_order(order_data)
            
            # Send notification
            await self._send_trade_notification(user_id, order_data, result)
            
            return OrderResponse(
                order_id=str(result['orderId']),
                client_order_id=client_order_id,
                symbol=order_request.symbol.value,
                side=order_request.side.value,
                type=OrderType.MARKET.value,
                quantity=float(result.get('executedQty', 0)),
                status=result['status'],
                created_at=datetime.utcnow(),
                executed_quantity=float(result.get('executedQty', 0)),
                cumulative_quote_qty=float(result.get('cummulativeQuoteQty', 0))
            )
            
        except BinanceAPIException as e:
            logger.error(f"Binance API error placing market order: {e}")
            await self._send_error_notification(user_id, f"Failed to place market order: {e}")
            raise TradingErrorResponse(
                error="ORDER_FAILED",
                error_code=str(e.code),
                message=str(e),
                symbol=order_request.symbol.value,
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            logger.error(f"Unexpected error placing market order: {e}")
            raise
    
    async def place_limit_order(self, user_id: str, order_request: LimitOrderRequest) -> OrderResponse:
        """Place a limit order"""
        try:
            # Validate balance
            if order_request.side == TradingSide.BUY:
                required_balance = order_request.quantity * order_request.price
                usdt_balance = await self.get_usdt_balance()
                if usdt_balance < required_balance:
                    raise TradingErrorResponse(
                        error="INSUFFICIENT_BALANCE",
                        message=f"Insufficient USDT balance. Required: {required_balance}, Available: {usdt_balance}",
                        balance_required=required_balance,
                        balance_available=usdt_balance,
                        timestamp=datetime.utcnow()
                    )
            
            client_order_id = generate_client_order_id(user_id)
            
            result = self.client.create_order(
                symbol=order_request.symbol.value,
                side=order_request.side.value,
                type=Client.ORDER_TYPE_LIMIT,
                timeInForce=order_request.time_in_force,
                quantity=self._format_quantity(order_request.quantity, order_request.symbol.value),
                price=self._format_price(order_request.price, order_request.symbol.value),
                newClientOrderId=client_order_id
            )
            
            # Store order in database
            order_data = {
                'user_id': user_id,
                'symbol': order_request.symbol.value,
                'side': order_request.side.value,
                'type': OrderType.LIMIT.value,
                'quantity': order_request.quantity,
                'price': order_request.price,
                'status': result['status'],
                'binance_order_id': str(result['orderId']),
                'client_order_id': client_order_id,
                'created_at': datetime.utcnow()
            }
            
            await self._save_order(order_data)
            
            return OrderResponse(
                order_id=str(result['orderId']),
                client_order_id=client_order_id,
                symbol=order_request.symbol.value,
                side=order_request.side.value,
                type=OrderType.LIMIT.value,
                quantity=order_request.quantity,
                price=order_request.price,
                status=result['status'],
                time_in_force=order_request.time_in_force,
                created_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error placing limit order: {e}")
            raise
    
    async def cancel_order(self, user_id: str, symbol: str, order_id: str) -> bool:
        """Cancel an open order"""
        try:
            result = self.client.cancel_order(symbol=symbol, orderId=order_id)
            
            # Update order status in database
            await self._update_order_status(order_id, OrderStatus.CANCELED.value)
            
            return True
            
        except Exception as e:
            logger.error(f"Error canceling order {order_id}: {e}")
            return False
    
    async def get_open_orders(self, user_id: str, symbol: Optional[str] = None) -> List[OrderResponse]:
        """Get open orders for user"""
        try:
            orders = self.client.get_open_orders(symbol=symbol)
            order_responses = []
            
            for order in orders:
                order_response = OrderResponse(
                    order_id=str(order['orderId']),
                    client_order_id=order['clientOrderId'],
                    symbol=order['symbol'],
                    side=order['side'],
                    type=order['type'],
                    quantity=float(order['origQty']),
                    price=float(order['price']) if order['price'] != '0.00000000' else None,
                    stop_price=float(order['stopPrice']) if order['stopPrice'] != '0.00000000' else None,
                    status=order['status'],
                    time_in_force=order['timeInForce'],
                    created_at=datetime.fromtimestamp(order['time'] / 1000),
                    executed_quantity=float(order['executedQty']),
                    cumulative_quote_qty=float(order['cummulativeQuoteQty'])
                )
                order_responses.append(order_response)
            
            return order_responses
            
        except Exception as e:
            logger.error(f"Error getting open orders: {e}")
            return []
    
    # === Trading Strategy Methods ===
    
    async def analyze_market(self, symbol: str) -> MarketDataResponse:
        """Analyze market data and calculate technical indicators"""
        try:
            # Get current price
            current_price = await self.get_current_price(symbol)
            
            # Get historical data for indicator calculations
            historical_data = await self.get_historical_data(symbol, "1m", 100)
            
            if len(historical_data) < 20:
                return MarketDataResponse(
                    symbol=symbol,
                    current_price=current_price,
                    volume_24h=0.0,
                    last_updated=datetime.utcnow()
                )
            
            # Calculate technical indicators
            prices = [candle.close_price for candle in historical_data]
            volumes = [candle.volume for candle in historical_data]
            
            # Moving averages
            ma_20 = self._calculate_moving_average(prices, 20)
            ma_50 = self._calculate_moving_average(prices, 50) if len(prices) >= 50 else None
            
            # RSI
            rsi = self._calculate_rsi(prices, 14)
            
            # Bollinger Bands
            bb_upper, bb_lower = self._calculate_bollinger_bands(prices, 20, 2)
            
            # Volume analysis
            volume_avg = statistics.mean(volumes) if volumes else 0
            
            # Trend direction
            trend = self._determine_trend(prices, ma_20, ma_50)
            
            # Signal strength
            signal_strength = self._calculate_signal_strength(current_price, ma_20, rsi, bb_upper, bb_lower)
            
            return MarketDataResponse(
                symbol=symbol,
                current_price=current_price,
                moving_average_20=ma_20,
                moving_average_50=ma_50,
                rsi=rsi,
                bollinger_upper=bb_upper,
                bollinger_lower=bb_lower,
                volume_24h=sum(volumes),
                volume_average=volume_avg,
                trend_direction=trend,
                signal_strength=signal_strength,
                last_updated=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error analyzing market for {symbol}: {e}")
            raise
    
    async def generate_trading_signal(self, symbol: str) -> TradingSignalResponse:
        """Generate trading signal based on simplified responsive analysis"""
        try:
            market_data = await self.analyze_market(symbol)
            
            # Get recent price data for quick analysis
            historical_data = await self.get_klines(symbol, "5m", 20)  # Just 20 5-minute candles
            prices = [float(candle.close_price) for candle in historical_data]
            
            if len(prices) < 14:
                return TradingSignalResponse(
                    symbol=symbol,
                    signal="HOLD",
                    confidence=0.0,
                    reasoning="Insufficient price data"
                )
            
            current_price = prices[-1]
            
            # Simple but effective indicators
            rsi = self._calculate_rsi(prices, 14)
            ma_5 = sum(prices[-5:]) / 5  # 5-period moving average
            ma_10 = sum(prices[-10:]) / 10  # 10-period moving average
            
            # Price momentum (recent vs average)
            recent_avg = sum(prices[-3:]) / 3
            older_avg = sum(prices[-10:-7]) / 3
            price_momentum = (recent_avg - older_avg) / older_avg * 100
            
            # Initialize scoring
            buy_score = 0
            sell_score = 0
            reasoning_parts = []
            
            # RSI Signal (responsive thresholds)
            if rsi and rsi < 45:  # Oversold - good buying opportunity
                buy_score += 2
                reasoning_parts.append(f"RSI oversold ({rsi:.1f})")
            elif rsi and rsi > 55:  # Overbought - selling opportunity  
                sell_score += 2
                reasoning_parts.append(f"RSI overbought ({rsi:.1f})")
            
            # Moving Average Signal
            if current_price < ma_5 < ma_10:  # Price below both MAs - potential buy
                buy_score += 1
                reasoning_parts.append("Price below moving averages")
            elif current_price > ma_5 > ma_10:  # Price above both MAs - potential sell
                sell_score += 1
                reasoning_parts.append("Price above moving averages")
            
            # Price Drop Detection (immediate buy signal)
            if price_momentum < -0.3:  # Significant recent drop
                buy_score += 3  # Strong buy signal on drops
                reasoning_parts.append(f"Price drop detected ({price_momentum:.2f}%)")
            elif price_momentum > 0.3:  # Significant recent rise
                sell_score += 1
                reasoning_parts.append(f"Price rise detected ({price_momentum:.2f}%)")
            
            # Determine signal
            total_signals = max(buy_score, sell_score)
            if buy_score > sell_score and buy_score >= 2:
                signal = "BUY"
                confidence = min(buy_score / 5.0, 1.0)  # Max confidence at 5 points
                reasoning = f"BUY signal (score: {buy_score}): " + ", ".join(reasoning_parts)
            elif sell_score > buy_score and sell_score >= 2:
                signal = "SELL"
                confidence = min(sell_score / 5.0, 1.0)
                reasoning = f"SELL signal (score: {sell_score}): " + ", ".join(reasoning_parts)
            else:
                signal = "HOLD"
                confidence = 0.3
                reasoning = f"HOLD signal: Insufficient signals. " + ", ".join(reasoning_parts) if reasoning_parts else "No clear signal"
            
            return TradingSignalResponse(
                symbol=symbol,
                signal=signal,
                confidence=confidence,
                reasoning=reasoning,
                indicators={
                    "rsi": rsi,
                    "ma_5": ma_5,
                    "ma_10": ma_10,
                    "price_momentum": price_momentum,
                    "current_price": current_price
                }
            )
            
        except Exception as e:
            logger.error(f"Error generating trading signal: {e}")
            return TradingSignalResponse(
                symbol=symbol,
                signal="HOLD",
                confidence=0.0,
                reasoning=f"Error: {str(e)}"
            )
            reasoning_parts = []
            score = 0.0  # Composite score: negative = sell, positive = buy
            max_score = 0.0  # Track maximum possible score for confidence calculation
            
            current_price = market_data.current_price
            indicators = {"current_price": current_price}
            
            # === ADVANCED RSI ANALYSIS ===
            rsi_14 = self._calculate_rsi(prices, 14)
            rsi_9 = self._calculate_rsi(prices, 9)   # Short-term RSI
            rsi_21 = self._calculate_rsi(prices, 21) # Long-term RSI
            
            if rsi_14 and rsi_9 and rsi_21:
                # RSI Divergence Detection
                rsi_trend = self._calculate_rsi_trend(prices, rsi_14, 10)
                price_trend = self._calculate_price_trend(prices, 10)
                
                # Multi-timeframe RSI confirmation
                rsi_alignment = 0
                if rsi_9 < 30 and rsi_14 < 35 and rsi_21 < 40:  # All oversold
                    rsi_alignment = 3  # Strong buy
                elif rsi_9 > 70 and rsi_14 > 65 and rsi_21 > 60:  # All overbought
                    rsi_alignment = -3  # Strong sell
                elif rsi_9 < 40 and rsi_14 < 45:  # Short-term oversold
                    rsi_alignment = 1
                elif rsi_9 > 60 and rsi_14 > 55:  # Short-term overbought
                    rsi_alignment = -1
                
                score += rsi_alignment * 0.25  # RSI weight: 25%
                max_score += 0.75  # 3 * 0.25
                
                # RSI Divergence bonus
                if rsi_trend > 0 and price_trend < 0:  # Bullish divergence
                    score += 0.15
                    reasoning_parts.append("RSI bullish divergence detected")
                elif rsi_trend < 0 and price_trend > 0:  # Bearish divergence
                    score -= 0.15
                    reasoning_parts.append("RSI bearish divergence detected")
                
                indicators.update({"rsi_14": rsi_14, "rsi_9": rsi_9, "rsi_21": rsi_21})
            
            # === ADVANCED MOVING AVERAGES ===
            ema_9 = self._calculate_ema(prices, 9)
            ema_21 = self._calculate_ema(prices, 21)
            ema_50 = self._calculate_ema(prices, 50)
            sma_20 = self._calculate_moving_average(prices, 20)
            
            if ema_9 and ema_21 and ema_50:
                # EMA Crossover Analysis
                ema_score = 0
                if ema_9 > ema_21 > ema_50:  # Bullish alignment
                    ema_score = 2
                    reasoning_parts.append("Bullish EMA alignment (9>21>50)")
                elif ema_9 < ema_21 < ema_50:  # Bearish alignment
                    ema_score = -2
                    reasoning_parts.append("Bearish EMA alignment (9<21<50)")
                elif ema_9 > ema_21:  # Short-term bullish
                    ema_score = 1
                elif ema_9 < ema_21:  # Short-term bearish
                    ema_score = -1
                
                # Price position relative to EMAs
                if current_price > ema_9 > ema_21:
                    ema_score += 0.5
                elif current_price < ema_9 < ema_21:
                    ema_score -= 0.5
                
                score += ema_score * 0.2  # EMA weight: 20%
                max_score += 0.5  # 2.5 * 0.2
                
                indicators.update({"ema_9": ema_9, "ema_21": ema_21, "ema_50": ema_50})
            
            # === MACD ANALYSIS ===
            macd_line, macd_signal, macd_histogram = self._calculate_macd(prices)
            if macd_line and macd_signal:
                macd_score = 0
                if macd_line > macd_signal and macd_histogram[-1] > 0:  # Bullish MACD
                    macd_score = 1.5
                    reasoning_parts.append("MACD bullish crossover")
                elif macd_line < macd_signal and macd_histogram[-1] < 0:  # Bearish MACD
                    macd_score = -1.5
                    reasoning_parts.append("MACD bearish crossover")
                
                # MACD momentum
                if len(macd_histogram) >= 2:
                    if macd_histogram[-1] > macd_histogram[-2]:  # Increasing momentum
                        macd_score += 0.3
                    else:  # Decreasing momentum
                        macd_score -= 0.3
                
                score += macd_score * 0.15  # MACD weight: 15%
                max_score += 0.27  # 1.8 * 0.15
                
                indicators.update({"macd": macd_line, "macd_signal": macd_signal})
            
            # === VOLUME ANALYSIS ===
            if len(volumes) >= 20:
                volume_avg = statistics.mean(volumes[-20:])  # 20-period volume average
                current_volume = volumes[-1]
                volume_ratio = current_volume / volume_avg if volume_avg > 0 else 1
                
                volume_score = 0
                if volume_ratio > 1.5:  # High volume
                    if score > 0:  # Confirm bullish signals
                        volume_score = 0.3
                        reasoning_parts.append("High volume confirms bullish signal")
                    elif score < 0:  # Confirm bearish signals
                        volume_score = -0.3
                        reasoning_parts.append("High volume confirms bearish signal")
                elif volume_ratio < 0.7:  # Low volume - reduce confidence
                    volume_score = -0.1
                    reasoning_parts.append("Low volume reduces signal strength")
                
                score += volume_score
                max_score += 0.3
                
                indicators.update({"volume_ratio": volume_ratio, "volume_avg": volume_avg})
            
            # === SUPPORT/RESISTANCE ANALYSIS ===
            support_level, resistance_level = self._calculate_support_resistance(highs, lows, prices)
            if support_level and resistance_level:
                sr_score = 0
                price_to_support = (current_price - support_level) / support_level
                price_to_resistance = (resistance_level - current_price) / current_price
                
                if price_to_support < 0.02:  # Near support (within 2%)
                    sr_score = 1.0
                    reasoning_parts.append("Price near support level")
                elif price_to_resistance < 0.02:  # Near resistance (within 2%)
                    sr_score = -1.0
                    reasoning_parts.append("Price near resistance level")
                
                score += sr_score * 0.1  # Support/Resistance weight: 10%
                max_score += 0.1
                
                indicators.update({"support": support_level, "resistance": resistance_level})
            
            # === VOLATILITY ANALYSIS ===
            atr = self._calculate_atr(highs, lows, prices, 14)
            if atr:
                volatility_ratio = atr / current_price
                if volatility_ratio > 0.03:  # High volatility
                    score *= 0.8  # Reduce confidence in high volatility
                    reasoning_parts.append("High volatility reduces signal confidence")
                
                indicators.update({"atr": atr, "volatility": volatility_ratio})
            
            # === BOLLINGER BANDS ===
            bb_upper, bb_lower = self._calculate_bollinger_bands(prices, 20, 2)
            if bb_upper and bb_lower:
                bb_score = 0
                bb_width = (bb_upper - bb_lower) / sma_20 if sma_20 else 0
                
                if current_price < bb_lower:  # Oversold
                    bb_score = 0.8
                    reasoning_parts.append("Price below Bollinger lower band")
                elif current_price > bb_upper:  # Overbought
                    bb_score = -0.8
                    reasoning_parts.append("Price above Bollinger upper band")
                
                # Bollinger Band squeeze
                if bb_width < 0.04:  # Narrow bands indicate low volatility
                    reasoning_parts.append("Bollinger Band squeeze - volatility expansion expected")
                
                score += bb_score * 0.1  # Bollinger weight: 10%
                max_score += 0.08
                
                indicators.update({"bollinger_upper": bb_upper, "bollinger_lower": bb_lower})
            
            # === GENERATE FINAL SIGNAL ===
            if max_score > 0:
                confidence = min(abs(score) / max_score, 1.0)
            
            if score > 0.15:  # Strong bullish threshold
                signal = "BUY"
            elif score < -0.15:  # Strong bearish threshold
                signal = "SELL"
            else:
                signal = "HOLD"
                
            # Combine reasoning
            if reasoning_parts:
                reasoning = f"Score: {score:.3f}/{max_score:.3f}. " + "; ".join(reasoning_parts[:3])
            else:
                reasoning = f"Score: {score:.3f}/{max_score:.3f}. No strong signals detected."
            
            return TradingSignalResponse(
                symbol=symbol,
                signal=signal,
                confidence=confidence,
                price=current_price,
                strategy="advanced_multi_indicator",
                indicators=indicators,
                timestamp=datetime.utcnow(),
                reasoning=reasoning
            )
            
        except Exception as e:
            logger.error(f"Error generating trading signal for {symbol}: {e}")
            raise
    
    # === Risk Management Methods ===
    
    async def calculate_position_size(self, symbol: str, side: str, risk_percentage: float = None) -> float:
        """Calculate optimal position size based on risk management"""
        try:
            if risk_percentage is None:
                risk_percentage = self.trading_config.get('max_position_size_percentage', 10.0)
            
            # Get account balance
            balance_response = await self.get_account_balance()
            total_balance = balance_response.total_usdt_value
            
            # Calculate risk amount
            risk_amount = total_balance * (risk_percentage / 100)
            
            # Get current price
            current_price = await self.get_current_price(symbol)
            
            # Calculate quantity
            if side == "BUY":
                quantity = risk_amount / current_price
            else:
                # For sell orders, check available balance of the base asset
                base_asset = symbol.replace('USDT', '')
                balances = balance_response.balances
                available_balance = 0.0
                
                for balance in balances:
                    if balance.asset == base_asset:
                        available_balance = balance.free
                        break
                
                quantity = min(available_balance, risk_amount / current_price)
            
            return quantity
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0.0
    
    async def check_stop_loss_take_profit(self, user_id: str):
        """Check and execute stop-loss and take-profit orders"""
        try:
            # Get user's open positions (from database)
            positions = await self._get_user_positions(user_id)
            
            for position in positions:
                symbol = position['symbol']
                entry_price = position['entry_price']
                quantity = position['quantity']
                side = position['side']
                
                current_price = await self.get_current_price(symbol)
                
                # Calculate PnL percentage
                if side == "BUY":
                    pnl_percentage = ((current_price - entry_price) / entry_price) * 100
                else:
                    pnl_percentage = ((entry_price - current_price) / entry_price) * 100
                
                # Check stop-loss
                stop_loss_threshold = -self.trading_config.get('stop_loss_percentage', 5.0)
                if pnl_percentage <= stop_loss_threshold:
                    await self._execute_stop_loss(user_id, position, current_price)
                
                # Check take-profit
                take_profit_threshold = self.trading_config.get('take_profit_percentage', 10.0)
                if pnl_percentage >= take_profit_threshold:
                    await self._execute_take_profit(user_id, position, current_price)
                    
        except Exception as e:
            logger.error(f"Error checking stop-loss/take-profit: {e}")
    
    # === Technical Indicator Calculations ===
    
    def _calculate_moving_average(self, prices: List[float], period: int) -> Optional[float]:
        """Calculate simple moving average"""
        if len(prices) < period:
            return None
        return statistics.mean(prices[-period:])
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return None
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [delta if delta > 0 else 0 for delta in deltas]
        losses = [-delta if delta < 0 else 0 for delta in deltas]
        
        avg_gain = statistics.mean(gains[-period:])
        avg_loss = statistics.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: float = 2) -> Tuple[Optional[float], Optional[float]]:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            return None, None
        
        recent_prices = prices[-period:]
        sma = statistics.mean(recent_prices)
        std = statistics.stdev(recent_prices)
        
        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)
        
        return upper_band, lower_band
    
    def _determine_trend(self, prices: List[float], ma_20: Optional[float], ma_50: Optional[float]) -> str:
        """Determine trend direction"""
        if not ma_20:
            return "sideways"
        
        current_price = prices[-1]
        
        if ma_50:
            if current_price > ma_20 > ma_50:
                return "bullish"
            elif current_price < ma_20 < ma_50:
                return "bearish"
        else:
            if current_price > ma_20:
                return "bullish"
            elif current_price < ma_20:
                return "bearish"
        
        return "sideways"
    
    def _calculate_signal_strength(self, current_price: float, ma_20: Optional[float], 
                                 rsi: Optional[float], bb_upper: Optional[float], 
                                 bb_lower: Optional[float]) -> float:
        """Calculate signal strength (0.0 to 1.0)"""
        strength = 0.0
        factors = 0
        
        # Moving average factor
        if ma_20:
            ma_diff = abs(current_price - ma_20) / ma_20
            strength += min(ma_diff * 5, 0.33)  # Max 0.33 from MA
            factors += 1
        
        # RSI factor
        if rsi:
            if rsi < 30 or rsi > 70:
                strength += 0.33  # Strong RSI signal
            elif rsi < 40 or rsi > 60:
                strength += 0.17  # Moderate RSI signal
            factors += 1
        
        # Bollinger Bands factor
        if bb_upper and bb_lower:
            if current_price > bb_upper or current_price < bb_lower:
                strength += 0.33  # Strong BB signal
            factors += 1
        
        return min(strength, 1.0) if factors > 0 else 0.0
    
    # === Helper Methods ===
    
    def _format_quantity(self, quantity: float, symbol: str) -> str:
        """Format quantity according to symbol precision"""
        # Get symbol info for precision
        symbol_info = self.client.get_symbol_info(symbol)
        step_size = None
        
        for filter in symbol_info['filters']:
            if filter['filterType'] == 'LOT_SIZE':
                step_size = float(filter['stepSize'])
                break
        
        if step_size:
            precision = max(0, -int(np.log10(step_size)))
            return f"{quantity:.{precision}f}"
        
        return f"{quantity:.8f}"
    
    def _format_price(self, price: float, symbol: str) -> str:
        """Format price according to symbol precision"""
        symbol_info = self.client.get_symbol_info(symbol)
        tick_size = None
        
        for filter in symbol_info['filters']:
            if filter['filterType'] == 'PRICE_FILTER':
                tick_size = float(filter['tickSize'])
                break
        
        if tick_size:
            precision = max(0, -int(np.log10(tick_size)))
            return f"{price:.{precision}f}"
        
        return f"{price:.8f}"
    
    def _format_quote_quantity(self, quote_qty: float) -> str:
        """Format quote quantity (USDT amount)"""
        return f"{quote_qty:.2f}"
    
    async def _validate_buy_order(self, order_request: MarketOrderRequest):
        """Validate buy order requirements"""
        usdt_balance = await self.get_usdt_balance()
        
        if order_request.quote_order_qty:
            required_balance = order_request.quote_order_qty
        else:
            current_price = await self.get_current_price(order_request.symbol.value)
            required_balance = order_request.quantity * current_price
        
        if usdt_balance < required_balance:
            raise TradingErrorResponse(
                error="INSUFFICIENT_BALANCE",
                message=f"Insufficient USDT balance. Required: {required_balance}, Available: {usdt_balance}",
                balance_required=required_balance,
                balance_available=usdt_balance,
                symbol=order_request.symbol.value,
                timestamp=datetime.utcnow()
            )
    
    async def _validate_sell_order(self, order_request: MarketOrderRequest):
        """Validate sell order requirements"""
        base_asset = order_request.symbol.value.replace('USDT', '')
        account = self.client.get_account()
        
        available_balance = 0.0
        for balance in account['balances']:
            if balance['asset'] == base_asset:
                available_balance = float(balance['free'])
                break
        
        if available_balance < order_request.quantity:
            raise TradingErrorResponse(
                error="INSUFFICIENT_BALANCE",
                message=f"Insufficient {base_asset} balance. Required: {order_request.quantity}, Available: {available_balance}",
                balance_required=order_request.quantity,
                balance_available=available_balance,
                symbol=order_request.symbol.value,
                timestamp=datetime.utcnow()
            )
    
    # === Database Operations ===
    
    async def _get_trading_profile(self, user_id: str) -> Optional[Dict]:
        """Get user trading profile from database"""
        try:
            collection = get_collection('trading_profiles')
            profile = await collection.find_one({'user_id': user_id})
            return profile
        except Exception as e:
            logger.error(f"Error getting trading profile: {e}")
            return None
    
    async def _save_order(self, order_data: Dict):
        """Save order to database"""
        try:
            collection = get_collection('orders')
            await collection.insert_one(order_data)
        except Exception as e:
            logger.error(f"Error saving order: {e}")
    
    async def _update_order_status(self, order_id: str, status: str):
        """Update order status in database"""
        try:
            collection = get_collection('orders')
            await collection.update_one(
                {'binance_order_id': order_id},
                {'$set': {'status': status, 'updated_at': datetime.utcnow()}}
            )
        except Exception as e:
            logger.error(f"Error updating order status: {e}")
    
    async def _get_user_positions(self, user_id: str) -> List[Dict]:
        """Get user's open positions from database"""
        try:
            collection = get_collection('positions')
            positions = await collection.find({'user_id': user_id, 'is_open': True}).to_list(None)
            return positions
        except Exception as e:
            logger.error(f"Error getting user positions: {e}")
            return []
    
    # === Notification Methods ===
    
    async def _send_trade_notification(self, user_id: str, order_data: Dict, result: Dict):
        """Send trade notification via Discord"""
        try:
            message = f"Trade Executed: {order_data['side']} {order_data['quantity']} {order_data['symbol']} at ${result.get('fills', [{}])[0].get('price', 'N/A')}"
            
            # Send Discord notification
            await send_discord_notification(
                message=message,
                user_id=user_id,
                trade_data=order_data
            )
            
        except Exception as e:
            logger.error(f"Error sending trade notification: {e}")
    
    async def _send_error_notification(self, user_id: str, error_message: str):
        """Send error notification"""
        try:
            await send_discord_notification(
                message=f"Trading Error: {error_message}",
                user_id=user_id,
                error=True
            )
        except Exception as e:
            logger.error(f"Error sending error notification: {e}")
    
    # === ADVANCED TECHNICAL ANALYSIS HELPER METHODS ===
    
    def _calculate_ema(self, prices: list, period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return None
        
        multiplier = 2.0 / (period + 1)
        ema = prices[0]  # Start with first price
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def _calculate_macd(self, prices: list, fast=12, slow=26, signal=9):
        """Calculate MACD line, signal line, and histogram"""
        if len(prices) < slow:
            return None, None, []
        
        # Calculate MACD values for all periods
        macd_values = []
        for i in range(slow-1, len(prices)):
            ema_f = self._calculate_ema(prices[:i+1], fast)
            ema_s = self._calculate_ema(prices[:i+1], slow)
            if ema_f and ema_s:
                macd_values.append(ema_f - ema_s)
        
        if not macd_values:
            return None, None, []
        
        # Current MACD line value
        macd_line = macd_values[-1]
        
        # Calculate signal line (EMA of MACD)
        signal_line = self._calculate_ema(macd_values, signal) if len(macd_values) >= signal else None
        
        # Calculate histogram
        histogram = []
        if signal_line:
            # Calculate signal line for each period to get histogram
            for i in range(len(macd_values)):
                if i >= signal - 1:
                    sig_line = self._calculate_ema(macd_values[:i+1], signal)
                    if sig_line:
                        histogram.append(macd_values[i] - sig_line)
        
        return macd_line, signal_line, histogram
    
    def _calculate_rsi_trend(self, prices: list, rsi_values: list, period: int) -> float:
        """Calculate RSI trend over specified period"""
        if len(rsi_values) < period:
            return 0
        
        recent_rsi = rsi_values[-period:]
        if len(recent_rsi) < 2:
            return 0
        
        # Simple linear trend
        return recent_rsi[-1] - recent_rsi[0]
    
    def _calculate_price_trend(self, prices: list, period: int) -> float:
        """Calculate price trend over specified period"""
        if len(prices) < period:
            return 0
        
        recent_prices = prices[-period:]
        if len(recent_prices) < 2:
            return 0
        
        return (recent_prices[-1] - recent_prices[0]) / recent_prices[0]
    
    def _calculate_support_resistance(self, highs: list, lows: list, prices: list, window=20):
        """Calculate dynamic support and resistance levels"""
        if len(prices) < window:
            return None, None
        
        recent_highs = highs[-window:]
        recent_lows = lows[-window:]
        
        # Find significant highs and lows
        resistance_level = max(recent_highs)
        support_level = min(recent_lows)
        
        # Refine using price clustering
        price_range = resistance_level - support_level
        if price_range > 0:
            # Look for price levels that have been tested multiple times
            price_bins = {}
            bin_size = price_range * 0.02  # 2% bins
            
            for price in prices[-window:]:
                bin_key = int(price / bin_size)
                price_bins[bin_key] = price_bins.get(bin_key, 0) + 1
            
            # Find most tested levels
            if price_bins:
                most_tested = max(price_bins.items(), key=lambda x: x[1])
                tested_price = most_tested[0] * bin_size
                
                if tested_price > prices[-1]:  # Above current price
                    resistance_level = min(resistance_level, tested_price)
                else:  # Below current price
                    support_level = max(support_level, tested_price)
        
        return support_level, resistance_level
    
    def _calculate_atr(self, highs: list, lows: list, closes: list, period: int) -> float:
        """Calculate Average True Range"""
        if len(highs) < period + 1:
            return None
        
        true_ranges = []
        for i in range(1, len(highs)):
            high_low = highs[i] - lows[i]
            high_close_prev = abs(highs[i] - closes[i-1])
            low_close_prev = abs(lows[i] - closes[i-1])
            
            true_range = max(high_low, high_close_prev, low_close_prev)
            true_ranges.append(true_range)
        
        if len(true_ranges) >= period:
            return statistics.mean(true_ranges[-period:])
        
        return None
    
    async def _execute_stop_loss(self, user_id: str, position: Dict, current_price: float):
        """Execute stop-loss order"""
        try:
            symbol = position['symbol']
            quantity = position['quantity']
            side = "SELL" if position['side'] == "BUY" else "BUY"
            
            # Create market order to close position
            order_request = MarketOrderRequest(
                symbol=TradingSymbol(symbol),
                side=TradingSide(side),
                quantity=quantity
            )
            
            await self.place_market_order(user_id, order_request)
            
            # Mark position as closed
            await self._close_position(position['_id'])
            
            # Send notification
            message = f"Stop-Loss Triggered: Closed {symbol} position at ${current_price}"
            await send_discord_notification(message, user_id, stop_loss=True)
            
        except Exception as e:
            logger.error(f"Error executing stop-loss: {e}")
    
    async def _execute_take_profit(self, user_id: str, position: Dict, current_price: float):
        """Execute take-profit order"""
        try:
            symbol = position['symbol']
            quantity = position['quantity']
            side = "SELL" if position['side'] == "BUY" else "BUY"
            
            # Create market order to close position
            order_request = MarketOrderRequest(
                symbol=TradingSymbol(symbol),
                side=TradingSide(side),
                quantity=quantity
            )
            
            await self.place_market_order(user_id, order_request)
            
            # Mark position as closed
            await self._close_position(position['_id'])
            
            # Send notification
            message = f"Take-Profit Hit: Closed {symbol} position at ${current_price}"
            await send_discord_notification(message, user_id, take_profit=True)
            
        except Exception as e:
            logger.error(f"Error executing take-profit: {e}")
    
    async def _close_position(self, position_id: str):
        """Close position in database"""
        try:
            collection = get_collection('positions')
            await collection.update_one(
                {'_id': position_id},
                {'$set': {'is_open': False, 'closed_at': datetime.utcnow()}}
            )
        except Exception as e:
            logger.error(f"Error closing position: {e}")
        
    async def _start_websocket_streams(self):
        """Start WebSocket streams for real-time data (fixed threading)"""
        try:
            # Import here to avoid threading conflicts
            import nest_asyncio
            nest_asyncio.apply()
            
            from binance import ThreadedWebSocketManager
            
            self.twm = ThreadedWebSocketManager()
            self.twm.start()
            
            # Start price streams for supported symbols
            for symbol in TradingSymbol:
                try:
                    stream_name = self.twm.start_symbol_ticker_socket(
                        callback=self._handle_ticker_data,
                        symbol=symbol.value
                    )
                    self.active_streams.append(stream_name)
                except Exception as e:
                    logger.warning(f"Failed to start stream for {symbol.value}: {e}")
            
            logger.info("WebSocket streams started successfully")
            
        except Exception as e:
            logger.error(f"Error starting WebSocket streams: {e}")
            # Don't raise - let the bot use API fallback
    
    def _handle_ticker_data(self, msg):
        """Handle incoming ticker data from WebSocket"""
        try:
            symbol = msg['s']
            price = float(msg['c'])
            volume = float(msg['v'])
            
            # Update price cache
            if symbol in self.price_cache:
                self.price_cache[symbol].append(price)
                if len(self.price_cache[symbol]) > 200:
                    self.price_cache[symbol] = self.price_cache[symbol][-200:]
            
            # Update volume cache
            if symbol in self.volume_cache:
                self.volume_cache[symbol].append(volume)
                if len(self.volume_cache[symbol]) > 200:
                    self.volume_cache[symbol] = self.volume_cache[symbol][-200:]
                    
        except Exception as e:
            logger.error(f"Error handling ticker data: {e}")
    
    async def stop_websocket_streams(self):
        """Stop WebSocket streams"""
        try:
            if self.twm:
                self.twm.stop()
                self.twm = None
                self.active_streams = []
                logger.info("WebSocket streams stopped")
        except Exception as e:
            logger.error(f"Error stopping WebSocket streams: {e}")
    
    def __del__(self):
        """Cleanup when service is destroyed"""
        try:
            if self.twm:
                self.twm.stop()
        except:
            pass
