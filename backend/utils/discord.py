# backend/utils/discord.py

import aiohttp
import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Any, List
import json
import os
from app.config import DISCORD_WEBHOOK_URL

# Setup logging
logger = logging.getLogger(__name__)

# Discord configuration
DEFAULT_BOT_NAME = "AutoTradeBot"
DEFAULT_AVATAR_URL = "https://cdn.discordapp.com/attachments/123456789/bot-avatar.png"

# Debug logging for webhook URL
if DISCORD_WEBHOOK_URL:
    logger.info(f"Discord webhook URL loaded successfully (length: {len(DISCORD_WEBHOOK_URL)})")
else:
    logger.warning("Discord webhook URL not found in environment variables")

# Color codes for different message types
COLORS = {
    'buy': 0x00FF00,      # Green
    'sell': 0xFF0000,     # Red
    'profit': 0x00FFFF,   # Cyan
    'loss': 0xFFA500,     # Orange
    'info': 0x0099FF,     # Blue
    'warning': 0xFFFF00,  # Yellow
    'error': 0xFF0000,    # Red
    'success': 0x00FF00   # Green
}

# Emoji mappings
EMOJIS = {
    'buy': '🟢',
    'sell': '🔴',
    'profit': '💰',
    'loss': '📉',
    'stop_loss': '🛑',
    'take_profit': '🎯',
    'balance': '💳',
    'chart': '📊',
    'robot': '🤖',
    'warning': '⚠️',
    'error': '🚨',
    'success': '✅',
    'info': 'ℹ️'
}


