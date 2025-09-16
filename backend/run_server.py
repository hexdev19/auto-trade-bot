#!/usr/bin/env python3
"""
Simple server runner for the AutoTrade API
"""
import uvicorn
from app.main import app
from app.config import PORT

if __name__ == "__main__":
    print("🚀 Starting AutoTrade API...")    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(PORT),
        reload=False,
        log_level="info"
    )