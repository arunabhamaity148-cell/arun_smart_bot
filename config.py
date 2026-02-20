"""
ARUNABHA FINAL v4.0 - COMPLETE CONFIG
Market Adaptive | Indian Exchange Ready | TDS/GST Included
"""

import os
from typing import Dict, Any

# ======================================================
# TELEGRAM SETTINGS
# ======================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
WEBHOOK_PORT = int(os.getenv("PORT", "8080"))

# ======================================================
# EXCHANGE SETTINGS (Binance for data only)
# ======================================================
PRIMARY_EXCHANGE = "binance"
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET = os.getenv("BINANCE_SECRET", "")

# Indian Exchange Settings (for profit calculation)
INDIAN_EXCHANGE = "CoinDCX"  # or "Delta"
TDS_RATE = 1.0  # 1% TDS on profit
GST_RATE = 18.0  # 18% GST on brokerage

# ======================================================
# TRADING PAIRS
# ======================================================
TRADING_PAIRS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
TIMEFRAMES = ["5m", "15m", "1h"]
PRIMARY_TF = "15m"

# ======================================================
# CAPITAL & RISK (₹1 Lakh)
# ======================================================
ACCOUNT_SIZE = 100000  # ₹1,00,000
RISK_PER_TRADE = 1.0  # 1% = ₹1000 risk per trade
MAX_LEVERAGE = 15  # You'll use manually

# ======================================================
# CONFIDENCE THRESHOLDS (was magic numbers)
# ======================================================
CONFIDENCE = {
    "MIN_CONFIDENCE_ALLOW": 25,      # ২৫% কনফিডেন্স থাকলে ট্রেড করতে দেবে
    "MIN_CONFIDENCE_DIRECTION": 30,   # ডিরেকশন মিসম্যাচ হলেও ট্রেড করবে
    "MIN_CONFIDENCE_FORCE": 20,       # ফোর্স ট্রেডের জন্য
    "ADX_HIGH_CONFIDENCE": 25,        # ADX ২৫+ হলে হাই কনফিডেন্স
    "ADX_MED_CONFIDENCE": 20,         # ADX ২০-২৫ মিড কনফিডেন্স
}

# ======================================================
# MARKET ADAPTIVE SETTINGS
# ======================================================
MARKET_CONFIGS = {
    "TRENDING": {
        "min_score": 25,
        "min_filters": 3,
        "min_rr": 2.0,
        "max_trades": 6,
        "sl_mult": 1.5,
        "tp_mult": 3.0,
        "position_size": 1.0
    },
    "CHOPPY": {
        "min_score": 20,
        "min_filters": 2,
        "min_rr": 1.5,
        "max_trades": 4,
        "sl_mult": 1.2,
        "tp_mult": 1.8,
        "position_size": 0.8
    },
    "HIGH_VOL": {
        "min_score": 30,
        "min_filters": 4,
        "min_rr": 2.5,
        "max_trades": 3,
        "sl_mult": 1.0,
        "tp_mult": 2.5,
        "position_size": 0.5
    }
}

# ======================================================
# TECHNICAL INDICATORS
# ======================================================
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
EMA_FAST = 9
EMA_SLOW = 21
EMA_TREND = 200
VOLUME_MULT = 1.2
ATR_PERIOD = 14

# ======================================================
# TRADE MANAGEMENT
# ======================================================
BREAK_EVEN_AT = 0.4  # Move SL to entry at 0.4R
PARTIAL_EXIT_AT = 0.8  # Take 50% profit at 0.8R
MAX_CONSECUTIVE_LOSS = 2  # Stop after 2 losses
MAX_DAILY_LOSS = 3.0  # Stop if 3% down in a day
COOLDOWN_MINUTES = 20

# ======================================================
# FEAR & GREED
# ======================================================
FEAR_GREED_API_URL = "https://api.alternative.me/fng/?limit=1"
FEAR_INDEX_THRESHOLD = 80  # Don't trade above 80 (extreme greed)

# ======================================================
# MARKET SESSIONS (IST)
# ======================================================
BEST_TIMES = [
    (13, 15, "London Open"),   # 1PM-3PM
    (18, 20, "NY Open"),       # 6PM-8PM
    (7, 9, "Asia Open")        # 7AM-9AM
]

AVOID_TIMES = [
    (10, 11, "Lunch"),         # 10AM-11AM
    (23, 1, "Dead Zone")       # 11PM-1AM
]

# ======================================================
# PROFIT CALCULATION (Indian Exchange)
# ======================================================
def calculate_indian_profit(entry: float, exit: float, qty: float, side: str) -> Dict[str, float]:
    """Calculate profit after TDS/GST for Indian exchanges"""
    if side == "LONG":
        gross_pnl = (exit - entry) * qty
    else:
        gross_pnl = (entry - exit) * qty
    
    if gross_pnl <= 0:
        return {"net_pnl": gross_pnl, "tds": 0, "gst": 0, "gross": gross_pnl}
    
    tds = gross_pnl * (TDS_RATE / 100)
    gst = gross_pnl * (GST_RATE / 100)  # Simplified, actual calculation differs
    net_pnl = gross_pnl - tds - gst
    
    return {
        "gross": round(gross_pnl, 2),
        "tds": round(tds, 2),
        "gst": round(gst, 2),
        "net_pnl": round(net_pnl, 2)
    }