class DiscordNotifier:
    """Discord notification service for trading alerts"""
    
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or DISCORD_WEBHOOK_URL
        self.session = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def send_embed(self, title: str, description: str, color: int = COLORS['info'],
                        fields: Optional[List[Dict]] = None, footer: Optional[str] = None,
                        thumbnail: Optional[str] = None, image: Optional[str] = None) -> bool:
        """Send a rich embed message to Discord"""
        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured")
            return False
        
        embed = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": footer or f"{DEFAULT_BOT_NAME} • AutoTrade Alert"
            }
        }
        
        if fields:
            embed["fields"] = fields
            
        if thumbnail:
            embed["thumbnail"] = {"url": thumbnail}
            
        if image:
            embed["image"] = {"url": image}
        
        payload = {
            "username": DEFAULT_BOT_NAME,
            "avatar_url": DEFAULT_AVATAR_URL,
            "embeds": [embed]
        }
        
        return await self._send_webhook(payload)
    
    async def send_simple_message(self, message: str, username: str = None) -> bool:
        """Send a simple text message to Discord"""
        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured")
            return False
        
        payload = {
            "content": message,
            "username": username or DEFAULT_BOT_NAME,
            "avatar_url": DEFAULT_AVATAR_URL
        }
        
        return await self._send_webhook(payload)
    
    async def _send_webhook(self, payload: Dict) -> bool:
        """Send webhook payload to Discord"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 204:
                    logger.debug("Discord message sent successfully")
                    return True
                else:
                    logger.error(f"Discord webhook failed with status {response.status}")
                    error_text = await response.text()
                    logger.error(f"Discord error response: {error_text}")
                    return False
                    
        except asyncio.TimeoutError:
            logger.error("Discord webhook timeout")
            return False
        except Exception as e:
            logger.error(f"Error sending Discord webhook: {e}")
            return False


# Global notifier instance
discord_notifier = DiscordNotifier()


async def send_trade_notification( trade_data: Dict[str, Any]) -> bool:
    """Send trading notification to Discord"""
    try:
        symbol = trade_data.get('symbol', 'UNKNOWN')
        side = trade_data.get('side', 'UNKNOWN')
        quantity = trade_data.get('quantity', 0)
        price = trade_data.get('price', 0)
        confidence = trade_data.get('confidence', 0)
        pnl = trade_data.get('pnl')
        
        # Determine color and emoji based on trade type
        if side.upper() == 'BUY':
            color = COLORS['buy']
            emoji = EMOJIS['buy']
            action = "BOUGHT"
        else:
            color = COLORS['sell']
            emoji = EMOJIS['sell']
            action = "SOLD"
        
        # Calculate trade value
        trade_value = quantity * price
        
        # Create embed fields
        fields = [
            {
                "name": "📊 Symbol",
                "value": symbol,
                "inline": True
            },
            {
                "name": "💰 Quantity",
                "value": f"{quantity:.8f}",
                "inline": True
            },
            {
                "name": "💵 Price",
                "value": f"${price:.4f}",
                "inline": True
            },
            {
                "name": "💳 Total Value",
                "value": f"${trade_value:.2f}",
                "inline": True
            },
            {
                "name": "📈 Confidence",
                "value": f"{confidence:.1%}",
                "inline": True
            },
            {
                "name": "⏰ Time",
                "value": datetime.utcnow().strftime("%H:%M:%S UTC"),
                "inline": True
            }
        ]
        
        # Add PnL if available
        if pnl is not None:
            pnl_emoji = EMOJIS['profit'] if pnl > 0 else EMOJIS['loss']
            fields.append({
                "name": f"{pnl_emoji} P&L",
                "value": f"${pnl:.2f} ({pnl/trade_value*100:.2f}%)",
                "inline": True
            })
        
        title = f"{emoji} Trade Executed: {action} {symbol}"
        description = f"Successfully {action.lower()} {quantity:.8f} {symbol} at ${price:.4f}"
        
        async with discord_notifier:
            return await discord_notifier.send_embed(
                title=title,
                description=description,
                color=color,
                fields=fields,
            )
            
    except Exception as e:
        logger.error(f"Error sending trade notification: {e}")
        return False


async def send_stop_loss_notification( symbol: str, quantity: float, 
                                    trigger_price: float, loss_amount: float) -> bool:
    """Send stop-loss triggered notification"""
    try:
        fields = [
            {
                "name": "📊 Symbol",
                "value": symbol,
                "inline": True
            },
            {
                "name": "💰 Quantity",
                "value": f"{quantity:.8f}",
                "inline": True
            },
            {
                "name": "💵 Trigger Price",
                "value": f"${trigger_price:.4f}",
                "inline": True
            },
            {
                "name": "📉 Loss Amount",
                "value": f"${loss_amount:.2f}",
                "inline": True
            },
            {
                "name": "⏰ Time",
                "value": datetime.utcnow().strftime("%H:%M:%S UTC"),
                "inline": True
            }
        ]
        
        title = f"{EMOJIS['stop_loss']} Stop-Loss Triggered: {symbol}"
        description = f"Position closed at ${trigger_price:.4f} to limit losses"
        
        async with discord_notifier:
            return await discord_notifier.send_embed(
                title=title,
                description=description,
                color=COLORS['loss'],
                fields=fields,
            )
            
    except Exception as e:
        logger.error(f"Error sending stop-loss notification: {e}")
        return False


async def send_take_profit_notification( symbol: str, quantity: float,
                                      trigger_price: float, profit_amount: float) -> bool:
    """Send take-profit hit notification"""
    try:
        fields = [
            {
                "name": "📊 Symbol",
                "value": symbol,
                "inline": True
            },
            {
                "name": "💰 Quantity",
                "value": f"{quantity:.8f}",
                "inline": True
            },
            {
                "name": "💵 Trigger Price",
                "value": f"${trigger_price:.4f}",
                "inline": True
            },
            {
                "name": "💰 Profit Amount",
                "value": f"${profit_amount:.2f}",
                "inline": True
            },
            {
                "name": "⏰ Time",
                "value": datetime.utcnow().strftime("%H:%M:%S UTC"),
                "inline": True
            }
        ]
        
        title = f"{EMOJIS['take_profit']} Take-Profit Hit: {symbol}"
        description = f"Position closed at ${trigger_price:.4f} with profit!"
        
        async with discord_notifier:
            return await discord_notifier.send_embed(
                title=title,
                description=description,
                color=COLORS['profit'],
                fields=fields,
            )
            
    except Exception as e:
        logger.error(f"Error sending take-profit notification: {e}")
        return False


async def send_balance_update( total_balance: float, daily_pnl: float,
                            major_balances: Dict[str, float]) -> bool:
    """Send balance update notification"""
    try:
        # Format major balances
        balance_text = "\n".join([
            f"{asset}: {amount:.8f}" for asset, amount in major_balances.items()
            if amount > 0
        ])
        
        pnl_emoji = EMOJIS['profit'] if daily_pnl >= 0 else EMOJIS['loss']
        pnl_color = COLORS['profit'] if daily_pnl >= 0 else COLORS['loss']
        
        fields = [
            {
                "name": "💳 Total Balance",
                "value": f"${total_balance:.2f}",
                "inline": True
            },
            {
                "name": f"{pnl_emoji} Daily P&L",
                "value": f"${daily_pnl:.2f}",
                "inline": True
            },
            {
                "name": "💰 Asset Balances",
                "value": balance_text or "No significant balances",
                "inline": False
            }
        ]
        
        title = f"{EMOJIS['balance']} Portfolio Update"
        
        async with discord_notifier:
            return await discord_notifier.send_embed(
                title=title,
                color=pnl_color,
                fields=fields,
            )
            
    except Exception as e:
        logger.error(f"Error sending balance update: {e}")
        return False


async def send_signal_notification( symbol: str, signal: str, 
                                 confidence: float, price: float, reasoning: str) -> bool:
    """Send trading signal notification"""
    try:
        if signal.upper() == 'BUY':
            color = COLORS['buy']
            emoji = EMOJIS['buy']
        elif signal.upper() == 'SELL':
            color = COLORS['sell']
            emoji = EMOJIS['sell']
        else:
            color = COLORS['info']
            emoji = EMOJIS['info']
        
        fields = [
            {
                "name": "📊 Symbol",
                "value": symbol,
                "inline": True
            },
            {
                "name": "💵 Price",
                "value": f"${price:.4f}",
                "inline": True
            },
            {
                "name": "📈 Confidence",
                "value": f"{confidence:.1%}",
                "inline": True
            },
            {
                "name": "🧠 Analysis",
                "value": reasoning[:500] + "..." if len(reasoning) > 500 else reasoning,
                "inline": False
            }
        ]
        
        title = f"{emoji} Trading Signal: {signal.upper()} {symbol}"
        description = f"Signal generated with {confidence:.1%} confidence"
        
        async with discord_notifier:
            return await discord_notifier.send_embed(
                title=title,
                description=description,
                color=color,
                fields=fields,
            )
            
    except Exception as e:
        logger.error(f"Error sending signal notification: {e}")
        return False


async def send_error_notification( error_message: str, error_type: str = "TRADING_ERROR") -> bool:
    """Send error notification"""
    try:
        fields = [
            {
                "name": "🚨 Error Type",
                "value": error_type,
                "inline": True
            },
            {
                "name": "⏰ Time",
                "value": datetime.utcnow().strftime("%H:%M:%S UTC"),
                "inline": True
            },
            {
                "name": "📝 Details",
                "value": error_message[:1000] + "..." if len(error_message) > 1000 else error_message,
                "inline": False
            }
        ]
        
        title = f"{EMOJIS['error']} Trading Error Alert"
        description = "An error occurred in the trading system"
        
        async with discord_notifier:
            return await discord_notifier.send_embed(
                title=title,
                description=description,
                color=COLORS['error'],
                fields=fields,
            )
            
    except Exception as e:
        logger.error(f"Error sending error notification: {e}")
        return False


async def send_bot_status_notification( status: str, message: str) -> bool:
    """Send bot status notification"""
    try:
        if status.lower() == 'started':
            color = COLORS['success']
            emoji = EMOJIS['success']
        elif status.lower() == 'stopped':
            color = COLORS['warning']
            emoji = EMOJIS['warning']
        elif status.lower() == 'error':
            color = COLORS['error']
            emoji = EMOJIS['error']
        else:
            color = COLORS['info']
            emoji = EMOJIS['robot']
        
        title = f"{emoji} Trading Bot {status.title()}"
        description = message
        
        fields = [
            {
                "name": "⏰ Time",
                "value": datetime.utcnow().strftime("%H:%M:%S UTC"),
                "inline": True
            },
        ]
        
        async with discord_notifier:
            return await discord_notifier.send_embed(
                title=title,
                description=description,
                color=color,
                fields=fields
            )
            
    except Exception as e:
        logger.error(f"Error sending bot status notification: {e}")
        return False


async def send_daily_summary(summary_data: Dict[str, Any]) -> bool:
    """Send daily trading summary"""
    try:
        total_trades = summary_data.get('total_trades', 0)
        winning_trades = summary_data.get('winning_trades', 0)
        losing_trades = summary_data.get('losing_trades', 0)
        total_pnl = summary_data.get('total_pnl', 0)
        win_rate = summary_data.get('win_rate', 0)
        
        pnl_emoji = EMOJIS['profit'] if total_pnl >= 0 else EMOJIS['loss']
        color = COLORS['profit'] if total_pnl >= 0 else COLORS['loss']
        
        fields = [
            {
                "name": "📊 Total Trades",
                "value": str(total_trades),
                "inline": True
            },
            {
                "name": "✅ Winning Trades",
                "value": str(winning_trades),
                "inline": True
            },
            {
                "name": "❌ Losing Trades",
                "value": str(losing_trades),
                "inline": True
            },
            {
                "name": f"{pnl_emoji} Total P&L",
                "value": f"${total_pnl:.2f}",
                "inline": True
            },
            {
                "name": "🎯 Win Rate",
                "value": f"{win_rate:.1f}%",
                "inline": True
            },
            {
                "name": "📅 Date",
                "value": datetime.utcnow().strftime("%Y-%m-%d"),
                "inline": True
            }
        ]
        
        title = f"{EMOJIS['chart']} Daily Trading Summary"
        
        async with discord_notifier:
            return await discord_notifier.send_embed(
                title=title,
                color=color,
                fields=fields,
                footer=f"AutoTrade Bot • Daily Report"
            )
            
    except Exception as e:
        logger.error(f"Error sending daily summary: {e}")
        return False


# Main notification function used by other modules
async def send_discord_notification(message: str, **kwargs) -> bool:
    try:
        # Determine notification type and route accordingly
        if 'trade_data' in kwargs:
            return await send_trade_notification( kwargs['trade_data'])
        elif 'stop_loss' in kwargs:
            return await send_stop_loss_notification(**kwargs)
        elif 'take_profit' in kwargs:
            return await send_take_profit_notification(**kwargs)
        elif 'error' in kwargs:
            return await send_error_notification(message, kwargs.get('error_type', 'GENERAL_ERROR'))
        elif 'bot_status' in kwargs:
            return await send_bot_status_notification(kwargs.get('status', 'info'), message)
        elif 'daily_summary' in kwargs:
            return await send_daily_summary(kwargs['daily_summary'])
        else:
            # Send simple message
            async with discord_notifier:
                return await discord_notifier.send_simple_message(f"{message}")
        
    except Exception as e:
        logger.error(f"Error in send_discord_notification: {e}")
        return False





async def test_discord_webhook() -> bool:
    try:
        async with discord_notifier:
            return await discord_notifier.send_simple_message(
                f"{EMOJIS['robot']} Discord webhook test successful! • {datetime.utcnow().strftime('%H:%M:%S UTC')}"
            )
    except Exception as e:
        logger.error(f"Discord webhook test failed: {e}")
        return False
