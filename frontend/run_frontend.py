#!/usr/bin/env python3
"""
Streamlit Frontend for BTC Trading Bot
"""

import subprocess
import sys
import os

def main():
    print("🚀 Starting BTC Trading Bot Dashboard...")
    print("📊 Frontend will be available at: http://localhost:8501")
    print("🤖 Make sure the backend API is running at: http://localhost:8080")
    print()
    
    try:
        # Run streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.port", "8501",
            "--server.address", "0.0.0.0",
            "--theme.base", "light",
            "--theme.primaryColor", "#f7931a"
        ])
    except KeyboardInterrupt:
        print("\n👋 Frontend stopped")
    except Exception as e:
        print(f"❌ Error starting frontend: {e}")

if __name__ == "__main__":
    main()