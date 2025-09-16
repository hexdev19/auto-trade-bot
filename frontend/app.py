import streamlit as st
import requests
import json
import time
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import asyncio
import websockets
import threading
from typing import Dict, Optional

# Configuration
API_BASE_URL = "http://localhost:8080"
WS_URL = "ws://localhost:8080/ws"  # WebSocket endpoint

# Set page config
st.set_page_config(
    page_title="Real-Time BTC Trading Bot",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'real_time_data' not in st.session_state:
    st.session_state.real_time_data = {}
if 'price_history' not in st.session_state:
    st.session_state.price_history = []
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'ws_connected' not in st.session_state:
    st.session_state.ws_connected = False
if 'last_update' not in st.session_state:
    st.session_state.last_update = None
if 'final_summary' not in st.session_state:
    st.session_state.final_summary = None
if 'show_summary' not in st.session_state:
    st.session_state.show_summary = False

# Custom CSS for real-time dashboard
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #f7931a;
        text-align: center;
        margin-bottom: 1rem;
    }
    .real-time-badge {
        background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: bold;
        display: inline-block;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
    }
    .status-running {
        color: #28a745;
        font-weight: bold;
        font-size: 1.2rem;
    }
    .status-stopped {
        color: #dc3545;
        font-weight: bold;
        font-size: 1.2rem;
    }
    .connection-status {
        position: fixed;
        top: 10px;
        right: 10px;
        z-index: 999;
        padding: 0.5rem;
        border-radius: 10px;
        font-size: 0.8rem;
    }
    .connected {
        background-color: #d4edda;
        color: #155724;
        border: 1px solid #c3e6cb;
    }
    .disconnected {
        background-color: #f8d7da;
        color: #721c24;
        border: 1px solid #f5c6cb;
    }
    .price-update {
        animation: highlight 1s ease-in-out;
    }
    @keyframes highlight {
        0% { background-color: rgba(255, 193, 7, 0.3); }
        100% { background-color: transparent; }
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .trade-alert {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        animation: slideIn 0.5s ease-out;
    }
    @keyframes slideIn {
        from { transform: translateX(-100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
</style>
""", unsafe_allow_html=True)

def make_request(endpoint, method="GET", data=None):
    """Make API request with error handling"""
    try:
        url = f"{API_BASE_URL}{endpoint}"
        if method == "GET":
            response = requests.get(url, timeout=5)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=5)
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code}")
            return None
    except requests.exceptions.ConnectionError:
        st.error("🔴 Cannot connect to the trading bot API. Make sure the server is running on http://localhost:8080")
        return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None

def get_bot_status():
    """Get current bot status with real-time data"""
    return make_request("/api/v1/bot/status")

def start_bot(amount):
    """Start the trading bot with specified amount"""
    return make_request(f"/api/v1/bot/start?trading_amount={amount}", "POST")

def stop_bot():
    """Stop the trading bot"""
    return make_request("/api/v1/bot/stop", "POST")

def get_system_health():
    """Get system health status"""
    return make_request("/api/v1/system/health")

# Real-time data functions
def update_price_history(price: float):
    """Update price history for real-time chart"""
    current_time = datetime.now()
    st.session_state.price_history.append({
        'timestamp': current_time,
        'price': price
    })
    
    # Keep only last 100 points
    if len(st.session_state.price_history) > 100:
        st.session_state.price_history = st.session_state.price_history[-100:]

def update_real_time_status(status_data: Dict):
    """Update real-time status data"""
    st.session_state.real_time_data = status_data
    st.session_state.last_update = datetime.now()
    
    # Update price history
    if 'current_price' in status_data:
        update_price_history(status_data['current_price'])

def show_connection_status():
    """Show WebSocket connection status"""
    if st.session_state.ws_connected:
        st.markdown(
            '<div class="connection-status connected">🟢 Real-Time Connected</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div class="connection-status disconnected">🔴 Polling Mode</div>',
            unsafe_allow_html=True
        )

def create_real_time_price_chart():
    """Create real-time price chart"""
    if not st.session_state.price_history:
        return None
    
    df = pd.DataFrame(st.session_state.price_history)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['price'],
        mode='lines+markers',
        name='BTC Price',
        line=dict(color='#f7931a', width=2),
        marker=dict(size=4)
    ))
    
    fig.update_layout(
        title="Real-Time BTC Price",
        xaxis_title="Time",
        yaxis_title="Price (USDT)",
        height=300,
        showlegend=False,
        margin=dict(l=0, r=0, t=30, b=0)
    )
    
    return fig

def show_trade_alert(trade_data):
    """Show animated trade alert"""
    trade_type = trade_data.get('type', 'BUY')
    price = trade_data.get('price', 0)
    quantity = trade_data.get('quantity', 0)
    
    if trade_type == 'BUY':
        emoji = "🟢"
        color = "#28a745"
    else:
        emoji = "🔴"
        color = "#dc3545"
    
    st.markdown(f"""
    <div class="trade-alert" style="border-left: 4px solid {color};">
        <strong>{emoji} {trade_type} EXECUTED</strong><br>
        Price: ${price:.2f} | Quantity: {quantity:.6f} BTC<br>
        <small>Time: {datetime.now().strftime('%H:%M:%S')}</small>
    </div>
    """, unsafe_allow_html=True)

# Main App
def main():
    # Show connection status
    show_connection_status()
    
    # Header with real-time badge
    st.markdown('''
    <div class="main-header">
        ₿ Real-Time BTC Trading Bot 
        <span class="real-time-badge">LIVE</span>
    </div>
    ''', unsafe_allow_html=True)
    
    # Auto-refresh placeholder
    refresh_placeholder = st.empty()
    
    # Sidebar - Bot Controls
    with st.sidebar:
        st.header("🎛️ Bot Controls")
        
        # Trading Amount Input
        trading_amount = st.number_input(
            "Trading Amount (USDT)",
            min_value=10.0,
            max_value=10000.0,
            value=100.0,
            step=10.0,
            help="Amount in USDT to trade with"
        )
        
        # Bot Control Buttons
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🚀 Start Bot", type="primary", use_container_width=True):
                result = start_bot(trading_amount)
                if result and result.get("success"):
                    st.success("✅ Real-time bot started!")
                    time.sleep(0.5)  # Brief pause for user feedback
                    st.rerun()
                else:
                    st.error("❌ Failed to start bot")
        
        with col2:
            if st.button("🛑 Stop Bot", type="secondary", use_container_width=True):
                result = stop_bot()
                if result and result.get("success"):
                    # Store final summary in session state
                    if result.get("final_summary"):
                        st.session_state.final_summary = result["final_summary"]
                        st.session_state.show_summary = True
                    
                    st.success("✅ Bot stopped!")
                    time.sleep(0.5)  # Brief pause for user feedback
                    st.rerun()
                else:
                    st.error("❌ Failed to stop bot")
        
        st.divider()
        
        # Real-time Settings
        st.subheader("⚡ Real-Time Settings")
        auto_refresh = st.checkbox("Auto Refresh", value=True, help="Automatically refresh data")
        refresh_interval = st.slider("Refresh Interval (seconds)", 1, 10, 3)
        
        st.divider()
        
        # System Health
        st.subheader("🔧 System Health")
        health = get_system_health()
        if health:
            if health.get("status") == "healthy":
                st.success("✅ System Healthy")
            else:
                st.warning("⚠️ System Issues")
        else:
            st.error("❌ Cannot reach API")
    
    # Main Content Area
    main_container = st.container()
    
    with main_container:
        # Show final summary if available
        if st.session_state.show_summary and st.session_state.final_summary:
            summary = st.session_state.final_summary
            
            st.markdown("### 🏁 Final Trading Session Summary")
            
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                profit = summary.get('total_pnl', 0)
                if profit > 0:
                    st.metric("Total Result", f"+${profit:.2f}", delta=f"+{(profit/summary.get('final_value', 1)*100):.1f}%")
                elif profit < 0:
                    st.metric("Total Result", f"${profit:.2f}", delta=f"{(profit/summary.get('final_value', 1)*100):.1f}%")
                else:
                    st.metric("Total Result", "$0.00", delta="0.0%")
            
            with col2:
                st.metric("Final Value", f"${summary.get('final_value', 0):.2f}")
            
            with col3:
                st.metric("Total Trades", summary.get('total_trades', 0))
            
            with col4:
                if st.button("✖️ Dismiss", help="Close this summary"):
                    st.session_state.show_summary = False
                    st.rerun()
            
            # Detailed breakdown
            with st.expander("📊 Detailed Breakdown", expanded=False):
                detail_col1, detail_col2 = st.columns(2)
                
                with detail_col1:
                    st.write("**Final Position:**")
                    st.write(f"• Buy Price: ${summary.get('buy_price', 0):.2f}")
                    st.write(f"• Sell Price: ${summary.get('sell_price', 0):.2f}")
                    st.write(f"• BTC Quantity: {summary.get('btc_quantity', 0):.6f}")
                
                with detail_col2:
                    final_trade_profit = summary.get('final_trade_profit', 0)
                    final_trade_percent = summary.get('final_trade_percent', 0)
                    
                    st.write("**Last Trade Result:**")
                    if final_trade_profit > 0:
                        st.success(f"• Profit: +${final_trade_profit:.2f}")
                        st.success(f"• Return: +{final_trade_percent:.2f}%")
                    else:
                        st.error(f"• Loss: ${final_trade_profit:.2f}")
                        st.error(f"• Return: {final_trade_percent:.2f}%")
            
            st.divider()
        
        # Get bot status
        bot_status = get_bot_status()
        
        if not bot_status:
            st.error("🔴 Unable to connect to the trading bot. Please make sure the server is running.")
            st.info("To start the server, run: `python run_server.py` in the backend directory")
            return
        
        # Update real-time data
        if bot_status.get("success"):
            status_data = bot_status.get("data", {})
            update_real_time_status(status_data)
            
            # Bot Status Banner
            status_col1, status_col2, status_col3 = st.columns([2, 1, 1])
            
            with status_col1:
                if status_data.get("is_running"):
                    st.markdown(
                        '<div class="status-running">🟢 BOT IS RUNNING - REAL-TIME MODE</div>', 
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        '<div class="status-stopped">🔴 BOT IS STOPPED</div>', 
                        unsafe_allow_html=True
                    )
            
            with status_col2:
                connection_type = status_data.get('connection_type', 'API Fallback')
                if connection_type == 'WebSocket':
                    st.success(f"📡 {connection_type}")
                else:
                    st.warning(f"📊 {connection_type}")
            
            with status_col3:
                last_update = status_data.get('last_price_update_seconds_ago', 0)
                if last_update < 5:
                    st.success(f"🕒 {last_update:.1f}s ago")
                elif last_update < 30:
                    st.warning(f"🕒 {last_update:.1f}s ago")
                else:
                    st.error(f"🕒 {last_update:.1f}s ago")
            
            st.divider()
            
            # Real-time Price Chart
            price_chart_col, metrics_col = st.columns([2, 1])
            
            with price_chart_col:
                st.subheader("📈 Real-Time BTC Price")
                price_chart = create_real_time_price_chart()
                if price_chart:
                    st.plotly_chart(price_chart, use_container_width=True)
                else:
                    st.info("📊 Collecting real-time price data...")
            
            with metrics_col:
                st.subheader("⚡ Live Metrics")
                
                # Current Price (highlighted on update)
                current_price = status_data.get('current_price', 0)
                st.markdown(f"""
                <div class="metric-card">
                    <h3 style="margin:0; color: white;">💰 Current Price</h3>
                    <h2 style="margin:0; color: #ffd700;">${current_price:.2f}</h2>
                </div>
                """, unsafe_allow_html=True)
                
                st.write("")  # Spacing
                
                # Position Status
                position = status_data.get('current_position', 'None')
                if position == 'BUY':
                    st.success(f"🔵 Holding BTC")
                    buy_price = status_data.get('buy_price', 0)
                    btc_qty = status_data.get('btc_quantity', 0)
                    unrealized_pnl = status_data.get('unrealized_pnl', 0)
                    
                    st.write(f"**Buy Price:** ${buy_price:.2f}")
                    st.write(f"**Quantity:** {btc_qty:.6f} BTC")
                    
                    if unrealized_pnl > 0:
                        st.success(f"**P&L:** +${unrealized_pnl:.2f}")
                    else:
                        st.error(f"**P&L:** ${unrealized_pnl:.2f}")
                else:
                    st.info("💰 Holding USDT")
                    st.write("Scanning for opportunities...")
            
            # Metrics Dashboard
            st.subheader("📊 Trading Dashboard")
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric(
                    "Trading Amount",
                    f"${status_data.get('trading_amount', 0):.2f}",
                    help="Amount allocated for trading"
                )
            
            with col2:
                total_profit = status_data.get('total_profit', 0)
                session_return = status_data.get('session_return_percent', 0)
                profit_delta = f"{session_return:.2f}%" if session_return != 0 else None
                st.metric(
                    "Session Return", 
                    f"${total_profit:.2f}",
                    delta=profit_delta,
                    help="Total profit/loss from current session"
                )
            
            with col3:
                trade_count = status_data.get('trade_count', 0)
                st.metric(
                    "Completed Trades", 
                    trade_count,
                    help="Number of completed trades"
                )
            
            with col4:
                error_count = status_data.get('error_count', 0)
                st.metric(
                    "Error Count",
                    error_count,
                    delta=-error_count if error_count > 0 else None,
                    help="Number of errors encountered"
                )
            
            with col5:
                test_mode = status_data.get('test_mode', False)
                mode_text = "TEST" if test_mode else "LIVE"
                mode_color = "🧪" if test_mode else "🚀"
                st.metric(
                    "Mode",
                    f"{mode_color} {mode_text}",
                    help="Current trading mode"
                )
        
        else:
            st.error("Failed to get bot status")
    
    # Auto-refresh mechanism (only if bot is running and no summary is being shown)
    if (auto_refresh and 
        st.session_state.real_time_data.get('is_running') and 
        not st.session_state.show_summary):
        time.sleep(refresh_interval)
        st.rerun()
    
    # Manual refresh button (always available)
    refresh_col1, refresh_col2 = st.columns([1, 4])
    with refresh_col1:
        if st.button("🔄 Refresh", help="Manually refresh all data"):
            st.rerun()
    
    with refresh_col2:
        if st.session_state.show_summary:
            st.info("💡 Auto-refresh paused while showing summary")
        elif st.session_state.real_time_data.get('is_running'):
            st.success("⚡ Real-time updates active")
        else:
            st.warning("⏸️ Bot stopped - manual refresh only")

# Footer
def show_footer():
    st.divider()
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 1rem;'>
        🤖 Real-Time Automated BTC Trading Bot | 
        <a href="http://localhost:8080/docs" target="_blank">API Docs</a> | 
        <a href="http://localhost:8080/api/v1/system/health" target="_blank">Health Check</a> |
        <span style="color: #f7931a;">⚡ WebSocket Enabled</span>
    </div>
    """, unsafe_allow_html=True)

# Real-time data ticker at bottom
def show_real_time_ticker():
    """Show a real-time data ticker at the bottom"""
    if st.session_state.real_time_data:
        data = st.session_state.real_time_data
        last_update = st.session_state.last_update
        
        if last_update:
            time_ago = (datetime.now() - last_update).total_seconds()
            update_text = f"Last updated: {time_ago:.1f}s ago"
        else:
            update_text = "No recent updates"
        
        st.markdown(f"""
        <div style='position: fixed; bottom: 0; left: 0; right: 0; background: rgba(0,0,0,0.8); color: white; padding: 0.5rem; text-align: center; z-index: 999;'>
            💰 BTC: ${data.get('current_price', 0):.2f} | 
            📊 Position: {data.get('current_position', 'None')} | 
            💎 Profit: ${data.get('total_profit', 0):.2f} | 
            🔄 {update_text}
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
    show_real_time_ticker()
    show_footer()